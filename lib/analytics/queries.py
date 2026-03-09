"""
EAV query helpers for AllOtherData.

AllOtherData is in long format: one row per answer per respondent.
Columns: UniqueID, QuestionNumber, Answer (and optionally Rank for ranked Qs).

These helpers provide a clean interface for analytics modules so they never
need to know about the underlying EAV structure.
"""
from __future__ import annotations

import pandas as pd


def _filter_question(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.DataFrame:
    """Filter AllOtherData to a single question, optionally restricted to respondent IDs."""
    mask = df_questions["QuestionNumber"] == question
    if respondent_ids is not None:
        if isinstance(respondent_ids, pd.Series):
            ids = set(respondent_ids.astype(str))
        else:
            ids = set(str(r) for r in respondent_ids)
        mask = mask & df_questions["UniqueID"].isin(ids)
    subset = df_questions.loc[mask].copy()
    subset = subset[subset["Answer"].notna() & (subset["Answer"].astype(str).str.strip() != "")]
    return subset


def query_single(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.Series:
    """
    Single-code question (one answer per respondent).

    Returns a Series indexed by UniqueID with the answer value.
    If a respondent has multiple rows (shouldn't happen for single-code), keeps the first.
    """
    subset = _filter_question(df_questions, question, respondent_ids)
    if subset.empty:
        return pd.Series(dtype=str, name=question)
    return subset.drop_duplicates(subset="UniqueID", keep="first").set_index("UniqueID")["Answer"]


def query_multi(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.DataFrame:
    """
    Multi-select question (multiple answers per respondent).

    Returns a DataFrame with columns: UniqueID, Answer.
    One row per selection per respondent.
    """
    subset = _filter_question(df_questions, question, respondent_ids)
    if subset.empty:
        return pd.DataFrame(columns=["UniqueID", "Answer"])
    return subset[["UniqueID", "Answer"]].reset_index(drop=True)


def query_ranked(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.DataFrame:
    """
    Ranked question (ordered answers per respondent).

    Returns a DataFrame with columns: UniqueID, Answer, Rank.
    Rank is 1-based; derived from the row order within each respondent's answers
    (first row = rank 1, most important).

    If the EAV table already has a Rank column, it is used directly.
    """
    subset = _filter_question(df_questions, question, respondent_ids)
    if subset.empty:
        return pd.DataFrame(columns=["UniqueID", "Answer", "Rank"])

    result = subset[["UniqueID", "Answer"]].copy()

    if "Rank" in subset.columns:
        result["Rank"] = pd.to_numeric(subset["Rank"], errors="coerce").fillna(0).astype(int)
    else:
        result["Rank"] = result.groupby("UniqueID").cumcount() + 1

    return result.reset_index(drop=True)


def count_mentions(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.Series:
    """
    Count how many respondents selected each answer value.

    Useful for multi-select (Q2, Q9b, Q11, Q27) frequency tables.
    Returns a Series indexed by answer value, sorted descending.
    """
    multi = query_multi(df_questions, question, respondent_ids)
    if multi.empty:
        return pd.Series(dtype=int)
    return multi["Answer"].value_counts()


def respondent_count(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> int:
    """Count distinct respondents who answered this question."""
    subset = _filter_question(df_questions, question, respondent_ids)
    return subset["UniqueID"].nunique()


def top_reason(
    df_questions: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
    top_n: int = 5,
) -> list[dict]:
    """
    Ranked reason analysis.

    For each reason text, counts:
      - rank1_count: times it was ranked #1 (TopReason)
      - total_mentions: times it appeared at any rank
      - rank1_pct: rank1_count / total respondents who answered

    Returns list of dicts sorted by rank1_count descending, limited to top_n.
    """
    ranked = query_ranked(df_questions, question, respondent_ids)
    if ranked.empty:
        return []

    n_respondents = ranked["UniqueID"].nunique()
    rank1 = ranked[ranked["Rank"] == 1]
    all_mentions = ranked.groupby("Answer")["UniqueID"].nunique().rename("total_mentions")
    rank1_counts = rank1.groupby("Answer")["UniqueID"].nunique().rename("rank1_count")

    combined = pd.DataFrame({"rank1_count": rank1_counts, "total_mentions": all_mentions}).fillna(0)
    combined["rank1_pct"] = combined["rank1_count"] / n_respondents if n_respondents else 0
    combined["mention_pct"] = combined["total_mentions"] / n_respondents if n_respondents else 0
    combined = combined.sort_values("rank1_count", ascending=False).head(top_n)

    return [
        {
            "reason": reason,
            "rank1_count": int(row["rank1_count"]),
            "total_mentions": int(row["total_mentions"]),
            "rank1_pct": row["rank1_pct"],
            "mention_pct": row["mention_pct"],
        }
        for reason, row in combined.iterrows()
    ]
