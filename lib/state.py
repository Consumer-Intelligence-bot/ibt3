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
from lib.analytics.pivot import pivot_questions_to_wide
from lib.analytics.transforms import transform
from lib.config import (
    MAIN_TABLE, OTHER_TABLE,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
    PRODUCTS,
)
from lib.db import save_dataframe, load_dataframe, has_data, clear_data, save_metadata, load_metadata
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
                       main_table: str, other_table: str,
                       workspace_id: str, dataset_id: str):
    """Load and transform data for a single product, with wide question columns merged in."""
    df_raw = load_ss_maindata(
        token, start_month, end_month, main_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    if df_raw.empty:
        return pd.DataFrame()

    df = transform(df_raw, product)

    # Load EAV question data, pivot to wide, and merge onto main
    df_q = load_ss_questions(
        token, start_month, end_month, main_table, other_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    if not df_q.empty:
        df_q["UniqueID"] = df_q["UniqueID"].astype(str)
        df_q["Answer"] = df_q["Answer"].astype(str).str.strip()
        df_q["Product"] = product

        wide = pivot_questions_to_wide(df_q)
        if not wide.empty:
            df = df.merge(wide, left_on="UniqueID", right_index=True, how="left")

    return df


def init_ss_data(token: str, start_month: int, end_month: int,
                 main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE,
                 home_main_table: str = MAIN_TABLE, home_other_table: str = OTHER_TABLE):
    """Load S&S data from Power BI for all products, transform, and store in session state."""
    # Load motor data
    df_motor = _load_product_data(
        token, "Motor", start_month, end_month,
        main_table, other_table,
        MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    )

    # Load home data
    df_home = _load_product_data(
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

    st.session_state["df_motor"] = df_all

    if not df_all.empty:
        st.session_state["dimensions"] = get_all_dimensions(df_all)
        # Persist to local DB for refresh survival
        save_dataframe(df_all, "df_motor")
        # Store time window so we can detect stale cache on reload
        save_metadata("start_month", str(start_month))
        save_metadata("end_month", str(end_month))
    else:
        st.session_state["dimensions"] = {}


def load_from_db(start_month: int, end_month: int) -> bool:
    """Attempt to load data from local DuckDB cache.

    Returns True if data found and time window matches. If the cached data
    covers a different time window, returns False so the caller re-fetches.
    """
    if not has_data("df_motor"):
        return False

    # Check time window matches
    cached_start = load_metadata("start_month")
    cached_end = load_metadata("end_month")
    if cached_start != str(start_month) or cached_end != str(end_month):
        return False

    df_all = load_dataframe("df_motor")
    if df_all.empty:
        return False

    st.session_state["df_motor"] = df_all
    st.session_state["dimensions"] = get_all_dimensions(df_all)
    return True


def get_ss_data():
    """Get S&S dataframes from session state.

    Returns (df_motor, dimensions). All question data is merged into df_motor
    as wide columns — there is no separate df_questions table.
    """
    return (
        st.session_state.get("df_motor", pd.DataFrame()),
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
    # Persistent brand selection across pages
    default_idx = 0
    if "selected_insurer" in st.session_state and st.session_state["selected_insurer"] in insurer_list:
        default_idx = insurer_list.index(st.session_state["selected_insurer"]) + 1  # +1 for "" entry
    insurer = st.sidebar.selectbox(
        "Insurer", [""] + insurer_list,
        index=default_idx,
        format_func=lambda x: x or "All / Market",
        key="selected_insurer_selectbox",
    )
    # Store in session state for cross-page persistence
    if insurer:
        st.session_state["selected_insurer"] = insurer

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

    # "Other" toggle
    include_other = st.sidebar.toggle("Include 'Other'", value=False)

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
        "include_other": include_other,
    }


def render_dual_period_selector() -> dict | None:
    """
    Render dual period selector for the Brand Awareness tab (Change 1).

    Returns dict with keys:
      period_a_months, period_b_months, period_a_label, period_b_label,
      caption
    Or None if insufficient data to build the selector.
    """
    df_motor = st.session_state.get("df_motor", pd.DataFrame())
    if df_motor.empty or "RenewalYearMonth" not in df_motor.columns:
        return None

    all_months = sorted(
        df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist()
    )
    if len(all_months) < 2:
        return None

    month_labels = {m: format_month(m) for m in all_months}

    st.sidebar.markdown("---")
    st.sidebar.subheader("Period Comparison")

    # Period A — Comparison period (baseline)
    st.sidebar.markdown("**Comparison period** (baseline)")
    default_a_end_idx = max(0, len(all_months) - 13)
    default_a_start_idx = max(0, default_a_end_idx - 11)

    period_a_start, period_a_end = st.sidebar.select_slider(
        "Comparison period",
        options=all_months,
        value=(all_months[default_a_start_idx], all_months[default_a_end_idx]),
        format_func=lambda x: month_labels.get(x, str(x)),
        key="period_a_slider",
    )

    # Period B — Current period
    st.sidebar.markdown("**Current period** (now)")
    default_b_start_idx = min(default_a_end_idx + 1, len(all_months) - 1)

    # Filter months that come after Period A end
    b_options = [m for m in all_months if m > period_a_end]
    if not b_options:
        st.sidebar.error("Current period must follow comparison period.")
        return None

    period_b_start, period_b_end = st.sidebar.select_slider(
        "Current period",
        options=b_options,
        value=(b_options[0], b_options[-1]),
        format_func=lambda x: month_labels.get(x, str(x)),
        key="period_b_slider",
    )

    # Build month lists
    period_a_months = [m for m in all_months if period_a_start <= m <= period_a_end]
    period_b_months = [m for m in all_months if period_b_start <= m <= period_b_end]

    # Validation: at least one complete survey month each
    if not period_a_months or not period_b_months:
        st.sidebar.error("Select at least one full survey month for each period.")
        return None

    # Validation: no overlap
    if period_a_end >= period_b_start:
        st.sidebar.error("Periods overlap. Please adjust your selection.")
        return None

    period_a_label = f"{format_month(period_a_months[0])} to {format_month(period_a_months[-1])}"
    period_b_label = f"{format_month(period_b_months[0])} to {format_month(period_b_months[-1])}"
    caption = f"Comparison period: {period_a_label} | Current period: {period_b_label}"

    return {
        "period_a_months": period_a_months,
        "period_b_months": period_b_months,
        "period_a_label": period_a_label,
        "period_b_label": period_b_label,
        "caption": caption,
    }
