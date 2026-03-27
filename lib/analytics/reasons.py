"""
Reason ranking and percentage calculations using wide-format question data.

Supports ranked questions (Q8, Q18, Q19, Q33) and multi-select (Q31).
Uses queries helpers to access wide columns on the main DataFrame.
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.queries import top_reason as _top_reason


def calc_reason_ranking(
    df_main: pd.DataFrame,
    question: str,
    insurer: str | None = None,
    top_n: int = 5,
) -> list[dict] | None:
    """
    Top n reasons with rank-1 and total-mention frequencies.

    If *insurer* is provided, restricts to respondents whose CurrentCompany matches.
    """
    if df_main is None or df_main.empty:
        return None

    respondent_ids = None
    if insurer:
        respondent_ids = df_main.loc[
            df_main["CurrentCompany"] == insurer, "UniqueID"
        ]

    result = _top_reason(df_main, question, respondent_ids, top_n)
    return result if result else None


_MARKET_LOOKUP_TOP_N = 20
"""Number of market reasons to fetch for the lookup table.

This must be larger than the insurer top_n (default 5) so that reasons
which are rare market-wide (e.g. rank 6th–15th) but dominant for a
specific insurer are still found in the market lookup. Without a larger
top_n, the insurer-specific rare reason gets market_pct=0, which is
misleading (it looks like the market never cites it, when in fact it
does at a low but non-zero rate).
"""


def calc_reason_comparison(
    df_main: pd.DataFrame,
    question: str,
    insurer: str,
    top_n: int = 5,
) -> dict | None:
    """Insurer vs market reason rankings for dual table.

    Market reasons are fetched with a larger top_n (_MARKET_LOOKUP_TOP_N)
    than the insurer top_n so that reasons which are rare market-wide but
    common for this specific insurer are still found in the market lookup
    (avoiding false 0% market percentages).
    """
    insurer_rank = calc_reason_ranking(df_main, question, insurer, top_n)
    market_rank = calc_reason_ranking(df_main, question, None, _MARKET_LOOKUP_TOP_N)
    if insurer_rank is None and market_rank is None:
        return None
    return {"insurer": insurer_rank or [], "market": market_rank or []}


def calc_reason_index(
    insurer_results: list[dict],
    market_results: list[dict],
) -> list[dict]:
    """
    Calculate index values comparing insurer vs market reason frequencies.

    Index = (brand_pct / market_pct) * 100. An index of 110 means the insurer
    is 10% more likely to cite this reason than the market average.
    """
    if not insurer_results or not market_results:
        return []

    # Build lookup from market results
    mkt_lookup = {}
    for r in market_results:
        pct = r.get("rank1_pct", r.get("mention_pct", 0))
        mkt_lookup[r["reason"]] = pct

    rows = []
    for r in insurer_results:
        reason = r["reason"]
        brand_pct = r.get("rank1_pct", r.get("mention_pct", 0))
        market_pct = mkt_lookup.get(reason, 0)
        index_val = (brand_pct / market_pct * 100) if market_pct > 0 else None
        rows.append({
            "reason": reason,
            "brand_pct": brand_pct,
            "market_pct": market_pct,
            "index": index_val,
        })

    return rows


def calc_primary_reason(
    df_main: pd.DataFrame,
    question: str,
    insurer: str | None = None,
) -> str | None:
    """Single most common rank-1 reason."""
    rank = calc_reason_ranking(df_main, question, insurer, top_n=1)
    if not rank:
        return None
    return rank[0]["reason"]
