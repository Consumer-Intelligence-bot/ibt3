"""
Anomaly detection engine (Spec Section 12.2).

Scans all eligible insurers each month and surfaces top movements.
Used by the 'What Changed This Month' page (Page 8).
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import calc_ci_width
from lib.analytics.flows import calc_net_flow, calc_top_sources, calc_top_destinations
from lib.analytics.rates import calc_retention_rate, calc_shopping_rate
from lib.config import MIN_BASE_PUBLISHABLE


def scan_anomalies(
    df_current: pd.DataFrame,
    df_previous: pd.DataFrame,
) -> list[dict]:
    """
    Run anomaly scan rules across all eligible insurers.

    Compares current period vs previous period. Returns list of anomaly dicts
    sorted by absolute magnitude, each with:
        insurer, metric, current_value, previous_value, change, severity, module, description
    """
    anomalies = []

    # Get eligible insurers (n >= 50 in current period)
    if df_current.empty or "CurrentCompany" not in df_current.columns:
        return []

    insurer_counts = df_current["CurrentCompany"].value_counts()
    eligible = insurer_counts[insurer_counts >= MIN_BASE_PUBLISHABLE].index.tolist()

    market_ret_current = calc_retention_rate(df_current)
    market_ret_prev = calc_retention_rate(df_previous) if not df_previous.empty else None
    market_shop_current = calc_shopping_rate(df_current)
    prior_mean = market_ret_current if market_ret_current else 0.5

    for insurer in eligible:
        ins_current = df_current[df_current["CurrentCompany"] == insurer]
        ins_previous = df_previous[df_previous["CurrentCompany"] == insurer] if not df_previous.empty else pd.DataFrame()

        n_current = len(ins_current)
        n_previous = len(ins_previous)

        # 1. Retention moved by more than CI-width noise threshold
        ret_current = calc_retention_rate(ins_current)
        ret_previous = calc_retention_rate(ins_previous) if n_previous >= MIN_BASE_PUBLISHABLE else None

        if ret_current is not None and ret_previous is not None:
            ci_width = calc_ci_width(n_current, ret_current)
            change_pp = (ret_current - ret_previous) * 100
            if ci_width and abs(change_pp) > ci_width:
                anomalies.append({
                    "insurer": insurer,
                    "metric": "Retention Rate",
                    "current_value": ret_current,
                    "previous_value": ret_previous,
                    "change": change_pp,
                    "abs_change": abs(change_pp),
                    "severity": "high" if abs(change_pp) > ci_width * 2 else "medium",
                    "module": "Shopping & Switching",
                    "description": (
                        f"{insurer}'s retention rate moved {change_pp:+.1f}pp "
                        f"({ret_previous:.0%} to {ret_current:.0%}), "
                        f"exceeding the noise threshold of {ci_width:.1f}pp."
                    ),
                })

        # 2. Shopping rate moved by more than 5pp
        shop_current = calc_shopping_rate(ins_current)
        shop_previous = calc_shopping_rate(ins_previous) if n_previous >= MIN_BASE_PUBLISHABLE else None

        if shop_current is not None and shop_previous is not None:
            shop_change = (shop_current - shop_previous) * 100
            if abs(shop_change) > 5.0:
                anomalies.append({
                    "insurer": insurer,
                    "metric": "Shopping Rate",
                    "current_value": shop_current,
                    "previous_value": shop_previous,
                    "change": shop_change,
                    "abs_change": abs(shop_change),
                    "severity": "high" if abs(shop_change) > 10 else "medium",
                    "module": "Shopping & Switching",
                    "description": (
                        f"{insurer}'s shopping rate changed by {shop_change:+.1f}pp "
                        f"({shop_previous:.0%} to {shop_current:.0%})."
                    ),
                })

        # 3. Net flow direction reversed
        nf_current = calc_net_flow(df_current, insurer)
        nf_previous = calc_net_flow(df_previous, insurer) if not df_previous.empty else None

        if nf_previous and nf_current:
            prev_dir = "winner" if nf_previous["net"] > 0 else ("loser" if nf_previous["net"] < 0 else "neutral")
            curr_dir = "winner" if nf_current["net"] > 0 else ("loser" if nf_current["net"] < 0 else "neutral")
            if prev_dir != curr_dir and prev_dir != "neutral" and curr_dir != "neutral":
                anomalies.append({
                    "insurer": insurer,
                    "metric": "Net Flow Direction",
                    "current_value": nf_current["net"],
                    "previous_value": nf_previous["net"],
                    "change": nf_current["net"] - nf_previous["net"],
                    "abs_change": abs(nf_current["net"] - nf_previous["net"]),
                    "severity": "high",
                    "module": "Shopping & Switching",
                    "description": (
                        f"{insurer} reversed from net {prev_dir} ({nf_previous['net']:+d}) "
                        f"to net {curr_dir} ({nf_current['net']:+d})."
                    ),
                })

        # 4. New insurer in top 5 sources or destinations
        if not df_previous.empty:
            src_current = set(calc_top_sources(df_current, insurer, 5).index)
            src_previous = set(calc_top_sources(df_previous, insurer, 5).index)
            new_sources = src_current - src_previous
            for src in new_sources:
                anomalies.append({
                    "insurer": insurer,
                    "metric": "New Source",
                    "current_value": src,
                    "previous_value": None,
                    "change": 0,
                    "abs_change": 0,
                    "severity": "low",
                    "module": "Shopping & Switching",
                    "description": (
                        f"{src} is a new top-5 source of customers for {insurer}."
                    ),
                })

            dst_current = set(calc_top_destinations(df_current, insurer, 5).index)
            dst_previous = set(calc_top_destinations(df_previous, insurer, 5).index)
            new_dests = dst_current - dst_previous
            for dst in new_dests:
                anomalies.append({
                    "insurer": insurer,
                    "metric": "New Destination",
                    "current_value": dst,
                    "previous_value": None,
                    "change": 0,
                    "abs_change": 0,
                    "severity": "low",
                    "module": "Shopping & Switching",
                    "description": (
                        f"{dst} is a new top-5 destination for customers leaving {insurer}."
                    ),
                })

    # Sort by absolute change magnitude (highest first)
    anomalies.sort(key=lambda x: x.get("abs_change", 0), reverse=True)
    return anomalies
