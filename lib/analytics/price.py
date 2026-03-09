"""
Price sensitivity analysis.
"""
import pandas as pd


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
