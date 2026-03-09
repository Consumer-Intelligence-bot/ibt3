"""
Claims Intelligence Dashboard — Motor Insurance
Streamlit app connecting to Microsoft Fabric / Power BI semantic model.
"""

import datetime

import msal
import numpy as np
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Constants — Azure / Power BI credentials
# ---------------------------------------------------------------------------
TENANT_ID = "21c877f6-eb38-45b3-82dd-a27ccad676ce"
CLIENT_ID = "9cd99ce2-4c31-46e0-bb7c-eeb8e12e73d6"
WORKSPACE_ID = "db6f5221-fa36-48f7-8c14-259a1f570bc5"
DATASET_ID = "646c070f-5b4f-4ded-b0f9-4ae8a8b8a7ad"
SCOPE = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]

# ---------------------------------------------------------------------------
# Constants — CI Brand colours
# ---------------------------------------------------------------------------
CI_VIOLET = "#981D97"
CI_YELLOW = "#FFCD00"
CI_GREEN = "#48A23F"
CI_RED = "#F4364C"
CI_BLUE = "#5BC2E7"
CI_DARK = "#4D5153"
CI_LGREY = "#E9EAEB"
CI_WHITE = "#FFFFFF"

# ---------------------------------------------------------------------------
# Constants — Confidence / suppression thresholds
# ---------------------------------------------------------------------------
MIN_BASE_PUBLISHABLE = 50
MIN_BASE_INDICATIVE = 30
Z_95 = 1.96

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
CSS = f"""
<style>
html, body, [class*="css"] {{
    font-family: Verdana, sans-serif;
    color: {CI_DARK};
}}
.ci-header {{
    padding: 12px 0 16px 0;
    border-bottom: 3px solid {CI_VIOLET};
    margin-bottom: 24px;
}}
.ci-logo {{
    font-size: 20px;
    font-weight: bold;
    color: {CI_VIOLET};
}}
.section-title {{
    font-size: 15px;
    font-weight: bold;
    color: {CI_DARK};
    border-bottom: 2px solid {CI_LGREY};
    padding-bottom: 8px;
    margin-bottom: 16px;
}}
div[data-testid="stMetricValue"] {{
    font-size: 26px !important;
    font-weight: bold !important;
    color: {CI_VIOLET} !important;
}}
</style>
"""

# ---------------------------------------------------------------------------
# Authentication — MSAL device flow
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def get_token():
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    flow = app.initiate_device_flow(scopes=SCOPE)
    st.info(
        f"Sign in at **https://microsoft.com/devicelogin** "
        f"with code: **{flow['user_code']}**"
    )
    token = app.acquire_token_by_device_flow(flow)
    if "access_token" not in token:
        st.error("Authentication failed.")
        st.stop()
    return token["access_token"]


# ---------------------------------------------------------------------------
# DAX query helper
# ---------------------------------------------------------------------------


def run_dax(token: str, dax: str) -> pd.DataFrame:
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    if r.status_code != 200:
        st.error(f"Query failed: {r.text}")
        return pd.DataFrame()
    rows = r.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [c.split("[")[-1].replace("]", "") for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Table discovery — probe actual Power BI table names
# ---------------------------------------------------------------------------

# Known candidate names (Power BI models may use product-suffixed names)
_MAIN_CANDIDATES = ["MainData_Motor", "MainData", "MainData_Home", "FactClaims"]
_EAV_CANDIDATES = ["AllOtherData_Motor", "AllOtherData", "AllOtherData_Home"]


def _table_exists(token: str, table_name: str) -> bool:
    """Probe whether a table exists by running a minimal DAX query."""
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    dax = f"EVALUATE TOPN(1, '{table_name}')"
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    return r.status_code == 200


@st.cache_data(ttl=3600, show_spinner="Discovering model tables...")
def discover_tables(_token):
    """Probe candidate table names to find the actual MainData and AllOtherData tables."""
    main_table = None
    eav_table = None
    probed = []

    for candidate in _MAIN_CANDIDATES:
        probed.append(candidate)
        if _table_exists(_token, candidate):
            main_table = candidate
            break

    for candidate in _EAV_CANDIDATES:
        probed.append(candidate)
        if _table_exists(_token, candidate):
            eav_table = candidate
            break

    if main_table is None:
        st.error(
            f"Could not find a MainData table. "
            f"Probed: {probed}"
        )
        st.stop()

    return main_table, eav_table


# ---------------------------------------------------------------------------
# Data loading functions
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner="Loading months...")
def load_months(_token, main_table: str):
    dax = f"""
        EVALUATE
        SUMMARIZE(
            '{main_table}',
            '{main_table}'[RenewalYearMonth]
        )
        ORDER BY '{main_table}'[RenewalYearMonth] ASC
    """
    df = run_dax(_token, dax)
    if df.empty:
        return []
    return sorted(df["RenewalYearMonth"].dropna().unique().astype(int).tolist())


