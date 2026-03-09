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
from config import CI_GREEN, CI_GREY, CI_RED, DEFAULT_TIME_WINDOW_INSURER
from shared import DF_MOTOR, DF_HOME, DF_QUESTIONS, DF_QUESTIONS_HOME, format_year_month

dash.register_page(__name__, path="/awareness-market", name="Awareness: Market")


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[
            html.H1("Brand Awareness — Market View"),
        ]),

        # Awareness level toggle (Spec 9.2)
        dbc.Row([
            dbc.Col([
                dbc.RadioItems(
                    id="awareness-level-toggle",
                    options=[
                        {"label": "Spontaneous (Q1)", "value": "spontaneous", "disabled": True},
                        {"label": "Prompted (Q2)", "value": "prompted"},
                        {"label": "Consideration (Q27)", "value": "consideration"},
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
                html.H2(id="awareness-bar-title"),
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
        Output("awareness-bar-title", "children"),
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
    selected = [int(v) for v in time_window] if time_window else None

    # Show gating message for spontaneous
    gating_style = {"display": "block"} if level == "spontaneous" else {"display": "none"}
    if level == "spontaneous":
        empty_msg = html.Div(Q1_GATING_MESSAGE, className="ci-suppression p-4")
        return [], empty_msg, empty_msg, "Awareness Rate — Latest Month", gating_style

    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_questions = DF_QUESTIONS if product == "Motor" else (DF_QUESTIONS_HOME if DF_QUESTIONS_HOME is not None and len(DF_QUESTIONS_HOME) > 0 else DF_QUESTIONS)
    df_main = apply_filters(df_main, product=product, selected_months=selected)

    # KPI summary (Spec 9.3)
    summary = calc_awareness_summary(df_main, df_questions, level)
    if summary is None:
        no_data = html.Div("No awareness data available for this selection.", className="ci-suppression p-4")
        return [], no_data, no_data, "Awareness Rate — Latest Month", gating_style

    # Most improved card (Spec 9.3)
    most_improved_text = "—"
    if summary.get("most_improved_name"):
        change = summary["most_improved_change"]
        sign = "+" if change > 0 else ""
        most_improved_text = f"{summary['most_improved_name']} ({sign}{change:.1%})"

    kpi_cards = dbc.Row([
        dbc.Col(ci_stat_card("Brands Eligible", summary["n_brands"], fmt="{:,}"), md=3),
        dbc.Col(ci_stat_card("Market Average", summary["mean_rate"], fmt="{:.1%}"), md=3),
        dbc.Col(ci_stat_card(
            "Highest",
            summary["top_brand_rate"],
            fmt="{:.1%}",
            subtitle=summary["top_brand_name"],
        ), md=3),
        dbc.Col(ci_stat_card("Most Improved", most_improved_text), md=3),
    ])

    # Bump chart (Spec 9.4) — brands sorted alphabetically for colour assignment
    bump_data = calc_awareness_bump(df_main, df_questions, level)
    if bump_data.empty:
        bump_content = html.Div("Insufficient data for bump chart.", className="ci-suppression p-4")
    else:
        bump_data["month_label"] = bump_data["month"].apply(format_year_month)
        fig = create_bump_chart(
            bump_data,
            x_col="month_label",
            y_col="rank",
            brand_col="brand",
            rate_col="rate",
            title="",
        )
        bump_content = dcc.Graph(figure=fig, config={"displayModeBar": False})

    # Ranked bar chart — latest month (Spec 9.5)
    rates = calc_awareness_rates(df_main, df_questions, level)
    if rates.empty:
        bar_content = html.Div("Insufficient data for bar chart.", className="ci-suppression p-4")
        bar_title = "Awareness Rate — Latest Month"
    else:
        latest_month = rates["month"].max()
        latest = rates[rates["month"] == latest_month].sort_values("rate", ascending=True)
        market_avg = latest["rate"].mean()

        # Green above market, red below (Spec 9.5)
        bar_colours = [CI_GREEN if r > market_avg else CI_RED for r in latest["rate"]]

        fig_bar = go.Figure()
        fig_bar.add_trace(go.Bar(
            y=latest["brand"],
            x=latest["rate"],
            orientation="h",
            marker_color=bar_colours,
            text=[f"{r:.1%}" for r in latest["rate"]],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Rate: %{x:.1%}<extra></extra>",
        ))
        # Market average reference line (Spec 9.5)
        fig_bar.add_vline(
            x=market_avg,
            line_dash="dash",
            line_color=CI_GREY,
            line_width=1.5,
            annotation_text=f"Market avg: {market_avg:.1%}",
            annotation_font_size=11,
            annotation_font_color=CI_GREY,
        )
        fig_bar = create_branded_figure(fig_bar, title="")
        fig_bar.update_layout(
            xaxis_tickformat=".0%",
            yaxis_title="",
            height=max(400, len(latest) * 30),
            margin=dict(l=150),
        )
        bar_content = dcc.Graph(figure=fig_bar, config={"displayModeBar": False})
        bar_title = f"Awareness Rate — {format_year_month(latest_month)}"

    return kpi_cards, bump_content, bar_content, bar_title, gating_style
