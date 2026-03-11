"""
AI-generated narrative summaries for both S&S and Claims dashboards.

Uses the Anthropic API (Claude Opus) to produce headline, subtitle, and
explanatory paragraph. Falls back to None when the API key is absent or
any error occurs.
"""

import json
import logging
import os
from collections import OrderedDict

import anthropic

from lib.config import NARRATIVE_ENABLED, NARRATIVE_MODEL, NEUTRAL_GAP_THRESHOLD

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# S&S Narrative (Shopping & Switching Headline page)
# ---------------------------------------------------------------------------

_SS_SYSTEM_PROMPT = """\
You write concise market intelligence summaries for a UK motor insurance dashboard.
Your audience is senior leaders at insurance companies.

You will receive brand metrics compared to market benchmarks, each tagged
AHEAD, BELOW, or IN LINE.

Return ONLY valid JSON with exactly these keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences>",
  "descriptions": {
    "shopping_rate": "<1-2 sentences>",
    "retention": "<1-2 sentences>",
    "shopped_and_stayed": "<1-2 sentences>",
    "new_business": "<1-2 sentences>",
    "inbound_switching": "<1-2 sentences>"
  }
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

Paragraph (3-5 sentences of plain English explanation):
- What the shopping rate tells us
- Whether retention helped or hurt
- What inbound switching from competitors contributed
- What new-to-market business contributed
- The net share outcome

Descriptions (1-2 sentences each explaining what the metric means for the brand):
- shopping_rate: What the brand's shopping rate tells us compared to market
- retention: How the brand's retention compares and what it means
- shopped_and_stayed: What the shopped-and-stayed rate reveals about competitiveness
- new_business: What the new business acquisition rate means for the brand
- inbound_switching: What the brand's ability to attract switchers from competitors tells us

Do not use bullet points. Do not use jargon. Write in British English.
Do not mention sample sizes or survey methodology.
"""


def _derive_tag(ins_val: float, mkt_val: float) -> str:
    gap_pp = (ins_val - mkt_val) * 100
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "IN LINE"
    return "AHEAD" if gap_pp > 0 else "BELOW"


def _format_ss_metrics(d: dict) -> str:
    pre_pp = d["pre_share"] * 100
    post_pp = d["after_share"] * 100
    delta_pp = d["share_delta"] * 100

    shop_tag = _derive_tag(d["shop_pct"], d["mkt_shop_pct"])
    ret_tag = _derive_tag(d["retained_pct"], d["mkt_retained_pct"])
    stay_tag = _derive_tag(d["shop_stay_pct"], d["mkt_shop_stay_pct"])
    biz_tag = _derive_tag(d["new_biz_pct"], d["mkt_new_biz_pct"])
    inbound_tag = _derive_tag(d["inbound_switch_pct"], d["mkt_inbound_switch_pct"])

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
        f"Inbound switching: {d['inbound_switch_pct'] * 100:.1f}% vs market "
        f"{d['mkt_inbound_switch_pct'] * 100:.1f}% — {inbound_tag}\n"
        f"New business acquisition: {d['new_biz_pct'] * 100:.1f}% vs market "
        f"{d['mkt_new_biz_pct'] * 100:.1f}% — {biz_tag}\n\n"
        f"Write the headline, subtitle, and explanatory paragraph for this brand."
    )


# ---------------------------------------------------------------------------
# Claims Narrative
# ---------------------------------------------------------------------------

_CLAIMS_SYSTEM_PROMPT = """\
You write concise claims satisfaction summaries for a UK motor insurance dashboard.
Your audience is senior leaders at insurance companies.

You will receive an insurer's claims satisfaction data compared to market benchmarks.

Return ONLY valid JSON with exactly three keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences>"
}

Rules for the headline (one sentence):
- If the insurer scores ABOVE market: "{brand} delivers above-market claims satisfaction..."
- If the insurer scores AT market: "{brand} delivers market-average claims satisfaction..."
- If the insurer scores BELOW market: "{brand}'s claims satisfaction falls below market..."
- Complete with star rating context: "...earning {stars} stars."

Subtitle (one sentence): Summarise the gap to market and confidence level.

Paragraph (3-4 sentences of plain English explanation):
- Overall satisfaction position
- Key diagnostic strengths (highest-rated statements vs market)
- Key diagnostic weaknesses (lowest-rated statements vs market)
- What this means for the brand

Do not use bullet points. Do not use jargon. Write in British English.
Do not mention sample sizes or survey methodology.
"""


