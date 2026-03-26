"""
Header bar: horizontal tab navigation, insurer toggle, time slider, product selector.

Renders in the main area (not sidebar). Uses st.session_state["active_screen"]
for navigation with conditional rendering (not st.tabs).
"""

import streamlit as st

from lib.config import CI_GREY, CI_LIGHT_GREY, PRODUCTS
from lib.state import format_month
from screens import SCREENS, ADMIN_SCREENS


def _init_navigation():
    """Initialise session state keys for navigation."""
    if "active_screen" not in st.session_state:
        st.session_state["active_screen"] = "pre_renewal"


def render_tab_bar():
    """Render horizontal tab bar using st.columns + st.button."""
    active = st.session_state.get("active_screen", "switching")

    cols = st.columns(len(SCREENS))
    for i, screen in enumerate(SCREENS):
        with cols[i]:
            is_active = screen["key"] == active
            label = f"{screen['label']}"
            if st.button(
                label,
                key=f"tab_{screen['key']}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["active_screen"] = screen["key"]
                st.rerun()


def render_global_controls():
    """Render insurer toggle, product selector, and time slider in the sidebar.

    Returns a filters dict compatible with the existing page pattern.
    """
    _init_navigation()

    dimensions = st.session_state.get("dimensions", {})
    df_motor = st.session_state.get("df_motor")

    # --- Sidebar controls ---

    # Product selector
    product = st.sidebar.selectbox("Product", PRODUCTS, key="header_product")

    # Insurer selector (Market = no insurer selected)
    insurer_list = []
    if "DimInsurer" in dimensions:
        insurer_list = sorted(
            dimensions["DimInsurer"]["Insurer"].dropna().astype(str).tolist()
        )

    default_idx = 0
    if (
        "selected_insurer" in st.session_state
        and st.session_state["selected_insurer"] in insurer_list
    ):
        default_idx = insurer_list.index(st.session_state["selected_insurer"]) + 1

    insurer = st.sidebar.selectbox(
        "Insurer",
        [""] + insurer_list,
        index=default_idx,
        format_func=lambda x: x or "All / Market",
        key="header_insurer_selectbox",
    )
    if insurer:
        st.session_state["selected_insurer"] = insurer
    else:
        st.session_state.pop("selected_insurer", None)

    # Age Band
    age_options = ["ALL"]
    if "DimAgeBand" in dimensions:
        age_options += sorted(
            dimensions["DimAgeBand"]["AgeBand"].dropna().astype(str).tolist()
        )
    age_band = st.sidebar.selectbox("Age Band", age_options, key="header_age_band")

    # Region
    region_options = ["ALL"]
    if "DimRegion" in dimensions:
        region_options += sorted(
            dimensions["DimRegion"]["Region"].dropna().astype(str).tolist()
        )
    region = st.sidebar.selectbox("Region", region_options, key="header_region")

    # Payment Type
    payment_options = ["ALL"]
    if "DimPaymentType" in dimensions:
        payment_options += sorted(
            dimensions["DimPaymentType"]["PaymentType"]
            .dropna()
            .astype(str)
            .tolist()
        )
    payment_type = st.sidebar.selectbox(
        "Payment Type", payment_options, key="header_payment_type"
    )

    # Time Window
    months = []
    if df_motor is not None and not df_motor.empty and "RenewalYearMonth" in df_motor.columns:
        months = sorted(
            df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist()
        )

    selected_months = None
    if months:
        month_labels = {m: format_month(m) for m in months}
        default_start_idx = max(0, len(months) - 12)
        start_m, end_m = st.sidebar.select_slider(
            "Time window",
            options=months,
            value=(months[default_start_idx], months[-1]),
            format_func=lambda x: month_labels.get(x, str(x)),
            key="header_time_slider",
        )
        selected_months = [m for m in months if start_m <= m <= end_m]

    # "Other" toggle
    include_other = st.sidebar.toggle(
        "Include 'Other'", value=False, key="header_include_other"
    )

    # --- Admin / Methodology sidebar links ---
    st.sidebar.markdown("---")
    for screen in ADMIN_SCREENS:
        if st.sidebar.button(
            f"{screen['icon']} {screen['label']}",
            key=f"sidebar_{screen['key']}",
            use_container_width=True,
        ):
            st.session_state["active_screen"] = screen["key"]
            st.rerun()

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
