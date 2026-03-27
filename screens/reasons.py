"""
Screen 6: Reasons & Drivers.

Market View: Top reasons for shopping (Q8), not shopping (Q19), staying (Q18),
             leaving (Q31), and choosing (Q33).
Insurer View: Insurer vs market comparison for each reason set.

Layout: Decision Screen pattern (context bar, narrative, sequential panels, footer).
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.narrative_engine import generate_screen_narrative
from lib.analytics.reasons import calc_reason_ranking, calc_reason_comparison, calc_reason_index
from lib.analytics.flow_display import format_reason_pct
from lib.chart_export import apply_export_metadata, render_suppression_html
from lib.components.context_bar import render_context_bar
from lib.components.context_footer import render_context_footer
from lib.components.decision_kpi import decision_kpi_row
from lib.components.narrative_panel import render_narrative_compact
from lib.components.question_info import render_question_info
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    MARKET_COLOUR,
    MIN_BASE_REASON,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct, period_label, FONT
from lib.question_ref import get_question_text
from lib.state import get_ss_data


# Reason question definitions: (q_code, title, base_description, filter_fn)
_MARKET_PANELS = [
    ("Q8", "Why Customers Shop", "Shoppers (Q7=Yes)", lambda df: df[df["IsShopper"]] if "IsShopper" in df.columns else df),
    ("Q19", "Why Customers Don't Shop", "Non-shoppers (Q7=No)", lambda df: df[~df["IsShopper"]] if "IsShopper" in df.columns else df),
    ("Q18", "Why Customers Stay After Shopping", "Shoppers who stayed", lambda df: df[(df["IsShopper"]) & (~df["IsSwitcher"])] if "IsShopper" in df.columns and "IsSwitcher" in df.columns else df),
    ("Q31", "Why Customers Leave", "Switchers", lambda df: df[df["IsSwitcher"]] if "IsSwitcher" in df.columns else df),
    ("Q33", "Why Customers Choose Their New Insurer", "Switchers", lambda df: df[df["IsSwitcher"]] if "IsSwitcher" in df.columns else df),
]


def render(filters: dict):
    """Render the Reasons & Drivers screen."""
    df_motor, dimensions = get_ss_data()

    if df_motor.empty:
        st.warning("No data loaded. Go to Admin to refresh from Power BI.")
        return

    insurer = filters["insurer"]
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

    if insurer:
        _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt)
    else:
        _render_market_view(df_mkt, filters, period, n_mkt)


# ---------------------------------------------------------------------------
# Market view
# ---------------------------------------------------------------------------

def _render_market_view(df_mkt, filters, period, n_mkt):
    """Market-level reason panels: 5 question sets."""
    product = filters["product"]

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Reasons & Drivers",
        product=product,
        period=period,
        n_market=n_mkt,
    )

    # ── Sequential panels ────────────────────────────────────────
    for q_code, title, base_desc, filter_fn in _MARKET_PANELS:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:700; '
            f'color:{CI_GREY}; margin:16px 0 4px 0;">'
            f'{title} ({q_code})</div>',
            unsafe_allow_html=True,
        )
        render_question_info(q_code)

        base_df = filter_fn(df_mkt)
        n_base = len(base_df)

        if n_base < MIN_BASE_REASON:
            st.info(
                f"Insufficient base for {q_code} analysis "
                f"(below minimum threshold). {base_desc}."
            )
            continue

        reasons = calc_reason_ranking(df_mkt, q_code, top_n=5)
        if not reasons:
            st.info(f"No {q_code} data available.")
            continue

        _render_reason_bar(reasons, q_code, title, period, n_base)

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="reasons_market",
        product=product,
        period=period,
        sample_n=n_mkt,
    )


# ---------------------------------------------------------------------------
# Insurer view
# ---------------------------------------------------------------------------

def _render_insurer_view(df_motor, df_mkt, insurer, filters, period, n_mkt):
    """Insurer vs market comparison for each reason set."""
    product = filters["product"]
    selected_months = filters["selected_months"]

    df_ins = apply_filters(
        df_motor,
        insurer=insurer,
        age_band=filters["age_band"],
        region=filters["region"],
        payment_type=filters["payment_type"],
        product=product,
        selected_months=selected_months,
    )

    n_ins = len(df_ins)

    # ── Context bar ──────────────────────────────────────────────
    render_context_bar(
        "Reasons & Drivers",
        insurer=insurer,
        product=product,
        period=period,
        n_insurer=n_ins,
        n_market=n_mkt,
    )

    # ── Suppression check ────────────────────────────────────────
    if n_ins < MIN_BASE_PUBLISHABLE:
        st.markdown(
            render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE),
            unsafe_allow_html=True,
        )
        return

    # ── AI Narrative (top of screen) ─────────────────────────────
    top_stay = calc_reason_ranking(df_mkt, "Q18", insurer, top_n=1)
    top_leave = calc_reason_ranking(df_mkt, "Q31", insurer, top_n=1)
    top_shop = calc_reason_ranking(df_mkt, "Q8", insurer, top_n=1)
    narrative = generate_screen_narrative("reasons", {
        "insurer": insurer,
        "product": filters["product"],
        "top_stay_reason": top_stay[0]["reason"] if top_stay else "N/A",
        "top_leave_reason": top_leave[0]["reason"] if top_leave else "N/A",
        "top_shop_reason": top_shop[0]["reason"] if top_shop else "N/A",
    })
    render_narrative_compact(narrative, "reasons")

    # ── Sequential reason panels ─────────────────────────────────
    _INSURER_PANELS = [
        ("Q8", f"Why {insurer}'s Customers Shopped Around", "shoppers"),
        ("Q19", f"Why {insurer}'s Customers Didn't Shop Around", "non-shoppers"),
        ("Q18", f"Why {insurer}'s Customers Stayed After Shopping", "shoppers who stayed"),
        ("Q31", f"Why Customers Left {insurer}", "switchers from this insurer"),
        ("Q33", f"Why Customers Chose {insurer} Over Alternatives", "switchers to this insurer"),
        ("Q28", f"What Would Bring Customers Back to {insurer}", "switchers from this insurer"),
    ]

    for q_code, title, base_desc in _INSURER_PANELS:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:700; '
            f'color:{CI_GREY}; margin:16px 0 4px 0;">'
            f'{title} ({q_code})</div>',
            unsafe_allow_html=True,
        )
        render_question_info(q_code)

        comparison = calc_reason_comparison(df_mkt, q_code, insurer, top_n=5)
        if not comparison:
            st.info(f"No {q_code} data available.")
            continue

        ins_reasons = comparison.get("insurer", [])
        mkt_reasons = comparison.get("market", [])

        if not ins_reasons and not mkt_reasons:
            st.info(f"No {q_code} data available.")
            continue

        _render_reason_index_table(ins_reasons, mkt_reasons, insurer, q_code)

    # ── Cross-screen links ───────────────────────────────────────
    st.markdown(
        f'<div style="font-size:11px; font-weight:700; text-transform:uppercase; '
        f'letter-spacing:0.8px; color:{CI_GREY}; margin:16px 0 6px 0;">Explore</div>',
        unsafe_allow_html=True,
    )
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Switching & Flows", key="reasons_to_switching"):
            from lib.state import navigate_to
            navigate_to("switching")
    with col2:
        if st.button("Satisfaction & Loyalty", key="reasons_to_satisfaction"):
            from lib.state import navigate_to
            navigate_to("satisfaction")

    # ── Context footer ───────────────────────────────────────────
    render_context_footer(
        screen_name="reasons",
        product=product,
        period=period,
        sample_n=n_ins,
    )


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _render_reason_bar(reasons: list[dict], q_code: str, title: str, period: str, n_base: int):
    """Render a horizontal bar chart for market-level reasons."""
    df = pd.DataFrame(reasons)

    # Use rank1_pct for ranked questions, mention_pct for multi-select
    pct_col = "rank1_pct" if "rank1_pct" in df.columns else "mention_pct"

    fig = go.Figure(go.Bar(
        x=df[pct_col],
        y=df["reason"],
        orientation="h",
        marker_color=CI_MAGENTA,
        text=[f"{p:.0%}" for p in df[pct_col]],
        textposition="outside",
        hovertemplate="%{y}: %{x:.1%}<extra></extra>",
    ))

    fig.update_layout(
        xaxis_tickformat=".0%",
        height=max(250, len(df) * 40 + 80),
        margin=dict(l=10, r=50, t=40, b=60),
        font=dict(family=FONT, size=11, color=CI_GREY),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        yaxis=dict(autorange="reversed"),
    )

    apply_export_metadata(
        fig,
        title=f"{title} \u2014 Top 5",
        period=period,
        base=n_base,
        question=q_code,
    )

    st.plotly_chart(fig, use_container_width=True)


def _render_reason_index_table(
    ins_reasons: list[dict],
    mkt_reasons: list[dict],
    insurer: str,
    q_code: str,
):
    """Render insurer vs market reason comparison as an indexed table."""
    indexed = calc_reason_index(ins_reasons, mkt_reasons)
    if not indexed:
        st.info(f"No {q_code} data available for indexing.")
        return

    # Build HTML table
    header = (
        f'<table style="width:100%; font-family:{FONT}; font-size:12px; '
        f'border-collapse:collapse; margin-bottom:12px;">'
        f'<tr style="border-bottom:2px solid {CI_GREY};">'
        f'<th style="text-align:left; padding:6px;">Reason</th>'
        f'<th style="text-align:right; padding:6px; color:{CI_MAGENTA};">{insurer}</th>'
        f'<th style="text-align:right; padding:6px; color:{MARKET_COLOUR};">Market</th>'
        f'<th style="text-align:right; padding:6px;">Index</th></tr>'
    )

    rows_html = []
    for r in indexed:
        brand_pct = r["brand_pct"]
        market_pct = r["market_pct"]
        index_val = r["index"]

        if index_val is not None:
            if index_val >= 110:
                idx_colour = CI_GREEN
            elif index_val <= 90:
                idx_colour = CI_RED
            else:
                idx_colour = CI_GREY
            idx_str = f"{index_val:.0f}"
        else:
            idx_colour = CI_GREY
            idx_str = "\u2014"

        rows_html.append(
            f'<tr style="border-bottom:1px solid {CI_LIGHT_GREY};">'
            f'<td style="padding:5px 6px;">{r["reason"]}</td>'
            f'<td style="text-align:right; padding:5px 6px; color:{CI_MAGENTA}; font-weight:bold;">{format_reason_pct(brand_pct)}</td>'
            f'<td style="text-align:right; padding:5px 6px; color:{MARKET_COLOUR};">{format_reason_pct(market_pct)}</td>'
            f'<td style="text-align:right; padding:5px 6px; color:{idx_colour}; font-weight:bold;">{idx_str}</td>'
            f'</tr>'
        )

    st.markdown(header + "".join(rows_html) + "</table>", unsafe_allow_html=True)
