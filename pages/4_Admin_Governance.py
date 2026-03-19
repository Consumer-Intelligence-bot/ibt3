"""
Admin / Governance — Internal page.
Data quality monitoring, confidence threshold management.
Enhanced per Spec Section 8.
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
    TREND_NOISE_THRESHOLD, CI_MAGENTA, CI_LIGHT_GREY,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
)
from lib.db import clear_data, load_metadata
from lib.state import format_year_month, get_ss_data, init_ss_data

# ---------------------------------------------------------------------------
# Page-level CSS: Verdana font, CI brand colours, table highlights
# ---------------------------------------------------------------------------
st.markdown(
    f"""
    <style>
    html, body, [class*="css"] {{
        font-family: Verdana, sans-serif;
        color: {CI_GREY};
    }}
    div[data-testid="stMetricValue"] {{
        font-size: 26px !important;
        font-weight: bold !important;
        color: {CI_MAGENTA} !important;
    }}
    .alert-badge {{
        display: inline-block;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 12px;
        font-weight: bold;
        margin-top: 4px;
    }}
    .alert-red {{
        background-color: {CI_RED};
        color: white;
    }}
    .alert-yellow {{
        background-color: {CI_YELLOW};
        color: {CI_GREY};
    }}
    .alert-green {{
        background-color: {CI_GREEN};
        color: white;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.header("Admin / Governance")
st.caption("Internal page \u2014 not visible to clients")

# ---------------------------------------------------------------------------
# Data Management — Refresh from Power BI
# ---------------------------------------------------------------------------

st.subheader("Data Management")

cached_start = load_metadata("start_month")
cached_end = load_metadata("end_month")
cache_info = f"Cached period: {format_year_month(int(cached_start))} to {format_year_month(int(cached_end))}" if cached_start and cached_end else "No cached data"

col_info, col_action = st.columns([3, 1])
with col_info:
    st.info(cache_info)
with col_action:
    refresh_clicked = st.button("Refresh from Power BI", type="primary")

if refresh_clicked:
    with st.spinner("Authenticating and pulling data from Power BI. This may take several minutes..."):
        try:
            from lib.powerbi import get_token, get_main_table, get_other_table, load_months

            # Clear existing caches (Streamlit + DuckDB)
            clear_data()
            st.cache_data.clear()

            token = get_token()

            # Discover tables
            main_table = get_main_table(token, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
            other_table = get_other_table(token, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
            home_main_table = get_main_table(token, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)
            home_other_table = get_other_table(token, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)

            # Discover months
            motor_months = load_months(token, main_table, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
            home_months = load_months(token, home_main_table, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)
            months = sorted(set(motor_months) | set(home_months))

            if len(months) < 2:
                st.error("Fewer than 2 data months available from Power BI.")
            else:
                start_month = months[max(0, len(months) - 12)]
                end_month = months[-1]

                # Store for Claims page
                st.session_state["token"] = token
                st.session_state["main_table"] = main_table
                st.session_state["other_table"] = other_table
                st.session_state["home_main_table"] = home_main_table
                st.session_state["home_other_table"] = home_other_table
                st.session_state["start_month"] = start_month
                st.session_state["end_month"] = end_month

                init_ss_data(token, start_month, end_month, main_table, other_table,
                             home_main_table, home_other_table)
                st.session_state["data_loaded"] = True
                st.session_state["cached_start_month"] = start_month
                st.session_state["cached_end_month"] = end_month

                st.success(f"Data refreshed: {format_year_month(start_month)} to {format_year_month(end_month)}")
                st.rerun()
        except Exception as e:
            st.error(f"Failed to refresh data: {e}")

st.markdown("---")

df_motor, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded. Click **Refresh from Power BI** above to pull data.")
    st.stop()

# ---- Summary KPIs (Spec 8.2) ----
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
    if eligible < 15:
        st.markdown(
            f'<span class="alert-badge alert-red">⚠ &lt;15 eligible</span>',
            unsafe_allow_html=True,
        )
with col3:
    st.metric("Suppressed", f"{suppressed:,}")
    if suppressed > 10:
        st.markdown(
            f'<span class="alert-badge alert-yellow">⚠ &gt;10 suppressed</span>',
            unsafe_allow_html=True,
        )
with col4:
    st.metric("Data Freshness", f"{freshness} days" if freshness else "N/A")
    if freshness and freshness > 45:
        st.markdown(
            f'<span class="alert-badge alert-red">⚠ &gt;45 days old</span>',
            unsafe_allow_html=True,
        )

# ---- Confidence Thresholds ----
st.subheader("Confidence Thresholds")

thresholds = pd.DataFrame([
    {"Metric Type": "Retention / Shopping / Switching", "Threshold": "Confidence Interval Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_RATE, "Description": "Max 95% posterior confidence interval width for client output"},
    {"Metric Type": "Retention / Shopping / Switching", "Threshold": "Confidence Interval Width: Indicative", "Value": CI_WIDTH_INDICATIVE_RATE, "Description": "Max confidence interval width for internal indicative results"},
    {"Metric Type": "Reason Percentages", "Threshold": "Confidence Interval Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_REASON, "Description": "Reason %s are noisier; wider threshold"},
    {"Metric Type": "Reason Percentages", "Threshold": "Confidence Interval Width: Indicative", "Value": CI_WIDTH_INDICATIVE_REASON, "Description": "Internal indicative for reason analysis"},
    {"Metric Type": "Awareness Rates", "Threshold": "Confidence Interval Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_AWARENESS, "Description": "Same as binary rate metrics at insurer level"},
    {"Metric Type": "Awareness Rates", "Threshold": "Confidence Interval Width: Indicative", "Value": CI_WIDTH_INDICATIVE_AWARENESS, "Description": "Internal indicative for awareness"},
    {"Metric Type": "NPS (Q40b)", "Threshold": "Minimum n", "Value": float(NPS_MIN_N), "Description": "NPS uses n floor, not confidence interval width"},
    {"Metric Type": "All metrics", "Threshold": "Absolute n floor", "Value": float(SYSTEM_FLOOR_N), "Description": "Floor below which no result shown (hardcoded)"},
])

edited = st.data_editor(thresholds, width="stretch", num_rows="fixed", key="threshold_editor")

# ---- Governance Parameters (Spec 8.6 — read-only) ----
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

# ---- Market-Level CI (Spec 8.4) ----
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
        st.metric(f"Market {label} Confidence Interval", f"{ci_w:.0f}pp" if ci_w else "N/A")
        if alert:
            st.warning(f"Alert: > {MARKET_CI_ALERT_THRESHOLD}pp")

# ---- QC Flags: Q4=Q39 ----
st.subheader("QC Flags: Q4=Q39")
if "Q4" in df_motor.columns and "Q39" in df_motor.columns and "RenewalYearMonth" in df_motor.columns:
    switchers = df_motor[df_motor["IsSwitcher"]][["UniqueID", "RenewalYearMonth", "Q4", "Q39"]].copy()
    if not switchers.empty:
        switchers["flagged"] = switchers["Q4"] == switchers["Q39"]
        by_month = switchers.groupby("RenewalYearMonth").agg(
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

# ---- Respondents by Month (Spec 8.5) ----
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

# ---- Insurer Data Quality (Spec 8.3 — enhanced) ----
st.subheader("Insurer Data Quality")

# Confidence icon mapping
_CONF_ICONS = {
    "HIGH": "\u2705",        # green check
    "MEDIUM": "\U0001F7E1",  # yellow circle
    "LOW": "\U0001F7E0",     # orange circle
    "INSUFFICIENT": "\u274C", # red cross
}


def _n_highlight(val: int) -> str:
    """Return background colour CSS for sample size cells."""
    if val < 50:
        return f"background-color: {CI_RED}; color: white"
    elif val < 100:
        return f"background-color: {CI_YELLOW}; color: {CI_GREY}"
    return ""


def _ci_highlight(val: float) -> str:
    """Return background colour CSS for CI Width cells."""
    if val > 12.0:
        return f"background-color: {CI_RED}; color: white"
    elif val > 8.0:
        return f"background-color: {CI_YELLOW}; color: {CI_GREY}"
    return ""


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

    # Detect active issues / flags
    issues = []
    if n < MIN_BASE_PUBLISHABLE:
        issues.append(f"n<{MIN_BASE_PUBLISHABLE}")
    if ci_w > CI_WIDTH_INDICATIVE_RATE:
        issues.append("CI too wide")
    if conf.label.value == "INSUFFICIENT":
        issues.append("Insufficient")

    quality_rows.append({
        "Insurer": ins,
        "n": n,
        "Confidence Interval Width (pp)": round(ci_w, 0),
        "Confidence": f"{_CONF_ICONS.get(conf.label.value, '')} {conf.label.value}",
        "Smoothing Weight": f"{smoothed['weight']:.0%}",
        "Issues": ", ".join(issues) if issues else "\u2014",
    })

if quality_rows:
    df_quality = pd.DataFrame(quality_rows)

    # Apply colour-coded styling via pandas Styler
    def _style_quality(row: pd.Series) -> list[str]:
        """Row-wise styler returning CSS strings per cell."""
        styles = [""] * len(row)
        col_names = list(row.index)

        # n column highlighting
        n_idx = col_names.index("n")
        n_val = row["n"]
        if n_val < 50:
            styles[n_idx] = f"background-color: {CI_RED}; color: white"
        elif n_val < 100:
            styles[n_idx] = f"background-color: {CI_YELLOW}; color: {CI_GREY}"

        # CI Width column highlighting
        ci_idx = col_names.index("Confidence Interval Width (pp)")
        ci_val = row["Confidence Interval Width (pp)"]
        if ci_val > 12.0:
            styles[ci_idx] = f"background-color: {CI_RED}; color: white"
        elif ci_val > 8.0:
            styles[ci_idx] = f"background-color: {CI_YELLOW}; color: {CI_GREY}"

        return styles

    styled = (
        df_quality.style
        .apply(_style_quality, axis=1)
        .set_properties(**{"font-family": "Verdana, sans-serif"})
    )
    st.dataframe(styled, width="stretch", hide_index=True)
else:
    st.info("No insurer quality data.")
