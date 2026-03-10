"""
Session state management for the unified Streamlit dashboard.

Handles data loading from Power BI (or disk cache), transformation,
and filter application.  All pages read from st.session_state rather
than loading data independently.
"""

import datetime

import pandas as pd
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.dimensions import get_all_dimensions
from lib.analytics.transforms import transform
from lib.cache import is_cached, load_cache, save_cache
from lib.config import MAIN_TABLE, OTHER_TABLE
from lib.powerbi import (
    load_all_maindata,
    load_all_questions,
    load_months,
    load_ss_maindata,
    load_ss_questions,
)


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


def load_startup_data(token: str) -> tuple[str, str, list[int]]:
    """Load table names and months, using disk cache when available.

    Returns (main_table, other_table, months).
    Falls back to Power BI queries if no disk cache exists.
    """
    cache = load_cache()
    if cache is not None:
        return cache["main_table"], cache["other_table"], cache["months"]

    # No disk cache — must query Power BI
    from lib.powerbi import get_main_table, get_other_table

    main_table = get_main_table(token)
    other_table = get_other_table(token)
    months = load_months(token, main_table)
    return main_table, other_table, months


def init_ss_data(token: str, start_month: int, end_month: int,
                 main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE):
    """Load S&S data, transform, and store in session state.

    Uses disk cache when available.  Falls back to Power BI queries
    and saves the result to disk for future restarts.
    """
    cache = load_cache()

    if cache is not None:
        # Disk cache hit — filter by time window in memory
        df_raw = cache["df_main"]
        df_questions = cache["df_questions"]

        if not df_raw.empty and "RenewalYearMonth" in df_raw.columns:
            df_raw = df_raw[
                (df_raw["RenewalYearMonth"] >= start_month)
                & (df_raw["RenewalYearMonth"] <= end_month)
            ].copy()

        if not df_questions.empty and "UniqueID" in df_questions.columns:
            valid_ids = set(df_raw["UniqueID"].astype(str)) if "UniqueID" in df_raw.columns else set()
            if valid_ids:
                df_questions = df_questions[
                    df_questions["UniqueID"].astype(str).isin(valid_ids)
                ].copy()
    else:
        # No disk cache — fetch ALL data from Power BI and cache to disk
        df_all_main = load_all_maindata(token, main_table)
        df_all_questions = load_all_questions(token, main_table, other_table)

        # Compute months list from the full dataset
        if not df_all_main.empty and "RenewalYearMonth" in df_all_main.columns:
            months = sorted(df_all_main["RenewalYearMonth"].dropna().unique().astype(int).tolist())
        else:
            months = []

        # Persist to disk
        save_cache(main_table, other_table, months, df_all_main, df_all_questions)

        # Filter to requested time window
        df_raw = df_all_main
        df_questions = df_all_questions
        if not df_raw.empty and "RenewalYearMonth" in df_raw.columns:
            df_raw = df_raw[
                (df_raw["RenewalYearMonth"] >= start_month)
                & (df_raw["RenewalYearMonth"] <= end_month)
            ].copy()

        if not df_questions.empty and "UniqueID" in df_questions.columns:
            valid_ids = set(df_raw["UniqueID"].astype(str)) if "UniqueID" in df_raw.columns else set()
            if valid_ids:
                df_questions = df_questions[
                    df_questions["UniqueID"].astype(str).isin(valid_ids)
                ].copy()

    # Transform and store in session state
    if df_raw.empty:
        st.session_state["df_motor"] = pd.DataFrame()
        st.session_state["df_questions"] = pd.DataFrame()
        st.session_state["dimensions"] = {}
        return

    df_motor = transform(df_raw, "Motor")
    st.session_state["df_motor"] = df_motor

    if not df_questions.empty:
        df_questions["UniqueID"] = df_questions["UniqueID"].astype(str)
        df_questions["Answer"] = df_questions["Answer"].astype(str).str.strip()
    st.session_state["df_questions"] = df_questions

    st.session_state["dimensions"] = get_all_dimensions(df_motor)


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
    product = st.sidebar.selectbox("Product", ["Motor"], disabled=True)

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
