"""
Page 3: Insurer Comparison (Spec Section 7).

Side-by-side view of retention with CI whiskers, market line, and confidence labels.
Includes Trend column, conditional formatting, and multi-select insurer filter.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dash_table, dcc, html

from analytics.bayesian import bayesian_smooth_rate
from analytics.confidence import ConfidenceLabel, MetricType, assess_confidence
from analytics.demographics import apply_filters
from analytics.flows import calc_net_flow
from analytics.rates import calc_retention_rate, calc_shopping_rate
from analytics.trends import calc_trend
from auth.access import get_authorized_insurers
from components.branded_chart import add_ci_whiskers, create_branded_figure
from components.filter_bar import filter_bar
from config import (
    CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, CI_YELLOW,
    DEFAULT_TIME_WINDOW_INSURER, MIN_BASE_PUBLISHABLE, SYSTEM_FLOOR_N,
)
from shared import DF_MOTOR, DIMENSIONS

dash.register_page(__name__, path="/insurer-comparison", name="Insurer Comparison")


def layout():
    all_insurers = DIMENSIONS["DimInsurer"]["Insurer"].dropna().astype(str).tolist()
    insurer_options = [{"label": i, "value": i} for i in sorted(all_insurers)]

    return dbc.Container([
        html.Div(className="ci-page-header", children=[html.H1("Insurer Comparison")]),
        html.Div(id="filter-bar-comp"),
        # Multi-select insurer filter (Spec 7.3)
        dbc.Row([
            dbc.Col([
                dcc.Dropdown(
                    id="comp-insurer-filter",
                    options=insurer_options,
                    multi=True,
                    placeholder="Filter to specific insurers (optional)...",
                ),
            ], md=6),
        ], className="mb-3"),
        dbc.Row([dbc.Col(html.Div(id="retention-chart-comp"), md=12)], className="mb-4"),
        dbc.Row([dbc.Col(html.Div(id="metrics-table-comp"), md=12)]),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


@callback(
    [Output("filter-bar-comp", "children"), Output("retention-chart-comp", "children"), Output("metrics-table-comp", "children")],
    [Input("global-age-band", "value"), Input("global-region", "value"), Input("global-payment-type", "value"),
     Input("global-product", "value"), Input("global-time-window", "value"), Input("comp-insurer-filter", "value")],
)
def update_comparison(age_band, region, payment_type, product, time_window, selected_insurers):
    product = product or "Motor"
    tw = int(time_window or DEFAULT_TIME_WINDOW_INSURER)
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)

    df_mkt = apply_filters(DF_MOTOR, product=product, time_window_months=tw, age_band=age_band, region=region, payment_type=payment_type)
    market_ret = calc_retention_rate(df_mkt)

    all_insurers = DIMENSIONS["DimInsurer"]["Insurer"].dropna().astype(str).tolist()
    insurers = get_authorized_insurers(all_insurers)

    if selected_insurers:
        insurers = [i for i in insurers if i in selected_insurers]

    rows = []

    for ins in insurers:
        df_ins = apply_filters(DF_MOTOR, insurer=ins, product=product, time_window_months=tw, age_band=age_band, region=region, payment_type=payment_type)
        n = len(df_ins)
        if n < SYSTEM_FLOOR_N:
            continue

        retained = (df_ins["IsRetained"] & ~df_ins["IsNewToMarket"]).sum()
        total = len(df_ins[~df_ins["IsNewToMarket"]])
        if total == 0:
            continue

        bay = bayesian_smooth_rate(int(retained), total, market_ret or 0.5)
        ci_w = (bay["ci_upper"] - bay["ci_lower"]) * 100
        conf = assess_confidence(n, bay["posterior_mean"], MetricType.RATE, posterior_ci_width=ci_w)

        if conf.label == ConfidenceLabel.INSUFFICIENT:
            continue

        shopping = calc_shopping_rate(df_ins)
        nf = calc_net_flow(df_mkt, ins)

        # Trend calculation (Spec 12.3)
        trend = calc_trend(df_ins, market_ret or 0.5)
        trend_dir = trend["direction"] if not trend["suppressed"] else None

        rows.append({
            "Insurer": ins,
            "n": total,
            "retention": bay["posterior_mean"],
            "ci_lower": bay["ci_lower"],
            "ci_upper": bay["ci_upper"],
            "ci_width": ci_w,
            "shopping": shopping,
            "net_flow": nf["net"],
            "confidence": conf.label.value,
            "trend_dir": trend_dir,
        })

    df_tbl = pd.DataFrame(rows)
    eligible = len(df_tbl)
    filter_bar_el = filter_bar(age_band, region, payment_type, eligible_count=eligible)

    if df_tbl.empty:
        return filter_bar_el, html.P("No insurers meet threshold.", className="ci-suppression p-4"), html.Div()

    df_tbl = df_tbl.sort_values("retention", ascending=False)

    # Retention bar chart with CI whiskers and market line
    colours = [CI_GREEN if r > (market_ret or 0) else CI_RED for r in df_tbl["retention"]]
    fig = go.Figure(go.Bar(
        x=df_tbl["retention"],
        y=df_tbl["Insurer"],
        orientation="h",
        marker_color=colours,
        text=[f"{r:.1%}" for r in df_tbl["retention"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Retention: %{x:.1%}<extra></extra>",
    ))
    fig = add_ci_whiskers(
        fig,
        x_values=df_tbl["retention"].tolist(),
        y_values=df_tbl["Insurer"].tolist(),
        ci_lower=df_tbl["ci_lower"].tolist(),
        ci_upper=df_tbl["ci_upper"].tolist(),
        colour=CI_GREY,
        horizontal=True,
    )
    fig = create_branded_figure(fig, title="", show_market_line=True, market_value=market_ret)
    fig.update_layout(
        xaxis_tickformat=".0%",
        yaxis=dict(autorange="reversed"),
        height=max(400, len(df_tbl) * 35),
        margin=dict(l=150),
    )
    chart = dcc.Graph(figure=fig, config={"displayModeBar": False})

    # Metrics table with Trend column and conditional formatting (Spec 7.3)
    _TREND_ARROWS = {"up": "▲", "down": "▼", "stable": "●"}
    display = df_tbl.copy()
    display["Retention"] = display["retention"].apply(lambda x: f"{x:.1%}")
    display["Shopping Rate"] = display["shopping"].apply(lambda x: f"{x:.1%}" if x else "-")
    display["Net Flow"] = display["net_flow"].apply(lambda x: f"{x:+,}" if x else "-")
    display["Trend"] = display["trend_dir"].apply(lambda x: _TREND_ARROWS.get(x, "—") if x else "—")
    display["Confidence"] = display["confidence"]
    display["Renewals"] = display["n"].apply(lambda x: f"{x:,}")
    display["_ret_raw"] = display["retention"]
    display["_nf_raw"] = display["net_flow"]
    display = display[["Insurer", "Renewals", "Retention", "Shopping Rate", "Net Flow", "Trend", "Confidence", "_ret_raw", "_nf_raw"]]

    table = dash_table.DataTable(
        data=display.to_dict("records"),
        columns=[{"name": c, "id": c} for c in display.columns if not c.startswith("_")],
        sort_action="native",
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#E9EAEB", "fontWeight": 600, "fontSize": "12px", "color": CI_GREY},
        style_cell={"fontSize": "13px", "padding": "8px 12px"},
        style_data_conditional=[
            {"if": {"filter_query": "{Confidence} = LOW"}, "fontStyle": "italic", "color": "#E65100"},
            {"if": {"filter_query": "{Confidence} = HIGH"}, "color": CI_GREEN},
            # Green/red for retention vs market
            {"if": {"filter_query": f"{{_ret_raw}} > {market_ret or 0}", "column_id": "Retention"}, "backgroundColor": "#E8F5E9", "color": CI_GREEN},
            {"if": {"filter_query": f"{{_ret_raw}} < {market_ret or 0}", "column_id": "Retention"}, "backgroundColor": "#FFEBEE", "color": CI_RED},
            # Green/red for net flow
            {"if": {"filter_query": "{_nf_raw} > 0", "column_id": "Net Flow"}, "backgroundColor": "#E8F5E9", "color": CI_GREEN},
            {"if": {"filter_query": "{_nf_raw} < 0", "column_id": "Net Flow"}, "backgroundColor": "#FFEBEE", "color": CI_RED},
            # Trend arrows
            {"if": {"filter_query": '{Trend} = "▲"', "column_id": "Trend"}, "color": CI_GREEN},
            {"if": {"filter_query": '{Trend} = "▼"', "column_id": "Trend"}, "color": CI_RED},
            {"if": {"filter_query": '{Trend} = "●"', "column_id": "Trend"}, "color": CI_GREY},
        ],
        hidden_columns=["_ret_raw", "_nf_raw"],
    )

    return filter_bar_el, chart, table
