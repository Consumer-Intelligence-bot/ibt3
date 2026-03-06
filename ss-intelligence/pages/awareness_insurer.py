"""
Page 6: Awareness — Insurer View (Spec Section 10).

Funnel analysis for a single insurer: prompted and consideration rates
with slopegraph panels and trend lines with market percentile band.

Line colours per spec:
  Spontaneous = CI Magenta (gated)
  Prompted    = CI Blue
  Consideration = CI Green
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
from config import CI_BLUE, CI_GREEN, CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_RED, DEFAULT_TIME_WINDOW_INSURER
from shared import DF_MOTOR, DF_HOME, DF_QUESTIONS, DF_QUESTIONS_HOME, DIMENSIONS, format_year_month

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
    """Render a single slopegraph panel with market average below the metric."""
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
    arrows = {"up": "\u2191", "down": "\u2193", "flat": "\u2192"}
    delta_sign = "+" if data["change"] > 0 else ""

    # Market averages for context (Spec 10.3)
    start_mkt = data.get("start_market_rate")
    end_mkt = data.get("end_market_rate")
    mkt_start_str = f"Market: {start_mkt:.1%}" if start_mkt is not None else ""
    mkt_end_str = f"Market: {end_mkt:.1%}" if end_mkt is not None else ""

    content = html.Div([
        html.Div(title, className="kpi-title mb-2"),
        html.Div(f"{data['start_rate']:.1%}", className="slopegraph-value text-ci-magenta"),
        html.Div(format_year_month(data["start_month"]), className="kpi-subtitle"),
        html.Div(mkt_start_str, className="kpi-subtitle", style={"color": CI_GREY}),
        html.Div(arrows.get(direction, "\u2192"), className=arrow_cls),
        html.Div(f"{data['end_rate']:.1%}", className="slopegraph-value text-ci-magenta"),
        html.Div(format_year_month(data["end_month"]), className="kpi-subtitle"),
        html.Div(mkt_end_str, className="kpi-subtitle", style={"color": CI_GREY}),
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
    tw = int(time_window or DEFAULT_TIME_WINDOW_INSURER)

    if not insurer:
        msg = html.Div("Select an insurer to view awareness data.", className="ci-suppression p-4")
        return msg, [], msg

    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_questions = DF_QUESTIONS if product == "Motor" else (DF_QUESTIONS_HOME if DF_QUESTIONS_HOME is not None and len(DF_QUESTIONS_HOME) > 0 else DF_QUESTIONS)
    df_main = apply_filters(df_main, product=product, time_window_months=tw)
    n_insurer = len(df_main[df_main["CurrentCompany"] == insurer])

    banner = confidence_banner(
        n=n_insurer,
        time_window=f"Last {tw} months",
        metric_type=MetricType.AWARENESS,
    )

    # Slopegraph panels (Spec 10.3)
    prompted_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "prompted")
    consideration_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "consideration")

    slopegraph = [
        _slopegraph_panel("Spontaneous (Q1)", None, gated=True),
        _slopegraph_panel("Prompted (Q2)", prompted_slope),
        _slopegraph_panel("Consideration (Q27)", consideration_slope),
    ]

    # Trend chart with market percentile bands (Spec 10.4)
    prompted_rates = calc_awareness_rates(df_main, df_questions, "prompted")
    consideration_rates = calc_awareness_rates(df_main, df_questions, "consideration")
    prompted_bands = calc_awareness_market_bands(df_main, df_questions, "prompted")
    consideration_bands = calc_awareness_market_bands(df_main, df_questions, "consideration")

    fig = go.Figure()

    # Market percentile bands — one per metric (Spec 10.4)
    for bands_df, band_colour, band_label in [
        (prompted_bands, "rgba(91, 194, 231, 0.15)", "Market 25th\u201375th (Prompted)"),
        (consideration_bands, "rgba(72, 162, 63, 0.15)", "Market 25th\u201375th (Consideration)"),
    ]:
        if not bands_df.empty:
            months_label = [format_year_month(m) for m in bands_df["month"]]
            fig.add_trace(go.Scatter(
                x=months_label, y=bands_df["p75"],
                mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
            ))
            fig.add_trace(go.Scatter(
                x=months_label, y=bands_df["p25"],
                mode="lines", line=dict(width=0), fill="tonexty",
                fillcolor=band_colour,
                name=band_label,
                hoverinfo="skip",
                showlegend=False,
            ))

    # Insurer lines — correct colours per spec 10.4:
    # Spontaneous = CI Magenta (gated), Prompted = CI Blue, Consideration = CI Green
    for level, rates_df, colour, label in [
        ("prompted", prompted_rates, CI_BLUE, "Prompted"),
        ("consideration", consideration_rates, CI_GREEN, "Consideration"),
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
        yaxis_range=[0, 1],
        legend=dict(orientation="h", yanchor="top", y=-0.12),
        height=400,
    )
    trend_content = dcc.Graph(figure=fig, config={"displayModeBar": False})

    return banner, slopegraph, trend_content
