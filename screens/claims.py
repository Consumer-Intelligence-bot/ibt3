"""
Screen 8: Claims Intelligence.

Ported from pages/7_Claims_Intelligence.py. Satisfaction analysis from Q52/Q53,
star ratings, CI bands, journey statements, AI narrative.
Pet guard: no claims data for Pet.
"""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.narrative_engine import generate_screen_narrative
from lib.chart_export import apply_export_metadata, confidence_tooltip
from lib.components.kpi_cards import kpi_card
from lib.components.narrative_panel import render_narrative_panel
from lib.config import (
    CI_BLUE, CI_DARK, CI_GREEN, CI_GREY, CI_LGREY, CI_LIGHT_GREY,
    CI_MAGENTA, CI_RED, CI_VIOLET, CI_WHITE,
    MIN_BASE_INDICATIVE, SISTER_BRANDS, Z_95,
)
from lib.formatting import FONT, section_divider
from lib.narrative import generate_claims_narrative
from lib.state import format_month


def _confidence_interval(mean, std, n):
    if n < 1 or std is None or np.isnan(std):
        return (None, None)
    margin = Z_95 * std / np.sqrt(n)
    return (round(mean - margin, 3), round(mean + margin, 3))


def _confidence_tier(n, ci_width):
    if n < 30:
        return "INSUFFICIENT"
    if n < 50:
        return "LOW"
    if n >= 90 and ci_width <= 0.25:
        return "HIGH"
    if n >= 50 and ci_width <= 0.35:
        return "MEDIUM"
    return "LOW"


def _assign_stars(insurer_mean, all_means):
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
    return 1


def _gap_colour(gap):
    if gap > 0.1:
        return CI_GREEN
    elif gap < -0.1:
        return CI_RED
    return CI_DARK


def _tier_colour(tier):
    return {"HIGH": CI_GREEN, "MEDIUM": CI_BLUE, "LOW": "#FFCD00", "INSUFFICIENT": CI_RED}.get(tier, CI_DARK)


