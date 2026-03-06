"""
Pre-compute Bayesian-smoothed retention rates at refresh time.
Stores results in data/processed/bayesian_cache.parquet for fast callback lookup.
"""
from pathlib import Path

import pandas as pd

from analytics.rates import calc_retention_rate
from analytics.bayesian import bayesian_smooth_rate
from analytics.demographics import apply_filters

# Path to cache file
_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "processed" / "bayesian_cache.parquet"


def precompute_retention_rates(df: pd.DataFrame, product: str, time_window_months: int = 24) -> pd.DataFrame:
    """
    Pre-compute Bayesian-smoothed retention for each insurer × product.
    Returns DataFrame with columns: insurer, product, n, raw_rate, posterior_mean, ci_lower, ci_upper, market_rate.
    """
    df_market = apply_filters(df, product=product, time_window_months=time_window_months)
    market_rate = calc_retention_rate(df_market)
    if market_rate is None:
        return pd.DataFrame()

    insurers = df_market["CurrentCompany"].dropna().astype(str).str.strip().unique()
    insurers = [i for i in insurers if i and i.lower() != "nan"]

    rows = []
    for insurer in insurers:
        df_ins = apply_filters(df, insurer=insurer, product=product, time_window_months=time_window_months)
        df_ins = df_ins[~df_ins.get("IsNewToMarket", False)]
        n = len(df_ins)
        if n == 0:
            continue
        retained = int(df_ins["IsRetained"].sum())
        total = n
        result = bayesian_smooth_rate(retained, total, market_rate)
        rows.append({
            "insurer": insurer,
            "product": product,
            "time_window_months": time_window_months,
            "n": n,
            "raw_rate": result["raw_rate"],
            "posterior_mean": result["posterior_mean"],
            "ci_lower": result["ci_lower"],
            "ci_upper": result["ci_upper"],
            "market_rate": market_rate,
        })

    return pd.DataFrame(rows)


def run_precompute(df_motor: pd.DataFrame, df_home: pd.DataFrame | None = None) -> Path | None:
    """
    Pre-compute Bayesian cache for Motor (and Home if available).
    Saves to bayesian_cache.parquet. Returns path or None if failed.
    """
    all_rows = []
    for product, df in [("Motor", df_motor), ("Home", df_home)]:
        if df is None or len(df) == 0:
            continue
        for tw in (6, 12, 24):
            rows = precompute_retention_rates(df, product, tw)
            if len(rows) > 0:
                all_rows.append(rows)

    if not all_rows:
        return None

    cache_df = pd.concat(all_rows, ignore_index=True)
    _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        cache_df.to_parquet(_CACHE_PATH, index=False)
        return _CACHE_PATH
    except ImportError:
        return None


def precompute_all(product: str = "Motor") -> Path | None:
    """
    Pre-compute Bayesian cache for Motor and Home (if available).
    Loads data from loader and calls run_precompute.
    The product argument is for API compatibility; both products are precomputed when available.
    """
    from data.loader import load_main
    df_motor, _ = load_main("Motor")
    df_home = None
    try:
        df_home, _ = load_main("Home")
    except FileNotFoundError:
        pass
    return run_precompute(df_motor, df_home)


def get_cached_rate(insurer: str, product: str, time_window_months: int) -> dict | None:
    """
    Look up pre-computed Bayesian result. Returns None if not in cache.
    """
    if not _CACHE_PATH.exists():
        return None
    try:
        cache = pd.read_parquet(_CACHE_PATH)
    except Exception:
        return None
    match = cache[
        (cache["insurer"] == insurer)
        & (cache["product"] == product)
        & (cache["time_window_months"] == time_window_months)
    ]
    if len(match) == 0:
        return None
    row = match.iloc[0]
    return {
        "posterior_mean": row["posterior_mean"],
        "ci_lower": row["ci_lower"],
        "ci_upper": row["ci_upper"],
        "raw_rate": row["raw_rate"],
        "n": int(row["n"]),
    }
