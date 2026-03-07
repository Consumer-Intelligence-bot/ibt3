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

You will receive brand metrics compared to market benchmarks, each tagged
AHEAD, BELOW, or IN LINE.

Return ONLY valid JSON with exactly three keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences>"
}

Rules for the headline (one sentence):
- If shopping rate is BELOW market: start with "Fewer {brand} customers shop around than average..."
- If shopping rate is IN LINE:      start with "Customers shop at the market rate..."
- If shopping rate is AHEAD:        start with "More {brand} customers shop around than average..."
Then complete the headline based on what drives the share outcome:
- If share GAINS and retention is AHEAD: "...and {brand} keeps more of them, growing share."
- If share FLAT  and retention is AHEAD: "...and {brand} retains them well, holding share steady."
- If share FALLS and retention is AHEAD: "...and {brand} retains well, but weak new business trims share."
- If retention is IN LINE and share gains: "...converting at the market rate, with new business lifting share."
- Adapt logically for other combinations.

Subtitle (one sentence): Summarise what retention and new business did to share overall.

Paragraph (3-4 sentences of plain English explanation):
- What the shopping rate tells us
- Whether retention helped or hurt
- What new business contributed
- The net share outcome

Do not use bullet points. Do not use jargon. Write in British English.
Do not mention sample sizes or survey methodology.
"""


def _derive_tag(ins_val: float, mkt_val: float) -> str:
    """Return AHEAD / BELOW / IN LINE tag (matching prompt expectations)."""
    gap_pp = (ins_val - mkt_val) * 100
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "IN LINE"
    return "AHEAD" if gap_pp > 0 else "BELOW"


def _format_metrics_for_prompt(d: dict) -> str:
    """Convert the headline metrics dict into the user-message for the API."""
    pre_pp = d["pre_share"] * 100
    post_pp = d["after_share"] * 100
    delta_pp = d["share_delta"] * 100

    shop_tag = _derive_tag(d["shop_pct"], d["mkt_shop_pct"])
    ret_tag = _derive_tag(d["retained_pct"], d["mkt_retained_pct"])
    stay_tag = _derive_tag(d["shop_stay_pct"], d["mkt_shop_stay_pct"])
    biz_tag = _derive_tag(d["new_biz_pct"], d["mkt_new_biz_pct"])

    return (
        f"Brand: {d['insurer']}\n"
        f"Share:\n"
        f"  Pre-renewal: {pre_pp:.1f}%\n"
        f"  Post-renewal: {post_pp:.1f}%\n"
        f"  Net movement: {delta_pp:+.1f} pts\n"
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
