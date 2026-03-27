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


_SYSTEM_PROMPT = """\
You are a market intelligence analyst writing for UK insurance executives. Write in plain English that a board member would understand without context.

Rules:
1. Headlines must be complete sentences that make sense without seeing the data. Bad: "Pricing splits market." Good: "First Central customers are more likely to shop around when prices rise."
2. Always state the 'so what' — is this good or bad for the insurer? How does it compare to the market?
3. Compare to market in every finding: "X% vs market Y% (Zpp above/below)."
4. If referencing a rank, name who is #1.
5. Never speculate about internal business decisions, media spend, mergers, or strategy. Only state what the data shows.
6. Use British English. No jargon. No em dashes.
7. Return valid JSON only: {"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{"fact": "...", "observation": "...", "prompt": "..."}]}
"""

_SCREEN_PROMPTS = {
    "switching": """\
Analyse the switching and flow metrics for {insurer} in UK {product} insurance.

Key metrics:
- Retention rate: {retention_rate:.1%} (market: {mkt_retention_rate:.1%})
- Net flow: {net_flow:+,} (gained: {gained:,}, lost: {lost:,})
- Top sources (where {insurer} gained customers from): {top_sources}
- Top destinations (where {insurer} lost customers to): {top_destinations}

So what: Is {insurer} retaining customers above or below market? Is net flow positive or negative, and which competitor is driving most of the loss?

Good headline example: "Admiral retains 72% of customers, 5pp above market. But net flow is negative — losing more to Direct Line than gaining."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "shopping": """\
Analyse shopping behaviour for {insurer} in UK {product} insurance.

Key metrics:
- Shopping rate: {shopping_rate:.1%} (market: {mkt_shopping_rate:.1%})
- Conversion rate: {conversion_rate:.1%} (market: {mkt_conversion_rate:.1%})

So what: Are {insurer} customers more or less likely to shop around than the market average? Does high shopping combined with strong conversion suggest price sensitivity, or does low conversion suggest poor competitiveness?

Good headline example: "First Central customers shop at 74%, 4pp above market. But conversion is strong at 58%, suggesting price-sensitive but loyal shoppers."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "awareness": """\
Analyse awareness metrics for {insurer} in UK {product} insurance.

Key metrics:
- Prompted awareness: {awareness_rate:.1%} (rank {rank} of {total_brands})
- Period change: {change_pp:+.1f}pp

So what: Where does {insurer} sit in the awareness ranking? Who is #1? Is {insurer} gaining or losing ground? Is any change within the margin of error?

Good headline example: "Aviva is the second most recognised motor insurer (63%), behind Admiral (65%). The gap is within margin of error."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "reasons": """\
Analyse reasons and drivers for {insurer} in UK {product} insurance.

Key metrics:
- Top reason for staying (Q18): {top_stay_reason}
- Top reason for leaving (Q31): {top_leave_reason}
- Top reason for shopping (Q8): {top_shop_reason}

So what: Is {insurer} retaining customers because of genuine satisfaction or just because rivals are no cheaper? Is the top leave reason something the insurer can act on?

Good headline example: "Price dominates First Central's retention story. Customers stay because they can't find cheaper, not because they're satisfied."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "channels": """\
Analyse channel usage for {insurer} in UK {product} insurance.

Key metrics:
- Top shopping channel: {top_channel}
- PCW usage rate: {pcw_usage_rate}
- Quote reach: {quote_reach:,} shoppers

So what: Are {insurer} customers more reliant on price comparison websites than the market average? High PCW usage suggests price sensitivity and lower brand loyalty.

Good headline example: "PCW usage among Aviva customers (82%) is 6pp above market, suggesting high price sensitivity."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "pre_renewal": """\
Analyse pre-renewal context for {insurer} in UK {product} insurance.

Key metrics:
- Price direction: {pct_higher:.0%} saw higher prices, {pct_lower:.0%} saw lower, {pct_unchanged:.0%} unchanged
- Shopping rate among those with higher prices: {higher_shopping_rate}

So what: Is {insurer} passing on more price increases than the market average? Does seeing a higher price drive customers to shop — and how does that compare to market behaviour?

Good headline example: "47% of First Central customers saw higher prices at renewal, in line with the market average of 48%."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "satisfaction": """\
Analyse satisfaction for {insurer} in UK {product} insurance.

Key metrics:
- Current satisfaction (Q47): {satisfaction:.2f} (market: {mkt_satisfaction:.2f})
- NPS (Q48): {nps:+.0f} (market: {mkt_nps:+.0f})
- Departed satisfaction (Q40a): {departed_sat}

So what: Is {insurer} above or below market on satisfaction and NPS? A positive NPS relative to the market is a standout strength. Low departed satisfaction explains why customers left.

Good headline example: "Aviva's satisfaction score (4.2/5) is 0.3 above market. NPS of +12 vs market -5 is a standout strength."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",

    "claims": """\
Analyse claims satisfaction for {insurer} in UK {product} insurance.

Key metrics:
- Overall satisfaction (Q52): {satisfaction:.2f} (market: {mkt_satisfaction:.2f})
- Star rating: {stars} stars
- Gap to market: {gap:+.2f}

So what: Is {insurer} handling claims better or worse than market average? The star rating provides a simple benchmark. A below-average score is a retention risk — unhappy claimants are more likely to switch.

Good headline example: "Churchill's claims satisfaction (3.8/5) sits 0.2 below market average, earning a 3-star rating."

Use the fact-observation-prompt pattern. Max 200 words. Return JSON:
{{"headline": "...", "subtitle": "...", "paragraph": "...", "findings": [{{"fact": "...", "observation": "...", "prompt": "..."}}]}}""",
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

        placeholder = st.empty()
        placeholder.caption("Thinking about this... bear with me a moment.")
        response = client.messages.create(
            model=NARRATIVE_MODEL,
            max_tokens=700,
            system=_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_prompt}],
        )
        placeholder.empty()

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
