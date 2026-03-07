"""
AI-generated narrative summaries for the Headline page.

Uses the Anthropic API to produce a headline, subtitle, and explanatory
paragraph tailored to the selected insurer's metrics vs. market benchmarks.
Falls back to None (caller supplies hardcoded text) when the API key is
absent or any error occurs.
"""

import json
import logging
import os
from collections import OrderedDict

from config import NARRATIVE_ENABLED, NARRATIVE_MODEL, NEUTRAL_GAP_THRESHOLD

log = logging.getLogger(__name__)

# ── Prompt ────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You write concise market intelligence summaries for a UK motor insurance dashboard.
Your audience is senior leaders at insurance companies.

You will receive brand metrics compared to market benchmarks. Each metric
carries a sentiment tag that reflects its ACTUAL impact on the brand — pay
close attention to these tags, as some metrics are inverted (see below).

The net share movement is tagged FELL, FLAT, or GREW.

Return ONLY valid JSON with exactly three keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences>"
}

─── METRIC INTERPRETATION (READ CAREFULLY) ───

Shopping rate is INVERTED — higher than market is BAD:
  - ELEVATED = above market = more customers are dissatisfied and looking to
    leave. This is churn intent, not competitive engagement. Never frame it
    positively.
  - IN LINE or BELOW MARKET = neutral or positive.

Retention: below market is always negative. The brand loses a higher share
of renewing customers than peers.

Shopped and stayed: below market is always negative. When customers test
alternatives, the brand loses more of them than peers do. This signals a
pricing or proposition weakness at the point of decision.

New business acquisition: below market means the brand is not compensating
for retention losses through inflows. A value of 0% when market is positive
is a significant gap — flag it explicitly.

─── THE CAUSAL CHAIN ───

Read the metrics as a connected sequence, not in isolation:
  High shopping rate → more customers test alternatives
    → low shopped-and-stayed → more customers leave
      → low retention → share loss
        → not recovered by new business → net share decline

If this chain is present in the data, the narrative MUST reflect it end to
end. Do not interrupt the chain with positive framing on any individual step.

─── HEADLINE RULES (one sentence) ───

The headline MUST lead with the net share outcome.

- If share FELL: "{brand} lost share at renewal. [Primary driver of loss]."
  Tone: cautionary. No positive framing words when the net outcome is negative.
- If share FLAT: "{brand} held share steady at renewal, [brief driver]."
  Tone: neutral.
- If share GREW: "{brand} grew share at renewal, driven by [primary driver]."
  Tone: positive.

After stating the outcome, name the primary driver and, if relevant, the
offsetting factor. Use actual metric values, not vague language.

─── SUBTITLE (one sentence) ───

Reinforce and expand on the headline. Must not contradict headline tone.
If the headline reports a loss, the subtitle must acknowledge the loss.
Do not write a positive subtitle after a negative headline.

─── PARAGRAPH (3-4 sentences) ───

1. The net share outcome and its magnitude
2. Whether retention helped or hurt (with numbers vs market)
3. What new business contributed (with numbers vs market)
4. What the shopping rate tells us about churn intent

─── PROHIBITED PATTERNS ───

When net share movement is negative, NEVER use:
- "keeps more of them" when retention is below market
- "beats market" when the outcome metric is negative
- "performs better when they do" when shopped-and-stayed is below market
- Any positive label on a metric that contributes to the chain of share loss
- Burying net share loss in a subordinate clause after a positive headline

─── SUMMARY RULE ───

If the net outcome is negative, no individual metric may be framed positively
unless it is genuinely isolated from the chain of loss AND accompanied by an
explicit caveat explaining why it does not mitigate the overall result.

