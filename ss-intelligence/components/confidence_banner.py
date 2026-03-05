"""
Confidence banner showing CI-width confidence level, n, filters, time window.

Uses the new confidence-first framework (Spec Section 12.1).
"""
from __future__ import annotations

from dash import html
import dash_bootstrap_components as dbc

from analytics.confidence import ConfidenceLabel, ConfidenceResult, MetricType, assess_confidence
from analytics.demographics import get_active_filters


_BANNER_CLASSES = {
    ConfidenceLabel.HIGH: "ci-banner ci-banner--high",
    ConfidenceLabel.MEDIUM: "ci-banner ci-banner--medium",
    ConfidenceLabel.LOW: "ci-banner ci-banner--low",
    ConfidenceLabel.INSUFFICIENT: "ci-banner ci-banner--insuff",
}

_ICONS = {
    ConfidenceLabel.HIGH: "✓",
    ConfidenceLabel.MEDIUM: "✓",
    ConfidenceLabel.LOW: "⚠",
    ConfidenceLabel.INSUFFICIENT: "✕",
}


def confidence_banner(
    n: int,
    time_window: str,
    rate: float | None = None,
    posterior_ci_width: float | None = None,
    metric_type: MetricType | str = MetricType.RATE,
    age_band: str | None = None,
    region: str | None = None,
    payment_type: str | None = None,
    suppression_message: str | None = None,
    id_prefix: str = "",
) -> html.Div:
    """Render confidence banner with CI-width assessment."""
    conf = assess_confidence(
        n=n,
        rate=rate,
        metric_type=metric_type,
        posterior_ci_width=posterior_ci_width,
    )

    a = None if age_band in (None, "ALL", "") else age_band
    r = None if region in (None, "ALL", "") else region
    p = None if payment_type in (None, "ALL", "") else payment_type
    active = get_active_filters(a, r, p)
    filter_str = " | ".join(f"{k}: {v}" for k, v in active.items()) if active else "All respondents"

    if conf.label == ConfidenceLabel.INSUFFICIENT:
        msg = suppression_message or conf.message or "Insufficient data to display results."
        return html.Div(
            [
                html.Span(f"{_ICONS[conf.label]} ", style={"fontSize": "16px"}),
                html.Span(msg),
                html.Span(f" | {n:,} renewals | {time_window}", className="ms-2", style={"opacity": 0.7}),
            ],
            className=_BANNER_CLASSES[conf.label],
        )

    ci_text = f" | CI width: {conf.ci_width:.1f}pp" if conf.ci_width is not None else ""

    return html.Div(
        [
            html.Span(
                f"{_ICONS[conf.label]} {conf.label.value}",
                className=f"badge-confidence badge-{conf.label.value}",
            ),
            html.Span(
                f"Based on {n:,} renewals | {filter_str} | {time_window}{ci_text}",
                className="ms-2",
            ),
        ],
        className=_BANNER_CLASSES[conf.label],
    )
