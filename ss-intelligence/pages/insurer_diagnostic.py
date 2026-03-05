"""
Page 2: Insurer Diagnostic (Spec Section 6).

Single insurer deep-dive: retention, flows, behavioural drivers, Q40a/Q40b.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, callback, dcc, html

from analytics.bayesian import bayesian_smooth_rate
from analytics.bayesian_precompute import get_cached_rate
from analytics.confidence import MetricType
from analytics.demographics import apply_filters, get_active_filters
from analytics.flows import (
    calc_net_flow,
    calc_top_destinations,
    calc_top_sources,
    is_flow_cell_suppressed,
)
from analytics.reasons import calc_reason_comparison
from analytics.rates import calc_retention_rate
from analytics.suppression import check_suppression
from components.branded_chart import create_branded_figure
from components.ci_card import ci_kpi_card
from components.confidence_banner import confidence_banner
from components.dual_table import dual_table
from components.filter_bar import filter_bar
from config import CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, NPS_MIN_N
from shared import DF_MOTOR, DF_QUESTIONS, format_year_month

dash.register_page(__name__, path="/insurer-diagnostic", name="Insurer Diagnostic")


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[html.H1("Insurer Diagnostic")]),
        html.Div(id="filter-bar-diag"),
        html.Div(id="confidence-banner-diag"),

        # Retention performance cards
        dbc.Row([
            dbc.Col(html.Div(id="retention-card-diag"), md=4),
            dbc.Col(html.Div(id="net-flow-diag"), md=8),
        ], className="mb-4"),

        # Customer flow panel
        dbc.Row([
            dbc.Col(html.Div(id="flows-sources-diag"), md=6),
            dbc.Col(html.Div(id="flows-dest-diag"), md=6),
        ], className="mb-4"),

        # Why Stay / Why Leave
        dbc.Row([
            dbc.Col(html.Div(id="why-stay-diag"), md=6),
            dbc.Col(html.Div(id="why-leave-diag"), md=6),
        ], className="mb-4"),

        # Q40a/Q40b: Leavers' rating (Spec Section 6.8)
        dbc.Row([
            dbc.Col(html.Div(id="leavers-rating-diag"), md=12),
        ]),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


def _calc_leavers_rating(df_mkt: pd.DataFrame, insurer: str) -> html.Div | None:
    """Q40a satisfaction + Q40b NPS for leavers of this insurer."""
    departed = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
    n = len(departed)
    if n < NPS_MIN_N:
        return html.Div(
            f"Insufficient leavers ({n}) for satisfaction/NPS display (minimum {NPS_MIN_N}).",
            className="text-muted small",
        )

    cards = []

    # Q40a satisfaction (1-5 scale)
    if "Q40a" in departed.columns:
        q40a = pd.to_numeric(departed["Q40a"], errors="coerce").dropna()
        if len(q40a) > 0:
            cards.append(dbc.Col(
                ci_kpi_card("Satisfaction (Q40a)", q40a.mean(), fmt="{:.1f}", confidence_label=None),
                md=4,
            ))

    # Q40b NPS (0-10)
    if "Q40b" in departed.columns:
        q40b = pd.to_numeric(departed["Q40b"], errors="coerce").dropna()
        if len(q40b) > 0:
            promoters = (q40b >= 9).sum()
            detractors = (q40b <= 6).sum()
            nps = 100 * (promoters - detractors) / len(q40b)
            cards.append(dbc.Col(
                ci_kpi_card("NPS (Q40b)", nps / 100, fmt="{:+.0%}", confidence_label=None),
                md=4,
            ))

    # Respondent base
    cards.append(dbc.Col(
        ci_kpi_card("Leaver Base", n, fmt="{:.0f}", confidence_label=None),
        md=4,
    ))

    if not cards:
        return None

    return html.Div([
        html.H2("How Leavers Rated This Insurer"),
        html.P("Shown for respondents who switched away from this insurer.", className="text-muted small"),
        dbc.Row(cards),
    ])


@callback(
    [
        Output("filter-bar-diag", "children"),
        Output("confidence-banner-diag", "children"),
        Output("retention-card-diag", "children"),
        Output("net-flow-diag", "children"),
        Output("flows-sources-diag", "children"),
        Output("flows-dest-diag", "children"),
        Output("why-stay-diag", "children"),
        Output("why-leave-diag", "children"),
        Output("leavers-rating-diag", "children"),
    ],
    [
        Input("global-insurer", "value"),
        Input("global-age-band", "value"),
        Input("global-region", "value"),
        Input("global-payment-type", "value"),
        Input("global-product", "value"),
        Input("global-time-window", "value"),
    ],
)
def update_insurer_diagnostic(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    tw = int(time_window or 24)
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)

    df_ins = apply_filters(DF_MOTOR, insurer=insurer, age_band=age_band, region=region, payment_type=payment_type, product=product, time_window_months=tw)
    df_mkt = apply_filters(DF_MOTOR, insurer=None, age_band=age_band, region=region, payment_type=payment_type, product=product, time_window_months=tw)

    market_ret = calc_retention_rate(df_mkt)

    # Bayesian-smoothed retention for CI-width assessment
    retained = (df_ins["IsRetained"] & ~df_ins["IsNewToMarket"]).sum() if len(df_ins) > 0 else 0
    total = len(df_ins[~df_ins["IsNewToMarket"]]) if len(df_ins) > 0 else 0
    bay = None
    posterior_ci_width = None
    if total > 0 and market_ret:
        cached = get_cached_rate(insurer, product, tw) if not (age_band or region or payment_type) else None
        bay = cached or bayesian_smooth_rate(int(retained), total, market_ret)
        posterior_ci_width = (bay["ci_upper"] - bay["ci_lower"]) * 100

    sup = check_suppression(
        df_ins, df_mkt,
        metric_type=MetricType.RATE,
        rate=bay["posterior_mean"] if bay else None,
        posterior_ci_width=posterior_ci_width,
        active_filters=get_active_filters(age_band, region, payment_type),
    )

    filter_bar_el = filter_bar(age_band, region, payment_type)
    tw_str = f"Last {tw} months"
    conf_banner = confidence_banner(
        n=len(df_ins),
        time_window=tw_str,
        rate=bay["posterior_mean"] if bay else None,
        posterior_ci_width=posterior_ci_width,
        metric_type=MetricType.RATE,
        age_band=age_band,
        region=region,
        payment_type=payment_type,
        suppression_message=sup.message,
    )

    # Retention card
    if sup.can_show_insurer and bay:
        conf_label = sup.confidence.label.value if sup.confidence else None
        ret_card = ci_kpi_card(
            "Your Retention",
            bay["posterior_mean"], market_ret,
            ci_lower=bay.get("ci_lower"), ci_upper=bay.get("ci_upper"),
            confidence_label=conf_label,
        )
    else:
        ret_card = ci_kpi_card("Your Retention", None, market_ret, suppression_message=sup.message)

    # Net flow
    if insurer and sup.can_show_insurer:
        nf = calc_net_flow(df_mkt, insurer)
        net_colour = "text-ci-green" if nf["net"] > 0 else "text-ci-red" if nf["net"] < 0 else ""
        net_div = dbc.Row([
            dbc.Col(ci_kpi_card("Gained", nf["gained"], fmt="{:.0f}"), md=4),
            dbc.Col(ci_kpi_card("Lost", nf["lost"], fmt="{:.0f}"), md=4),
            dbc.Col(ci_kpi_card("Net Flow", nf["net"], fmt="{:+.0f}"), md=4),
        ])
    else:
        net_div = html.P("Select an insurer", className="text-muted")

    # Top sources / destinations with flow-cell suppression
    if insurer and sup.can_show_insurer:
        src = calc_top_sources(df_mkt, insurer, 5)
        dst = calc_top_destinations(df_mkt, insurer, 5)
        # Suppress flow cells below threshold
        src = src[src.apply(lambda x: not is_flow_cell_suppressed(x))]
        dst = dst[dst.apply(lambda x: not is_flow_cell_suppressed(x))]

        src = src.sort_values(ascending=True) if len(src) > 0 else src
        dst = dst.sort_values(ascending=True) if len(dst) > 0 else dst
        fig_src = go.Figure(go.Bar(x=src.values, y=src.index, orientation="h", marker_color=CI_GREEN)) if len(src) > 0 else go.Figure()
        fig_dst = go.Figure(go.Bar(x=dst.values, y=dst.index, orientation="h", marker_color=CI_RED)) if len(dst) > 0 else go.Figure()
        fig_src = create_branded_figure(fig_src, title="Top Sources (Gained From)")
        fig_dst = create_branded_figure(fig_dst, title="Top Destinations (Lost To)")
        src_div = dcc.Graph(figure=fig_src, config={"displayModeBar": False})
        dst_div = dcc.Graph(figure=fig_dst, config={"displayModeBar": False})
    else:
        src_div = html.P("Select an insurer", className="text-muted")
        dst_div = html.P("Select an insurer", className="text-muted")

    # Why Stay (Q18) — ALL non-switchers (not just shoppers)
    # Why Leave (Q31) — switchers only
    if DF_QUESTIONS is not None and not DF_QUESTIONS.empty:
        cmp_stay = calc_reason_comparison(df_ins, DF_QUESTIONS, "Q18", insurer, 5)
        cmp_leave = calc_reason_comparison(df_ins, DF_QUESTIONS, "Q31", insurer, 5)
    else:
        cmp_stay = calc_reason_comparison(df_ins, df_mkt, "Q18", 5) if "Q18" in DF_MOTOR.columns else None
        cmp_leave = calc_reason_comparison(df_ins, df_mkt, "Q31", 5) if "Q31" in DF_MOTOR.columns else None

    stay_tbl = dual_table(cmp_stay.get("insurer"), cmp_stay.get("market"), "Why Customers Stay (Q18)", "Market", "stay") if cmp_stay else html.P("Q18 data not available", className="text-muted")
    leave_tbl = dual_table(cmp_leave.get("insurer"), cmp_leave.get("market"), "Why Customers Leave (Q31)", "Market", "leave") if cmp_leave else html.P("Q31 data not available", className="text-muted")

    # Leavers' rating (Q40a/Q40b) — Spec Section 6.8
    leavers = _calc_leavers_rating(df_mkt, insurer) if insurer and sup.can_show_insurer else None
    leavers_div = leavers or html.Div()

    return filter_bar_el, conf_banner, ret_card, net_div, src_div, dst_div, stay_tbl, leave_tbl, leavers_div