def render(filters: dict):
    """Render the Claims Intelligence screen."""
    product = filters["product"]

    st.subheader(f"Claims Intelligence: {product}")

    # Pet guard
    if product == "Pet":
        st.info("Claims data is not available for Pet insurance.")
        return

    # Get cached claims data
    product_key = product.lower()
    q52_key = f"claims_q52_{product_key}"
    q53_key = f"claims_q53_{product_key}"

    q52_df = st.session_state.get(q52_key, pd.DataFrame())
    q53_df = st.session_state.get(q53_key, pd.DataFrame())

    start_month = st.session_state.get("start_month")
    end_month = st.session_state.get("end_month")

    if q52_df.empty:
        st.warning(
            "No claims data cached. Go to **Admin / Governance** and click "
            "**Refresh from Power BI** to pull data."
        )
        return

    period_text = f"{format_month(start_month)} to {format_month(end_month)}" if start_month and end_month else "All cached data"

    for col in ["Q52_n", "Q52_mean", "Q52_std"]:
        if col in q52_df.columns:
            q52_df[col] = pd.to_numeric(q52_df[col], errors="coerce")

    # Market averages
    eligible = q52_df[q52_df["Q52_n"] >= MIN_BASE_INDICATIVE].copy()
    if eligible.empty:
        st.warning("No insurers meet the minimum sample size requirement.")
        return

    total_n = eligible["Q52_n"].sum()
    market_mean = (eligible["Q52_mean"] * eligible["Q52_n"]).sum() / total_n
    all_eligible_means = eligible["Q52_mean"].tolist()

    # Use insurer from filters, or show market overview
    insurer = filters["insurer"]
    insurer_list = sorted(eligible["CurrentCompany"].dropna().unique().tolist())

    if not insurer:
        # Market overview: show bar chart of all insurers
        _render_market_overview(eligible, market_mean, total_n, period_text, product)
        return

    # Check insurer has claims data
    ins_row = q52_df[q52_df["CurrentCompany"] == insurer]
    if ins_row.empty:
        st.warning(f"No claims data for {insurer}.")
        return

    ins_row = ins_row.iloc[0]
    ins_n = int(ins_row["Q52_n"])
    ins_mean = float(ins_row["Q52_mean"])
    ins_std = float(ins_row["Q52_std"]) if pd.notna(ins_row["Q52_std"]) else 0.0

    ci_lo, ci_hi = _confidence_interval(ins_mean, ins_std, ins_n)
    ci_w = (ci_hi - ci_lo) if ci_lo is not None and ci_hi is not None else 999
    tier = _confidence_tier(ins_n, ci_w)
    gap = ins_mean - market_mean
    stars = _assign_stars(ins_mean, all_eligible_means)

    sorted_desc = sorted(all_eligible_means, reverse=True)
    rank = sorted_desc.index(ins_mean) + 1 if ins_mean in sorted_desc else None
    total_insurers = len(sorted_desc)
    index_score = (ins_mean / market_mean * 100) if market_mean > 0 else None

    if ins_n < MIN_BASE_INDICATIVE:
        st.warning(f"Insufficient data for {insurer}. Minimum 30 claimants required.")
        return

    # Period banner
    st.markdown(
        f'<div style="background:{CI_LIGHT_GREY}; padding:10px 16px; border-radius:4px; '
        f'font-family:{FONT}; font-size:13px; color:{CI_GREY}; margin-bottom:16px;">'
        f"<b>{insurer}</b> &nbsp;|&nbsp; {product} &nbsp;|&nbsp; {period_text} "
        f"&nbsp;|&nbsp; n={ins_n:,}"
        f"</div>",
        unsafe_allow_html=True,
    )

    # Sister brand note
    sisters = SISTER_BRANDS.get(insurer)
    if sisters:
        st.markdown(
            f'<div style="background:white; border-left:4px solid {CI_BLUE}; '
            f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:13px; '
            f'color:{CI_GREY};">Note: {insurer} shares claims handling with {", ".join(sisters)}.</div>',
            unsafe_allow_html=True,
        )

    # Confidence banner
    t_col = _tier_colour(tier)
    st.markdown(
        f'<div style="padding:12px; border-left:4px solid {t_col}; '
        f'background:{CI_LGREY}; margin-bottom:16px; font-family:{FONT}; font-size:13px;">'
        f"<strong>{insurer}</strong> &mdash; "
        f"<strong style='color:{t_col}'>{tier}</strong> confidence &nbsp;|&nbsp; "
        f"<strong>{ins_n:,}</strong> claimant responses</div>",
        unsafe_allow_html=True,
    )

    # Key metrics
    section_divider("Key Metrics")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        kpi_card("Overall Satisfaction", f"{ins_mean:.2f}", "Q52 mean (1-5)", CI_VIOLET)
    with col2:
        kpi_card("Market Average", f"{market_mean:.2f}", f"n={int(total_n):,}", CI_GREY)
    with col3:
        g_col = _gap_colour(gap)
        kpi_card("Gap to Market", f"{gap:+.2f}", f"Rank {rank} of {total_insurers}" if rank else "", g_col)
    with col4:
        idx_col = CI_GREEN if index_score and index_score > 100 else CI_RED if index_score and index_score < 100 else CI_GREY
        kpi_card("Index vs Market", f"{index_score:.0f}" if index_score else "\u2014", "100 = market average", idx_col)

    # Star rating
    section_divider("Star Rating")
    if stars is not None:
        filled = "\u2605" * stars
        empty = "\u2606" * (5 - stars)
        star_desc = {5: "Top quintile", 4: "Second quintile", 3: "Middle quintile", 2: "Fourth quintile", 1: "Bottom quintile"}
        ci_text = f"95% CI: {ci_lo:.2f} \u2013 {ci_hi:.2f}" if ci_lo and ci_hi else ""

        st.markdown(
            f'<div style="text-align:center; font-family:{FONT};">'
            f'<span style="font-size:48px; color:{CI_VIOLET};">{filled}{empty}</span>'
            f'<div style="font-size:13px; color:{CI_GREY}; margin-top:6px;">'
            f'{star_desc.get(stars, "")} &nbsp;|&nbsp; {ci_text}</div></div>',
            unsafe_allow_html=True,
        )

    # All insurers bar chart
    section_divider("Overall Satisfaction by Insurer")
    _render_insurer_bar_chart(eligible, insurer, market_mean, total_n, period_text)

    # Q53 Journey Statements
    if not q53_df.empty:
        _render_q53_journey(q53_df, eligible, insurer, market_mean, period_text)

    # AI Narrative (claims-specific via lib/narrative.py, plus screen narrative)
    section_divider("AI Claims Narrative")
    diagnostics = _get_diagnostics(q53_df, eligible, insurer)
    narrative = generate_claims_narrative(insurer, ins_mean, market_mean, gap, stars, diagnostics)
    render_narrative_panel(narrative, "claims")

    # Also try screen-level narrative engine as fallback
    if narrative is None:
        screen_narrative = generate_screen_narrative("claims", {
            "insurer": insurer,
            "product": product,
            "satisfaction": ins_mean,
            "mkt_satisfaction": market_mean,
            "stars": stars or 0,
            "gap": gap,
        })
        render_narrative_panel(screen_narrative, "claims_fallback")

    # --- Cross-screen links ---
    col1, col2 = st.columns(2)
    with col1:
        if st.button("View Satisfaction & Loyalty", key="claims_to_satisfaction"):
            from lib.state import navigate_to
            navigate_to("satisfaction")
    with col2:
        if st.button("View Switching & Flows", key="claims_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")

    # Footer
    st.markdown("---")
    st.caption(f"Claims Intelligence | {insurer} | {product} | {period_text} | n={ins_n:,}")


