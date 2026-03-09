"""
Shopping & Switching Intelligence — Dash application (LEGACY).

CI-branded dashboard with confidence-first governance.

NOTE: This is the legacy Dash version. The active dashboard is the
Streamlit app in the repository root (../app.py).  Do NOT run this
file with ``streamlit run`` — use ``python app.py`` or gunicorn.
"""
import os
import sys
from pathlib import Path

# Guard: prevent accidental execution inside Streamlit's script runner.
if "streamlit.runtime.scriptrunner" in sys.modules:
    raise SystemExit(
        "ERROR: ss-intelligence/app.py is a Dash app and cannot be run "
        "with 'streamlit run'.  Use the root app.py instead:\n"
        "  streamlit run ../app.py"
    )

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import dash
from dash import html, dcc, callback, Input, Output
import dash_bootstrap_components as dbc

sys_path = Path(__file__).resolve().parent
if str(sys_path) not in sys.path:
    sys.path.insert(0, str(sys_path))

from shared import DF_MOTOR, DF_HOME, DIMENSIONS, format_year_month
from auth.access import get_authorized_insurers
from components.global_filters import global_filter_bar
from components.ci_navbar import ci_navbar

app = dash.Dash(
    __name__,
    use_pages=True,
    pages_folder="dash_pages",
    external_stylesheets=[dbc.themes.BOOTSTRAP],
    suppress_callback_exceptions=True,
)

# Market Overview lives outside Dash Pages to avoid duplicate callback registration for path="/"
from views.market_overview import layout as market_overview_layout, register_callbacks as register_market_overview
register_market_overview(app, DF_MOTOR, DF_HOME)


def _build_renewal_month_options():
    """Extract unique RenewalYearMonth values from data and build dropdown options."""
    import numpy as np
    all_ym = set()
    for df in (DF_MOTOR, DF_HOME):
        if df is not None and "RenewalYearMonth" in df.columns:
            all_ym.update(df["RenewalYearMonth"].dropna().unique())
    sorted_ym = sorted(all_ym, reverse=True)  # newest first
    options = [{"label": format_year_month(int(ym)), "value": int(ym)} for ym in sorted_ym]
    defaults = [int(ym) for ym in sorted_ym[:12]]  # last 12 months
    return options, defaults


def _build_global_filter_bar():
    all_insurers = DIMENSIONS["DimInsurer"]["Insurer"].dropna().astype(str).tolist()
    authorized = get_authorized_insurers(all_insurers)
    dim_insurer = [{"Insurer": i, "value": i, "label": i, "SortOrder": idx} for idx, i in enumerate(authorized)]
    dim_age = DIMENSIONS["DimAgeBand"].to_dict("records")
    dim_region = DIMENSIONS["DimRegion"].to_dict("records")
    dim_payment = DIMENSIONS["DimPaymentType"].to_dict("records")
    month_options, month_defaults = _build_renewal_month_options()
    return global_filter_bar(dim_insurer, dim_age, dim_region, dim_payment,
                             month_options=month_options, month_defaults=month_defaults)


@callback(
    Output("page-content", "children"),
    Input("url", "pathname"),
)
def display_page(pathname):
    if pathname == "/" or pathname is None:
        return market_overview_layout(DF_MOTOR, DF_HOME)
    return dbc.Container(dash.page_container, fluid=True, className="mb-5")


@callback(
    Output("global-filter-container", "className"),
    Input("url", "pathname"),
)
def toggle_global_filters(pathname):
    return "d-none" if pathname == "/admin" else "ci-filter-bar mb-3"


@callback(
    Output("navbar-container", "children"),
    Input("url", "pathname"),
)
def update_navbar(pathname):
    return ci_navbar(pathname or "/")


app.layout = html.Div([
    dcc.Location(id="url", refresh=False),
    html.Div(ci_navbar("/"), id="navbar-container"),
    html.Div(_build_global_filter_bar(), id="global-filter-container", className="ci-filter-bar mb-3"),
    html.Div(id="page-content"),
])


server = app.server

_auth_user = os.getenv("BASIC_AUTH_USERNAME")
_auth_pass = os.getenv("BASIC_AUTH_PASSWORD")
if _auth_user and _auth_pass:
    from dash_auth import BasicAuth
    BasicAuth(app, {_auth_user: _auth_pass})

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=8050, use_reloader=False)
