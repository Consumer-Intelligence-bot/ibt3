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
    "Q39", "Q41", "Q42", "Q43", "Q43a", "Q49", "Q50", "Q51",
    "Q51a", "Q57", "Q58", "Q59", "Q60", "Q61", "Q62",
}

MULTI_CODE = {
    "Q2", "Q5a", "Q5b", "Q9b", "Q10", "Q11", "Q13b", "Q14a", "Q14b",
    "Q14c", "Q27", "Q28", "Q31", "Q45", "Q54",
}

RANKED = {"Q8", "Q13a", "Q18", "Q19", "Q33", "Q44", "Q55"}

GRID = {"Q46", "Q53"}

NPS_SCALE = {"Q11d", "Q40", "Q40a", "Q40b", "Q47", "Q48", "Q52"}

# Q1 spontaneous awareness: free-text grid (Q1_1 through Q1_10).
# Handled separately — needs brand name normalisation before pivoting.
Q1_SPONTANEOUS = {f"Q1_{i}" for i in range(1, 11)}

ALL_KNOWN = SINGLE_CODE | MULTI_CODE | RANKED | GRID | NPS_SCALE | Q1_SPONTANEOUS


def pivot_questions_to_wide(df_questions: pd.DataFrame, product: str = "Motor") -> pd.DataFrame:
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

    # Select classification sets based on product
    if product == "Pet":
        from lib.pet_questions import PET_SINGLE_CODE, PET_MULTI_CODE, PET_NPS_SCALE, PET_ALL_KNOWN
        single_set = PET_SINGLE_CODE
        multi_set = PET_MULTI_CODE
        nps_set = PET_NPS_SCALE
        known_set = PET_ALL_KNOWN
    else:
        single_set = SINGLE_CODE
        multi_set = MULTI_CODE
        nps_set = NPS_SCALE
        known_set = ALL_KNOWN

    # Filter to known question types only (skip hidden/derived fields)
    df = df[df["QuestionNumber"].isin(known_set)]
    df = df[df["Answer"].notna() & (df["Answer"] != "") & (df["Answer"] != "nan")]
    if df.empty:
        return pd.DataFrame()

    all_ids = df["UniqueID"].unique()
    result = pd.DataFrame({"UniqueID": all_ids})

    # --- Single-code: one column per question, value = Answer ---
    _pivot_single(df, result, question_set=single_set)

    # --- Multi-code: boolean columns Q{n}_{answer} ---
    _pivot_multi(df, result, question_set=multi_set)

    # --- Ranked: Q{n}_rank{i} = Answer ---
    if product != "Pet":
        _pivot_ranked(df, result)

    # --- NPS / Scale: one column per question, numeric value ---
    _pivot_nps(df, result, question_set=nps_set)

    # --- Grid: Q{n}_{subject} = numeric value ---
    if product != "Pet":
        _pivot_grid(df, result)

    # --- Q1 spontaneous awareness: normalise free text → boolean brand columns ---
    if product != "Pet":
        _pivot_q1_spontaneous(df, result)

    n_cols = len(result.columns) - 1  # minus UniqueID
    log.info("Pivoted %d EAV rows into %d wide columns for %d respondents",
             len(df_questions), n_cols, len(result))

    return result.set_index("UniqueID")


# ---------------------------------------------------------------------------
# Per-type pivot helpers
# ---------------------------------------------------------------------------

def _pivot_single(df: pd.DataFrame, result: pd.DataFrame, question_set: set | None = None) -> None:
    """Single-code questions: one value per respondent."""
    subset = df[df["QuestionNumber"].isin(question_set or SINGLE_CODE)]
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


def _pivot_multi(df: pd.DataFrame, result: pd.DataFrame, question_set: set | None = None) -> None:
    """Multi-code questions: boolean column per answer option."""
    subset = df[df["QuestionNumber"].isin(question_set or MULTI_CODE)]
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
    pivoted = pivoted.fillna(False).infer_objects(copy=False)
    merged = result.merge(pivoted, on="UniqueID", how="left")
    for col in pivoted.columns:
        result[col] = merged[col].fillna(False).values


