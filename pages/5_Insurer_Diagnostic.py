"""
Insurer Diagnostic — Single insurer deep-dive.
Retention, flows, behavioural drivers, Q40a/Q40b.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import calc_net_flow, calc_top_sources, calc_top_destinations
from lib.analytics.rates import calc_retention_rate
from lib.analytics.reasons import calc_reason_comparison
from lib.analytics.suppression import check_suppression
from lib.analytics.trends import calc_trend
from lib.config import CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, MIN_BASE_REASON, NPS_MIN_N
from lib.state import render_global_filters, get_ss_data

st.header("Insurer Diagnostic")

filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

insurer = filters["insurer"]
if not insurer:
    st.info("Select an insurer in the sidebar.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]

df_ins = apply_filters(
    df_motor, insurer=insurer, age_band=filters["age_band"], region=filters["region"],
    payment_type=filters["payment_type"], product=product, selected_months=selected_months,
)
df_mkt = apply_filters(
    df_motor, insurer=None, age_band=filters["age_band"], region=filters["region"],
    payment_type=filters["payment_type"], product=product, selected_months=selected_months,
)

market_ret = calc_retention_rate(df_mkt)
sup = check_suppression(df_ins, df_mkt)

# ---- Retention ----
st.subheader("Retention Performance")

if sup.can_show_insurer and len(df_ins) > 0:
    existing_ins = df_ins[~df_ins["IsNewToMarket"]]
    retained = (existing_ins["IsRetained"]).sum()
    total_existing = len(existing_ins)

    if total_existing > 0 and market_ret:
        bay = bayesian_smooth_rate(int(retained), total_existing, market_ret)
        trend = calc_trend(df_ins, market_ret)
        trend_arrow = {"up": "\u25B2", "down": "\u25BC", "stable": "\u25CF"}.get(
            trend["direction"] if not trend["suppressed"] else None, "\u2014"
        )

        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Retention (Bayesian)", f"{bay['posterior_mean']:.1%}")
            st.caption(f"95% CI: {bay['ci_lower']:.1%} \u2013 {bay['ci_upper']:.1%}")
        with col2:
            st.metric("Market Retention", f"{market_ret:.1%}")
        with col3:
            gap = bay["posterior_mean"] - market_ret
            st.metric("Gap to Market", f"{gap:+.1%}")
            st.caption(f"Trend: {trend_arrow}")
    else:
        st.info("Insufficient existing customer data for retention calculation.")
else:
    st.warning(sup.message if sup.message else "Insufficient data.")

# ---- Net Flow ----
st.subheader("Customer Flow")

if sup.can_show_insurer:
    nf = calc_net_flow(df_mkt, insurer)
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Gained", f"{nf['gained']:,}")
    with col2:
        st.metric("Lost", f"{nf['lost']:,}")
    with col3:
        st.metric("Net Flow", f"{nf['net']:+,}")
else:
    st.warning("Insufficient data for flow analysis.")

# ---- Top Sources / Destinations ----
if sup.can_show_insurer:
    col_src, col_dst = st.columns(2)
    with col_src:
        st.subheader("Gained From")
        src = calc_top_sources(df_mkt, insurer, 5)
        if len(src) > 0:
            src = src.sort_values(ascending=True)
            fig = go.Figure(go.Bar(x=src.values, y=src.index, orientation="h", marker_color=CI_GREEN))
            fig.update_layout(height=250, margin=dict(l=150, t=10), font=dict(family="Verdana"),
                              plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No source data.")

    with col_dst:
        st.subheader("Lost To")
        dst = calc_top_destinations(df_mkt, insurer, 5)
        if len(dst) > 0:
            dst = dst.sort_values(ascending=True)
            fig = go.Figure(go.Bar(x=dst.values, y=dst.index, orientation="h", marker_color=CI_RED))
            fig.update_layout(height=250, margin=dict(l=150, t=10), font=dict(family="Verdana"),
                              plot_bgcolor="white", paper_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
        else:
            st.info("No destination data.")

# ---- Why Stay (Q18) / Why Leave (Q31) ----
if sup.can_show_insurer and not df_questions.empty:
    col_stay, col_leave = st.columns(2)

    with col_stay:
        st.subheader("Why Customers Stay (Q18)")
        staying_shoppers = df_ins[(df_ins["IsShopper"]) & (df_ins["IsRetained"])]
        if len(staying_shoppers) >= MIN_BASE_REASON:
            cmp_stay = calc_reason_comparison(df_ins, df_questions, "Q18", insurer, 5)
            if cmp_stay:
                ins_reasons = cmp_stay.get("insurer", [])
                mkt_reasons = cmp_stay.get("market", [])
                if ins_reasons:
                    data = []
                    for i, r in enumerate(ins_reasons):
                        mkt_val = mkt_reasons[i]["pct"] if i < len(mkt_reasons) else 0
                        data.append({"Reason": r["reason"], f"{insurer}": f"{r['pct']:.0%}", "Market": f"{mkt_val:.0%}"})
                    st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
            else:
                st.info("No Q18 data available.")
        else:
            st.info(f"Insufficient staying shoppers ({len(staying_shoppers)}) for Q18 analysis.")

    with col_leave:
        st.subheader("Why Customers Leave (Q31)")
        switchers_from = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
        if len(switchers_from) >= MIN_BASE_REASON:
            cmp_leave = calc_reason_comparison(df_ins, df_questions, "Q31", insurer, 5)
            if cmp_leave:
                ins_reasons = cmp_leave.get("insurer", [])
                mkt_reasons = cmp_leave.get("market", [])
                if ins_reasons:
                    data = []
                    for i, r in enumerate(ins_reasons):
                        mkt_val = mkt_reasons[i]["pct"] if i < len(mkt_reasons) else 0
                        data.append({"Reason": r["reason"], f"{insurer}": f"{r['pct']:.0%}", "Market": f"{mkt_val:.0%}"})
                    st.dataframe(pd.DataFrame(data), width="stretch", hide_index=True)
            else:
                st.info("No Q31 data available.")
        else:
            st.info(f"Insufficient switchers ({len(switchers_from)}) for Q31 analysis.")

# ---- Leavers Rating (Q40a/Q40b) ----
if sup.can_show_insurer:
    st.subheader("How Leavers Rated This Insurer")
    departed = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
    if len(departed) >= NPS_MIN_N:
        all_switchers = df_mkt[df_mkt["IsSwitcher"]]
        cols = st.columns(3)

        if "Q40a" in departed.columns:
            q40a = pd.to_numeric(departed["Q40a"], errors="coerce").dropna()
            q40a_mkt = pd.to_numeric(all_switchers["Q40a"], errors="coerce").dropna() if "Q40a" in all_switchers.columns else pd.Series(dtype=float)
            if len(q40a) > 0:
                with cols[0]:
                    st.metric("Satisfaction (Q40a)", f"{q40a.mean():.1f}",
                              delta=f"{q40a.mean() - q40a_mkt.mean():+.1f} vs market" if len(q40a_mkt) > 0 else None)

        if "Q40b" in departed.columns:
            q40b = pd.to_numeric(departed["Q40b"], errors="coerce").dropna()
            if len(q40b) > 0:
                promoters = (q40b >= 9).sum()
                detractors = (q40b <= 6).sum()
                nps = 100 * (promoters - detractors) / len(q40b)
                with cols[1]:
                    st.metric("NPS (Q40b)", f"{nps:+.0f}")

        with cols[2]:
            st.metric("Leaver Base", f"{len(departed):,}")
    else:
        st.info(f"Insufficient leavers ({len(departed)}) for satisfaction display (minimum {NPS_MIN_N}).")
