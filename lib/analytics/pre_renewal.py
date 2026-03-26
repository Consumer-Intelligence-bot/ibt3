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


def merge_tenure_mid_buckets(tenure: pd.Series) -> pd.Series:
    """
    Collapse the 6, 7, and 8 year tenure buckets into a single '6-8 years' bucket.

    Ann noted these individual year buckets each show ~1%, likely a sample
    artefact.  Merging them produces a more stable and readable chart.

    Parameters
    ----------
    tenure : pd.Series
        Indexed by tenure label (e.g. '1 year', '2 years', ..., '10 years or more').
        Values are proportions (summing to 1.0) as returned by calc_tenure_distribution.

    Returns
    -------
    pd.Series
        New series with '6 years', '7 years', '8 years' replaced by '6-8 years'
        at the same position.  If none of those keys are present, the original
        series is returned unchanged.  The input series is never mutated.
    """
    _MID_KEYS = {"6 years", "7 years", "8 years"}
    present = [k for k in tenure.index if k in _MID_KEYS]
    if not present:
        return tenure.copy()

    merged_value = sum(tenure.get(k, 0.0) for k in present)

    # Rebuild the series in order, replacing the first mid-key position
    new_items: list[tuple[str, float]] = []
    inserted = False
    for label in tenure.index:
        if label in _MID_KEYS:
            if not inserted:
                new_items.append(("6-8 years", merged_value))
                inserted = True
            # skip the individual 6/7/8 entries
        else:
            new_items.append((label, float(tenure[label])))

    labels, values = zip(*new_items)
    return pd.Series(list(values), index=list(labels))


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
