"""
Consumer Intelligence branded KPI card.

Uses CSS classes from custom.css instead of inline styles.
Supports: insurer vs market values, gap badges, trend arrows, confidence icons.
"""
from __future__ import annotations

import dash_bootstrap_components as dbc
from dash import html

from config import NEUTRAL_GAP_THRESHOLD


def _format_value(value, fmt: str = "{:.1%}") -> str:
    if value is None:
        return "-"
    return fmt.format(value)


def _gap_badge(gap: float | None, invert: bool = False) -> html.Span | None:
    if gap is None:
        return None
    if abs(gap) <= NEUTRAL_GAP_THRESHOLD / 100:
        cls = "gap-badge gap-badge--neutral"
    elif (gap > 0) != invert:
        cls = "gap-badge gap-badge--positive"
    else:
        cls = "gap-badge gap-badge--negative"
    sign = "+" if gap > 0 else ""
    return html.Span(f"{sign}{gap:.1%}", className=cls)


def _trend_arrow(direction: str | None) -> html.Span | None:
    if direction is None:
        return None
    arrows = {"up": "▲", "down": "▼", "flat": "●"}
    colors = {"up": "text-ci-green", "down": "text-ci-red", "flat": ""}
    return html.Span(
        arrows.get(direction, ""),
        className=colors.get(direction, ""),
        style={"fontSize": "14px", "marginLeft": "6px"},
    )


def _confidence_icon(label: str | None) -> html.Span | None:
    if label is None:
        return None
    return html.Span(label, className=f"badge-confidence badge-{label}")


def ci_kpi_card(
    title: str,
    insurer_value: float | None = None,
    market_value: float | None = None,
    fmt: str = "{:.1%}",
    ci_lower: float | None = None,
    ci_upper: float | None = None,
    trend_direction: str | None = None,
    confidence_label: str | None = None,
    invert_colour: bool = False,
    suppression_message: str | None = None,
) -> dbc.Card:
    """
    Branded KPI card with CI design system classes.

    For insurer pages: pass both insurer_value and market_value.
    For market pages: pass insurer_value only (displayed as primary value).
    """
    header_children = [html.Span(title)]
    if confidence_label:
        header_children.append(_confidence_icon(confidence_label))

    header = html.Div(
        header_children,
        className="d-flex justify-content-between align-items-center",
    )

    if suppression_message and insurer_value is None:
        body = html.P(suppression_message, className="text-muted small mb-0")
    else:
        gap = None
        if insurer_value is not None and market_value is not None:
            gap = insurer_value - market_value

        value_children = [
            html.Span(_format_value(insurer_value, fmt), className="kpi-value kpi-value--insurer"),
        ]
        if trend_direction:
            value_children.append(_trend_arrow(trend_direction))

        body_children = [html.Div(value_children)]

        if market_value is not None:
            body_children.append(
                html.Div(
                    [
                        html.Span("Market ", className="kpi-subtitle"),
                        html.Span(_format_value(market_value, fmt), style={"fontWeight": 600}),
                    ],
                    className="mt-1",
                )
            )

        if gap is not None:
            badge = _gap_badge(gap, invert_colour)
            if badge:
                body_children.append(html.Div(badge, className="mt-1"))

        if ci_lower is not None and ci_upper is not None:
            body_children.append(
                html.Div(
                    f"95% CI: {_format_value(ci_lower, fmt)} – {_format_value(ci_upper, fmt)}",
                    className="kpi-subtitle mt-1",
                )
            )

        body = html.Div(body_children)

    return dbc.Card(
        [
            dbc.CardHeader(header),
            dbc.CardBody(body),
        ],
        className="ci-card h-100",
    )


def ci_stat_card(
    title: str,
    value: str | int | float,
    fmt: str | None = None,
    subtitle: str | None = None,
    alert: bool = False,
) -> dbc.Card:
    """Simple stat card for Admin/summary pages. No insurer/market comparison."""
    if fmt and isinstance(value, (int, float)):
        display = fmt.format(value)
    else:
        display = str(value)

    value_cls = "kpi-value kpi-value--insurer" if not alert else "kpi-value text-ci-red"

    body_children = [html.Div(display, className=value_cls)]
    if subtitle:
        body_children.append(html.Div(subtitle, className="kpi-subtitle"))

    return dbc.Card(
        [
            dbc.CardHeader(title),
            dbc.CardBody(body_children),
        ],
        className="ci-card h-100",
    )
