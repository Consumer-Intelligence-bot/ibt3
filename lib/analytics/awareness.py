"""
Brand awareness analytics using wide-format question data.

Supports:
  - Prompted awareness (Q2) — multi-select boolean columns Q2_{brand}
  - Consideration (Q27) — multi-select boolean columns Q27_{brand}
  - Spontaneous (Q1) — GATED: not available in current data wave

All functions accept df_main (the single wide DataFrame with question columns).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lib.analytics.bayesian import bayesian_change_test, bayesian_smooth_rate
from lib.analytics.confidence import MetricType, assess_confidence
from lib.config import (
    MIN_BASE_INDICATIVE,
    MIN_BASE_PUBLISHABLE,
    SYSTEM_FLOOR_N,
)

# Maps awareness level names to Q-codes, per product
AWARENESS_LEVELS = {
    "Motor": {"spontaneous": "Q1", "prompted": "Q2", "consideration": "Q27"},
    "Home": {"spontaneous": "Q1", "prompted": "Q2", "consideration": "Q27"},
    "Pet": {"prompted": "PET_PROMPTED_AWARENESS", "consideration": "PET_CONSIDERATION"},
}

# Flat default for backward compatibility (Motor/Home)
_DEFAULT_LEVELS = AWARENESS_LEVELS["Motor"]

Q1_GATING_MESSAGE = "Spontaneous awareness (Q1) is not available in the current data wave."

# Current product context for awareness functions
_current_product = "Motor"


def set_awareness_product(product: str) -> None:
    """Set the product context for awareness calculations."""
    global _current_product
    _current_product = product


def _get_q_code(awareness_level: str) -> str | None:
    """Return Q-code for an awareness level, or None if gated."""
    levels = AWARENESS_LEVELS.get(_current_product, _DEFAULT_LEVELS)
    return levels.get(awareness_level)


def _brand_cols(df: pd.DataFrame, q_code: str) -> list[str]:
    """Return boolean column names for a multi-code question.

    Excludes position columns (Q1_pos*), survey artefacts ({SUB_*}),
    and _Other columns.
    """
    prefix = f"{q_code}_"
    return [
        c for c in df.columns
        if c.startswith(prefix)
        and not c.startswith(f"{q_code}_pos")   # Q1_pos1a etc. (text, not bool)
        and not c.startswith(f"{q_code}_{{")    # {SUB_Q...} artefacts
        and c != f"{q_code}_Other"
        and c != f"{q_code}_None of these"
        and pd.api.types.is_bool_dtype(df[c])
    ]


def calc_awareness_rates(
    df_main: pd.DataFrame,
    awareness_level: str,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Awareness rate per brand per month.

    Returns DataFrame with columns:
      brand, month, rate, ci_lower, ci_upper, ci_width, n_mentions, n_total, rank
    """
    q_code = _get_q_code(awareness_level)
    if q_code is None:
        return pd.DataFrame()

    cols = _brand_cols(df_main, q_code)
    if not cols:
        return pd.DataFrame()

    prefix = f"{q_code}_"
    months = sorted(df_main[time_col].dropna().unique())
    rows = []

    for month in months:
        month_data = df_main[df_main[time_col] == month]

        # Denominator: respondents who answered this question (have at least
        # one True in any brand column), NOT all MainData respondents.
        # This matches the fieldwork base and avoids deflating rates when
        # only a subset of respondents were shown the question.
        answered_mask = month_data[cols].any(axis=1)
        total_respondents = int(answered_mask.sum())
        if total_respondents < SYSTEM_FLOOR_N:
            continue

        # Compute market rate across all brands for Bayesian prior
        total_mentions = sum(int(month_data[col].sum()) for col in cols)
        n_brands_with_data = sum(1 for col in cols if month_data[col].sum() > 0)
        market_rate = total_mentions / (total_respondents * max(1, n_brands_with_data))

        for col in cols:
            brand = col[len(prefix):]
            n_mentions = int(month_data[col].sum())
            if n_mentions == 0:
                continue
            rate = n_mentions / total_respondents
            smoothed = bayesian_smooth_rate(
                successes=n_mentions,
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
                "n_mentions": n_mentions,
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
    awareness_level: str,
) -> pd.DataFrame:
    """
    Rank-by-month for bump chart.

    Returns: brand, month, rank, rate.
    Spec 9.4: brands are excluded entirely if they lack eligible data in any
    month of the selected period — ensures continuous lines with no gaps.
    """
    rates = calc_awareness_rates(df_main, awareness_level)
    if rates.empty:
        return pd.DataFrame()

    all_months = rates["month"].nunique()
    brand_months = rates.groupby("brand")["month"].nunique()
    eligible = brand_months[brand_months >= all_months].index
    return rates[rates["brand"].isin(eligible)][["brand", "month", "rank", "rate"]].copy()


