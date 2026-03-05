"""
Load source data from CSV or Parquet.

Supports two data shapes:
  1. Dual-table: MainData (wide) + AllOtherData (EAV)
  2. Flat export: single CSV with 131+ columns (un-pivoted into EAV at load time)
  3. Legacy: MainData-only (25-column prefixed CSV — no AllOtherData available)

Search order: DATA_DIR (env) → data/processed/ (parquet) → data/raw/ → ../public/data/
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pandas as pd

from data.transforms import transform

_DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = _DATA_DIR / "raw"
PROCESSED_DIR = _DATA_DIR / "processed"
FALLBACK_DIR = _DATA_DIR.parent.parent / "public" / "data"

DATA_DIR = os.getenv("DATA_DIR")
_DATA_DIR_PATH = Path(DATA_DIR) if DATA_DIR else None

# Q-code columns are those starting with Q followed by a digit
_Q_COL_RE = re.compile(r"^Q\d")

# Profile columns that belong in MainData (not Q-codes)
_PROFILE_COLS = {
    "UniqueID", "SurveyYearMonth", "RenewalYearMonth", "Gender", "Region",
    "Are you insured", "Shoppers", "Switchers", "PreRenewalCompany",
    "CurrentCompany", "Renewal premium change", "How much higher",
    "How much lower", "Did you use a PCW for shopping", "Claimants",
    "StartedDateTime", "Age Group", "Employment status",
    "Renewal premium change combined", "SortOrder", "Retained",
}


def _normalise_column_name(name: str) -> str:
    """Strip MainData[, RespondentProfile[, etc. prefixes from column names."""
    if not name:
        return name
    name = name.replace("\ufeff", "").strip()
    for prefix in ("MainData_Motor[", "MainData[", "RespondentProfile["):
        if name.startswith(prefix):
            name = name[len(prefix):]
    if name.endswith("]"):
        name = name[:-1]
    return name.strip()


def _read_csv(path: Path) -> pd.DataFrame:
    """Read CSV, normalise column names, and deduplicate columns (keep first)."""
    df = pd.read_csv(path, dtype=str, low_memory=False)
    df.columns = [_normalise_column_name(c) for c in df.columns]
    if df.columns.duplicated().any():
        df = df.loc[:, ~df.columns.duplicated()]
    return df


def _is_flat_export(df: pd.DataFrame) -> bool:
    """True if the CSV looks like the 131-column flat export (has Q-code columns)."""
    q_cols = [c for c in df.columns if _Q_COL_RE.match(c)]
    return len(q_cols) > 10


_SUB_TOKEN_RE = re.compile(r"^\{SUB_Q\d+.*\}$")

# Matrix columns already pivoted in the flat export (e.g. Q11d_Compare_the_Market).
# We store these with a ParentQuestion so analytics can query by parent.
_MATRIX_PREFIX_RE = re.compile(r"^(Q\d+[a-z]?)_(.+)$")


def _split_flat_export(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split a flat wide-format export into MainData (profile) + AllOtherData (EAV).

    Profile columns stay wide. Q-code columns are un-pivoted into
    UniqueID / QuestionNumber / Answer long format.

    Handles:
      - Pipe-separated multi/ranked fields (Q2, Q8, Q9b, Q11, Q18, etc.)
      - Matrix columns (Q11d_*, Q13a_*, Q46_*, Q53_*, Q55_*)
      - {SUB_*} placeholder tokens in Q27 (filtered out)
    """
    q_cols = [c for c in df.columns if _Q_COL_RE.match(c)]
    profile_cols = [c for c in df.columns if not _Q_COL_RE.match(c)]

    df_main = df[profile_cols].copy()

    # --- Simple Q-code columns (not matrix) ---
    simple_q_cols = [c for c in q_cols if not _MATRIX_PREFIX_RE.match(c)]
    matrix_q_cols = [c for c in q_cols if _MATRIX_PREFIX_RE.match(c)]

    eav_parts = []

    # 1. Un-pivot simple Q-code columns
    if simple_q_cols:
        df_simple = df[["UniqueID"] + simple_q_cols].melt(
            id_vars="UniqueID",
            var_name="QuestionNumber",
            value_name="Answer",
        )
        df_simple = df_simple[
            df_simple["Answer"].notna()
            & (df_simple["Answer"].astype(str).str.strip() != "")
        ]

        # Pipe-separated multi/ranked fields: expand into individual rows
        pipe_mask = df_simple["Answer"].astype(str).str.contains(r"\|", na=False)
        if pipe_mask.any():
            pipe_rows = df_simple[pipe_mask].copy()
            non_pipe_rows = df_simple[~pipe_mask].copy()
            exploded = pipe_rows.assign(
                Answer=pipe_rows["Answer"].str.split(r"\s*\|\s*")
            ).explode("Answer")
            exploded["Answer"] = exploded["Answer"].str.strip()
            exploded["Rank"] = exploded.groupby(["UniqueID", "QuestionNumber"]).cumcount() + 1
            df_simple = pd.concat([non_pipe_rows, exploded], ignore_index=True)

        eav_parts.append(df_simple)

    # 2. Un-pivot matrix columns (Q11d_Compare_the_Market → Q11d / Compare the Market)
    if matrix_q_cols:
        df_matrix = df[["UniqueID"] + matrix_q_cols].melt(
            id_vars="UniqueID",
            var_name="_raw_col",
            value_name="Answer",
        )
        df_matrix = df_matrix[
            df_matrix["Answer"].notna()
            & (df_matrix["Answer"].astype(str).str.strip() != "")
        ]
        if not df_matrix.empty:
            parsed = df_matrix["_raw_col"].str.extract(_MATRIX_PREFIX_RE)
            df_matrix["QuestionNumber"] = parsed[0]
            df_matrix["MatrixItem"] = parsed[1].str.replace("_", " ")
            df_matrix = df_matrix.drop(columns=["_raw_col"])
            eav_parts.append(df_matrix)

    if not eav_parts:
        return df_main, pd.DataFrame(columns=["UniqueID", "QuestionNumber", "Answer"])

    df_eav = pd.concat(eav_parts, ignore_index=True)
    df_eav["UniqueID"] = df_eav["UniqueID"].astype(str)
    df_eav["Answer"] = df_eav["Answer"].astype(str).str.strip()

    # Remove {SUB_*} placeholder tokens (appear in Q27)
    df_eav = df_eav[~df_eav["Answer"].str.match(_SUB_TOKEN_RE, na=False)]

    # Remove any remaining empty answers
    df_eav = df_eav[df_eav["Answer"] != ""].reset_index(drop=True)

    return df_main, df_eav


def _find_file(names: list[str], dirs: list[Path]) -> Path | None:
    """Search directories for the first matching filename."""
    for d in dirs:
        if not d.exists():
            continue
        for name in names:
            candidate = d / name
            if candidate.exists():
                return candidate
    return None


# ---- Public API ----

def load_main(product: str = "Motor") -> tuple[pd.DataFrame, dict]:
    """
    Load MainData (wide, one row per respondent).

    Returns (DataFrame, metadata dict).
    """
    metadata = {"product": product, "source": None, "row_count": 0}

    # Parquet cache (already transformed)
    parquet = PROCESSED_DIR / f"{product.lower()}_main.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        metadata.update(source=str(parquet), row_count=len(df))
        return df, metadata

    # CSV search — prefer the 131-col flat export (has Q-codes) over profile-only CSVs
    main_names = {
        "Motor": [
            "ibt_motor_export_FINAL.csv", "motor all data.csv",
            "motor_main_data.csv", "motor_main_data_demo.csv",
            "motor main data.csv", "motor.csv",
        ],
        "Home": ["all home data.csv", "home_main_data.csv", "home.csv"],
    }
    search_dirs = [d for d in [_DATA_DIR_PATH, RAW_DIR, FALLBACK_DIR] if d]
    path = _find_file(main_names.get(product, []), search_dirs)
    if path is None:
        raise FileNotFoundError(f"No MainData file found for {product}.")

    df = _read_csv(path)

    if _is_flat_export(df):
        df, _ = _split_flat_export(df)

    df = transform(df, product)
    metadata.update(source=str(path), row_count=len(df))
    return df, metadata


def load_questions(product: str = "Motor") -> tuple[pd.DataFrame, dict]:
    """
    Load AllOtherData (EAV: UniqueID, QuestionNumber, Answer).

    If a dedicated AllOtherData CSV exists, load it directly.
    If only a flat export exists, un-pivot Q-code columns.
    Returns (DataFrame, metadata dict).
    """
    metadata = {"product": product, "source": None, "row_count": 0}

    # Parquet cache
    parquet = PROCESSED_DIR / f"{product.lower()}_questions.parquet"
    if parquet.exists():
        df = pd.read_parquet(parquet)
        metadata.update(source=str(parquet), row_count=len(df))
        return df, metadata

    # Dedicated AllOtherData CSV
    eav_names = [
        "all_other_data.csv", "AllOtherData.csv",
        f"{product.lower()}_all_other_data.csv",
        f"{product.lower()}_questions.csv",
    ]
    search_dirs = [d for d in [_DATA_DIR_PATH, RAW_DIR, FALLBACK_DIR] if d]
    path = _find_file(eav_names, search_dirs)
    if path:
        df = _read_csv(path)
        for col in ("UniqueID", "QuestionNumber", "Answer"):
            if col not in df.columns:
                raise ValueError(f"AllOtherData file missing required column: {col}")
        df["UniqueID"] = df["UniqueID"].astype(str)
        metadata.update(source=str(path), row_count=len(df))
        return df, metadata

    # Fall back: try flat export and un-pivot
    flat_names = {
        "Motor": [
            "ibt_motor_export_FINAL.csv", "motor all data.csv",
            "motor_main_data.csv", "motor_main_data_demo.csv",
        ],
        "Home": ["all home data.csv", "home_main_data.csv"],
    }
    path = _find_file(flat_names.get(product, []), search_dirs)
    if path:
        df = _read_csv(path)
        if _is_flat_export(df):
            _, df_eav = _split_flat_export(df)
            metadata.update(source=f"{path} (un-pivoted)", row_count=len(df_eav))
            return df_eav, metadata

    # No AllOtherData available — return empty EAV frame
    return pd.DataFrame(columns=["UniqueID", "QuestionNumber", "Answer"]), metadata


def load_data(product: str) -> tuple[pd.DataFrame, dict]:
    """
    Legacy API — loads MainData only (backward compatible with existing pages).
    Existing code that calls load_data() continues to work unchanged.
    """
    return load_main(product)
