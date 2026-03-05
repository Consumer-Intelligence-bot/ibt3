"""
Brand awareness analytics using EAV data.

Supports:
  - Prompted awareness (Q2) — multi-select brand mentions
  - Consideration (Q27) — multi-select brand mentions
  - Spontaneous (Q1) — GATED: not available in current data wave

All functions accept df_main (MainData) and df_questions (AllOtherData EAV).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from analytics.bayesian import bayesian_smooth_rate
from analytics.confidence import MetricType, assess_confidence
from config import SYSTEM_FLOOR_N
from data.queries import count_mentions, query_multi

# Maps awareness level names to Q-codes
AWARENESS_LEVELS = {
    "prompted": "Q2",
    "consideration": "Q27",
}

Q1_GATING_MESSAGE = "Spontaneous awareness (Q1) is not available in the current data wave."


def _get_q_code(awareness_level: str) -> str | None:
    """Return Q-code for an awareness level, or None if gated."""
    if awareness_level == "spontaneous":
        return None
    return AWARENESS_LEVELS.get(awareness_level)


def calc_awareness_rates(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Awareness rate per brand per month.

    Returns DataFrame with columns:
      brand, month, rate, ci_lower, ci_upper, ci_width, n_mentions, n_total, rank
    """
    q_code = _get_q_code(awareness_level)
    if q_code is None or df_questions.empty:
        return pd.DataFrame()

    mentions = query_multi(df_questions, q_code)
    if mentions.empty:
        return pd.DataFrame()

    mentions = mentions.merge(
        df_main[["UniqueID", time_col]].drop_duplicates(),
        on="UniqueID",
        how="left",
    )

    months = sorted(df_main[time_col].dropna().unique())
    rows = []

    for month in months:
        total_respondents = len(df_main[df_main[time_col] == month])
        if total_respondents < SYSTEM_FLOOR_N:
            continue

        month_mentions = mentions[mentions[time_col] == month]
        brand_counts = month_mentions.groupby("Answer")["UniqueID"].nunique()

        market_rate = brand_counts.sum() / (total_respondents * max(1, len(brand_counts)))

        for brand, n_mentions in brand_counts.items():
            rate = n_mentions / total_respondents
            smoothed = bayesian_smooth_rate(
                successes=int(n_mentions),
                trials=total_respondents,
                prior_mean=market_rate,
            )
            rows.append({
                "brand": brand,
                "month": month,
                "rate": smoothed["posterior_mean"],
                "raw_rate": rate,
                "ci_lower": smoothed["ci_lower"],
                "ci_upper": smoothed["ci_upper"],
                "ci_width": (smoothed["ci_upper"] - smoothed["ci_lower"]) * 100,
                "n_mentions": int(n_mentions),
                "n_total": total_respondents,
                "weight": smoothed["weight"],
            })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result["rank"] = result.groupby("month")["rate"].rank(ascending=False, method="min").astype(int)
    return result


def calc_awareness_bump(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
) -> pd.DataFrame:
    """
    Rank-by-month for bump chart.

    Returns: brand, month, rank, rate.
    Spec 9.4: brands are excluded entirely if they lack eligible data in any
    month of the selected period — ensures continuous lines with no gaps.
    """
    rates = calc_awareness_rates(df_main, df_questions, awareness_level)
    if rates.empty:
        return pd.DataFrame()

    all_months = rates["month"].nunique()
    brand_months = rates.groupby("brand")["month"].nunique()
    eligible = brand_months[brand_months >= all_months].index
    return rates[rates["brand"].isin(eligible)][["brand", "month", "rank", "rate"]].copy()


def calc_awareness_slopegraph(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    brand: str,
    awareness_level: str,
) -> dict | None:
    """
    Start/end rate + change for slopegraph panels (Page 6).

    Returns dict with insurer and market rates at start and end of period.
    If start or end month is suppressed for this brand, uses nearest eligible month.
    """
    rates = calc_awareness_rates(df_main, df_questions, awareness_level)
    if rates.empty:
        return None

    brand_data = rates[rates["brand"] == brand].sort_values("month")
    if len(brand_data) < 2:
        return None

    start = brand_data.iloc[0]
    end = brand_data.iloc[-1]
    change = end["rate"] - start["rate"]

    # Market average at start and end months
    start_mkt = rates[rates["month"] == start["month"]]["rate"].mean()
    end_mkt = rates[rates["month"] == end["month"]]["rate"].mean()

    conf = assess_confidence(
        n=int(end["n_total"]),
        rate=end["rate"],
        metric_type=MetricType.AWARENESS,
        posterior_ci_width=end["ci_width"],
    )

    return {
        "start_month": start["month"],
        "end_month": end["month"],
        "start_rate": start["rate"],
        "end_rate": end["rate"],
        "start_market_rate": start_mkt,
        "end_market_rate": end_mkt,
        "change": change,
        "direction": "up" if change > 0 else ("down" if change < 0 else "flat"),
        "confidence": conf.label.value,
        "can_show": conf.can_show,
    }


def calc_awareness_market_bands(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
) -> pd.DataFrame:
    """
    25th–75th percentile band per month across eligible brands.

    Returns DataFrame: month, p25, median, p75.
    Used as context band on Page 6 trend chart.
    """
    rates = calc_awareness_rates(df_main, df_questions, awareness_level)
    if rates.empty:
        return pd.DataFrame()

    bands = rates.groupby("month")["rate"].agg(
        p25=lambda x: np.percentile(x, 25),
        median="median",
        p75=lambda x: np.percentile(x, 75),
    ).reset_index()
    return bands


def calc_awareness_summary(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
) -> dict | None:
    """
    Summary strip KPIs for Page 5.

    Returns: n_brands, top_brand_rate, top_brand_name, mean_rate,
             most_improved_name, most_improved_change, period_start, period_end
    """
    rates = calc_awareness_rates(df_main, df_questions, awareness_level)
    if rates.empty:
        return None

    latest_month = rates["month"].max()
    earliest_month = rates["month"].min()
    latest = rates[rates["month"] == latest_month]

    # Most improved: brand with largest positive change from earliest to latest month
    most_improved_name = None
    most_improved_change = None
    if earliest_month != latest_month:
        earliest = rates[rates["month"] == earliest_month]
        merged = latest[["brand", "rate"]].merge(
            earliest[["brand", "rate"]], on="brand", suffixes=("_end", "_start"),
        )
        if not merged.empty:
            merged["change"] = merged["rate_end"] - merged["rate_start"]
            best = merged.loc[merged["change"].idxmax()]
            most_improved_name = best["brand"]
            most_improved_change = best["change"]

    return {
        "n_brands": latest["brand"].nunique(),
        "top_brand_name": latest.loc[latest["rate"].idxmax(), "brand"] if not latest.empty else None,
        "top_brand_rate": latest["rate"].max() if not latest.empty else None,
        "mean_rate": latest["rate"].mean() if not latest.empty else None,
        "most_improved_name": most_improved_name,
        "most_improved_change": most_improved_change,
        "period_start": int(earliest_month),
        "period_end": int(latest_month),
    }
