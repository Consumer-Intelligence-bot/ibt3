"""
Pivot EAV question data (AllOtherData) to wide format (one row per respondent).

Called once at load time in state.py. The wide columns are merged onto
the main DataFrame so all downstream queries become simple column lookups.
"""
from __future__ import annotations

import logging

import pandas as pd

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Question classification (derived from exploration data)
# ---------------------------------------------------------------------------

SINGLE_CODE = {
    "Q3", "Q4", "Q5", "Q6", "Q6a", "Q7", "Q9a", "Q15", "Q20a", "Q20b",
    "Q21", "Q29", "Q30", "Q34a", "Q34b", "Q35", "Q36", "Q37",
    "Q39", "Q40", "Q41", "Q42", "Q43", "Q43a", "Q49", "Q50", "Q51",
    "Q51a", "Q57", "Q58", "Q59", "Q60", "Q61", "Q62",
}

MULTI_CODE = {
    "Q2", "Q5a", "Q5b", "Q9b", "Q10", "Q11", "Q13b", "Q14a", "Q14b",
    "Q14c", "Q27", "Q28", "Q31", "Q45", "Q54",
}

RANKED = {"Q8", "Q13a", "Q18", "Q19", "Q33", "Q44", "Q55"}

GRID = {"Q46", "Q53"}

NPS_SCALE = {"Q11d", "Q40a", "Q40b", "Q47", "Q48", "Q52"}

ALL_KNOWN = SINGLE_CODE | MULTI_CODE | RANKED | GRID | NPS_SCALE


def pivot_questions_to_wide(df_questions: pd.DataFrame) -> pd.DataFrame:
    """
    Pivot EAV question data into a wide DataFrame indexed by UniqueID.

    Strategy per type:
      - Single-code: one column per question, value = Answer text
      - Multi-code: boolean columns ``Q{n}_{answer_text}``
      - Ranked: columns ``Q{n}_rank{i}`` = Answer text (up to rank 10)
      - Grid: columns ``Q{n}_{subject}`` = numeric scale value
      - NPS/Scale: one column per question, value = numeric Answer
    """
    if df_questions is None or df_questions.empty:
        return pd.DataFrame()

    df = df_questions.copy()
    df["UniqueID"] = df["UniqueID"].astype(str)
    df["QuestionNumber"] = df["QuestionNumber"].astype(str).str.strip()
    df["Answer"] = df["Answer"].astype(str).str.strip()

    # Filter to known question types only (skip hidden/derived fields)
    df = df[df["QuestionNumber"].isin(ALL_KNOWN)]
    df = df[df["Answer"].notna() & (df["Answer"] != "") & (df["Answer"] != "nan")]
    if df.empty:
        return pd.DataFrame()

    all_ids = df["UniqueID"].unique()
    result = pd.DataFrame({"UniqueID": all_ids})

    # --- Single-code: one column per question, value = Answer ---
    _pivot_single(df, result)

    # --- Multi-code: boolean columns Q{n}_{answer} ---
    _pivot_multi(df, result)

    # --- Ranked: Q{n}_rank{i} = Answer ---
    _pivot_ranked(df, result)

    # --- NPS / Scale: one column per question, numeric value ---
    _pivot_nps(df, result)

    # --- Grid: Q{n}_{subject} = numeric value ---
    _pivot_grid(df, result)

    n_cols = len(result.columns) - 1  # minus UniqueID
    log.info("Pivoted %d EAV rows into %d wide columns for %d respondents",
             len(df_questions), n_cols, len(result))

    return result.set_index("UniqueID")


# ---------------------------------------------------------------------------
# Per-type pivot helpers
# ---------------------------------------------------------------------------

