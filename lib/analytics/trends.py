"""
Trend calculation: compare recent vs earlier half of selected period.

Spec Section 12.3:
  - Show trend when both halves meet minimum base AND change exceeds avg CI width.
  - Suppress when either half is below minimum base, time window too short,
    or change does not exceed the CI-width noise threshold.
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import calc_ci_width
from lib.config import MIN_BASE_TREND


def calc_trend(
    df: pd.DataFrame,
    market_rate: float,
    rate_col: str = "IsRetained",
    time_col: str = "RenewalYearMonth",
    exclude_new: bool = True,
) -> dict:
    """
    Split the data into earlier and recent halves by renewal month, compute
    Bayesian-smoothed retention in each half, and determine trend direction.

    Returns:
        direction: "up" | "down" | "stable" | None (suppressed)
        change: absolute change in pp (recent minus earlier)
        ci_threshold: average CI width across the two periods
        earlier_rate, recent_rate: smoothed rates
        suppressed: True if trend cannot be shown
    """
    result = {
        "direction": None,
        "change": None,
        "ci_threshold": None,
        "earlier_rate": None,
        "recent_rate": None,
        "suppressed": True,
    }

    if df is None or len(df) == 0 or time_col not in df.columns:
        return result

    months = sorted(df[time_col].dropna().unique())
    if len(months) < 2:
        return result

    mid = len(months) // 2
    earlier_months = set(months[:mid])
    recent_months = set(months[mid:])

    df_earlier = df[df[time_col].isin(earlier_months)]
    df_recent = df[df[time_col].isin(recent_months)]

    if exclude_new and "IsNewToMarket" in df.columns:
        df_earlier = df_earlier[~df_earlier["IsNewToMarket"]]
        df_recent = df_recent[~df_recent["IsNewToMarket"]]

    n_earlier = len(df_earlier)
    n_recent = len(df_recent)

    if n_earlier < MIN_BASE_TREND or n_recent < MIN_BASE_TREND:
        return result

    retained_e = df_earlier[rate_col].sum() if rate_col in df_earlier.columns else 0
    retained_r = df_recent[rate_col].sum() if rate_col in df_recent.columns else 0

    bay_e = bayesian_smooth_rate(int(retained_e), n_earlier, market_rate)
    bay_r = bayesian_smooth_rate(int(retained_r), n_recent, market_rate)

    ci_w_e = (bay_e["ci_upper"] - bay_e["ci_lower"]) * 100
    ci_w_r = (bay_r["ci_upper"] - bay_r["ci_lower"]) * 100
    avg_ci = (ci_w_e + ci_w_r) / 2

    change_pp = (bay_r["posterior_mean"] - bay_e["posterior_mean"]) * 100

    if abs(change_pp) <= avg_ci:
        direction = "stable"
    elif change_pp > 0:
        direction = "up"
    else:
        direction = "down"

    return {
        "direction": direction,
        "change": change_pp,
        "ci_threshold": avg_ci,
        "earlier_rate": bay_e["posterior_mean"],
        "recent_rate": bay_r["posterior_mean"],
        "suppressed": False,
    }
