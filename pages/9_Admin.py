"""
Admin / Governance — Internal page.
Data quality monitoring, confidence threshold management.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.confidence import MetricType, assess_confidence, calc_ci_width
from lib.analytics.flows import calc_flow_matrix
from lib.analytics.rates import calc_retention_rate, calc_shopping_rate, calc_switching_rate
from lib.config import (
    CI_GREEN, CI_GREY, CI_RED, CI_YELLOW,
    CI_WIDTH_INDICATIVE_AWARENESS, CI_WIDTH_INDICATIVE_RATE, CI_WIDTH_INDICATIVE_REASON,
    CI_WIDTH_PUBLISHABLE_AWARENESS, CI_WIDTH_PUBLISHABLE_RATE, CI_WIDTH_PUBLISHABLE_REASON,
    CONFIDENCE_LEVEL, MARKET_CI_ALERT_THRESHOLD, MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE, NPS_MIN_N, PRIOR_STRENGTH, SYSTEM_FLOOR_N,
    TREND_NOISE_THRESHOLD,
)
from lib.state import format_year_month, get_ss_data

st.header("Admin / Governance")
st.caption("Internal page \u2014 not visible to clients")

df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

# ---- Summary KPIs ----
total = len(df_motor)
all_insurers = dimensions.get("DimInsurer", pd.DataFrame())
insurer_list = all_insurers["Insurer"].dropna().astype(str).tolist() if not all_insurers.empty else []
eligible = sum(1 for ins in insurer_list if len(df_motor[df_motor["CurrentCompany"] == ins]) >= MIN_BASE_PUBLISHABLE)
suppressed = len(insurer_list) - eligible

# Data freshness
freshness = None
if "RenewalYearMonth" in df_motor.columns:
    max_ym = df_motor["RenewalYearMonth"].max()
    if pd.notna(max_ym):
        y, m = int(max_ym // 100), int(max_ym % 100)
        latest = datetime(y, m, 1, tzinfo=timezone.utc)
        freshness = (datetime.now(timezone.utc) - latest).days

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Total Respondents", f"{total:,}")
with col2:
    st.metric("Eligible Insurers", f"{eligible:,}")
with col3:
    st.metric("Suppressed", f"{suppressed:,}")
with col4:
    st.metric("Data Freshness", f"{freshness} days" if freshness else "N/A")
    if freshness and freshness > 45:
        st.warning("Alert: > 45 days old")

# ---- Confidence Thresholds ----
st.subheader("Confidence Thresholds")

thresholds = pd.DataFrame([
    {"Metric Type": "Retention / Shopping / Switching", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_RATE, "Description": "Max 95% posterior CI width for client output"},
    {"Metric Type": "Retention / Shopping / Switching", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_RATE, "Description": "Max CI width for internal indicative results"},
    {"Metric Type": "Reason Percentages", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_REASON, "Description": "Reason %s are noisier; wider threshold"},
    {"Metric Type": "Reason Percentages", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_REASON, "Description": "Internal indicative for reason analysis"},
    {"Metric Type": "Awareness Rates", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_AWARENESS, "Description": "Same as binary rate metrics at insurer level"},
    {"Metric Type": "Awareness Rates", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_AWARENESS, "Description": "Internal indicative for awareness"},
    {"Metric Type": "NPS (Q40b)", "Threshold": "Minimum n", "Value": float(NPS_MIN_N), "Description": "NPS uses n floor, not CI width"},
    {"Metric Type": "All metrics", "Threshold": "Absolute n floor", "Value": float(SYSTEM_FLOOR_N), "Description": "Floor below which no result shown (hardcoded)"},
])

edited = st.data_editor(thresholds, width="stretch", num_rows="fixed", key="threshold_editor")

# ---- Governance Parameters ----
st.subheader("Governance Parameters")
market_ret = df_motor["IsRetained"].mean() if "IsRetained" in df_motor.columns else 0.5

params = pd.DataFrame([
    {"Parameter": "Minimum base (publishable)", "Value": str(MIN_BASE_PUBLISHABLE), "Description": "n \u2265 50 for client-facing outputs"},
    {"Parameter": "Minimum base (indicative)", "Value": "30", "Description": "n \u2265 30 for internal review with caveat"},
    {"Parameter": "Minimum base (flow cell)", "Value": str(MIN_BASE_FLOW_CELL), "Description": "n \u2265 10 for insurer-to-insurer pairs"},
    {"Parameter": "Bayesian prior strength", "Value": str(PRIOR_STRENGTH), "Description": "Pseudo-observations"},
    {"Parameter": "Bayesian prior mean", "Value": f"{market_ret:.1%}", "Description": "Market average retention rate"},
    {"Parameter": "Confidence interval", "Value": f"{CONFIDENCE_LEVEL:.0%}", "Description": "Credible interval level"},
    {"Parameter": "Trend noise threshold", "Value": f"{TREND_NOISE_THRESHOLD:.1f}pp", "Description": "Change must exceed avg CI width"},
])
st.dataframe(params, width="stretch", hide_index=True)

# ---- Market-Level CI ----
st.subheader("Market-Level Confidence")
col1, col2, col3 = st.columns(3)
for col, label, calc_fn in [
    (col1, "Retention", calc_retention_rate),
    (col2, "Shopping", calc_shopping_rate),
    (col3, "Switching", calc_switching_rate),
]:
    rate = calc_fn(df_motor)
    ci_w = calc_ci_width(total, rate) if rate else None
    alert = ci_w is not None and ci_w > MARKET_CI_ALERT_THRESHOLD
    with col:
        st.metric(f"Market {label} CI", f"{ci_w:.2f}pp" if ci_w else "N/A")
        if alert:
            st.warning(f"Alert: > {MARKET_CI_ALERT_THRESHOLD}pp")

# ---- QC Flags: Q4=Q39 ----
st.subheader("QC Flags: Q4=Q39")
if not df_questions.empty and "RenewalYearMonth" in df_motor.columns:
    switchers = df_motor[df_motor["IsSwitcher"]][["UniqueID", "RenewalYearMonth"]].copy()
    if not switchers.empty:
        q4 = df_questions[df_questions["QuestionNumber"] == "Q4"][["UniqueID", "Answer"]].rename(columns={"Answer": "Q4"})
        q39 = df_questions[df_questions["QuestionNumber"] == "Q39"][["UniqueID", "Answer"]].rename(columns={"Answer": "Q39"})
        merged = switchers.merge(q4, on="UniqueID", how="left").merge(q39, on="UniqueID", how="left")
        merged["flagged"] = merged["Q4"] == merged["Q39"]
        by_month = merged.groupby("RenewalYearMonth").agg(
            total=("UniqueID", "count"), flagged=("flagged", "sum"),
        ).reset_index()
        by_month["flag_rate"] = by_month["flagged"] / by_month["total"]
        by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)

        fig_qc = go.Figure()
        fig_qc.add_trace(go.Bar(
            x=by_month["month_label"], y=by_month["flag_rate"],
            marker_color=CI_GREY,
            text=[f"{r:.1%}" for r in by_month["flag_rate"]],
            textposition="outside",
        ))
        fig_qc.add_hline(y=0.02, line_dash="dash", line_color=CI_RED, annotation_text="2% threshold")
        fig_qc.update_layout(
            height=250, margin=dict(t=30), yaxis_tickformat=".1%",
            font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig_qc, width="stretch")
    else:
        st.info("No switcher data for QC flags.")
else:
    st.info("No QC flag data available.")

# ---- Respondents by Month ----
st.subheader("Respondents by Month")
by_month = df_motor.groupby("RenewalYearMonth").size().reset_index(name="count")
by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)
fig_dist = go.Figure(go.Bar(x=by_month["month_label"], y=by_month["count"], marker_color=CI_GREY))
fig_dist.update_layout(
    height=250, margin=dict(t=10), font=dict(family="Verdana"),
    plot_bgcolor="white", paper_bgcolor="white",
)
st.plotly_chart(fig_dist, width="stretch")

# ---- Data Validation ----
st.subheader("Data Validation")
val_results = []
if "UniqueID" in df_motor.columns:
    dup = df_motor["UniqueID"].duplicated().sum()
    val_results.append({"Check": "No duplicate IDs", "Status": "PASS" if dup == 0 else "FAIL", "Detail": f"{dup} duplicates" if dup else "OK"})
for col_name in ("AgeBand", "Region"):
    if col_name in df_motor.columns:
        missing = df_motor[col_name].isna().sum()
        val_results.append({"Check": f"{col_name} complete", "Status": "PASS" if missing == 0 else "WARN", "Detail": f"{missing} missing" if missing else "OK"})
flow_mat = calc_flow_matrix(df_motor)
if len(flow_mat) > 0:
    total_out = flow_mat.sum().sum()
    total_in = flow_mat.sum(axis=1).sum()
    balanced = abs(total_out - total_in) < 1
    val_results.append({"Check": "Flow balance", "Status": "PASS" if balanced else "FAIL", "Detail": "OK" if balanced else f"Out={total_out:.0f} In={total_in:.0f}"})

if val_results:
    st.dataframe(pd.DataFrame(val_results), width="stretch", hide_index=True)

# ---- Insurer Data Quality ----
st.subheader("Insurer Data Quality")
quality_rows = []
for ins in sorted(insurer_list):
    ins_df = df_motor[df_motor["CurrentCompany"] == ins]
    n = len(ins_df)
    if n == 0:
        continue
    retained = ins_df["IsRetained"].sum() if "IsRetained" in ins_df.columns else 0
    smoothed = bayesian_smooth_rate(int(retained), n, market_ret)
    ci_w = (smoothed["ci_upper"] - smoothed["ci_lower"]) * 100
    conf = assess_confidence(n, retained / n if n > 0 else 0, MetricType.RATE, posterior_ci_width=ci_w)
    quality_rows.append({
        "Insurer": ins, "n": n,
        "CI Width (pp)": round(ci_w, 1),
        "Confidence": conf.label.value,
        "Weight": f"{smoothed['weight']:.0%}",
    })

if quality_rows:
    st.dataframe(pd.DataFrame(quality_rows), width="stretch", hide_index=True)
else:
    st.info("No insurer quality data.")
