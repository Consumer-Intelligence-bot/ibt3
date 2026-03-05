"""
Data refresh entry point.

Validates source data, applies transforms, pre-computes Bayesian rates,
and saves Parquet cache for fast startup.

Usage:
    python -m data.refresh            # from ss-intelligence/
    python data/refresh.py Motor      # explicit product
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data.loader import PROCESSED_DIR, load_main, load_questions


def _validate(df_main: pd.DataFrame, df_questions: pd.DataFrame) -> list[str]:
    """Run validation checks. Returns list of warnings (empty = OK)."""
    warnings = []

    if "UniqueID" not in df_main.columns:
        warnings.append("MainData missing UniqueID column")
        return warnings

    dup = df_main["UniqueID"].duplicated().sum()
    if dup > 0:
        warnings.append(f"{dup} duplicate UniqueIDs in MainData")

    for col in ("CurrentCompany", "RenewalYearMonth", "Switchers", "Shoppers"):
        if col not in df_main.columns:
            warnings.append(f"MainData missing expected column: {col}")

    if df_questions.empty:
        warnings.append("AllOtherData is empty — EAV queries will return no results")
    else:
        for col in ("UniqueID", "QuestionNumber", "Answer"):
            if col not in df_questions.columns:
                warnings.append(f"AllOtherData missing column: {col}")
        q_ids = set(df_questions["UniqueID"].unique())
        m_ids = set(df_main["UniqueID"].unique())
        orphans = q_ids - m_ids
        if orphans:
            warnings.append(f"{len(orphans)} AllOtherData respondents not in MainData")

    return warnings


def refresh(product: str = "Motor"):
    """Full refresh pipeline: load → validate → cache."""
    print(f"[refresh] Loading {product}...")
    t0 = time.time()

    df_main, meta_main = load_main(product)
    print(f"  MainData: {len(df_main):,} rows from {meta_main['source']}")

    df_questions, meta_q = load_questions(product)
    print(f"  AllOtherData: {len(df_questions):,} rows from {meta_q['source']}")

    # Validate
    warnings = _validate(df_main, df_questions)
    for w in warnings:
        print(f"  WARNING: {w}")

    # Save Parquet cache
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    main_path = PROCESSED_DIR / f"{product.lower()}_main.parquet"
    q_path = PROCESSED_DIR / f"{product.lower()}_questions.parquet"

    df_main.to_parquet(main_path, index=False)
    print(f"  Cached MainData → {main_path}")

    if not df_questions.empty:
        df_questions.to_parquet(q_path, index=False)
        print(f"  Cached AllOtherData → {q_path}")

    # Pre-compute Bayesian rates
    try:
        from analytics.bayesian_precompute import precompute_all
        precompute_all(product)
        print("  Bayesian rates pre-computed")
    except (ImportError, Exception) as e:
        print(f"  Bayesian pre-compute skipped: {e}")

    elapsed = time.time() - t0
    status = "OK" if not warnings else f"{len(warnings)} warnings"
    print(f"[refresh] Done in {elapsed:.1f}s — {status}")
    return warnings


if __name__ == "__main__":
    product = sys.argv[1] if len(sys.argv) > 1 else "Motor"
    refresh(product)
