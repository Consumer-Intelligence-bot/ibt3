"""
Page 5: Awareness — Market View (Spec Section 9).

Shows brand rank and awareness rate across the market over time.
Public-facing page — no individual insurer named.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_bump,
    calc_awareness_rates,
    calc_awareness_summary,
)
from analytics.demographics import apply_filters
from components.branded_chart import add_ci_whiskers, create_branded_figure, create_bump_chart
from components.ci_card import ci_stat_card
from config import BUMP_COLOURS, CI_GREY
from shared import DF_MOTOR, DF_QUESTIONS, format_year_month

dash.register_page(__name__, path="/awareness-market", name="Awareness: Market")


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[
            html.H1("Brand Awareness — Market View"),
        ]),

        # Awareness level toggle
        dbc.Row([
            dbc.Col([
                dbc.RadioItems(
                    id="awareness-level-toggle",
                    options=[
                        {"label": "Prompted (Q2)", "value": "prompted"},
                        {"label": "Consideration (Q27)", "value": "consideration"},
                        {"label": "Spontaneous (Q1)", "value": "spontaneous", "disabled": True},
                    ],
                    value="prompted",
                    inline=True,
                    className="mb-3",
                ),
                html.Small(
                    Q1_GATING_MESSAGE,
                    id="q1-gating-msg",
                    className="text-muted",
                    style={"display": "none"},
                ),
            ], md=12),
        ], className="ci-filter-bar mb-3"),

        # KPI summary strip
        dbc.Row(id="awareness-kpi-row", className="mb-4"),

        # Bump chart
        dbc.Row([
            dbc.Col([
                html.H2("Brand Rank Over Time"),
                html.Div(id="awareness-bump-chart", className="bump-chart-container"),
            ], md=12),
        ], className="mb-4"),

        # Ranked bar chart
        dbc.Row([
            dbc.Col([
                html.H2("Awareness Rate — Latest Month"),
                html.Div(id="awareness-bar-chart"),
            ], md=12),
        ]),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


@callback(
    [
        Output("awareness-kpi-row", "children"),
        Output("awareness-bump-chart", "children"),
        Output("awareness-bar-chart", "children"),
        Output("q1-gating-msg", "style"),
    ],
    [
        Input("awareness-level-toggle", "value"),
        Input("global-product", "value"),
        Input("global-time-window", "value"),
    ],
)
def update_awareness_market(level, product, time_window):
    product = product or "Motor"
    tw = int(time_window or 24)

    # Show gating message for spontaneous
    gating_style = {"display": "block"} if level == "spontaneous" else {"display": "none"}
    if level == "spontaneous":
        empty_msg = html.Div(Q1_GATING_MESSAGE, className="ci-suppression p-4")
        return [], empty_msg, empty_msg, gating_style

    df_main = apply_filters(DF_MOTOR, product=product, time_window_months=tw)

    # KPI summary
    summary = calc_awareness_summary(df_main, DF_QUESTIONS, level)
    if summary is None:
        no_data = html.Div("No awareness data available for this selection.", className="ci-suppression p-4")
        return [], no_data, no_data, gating_style

    kpi_cards = dbc.Row([
        dbc.Col(ci_stat_card("Brands Tracked", summary["n_brands"], fmt="{:,}"), md=3),
        dbc.Col(ci_stat_card(
            "Top Brand Rate",
            summary["top_brand_rate"],
            fmt="{:.1%}",
            subtitle=summary["top_brand_name"],
        ), md=3),
        dbc.Col(ci_stat_card("Market Median", summary["median_rate"], fmt="{:.1%}"), md=3),
        dbc.Col(ci_stat_card(
            "Period",
            f"{format_year_month(summary['period_start'])} – {format_year_month(summary['period_end'])}",
        ), md=3),
    ])

    # Bump chart
    bump_data = calc_awareness_bump(df_main, DF_QUESTIONS, level)
    if bump_data.empty:
        bump_content = html.Div("Insufficient data for bump chart.", className="ci-suppression p-4")
    else:
        bump_data["month_label"] = bump_data["month"].apply(format_year_month)
        fig = create_bump_chart(
            bump_data,
            x_col="month_label",
            y_col="rank",
            brand_col="brand",
            title="",
        )
        bump_content = dcc.Graph(figure=fig, config={"displayModeBar": False})

    # Ranked bar chart (latest month)
    rates = calc_awareness_rates(df_main, DF_QUESTIONS, level)
    if rates.empty:
        bar_content = html.Div("Insufficient data for bar chart.", className="ci-suppression p-4")
    else:
        latest = rates[rates["month"] == rates["month"].max()].sort_values("rate", ascending=True)
        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=latest["brand"],
            x=latest["rate"],
            orientation="h",
            marker_color=[BUMP_COLOURS[i % len(BUMP_COLOURS)] for i in range(len(latest))],
            text=[f"{r:.1%}" for r in latest["rate"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Rate: %{x:.1%}<extra></extra>",
        ))
        fig_bar = add_ci_whiskers(
            fig_bar,
            x_values=latest["rate"].tolist(),
            y_values=latest["brand"].tolist(),
            ci_lower=latest["ci_lower"].tolist(),
            ci_upper=latest["ci_upper"].tolist(),
            colour=CI_GREY,
            horizontal=True,
        )
        fig_bar = create_branded_figure(fig_bar, title="")
        fig_bar.update_layout(
            xaxis_tickformat=".0%",
            yaxis_title="",
            height=max(400, len(latest) * 30),
            margin=dict(l=150),
        )
        bar_content = dcc.Graph(figure=fig_bar, config={"displayModeBar": False})

    return kpi_cards, bump_content, bar_content, gating_style