def _pivot_single(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Single-code questions: one value per respondent."""
    subset = df[df["QuestionNumber"].isin(SINGLE_CODE)]
    if subset.empty:
        return
    deduped = subset.drop_duplicates(subset=["UniqueID", "QuestionNumber"], keep="first")
    try:
        pivoted = deduped.pivot(index="UniqueID", columns="QuestionNumber", values="Answer")
    except ValueError:
        # Fallback if pivot fails (e.g. duplicate entries slipped through)
        pivoted = deduped.groupby(["UniqueID", "QuestionNumber"])["Answer"].first().unstack()
    cols_before = set(result.columns)
    merged = result.merge(pivoted, on="UniqueID", how="left")
    result.drop(result.columns.difference(["UniqueID"]), axis=1, inplace=True)
    for col in merged.columns:
        if col not in cols_before:
            result[col] = merged[col].values


def _pivot_multi(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Multi-code questions: boolean column per answer option."""
    subset = df[df["QuestionNumber"].isin(MULTI_CODE)]
    if subset.empty:
        return
    subset = subset.copy()
    subset["_col"] = subset["QuestionNumber"] + "_" + subset["Answer"]
    subset["_val"] = True
    deduped = subset.drop_duplicates(subset=["UniqueID", "_col"])
    try:
        pivoted = deduped.pivot(index="UniqueID", columns="_col", values="_val")
    except ValueError:
        pivoted = deduped.groupby(["UniqueID", "_col"])["_val"].first().unstack()
    pivoted = pivoted.fillna(False)
    merged = result.merge(pivoted, on="UniqueID", how="left")
    for col in pivoted.columns:
        result[col] = merged[col].fillna(False).values


def _pivot_ranked(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Ranked questions: Q{n}_rank{i} columns."""
    subset = df[df["QuestionNumber"].isin(RANKED)]
    if subset.empty:
        return
    subset = subset.copy()

    # Derive rank from Rank column or row order
    if "Rank" in subset.columns:
        subset["_rank"] = pd.to_numeric(subset["Rank"], errors="coerce").fillna(0).astype(int)
    else:
        subset["_rank"] = subset.groupby(["UniqueID", "QuestionNumber"]).cumcount() + 1

    # Cap at rank 10
    subset = subset[subset["_rank"].between(1, 10)]
    if subset.empty:
        return

    subset["_col"] = subset["QuestionNumber"] + "_rank" + subset["_rank"].astype(str)
    deduped = subset.drop_duplicates(subset=["UniqueID", "_col"])
    try:
        pivoted = deduped.pivot(index="UniqueID", columns="_col", values="Answer")
    except ValueError:
        pivoted = deduped.groupby(["UniqueID", "_col"])["Answer"].first().unstack()
    merged = result.merge(pivoted, on="UniqueID", how="left")
    for col in pivoted.columns:
        result[col] = merged[col].values


def _pivot_nps(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """NPS/Scale questions: one numeric column per question."""
    subset = df[df["QuestionNumber"].isin(NPS_SCALE)]
    if subset.empty:
        return
    subset = subset.copy()
    subset["_value"] = pd.to_numeric(subset["Answer"], errors="coerce")
    subset = subset.dropna(subset=["_value"])
    if subset.empty:
        return
    deduped = subset.drop_duplicates(subset=["UniqueID", "QuestionNumber"], keep="first")
    try:
        pivoted = deduped.pivot(index="UniqueID", columns="QuestionNumber", values="_value")
    except ValueError:
        pivoted = deduped.groupby(["UniqueID", "QuestionNumber"])["_value"].first().unstack()
    merged = result.merge(pivoted, on="UniqueID", how="left")
    for col in pivoted.columns:
        result[col] = merged[col].values


def _pivot_grid(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Grid/scale questions: Q{n}_{subject} = numeric value."""
    subset = df[df["QuestionNumber"].isin(GRID)]
    if subset.empty:
        return

    if "Subject" in subset.columns:
        subset = subset.copy()
        subset = subset[subset["Subject"].notna()]
        subset["_col"] = subset["QuestionNumber"] + "_" + subset["Subject"].astype(str).str.strip()
        subset["_value"] = pd.to_numeric(subset["Answer"], errors="coerce")
        subset = subset.dropna(subset=["_value"])
        if subset.empty:
            return
        deduped = subset.drop_duplicates(subset=["UniqueID", "_col"])
        try:
            pivoted = deduped.pivot(index="UniqueID", columns="_col", values="_value")
        except ValueError:
            pivoted = deduped.groupby(["UniqueID", "_col"])["_value"].first().unstack()
        merged = result.merge(pivoted, on="UniqueID", how="left")
        for col in pivoted.columns:
            result[col] = merged[col].values
    else:
        # No Subject column: treat as single-code fallback
        deduped = subset.drop_duplicates(subset=["UniqueID", "QuestionNumber"], keep="first")
        try:
            pivoted = deduped.pivot(index="UniqueID", columns="QuestionNumber", values="Answer")
        except ValueError:
            pivoted = deduped.groupby(["UniqueID", "QuestionNumber"])["Answer"].first().unstack()
        merged = result.merge(pivoted, on="UniqueID", how="left")
        for col in pivoted.columns:
            result[col] = merged[col].values
