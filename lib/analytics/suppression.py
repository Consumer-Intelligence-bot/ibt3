"""
Suppression and confidence gating.

Wraps analytics.confidence to provide page-level suppression decisions.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from lib.analytics.confidence import (
    ConfidenceLabel,
    ConfidenceResult,
    MetricType,
    assess_confidence,
)
from lib.config import MIN_ELIGIBLE_INSURERS_WARNING, SYSTEM_FLOOR_N


@dataclass
class SuppressionResult:
    can_show_insurer: bool
    can_show_market: bool
    insurer_n: int
    market_n: int
    confidence: ConfidenceResult | None
    message: str | None
    warning: str | None


def check_suppression(
    df_insurer: pd.DataFrame | None,
    df_market: pd.DataFrame | None,
    metric_type: MetricType | str = MetricType.RATE,
    rate: float | None = None,
    posterior_ci_width: float | None = None,
    active_filters: dict | None = None,
    thresholds: dict[str, tuple[float, float]] | None = None,
) -> SuppressionResult:
    """
    Check if insurer and market data meet confidence thresholds.

    Uses the CI-width confidence framework from assess_confidence().
    Falls back to n-based floor checks when rate information is unavailable.
    """
    if active_filters is None:
        active_filters = {}
    insurer_n = len(df_insurer) if df_insurer is not None else 0
    market_n = len(df_market) if df_market is not None else 0

    can_show_market = market_n >= SYSTEM_FLOOR_N

    # Assess insurer confidence
    conf = assess_confidence(
        n=insurer_n,
        rate=rate,
        metric_type=metric_type,
        posterior_ci_width=posterior_ci_width,
        thresholds=thresholds,
    )

    message = conf.message
    if not conf.can_show and message is None:
        filter_str = ", ".join(f"{k}: {v}" for k, v in active_filters.items())
        message = (
            f"Insufficient data: {insurer_n} respondents. "
            + (f"Active filters: {filter_str}. Try broadening your selection." if filter_str else "Try broadening your selection.")
        )

    warning = None
    if len(active_filters) >= 2:
        warning = f"Multiple filters active — fewer than {MIN_ELIGIBLE_INSURERS_WARNING} insurers may meet threshold."

    return SuppressionResult(
        can_show_insurer=conf.can_show,
        can_show_market=can_show_market,
        insurer_n=insurer_n,
        market_n=market_n,
        confidence=conf,
        message=message,
        warning=warning,
    )


def get_confidence_level(
    n: int,
    rate: float | None = None,
    metric_type: MetricType | str = MetricType.RATE,
    posterior_ci_width: float | None = None,
) -> ConfidenceLabel:
    """Convenience: returns just the label for a given n/rate/metric combination."""
    result = assess_confidence(
        n=n,
        rate=rate,
        metric_type=metric_type,
        posterior_ci_width=posterior_ci_width,
    )
    return result.label
