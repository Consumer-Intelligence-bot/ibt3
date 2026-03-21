"""
Pre-renewal analytics: Q6 price direction, Q6a/Q6b bands, Q21 tenure,
and price-to-shopping crossover (Q6 x Q7).
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.rates import calc_shopping_rate


def calc_tenure_distribution(df: pd.DataFrame) -> pd.Series | None:
    """Distribution of Q21 tenure with current insurer."""
    if df is None or df.empty or "Q21" not in df.columns:
        return None
    valid = df[df["Q21"].notna() & (df["Q21"].astype(str).str.strip() != "")]
    if valid.empty:
        return None
    return valid["Q21"].value_counts(normalize=True).sort_index()


def calc_price_shopping_crossover(df: pd.DataFrame) -> pd.DataFrame | None:
    """Shopping rate by price direction (Q6 x Q7 crossover).

    Returns DataFrame with columns: direction, shopping_rate, n.
    """
    if df is None or df.empty:
        return None
    if "PriceDirection" not in df.columns or "IsShopper" not in df.columns:
        return None

    valid = df[df["PriceDirection"].notna() & (df["PriceDirection"] != "")]
    if valid.empty:
        return None

    rows = []
    for direction in ["Higher", "Lower", "Unchanged"]:
        subset = valid[valid["PriceDirection"] == direction]
        n = len(subset)
        if n > 0:
            rate = calc_shopping_rate(subset)
            rows.append({"direction": direction, "shopping_rate": rate, "n": n})

    return pd.DataFrame(rows) if rows else None


def calc_tenure_retention_crossover(df: pd.DataFrame) -> pd.DataFrame | None:
    """Retention rate by tenure band (Q21 x IsRetained).

    Returns DataFrame with columns: tenure, retention_rate, n.
    """
    if df is None or df.empty:
        return None
    if "Q21" not in df.columns or "IsRetained" not in df.columns:
        return None

    valid = df[df["Q21"].notna() & (df["Q21"].astype(str).str.strip() != "")]
    if valid.empty:
        return None

    rows = []
    for tenure in sorted(valid["Q21"].unique(), key=str):
        subset = valid[valid["Q21"] == tenure]
        n = len(subset)
        if n >= 10:
            rate = subset["IsRetained"].mean()
            rows.append({"tenure": str(tenure), "retention_rate": rate, "n": n})

    return pd.DataFrame(rows) if rows else None
