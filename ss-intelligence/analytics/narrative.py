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

You will receive brand metrics compared to market benchmarks. Each metric is
tagged AHEAD, BELOW, or IN LINE. The net share movement is tagged FELL, FLAT,
or GREW.

Return ONLY valid JSON with exactly three keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences>"
}

CRITICAL — the headline must lead with the net share outcome. Net share change
is the outcome metric; shopping rate, retention, and conversion are process
metrics. The outcome takes precedence.

Headline rules (one sentence):
- If share FELL:  "{brand} lost share at renewal despite [best positive factor]."
  Tone: cautionary. Do not use positive framing words (keeps more, beats market,
  ahead) as the primary message when the net outcome is negative.
- If share FLAT:  "{brand} held share steady at renewal, [brief driver]."
  Tone: neutral.
- If share GREW:  "{brand} grew share at renewal, driven by [primary driver]."
  Tone: positive.

After stating the outcome, name the primary driver (retention or new business)
and, if relevant, the offsetting factor. Be specific — use the actual metric
values rather than vague language.

Subtitle (one sentence): Reinforce and expand on the headline. It must not
contradict the headline tone. If the headline reports a loss, the subtitle
must acknowledge the loss — do not quietly mention share loss in a subtitle
that otherwise sounds positive.

Paragraph (3-4 sentences of plain English explanation):
1. The net share outcome and its magnitude
2. Whether retention helped or hurt (with numbers)
3. What new business contributed (with numbers)
4. What the shopping rate tells us

Be direct and specific. Avoid euphemism. A good headline names both the
outcome and the primary driver.

Do not use bullet points. Do not use jargon. Write in British English.
Do not mention sample sizes or survey methodology.
"""


def _derive_tag(ins_val: float, mkt_val: float) -> str:
    """Return AHEAD / BELOW / IN LINE tag (matching prompt expectations)."""
    gap_pp = (ins_val - mkt_val) * 100
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "IN LINE"
    return "AHEAD" if gap_pp > 0 else "BELOW"


def _share_movement_tag(delta: float) -> str:
    """Return FELL / FLAT / GREW based on net share change (as proportion)."""
    delta_pp = delta * 100
    if delta_pp < -NEUTRAL_GAP_THRESHOLD:
        return "FELL"
    if delta_pp > NEUTRAL_GAP_THRESHOLD:
        return "GREW"
    return "FLAT"


def _format_metrics_for_prompt(d: dict) -> str:
    """Convert the headline metrics dict into the user-message for the API."""
    pre_pp = d["pre_share"] * 100
    post_pp = d["after_share"] * 100
    delta_pp = d["share_delta"] * 100

    share_tag = _share_movement_tag(d["share_delta"])
    shop_tag = _derive_tag(d["shop_pct"], d["mkt_shop_pct"])
    ret_tag = _derive_tag(d["retained_pct"], d["mkt_retained_pct"])
    stay_tag = _derive_tag(d["shop_stay_pct"], d["mkt_shop_stay_pct"])
    biz_tag = _derive_tag(d["new_biz_pct"], d["mkt_new_biz_pct"])

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
