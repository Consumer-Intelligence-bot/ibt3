"""
Satisfaction analytics: Q47, Q48, Q46, Q40a/Q40b, satisfaction-retention matrix.
"""
from __future__ import annotations

import pandas as pd
import numpy as np


def calc_overall_satisfaction(df: pd.DataFrame, q_col: str = "Q47") -> dict | None:
    """Mean satisfaction score and distribution from Q47 (current insurer)."""
    if df is None or df.empty or q_col not in df.columns:
        return None
    vals = pd.to_numeric(df[q_col], errors="coerce").dropna()
    if len(vals) == 0:
        return None
    return {
        "mean": float(vals.mean()),
        "median": float(vals.median()),
        "n": len(vals),
        "distribution": vals.value_counts(normalize=True).sort_index().to_dict(),
    }


def calc_nps(df: pd.DataFrame, q_col: str = "Q48") -> dict | None:
    """NPS calculation from Q48 (recommend current insurer, 0-10 scale)."""
    if df is None or df.empty or q_col not in df.columns:
        return None
    vals = pd.to_numeric(df[q_col], errors="coerce").dropna()
    if len(vals) == 0:
        return None
    promoters = (vals >= 9).sum()
    detractors = (vals <= 6).sum()
    passives = len(vals) - promoters - detractors
    nps = 100 * (promoters - detractors) / len(vals)
    return {
        "nps": float(nps),
        "promoters_pct": float(promoters / len(vals)),
        "detractors_pct": float(detractors / len(vals)),
        "passives_pct": float(passives / len(vals)),
        "n": len(vals),
    }


def calc_brand_perception(df: pd.DataFrame, insurer: str | None = None) -> pd.DataFrame | None:
    """Q46 brand perception matrix: mean scores per subject.

    Returns DataFrame with columns: subject, mean_score, n.
    """
    if df is None or df.empty:
        return None

    if insurer:
        df = df[df["CurrentCompany"] == insurer]

    q46_cols = [c for c in df.columns if c.startswith("Q46_")]
    if not q46_cols:
        return None

    rows = []
    for col in q46_cols:
        subject = col[4:]  # strip "Q46_"
        vals = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(vals) >= 10:
            rows.append({
                "subject": subject,
                "mean_score": float(vals.mean()),
                "n": len(vals),
            })

    return pd.DataFrame(rows) if rows else None


def calc_satisfaction_retention_matrix(df: pd.DataFrame) -> pd.DataFrame | None:
    """Cross-tabulate satisfaction quintile by retention status.

    Returns DataFrame with columns: satisfaction_band, retained_pct, n.
    """
    if df is None or df.empty:
        return None
    if "Q47" not in df.columns or "IsRetained" not in df.columns:
        return None

    df = df.copy()
    df["Q47_num"] = pd.to_numeric(df["Q47"], errors="coerce")
    valid = df[df["Q47_num"].notna()]
    if len(valid) < 30:
        return None

    # Band into quintiles (1-2, 2-3, 3-4, 4-5)
    bins = [0, 2, 3, 4, 5.01]
    labels = ["1-2 (Low)", "2-3", "3-4", "4-5 (High)"]
    valid["sat_band"] = pd.cut(valid["Q47_num"], bins=bins, labels=labels, include_lowest=True)

    rows = []
    for band in labels:
        subset = valid[valid["sat_band"] == band]
        n = len(subset)
        if n >= 10:
            retained_pct = subset["IsRetained"].mean()
            rows.append({
                "satisfaction_band": band,
                "retained_pct": float(retained_pct),
                "n": n,
            })

    return pd.DataFrame(rows) if rows else None


def calc_previous_insurer_satisfaction(
    df: pd.DataFrame, insurer: str | None = None
) -> dict | None:
    """Q40a/Q40b satisfaction and NPS for previous insurer (departed customers)."""
    if df is None or df.empty:
        return None

    if insurer:
        # Customers who left this insurer
        departed = df[(df["IsSwitcher"]) & (df["PreviousCompany"] == insurer)] if "PreviousCompany" in df.columns else pd.DataFrame()
    else:
        departed = df[df["IsSwitcher"]] if "IsSwitcher" in df.columns else pd.DataFrame()

    if departed.empty:
        return None

    result = {"n": len(departed)}

    if "Q40a" in departed.columns:
        vals = pd.to_numeric(departed["Q40a"], errors="coerce").dropna()
        if len(vals) > 0:
            result["mean_q40a"] = float(vals.mean())

    if "Q40b" in departed.columns:
        vals = pd.to_numeric(departed["Q40b"], errors="coerce").dropna()
        if len(vals) > 0:
            promoters = (vals >= 9).sum()
            detractors = (vals <= 6).sum()
            result["nps"] = float(100 * (promoters - detractors) / len(vals))

    return result