def _format_claims_metrics(
    insurer: str,
    mean: float,
    market_mean: float,
    gap: float,
    stars: int | None,
    diagnostics: list[dict] | None,
) -> str:
    position = "ABOVE" if gap > 0.1 else ("BELOW" if gap < -0.1 else "AT")
    stars_str = f"{stars}/5 stars" if stars else "N/A"

    lines = [
        f"Brand: {insurer}",
        f"Overall satisfaction: {mean:.2f} vs market {market_mean:.2f} (gap: {gap:+.2f}) — {position}",
        f"Star rating: {stars_str}",
    ]

    if diagnostics:
        lines.append("\nDiagnostic statements (insurer vs market):")
        for d in diagnostics[:8]:
            g = d.get("gap", 0)
            tag = "ABOVE" if g > 0.1 else ("BELOW" if g < -0.1 else "AT")
            lines.append(
                f"  {d['subject']}: {d['ins_mean']:.2f} vs {d['mkt_mean']:.2f} (gap: {g:+.2f}) — {tag}"
            )

    lines.append("\nWrite the headline, subtitle, and explanatory paragraph for this brand.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

_MAX_CACHE_SIZE = 200
_narrative_cache: OrderedDict[str, dict] = OrderedDict()


def _cache_key_ss(d: dict) -> str:
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
        round(d["inbound_switch_pct"] * 1000),
        round(d["mkt_inbound_switch_pct"] * 1000),
        round(d["new_biz_pct"] * 1000),
        round(d["mkt_new_biz_pct"] * 1000),
    )
    return f"ss:{parts}"


def _cache_key_claims(insurer: str, mean: float, market_mean: float) -> str:
    return f"claims:{insurer}:{round(mean * 100)}:{round(market_mean * 100)}"


def _call_api(system_prompt: str, user_content: str) -> dict | None:
    """Call Claude API and parse JSON response."""
    if not os.getenv("ANTHROPIC_API_KEY"):
        log.info("ANTHROPIC_API_KEY not set; skipping narrative generation")
        return None
    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=700,
            system=system_prompt,
            messages=[{"role": "user", "content": user_content}],
        )
        if not response.content:
            log.warning("API returned no content blocks (stop_reason=%s)", response.stop_reason)
            return None
        text = response.content[0].text.strip()
        if not text:
            log.warning("API returned empty text; skipping narrative")
            return None
        # Strip markdown code fences the model sometimes wraps around JSON
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[: -3].strip()
        log.debug("Raw API response text: %s", text[:500])
        result = json.loads(text)
        for k in ("headline", "subtitle", "paragraph"):
            if k not in result:
                raise KeyError(f"Missing key in API response: {k}")
        return result
    except Exception:
        log.exception("Narrative generation failed; caller will use fallback text")
        return None


def _cached_call(cache_key: str, system_prompt: str, user_content: str) -> dict | None:
    """Check cache, call API if needed, store result."""
    if cache_key in _narrative_cache:
        _narrative_cache.move_to_end(cache_key)
        return _narrative_cache[cache_key]

    result = _call_api(system_prompt, user_content)
    if result:
        _narrative_cache[cache_key] = result
        if len(_narrative_cache) > _MAX_CACHE_SIZE:
            _narrative_cache.popitem(last=False)
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_narrative(metrics: dict) -> dict | None:
    """Generate AI narrative for the S&S Headline page.

    Returns {"headline": str, "subtitle": str, "paragraph": str} or None.
    """
    if not NARRATIVE_ENABLED:
        return None
    key = _cache_key_ss(metrics)
    user_content = _format_ss_metrics(metrics)
    return _cached_call(key, _SS_SYSTEM_PROMPT, user_content)


def generate_claims_narrative(
    insurer: str,
    mean: float,
    market_mean: float,
    gap: float,
    stars: int | None = None,
    diagnostics: list[dict] | None = None,
) -> dict | None:
    """Generate AI narrative for the Claims Intelligence page.

    Returns {"headline": str, "subtitle": str, "paragraph": str} or None.
    """
    if not NARRATIVE_ENABLED:
        return None
    key = _cache_key_claims(insurer, mean, market_mean)
    user_content = _format_claims_metrics(insurer, mean, market_mean, gap, stars, diagnostics)
    return _cached_call(key, _CLAIMS_SYSTEM_PROMPT, user_content)
