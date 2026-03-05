"""
Market Overview (Page 1, Spec Section 5).

Public-facing page showing market-level KPIs, trends, top reasons, and channels.
No individual insurer names. Uses Bayesian CI where appropriate.
"""
import pandas as pd
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from analytics.bayesian import bayesian_smooth_rate
from analytics.channels import calc_channel_usage, calc_pcw_usage
from analytics.confidence import calc_ci_width
from analytics.demographics import apply_filters
from analytics.rates import calc_shopping_rate, calc_switching_rate, calc_retention_rate
from analytics.reasons import calc_reason_ranking
from components.branded_chart import create_branded_figure
from components.ci_card import ci_kpi_card, ci_stat_card
from config import CI_GREEN, CI_GREY, CI_MAGENTA, MARKET_CI_ALERT_THRESHOLD
from shared import format_year_month


def layout(DF_MOTOR, DF_HOME):
    return dbc.Container(
        [html.Div(id="market-overview-content-mo")],
        fluid=True,
        className="mb-5",
    )


def register_callbacks(app, DF_MOTOR, DF_HOME):
    from shared import DF_QUESTIONS

    @app.callback(
        Output("market-overview-content-mo", "children"),
        [Input("global-product", "value"), Input("global-time-window", "value")],
    )
    def update_market_overview(product, time_window):
        product = product or "Motor"
        tw = int(time_window or 24)
        df = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
        df_market = apply_filters(df, product=product, time_window_months=tw)
        n = len(df_market)

        shop = calc_shopping_rate(df_market)
        switch = calc_switching_rate(df_market)
        retain = calc_retention_rate(df_market)

        # KPI cards with Bayesian CI
        kpi_cards = dbc.Row([
            dbc.Col(ci_kpi_card("Shopping Rate", shop, fmt="{:.0%}"), md=3),
            dbc.Col(ci_kpi_card("Switching Rate", switch, fmt="{:.0%}"), md=3),
            dbc.Col(ci_kpi_card("Retention Rate", retain, fmt="{:.0%}"), md=3),
            dbc.Col(ci_stat_card("Respondents", n, fmt="{:,}"), md=3),
        ], className="mb-4")

        # Retention trend
        by_month = df_market.groupby("RenewalYearMonth").agg(
            retained=("IsRetained", "sum"),
            total=("UniqueID", "count"),
        ).reset_index()
        by_month["retention"] = by_month["retained"] / by_month["total"]
        by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)

        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=by_month["month_label"],
            y=by_month["retention"],
            mode="lines+markers",
            line=dict(color=CI_MAGENTA, width=2.5),
            marker=dict(size=6),
            hovertemplate="Retention: %{y:.1%}<br>%{x}<extra></extra>",
        ))
        fig_trend = create_branded_figure(fig_trend, title="Market Retention Trend")
        fig_trend.update_layout(yaxis_tickformat=".0%")

        # Why customers shop (Q8) — rank 1 only
        why_content = html.P("Q8 data not available", className="text-muted")
        if DF_QUESTIONS is not None and not DF_QUESTIONS.empty:
            why = calc_reason_ranking(df_market, DF_QUESTIONS, "Q8", top_n=5)
            if why:
                why_df = pd.DataFrame(why)
                fig_why = go.Figure(go.Bar(
                    x=why_df["rank1_pct"],
                    y=why_df["reason"],
                    orientation="h",
                    marker_color=CI_MAGENTA,
                    text=[f"{p:.0%}" for p in why_df["rank1_pct"]],
                    textposition="outside",
                ))
                fig_why = create_branded_figure(fig_why, title="")
                fig_why.update_layout(
                    xaxis_tickformat=".0%",
                    height=250,
                    margin=dict(l=200, t=10),
                )
                why_content = dcc.Graph(figure=fig_why, config={"displayModeBar": False})
        elif "Q8" in df_market.columns:
            why = calc_reason_ranking(df_market, pd.DataFrame(), "Q8", top_n=5)
            if why:
                why_df = pd.DataFrame(why)
                why_content = dbc.Table.from_dataframe(
                    why_df[["reason", "rank1_pct"]].rename(columns={"rank1_pct": "%"}),
                    striped=True, size="sm",
                )

        # Channel usage (Q9b via EAV)
        ch = calc_channel_usage(df_market, DF_QUESTIONS)
        if ch is not None and len(ch) > 0:
            ch = ch.head(8)
            fig_ch = go.Figure(go.Bar(
                x=ch.values, y=ch.index, orientation="h",
                marker_color=CI_GREEN,
                text=[f"{v:.0%}" for v in ch.values],
                textposition="outside",
            ))
            fig_ch = create_branded_figure(fig_ch, title="")
            fig_ch.update_layout(xaxis_tickformat=".0%", height=250, margin=dict(l=150, t=10))
            channel_div = dcc.Graph(figure=fig_ch, config={"displayModeBar": False})
        else:
            channel_div = html.P("Channel data not available", className="text-muted")

        # PCW usage (Q11)
        pcw = calc_pcw_usage(df_market, DF_QUESTIONS)
        if pcw is not None and len(pcw) > 0:
            fig_pcw = go.Figure(go.Pie(
                labels=pcw.index, values=pcw.values, hole=0.4,
                textinfo="label+percent",
                marker=dict(line=dict(color="white", width=2)),
            ))
            fig_pcw = create_branded_figure(fig_pcw, title="")
            fig_pcw.update_layout(height=250, margin=dict(t=10))
            pcw_content = dcc.Graph(figure=fig_pcw, config={"displayModeBar": False})
        else:
            pcw_content = html.P("PCW data not available", className="text-muted")

        max_ym = df_market["RenewalYearMonth"].max() if "RenewalYearMonth" in df_market.columns else ""
        period_str = format_year_month(max_ym) if pd.notna(max_ym) and max_ym else "—"
        footer = html.Div(
            f"Data period: {period_str} | n={n:,} | (c) Consumer Intelligence 2026",
            className="text-muted small mt-4",
        )

        return dbc.Container([
            kpi_cards,
            dbc.Row([
                dbc.Col(dcc.Graph(figure=fig_trend, config={"displayModeBar": False}), md=6),
                dbc.Col(html.Div([html.H2("Why Customers Shop (Q8)"), why_content]), md=6),
            ], className="mb-4"),
            dbc.Row([
                dbc.Col(html.Div([html.H2("Shopping Channels"), channel_div]), md=6),
                dbc.Col(html.Div([html.H2("PCW Market Share"), pcw_content, footer]), md=6),
            ]),
        ], fluid=True)
