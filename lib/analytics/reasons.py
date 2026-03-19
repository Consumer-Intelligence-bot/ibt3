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


def calc_reason_comparison(
    df_main: pd.DataFrame,
    question: str,
    insurer: str,
    top_n: int = 5,
) -> dict | None:
    """Insurer vs market reason rankings for dual table."""
    insurer_rank = calc_reason_ranking(df_main, question, insurer, top_n)
    market_rank = calc_reason_ranking(df_main, question, None, top_n)
    if insurer_rank is None and market_rank is None:
        return None
    return {"insurer": insurer_rank or [], "market": market_rank or []}


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
