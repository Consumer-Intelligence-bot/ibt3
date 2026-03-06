"""Page 4: Channel and PCW Analysis."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc
import plotly.graph_objects as go

from shared import DF_MOTOR, DF_HOME, DF_QUESTIONS
from analytics.channels import calc_channel_usage, calc_quote_buy_mismatch
from analytics.demographics import apply_filters
from analytics.suppression import check_suppression
from components.filter_bar import filter_bar
from components.cards import kpi_card
from components.branded_chart import create_branded_figure
import dash

dash.register_page(__name__, path="/channel-pcw", name="Channel & PCW")


def layout():
    return dbc.Container(
        [
            html.Div(id="filter-bar-ch"),
            dbc.Row(
                [dbc.Col(html.Div(id="mismatch-ch"), md=6), dbc.Col(html.Div(id="channel-usage-ch"), md=6)],
                className="mb-4",
            ),
        ],
        fluid=True,
    )


def _norm(val):
    return None if val in (None, "ALL", "") else val


@callback(
    [Output("filter-bar-ch", "children"), Output("mismatch-ch", "children"), Output("channel-usage-ch", "children")],
    [Input("global-insurer", "value"), Input("global-age-band", "value"), Input("global-region", "value"), Input("global-payment-type", "value"), Input("global-product", "value"), Input("global-time-window", "value")],
)
def update_channel(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    selected = [int(v) for v in time_window] if time_window else None
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)
    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_ins = apply_filters(df_main, insurer=insurer, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    df_mkt = apply_filters(df_main, insurer=None, product=product, selected_months=selected, age_band=age_band, region=region, payment_type=payment_type)
    sup = check_suppression(df_ins, df_mkt)
    filter_bar_el = filter_bar(age_band, region, payment_type)

    mis_ins = calc_quote_buy_mismatch(df_ins, DF_QUESTIONS) if insurer and sup.can_show_insurer else None
    mis_mkt = calc_quote_buy_mismatch(df_mkt, DF_QUESTIONS)
    mismatch_div = kpi_card("Quote-to-Buy Mismatch", mis_ins, mis_mkt) if mis_mkt is not None else html.P("Data not available", className="text-muted")

    ch = calc_channel_usage(df_ins if insurer and sup.can_show_insurer else df_mkt, DF_QUESTIONS)
    if ch is not None and len(ch) > 0:
        fig = go.Figure(go.Bar(x=ch.values, y=ch.index, orientation="h"))
        fig = create_branded_figure(fig, title="Channel Usage")
        channel_div = dcc.Graph(figure=fig)
    else:
        channel_div = html.P("Data not available", className="text-muted")

    return filter_bar_el, mismatch_div, channel_div
