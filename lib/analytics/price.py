"""
Price sensitivity analysis.
"""
from __future__ import annotations

import pandas as pd

from lib.config import MIN_BASE_REASON


# ---------------------------------------------------------------------------
# Midpoint mapping for price change bands (Q6a / Q6b)
# ---------------------------------------------------------------------------

BAND_MIDPOINTS = {
    "£10 or less a year": 5.0,
    "£11 to £20 a year": 15.5,
    "£21 to £30 a year": 25.5,
    "£31 to £40 a year": 35.5,
    "£41 to £50 a year": 45.5,
    "£51 to £75 a year": 63.0,
    "£76 to £100 a year": 88.0,
    "£101 to £125 a year": 113.0,
    "£126 to £150 a year": 138.0,
    "£151 to £250 a year": 200.5,
    "£251 to £350 a year": 300.5,
    "Over £350 a year": 525.0,
}


def calc_price_direction_dist(df: pd.DataFrame) -> pd.Series | None:
    """Distribution of PriceDirection (Higher/Lower/Unchanged/New)."""
    if df is None or len(df) == 0 or "PriceDirection" not in df.columns:
        return None
    valid = df[df["PriceDirection"].notna() & (df["PriceDirection"] != "")]
    if len(valid) == 0:
        return None
    return valid["PriceDirection"].value_counts(normalize=True)


def calc_rate_by_price_direction(
    df: pd.DataFrame, rate_func, exclude_new: bool = True
) -> pd.DataFrame | None:
    """Shopping or switching rate segmented by price direction."""
    if df is None or len(df) == 0:
        return None
    if exclude_new:
        df = df[df["PriceDirection"] != "New"]
    if len(df) == 0:
        return None
    results = []
    for direction in ["Higher", "Lower", "Unchanged", "New"]:
        subset = df[df["PriceDirection"] == direction]
        if len(subset) > 0:
            rate = rate_func(subset)
            results.append({"direction": direction, "rate": rate, "n": len(subset)})
    return pd.DataFrame(results) if results else None


def calc_price_magnitude_dist(
    df: pd.DataFrame, direction: str
) -> pd.Series | None:
    """Distribution of Q6a (Higher) or Q6b (Lower) bands."""
    col = "Q6a" if direction == "Higher" else "Q6b"
    if df is None or col not in df.columns:
        return None
    subset = df[df["PriceDirection"] == direction]
    if len(subset) == 0:
        return None
    return subset[col].value_counts(normalize=True)


def calc_switching_savings_dist(df: pd.DataFrame) -> pd.Series | None:
    """Distribution of Q30 savings bands for switchers."""
    if df is None or "Q30" not in df.columns:
        return None
    switchers = df[df["IsSwitcher"]]
    if len(switchers) == 0:
        return None
    return switchers["Q30"].value_counts(normalize=True)


def calc_median_band(series: pd.Series) -> str | None:
    """Most common band (mode) for banded data."""
    if series is None or len(series) == 0:
        return None
    mode = series.mode()
    return str(mode.iloc[0]) if len(mode) > 0 else None


# ---------------------------------------------------------------------------
# Price Change Analysis (Dual Lens)
# ---------------------------------------------------------------------------

def _assign_signed_midpoint(row: pd.Series) -> float | None:
    """Map a respondent's price band to a signed midpoint value.

    Higher = positive, Lower = negative, Unchanged/New = 0.
    """
    direction = row.get("PriceDirection")
    if direction == "Higher" and "Q6a" in row.index:
        band = row["Q6a"]
        mid = BAND_MIDPOINTS.get(str(band).strip()) if pd.notna(band) else None
        return mid  # positive
    elif direction == "Lower" and "Q6b" in row.index:
        band = row["Q6b"]
        mid = BAND_MIDPOINTS.get(str(band).strip()) if pd.notna(band) else None
        return -mid if mid is not None else None  # negative
    elif direction in ("Unchanged", "New"):
        return 0.0
    return None