@st.cache_data(ttl=3600, show_spinner="Loading Q52 data...")
def load_q52(_token, start_month: int, end_month: int, main_table: str, eav_table: str):
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                '{main_table}'[CurrentCompany],
                "Q52_n", CALCULATE(
                    COUNTROWS('{eav_table}'),
                    '{eav_table}'[QuestionNumber] = "Q52"
                ),
                "Q52_mean", CALCULATE(
                    AVERAGEX('{eav_table}', VALUE('{eav_table}'[Scale])),
                    '{eav_table}'[QuestionNumber] = "Q52"
                ),
                "Q52_std", CALCULATE(
                    STDEVX.P('{eav_table}', VALUE('{eav_table}'[Scale])),
                    '{eav_table}'[QuestionNumber] = "Q52"
                )
            ),
            '{main_table}'[Claimants] = "Claimant",
            '{main_table}'[RenewalYearMonth] >= {start_month},
            '{main_table}'[RenewalYearMonth] <= {end_month}
        )
        ORDER BY [Q52_n] DESC
    """
    return run_dax(_token, dax)


@st.cache_data(ttl=3600, show_spinner="Loading Q53 data...")
def load_q53(_token, start_month: int, end_month: int, main_table: str, eav_table: str):
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                '{main_table}'[CurrentCompany],
                '{eav_table}'[Subject],
                '{eav_table}'[Ranking],
                "Q53_n", COUNTROWS('{eav_table}'),
                "Q53_mean", AVERAGEX('{eav_table}', VALUE('{eav_table}'[Scale])),
                "Q53_std", STDEVX.P('{eav_table}', VALUE('{eav_table}'[Scale]))
            ),
            '{eav_table}'[QuestionNumber] = "Q53",
            '{main_table}'[Claimants] = "Claimant",
            '{main_table}'[RenewalYearMonth] >= {start_month},
            '{main_table}'[RenewalYearMonth] <= {end_month}
        )
        ORDER BY '{main_table}'[CurrentCompany] ASC, '{eav_table}'[Ranking] ASC
    """
    return run_dax(_token, dax)


# ---------------------------------------------------------------------------
# Analytics functions
# ---------------------------------------------------------------------------


def confidence_interval(mean: float, std: float, n: int) -> tuple:
    """Returns (lower, upper) 95% CI for a mean on a 1-5 scale."""
    if n < 1 or std is None or np.isnan(std):
        return (None, None)
    margin = Z_95 * std / np.sqrt(n)
    return (round(mean - margin, 3), round(mean + margin, 3))


def confidence_tier(n: int, ci_width: float) -> str:
    """
    Returns confidence tier label.
    HIGH:         n >= 90 and CI width <= 0.25
    MEDIUM:       n >= 50 and CI width <= 0.35
    LOW:          n >= 30
    INSUFFICIENT: n < 30
    """
    if n < 30:
        return "INSUFFICIENT"
    if n < 50:
        return "LOW"
    if n >= 90 and ci_width <= 0.25:
        return "HIGH"
    if n >= 50 and ci_width <= 0.35:
        return "MEDIUM"
    return "LOW"


def assign_stars(insurer_mean: float, all_means: list) -> int:
    """
    Assigns 1-5 stars based on market position.
    Top 20% = 5 stars, next 20% = 4 stars, etc.
    """
    if not all_means or insurer_mean is None:
        return None
    sorted_means = sorted(all_means)
    n = len(sorted_means)
    rank = sum(m <= insurer_mean for m in sorted_means)
    percentile = rank / n
    if percentile >= 0.80:
        return 5
    elif percentile >= 0.60:
        return 4
    elif percentile >= 0.40:
        return 3
    elif percentile >= 0.20:
        return 2
    else:
        return 1


def can_show(n: int) -> bool:
    return n >= MIN_BASE_INDICATIVE


