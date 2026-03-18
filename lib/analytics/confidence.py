"""
Confidence-first assessment (Spec Section 12.1).

Three-layer framework:
  Layer 1 — System floor (n < SYSTEM_FLOOR_N → always suppress)
  Layer 2 — CI-width threshold per metric type (publishable / indicative)
  Layer 3 — User preference (stub → admin default until auth is built)
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from lib.config import (
    CI_WIDTH_INDICATIVE_AWARENESS,
    CI_WIDTH_INDICATIVE_RATE,
    CI_WIDTH_INDICATIVE_REASON,
    CI_WIDTH_PUBLISHABLE_AWARENESS,
    CI_WIDTH_PUBLISHABLE_RATE,
    CI_WIDTH_PUBLISHABLE_REASON,
    NPS_MIN_N,
    SYSTEM_FLOOR_N,
)


class MetricType(str, Enum):
    RATE = "rate"              # retention, shopping, switching
    REASON = "reason"          # Q8, Q18, Q19, Q31, Q33
    AWARENESS = "awareness"    # Q2, Q27
    NPS = "nps"                # Q40b — uses n floor, not CI width


class ConfidenceLabel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INSUFFICIENT = "INSUFFICIENT"


@dataclass(frozen=True)
class ConfidenceResult:
    label: ConfidenceLabel
    ci_width: float | None
    n: int
    can_show: bool
    message: str | None


# Threshold pairs keyed by MetricType
_DEFAULT_THRESHOLDS: dict[MetricType, tuple[float, float]] = {
    MetricType.RATE: (CI_WIDTH_PUBLISHABLE_RATE, CI_WIDTH_INDICATIVE_RATE),
    MetricType.REASON: (CI_WIDTH_PUBLISHABLE_REASON, CI_WIDTH_INDICATIVE_REASON),
    MetricType.AWARENESS: (CI_WIDTH_PUBLISHABLE_AWARENESS, CI_WIDTH_INDICATIVE_AWARENESS),
}


def get_thresholds(
    metric_type: MetricType | str,
    overrides: dict[str, tuple[float, float]] | None = None,
) -> tuple[float, float]:
    """Return (publishable, indicative) CI-width thresholds for a metric type."""
    mt = MetricType(metric_type) if isinstance(metric_type, str) else metric_type
    if overrides and mt.value in overrides:
        return overrides[mt.value]
    return _DEFAULT_THRESHOLDS.get(mt, (CI_WIDTH_PUBLISHABLE_RATE, CI_WIDTH_INDICATIVE_RATE))


def calc_ci_width(n: int, rate: float) -> float:
    """Raw CI width = 2 × 1.96 × √(p(1−p)/n).  Spec Section 12.1."""
    if n <= 0 or rate is None:
        return float("inf")
    p = max(0.0, min(1.0, rate))
    return 2 * 1.96 * math.sqrt(p * (1 - p) / n) * 100  # in percentage points


def assess_confidence(
    n: int,
    rate: float | None,
    metric_type: MetricType | str,
    *,
    posterior_ci_width: float | None = None,
    thresholds: dict[str, tuple[float, float]] | None = None,
) -> ConfidenceResult:
    """
    Three-layer confidence assessment.

    If *posterior_ci_width* is provided (from Bayesian smoothing), it is used
    instead of the raw formula.  Units: percentage points.
    """
    mt = MetricType(metric_type) if isinstance(metric_type, str) else metric_type

    # Layer 1: System floor
    if n < SYSTEM_FLOOR_N:
        return ConfidenceResult(
            label=ConfidenceLabel.INSUFFICIENT,
            ci_width=None,
            n=n,
            can_show=False,
            message=f"Insufficient data: {n} respondents (minimum {SYSTEM_FLOOR_N} required).",
        )

    # NPS uses n floor only, not CI width
    if mt == MetricType.NPS:
        if n >= NPS_MIN_N:
            return ConfidenceResult(ConfidenceLabel.HIGH, None, n, True, None)
        return ConfidenceResult(
            ConfidenceLabel.INSUFFICIENT, None, n, False,
            f"Insufficient data for NPS: {n} respondents (minimum {NPS_MIN_N} required).",
        )

    # Layer 2: CI-width threshold
    publishable, indicative = get_thresholds(mt, thresholds)

    ci_w = posterior_ci_width if posterior_ci_width is not None else calc_ci_width(n, rate or 0.5)

    if ci_w <= publishable:
        label = ConfidenceLabel.HIGH
    elif ci_w <= publishable + 2.0:
        label = ConfidenceLabel.MEDIUM
    elif ci_w <= indicative:
        label = ConfidenceLabel.LOW
    else:
        return ConfidenceResult(
            label=ConfidenceLabel.INSUFFICIENT,
            ci_width=ci_w,
            n=n,
            can_show=False,
            message=(
                f"Confidence interval width {ci_w:.0f}pp exceeds indicative threshold ({indicative:.0f}pp). "
                f"Extend the time window or wait for more data."
            ),
        )

    return ConfidenceResult(label=label, ci_width=ci_w, n=n, can_show=True, message=None)
