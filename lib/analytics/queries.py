"""
Wide-format query helpers.

After the EAV-to-wide migration, all question data lives as columns on
the main DataFrame. These helpers provide the same clean interface used
by analytics modules, but read from wide columns instead of scanning
the 1.9M-row EAV table.

Column naming conventions (set by pivot.py):
  - Single-code:  Q{n}            → Answer text
  - Multi-code:   Q{n}_{answer}   → True / False
  - Ranked:       Q{n}_rank{i}    → Answer text
  - NPS/Scale:    Q{n}            → Numeric value
  - Grid:         Q{n}_{subject}  → Numeric value
"""
from __future__ import annotations

import pandas as pd


def _resolve_ids(respondent_ids) -> set[str] | None:
    """Normalise respondent_ids to a set of strings, or None."""
    if respondent_ids is None:
        return None
    if isinstance(respondent_ids, pd.Series):
        return set(respondent_ids.astype(str))
    return set(str(r) for r in respondent_ids)


def query_single(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.Series:
    """
    Single-code question (one answer per respondent).

    Reads column *question* directly from the wide DataFrame.
    Returns a Series indexed by UniqueID with the answer value.
    """
    if question not in df.columns:
        return pd.Series(dtype=str, name=question)

    data = df[["UniqueID", question]].copy()
    ids = _resolve_ids(respondent_ids)
    if ids is not None:
        data = data[data["UniqueID"].isin(ids)]

    data = data[data[question].notna() & (data[question].astype(str).str.strip() != "")]
    return data.drop_duplicates(subset="UniqueID", keep="first").set_index("UniqueID")[question]


def query_multi(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.DataFrame:
    """
    Multi-select question (multiple answers per respondent).

    Finds all boolean columns matching ``Q{n}_*`` and melts them back
    into (UniqueID, Answer) rows where the value is True.
    """
    prefix = f"{question}_"
    cols = [c for c in df.columns if c.startswith(prefix)]
    if not cols:
        return pd.DataFrame(columns=["UniqueID", "Answer"])

    data = df[["UniqueID"] + cols].copy()
    ids = _resolve_ids(respondent_ids)
    if ids is not None:
        data = data[data["UniqueID"].isin(ids)]

    melted = data.melt(id_vars="UniqueID", value_vars=cols,
                       var_name="_col", value_name="_sel")
    melted = melted[melted["_sel"] == True]  # noqa: E712
    melted["Answer"] = melted["_col"].str[len(prefix):]
    return melted[["UniqueID", "Answer"]].reset_index(drop=True)


def query_ranked(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.DataFrame:
    """
    Ranked question (ordered answers per respondent).

    Reads ``Q{n}_rank1`` through ``Q{n}_rank10`` and returns
    (UniqueID, Answer, Rank).
    """
    rank_cols = []
    for i in range(1, 11):
        col = f"{question}_rank{i}"
        if col in df.columns:
            rank_cols.append((i, col))
    if not rank_cols:
        return pd.DataFrame(columns=["UniqueID", "Answer", "Rank"])

    data = df[["UniqueID"] + [c for _, c in rank_cols]].copy()
    ids = _resolve_ids(respondent_ids)
    if ids is not None:
        data = data[data["UniqueID"].isin(ids)]

    parts = []
    for rank_val, col in rank_cols:
        subset = data[data[col].notna() & (data[col].astype(str).str.strip() != "")][["UniqueID", col]].copy()
        if subset.empty:
            continue
        subset["Rank"] = rank_val
        subset = subset.rename(columns={col: "Answer"})
        parts.append(subset)

    if not parts:
        return pd.DataFrame(columns=["UniqueID", "Answer", "Rank"])
    return pd.concat(parts, ignore_index=True)


def count_mentions(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> pd.Series:
    """
    Count how many respondents selected each answer value.

    Works with multi-select boolean columns. Returns a Series indexed
    by answer value, sorted descending.
    """
    multi = query_multi(df, question, respondent_ids)
    if multi.empty:
        return pd.Series(dtype=int)
    return multi["Answer"].value_counts()


def respondent_count(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
) -> int:
    """Count distinct respondents who answered this question."""
    # Direct column (single/NPS)
    if question in df.columns:
        data = df[["UniqueID", question]].copy()
        ids = _resolve_ids(respondent_ids)
        if ids is not None:
            data = data[data["UniqueID"].isin(ids)]
        return data[data[question].notna()]["UniqueID"].nunique()

    # Multi-code columns
    multi = query_multi(df, question, respondent_ids)
    return multi["UniqueID"].nunique()


def top_reason(
    df: pd.DataFrame,
    question: str,
    respondent_ids: pd.Series | list | None = None,
    top_n: int = 5,
) -> list[dict]:
    """
    Ranked reason analysis.

    For each reason text, counts:
      - rank1_count: times it was ranked #1
      - total_mentions: times it appeared at any rank
      - rank1_pct: rank1_count / total respondents who answered

    Returns list of dicts sorted by rank1_count descending, limited to top_n.
    """
    ranked = query_ranked(df, question, respondent_ids)
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