def _pivot_ranked(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Ranked questions: Q{n}_rank{i} columns."""
    subset = df[df["QuestionNumber"].isin(RANKED)]
    if subset.empty:
        return
    subset = subset.copy()

    # Derive rank from Ranking/Rank column or row order
    rank_col = "Ranking" if "Ranking" in subset.columns else ("Rank" if "Rank" in subset.columns else None)
    if rank_col is not None:
        subset["_rank"] = pd.to_numeric(subset[rank_col], errors="coerce").fillna(0).astype(int)
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


def _pivot_nps(df: pd.DataFrame, result: pd.DataFrame, question_set: set | None = None) -> None:
    """NPS/Scale questions: one numeric column per question."""
    subset = df[df["QuestionNumber"].isin(question_set or NPS_SCALE)]
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
        log.warning("No GRID question rows (Q46, Q53) found in EAV data")
        return

    # Diagnostic: log which grid questions are present
    grid_qs = subset["QuestionNumber"].unique().tolist()
    log.info("GRID questions present in EAV data: %s", grid_qs)
    for gq in sorted(GRID):
        gq_rows = subset[subset["QuestionNumber"] == gq]
        has_subject = "Subject" in gq_rows.columns and gq_rows["Subject"].notna().any()
        log.info("  %s: %d rows, Subject present: %s", gq, len(gq_rows), has_subject)

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


def _pivot_q1_spontaneous(df: pd.DataFrame, result: pd.DataFrame) -> None:
    """Q1 spontaneous awareness: normalise free text, preserving mention position.

    Creates two sets of columns:
      - Q1_pos{row}{a|b} = normalised brand name (text), preserving rank/position
      - Q1_{brand} = True/False (boolean), for awareness-level calculations

    The position columns enable TOMA (pos 1), top-3, and mean position metrics.
    The boolean columns enable standard awareness rate calculations.
    """
    subset = df[df["QuestionNumber"].isin(Q1_SPONTANEOUS)]
    if subset.empty:
        return
    subset = subset[subset["Answer"].notna() & (subset["Answer"] != "") & (subset["Answer"] != "nan")]
    if subset.empty:
        return

    # Get canonical brand list from Q2 columns already on the result
    q2_brands = [c[3:] for c in result.columns if c.startswith("Q2_")]
    if not q2_brands:
        log.warning("No Q2 brand columns found; cannot normalise Q1 spontaneous awareness")
        return

    # Run brand normalisation
    from lib.analytics.brand_match import normalise_q1_brands

    matched = normalise_q1_brands(subset, canonical_brands=q2_brands)
    matched = matched[matched["Brand"].notna()].copy()
    if matched.empty:
        log.info("Q1 spontaneous: no brands matched after normalisation")
        return

    # --- Position columns: Q1_pos{row}{slot} = brand name ---
    # Map Q1 sub-questions to position column names
    _pos_col_map = {
        "Q1_1": "Q1_pos1a", "Q1_2": "Q1_pos1b",
        "Q1_3": "Q1_pos2a", "Q1_4": "Q1_pos2b",
        "Q1_5": "Q1_pos3a", "Q1_6": "Q1_pos3b",
        "Q1_7": "Q1_pos4a", "Q1_8": "Q1_pos4b",
        "Q1_9": "Q1_pos5a", "Q1_10": "Q1_pos5b",
    }
    matched["_pos_col"] = matched["QuestionNumber"].map(_pos_col_map)
    pos_data = matched[matched["_pos_col"].notna()][["UniqueID", "_pos_col", "Brand"]].copy()
    pos_deduped = pos_data.drop_duplicates(subset=["UniqueID", "_pos_col"])

    if not pos_deduped.empty:
        try:
            pos_pivoted = pos_deduped.pivot(index="UniqueID", columns="_pos_col", values="Brand")
        except ValueError:
            pos_pivoted = pos_deduped.groupby(["UniqueID", "_pos_col"])["Brand"].first().unstack()
        merged_pos = result.merge(pos_pivoted, on="UniqueID", how="left")
        for col in pos_pivoted.columns:
            result[col] = merged_pos[col].values

    # --- Boolean columns: Q1_{brand} = True/False ---
    matched["_bool_col"] = "Q1_" + matched["Brand"]
    matched["_val"] = True
    bool_deduped = matched.drop_duplicates(subset=["UniqueID", "_bool_col"])

    try:
        bool_pivoted = bool_deduped.pivot(index="UniqueID", columns="_bool_col", values="_val")
    except ValueError:
        bool_pivoted = bool_deduped.groupby(["UniqueID", "_bool_col"])["_val"].first().unstack()
    bool_pivoted = bool_pivoted.fillna(False).infer_objects(copy=False)

    merged_bool = result.merge(bool_pivoted, on="UniqueID", how="left")
    for col in bool_pivoted.columns:
        result[col] = merged_bool[col].fillna(False).values

    n_brands = len(bool_pivoted.columns)
    n_matched = matched["UniqueID"].nunique()
    log.info("Q1 spontaneous: %d brands, %d respondents, %d position cols",
             n_brands, n_matched, len(pos_pivoted.columns) if not pos_deduped.empty else 0)