def calc_awareness_slopegraph(
    df_main: pd.DataFrame,
    brand: str,
    awareness_level: str,
) -> dict | None:
    """
    Start/end rate + change for slopegraph panels (Page 6).

    Returns dict with insurer and market rates at start and end of period.
    If start or end month is suppressed for this brand, uses nearest eligible month.
    """
    rates = calc_awareness_rates(df_main, awareness_level)
    if rates.empty:
        return None

    brand_data = rates[rates["brand"] == brand].sort_values("month")
    if len(brand_data) < 2:
        return None

    start = brand_data.iloc[0]

    # Use the last month with an acceptable CI width as the end point.
    # Trailing months often have thin data (incomplete fieldwork).
    from lib.config import CI_WIDTH_INDICATIVE_AWARENESS
    eligible_end = brand_data[brand_data["ci_width"] <= CI_WIDTH_INDICATIVE_AWARENESS]
    if eligible_end.empty:
        # Fall back to best available month (lowest CI width)
        end = brand_data.loc[brand_data["ci_width"].idxmin()]
    else:
        end = eligible_end.iloc[-1]

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
    awareness_level: str,
) -> pd.DataFrame:
    """
    25th-75th percentile band per month across eligible brands.

    Returns DataFrame: month, p25, median, p75.
    Used as context band on Page 6 trend chart.
    """
    rates = calc_awareness_rates(df_main, awareness_level)
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
    awareness_level: str,
) -> dict | None:
    """
    Summary strip KPIs for Page 5.

    Returns: n_brands, top_brand_rate, top_brand_name, mean_rate,
             most_improved_name, most_improved_change, period_start, period_end
    """
    rates = calc_awareness_rates(df_main, awareness_level)
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
# Dual-period awareness comparison (Changes 1-5)
# ---------------------------------------------------------------------------