def calc_avg_price_change(df: pd.DataFrame, brand: str | None = None) -> dict | None:
    """
    Average signed price change using midpoints.

    Parameters
    ----------
    df : DataFrame with PriceDirection, Q6a, Q6b, and optionally PreRenewalCompany.
    brand : If provided, filter to respondents whose PreRenewalCompany matches.

    Returns
    -------
    dict with avg_change, n, direction_split (Series of direction counts).
    """
    if df is None or df.empty or "PriceDirection" not in df.columns:
        return None

    data = df.copy()
    if brand and "PreRenewalCompany" in data.columns:
        data = data[data["PreRenewalCompany"] == brand]

    if data.empty:
        return None

    data["_midpoint"] = data.apply(_assign_signed_midpoint, axis=1)
    valid = data[data["_midpoint"].notna()]

    if len(valid) == 0:
        return None

    direction_split = data["PriceDirection"].value_counts()

    return {
        "avg_change": float(valid["_midpoint"].mean()),
        "n": len(valid),
        "direction_split": direction_split,
    }


def calc_price_direction_index(
    insurer_dist: pd.Series | None,
    market_dist: pd.Series | None,
) -> pd.DataFrame | None:
    """
    Compare insurer vs market price direction distributions as an index.

    Instead of showing two side-by-side bar charts that look near-identical,
    express the difference as percentage-point (pp) deviations from the market.

    Parameters
    ----------
    insurer_dist : pd.Series | None
        Normalised distribution for the selected insurer (0–1 proportions),
        as returned by calc_price_direction_dist.
    market_dist : pd.Series | None
        Normalised distribution for the full market.

    Returns
    -------
    pd.DataFrame | None
        Columns: direction, insurer_pct, market_pct, diff_pp
        - insurer_pct / market_pct are in percentage points (0–100).
        - diff_pp = insurer_pct − market_pct (positive = insurer above market).
        Returns None when either input is None or empty.
    """
    if insurer_dist is None or market_dist is None:
        return None
    if len(insurer_dist) == 0 or len(market_dist) == 0:
        return None

    all_directions = sorted(set(insurer_dist.index) | set(market_dist.index))
    rows = []
    for direction in all_directions:
        ins_pct = float(insurer_dist.get(direction, 0.0)) * 100
        mkt_pct = float(market_dist.get(direction, 0.0)) * 100
        rows.append({
            "direction": direction,
            "insurer_pct": ins_pct,
            "market_pct": mkt_pct,
            "diff_pp": ins_pct - mkt_pct,
        })

    return pd.DataFrame(rows)


def calc_price_change_comparison(
    df: pd.DataFrame, brand: str
) -> dict | None:
    """
    Compare brand's average price change vs all others.

    Returns dict with 'brand' and 'others' keys, each containing
    the output of calc_avg_price_change.
    """
    if df is None or df.empty:
        return None

    brand_result = calc_avg_price_change(df, brand=brand)
    if brand_result is None:
        return None

    if "PreRenewalCompany" in df.columns:
        others_df = df[df["PreRenewalCompany"] != brand]
    else:
        others_df = df

    others_result = calc_avg_price_change(others_df)

    return {"brand": brand_result, "others": others_result}


def calc_price_change_by_demo(
    df: pd.DataFrame,
    demo_col: str,
    brand: str | None = None,
) -> pd.DataFrame | None:
    """
    Average price change broken down by a demographic column.

    Returns DataFrame with columns: group, avg_change, n, flag_low_n.
    Groups with n < MIN_BASE_REASON are flagged.
    """
    if df is None or df.empty or demo_col not in df.columns:
        return None

    data = df.copy()
    if brand and "PreRenewalCompany" in data.columns:
        data = data[data["PreRenewalCompany"] == brand]

    if data.empty:
        return None

    data["_midpoint"] = data.apply(_assign_signed_midpoint, axis=1)
    valid = data[data["_midpoint"].notna()]

    if valid.empty:
        return None

    grouped = (
        valid.groupby(demo_col)["_midpoint"]
        .agg(avg_change="mean", n="count")
        .reset_index()
        .rename(columns={demo_col: "group"})
    )
    grouped["flag_low_n"] = grouped["n"] < MIN_BASE_REASON

    return grouped
