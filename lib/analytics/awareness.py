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

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import MetricType, assess_confidence
from lib.config import (
    MIN_BASE_INDICATIVE,
    MIN_BASE_PUBLISHABLE,
    SYSTEM_FLOOR_N,
)
from lib.analytics.queries import count_mentions, query_multi

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


# ---------------------------------------------------------------------------
# Dual-period awareness comparison (Changes 1–5)
# ---------------------------------------------------------------------------

def _aggregate_period(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
    months: list[int],
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Aggregate awareness rates across *months* for each brand.

    Returns DataFrame with columns:
      brand, rate, raw_rate, n_mentions, n_total, rank, ci_width,
      confidence_tier ('full' | 'indicative' | 'suppress')
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

    period_main = df_main[df_main[time_col].isin(months)]
    period_mentions = mentions[mentions[time_col].isin(months)]

    total_respondents = period_main["UniqueID"].nunique()
    if total_respondents < SYSTEM_FLOOR_N:
        return pd.DataFrame()

    brand_counts = period_mentions.groupby("Answer")["UniqueID"].nunique()
    market_rate = brand_counts.sum() / (total_respondents * max(1, len(brand_counts)))

    rows = []
    for brand, n_mentions in brand_counts.items():
        rate = n_mentions / total_respondents
        smoothed = bayesian_smooth_rate(
            successes=int(n_mentions),
            trials=total_respondents,
            prior_mean=market_rate,
        )
        ci_width = (smoothed["ci_upper"] - smoothed["ci_lower"]) * 100

        # Confidence tier (Change 5)
        if total_respondents >= MIN_BASE_PUBLISHABLE:
            tier = "full"
        elif total_respondents >= MIN_BASE_INDICATIVE:
            tier = "indicative"
        else:
            tier = "suppress"

        rows.append({
            "brand": brand,
            "rate": smoothed["posterior_mean"],
            "raw_rate": rate,
            "n_mentions": int(n_mentions),
            "n_total": total_respondents,
            "ci_width": ci_width,
            "confidence_tier": tier,
        })

    if not rows:
        return pd.DataFrame()

    result = pd.DataFrame(rows)
    result["rank"] = result["rate"].rank(ascending=False, method="min").astype(int)
    return result


def calc_dual_period_comparison(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    awareness_level: str,
    period_a_months: list[int],
    period_b_months: list[int],
) -> pd.DataFrame:
    """
    Compare brand awareness between two periods.

    Returns DataFrame with columns:
      brand, rate_a, rate_b, rate_change_pp, rank_a, rank_b, rank_movement,
      n_total_a, n_total_b, tier_a, tier_b, combined_tier
    """
    agg_a = _aggregate_period(df_main, df_questions, awareness_level, period_a_months)
    agg_b = _aggregate_period(df_main, df_questions, awareness_level, period_b_months)

    if agg_a.empty or agg_b.empty:
        return pd.DataFrame()

    merged = agg_a[["brand", "rate", "rank", "n_total", "confidence_tier"]].merge(
        agg_b[["brand", "rate", "rank", "n_total", "confidence_tier"]],
        on="brand",
        suffixes=("_a", "_b"),
        how="outer",
    )

    merged["rate_a"] = merged["rate_a"].fillna(0)
    merged["rate_b"] = merged["rate_b"].fillna(0)
    merged["rate_change_pp"] = (merged["rate_b"] - merged["rate_a"]) * 100
    merged["rank_a"] = merged["rank_a"].fillna(merged["rank_a"].max() + 1).astype(int)
    merged["rank_b"] = merged["rank_b"].fillna(merged["rank_b"].max() + 1).astype(int)
    # Positive rank_movement = moved UP (rank number decreased)
    merged["rank_movement"] = merged["rank_a"] - merged["rank_b"]
    merged["abs_rank_movement"] = merged["rank_movement"].abs()

    merged["n_total_a"] = merged["n_total_a"].fillna(0).astype(int)
    merged["n_total_b"] = merged["n_total_b"].fillna(0).astype(int)
    merged["tier_a"] = merged["confidence_tier_a"].fillna("suppress")
    merged["tier_b"] = merged["confidence_tier_b"].fillna("suppress")

    # Combined tier: worst of the two (Change 5)
    tier_order = {"full": 2, "indicative": 1, "suppress": 0}
    merged["combined_tier"] = merged.apply(
        lambda r: min(
            tier_order.get(r["tier_a"], 0),
            tier_order.get(r["tier_b"], 0),
        ),
        axis=1,
    ).map({2: "full", 1: "indicative", 0: "suppress"})

    # Brand present in only one period
    merged.loc[merged["confidence_tier_a"].isna(), "combined_tier"] = "absent"
    merged.loc[merged["confidence_tier_b"].isna(), "combined_tier"] = "absent"

    cols = [
        "brand", "rate_a", "rate_b", "rate_change_pp",
        "rank_a", "rank_b", "rank_movement", "abs_rank_movement",
        "n_total_a", "n_total_b", "tier_a", "tier_b", "combined_tier",
    ]
    return merged[[c for c in cols if c in merged.columns]]


def calc_most_improved_enriched(
    comparison: pd.DataFrame,
) -> dict | None:
    """
    Rank-enriched 'Most Improved' callout (Change 2).

    Returns dict with brand, awareness scores, ranks, and movement,
    or None if no eligible brand.
    """
    if comparison.empty:
        return None

    # Only consider brands with full or indicative data in BOTH periods
    eligible = comparison[comparison["combined_tier"].isin(["full", "indicative"])]

    # Must meet n >= 50 in both periods (Change 2 suppression rule)
    eligible = eligible[
        (eligible["n_total_a"] >= MIN_BASE_PUBLISHABLE)
        & (eligible["n_total_b"] >= MIN_BASE_PUBLISHABLE)
    ]

    if eligible.empty:
        return None

    # Find brand with largest positive rank movement
    best_idx = eligible["rank_movement"].idxmax()
    best = eligible.loc[best_idx]

    # If no positive movement at all, find best rate change
    if best["rank_movement"] <= 0:
        best_idx = eligible["rate_change_pp"].idxmax()
        best = eligible.loc[best_idx]
        if best["rate_change_pp"] <= 0:
            return None

    rank_move = int(best["rank_movement"])
    if rank_move > 0:
        direction_text = f"Moved up {rank_move} positions"
    elif rank_move < 0:
        direction_text = f"Moved down {abs(rank_move)} positions"
    else:
        direction_text = "No change in rank"

    return {
        "brand": best["brand"],
        "rate_a": best["rate_a"],
        "rate_b": best["rate_b"],
        "rate_change_pp": best["rate_change_pp"],
        "rank_a": int(best["rank_a"]),
        "rank_b": int(best["rank_b"]),
        "rank_movement": rank_move,
        "direction_text": direction_text,
    }


def apply_movement_filters(
    comparison: pd.DataFrame,
    *,
    min_rank_movement: int | None = None,
    min_awareness_change_pp: float | None = None,
    top_n: int | None = None,
    pinned_brands: list[str] | None = None,
) -> pd.DataFrame:
    """
    Apply movement-threshold filters (Change 3).

    Filters are additive (AND). Pinned brands always pass.
    """
    if comparison.empty:
        return comparison

    pinned = set(pinned_brands or [])
    mask = pd.Series(True, index=comparison.index)

    if min_rank_movement is not None and min_rank_movement > 0:
        mask = mask & (comparison["abs_rank_movement"] >= min_rank_movement)

    if min_awareness_change_pp is not None and min_awareness_change_pp > 0:
        mask = mask & (comparison["rate_change_pp"].abs() >= min_awareness_change_pp)

    if top_n is not None and top_n > 0:
        top_brands = set(
            comparison.nsmallest(top_n, "rank_b")["brand"].tolist()
        )
        mask = mask & comparison["brand"].isin(top_brands)

    # Always include pinned brands
    if pinned:
        mask = mask | comparison["brand"].isin(pinned)

    return comparison[mask].copy()
