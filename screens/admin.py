"""
Admin / Governance screen.

Ported from pages/4_Admin_Governance.py. Handles data refresh from Power BI,
confidence thresholds, data quality monitoring.
"""

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
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
    PET_WORKSPACE_ID, PET_DATASET_ID,
)
from lib.db import clear_data, has_data, load_metadata
from lib.state import format_year_month, get_ss_data, init_ss_data


def render(filters: dict):
    """Render the Admin / Governance screen."""
    st.header("Admin / Governance")
    st.caption("Internal page \u2014 not visible to clients")

    # --- Data Management ---
    st.subheader("Data Management")

    cached_start = load_metadata("start_month")
    cached_end = load_metadata("end_month")
    if cached_start and cached_end:
        cache_info = f"Cached period: {format_year_month(int(cached_start))} to {format_year_month(int(cached_end))}"
    elif has_data("df_motor"):
        cache_info = "Cached data available (period metadata missing)"
    else:
        cache_info = "No cached data"

    col_info, col_action = st.columns([3, 1])
    with col_info:
        st.info(cache_info)
    with col_action:
        refresh_clicked = st.button("Refresh from Power BI", type="primary", key="admin_refresh")

    if refresh_clicked:
        audit_container = st.container()
        audit_container.subheader("Refresh Audit Log")
        audit_lines = []

        def _audit_log(msg):
            from datetime import datetime as _dt
            ts = _dt.now().strftime("%H:%M:%S")
            audit_lines.append((ts, msg))
            audit_container.code(
                "\n".join(f"{t} {m}" for t, m in audit_lines),
                language="text",
            )

        with st.spinner("Authenticating and pulling data from Power BI. This may take several minutes..."):
            try:
                _audit_log("Starting refresh...")
                from lib.powerbi import (
                    get_token, get_main_table, get_other_table,
                    load_months, load_pet_quarters,
                )

                _audit_log("Clearing DuckDB cache and Streamlit cache")
                clear_data()
                st.cache_data.clear()

                _audit_log("Authenticating with Power BI (MSAL device flow)")
                token = get_token()
                _audit_log("Auth OK \u2014 token acquired")

                _audit_log("Discovering Motor tables...")
                main_table = get_main_table(token, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
                other_table = get_other_table(token, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
                _audit_log(f"Motor tables: main={main_table}, other={other_table}")

                _audit_log("Discovering Home tables...")
                home_main_table = get_main_table(token, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)
                home_other_table = get_other_table(token, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)
                _audit_log(f"Home tables: main={home_main_table}, other={home_other_table}")

                _audit_log("Discovering available months...")
                motor_months = load_months(token, main_table, workspace_id=MOTOR_WORKSPACE_ID, dataset_id=MOTOR_DATASET_ID)
                home_months = load_months(token, home_main_table, workspace_id=HOME_WORKSPACE_ID, dataset_id=HOME_DATASET_ID)
                months = sorted(set(motor_months) | set(home_months))
                _audit_log(f"Motor months: {len(motor_months)}, Home months: {len(home_months)}, Combined: {len(months)}")
                if months:
                    _audit_log(f"Range: {months[0]} to {months[-1]}")

                _audit_log("Discovering Pet quarters...")
                pet_quarters = load_pet_quarters(token, workspace_id=PET_WORKSPACE_ID, dataset_id=PET_DATASET_ID)
                _audit_log(f"Pet quarters: {pet_quarters}")

                if len(months) < 2:
                    _audit_log("FAIL: fewer than 2 data months available")
                    st.error("Fewer than 2 data months available from Power BI.")
                else:
                    start_month = months[max(0, len(months) - 12)]
                    end_month = months[-1]
                    _audit_log(f"Loading window: {start_month} to {end_month}")

                    st.session_state["token"] = token
                    st.session_state["main_table"] = main_table
                    st.session_state["other_table"] = other_table
                    st.session_state["home_main_table"] = home_main_table
                    st.session_state["home_other_table"] = home_other_table
                    st.session_state["start_month"] = start_month
                    st.session_state["end_month"] = end_month

                    init_ss_data(
                        token, start_month, end_month, main_table, other_table,
                        home_main_table, home_other_table,
                        pet_quarters=pet_quarters,
                        log_fn=_audit_log,
                    )
                    st.session_state["data_loaded"] = True
                    st.session_state["cached_start_month"] = start_month
                    st.session_state["cached_end_month"] = end_month

                    _audit_log("REFRESH COMPLETE \u2014 all data saved")
                    st.success(f"Data refreshed: {format_year_month(start_month)} to {format_year_month(end_month)}")
            except Exception as e:
                import traceback
                _audit_log(f"EXCEPTION: {e}")
                _audit_log(traceback.format_exc())
                st.error(f"Failed to refresh data: {e}")

    st.markdown("---")

    df_motor, dimensions = get_ss_data()
    if df_motor.empty:
        st.warning("No S&S data loaded. Click **Refresh from Power BI** above to pull data.")
        return

    # --- Summary KPIs ---
    total = len(df_motor)
    all_insurers = dimensions.get("DimInsurer", pd.DataFrame())
    insurer_list = all_insurers["Insurer"].dropna().astype(str).tolist() if not all_insurers.empty else []
    eligible = sum(
        1 for ins in insurer_list
        if len(df_motor[df_motor["CurrentCompany"] == ins]) >= MIN_BASE_PUBLISHABLE
    )
    suppressed = len(insurer_list) - eligible

    # Data freshness
    freshness = None
    if "RenewalYearMonth" in df_motor.columns:
        from datetime import datetime, timezone
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
            st.markdown('<span class="alert-badge alert-red">\u26A0 &lt;15 eligible</span>', unsafe_allow_html=True)
    with col3:
        st.metric("Suppressed", f"{suppressed:,}")
        if suppressed > 10:
            st.markdown('<span class="alert-badge alert-yellow">\u26A0 &gt;10 suppressed</span>', unsafe_allow_html=True)
    with col4:
        st.metric("Data Freshness", f"{freshness} days" if freshness else "N/A")
        if freshness and freshness > 45:
            st.markdown('<span class="alert-badge alert-red">\u26A0 &gt;45 days old</span>', unsafe_allow_html=True)

    # --- Confidence Thresholds ---
    st.subheader("Confidence Thresholds")
    thresholds = pd.DataFrame([
        {"Metric Type": "Retention / Shopping / Switching", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_RATE},
        {"Metric Type": "Retention / Shopping / Switching", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_RATE},
        {"Metric Type": "Reason Percentages", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_REASON},
        {"Metric Type": "Reason Percentages", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_REASON},
        {"Metric Type": "Awareness Rates", "Threshold": "CI Width: Publishable", "Value": CI_WIDTH_PUBLISHABLE_AWARENESS},
        {"Metric Type": "Awareness Rates", "Threshold": "CI Width: Indicative", "Value": CI_WIDTH_INDICATIVE_AWARENESS},
        {"Metric Type": "NPS (Q40b)", "Threshold": "Minimum n", "Value": float(NPS_MIN_N)},
        {"Metric Type": "All metrics", "Threshold": "Absolute n floor", "Value": float(SYSTEM_FLOOR_N)},
    ])
    st.data_editor(thresholds, use_container_width=True, num_rows="fixed", key="admin_threshold_editor")

    # --- Governance Parameters ---
    st.subheader("Governance Parameters")
    market_ret = df_motor["IsRetained"].mean() if "IsRetained" in df_motor.columns else 0.5
    params = pd.DataFrame([
        {"Parameter": "Minimum base (publishable)", "Value": str(MIN_BASE_PUBLISHABLE)},
        {"Parameter": "Minimum base (indicative)", "Value": "30"},
        {"Parameter": "Minimum base (flow cell)", "Value": str(MIN_BASE_FLOW_CELL)},
        {"Parameter": "Bayesian prior strength", "Value": str(PRIOR_STRENGTH)},
        {"Parameter": "Bayesian prior mean", "Value": f"{market_ret:.1%}"},
        {"Parameter": "Confidence interval", "Value": f"{CONFIDENCE_LEVEL:.0%}"},
        {"Parameter": "Trend noise threshold", "Value": f"{TREND_NOISE_THRESHOLD:.1f}pp"},
    ])
    st.dataframe(params, use_container_width=True, hide_index=True)

    # --- Market-Level CI ---
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
            st.metric(f"Market {label} CI", f"{ci_w:.0f}pp" if ci_w else "N/A")
            if alert:
                st.warning(f"Alert: > {MARKET_CI_ALERT_THRESHOLD}pp")

    # --- QC Flags: Q4=Q39 ---
    st.subheader("QC Flags: Q4=Q39")
    if "Q4" in df_motor.columns and "Q39" in df_motor.columns and "RenewalYearMonth" in df_motor.columns:
        switchers = df_motor[df_motor["IsSwitcher"]][["UniqueID", "RenewalYearMonth", "Q4", "Q39"]].copy()
        if not switchers.empty:
            switchers["flagged"] = switchers["Q4"] == switchers["Q39"]
            by_month_qc = switchers.groupby("RenewalYearMonth").agg(
                total=("UniqueID", "count"), flagged=("flagged", "sum"),
            ).reset_index()
            by_month_qc["flag_rate"] = by_month_qc["flagged"] / by_month_qc["total"]
            by_month_qc["month_label"] = by_month_qc["RenewalYearMonth"].apply(format_year_month)

            fig_qc = go.Figure()
            fig_qc.add_trace(go.Bar(
                x=by_month_qc["month_label"], y=by_month_qc["flag_rate"],
                marker_color=CI_GREY,
                text=[f"{r:.1%}" for r in by_month_qc["flag_rate"]],
                textposition="outside",
            ))
            fig_qc.add_hline(y=0.02, line_dash="dash", line_color=CI_RED, annotation_text="2% threshold")
            fig_qc.update_layout(
                height=250, margin=dict(t=30), yaxis_tickformat=".1%",
                font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white",
            )
            st.plotly_chart(fig_qc, use_container_width=True)
        else:
            st.info("No switcher data for QC flags.")
    else:
        st.info("No QC flag data available.")

    # --- Respondents by Month ---
    st.subheader("Respondents by Month")
    by_month = df_motor.groupby("RenewalYearMonth").size().reset_index(name="count")
    by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)
    fig_dist = go.Figure(go.Bar(x=by_month["month_label"], y=by_month["count"], marker_color=CI_GREY))
    fig_dist.update_layout(
        height=250, margin=dict(t=10), font=dict(family="Verdana"),
        plot_bgcolor="white", paper_bgcolor="white",
    )
    st.plotly_chart(fig_dist, use_container_width=True)

    # --- Data Validation ---
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
        st.dataframe(pd.DataFrame(val_results), use_container_width=True, hide_index=True)

    # --- Insurer Data Quality ---
    st.subheader("Insurer Data Quality")

    _CONF_ICONS = {"HIGH": "\u2705", "MEDIUM": "\U0001F7E1", "LOW": "\U0001F7E0", "INSUFFICIENT": "\u274C"}

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
            "CI Width (pp)": round(ci_w, 0),
            "Confidence": f"{_CONF_ICONS.get(conf.label.value, '')} {conf.label.value}",
            "Smoothing Weight": f"{smoothed['weight']:.0%}",
            "Issues": ", ".join(issues) if issues else "\u2014",
        })

    if quality_rows:
        df_quality = pd.DataFrame(quality_rows)

        def _style_quality(row: pd.Series) -> list[str]:
            styles = [""] * len(row)
            col_names = list(row.index)
            n_idx = col_names.index("n")
            n_val = row["n"]
            if n_val < 50:
                styles[n_idx] = f"background-color: {CI_RED}; color: white"
            elif n_val < 100:
                styles[n_idx] = f"background-color: {CI_YELLOW}; color: {CI_GREY}"
            ci_idx = col_names.index("CI Width (pp)")
            ci_val = row["CI Width (pp)"]
            if ci_val > 12.0:
                styles[ci_idx] = f"background-color: {CI_RED}; color: white"
            elif ci_val > 8.0:
                styles[ci_idx] = f"background-color: {CI_YELLOW}; color: {CI_GREY}"
            return styles

        styled = df_quality.style.apply(_style_quality, axis=1).set_properties(**{"font-family": "Verdana, sans-serif"})
        st.dataframe(styled, use_container_width=True, hide_index=True)
