"""
Reason ranking and percentage calculations using EAV data.

Supports ranked questions (Q8, Q18, Q19, Q33) and multi-select (Q31).
Uses data.queries helpers to access AllOtherData.
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.queries import count_mentions, query_ranked, top_reason as _top_reason_eav


def calc_reason_ranking(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    question: str,
    insurer: str | None = None,
    top_n: int = 5,
) -> list[dict] | None:
    """
    Top n reasons with rank-1 and total-mention frequencies.

    If *insurer* is provided, restricts to respondents whose CurrentCompany matches.
    Q18 uses all non-switchers (not just shoppers who stayed).
    """
    if df_questions is None or df_questions.empty:
        return _fallback_wide(df_main, question, insurer, top_n)

    respondent_ids = None
    if insurer and df_main is not None:
        respondent_ids = df_main.loc[
            df_main["CurrentCompany"] == insurer, "UniqueID"
        ]

    result = _top_reason_eav(df_questions, question, respondent_ids, top_n)
    return result if result else None


def calc_reason_comparison(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    question: str,
    insurer: str,
    top_n: int = 5,
) -> dict | None:
    """Insurer vs market reason rankings for dual table."""
    insurer_rank = calc_reason_ranking(df_main, df_questions, question, insurer, top_n)
    market_rank = calc_reason_ranking(df_main, df_questions, question, None, top_n)
    if insurer_rank is None and market_rank is None:
        return None
    return {"insurer": insurer_rank or [], "market": market_rank or []}


def calc_primary_reason(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    question: str,
    insurer: str | None = None,
) -> str | None:
    """Single most common rank-1 reason."""
    rank = calc_reason_ranking(df_main, df_questions, question, insurer, top_n=1)
    if not rank:
        return None
    return rank[0]["reason"]


# ---------------------------------------------------------------------------
# Fallback for legacy wide-format data (no AllOtherData available)
# ---------------------------------------------------------------------------

def _fallback_wide(
    df: pd.DataFrame,
    question_col: str,
    insurer: str | None,
    top_n: int,
) -> list[dict] | None:
    """Legacy path: treat wide column as single-value (pre-EAV behaviour)."""
    if df is None or len(df) == 0 or question_col not in df.columns:
        return None
    data = df.copy()
    if insurer:
        data = data[data["CurrentCompany"] == insurer]
    base = data[data[question_col].notna() & (data[question_col].astype(str).str.strip() != "")]
    if len(base) == 0:
        return None
    counts = base[question_col].astype(str).value_counts()
    total = counts.sum()
    return [
        {
            "reason": reason,
            "rank1_count": int(count),
            "total_mentions": int(count),
            "rank1_pct": count / total,
            "mention_pct": count / total,
        }
        for reason, count in counts.head(top_n).items()
    ]
