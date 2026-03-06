"""
Global filter bar - shared across all pages for cross-tab context persistence.
"""
from dash import html, dcc
import dash_bootstrap_components as dbc

from components.filters import (
    insurer_dropdown,
    age_band_dropdown,
    region_dropdown,
    payment_type_dropdown,
    product_toggle,
    renewal_month_dropdown,
)


def global_filter_bar(dim_insurer, dim_age, dim_region, dim_payment,
                       month_options=None, month_defaults=None):
    """Build the shared filter bar with global IDs. Used in app layout.

    Parameters
    ----------
    month_options : list of {'label': 'Mon YY', 'value': YYYYMM}
    month_defaults : list of YYYYMM ints (default selection, e.g. last 12)
    """
    month_options = month_options or []
    month_defaults = month_defaults or []
    return dbc.Container(
        dbc.Row(
            [
                dbc.Col(insurer_dropdown("global-insurer", dim_insurer), md=2),
                dbc.Col(age_band_dropdown("global-age-band", dim_age), md=2),
                dbc.Col(region_dropdown("global-region", dim_region), md=2),
                dbc.Col(payment_type_dropdown("global-payment-type", dim_payment), md=2),
                dbc.Col(product_toggle("global-product", "Motor"), md=1),
                dbc.Col(
                    renewal_month_dropdown(
                        "global-time-window",
                        month_options,
                        month_defaults,
                    ),
                    md=3,
                ),
            ],
            className="mb-2",
        ),
        fluid=True,
    )
