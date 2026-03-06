"""Page 6: Customer Flows."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from shared import DF_MOTOR, DF_HOME
from analytics.flows import calc_net_flow, calc_top_sources, calc_top_destinations
from analytics.demographics import apply_filters
from analytics.suppression import check_suppression
from components.filter_bar import filter_bar
from components.cards import kpi_card
from components.branded_chart import create_branded_figure
import dash
dash.register_page(__name__, path="/customer-flows", name="Customer Flows")

def layout():
    return dbc.Container([
        html.Div(id="filter-bar-cf"),
        dbc.Row([dbc.Col(html.Div(id="net-flow-cf"), md=12)], className="mb-4"),
        dbc.Row([dbc.Col(html.Div(id="sources-cf"), md=6), dbc.Col(html.Div(id="destinations-cf"), md=6)], className="mb-4"),
    ], fluid=True)

def _norm(val):
    return None if val in (None, "ALL", "") else val

@callback(
    [Output("filter-bar-cf", "children"), Output("net-flow-cf", "children"), Output("sources-cf", "children"), Output("destinations-cf", "children")],
    [Input("global-insurer", "value"), Input("global-age-band", "value"), Input("global-region", "value"), Input("global-payment-type", "value"), Input("global-product", "value"), Input("global-time-window", "value")],
)
def update_flows(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    selected = [int(v) for v in time_window] if time_window else None
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)
    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df = apply_filters(df_main, insurer=insurer, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    df_mkt = apply_filters(df_main, insurer=None, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    sup = check_suppression(df, df_mkt)
    filter_bar_el = filter_bar(age_band, region, payment_type)
    if not insurer:
        return filter_bar_el, html.P("Select an insurer", className="text-muted"), html.P("Select an insurer", className="text-muted"), html.P("Select an insurer", className="text-muted")
    if not sup.can_show_insurer:
        return filter_bar_el, html.P(sup.message, className="text-muted"), html.Div("—", className="text-muted"), html.Div("—", className="text-muted")
    nf = calc_net_flow(df_mkt, insurer)
    net_div = dbc.Row([
        dbc.Col(kpi_card("Gained", nf["gained"], nf["gained"], format_str="{:.0f}"), md=4),
        dbc.Col(kpi_card("Lost", nf["lost"], nf["lost"], format_str="{:.0f}"), md=4),
        dbc.Col(kpi_card("Net", nf["net"], nf["net"], format_str="{:.0f}"), md=4),
    ])
    src = calc_top_sources(df_mkt, insurer, 10)
    dst = calc_top_destinations(df_mkt, insurer, 10)
    # Sort ascending so largest appears at top (Plotly renders first y at bottom)
    src = src.sort_values(ascending=True) if len(src) > 0 else src
    dst = dst.sort_values(ascending=True) if len(dst) > 0 else dst
    fig_src = go.Figure(go.Bar(x=src.values, y=src.index, orientation="h")) if len(src) > 0 else go.Figure()
    fig_dst = go.Figure(go.Bar(x=dst.values, y=dst.index, orientation="h")) if len(dst) > 0 else go.Figure()
    fig_src = create_branded_figure(fig_src, title="Gaining From")
    fig_dst = create_branded_figure(fig_dst, title="Losing To")
    return filter_bar_el, net_div, dcc.Graph(figure=fig_src), dcc.Graph(figure=fig_dst)