def _aggregate_period(
    df_main: pd.DataFrame,
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
    if q_code is None:
        return pd.DataFrame()

    cols = _brand_cols(df_main, q_code)
    if not cols:
        return pd.DataFrame()

    prefix = f"{q_code}_"
    period_data = df_main[df_main[time_col].isin(months)]
    # Denominator: respondents who answered this question
    answered_mask = period_data[cols].any(axis=1)
    total_respondents = int(answered_mask.sum())
    if total_respondents < SYSTEM_FLOOR_N:
        return pd.DataFrame()

    # Count mentions per brand across the whole period
    brand_counts = {}
    for col in cols:
        brand = col[len(prefix):]
        n = int(period_data[col].sum())
        if n > 0:
            brand_counts[brand] = n

    if not brand_counts:
        return pd.DataFrame()

    total_mentions = sum(brand_counts.values())
    market_rate = total_mentions / (total_respondents * max(1, len(brand_counts)))

    # Confidence tier (Change 5)
    if total_respondents >= MIN_BASE_PUBLISHABLE:
        tier = "full"
    elif total_respondents >= MIN_BASE_INDICATIVE:
        tier = "indicative"
    else:
        tier = "suppress"

    rows = []
    for brand, n_mentions in brand_counts.items():
        rate = n_mentions / total_respondents
        smoothed = bayesian_smooth_rate(
            successes=n_mentions,
            trials=total_respondents,
            prior_mean=market_rate,
        )
        ci_width = (smoothed["ci_upper"] - smoothed["ci_lower"]) * 100
        rows.append({
            "brand": brand,
            "rate": smoothed["posterior_mean"],
            "raw_rate": rate,
            "n_mentions": n_mentions,
            "n_total": total_respondents,
            "ci_width": ci_width,
            "confidence_tier": tier,
        })

    result = pd.DataFrame(rows)
    result["rank"] = result["rate"].rank(ascending=False, method="min").astype(int)
    return result


def calc_dual_period_comparison(
    df_main: pd.DataFrame,
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
    agg_a = _aggregate_period(df_main, awareness_level, period_a_months)
    agg_b = _aggregate_period(df_main, awareness_level, period_b_months)

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


def calc_awareness_funnel(
    df_main: pd.DataFrame,
    brands: list[str],
    product: str = "Motor",
) -> pd.DataFrame:
    """
    Awareness funnel rates per brand across three stages.

    Aggregates data across all months in df_main (no per-month split).

    Parameters
    ----------
    df_main : pd.DataFrame
        Wide-format respondent data with Q1_pos*, Q2_*, Q27_* columns.
    brands : list[str]
        Brand names to include in the funnel.
    product : str
        Product context: 'Motor', 'Home', or 'Pet'. Used to resolve Q-codes.

    Returns
    -------
    pd.DataFrame with columns:
        brand, unprompted, prompted, consideration
    All values are proportions (0–1). Missing data yields NaN for that stage.
    """
    if df_main is None or df_main.empty or not brands:
        return pd.DataFrame(columns=["brand", "unprompted", "prompted", "consideration"])

    levels = AWARENESS_LEVELS.get(product, _DEFAULT_LEVELS)
    prompted_q = levels.get("prompted")
    consideration_q = levels.get("consideration")

    # --- Unprompted: derive from Q1 position columns ---
    # Denominator: respondents with at least one non-null Q1 position
    pos_cols = [c for c in df_main.columns if c.startswith("Q1_pos")]
    unprompted_rates: dict[str, float | None] = {}

    if pos_cols:
        # Flag each respondent as having answered
        def _has_answer(row) -> bool:
            return any(
                pd.notna(v) and str(v).strip() not in ("", "nan", "None", "False")
                for v in row
            )
        answered_mask = df_main[pos_cols].apply(_has_answer, axis=1)
        n_total = int(answered_mask.sum())

        if n_total >= SYSTEM_FLOOR_N:
            # Collect all text mentions per respondent across all pos cols
            all_mentions = pd.concat(
                [df_main[c].astype(str).str.strip() for c in pos_cols],
                axis=1,
            )
            for brand in brands:
                n_mention = int((all_mentions == brand).any(axis=1).sum())
                # Return NaN if brand never appeared — cannot distinguish
                # "zero awareness" from "brand not in survey universe"
                unprompted_rates[brand] = (n_mention / n_total) if n_mention > 0 else None
        else:
            for brand in brands:
                unprompted_rates[brand] = None
    else:
        for brand in brands:
            unprompted_rates[brand] = None

    # --- Prompted: Q2_ boolean columns ---
    prompted_rates: dict[str, float | None] = {}
    if prompted_q:
        prompt_cols = _brand_cols_for_q(df_main, prompted_q)
        if prompt_cols:
            answered = df_main[prompt_cols].any(axis=1)
            n_total = int(answered.sum())
            prefix = f"{prompted_q}_"
            for brand in brands:
                col = f"{prefix}{brand}"
                if col in df_main.columns and n_total >= SYSTEM_FLOOR_N:
                    n_mention = int(df_main[col].sum())
                    prompted_rates[brand] = n_mention / n_total
                else:
                    prompted_rates[brand] = None
        else:
            for brand in brands:
                prompted_rates[brand] = None
    else:
        for brand in brands:
            prompted_rates[brand] = None

    # --- Consideration: Q27_ boolean columns ---
    consideration_rates: dict[str, float | None] = {}
    if consideration_q:
        consid_cols = _brand_cols_for_q(df_main, consideration_q)
        if consid_cols:
            answered = df_main[consid_cols].any(axis=1)
            n_total = int(answered.sum())
            prefix = f"{consideration_q}_"
            for brand in brands:
                col = f"{prefix}{brand}"
                if col in df_main.columns and n_total >= SYSTEM_FLOOR_N:
                    n_mention = int(df_main[col].sum())
                    consideration_rates[brand] = n_mention / n_total
                else:
                    consideration_rates[brand] = None
        else:
            for brand in brands:
                consideration_rates[brand] = None
    else:
        for brand in brands:
            consideration_rates[brand] = None

    rows = []
    for brand in brands:
        rows.append({
            "brand": brand,
            "unprompted": unprompted_rates.get(brand),
            "prompted": prompted_rates.get(brand),
            "consideration": consideration_rates.get(brand),
        })

    return pd.DataFrame(rows)


def _brand_cols_for_q(df: pd.DataFrame, q_code: str) -> list[str]:
    """Return boolean columns for a question code (without modifying global state)."""
    prefix = f"{q_code}_"
    return [
        c for c in df.columns
        if c.startswith(prefix)
        and not c.startswith(f"{q_code}_pos")
        and not c.startswith(f"{q_code}_{{")
        and c != f"{q_code}_Other"
        and c != f"{q_code}_None of these"
        and pd.api.types.is_bool_dtype(df[c])
    ]


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


# ---------------------------------------------------------------------------
# Bayesian awareness movers (statistically valid change detection)
# ---------------------------------------------------------------------------

def calc_awareness_movers(
    df_main: pd.DataFrame,
    awareness_level: str,
    period_a_months: list[int],
    period_b_months: list[int],
    min_evidence: str = "moderate",
    top_n_each: int = 10,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Identify brands with genuine awareness movement using Bayesian change
    detection. Monte Carlo samples from each period's Beta posterior are
    compared to produce P(gain), P(loss), and a credible interval.

    Small brands are naturally handled via shrinkage: uncertain estimates
    are pulled toward zero change, so they only appear when the signal is
    strong relative to the noise.

    Parameters
    ----------
    min_evidence : str
        Minimum evidence threshold: 'strong' (95%), 'moderate' (90%),
        'weak' (80%), or 'any'.
    top_n_each : int
        Maximum gainers and losers to return.

    Returns DataFrame with columns:
        brand, rate_a, rate_b, change_pp, posterior_change_pp,
        ci_lower_pp, ci_upper_pp, prob_gain, prob_loss,
        significant, evidence_strength, direction,
        n_mentions_a, n_mentions_b, n_total_a, n_total_b
    """
    q_code = _get_q_code(awareness_level)
    if q_code is None:
        return pd.DataFrame()

    cols = _brand_cols(df_main, q_code)
    if not cols:
        return pd.DataFrame()

    prefix = f"{q_code}_"

    # Compute raw counts per brand per period
    def _period_counts(months):
        period = df_main[df_main[time_col].isin(months)]
        answered = period[cols].any(axis=1)
        n_total = int(answered.sum())
        if n_total < SYSTEM_FLOOR_N:
            return None, 0
        counts = {}
        for col in cols:
            brand = col[len(prefix):]
            k = int(period[col].sum())
            if k > 0:
                counts[brand] = k
        return counts, n_total

    counts_a, n_a = _period_counts(period_a_months)
    counts_b, n_b = _period_counts(period_b_months)

    if counts_a is None or counts_b is None:
        return pd.DataFrame()

    # Market prior: average rate across all brands
    all_brands = set((counts_a or {}).keys()) | set((counts_b or {}).keys())
    total_mentions = sum(counts_a.get(b, 0) + counts_b.get(b, 0) for b in all_brands)
    total_trials = n_a + n_b
    market_rate = total_mentions / (total_trials * max(1, len(all_brands)))

    rows = []
    for brand in sorted(all_brands):
        k_a = counts_a.get(brand, 0)
        k_b = counts_b.get(brand, 0)

        test = bayesian_change_test(
            successes_a=k_a, trials_a=n_a,
            successes_b=k_b, trials_b=n_b,
            prior_mean=market_rate,
        )

        rate_a = k_a / n_a if n_a > 0 else 0
        rate_b = k_b / n_b if n_b > 0 else 0

        rows.append({
            "brand": brand,
            "rate_a": rate_a,
            "rate_b": rate_b,
            "change_pp": (rate_b - rate_a) * 100,
            "posterior_change_pp": test["posterior_mean_change"] * 100,
            "ci_lower_pp": test["ci_lower"] * 100,
            "ci_upper_pp": test["ci_upper"] * 100,
            "prob_gain": test["prob_gain"],
            "prob_loss": test["prob_loss"],
            "significant": test["significant"],
            "evidence_strength": test["evidence_strength"],
            "direction": test["direction"],
            "n_mentions_a": k_a,
            "n_mentions_b": k_b,
            "n_total_a": n_a,
            "n_total_b": n_b,
        })

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame(rows)

    # Filter by evidence threshold
    thresholds = {"strong": 0.95, "moderate": 0.90, "weak": 0.80, "any": 0.0}
    min_prob = thresholds.get(min_evidence, 0.90)
    df["max_prob"] = df[["prob_gain", "prob_loss"]].max(axis=1)
    eligible = df[df["max_prob"] >= min_prob].copy()

    if eligible.empty:
        return eligible

    # Top N gainers and losers
    gainers = (eligible[eligible["direction"] == "gain"]
               .sort_values("prob_gain", ascending=False)
               .head(top_n_each))
    losers = (eligible[eligible["direction"] == "loss"]
              .sort_values("prob_loss", ascending=False)
              .head(top_n_each))

    result = pd.concat([gainers, losers], ignore_index=True)
    # Sort: strongest evidence first
    result = result.sort_values("max_prob", ascending=False).reset_index(drop=True)
    return result