def _render_market_overview(eligible, market_mean, total_n, period_text, product):
    """Show all-insurer bar chart when no insurer selected."""
    st.info("Select an insurer from the sidebar for detailed claims analysis. Showing market overview below.")

    section_divider("Overall Satisfaction by Insurer")
    _render_insurer_bar_chart(eligible, None, market_mean, total_n, period_text)

    st.markdown("---")
    st.caption(f"Claims Intelligence | Market | {product} | {period_text} | n={int(total_n):,}")


def _render_insurer_bar_chart(eligible, selected_insurer, market_mean, total_n, period_text):
    """Horizontal bar chart of all insurers with CI bands."""
    chart_df = eligible.sort_values("Q52_mean", ascending=True).copy()
    colours = [CI_VIOLET if c == selected_insurer else CI_BLUE for c in chart_df["CurrentCompany"]]

    chart_df["ci_lo"] = chart_df.apply(
        lambda r: _confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[0]
        if pd.notna(r["Q52_std"]) else r["Q52_mean"], axis=1,
    )
    chart_df["ci_hi"] = chart_df.apply(
        lambda r: _confidence_interval(r["Q52_mean"], r["Q52_std"], int(r["Q52_n"]))[1]
        if pd.notna(r["Q52_std"]) else r["Q52_mean"], axis=1,
    )
    chart_df["err_minus"] = chart_df["Q52_mean"] - chart_df["ci_lo"]
    chart_df["err_plus"] = chart_df["ci_hi"] - chart_df["Q52_mean"]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=chart_df["CurrentCompany"],
        x=chart_df["Q52_mean"],
        orientation="h",
        marker_color=colours,
        error_x=dict(
            type="data", symmetric=False,
            array=chart_df["err_plus"].tolist(),
            arrayminus=chart_df["err_minus"].tolist(),
            color=CI_DARK, thickness=1.5, width=3,
        ),
        text=[f"{v:.2f}" for v in chart_df["Q52_mean"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Satisfaction: %{x:.2f}<br>n=%{customdata:,}<extra></extra>",
        customdata=chart_df["Q52_n"].astype(int),
    ))
    fig.add_vline(x=market_mean, line_dash="dash", line_color=CI_DARK,
                  annotation_text=f"Market avg: {market_mean:.2f}")

    fig.update_layout(
        height=max(400, len(chart_df) * 30),
        margin=dict(l=10, r=60, t=30, b=40),
        xaxis=dict(range=[1, 5.3], title="Mean satisfaction (1-5)", gridcolor=CI_LIGHT_GREY),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE, paper_bgcolor=CI_WHITE,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_q53_journey(q53_df, eligible, insurer, market_mean, period_text):
    """Q53 journey statement detail table."""
    for col in ["Q53_n", "Q53_mean", "Q53_std"]:
        if col in q53_df.columns:
            q53_df[col] = pd.to_numeric(q53_df[col], errors="coerce")

    eligible_companies = set(eligible["CurrentCompany"].tolist())
    q53_eligible = q53_df[
        (q53_df["CurrentCompany"].isin(eligible_companies))
        & (q53_df["Q53_n"] >= MIN_BASE_INDICATIVE)
    ]

    market_q53 = (
        q53_eligible.groupby("Subject")
        .apply(lambda g: pd.Series({"market_mean": (g["Q53_mean"] * g["Q53_n"]).sum() / g["Q53_n"].sum()}), include_groups=False)
        .reset_index()
    )

    ins_q53 = q53_df[q53_df["CurrentCompany"] == insurer].copy()
    if ins_q53.empty or market_q53.empty:
        return

    diag = ins_q53.merge(market_q53, on="Subject")
    diag = diag[diag["Q53_n"] >= MIN_BASE_INDICATIVE]
    if diag.empty:
        return

    section_divider("Claims Journey Statements (Q53)")

    diag["gap"] = diag["Q53_mean"] - diag["market_mean"]
    diag = diag.sort_values("gap")

    rows_html = []
    for _, d in diag.iterrows():
        g = d["gap"]
        g_c = _gap_colour(g)
        indicator = f'<span style="color:{CI_GREEN};">\u25B2</span>' if g > 0.1 else f'<span style="color:{CI_RED};">\u25BC</span>' if g < -0.1 else f'<span style="color:{CI_GREY};">\u25C6</span>'
        rows_html.append(
            f'<tr><td style="padding:8px 12px; border-bottom:1px solid {CI_LIGHT_GREY};">{d["Subject"]}</td>'
            f'<td style="padding:8px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; font-weight:bold; color:{CI_VIOLET};">{d["Q53_mean"]:.2f}</td>'
            f'<td style="padding:8px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; color:{CI_GREY};">{d["market_mean"]:.2f}</td>'
            f'<td style="padding:8px; text-align:center; border-bottom:1px solid {CI_LIGHT_GREY}; color:{g_c}; font-weight:bold;">{indicator} {g:+.2f}</td></tr>'
        )

    table = (
        f'<table style="width:100%; border-collapse:collapse; font-family:{FONT}; font-size:13px;">'
        f'<thead><tr><th style="text-align:left; padding:8px; background:{CI_LGREY}; color:{CI_GREY};">Statement</th>'
        f'<th style="text-align:center; padding:8px; background:{CI_LGREY}; color:{CI_GREY};">{insurer}</th>'
        f'<th style="text-align:center; padding:8px; background:{CI_LGREY}; color:{CI_GREY};">Market</th>'
        f'<th style="text-align:center; padding:8px; background:{CI_LGREY}; color:{CI_GREY};">Gap</th></tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table>'
    )
    st.markdown(table, unsafe_allow_html=True)
    st.caption(f"Sorted by gap (lowest first). Min n={MIN_BASE_INDICATIVE} per statement.")


def _get_diagnostics(q53_df, eligible, insurer):
    """Extract Q53 diagnostics for AI narrative."""
    if q53_df.empty:
        return None

    for col in ["Q53_n", "Q53_mean", "Q53_std"]:
        if col in q53_df.columns:
            q53_df[col] = pd.to_numeric(q53_df[col], errors="coerce")

    eligible_companies = set(eligible["CurrentCompany"].tolist())
    q53_eligible = q53_df[
        (q53_df["CurrentCompany"].isin(eligible_companies))
        & (q53_df["Q53_n"] >= MIN_BASE_INDICATIVE)
    ]

    market_q53 = (
        q53_eligible.groupby("Subject")
        .apply(lambda g: pd.Series({"market_mean": (g["Q53_mean"] * g["Q53_n"]).sum() / g["Q53_n"].sum()}), include_groups=False)
        .reset_index()
    )

    ins_q53 = q53_df[q53_df["CurrentCompany"] == insurer].copy()
    if ins_q53.empty or market_q53.empty:
        return None

    diag = ins_q53.merge(market_q53, on="Subject")
    diag = diag[diag["Q53_n"] >= MIN_BASE_INDICATIVE]
    if diag.empty:
        return None

    return [
        {"subject": row["Subject"], "ins_mean": row["Q53_mean"], "mkt_mean": row["market_mean"], "gap": row["Q53_mean"] - row["market_mean"]}
        for _, row in diag.iterrows()
    ]
