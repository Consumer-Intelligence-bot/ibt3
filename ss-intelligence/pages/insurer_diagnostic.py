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
from analytics.trends import calc_trend
from components.branded_chart import create_branded_figure
from components.ci_card import ci_kpi_card
from components.confidence_banner import confidence_banner
from components.dual_table import dual_table
from components.filter_bar import filter_bar
from config import (
    CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, DEFAULT_TIME_WINDOW_INSURER,
    MIN_BASE_REASON, NPS_MIN_N,
)
from shared import DF_MOTOR, DF_HOME, DF_QUESTIONS, format_year_month

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
    """Q40a satisfaction + Q40b NPS for leavers of this insurer, with market benchmarks."""
    departed = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
    n = len(departed)
    if n < NPS_MIN_N:
        return html.Div(
            f"Insufficient leavers ({n}) for satisfaction/NPS display (minimum {NPS_MIN_N}).",
            className="ci-suppression p-4",
        )

    all_switchers = df_mkt[df_mkt["IsSwitcher"]]
    cards = []

    # Q40a satisfaction (1-5 scale) — insurer + market benchmark
    if "Q40a" in departed.columns:
        q40a = pd.to_numeric(departed["Q40a"], errors="coerce").dropna()
        q40a_mkt = pd.to_numeric(all_switchers["Q40a"], errors="coerce").dropna() if "Q40a" in all_switchers.columns else pd.Series(dtype=float)
        if len(q40a) > 0:
            mkt_val = q40a_mkt.mean() if len(q40a_mkt) > 0 else None
            cards.append(dbc.Col(
                ci_kpi_card("Satisfaction (Q40a)", q40a.mean(), mkt_val, fmt="{:.1f}"),
                md=3,
            ))

    # Q40b NPS (0-10) — insurer + market benchmark
    if "Q40b" in departed.columns:
        q40b = pd.to_numeric(departed["Q40b"], errors="coerce").dropna()
        q40b_mkt = pd.to_numeric(all_switchers["Q40b"], errors="coerce").dropna() if "Q40b" in all_switchers.columns else pd.Series(dtype=float)
        if len(q40b) > 0:
            promoters = (q40b >= 9).sum()
            detractors = (q40b <= 6).sum()
            nps = 100 * (promoters - detractors) / len(q40b)
            mkt_nps = None
            if len(q40b_mkt) > 0:
                mkt_p = (q40b_mkt >= 9).sum()
                mkt_d = (q40b_mkt <= 6).sum()
                mkt_nps = 100 * (mkt_p - mkt_d) / len(q40b_mkt) / 100
            cards.append(dbc.Col(
                ci_kpi_card("NPS (Q40b)", nps / 100, mkt_nps, fmt="{:+.0%}"),
                md=3,
            ))

    cards.append(dbc.Col(
        ci_kpi_card("Leaver Base", n, fmt="{:.0f}", confidence_label=None),
        md=3,
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
    tw = int(time_window or DEFAULT_TIME_WINDOW_INSURER)
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)

    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_ins = apply_filters(df_main, insurer=insurer, age_band=age_band, region=region, payment_type=payment_type, product=product, time_window_months=tw)
    df_mkt = apply_filters(df_main, insurer=None, age_band=age_band, region=region, payment_type=payment_type, product=product, time_window_months=tw)

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

    # Trend indicator (Spec 6.3 / 12.3)
    trend_dir = None
    if insurer and sup.can_show_insurer:
        trend = calc_trend(df_ins, market_ret or 0.5)
        if not trend["suppressed"]:
            trend_dir = trend["direction"]

    # Retention card with position and trend
    if sup.can_show_insurer and bay:
        conf_label = sup.confidence.label.value if sup.confidence else None
        ret_card = ci_kpi_card(
            "Your Retention",
            bay["posterior_mean"], market_ret,
            ci_lower=bay.get("ci_lower"), ci_upper=bay.get("ci_upper"),
            confidence_label=conf_label,
            trend_direction=trend_dir,
        )
    else:
        ret_card = ci_kpi_card("Your Retention", None, market_ret, suppression_message=sup.message)

    # Net flow with visual indicator (Spec 6.5)
    if insurer and sup.can_show_insurer:
        nf = calc_net_flow(df_mkt, insurer)
        net_arrow = "up" if nf["net"] > 0 else ("down" if nf["net"] < 0 else "stable")
        net_div = dbc.Row([
            dbc.Col(ci_kpi_card("Gained", nf["gained"], fmt="{:.0f}"), md=3),
            dbc.Col(ci_kpi_card("Lost", nf["lost"], fmt="{:.0f}"), md=3),
            dbc.Col(ci_kpi_card("Net Flow", nf["net"], fmt="{:+.0f}", trend_direction=net_arrow), md=3),
        ])
    else:
        net_div = html.P("Select an insurer", className="text-muted")

    # Top sources / destinations with flow-cell suppression
    if insurer and sup.can_show_insurer:
        src = calc_top_sources(df_mkt, insurer, 5)
        dst = calc_top_destinations(df_mkt, insurer, 5)
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

    # Why Stay (Q18) — shoppers who stayed (Spec 6.6)
    # Why Leave (Q31) — switchers from this insurer (Spec 6.7)
    stay_tbl = html.P("Q18 data not available", className="text-muted")
    leave_tbl = html.P("Q31 data not available", className="text-muted")

    if insurer and sup.can_show_insurer:
        # Q18 suppression: need >= MIN_BASE_REASON staying shoppers
        staying_shoppers = df_ins[(df_ins["IsShopper"]) & (df_ins["IsRetained"])]
        n_staying = len(staying_shoppers)

        # Q31 suppression: need >= MIN_BASE_REASON switchers from this insurer
        switchers_from = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
        n_switchers = len(switchers_from)

        if DF_QUESTIONS is not None and not DF_QUESTIONS.empty:
            if n_staying >= MIN_BASE_REASON:
                cmp_stay = calc_reason_comparison(df_ins, DF_QUESTIONS, "Q18", insurer, 5)
                if cmp_stay:
                    stay_tbl = dual_table(cmp_stay.get("insurer"), cmp_stay.get("market"), "Why Customers Stay (Q18)", "Market", "stay")
            else:
                stay_tbl = html.Div(
                    f"Insufficient staying shoppers ({n_staying}) for Q18 analysis (minimum {MIN_BASE_REASON}).",
                    className="ci-suppression p-4",
                )

            if n_switchers >= MIN_BASE_REASON:
                cmp_leave = calc_reason_comparison(df_ins, DF_QUESTIONS, "Q31", insurer, 5)
                if cmp_leave:
                    leave_tbl = dual_table(cmp_leave.get("insurer"), cmp_leave.get("market"), "Why Customers Leave (Q31)", "Market", "leave")
            else:
                leave_tbl = html.Div(
                    f"Insufficient switchers ({n_switchers}) for Q31 analysis (minimum {MIN_BASE_REASON}).",
                    className="ci-suppression p-4",
                )

    # Leavers' rating (Q40a/Q40b) — Spec Section 6.8
    leavers = _calc_leavers_rating(df_mkt, insurer) if insurer and sup.can_show_insurer else None
    leavers_div = leavers or html.Div()

    return filter_bar_el, conf_banner, ret_card, net_div, src_div, dst_div, stay_tbl, leave_tbl, leavers_div
