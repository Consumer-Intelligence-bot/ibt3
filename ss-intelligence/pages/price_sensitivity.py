"""Page 5: Price Sensitivity."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go
from shared import DF_MOTOR, DF_HOME
from analytics.price import calc_price_direction_dist
from analytics.demographics import apply_filters
from analytics.suppression import check_suppression
from components.filter_bar import filter_bar
from components.branded_chart import create_branded_figure
import dash
dash.register_page(__name__, path="/price-sensitivity", name="Price Sensitivity")

def layout():
    return dbc.Container([
        html.Div(id="filter-bar-ps"),
        dbc.Row([dbc.Col(html.Div(id="price-direction-ps"), md=12)], className="mb-4"),
    ], fluid=True)

def _norm(val):
    return None if val in (None, "ALL", "") else val

@callback(
    [Output("filter-bar-ps", "children"), Output("price-direction-ps", "children")],
    [Input("global-insurer", "value"), Input("global-age-band", "value"), Input("global-region", "value"), Input("global-payment-type", "value"), Input("global-product", "value"), Input("global-time-window", "value")],
)
def update_price(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    selected = [int(v) for v in time_window] if time_window else None
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)
    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_ins = apply_filters(df_main, insurer=insurer, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    df_mkt = apply_filters(df_main, insurer=None, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    sup = check_suppression(df_ins, df_mkt)
    filter_bar_el = filter_bar(age_band, region, payment_type)
    dist_ins = calc_price_direction_dist(df_ins) if insurer and sup.can_show_insurer else None
    dist_mkt = calc_price_direction_dist(df_mkt)
    if dist_mkt is not None and len(dist_mkt) > 0:
        fig = go.Figure()
        if dist_ins is not None and len(dist_ins) > 0:
            fig.add_trace(go.Bar(name="Your Customers", x=dist_ins.index, y=dist_ins.values, marker_color="#981D97"))
        fig.add_trace(go.Bar(name="Market", x=dist_mkt.index, y=dist_mkt.values, marker_color="#54585A"))
        fig.update_layout(barmode="group")
        fig = create_branded_figure(fig, title="Price Direction Distribution")
        price_div = dcc.Graph(figure=fig)
    else:
        price_div = html.P("Data not available", className="text-muted")
    return filter_bar_el, price_div
