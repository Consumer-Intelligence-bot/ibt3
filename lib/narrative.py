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

IMPORTANT: Follow the fact-observation-prompt pattern for every insight:
1. Lead with the FACT: "{Brand}'s shopping rate is 67%, versus 71% for the market."
2. Then the OBSERVATION: "This is below market, suggesting customers are less inclined to compare."
3. Then the PROMPT: "The top reasons given for not shopping were X, Y, Z. This may warrant investigation."
Never state causation. You can suggest hypotheses and prompt investigation.
"What are the contributing factors?" not "What is driving it?"

Return ONLY valid JSON with exactly these keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences following fact-observation-prompt pattern>",
  "descriptions": {
    "shopping_rate": "<1-2 sentences: fact then observation>",
    "retention": "<1-2 sentences: fact then observation>",
    "shopped_and_stayed": "<1-2 sentences: fact then observation>",
    "new_business": "<1-2 sentences: fact then observation>"
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

Paragraph (3-4 sentences following fact-observation-prompt):
- State the shopping rate fact and observation
- State the retention fact and observation
- State what new business contributed (fact)
- End with a prompt: what should be investigated next

Descriptions (1-2 sentences each, always lead with the fact):
- shopping_rate: State the rate vs market, then what it suggests
- retention: State the rate vs market, then what it means
- shopped_and_stayed: State the rate, then what it reveals about competitiveness
- new_business: State the rate, then what it means for the brand

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


# ---------------------------------------------------------------------------
# Claims Narrative
# ---------------------------------------------------------------------------

_CLAIMS_SYSTEM_PROMPT = """\
You write concise claims satisfaction summaries for a UK motor insurance dashboard.
Your audience is senior leaders at insurance companies.

You will receive an insurer's claims satisfaction data compared to market benchmarks.

IMPORTANT: Follow the fact-observation-prompt pattern for every insight:
1. Lead with the FACT: "{Brand}'s overall claims satisfaction is 4.19, versus 3.87 for the market."
2. Then the OBSERVATION: "This places {brand} in the top quintile, earning five stars."
3. Then the PROMPT: "The strongest areas are X and Y. It may be worth investigating whether Z is contributing."
Never state causation. Suggest hypotheses and prompt investigation.

Return ONLY valid JSON with exactly three keys:

{
  "headline": "<one sentence>",
  "subtitle": "<one sentence>",
  "paragraph": "<3-4 sentences following fact-observation-prompt pattern>"
}

Rules for the headline (one sentence):
- If the insurer scores ABOVE market: "{brand} delivers above-market claims satisfaction..."
- If the insurer scores AT market: "{brand} delivers market-average claims satisfaction..."
- If the insurer scores BELOW market: "{brand}'s claims satisfaction falls below market..."
- Complete with star rating context: "...earning {stars} stars."

Subtitle (one sentence): Summarise the gap to market and confidence level.

Paragraph (3-4 sentences following fact-observation-prompt):
- State the overall satisfaction fact and market comparison
- Identify key diagnostic strengths (top journey statements vs market)
- Identify key diagnostic weaknesses (bottom journey statements vs market)
- End with a prompt about what to investigate or what external data might help

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
    except anthropic.APIError as e:
        log.warning("Anthropic API error during narrative generation: %s", e)
        return None
    except json.JSONDecodeError as e:
        log.warning("Failed to parse narrative JSON response: %s", e)
        return None
    except KeyError as e:
        log.warning("Missing expected key in narrative response: %s", e)
        return None
    except Exception:
        log.exception("Unexpected error during narrative generation; caller will use fallback text")
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


# ---------------------------------------------------------------------------
# Insurer Diagnostic Narrative (Spec Section 13.2 — Funnel Sequence)
# ---------------------------------------------------------------------------

_DIAGNOSTIC_SYSTEM_PROMPT = """\
You write concise insurer diagnostic summaries for a UK motor insurance dashboard.
Your audience is senior leaders at insurance companies.

CRITICAL: Follow the fact-observation-prompt pattern for EVERY finding:
1. FACT: State the metric and its value vs market. Include actual numbers.
2. OBSERVATION: What this suggests about the insurer's position. Do not state causation.
3. PROMPT: What should be investigated next, or what external data would help.

Follow the diagnostic funnel sequence:
1. Shopping rate: What proportion shopped? How does this compare to market?
2. Non-shopper reasons: For those who did not shop, what reasons did they give?
3. Shopper reasons: For those who did shop, what triggered it?
4. Switching rate: Of shoppers, what proportion switched?
5. Retention analysis: Who stayed and why? Who left and why? Who switched in?
6. Net flow: Net winner or net loser? Which insurers are biggest sources/destinations?
7. Anomaly check: Flag anything that deviates meaningfully from market.

Where the data cannot answer a question, say so explicitly and suggest what
external data source would help (e.g. advertising schedules, pricing data).

Return ONLY valid JSON:
{
  "headline": "<one sentence summary of the insurer's position>",
  "subtitle": "<one sentence on the key finding>",
  "findings": [
    {"fact": "<metric statement>", "observation": "<what it suggests>", "prompt": "<what to investigate>"},
    ...
  ],
  "data_gaps": ["<external data source that would help>", ...]
}

Write 3-5 findings. Each should follow the fact-observation-prompt pattern.
Do not use bullet points within text. Write in British English.
Do not mention sample sizes or survey methodology.
"""


def _format_diagnostic_metrics(d: dict) -> str:
    """Format insurer diagnostic data for the AI funnel narrative."""
    lines = [f"Brand: {d['insurer']}"]

    # Shopping
    if d.get("shopping_rate") is not None:
        tag = _derive_tag(d["shopping_rate"], d.get("mkt_shopping_rate", 0))
        lines.append(
            f"Shopping rate: {d['shopping_rate'] * 100:.1f}% vs market "
            f"{d.get('mkt_shopping_rate', 0) * 100:.1f}% — {tag}"
        )

    # Retention
    if d.get("retention_rate") is not None:
        tag = _derive_tag(d["retention_rate"], d.get("mkt_retention_rate", 0))
        lines.append(
            f"Retention rate: {d['retention_rate'] * 100:.1f}% vs market "
            f"{d.get('mkt_retention_rate', 0) * 100:.1f}% — {tag}"
        )

    # Net flow
    if d.get("net_flow") is not None:
        nf = d["net_flow"]
        direction = "net winner" if nf > 0 else ("net loser" if nf < 0 else "neutral")
        lines.append(f"Net flow: {nf:+d} ({direction})")
        if d.get("gained"):
            lines.append(f"  Gained: {d['gained']}")
        if d.get("lost"):
            lines.append(f"  Lost: {d['lost']}")

    # Top sources and destinations
    if d.get("top_sources"):
        lines.append(f"Top sources (won from): {', '.join(d['top_sources'][:3])}")
    if d.get("top_destinations"):
        lines.append(f"Top destinations (lost to): {', '.join(d['top_destinations'][:3])}")

    # Reasons
    if d.get("stay_reasons"):
        lines.append(f"Top reasons for staying (Q18): {', '.join(d['stay_reasons'][:3])}")
    if d.get("leave_reasons"):
        lines.append(f"Top reasons for leaving (Q31): {', '.join(d['leave_reasons'][:3])}")
    if d.get("shop_reasons"):
        lines.append(f"Top reasons for shopping (Q8): {', '.join(d['shop_reasons'][:3])}")
    if d.get("no_shop_reasons"):
        lines.append(f"Top reasons for not shopping (Q19): {', '.join(d['no_shop_reasons'][:3])}")

    # Satisfaction
    if d.get("departed_satisfaction") is not None:
        lines.append(f"Departed satisfaction (Q40a): {d['departed_satisfaction']:.1f}")
    if d.get("departed_nps") is not None:
        lines.append(f"Departed NPS (Q40b): {d['departed_nps']:+.0f}")

    lines.append(
        "\nWrite the diagnostic headline, subtitle, and 3-5 findings "
        "following the fact-observation-prompt pattern."
    )
    return "\n".join(lines)


def generate_diagnostic_narrative(metrics: dict) -> dict | None:
    """Generate AI narrative for the Insurer Diagnostic page.

    Follows the funnel sequence from Spec Section 13.2.
    Returns {"headline": str, "subtitle": str, "findings": list, "data_gaps": list} or None.
    """
    if not NARRATIVE_ENABLED:
        return None
    key = f"diag:{metrics.get('insurer', '')}:{hash(str(sorted(metrics.items())))}"
    user_content = _format_diagnostic_metrics(metrics)
    return _cached_call(key, _DIAGNOSTIC_SYSTEM_PROMPT, user_content)
