"""
What Changed This Month — Anomaly Navigation (Spec Section 12).

Landing page that surfaces top movements and anomalies across all eligible
insurers. Entry point for quick scan mode.
"""

import pandas as pd
import streamlit as st

from lib.analytics.anomalies import scan_anomalies
from lib.analytics.demographics import apply_filters
from lib.analytics.rates import calc_retention_rate, calc_shopping_rate
from lib.analytics.flows import calc_net_flow
from lib.config import CI_GREEN, CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_RED, CI_YELLOW, MIN_BASE_PUBLISHABLE
from lib.narrative import generate_diagnostic_narrative
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("What Changed This Month")
st.caption("Anomaly detection across all eligible insurers")

# ---- Global filters ----
filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_all = apply_filters(df_motor, product=product, selected_months=selected_months)

if df_all.empty or not selected_months or len(selected_months) < 2:
    st.warning("Need at least two months of data to detect changes.")
    st.stop()

# ---- Split into current and previous periods ----
midpoint = len(selected_months) // 2
current_months = selected_months[midpoint:]
previous_months = selected_months[:midpoint]

df_current = df_all[df_all["RenewalYearMonth"].isin(current_months)]
df_previous = df_all[df_all["RenewalYearMonth"].isin(previous_months)]

period_label = (
    f"Current: {format_year_month(current_months[0])} to {format_year_month(current_months[-1])} | "
    f"Previous: {format_year_month(previous_months[0])} to {format_year_month(previous_months[-1])}"
)
st.caption(period_label)

# ---- Module filter ----
module_filter = st.radio(
    "Filter by module",
    ["All", "Shopping & Switching", "Awareness", "Claims"],
    horizontal=True,
)

# ---- Run anomaly scan ----
anomalies = scan_anomalies(df_current, df_previous)

if module_filter != "All":
    anomalies = [a for a in anomalies if a["module"] == module_filter]

# ---- AI Headline ----
if anomalies:
    top_findings = anomalies[:5]
    summary_text = "; ".join(a["description"] for a in top_findings[:3])
    st.markdown(f"**This month's key changes:** {summary_text}")
    st.markdown("---")

# ---- Anomaly Cards (top 5-10) ----
st.subheader("Top Movements")

if not anomalies:
    st.info("No significant anomalies detected in this period.")
else:
    for i, anomaly in enumerate(anomalies[:10]):
        severity_colours = {
            "high": CI_RED,
            "medium": CI_YELLOW,
            "low": CI_GREY,
        }
        border_colour = severity_colours.get(anomaly["severity"], CI_GREY)

        st.markdown(
            f'<div style="padding:12px 16px; border-left:4px solid {border_colour}; '
            f'background:{CI_LIGHT_GREY}; margin-bottom:8px; font-family:Verdana;">'
            f'<strong>{anomaly["insurer"]}</strong> &mdash; '
            f'{anomaly["metric"]} &nbsp;|&nbsp; '
            f'<span style="color:{border_colour}; font-weight:bold;">'
            f'{anomaly["severity"].upper()}</span><br>'
            f'<span style="font-size:13px;">{anomaly["description"]}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )

# ---- Movement Summary Table ----
st.markdown("---")
st.subheader("Movement Summary")

insurer_counts = df_current["CurrentCompany"].value_counts()
eligible_insurers = insurer_counts[insurer_counts >= MIN_BASE_PUBLISHABLE].index.tolist()

if eligible_insurers:
    summary_rows = []
    for insurer in sorted(eligible_insurers):
        ins_curr = df_current[df_current["CurrentCompany"] == insurer]
        ins_prev = df_previous[df_previous["CurrentCompany"] == insurer]

        ret_curr = calc_retention_rate(ins_curr)
        ret_prev = calc_retention_rate(ins_prev) if len(ins_prev) >= MIN_BASE_PUBLISHABLE else None
        shop_curr = calc_shopping_rate(ins_curr)
        shop_prev = calc_shopping_rate(ins_prev) if len(ins_prev) >= MIN_BASE_PUBLISHABLE else None
        n_ins_curr = len(ins_curr)
        nf_curr = calc_net_flow(df_current, insurer, base=n_ins_curr)
        nf_prev = calc_net_flow(df_previous, insurer, base=len(ins_prev) if len(ins_prev) > 0 else None) if not df_previous.empty else None

        ret_delta = ((ret_curr or 0) - (ret_prev or 0)) * 100 if ret_curr and ret_prev else None
        shop_delta = ((shop_curr or 0) - (shop_prev or 0)) * 100 if shop_curr and shop_prev else None
        nf_delta = nf_curr["net"] - nf_prev["net"] if nf_prev else None

        summary_rows.append({
            "Insurer": insurer,
            "Renewals": len(ins_curr),
            "Retention \u0394": f"{ret_delta:+.1f}pp" if ret_delta is not None else "\u2014",
            "Shopping \u0394": f"{shop_delta:+.1f}pp" if shop_delta is not None else "\u2014",
            "Net Flow": f"{nf_curr['net_pct']:+.1%} ({nf_curr['net']:+d})" if nf_curr.get("net_pct") is not None else f"{nf_curr['net']:+d}",
            "Net Flow \u0394": f"{nf_delta:+d}" if nf_delta is not None else "\u2014",
        })

    summary_df = pd.DataFrame(summary_rows)
    st.dataframe(summary_df, width="stretch", hide_index=True)
else:
    st.info("No insurers meet the minimum base threshold in the current period.")

# ---- Footer ----
st.caption(f"{period_label} | {len(eligible_insurers)} eligible insurers")