Be direct and specific. Avoid euphemism. Write in British English.
Do not use bullet points. Do not mention sample sizes or methodology.
"""



def _shopping_tag(ins_val: float, mkt_val: float) -> str:
    """Shopping rate is INVERTED — above market is negative (churn intent)."""
    gap_pp = (ins_val - mkt_val) * 100
    if gap_pp > NEUTRAL_GAP_THRESHOLD:
        return "ELEVATED (negative — churn intent)"
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "IN LINE WITH MARKET (neutral)"
    return "BELOW MARKET (positive — less churn intent)"


def _share_movement_tag(delta: float) -> str:
    """Return FELL / FLAT / GREW based on net share change (as proportion)."""
    delta_pp = delta * 100
    if delta_pp < -NEUTRAL_GAP_THRESHOLD:
        return "FELL"
    if delta_pp > NEUTRAL_GAP_THRESHOLD:
        return "GREW"
    return "FLAT"


def _below_above_tag(ins_val: float, mkt_val: float) -> str:
    """Standard tag for metrics where higher = better."""
    gap_pp = (ins_val - mkt_val) * 100
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "IN LINE WITH MARKET"
    return "ABOVE MARKET" if gap_pp > 0 else "BELOW MARKET"


def _format_metrics_for_prompt(d: dict) -> str:
    """Convert the headline metrics dict into the user-message for the API."""
    pre_pp = d["pre_share"] * 100
    post_pp = d["after_share"] * 100
    delta_pp = d["share_delta"] * 100

    share_tag = _share_movement_tag(d["share_delta"])
    shop_tag = _shopping_tag(d["shop_pct"], d["mkt_shop_pct"])
    ret_tag = _below_above_tag(d["retained_pct"], d["mkt_retained_pct"])
    stay_tag = _below_above_tag(d["shop_stay_pct"], d["mkt_shop_stay_pct"])
    biz_tag = _below_above_tag(d["new_biz_pct"], d["mkt_new_biz_pct"])

    return (
        f"Brand: {d['insurer']}\n"
        f"Share:\n"
        f"  Pre-renewal: {pre_pp:.1f}%\n"
        f"  Post-renewal: {post_pp:.1f}%\n"
        f"  Net movement: {delta_pp:+.1f} pts — {share_tag}\n"
        f"Shopping rate: {d['shop_pct'] * 100:.1f}% vs market "
        f"{d['mkt_shop_pct'] * 100:.1f}% — {shop_tag}\n"
        f"Retention: {d['retained_pct'] * 100:.1f}% vs market "
        f"{d['mkt_retained_pct'] * 100:.1f}% — {ret_tag}\n"
        f"Shopped and stayed: {d['shop_stay_pct'] * 100:.1f}% vs market "
        f"{d['mkt_shop_stay_pct'] * 100:.1f}% — {stay_tag}\n"
        f"New business acquisition: {d['new_biz_pct'] * 100:.1f}% vs market "
        f"{d['mkt_new_biz_pct'] * 100:.1f}% — {biz_tag}\n\n"
        f"Write the headline, subtitle, and explanatory paragraph for this brand."
    )


# ── Cache ─────────────────────────────────────────────────────────────────────

_MAX_CACHE_SIZE = 200
_narrative_cache: OrderedDict[str, dict] = OrderedDict()


def _cache_key(d: dict) -> str:
    """Deterministic key from the metrics that affect narrative content."""
    parts = (
        d["insurer"],
        round(d["pre_share"] * 1000),
        round(d["after_share"] * 1000),
        round(d["shop_pct"] * 1000),
        round(d["mkt_shop_pct"] * 1000),
        round(d["retained_pct"] * 1000),
        round(d["mkt_retained_pct"] * 1000),
        round(d["shop_stay_pct"] * 1000),
        round(d["mkt_shop_stay_pct"] * 1000),
        round(d["new_biz_pct"] * 1000),
        round(d["mkt_new_biz_pct"] * 1000),
    )
    return str(parts)


# ── Public API ────────────────────────────────────────────────────────────────

def generate_narrative(metrics: dict) -> dict | None:
    """Generate an AI narrative for the headline page.

    Returns ``{"headline": str, "subtitle": str, "paragraph": str}``
    or ``None`` if disabled, unconfigured, or on error.
    """
    if not NARRATIVE_ENABLED:
        return None

    key = _cache_key(metrics)
    if key in _narrative_cache:
        _narrative_cache.move_to_end(key)
        return _narrative_cache[key]

    if not os.getenv("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY not set; skipping narrative generation")
        return None

    try:
        import anthropic
        client = anthropic.Anthropic()
        user_content = _format_metrics_for_prompt(metrics)
        response = client.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text.strip()
        result = json.loads(text)

        # Validate expected keys
        for k in ("headline", "subtitle", "paragraph"):
            if k not in result:
                raise KeyError(f"Missing key in API response: {k}")

        # Store in cache with LRU eviction
        _narrative_cache[key] = result
        if len(_narrative_cache) > _MAX_CACHE_SIZE:
            _narrative_cache.popitem(last=False)

        return result

    except Exception:
        log.exception("Narrative generation failed; caller will use fallback text")
        return None
