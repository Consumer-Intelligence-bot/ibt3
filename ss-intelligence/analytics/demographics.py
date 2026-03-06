"""
Demographic filtering and active filter detection.
"""
import pandas as pd


def apply_filters(
    df: pd.DataFrame,
    insurer: str | None = None,
    age_band: str | None = None,
    region: str | None = None,
    payment_type: str | None = None,
    product: str = "Motor",
    time_window_months: int | None = None,
    selected_months: list[int] | None = None,
) -> pd.DataFrame:
    """
    Filter DataFrame by demographics. insurer=None means market (no insurer filter).

    Time filtering: if *selected_months* (list of YYYYMM ints) is provided it
    takes precedence.  Otherwise falls back to *time_window_months* (legacy).
    """
    if df is None or len(df) == 0:
        return df
    filtered = df.copy()
    filtered = filtered[filtered["Product"] == product]
    if selected_months is not None:
        filtered = _apply_selected_months(filtered, selected_months)
    elif time_window_months is not None:
        filtered = _apply_time_window(filtered, time_window_months)
    if age_band:
        filtered = filtered[filtered["AgeBand"] == age_band]
    if region:
        filtered = filtered[filtered["Region"] == region]
    if payment_type:
        filtered = filtered[filtered["PaymentType"] == payment_type]
    if insurer:
        filtered = filtered[filtered["CurrentCompany"] == insurer]
    return filtered


def _apply_selected_months(df: pd.DataFrame, months: list[int]) -> pd.DataFrame:
    """Keep only rows whose RenewalYearMonth is in the given list."""
    if not months or "RenewalYearMonth" not in df.columns:
        return df
    return df[df["RenewalYearMonth"].isin(months)]


def _apply_time_window(df: pd.DataFrame, months: int) -> pd.DataFrame:
    """Keep only rows within the last N months of RenewalYearMonth (legacy)."""
    if "RenewalYearMonth" not in df.columns or months <= 0:
        return df
    max_ym = df["RenewalYearMonth"].max()
    if pd.isna(max_ym):
        return df
    # Convert YYYYMM to months-since-epoch for comparison
    max_year = int(max_ym // 100)
    max_month = int(max_ym % 100)
    min_year = max_year - (months // 12)
    min_month = max_month - (months % 12)
    if min_month <= 0:
        min_month += 12
        min_year -= 1
    min_ym = min_year * 100 + min_month
    return df[df["RenewalYearMonth"] >= min_ym]


def get_active_filters(
    age_band: str | None,
    region: str | None,
    payment_type: str | None,
) -> dict:
    """Returns dict of active filter names and values."""
    active = {}
    if age_band:
        active["Age Band"] = age_band
    if region:
        active["Region"] = region
    if payment_type:
        active["Payment Type"] = payment_type
    return active
