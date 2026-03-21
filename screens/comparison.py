"""
Compare Insurers overlay.

Multi-insurer metrics comparison table: retention, shopping, switching,
net flow, NPS, satisfaction. Sortable by any column.
"""

import pandas as pd
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import calc_net_flow
from lib.analytics.rates import (
    calc_retention_rate,
    calc_shopping_rate,
    calc_switching_rate,
)
from lib.analytics.satisfaction import calc_nps, calc_overall_satisfaction
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_YELLOW,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct, section_divider, period_label, FONT
from lib.state import get_ss_data


def render(filters: dict):
    """Render the Compare Insurers screen."""
    df_motor, dimensions = get_ss_data()

    if df_motor.empty:
        st.warning("No data loaded. Go to Admin to refresh from Power BI.")
        return

    product = filters["product"]
    selected_months = filters["selected_months"]

    df_mkt = apply_filters(
        df_motor,
        insurer=None,
        age_band=filters["age_band"],
        region=filters["region"],
        payment_type=filters["payment_type"],
        product=product,
        selected_months=selected_months,
    )

    if df_mkt.empty:
        st.warning("No data for selected filters.")
        return

    period = period_label(selected_months)
    n_mkt = len(df_mkt)
    mkt_retention = calc_retention_rate(df_mkt) or 0.5

    st.subheader("Compare Insurers")

    # Build comparison table
    all_insurers = dimensions.get("DimInsurer", pd.DataFrame())
    insurer_list = sorted(
        all_insurers["Insurer"].dropna().astype(str).tolist()
    ) if not all_insurers.empty else []

    rows = []
    for ins in insurer_list:
        ins_df = apply_filters(
            df_motor,
            insurer=ins,
            age_band=filters["age_band"],
            region=filters["region"],
            payment_type=filters["payment_type"],
            product=product,
            selected_months=selected_months,
        )
        n = len(ins_df)
        if n < MIN_BASE_PUBLISHABLE:
            continue

        retention = calc_retention_rate(ins_df)
        shopping = calc_shopping_rate(ins_df)
        switching = calc_switching_rate(ins_df)
        nf = calc_net_flow(df_mkt, ins, base=n)

        # Bayesian smoothed retention
        existing = ins_df[~ins_df.get("IsNewToMarket", False)] if "IsNewToMarket" in ins_df.columns else ins_df
        retained = int(existing["IsRetained"].sum()) if "IsRetained" in existing.columns else 0
        bay = bayesian_smooth_rate(retained, len(existing), mkt_retention)

        rows.append({
            "Insurer": ins,
            "n": n,
            "Retention": retention,
            "Retention (Bayesian)": bay["posterior_mean"],
            "Shopping": shopping,
            "Switching": switching,
            "Net Flow": nf["net"],
        })

    if not rows:
        st.warning("No insurers with sufficient data for comparison.")
        return

    df_compare = pd.DataFrame(rows)

    # Sort control
    sort_col = st.selectbox(
        "Sort by",
        ["Retention (Bayesian)", "Shopping", "Switching", "Net Flow", "n"],
        key="comparison_sort",
    )
    ascending = sort_col in ["Shopping", "Switching"]
    df_compare = df_compare.sort_values(sort_col, ascending=ascending)

    # Style the table
    def _style_row(row):
        styles = [""] * len(row)
        cols = list(row.index)

        # n column
        n_idx = cols.index("n")
        if row["n"] < 100:
            styles[n_idx] = f"background-color: {CI_YELLOW}; color: {CI_GREY}"

        # Net Flow column
        nf_idx = cols.index("Net Flow")
        if row["Net Flow"] > 0:
            styles[nf_idx] = f"color: {CI_GREEN}; font-weight: bold"
        elif row["Net Flow"] < 0:
            styles[nf_idx] = f"color: {CI_RED}; font-weight: bold"

        return styles

    styled = (
        df_compare.style
        .apply(_style_row, axis=1)
        .format({
            "Retention": "{:.1%}",
            "Retention (Bayesian)": "{:.1%}",
            "Shopping": "{:.1%}",
            "Switching": "{:.1%}",
            "Net Flow": "{:+,}",
            "n": "{:,}",
        })
        .set_properties(**{"font-family": "Verdana, sans-serif", "font-size": "12px"})
    )

    st.dataframe(styled, use_container_width=True, hide_index=True, height=min(800, len(rows) * 35 + 40))

    st.caption(
        f"Showing {len(rows)} insurers with n >= {MIN_BASE_PUBLISHABLE}. "
        f"Sorted by {sort_col}. Period: {period}."
    )

    st.markdown("---")
    st.caption(f"Compare Insurers | {filters['product']} | {period} | Market n={n_mkt:,}")
