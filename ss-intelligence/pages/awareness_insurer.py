"""
Page 6: Awareness — Insurer View (Spec Section 10).

Funnel analysis for a single insurer: prompted and consideration rates
with slopegraph panels and trend lines with market percentile band.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
import numpy as np
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_market_bands,
    calc_awareness_rates,
    calc_awareness_slopegraph,
)
from analytics.confidence import MetricType
from analytics.demographics import apply_filters
from components.branded_chart import create_branded_figure
from components.confidence_banner import confidence_banner
from config import CI_BLUE, CI_GREEN, CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_RED
from shared import DF_MOTOR, DF_QUESTIONS, DIMENSIONS, format_year_month

dash.register_page(__name__, path="/awareness-insurer", name="Awareness: Insurer")


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[
            html.H1("Brand Awareness — Insurer View"),
        ]),

        html.Div(id="awareness-insurer-banner"),

        # Slopegraph strip
        dbc.Row(id="awareness-slopegraph-row", className="mb-4"),

        # Trend chart with market band
        dbc.Row([
            dbc.Col([
                html.H2("Awareness Trend vs Market"),
                html.Div(id="awareness-trend-chart"),
            ], md=12),
        ]),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


def _slopegraph_panel(title: str, data: dict | None, gated: bool = False) -> dbc.Col:
    """Render a single slopegraph panel (start → end with arrow)."""
    if gated:
        content = html.Div([
            html.Div(title, className="kpi-title mb-2"),
            html.Div(Q1_GATING_MESSAGE, className="text-muted small", style={"fontStyle": "italic"}),
        ], className="slopegraph-panel")
        return dbc.Col(content, md=4)

    if data is None or not data.get("can_show", False):
        content = html.Div([
            html.Div(title, className="kpi-title mb-2"),
            html.Div("Insufficient data", className="text-muted"),
        ], className="slopegraph-panel")
        return dbc.Col(content, md=4)

    direction = data["direction"]
    arrow_cls = f"slopegraph-arrow slopegraph-arrow--{direction}"
    arrows = {"up": "↑", "down": "↓", "flat": "→"}
    delta_sign = "+" if data["change"] > 0 else ""

    content = html.Div([
        html.Div(title, className="kpi-title mb-2"),
        html.Div(f"{data['start_rate']:.1%}", className="slopegraph-value text-ci-magenta"),
        html.Div(format_year_month(data["start_month"]), className="kpi-subtitle"),
        html.Div(arrows.get(direction, "→"), className=arrow_cls),
        html.Div(f"{data['end_rate']:.1%}", className="slopegraph-value text-ci-magenta"),
        html.Div(format_year_month(data["end_month"]), className="kpi-subtitle"),
        html.Div(
            f"{delta_sign}{data['change']:.1%}",
            className=f"slopegraph-delta mt-2 {'text-ci-green' if data['change'] > 0 else 'text-ci-red' if data['change'] < 0 else ''}",
        ),
    ], className="slopegraph-panel")
    return dbc.Col(content, md=4)


@callback(
    [
        Output("awareness-insurer-banner", "children"),
        Output("awareness-slopegraph-row", "children"),
        Output("awareness-trend-chart", "children"),
    ],
    [
        Input("global-insurer", "value"),
        Input("global-product", "value"),
        Input("global-time-window", "value"),
    ],
)
def update_awareness_insurer(insurer, product, time_window):
    product = product or "Motor"
    tw = int(time_window or 24)

    if not insurer:
        msg = html.Div("Select an insurer to view awareness data.", className="ci-suppression p-4")
        return msg, [], msg

    df_main = apply_filters(DF_MOTOR, product=product, time_window_months=tw)
    n_insurer = len(df_main[df_main["CurrentCompany"] == insurer])

    banner = confidence_banner(
        n=n_insurer,
        time_window=f"Last {tw} months",
        metric_type=MetricType.AWARENESS,
    )

    # Slopegraph panels
    prompted_slope = calc_awareness_slopegraph(df_main, DF_QUESTIONS, insurer, "prompted")
    consideration_slope = calc_awareness_slopegraph(df_main, DF_QUESTIONS, insurer, "consideration")

    slopegraph = [
        _slopegraph_panel("Spontaneous (Q1)", None, gated=True),
        _slopegraph_panel("Prompted (Q2)", prompted_slope),
        _slopegraph_panel("Consideration (Q27)", consideration_slope),
    ]

    # Trend chart with market percentile band
    prompted_rates = calc_awareness_rates(df_main, DF_QUESTIONS, "prompted")
    consideration_rates = calc_awareness_rates(df_main, DF_QUESTIONS, "consideration")
    prompted_bands = calc_awareness_market_bands(df_main, DF_QUESTIONS, "prompted")
    consideration_bands = calc_awareness_market_bands(df_main, DF_QUESTIONS, "consideration")

    fig = go.Figure()

    # Market percentile bands (prompted)
    if not prompted_bands.empty:
        months_label = [format_year_month(m) for m in prompted_bands["month"]]
        fig.add_trace(go.Scatter(
            x=months_label, y=prompted_bands["p75"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=months_label, y=prompted_bands["p25"],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor="rgba(91, 194, 231, 0.15)",
            name="Market 25th–75th (Prompted)",
            hoverinfo="skip",
        ))

    # Insurer lines
    for level, rates_df, colour, label in [
        ("prompted", prompted_rates, CI_MAGENTA, "Prompted"),
        ("consideration", consideration_rates, CI_BLUE, "Consideration"),
    ]:
        if rates_df.empty:
            continue
        brand_data = rates_df[rates_df["brand"] == insurer].sort_values("month")
        if brand_data.empty:
            continue
        x = [format_year_month(m) for m in brand_data["month"]]
        fig.add_trace(go.Scatter(
            x=x, y=brand_data["rate"],
            mode="lines+markers",
            name=label,
            line=dict(color=colour, width=2.5),
            marker=dict(size=6, color=colour),
            connectgaps=False,
            hovertemplate=f"<b>{label}</b><br>Rate: %{{y:.1%}}<br>%{{x}}<extra></extra>",
        ))

    fig = create_branded_figure(fig, title="")
    fig.update_layout(
        yaxis_tickformat=".0%",
        yaxis_title="Awareness Rate",
        legend=dict(orientation="h", yanchor="top", y=-0.12),
        height=400,
    )
    trend_content = dcc.Graph(figure=fig, config={"displayModeBar": False})

    return banner, slopegraph, trend_content
