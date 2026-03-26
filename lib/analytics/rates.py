"""
Rate calculations: shopping, switching, retention, conversion.
"""
import numpy as np
import pandas as pd

from lib.config import Z_SCORE


def calc_shopping_rate(df: pd.DataFrame) -> float | None:
    """Shopping rate = % where IsShopper is True."""
    if df is None or len(df) == 0:
        return None
    return df["IsShopper"].sum() / len(df)


def calc_switching_rate(df: pd.DataFrame) -> float | None:
    """Switching rate = % where IsSwitcher is True (exclude new-to-market)."""
    if df is None or len(df) == 0:
        return None
    # Exclude new-to-market for switching rate
    base = df[~df.get("IsNewToMarket", False)]
    if len(base) == 0:
        return None
    return base["IsSwitcher"].sum() / len(base)


def calc_retention_rate(df: pd.DataFrame) -> float | None:
    """Retention rate = 1 - switching rate."""
    sw = calc_switching_rate(df)
    if sw is None:
        return None
    return 1 - sw


def calc_conversion_rate(df: pd.DataFrame) -> float | None:
    """Conversion rate = switchers / shoppers."""
    if df is None or len(df) == 0:
        return None
    shoppers = df[df["IsShopper"]]
    if len(shoppers) == 0:
        return None
    switchers = shoppers[shoppers["IsSwitcher"]]
    return len(switchers) / len(shoppers)


def calc_insurer_rank(df_market: pd.DataFrame, insurer: str, min_base: int = 50) -> dict | None:
    """Return 1-based rank of insurer among all insurers with sufficient base.

    Uses Bayesian-smoothed retention rates for ranking (consistent with the
    Insurer Comparison page sort order).

    Returns dict with 'rank' and 'total' keys, or None if insurer not eligible.
    """
    from lib.analytics.bayesian import bayesian_smooth_rate

    if df_market is None or df_market.empty:
        return None
    if "PreviousCompany" not in df_market.columns:
        return None

    existing = df_market[~df_market.get("IsNewToMarket", False)]
    insurers = existing["PreviousCompany"].dropna().loc[lambda s: s != ""].unique()

    # Market-level retention as Bayesian prior
    mkt_retained = (~existing["IsSwitcher"]).sum()
    mkt_rate = mkt_retained / len(existing) if len(existing) > 0 else 0.5

    rates = {}
    for ins in insurers:
        ins_df = existing[existing["PreviousCompany"] == ins]
        if len(ins_df) < min_base:
            continue
        retained = int((~ins_df["IsSwitcher"]).sum())
        bay = bayesian_smooth_rate(retained, len(ins_df), mkt_rate)
        rates[ins] = bay["posterior_mean"]

    if insurer not in rates:
        return None

    sorted_insurers = sorted(rates.items(), key=lambda x: x[1], reverse=True)
    for i, (name, _) in enumerate(sorted_insurers, 1):
        if name == insurer:
            return {"rank": i, "total": len(sorted_insurers)}
    return None


def calc_rolling_switching_trend(df: pd.DataFrame, window: int = 1) -> pd.DataFrame:
    """Calculate per-month switching rates with optional rolling smoothing.

    Parameters
    ----------
    df : pd.DataFrame
        Respondent-level DataFrame containing RenewalYearMonth, IsSwitcher,
        IsNewToMarket columns.
    window : int
        Rolling mean window size. 1 = no smoothing (monthly). 3 = 3-month
        rolling mean. min_periods=1 so early months are never NaN.

    Returns
    -------
    pd.DataFrame
        Columns: month (int), label (str), switching_rate (float), n (int).
        Sorted by month ascending. Empty DataFrame if input is empty or
        RenewalYearMonth column is missing.
    """
    from lib.state import format_year_month

    _EMPTY = pd.DataFrame(columns=["month", "label", "switching_rate", "n"])

    if df is None or df.empty or "RenewalYearMonth" not in df.columns:
        return _EMPTY

    months = sorted(df["RenewalYearMonth"].dropna().unique().astype(int))
    if not months:
        return _EMPTY

    rows = []
    for m in months:
        df_month = df[df["RenewalYearMonth"] == m]
        sw = calc_switching_rate(df_month)
        if sw is not None:
            rows.append({
                "month": int(m),
                "label": format_year_month(m),
                "switching_rate": sw,
                "n": len(df_month),
            })

    if not rows:
        return _EMPTY

    result = pd.DataFrame(rows)
    if window > 1:
        result = result.copy()
        result["switching_rate"] = (
            result["switching_rate"]
            .rolling(window=window, min_periods=1)
            .mean()
        )
    return result.reset_index(drop=True)


def calc_rolling_avg(by_month_df: pd.DataFrame, window: int = 3, rate_col: str = "retention") -> pd.DataFrame:
    """Add a rolling average column to a month-level rates dataframe.

    Expects by_month_df to be sorted by RenewalYearMonth with a column named rate_col.
    Returns a copy with '{rate_col}_rolling' column added.
    """
    df = by_month_df.copy()
    df[f"{rate_col}_rolling"] = df[rate_col].rolling(window=window, min_periods=1).mean()
    return df


def _wilson_score(successes: int, n: int, z: float = Z_SCORE) -> tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0, centre - margin), min(1, centre + margin))


def calc_rate_with_ci(
    df: pd.DataFrame, col: str = "IsShopper"
) -> dict | None:
    """Rate + Wilson 95% CI. col is the boolean column name."""
    if df is None or len(df) == 0:
        return None
    successes = df[col].sum()
    n = len(df)
    rate = successes / n
    ci_lower, ci_upper = _wilson_score(int(successes), n)
    return {
        "rate": rate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n": n,
    }
