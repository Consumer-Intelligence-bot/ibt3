"""
Session state management for the unified Streamlit dashboard.

Handles data loading from Power BI, transformation, and filter application.
All pages read from st.session_state rather than loading data independently.
"""

import datetime

import pandas as pd
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.dimensions import get_all_dimensions
from lib.analytics.transforms import transform
from lib.config import (
    MAIN_TABLE, OTHER_TABLE,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
    PRODUCTS,
)
from lib.powerbi import load_months, load_ss_maindata, load_ss_questions


_MONTH_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def format_month(yyyymm: int) -> str:
    """Convert integer YYYYMM to 'Mon YYYY' label."""
    y = yyyymm // 100
    m = yyyymm % 100
    try:
        return datetime.date(y, m, 1).strftime("%b %Y")
    except ValueError:
        return str(yyyymm)


def format_year_month(ym) -> str:
    """Convert YYYYMM (e.g. 202401) to readable label (e.g. 'Jan 2024')."""
    if pd.isna(ym) or ym is None:
        return ""
    ym = int(float(ym))
    y, m = ym // 100, ym % 100
    if 1 <= m <= 12:
        return f"{_MONTH_ABBR[m]} {y}"
    return str(ym)


def _load_product_data(token: str, product: str, start_month: int, end_month: int,
                       main_table: str, other_table: str | None,
                       workspace_id: str, dataset_id: str):
    """Load and transform data for a single product from its fabric instance."""
    df_raw = load_ss_maindata(
        token, start_month, end_month, main_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    if df_raw.empty:
        return pd.DataFrame(), pd.DataFrame()

    df = transform(df_raw, product)

    df_q = pd.DataFrame()
    if other_table:
        df_q = load_ss_questions(
            token, start_month, end_month, main_table, other_table,
            workspace_id=workspace_id, dataset_id=dataset_id,
        )
    if not df_q.empty:
        df_q["UniqueID"] = df_q["UniqueID"].astype(str)
        df_q["Answer"] = df_q["Answer"].astype(str).str.strip()
        df_q["Product"] = product

    return df, df_q


def init_ss_data(token: str, start_month: int, end_month: int,
                 main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE,
                 home_main_table: str = MAIN_TABLE, home_other_table: str = OTHER_TABLE):
    """Load S&S data from Power BI for all products, transform, and store in session state."""
    # Load motor data
    df_motor, df_q_motor = _load_product_data(
        token, "Motor", start_month, end_month,
        main_table, other_table,
        MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    )

    # Load home data
    df_home, df_q_home = _load_product_data(
        token, "Home", start_month, end_month,
        home_main_table, home_other_table,
        HOME_WORKSPACE_ID, HOME_DATASET_ID,
    )

    # Combine products
    frames = [df for df in [df_motor, df_home] if not df.empty]
    if frames:
        df_all = pd.concat(frames, ignore_index=True)
    else:
        df_all = pd.DataFrame()

    q_frames = [df for df in [df_q_motor, df_q_home] if not df.empty]
    if q_frames:
        df_questions = pd.concat(q_frames, ignore_index=True)
    else:
        df_questions = pd.DataFrame()

    st.session_state["df_motor"] = df_all
    st.session_state["df_questions"] = df_questions

    if not df_all.empty:
        st.session_state["dimensions"] = get_all_dimensions(df_all)
    else:
        st.session_state["dimensions"] = {}


def get_ss_data():
    """Get S&S dataframes from session state."""
    return (
        st.session_state.get("df_motor", pd.DataFrame()),
        st.session_state.get("df_questions", pd.DataFrame()),
        st.session_state.get("dimensions", {}),
    )


def get_filtered_data(
    insurer: str | None = None,
    age_band: str | None = None,
    region: str | None = None,
    payment_type: str | None = None,
    product: str = "Motor",
    selected_months: list[int] | None = None,
):
    """Apply filters and return (df_insurer, df_market) tuple."""
    df_motor = st.session_state.get("df_motor", pd.DataFrame())
    if df_motor.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_mkt = apply_filters(
        df_motor, insurer=None, age_band=age_band, region=region,
        payment_type=payment_type, product=product, selected_months=selected_months,
    )
    df_ins = apply_filters(
        df_motor, insurer=insurer, age_band=age_band, region=region,
        payment_type=payment_type, product=product, selected_months=selected_months,
    ) if insurer else df_mkt

    return df_ins, df_mkt


def render_global_filters():
    """Render global filters in the sidebar and return filter values."""
    dimensions = st.session_state.get("dimensions", {})
    df_motor = st.session_state.get("df_motor", pd.DataFrame())

    # Insurer
    insurer_list = []
    if "DimInsurer" in dimensions:
        insurer_list = sorted(dimensions["DimInsurer"]["Insurer"].dropna().astype(str).tolist())
    insurer = st.sidebar.selectbox("Insurer", [""] + insurer_list, format_func=lambda x: x or "All / Market")

    # Product
    product = st.sidebar.selectbox("Product", PRODUCTS)

    # Age Band
    age_options = ["ALL"]
    if "DimAgeBand" in dimensions:
        age_options += sorted(dimensions["DimAgeBand"]["AgeBand"].dropna().astype(str).tolist())
    age_band = st.sidebar.selectbox("Age Band", age_options)

    # Region
    region_options = ["ALL"]
    if "DimRegion" in dimensions:
        region_options += sorted(dimensions["DimRegion"]["Region"].dropna().astype(str).tolist())
    region = st.sidebar.selectbox("Region", region_options)

    # Payment Type
    payment_options = ["ALL"]
    if "DimPaymentType" in dimensions:
        payment_options += sorted(dimensions["DimPaymentType"]["PaymentType"].dropna().astype(str).tolist())
    payment_type = st.sidebar.selectbox("Payment Type", payment_options)

    # Time Window
    months = []
    if not df_motor.empty and "RenewalYearMonth" in df_motor.columns:
        months = sorted(df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist())

    selected_months = None
    if months:
        month_labels = {m: format_month(m) for m in months}
        default_start_idx = max(0, len(months) - 12)
        start_m, end_m = st.sidebar.select_slider(
            "Time window",
            options=months,
            value=(months[default_start_idx], months[-1]),
            format_func=lambda x: month_labels.get(x, str(x)),
        )
        selected_months = [m for m in months if start_m <= m <= end_m]

    # Normalise
    insurer = insurer or None
    age_band = None if age_band in (None, "ALL", "") else age_band
    region = None if region in (None, "ALL", "") else region
    payment_type = None if payment_type in (None, "ALL", "") else payment_type

    return {
        "insurer": insurer,
        "product": product or "Motor",
        "age_band": age_band,
        "region": region,
        "payment_type": payment_type,
        "selected_months": selected_months,
    }
