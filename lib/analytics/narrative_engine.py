"""
Per-screen narrative generation with screen-specific prompts.

Extends lib/narrative.py patterns with the fact-observation-prompt structure.
Each screen can call generate_screen_narrative() with its metrics dict.
"""
from __future__ import annotations

import json
import logging
import os
from collections import OrderedDict

from lib.config import NARRATIVE_ENABLED, NARRATIVE_MODEL

log = logging.getLogger(__name__)

_CACHE: OrderedDict = OrderedDict()
_MAX_CACHE = 100


def _cache_key(screen: str, metrics: dict) -> str:
    """Deterministic cache key from screen name and metrics."""
    return f"{screen}:{json.dumps(metrics, sort_keys=True, default=str)}"


_SCREEN_PROMPTS = {
    "switching": """\
Analyse the switching and flow metrics for {insurer} in UK {product} insurance.
Key metrics:
- Retention rate: {retention_rate:.1%} (market: {mkt_retention_rate:.1%})
- Net flow: {net_flow:+,} (gained: {gained:,}, lost: {lost:,})
- Top sources: {top_sources}
- Top destinations: {top_destinations}

Follow the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "shopping": """\
Analyse shopping behaviour for {insurer} in UK {product} insurance.
- Shopping rate: {shopping_rate:.1%} (market: {mkt_shopping_rate:.1%})
- Conversion rate: {conversion_rate:.1%} (market: {mkt_conversion_rate:.1%})
Max 200 words. Return JSON with headline and findings.""",

    "awareness": """\
Analyse awareness metrics for {insurer} in UK {product} insurance.
- Prompted awareness: {awareness_rate:.1%} (rank {rank} of {total_brands})
- Period change: {change_pp:+.1f}pp
Max 200 words. Return JSON with headline and findings.""",

    "reasons": """\
Analyse reasons and drivers for {insurer} in UK {product} insurance.
- Top reason for staying (Q18): {top_stay_reason}
- Top reason for leaving (Q31): {top_leave_reason}
- Top reason for shopping (Q8): {top_shop_reason}
Follow the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "channels": """\
Analyse channel usage for {insurer} in UK {product} insurance.
- Top shopping channel: {top_channel}
- PCW usage rate: {pcw_usage_rate}
- Quote reach: {quote_reach:,} shoppers
Max 200 words. Return JSON with headline and findings.""",

    "pre_renewal": """\
Analyse pre-renewal context for {insurer} in UK {product} insurance.
- Price direction: {pct_higher:.0%} saw higher, {pct_lower:.0%} saw lower, {pct_unchanged:.0%} unchanged
- Shopping rate among those with higher prices: {higher_shopping_rate}
Max 200 words. Return JSON with headline and findings.""",

    "satisfaction": """\
Analyse satisfaction for {insurer} in UK {product} insurance.
- Current satisfaction (Q47): {satisfaction:.2f} (market: {mkt_satisfaction:.2f})
- NPS (Q48): {nps:+.0f} (market: {mkt_nps:+.0f})
- Departed satisfaction (Q40a): {departed_sat}
Max 200 words. Return JSON with headline and findings.""",

    "claims": """\
Analyse claims satisfaction for {insurer} in UK {product} insurance.
- Overall satisfaction (Q52): {satisfaction:.2f} (market: {mkt_satisfaction:.2f})
- Star rating: {stars} stars
- Gap to market: {gap:+.2f}
Max 200 words. Return JSON with headline and findings.""",
}


def generate_screen_narrative(
    screen: str,
    metrics: dict,
) -> dict | None:
    """Generate a narrative for a specific screen.

    Returns dict with 'headline' and 'findings' list, or None on failure.
    """
    if not NARRATIVE_ENABLED:
        return None

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    key = _cache_key(screen, metrics)
    if key in _CACHE:
        return _CACHE[key]

    prompt_template = _SCREEN_PROMPTS.get(screen)
    if not prompt_template:
        return None

    try:
        import streamlit as st
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)

        user_prompt = prompt_template.format(**metrics)

        with st.spinner("Generating insights..."):
            response = client.messages.create(
                model=NARRATIVE_MODEL,
                max_tokens=700,
                system=(
                    "You write concise market intelligence for UK insurance professionals. "
                    "Follow the fact-observation-prompt pattern. Return only valid JSON. "
                    "CRITICAL: Never speculate about a company's internal decisions, media spend, "
                    "restructuring, mergers, leadership changes, or business strategy. "
                    "Only state what the data shows. Do not infer causes that are not in the data."
                ),
                messages=[{"role": "user", "content": user_prompt}],
            )

        text = response.content[0].text.strip()
        # Strip markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]

        result = json.loads(text)

        # Cache
        _CACHE[key] = result
        if len(_CACHE) > _MAX_CACHE:
            _CACHE.popitem(last=False)

        return result

    except Exception as e:
        log.warning("Narrative generation failed for %s: %s", screen, e)
        return None