def format_month(yyyymm: int) -> str:
    """Convert integer YYYYMM to 'Mon YYYY' label."""
    y = yyyymm // 100
    m = yyyymm % 100
    try:
        return datetime.date(y, m, 1).strftime("%b %Y")
    except ValueError:
        return str(yyyymm)


def gap_colour(gap: float) -> str:
    """Return colour for a gap value."""
    if gap > 0.1:
        return CI_GREEN
    elif gap < -0.1:
        return CI_RED
    return CI_DARK


def tier_colour(tier: str) -> str:
    """Return colour for a confidence tier."""
    return {
        "HIGH": CI_GREEN,
        "MEDIUM": CI_BLUE,
        "LOW": CI_YELLOW,
        "INSUFFICIENT": CI_RED,
    }.get(tier, CI_DARK)


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main():
    st.set_page_config(
        page_title="Claims Intelligence",
        page_icon="📊",
        layout="wide",
    )
    st.markdown(CSS, unsafe_allow_html=True)

    # ---- Section 1: Header ----
    st.markdown(
        '<div class="ci-header">'
        '<span class="ci-logo">Consumer Intelligence</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<h1 style="color:{CI_VIOLET}; margin-top:0;">'
        "Claims Intelligence | Motor Insurance</h1>"
        '<p style="color:{CI_DARK}; margin-top:-12px;">Based on IBT survey data</p>',
        unsafe_allow_html=True,
    )

    # ---- Authentication ----
    token = get_token()

    # ---- Discover model tables ----
    main_table, eav_table = discover_tables(token)
    st.sidebar.caption(f"Model: {main_table} / {eav_table or '?'}")
    if eav_table is None:
        st.warning(
            "No AllOtherData table found. Q52/Q53 queries will fail."
        )

    # ---- Load months ----
    months = load_months(token, main_table)
    if len(months) < 2:
        st.warning("Fewer than 2 data months available. Cannot display dashboard.")
        st.stop()

    # ---- Section 2: Controls (sidebar) ----
    with st.sidebar:
        st.markdown(f'<div class="section-title">Controls</div>', unsafe_allow_html=True)

        # Product toggle
        st.selectbox("Product", ["Motor"], disabled=True, help="Home data not yet available")

        # Time window slider
        month_labels = {m: format_month(m) for m in months}
        default_start_idx = max(0, len(months) - 12)
        start_month, end_month = st.select_slider(
            "Time window",
            options=months,
            value=(months[default_start_idx], months[-1]),
            format_func=lambda x: month_labels.get(x, str(x)),
        )

    # ---- Load data for selected time window ----
    q52_df = load_q52(token, start_month, end_month, main_table, eav_table)
    q53_df = load_q53(token, start_month, end_month, main_table, eav_table)

    if q52_df.empty:
        st.warning("No data returned for this query.")
        st.stop()

    # Ensure numeric types
    for col in ["Q52_n", "Q52_mean", "Q52_std"]:
        if col in q52_df.columns:
            q52_df[col] = pd.to_numeric(q52_df[col], errors="coerce")

    # ---- Market averages (unfiltered — all eligible insurers) ----
    eligible = q52_df[q52_df["Q52_n"] >= MIN_BASE_INDICATIVE].copy()
    if eligible.empty:
        st.warning("No insurers meet the minimum sample size requirement.")
        st.stop()

    total_n = eligible["Q52_n"].sum()
    market_mean = (eligible["Q52_mean"] * eligible["Q52_n"]).sum() / total_n
    all_eligible_means = eligible["Q52_mean"].tolist()

    # ---- Insurer selector (sidebar) ----
    insurer_list = sorted(eligible["CurrentCompany"].dropna().unique().tolist())
    with st.sidebar:
        selected_insurer = st.selectbox("Insurer", insurer_list)

    # ---- Insurer data ----
    ins_row = q52_df[q52_df["CurrentCompany"] == selected_insurer]
    if ins_row.empty:
        st.warning(f"No data for {selected_insurer} in the selected period.")
        st.stop()

    ins_row = ins_row.iloc[0]
    ins_n = int(ins_row["Q52_n"])
    ins_mean = float(ins_row["Q52_mean"])
    ins_std = float(ins_row["Q52_std"]) if pd.notna(ins_row["Q52_std"]) else 0.0

    ci_lo, ci_hi = confidence_interval(ins_mean, ins_std, ins_n)
    ci_w = (ci_hi - ci_lo) if ci_lo is not None and ci_hi is not None else 999
    tier = confidence_tier(ins_n, ci_w)

    # ---- Section 3: Confidence Banner ----
    st.markdown('<div class="section-title">Data Confidence</div>', unsafe_allow_html=True)

    t_col = tier_colour(tier)
    st.markdown(
        f'<div style="padding:12px; border-left:4px solid {t_col}; '
        f'background:{CI_LGREY}; margin-bottom:16px;">'
        f"<strong>{selected_insurer}</strong> &mdash; "
        f"<strong style='color:{t_col}'>{tier}</strong> confidence &nbsp;|&nbsp; "
        f"<strong>{ins_n:,}</strong> claimant responses"
        f"</div>",
        unsafe_allow_html=True,
    )

    if not can_show(ins_n):
        st.error(
            f"Insufficient data for {selected_insurer}. "
            f"Minimum 30 claimants required. {ins_n} available in selected period."
        )
        st.stop()

    # ---- Section 4: Key Metrics Row ----
    st.markdown('<div class="section-title">Key Metrics</div>', unsafe_allow_html=True)

    gap = ins_mean - market_mean
    gap_str = f"{gap:+.1f}"
    g_col = gap_colour(gap)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overall Satisfaction", f"{ins_mean:.1f}")
    with col2:
        st.metric("Market Average", f"{market_mean:.1f}")
    with col3:
        st.markdown(
            f'<div style="text-align:center;">'
            f'<p style="font-size:14px; color:{CI_DARK}; margin-bottom:4px;">Gap to Market</p>'
            f'<p style="font-size:26px; font-weight:bold; color:{g_col};">{gap_str}</p>'
            f"</div>",
            unsafe_allow_html=True,
        )

    # ---- Section 5: Star Rating ----
    st.markdown('<div class="section-title">Star Rating</div>', unsafe_allow_html=True)

    stars = assign_stars(ins_mean, all_eligible_means)
    if stars is not None:
        filled = "★" * stars
        empty = "☆" * (5 - stars)
        st.markdown(
            f'<div style="text-align:center;">'
            f'<span style="font-size:48px; color:{CI_VIOLET};">{filled}{empty}</span>'
            f"</div>",
            unsafe_allow_html=True,
        )
        ci_text = ""
        if ci_lo is not None and ci_hi is not None:
            ci_text = f"95% CI: {ci_lo:.1f} – {ci_hi:.1f}"
        st.markdown(
            f'<p style="text-align:center; color:{CI_DARK}; font-size:13px;">'
            f"{ci_text} &nbsp;|&nbsp; "
            f"<span style='color:{t_col};'>{tier}</span> confidence</p>",
            unsafe_allow_html=True,
        )

    # ---- Section 6: Horizontal Bar Chart — All Insurers ----
    st.markdown(
        '<div class="section-title">Overall Satisfaction by Insurer</div>',
        unsafe_allow_html=True,
    )

    chart_df = eligible.sort_values("Q52_mean", ascending=True).copy()
    colours = [
        CI_VIOLET if c == selected_insurer else CI_BLUE
        for c in chart_df["CurrentCompany"]
    ]

    # Compute error bars
    chart_df["ci_lo"] = chart_df.apply(
        lambda r: confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[0]
        if pd.notna(r["Q52_std"]) else r["Q52_mean"],
        axis=1,
    )
    chart_df["ci_hi"] = chart_df.apply(
        lambda r: confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[1]
        if pd.notna(r["Q52_std"]) else r["Q52_mean"],
        axis=1,
    )
    chart_df["err_minus"] = chart_df["Q52_mean"] - chart_df["ci_lo"]
    chart_df["err_plus"] = chart_df["ci_hi"] - chart_df["Q52_mean"]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=chart_df["CurrentCompany"],
            x=chart_df["Q52_mean"],
            orientation="h",
            marker_color=colours,
            error_x=dict(
                type="data",
                symmetric=False,
                array=chart_df["err_plus"].tolist(),
                arrayminus=chart_df["err_minus"].tolist(),
                color=CI_DARK,
                thickness=1.5,
            ),
            text=[f"{v:.1f}" for v in chart_df["Q52_mean"]],
            textposition="outside",
            textfont=dict(family="Verdana", size=11, color=CI_DARK),
        )
    )
    fig.add_vline(
        x=market_mean,
        line_dash="dash",
        line_color=CI_DARK,
        annotation_text=f"Market avg: {market_mean:.2f}",
        annotation_position="top",
        annotation_font=dict(family="Verdana", size=11, color=CI_DARK),
    )
    bar_height = max(400, len(chart_df) * 30)
    fig.update_layout(
        height=bar_height,
        margin=dict(l=10, r=60, t=30, b=30),
        xaxis=dict(
            range=[1, 5.3],
            title="Mean satisfaction (1-5)",
            titlefont=dict(family="Verdana", size=12),
            tickfont=dict(family="Verdana"),
        ),
        yaxis=dict(tickfont=dict(family="Verdana", size=11)),
        font=dict(family="Verdana"),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # ---- Section 7: Q53 Diagnostic Statements ----
    if not q53_df.empty:
        st.markdown(
            '<div class="section-title">Claims Experience — Diagnostic Statements</div>',
            unsafe_allow_html=True,
        )

        # Ensure numeric types
        for col in ["Q53_n", "Q53_mean", "Q53_std", "Ranking"]:
            if col in q53_df.columns:
                q53_df[col] = pd.to_numeric(q53_df[col], errors="coerce")

        # Market averages per statement (weighted, across all eligible insurers)
        eligible_companies = set(eligible["CurrentCompany"].tolist())
        q53_eligible = q53_df[
            (q53_df["CurrentCompany"].isin(eligible_companies))
            & (q53_df["Q53_n"] >= MIN_BASE_INDICATIVE)
        ].copy()

        market_q53 = (
            q53_eligible.groupby("Subject")
            .apply(
                lambda g: pd.Series(
                    {
                        "market_mean": (g["Q53_mean"] * g["Q53_n"]).sum()
                        / g["Q53_n"].sum(),
                        "Ranking": g["Ranking"].iloc[0],
                    }
                )
            )
            .reset_index()
        )

        # Insurer Q53 data
        ins_q53 = q53_df[q53_df["CurrentCompany"] == selected_insurer].copy()

        if not ins_q53.empty and not market_q53.empty:
            diag = ins_q53.merge(market_q53, on="Subject", suffixes=("", "_mkt"))
            # Use insurer Ranking column; fall back to market if needed
            if "Ranking" in diag.columns:
                diag = diag.sort_values("Ranking")
            elif "Ranking_mkt" in diag.columns:
                diag = diag.sort_values("Ranking_mkt")

            # Filter out statements where insurer n < 30
            diag = diag[diag["Q53_n"] >= MIN_BASE_INDICATIVE]

            if not diag.empty:
                rows_html = []
                for _, row in diag.iterrows():
                    ins_m = row["Q53_mean"]
                    mkt_m = row["market_mean"]
                    g = ins_m - mkt_m
                    g_c = gap_colour(g)
                    rows_html.append(
                        f"<tr>"
                        f'<td style="padding:6px 10px;">{row["Subject"]}</td>'
                        f'<td style="padding:6px 10px; text-align:center;">{ins_m:.1f}</td>'
                        f'<td style="padding:6px 10px; text-align:center;">{mkt_m:.1f}</td>'
                        f'<td style="padding:6px 10px; text-align:center; '
                        f'color:{g_c}; font-weight:bold;">{g:+.1f}</td>'
                        f"</tr>"
                    )

                table_html = (
                    f'<table style="width:100%; border-collapse:collapse; '
                    f'font-family:Verdana; font-size:13px;">'
                    f"<thead><tr style='background:{CI_LGREY};'>"
                    f'<th style="text-align:left; padding:8px 10px;">Statement</th>'
                    f'<th style="text-align:center; padding:8px 10px;">{selected_insurer}</th>'
                    f'<th style="text-align:center; padding:8px 10px;">Market</th>'
                    f'<th style="text-align:center; padding:8px 10px;">Gap</th>'
                    f"</tr></thead><tbody>"
                    + "".join(rows_html)
                    + "</tbody></table>"
                )
                st.markdown(table_html, unsafe_allow_html=True)
            else:
                st.info("Insufficient data for diagnostic statements for this insurer.")
    else:
        st.warning("No Q53 diagnostic data returned.")

    # ---- Section 8: Footer ----
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(
        f'<div style="text-align:center; font-size:11px; color:{CI_DARK}; '
        f'padding:16px 0; border-top:1px solid {CI_LGREY};">'
        "Data: IBT Motor survey &nbsp;|&nbsp; Minimum base: n=30 &nbsp;|&nbsp; "
        "95% confidence intervals shown &nbsp;|&nbsp; "
        "&copy; Consumer Intelligence 2026"
        "</div>",
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
