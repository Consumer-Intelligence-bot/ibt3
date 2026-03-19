"""
Insurer Diagnostic — Comprehensive insurer deep-dive page.

Merges headline metrics, customer flows, reasons analysis, satisfaction,
cohort heat map, and AI narrative into a single diagnostic view.
Spec Sections 6.2-6.10.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.bayesian import bayesian_smooth_rate
from lib.analytics.cohort_heatmap import calc_cohort_heatmap
from lib.analytics.confidence import MetricType, assess_confidence, calc_ci_width
from lib.analytics.demographics import apply_filters
from lib.analytics.flows import (
    calc_net_flow,
    calc_top_sources,
    calc_top_destinations,
    calc_departed_sentiment,
)
from lib.analytics.rates import calc_shopping_rate, calc_switching_rate, calc_retention_rate, calc_insurer_rank
from lib.analytics.reasons import calc_reason_ranking, calc_reason_comparison
from lib.analytics.suppression import check_suppression
from lib.analytics.trends import calc_trend
from lib.chart_export import apply_export_metadata, render_suppression_html, confidence_tooltip
from lib.formatting import fmt_pct
from lib.config import (
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_YELLOW,
    MARKET_COLOUR,
    MIN_BASE_PUBLISHABLE,
    MIN_BASE_REASON,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_INDICATIVE,
)
from lib.narrative import generate_diagnostic_narrative
from lib.question_ref import get_question_text
from lib.state import format_year_month, render_global_filters, get_ss_data

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

FONT = "Verdana, Geneva, sans-serif"

st.set_page_config(page_title="Insurer Diagnostic", layout="wide") if "page_configured" not in st.session_state else None
st.header("Insurer Diagnostic")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fmt_pp(val, dp=1, sign=False):
    """Format a value already in percentage points."""
    if val is None:
        return "\u2014"
    prefix = "+" if sign and val > 0 else ""
    return f"{prefix}{val:.{dp}f}pp"


def _confidence_colour(label):
    """Map confidence label to CI brand colour."""
    mapping = {"HIGH": CI_GREEN, "MEDIUM": CI_YELLOW, "LOW": CI_RED, "INSUFFICIENT": CI_GREY}
    return mapping.get(str(label), CI_GREY)


def _card_html(title, value, subtitle="", colour=CI_MAGENTA):
    """Render a styled metric card as HTML."""
    return (
        f'<div style="background:white; border:1px solid {CI_LIGHT_GREY}; border-top:4px solid {colour}; '
        f'border-radius:4px; padding:16px 20px; text-align:center; font-family:{FONT};">'
        f'<div style="font-size:12px; color:{CI_GREY}; margin-bottom:6px;">{title}</div>'
        f'<div style="font-size:28px; font-weight:bold; color:{colour};">{value}</div>'
        f'<div style="font-size:11px; color:{CI_GREY}; margin-top:4px;">{subtitle}</div>'
        f"</div>"
    )


def _section_divider(title):
    """Render a branded section divider."""
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:15px; font-weight:bold; color:{CI_GREY}; '
        f'border-bottom:2px solid {CI_LIGHT_GREY}; padding-bottom:8px; margin:28px 0 16px 0;">'
        f"{title}</div>",
        unsafe_allow_html=True,
    )


def _period_label(selected_months):
    """Build a human-readable period label from selected months."""
    if not selected_months:
        return "All periods"
    start = format_year_month(min(selected_months))
    end = format_year_month(max(selected_months))
    if start == end:
        return start
    return f"{start} \u2013 {end}"


# ---------------------------------------------------------------------------
# Filters & data loading
# ---------------------------------------------------------------------------

filters = render_global_filters()
df_motor, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded. Check Power BI connection.")
    st.stop()

insurer = filters["insurer"]
product = filters["product"]
age_band = filters["age_band"]
region = filters["region"]
payment_type = filters["payment_type"]
selected_months = filters["selected_months"]

if not insurer:
    st.info("Select an insurer in the sidebar to view the diagnostic.")
    st.stop()

# Market-level data (all insurers)
df_mkt = apply_filters(
    df_motor, insurer=None, age_band=age_band, region=region,
    payment_type=payment_type, product=product, selected_months=selected_months,
)

# Insurer-level data
df_ins = apply_filters(
    df_motor, insurer=insurer, age_band=age_band, region=region,
    payment_type=payment_type, product=product, selected_months=selected_months,
)

if len(df_mkt) == 0:
    st.warning("No data for selected filters.")
    st.stop()

period = _period_label(selected_months)
n_ins = len(df_ins)
n_mkt = len(df_mkt)

# Active period banner
st.markdown(
    f'<div style="background:{CI_LIGHT_GREY}; padding:10px 16px; border-radius:4px; '
    f'font-family:{FONT}; font-size:13px; color:{CI_GREY}; margin-bottom:16px;">'
    f"<b>{insurer}</b> &nbsp;|&nbsp; {product} &nbsp;|&nbsp; {period} "
    f"&nbsp;|&nbsp; Insurer n={n_ins:,} &nbsp;|&nbsp; Market n={n_mkt:,}"
    f"</div>",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Section 1: Confidence Banner
# ---------------------------------------------------------------------------

# Compute insurer retention rate for confidence assessment
ins_retention = calc_retention_rate(df_ins)
mkt_retention = calc_retention_rate(df_mkt)

# Bayesian smoothing
ins_existing = df_ins[~df_ins.get("IsNewToMarket", False)] if "IsNewToMarket" in df_ins.columns else df_ins
retained_count = int(ins_existing["IsRetained"].sum()) if "IsRetained" in ins_existing.columns else 0
trials = len(ins_existing)

bay = bayesian_smooth_rate(
    retained_count, trials, mkt_retention if mkt_retention else 0.5
)
posterior_ci_width = (bay["ci_upper"] - bay["ci_lower"]) * 100  # pp

conf = assess_confidence(
    n=n_ins, rate=ins_retention, metric_type=MetricType.RATE,
    posterior_ci_width=posterior_ci_width,
)

# Render confidence banner
conf_colour = _confidence_colour(conf.label)
conf_icon = {"HIGH": "\u2705", "MEDIUM": "\u26A0\uFE0F", "LOW": "\u26A0\uFE0F", "INSUFFICIENT": "\u26D4"}.get(
    str(conf.label), ""
)
conf_text = {
    "HIGH": f"High confidence \u2014 n={n_ins:,}, Confidence interval width {posterior_ci_width:.0f}pp",
    "MEDIUM": f"Medium confidence \u2014 n={n_ins:,}, Confidence interval width {posterior_ci_width:.0f}pp. Treat as indicative.",
    "LOW": f"Low confidence \u2014 n={n_ins:,}, Confidence interval width {posterior_ci_width:.0f}pp. Interpret with caution.",
    "INSUFFICIENT": f"Insufficient data \u2014 n={n_ins:,}. Results suppressed.",
}.get(str(conf.label), "")

st.markdown(
    f'<div style="background:white; border-left:6px solid {conf_colour}; padding:12px 16px; '
    f'margin-bottom:20px; font-family:{FONT}; font-size:13px; color:{CI_GREY}; '
    f'border:1px solid {CI_LIGHT_GREY}; border-left:6px solid {conf_colour};">'
    f"{conf_icon} <b>{conf_text}</b>"
    f'<span style="float:right; cursor:help;" title="{confidence_tooltip("ci")}">\u2139\uFE0F</span>'
    f"</div>",
    unsafe_allow_html=True,
)

# If insufficient data, show suppression message and stop
if not conf.can_show:
    st.markdown(render_suppression_html(insurer, n_ins, MIN_BASE_PUBLISHABLE), unsafe_allow_html=True)
    st.stop()

# ---------------------------------------------------------------------------
# Section 2: Retention Performance Cards
# ---------------------------------------------------------------------------

_section_divider("Retention Performance")

# Insurer Bayesian-smoothed retention
ins_rate_display = bay["posterior_mean"]
ins_ci_lower = bay["ci_lower"]
ins_ci_upper = bay["ci_upper"]

# Market average (unsmoothed)
mkt_rate_display = mkt_retention if mkt_retention else 0

# Position assessment
gap_pp = (ins_rate_display - mkt_rate_display) * 100
rank_info = calc_insurer_rank(df_mkt, insurer, min_base=MIN_BASE_PUBLISHABLE)
rank_suffix = f" (Rank {rank_info['rank']} of {rank_info['total']})" if rank_info else ""

if abs(gap_pp) < 1.0:
    position_label = "At Market"
    position_colour = CI_GREY
elif gap_pp > 0:
    position_label = "Above Market"
    position_colour = CI_GREEN
else:
    position_label = "Below Market"
    position_colour = CI_RED

# Trend
trend = calc_trend(df_ins, mkt_rate_display)
trend_indicator = ""
if not trend["suppressed"] and trend["direction"]:
    if trend["direction"] == "up":
        trend_indicator = f'\u25B2 +{trend["change"]:.1f}pp'
    elif trend["direction"] == "down":
        trend_indicator = f'\u25BC {trend["change"]:.1f}pp'
    else:
        trend_indicator = "\u25C6 Stable"

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(
        _card_html(
            "Your Retention (Bayesian-smoothed)",
            fmt_pct(ins_rate_display),
            f"95% Confidence Interval: {fmt_pct(ins_ci_lower, dp=0)} \u2013 {fmt_pct(ins_ci_upper, dp=0)}",
            CI_MAGENTA,
        ),
        unsafe_allow_html=True,
    )

with col2:
    st.markdown(
        _card_html(
            "Market Average",
            fmt_pct(mkt_rate_display),
            f"n={n_mkt:,}",
            MARKET_COLOUR,
        ),
        unsafe_allow_html=True,
    )

with col3:
    trend_sub = f"{_fmt_pp(gap_pp, sign=True)} vs market"
    if rank_suffix:
        trend_sub += f" &nbsp;|&nbsp; {rank_suffix.strip(' ()')}"
    if trend_indicator:
        trend_sub += f" &nbsp;|&nbsp; Trend: {trend_indicator}"
    st.markdown(
        _card_html(
            "Your Position",
            position_label,
            trend_sub,
            position_colour,
        ),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 3: Customer Flow Panel
# ---------------------------------------------------------------------------

_section_divider("Customer Flows")

sources = calc_top_sources(df_mkt, insurer, 5)
destinations = calc_top_destinations(df_mkt, insurer, 5)

col_src, col_dst = st.columns(2)

with col_src:
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; color:{CI_GREEN}; '
        f'margin-bottom:8px;">Winning From (Top Sources)</div>',
        unsafe_allow_html=True,
    )
    if len(sources) > 0:
        # Suppress rows where cell count < MIN_BASE_FLOW_CELL
        for competitor, count in sources.items():
            if count < MIN_BASE_FLOW_CELL:
                continue
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; padding:4px 0; '
                f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                f'<span style="color:{CI_GREY};">{competitor}</span>'
                f'<span style="float:right; font-weight:bold; color:{CI_GREEN};">+{count}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No source data available.")

with col_dst:
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; color:{CI_RED}; '
        f'margin-bottom:8px;">Losing To (Top Destinations)</div>',
        unsafe_allow_html=True,
    )
    if len(destinations) > 0:
        for competitor, count in destinations.items():
            if count < MIN_BASE_FLOW_CELL:
                continue
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; padding:4px 0; '
                f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                f'<span style="color:{CI_GREY};">{competitor}</span>'
                f'<span style="float:right; font-weight:bold; color:{CI_RED};">\u2212{count}</span>'
                f"</div>",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No destination data available.")

# ---------------------------------------------------------------------------
# Section 4: Net Movement Summary
# ---------------------------------------------------------------------------

_section_divider("Net Movement")

nf = calc_net_flow(df_mkt, insurer, base=n_ins)
gained = nf["gained"]
lost = nf["lost"]
net = nf["net"]
gained_pct = nf.get("gained_pct")
lost_pct = nf.get("lost_pct")
net_pct = nf.get("net_pct")

if net > 0:
    net_colour = CI_GREEN
    net_icon = "\u25B2"
elif net < 0:
    net_colour = CI_RED
    net_icon = "\u25BC"
else:
    net_colour = CI_GREY
    net_icon = "\u25C6"

col_g, col_l, col_n = st.columns(3)

with col_g:
    gained_display = f"+{gained_pct:.1%} (+{gained:,})" if gained_pct is not None else f"+{gained:,}"
    st.markdown(
        _card_html("Gained", gained_display, "Switched in", CI_GREEN),
        unsafe_allow_html=True,
    )

with col_l:
    lost_display = f"\u2212{lost_pct:.1%} (\u2212{lost:,})" if lost_pct is not None else f"\u2212{lost:,}"
    st.markdown(
        _card_html("Lost", lost_display, "Switched out", CI_RED),
        unsafe_allow_html=True,
    )

with col_n:
    net_sign = "+" if net > 0 else ""
    if net_pct is not None:
        net_pct_sign = "+" if net_pct > 0 else ""
        net_display = f"{net_icon} {net_pct_sign}{net_pct:.1%} ({net_sign}{net:,})"
    else:
        net_display = f"{net_icon} {net_sign}{net:,}"
    st.markdown(
        _card_html(
            "Net Flow",
            net_display,
            "Net winner" if net > 0 else ("Net loser" if net < 0 else "Neutral"),
            net_colour,
        ),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 5: Why Customers Stay (Q18 Reasons)
# ---------------------------------------------------------------------------

_section_divider("Why Customers Stay (Q18)")
st.caption(get_question_text("Q18"))

if n_ins >= MIN_BASE_REASON:
    q18_comparison = calc_reason_comparison(df_mkt, "Q18", insurer, top_n=5)
    if q18_comparison:
        col_ins_r, col_mkt_r = st.columns(2)
        with col_ins_r:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
                f'color:{CI_MAGENTA}; margin-bottom:6px;">{insurer}</div>',
                unsafe_allow_html=True,
            )
            for r in q18_comparison.get("insurer", []):
                pct = r.get("rank1_pct", r.get("mention_pct", 0))
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'{r["reason"]} <span style="float:right; color:{CI_MAGENTA}; '
                    f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                    unsafe_allow_html=True,
                )

        with col_mkt_r:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
                f'color:{MARKET_COLOUR}; margin-bottom:6px;">Market</div>',
                unsafe_allow_html=True,
            )
            for r in q18_comparison.get("market", []):
                pct = r.get("rank1_pct", r.get("mention_pct", 0))
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'{r["reason"]} <span style="float:right; color:{MARKET_COLOUR}; '
                    f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.caption("No Q18 reason data available.")
else:
    st.markdown(
        render_suppression_html(f"{insurer} (Q18 Reasons)", n_ins, MIN_BASE_REASON),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 6: Why Customers Leave (Q31 Reasons)
# ---------------------------------------------------------------------------

_section_divider("Why Customers Leave (Q31)")
st.caption(get_question_text("Q31"))

# For Q31, the base is departed customers
departed_ins = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)] if "PreviousCompany" in df_mkt.columns else pd.DataFrame()
n_departed = len(departed_ins)

if n_departed >= MIN_BASE_REASON:
    q31_comparison = calc_reason_comparison(df_mkt, "Q31", insurer, top_n=5)
    if q31_comparison:
        col_ins_q31, col_mkt_q31 = st.columns(2)
        with col_ins_q31:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
                f'color:{CI_MAGENTA}; margin-bottom:6px;">{insurer}</div>',
                unsafe_allow_html=True,
            )
            for r in q31_comparison.get("insurer", []):
                pct = r.get("rank1_pct", r.get("mention_pct", 0))
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'{r["reason"]} <span style="float:right; color:{CI_MAGENTA}; '
                    f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                    unsafe_allow_html=True,
                )

        with col_mkt_q31:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:12px; font-weight:bold; '
                f'color:{MARKET_COLOUR}; margin-bottom:6px;">Market</div>',
                unsafe_allow_html=True,
            )
            for r in q31_comparison.get("market", []):
                pct = r.get("rank1_pct", r.get("mention_pct", 0))
                st.markdown(
                    f'<div style="font-family:{FONT}; font-size:12px; padding:3px 0; '
                    f'border-bottom:1px solid {CI_LIGHT_GREY};">'
                    f'{r["reason"]} <span style="float:right; color:{MARKET_COLOUR}; '
                    f'font-weight:bold;">{pct * 100:.0f}%</span></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.caption("No Q31 reason data available.")
else:
    st.markdown(
        render_suppression_html(f"{insurer} (Q31 Reasons)", n_departed, MIN_BASE_REASON),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 7: Previous Insurer Satisfaction (Q40a / Q40b)
# ---------------------------------------------------------------------------

_section_divider("Previous Insurer Satisfaction (Q40a / Q40b)")
st.caption(get_question_text("Q40a"))
st.caption(get_question_text("Q40b"))

sentiment_ins = calc_departed_sentiment(df_mkt, insurer)

# Market-level departed sentiment (all switchers)
sentiment_mkt = None
if "IsSwitcher" in df_mkt.columns:
    all_switchers = df_mkt[df_mkt["IsSwitcher"]]
    if len(all_switchers) >= MIN_BASE_REASON:
        sentiment_mkt_data = {"n": len(all_switchers)}
        if "Q40a" in all_switchers.columns:
            sentiment_mkt_data["mean_q40a"] = all_switchers["Q40a"].mean()
        if "Q40b" in all_switchers.columns:
            nps_vals = pd.to_numeric(all_switchers["Q40b"], errors="coerce")
            promoters = (nps_vals >= 9).sum()
            detractors = (nps_vals <= 6).sum()
            sentiment_mkt_data["nps"] = (
                100 * (promoters - detractors) / len(all_switchers)
                if len(all_switchers) > 0
                else 0
            )
        sentiment_mkt = sentiment_mkt_data

if sentiment_ins and sentiment_ins.get("n", 0) >= MIN_BASE_REASON:
    col_sat1, col_sat2, col_sat3, col_sat4 = st.columns(4)

    ins_sat = sentiment_ins.get("mean_q40a")
    mkt_sat = sentiment_mkt.get("mean_q40a") if sentiment_mkt else None
    ins_nps = sentiment_ins.get("nps")
    mkt_nps = sentiment_mkt.get("nps") if sentiment_mkt else None

    with col_sat1:
        st.markdown(
            _card_html(
                f"{insurer} Satisfaction",
                f"{ins_sat:.2f}" if ins_sat is not None else "\u2014",
                "Q40a mean (1\u20135)",
                CI_MAGENTA,
            ),
            unsafe_allow_html=True,
        )

    with col_sat2:
        st.markdown(
            _card_html(
                "Market Satisfaction",
                f"{mkt_sat:.2f}" if mkt_sat is not None else "\u2014",
                "Q40a mean (1\u20135)",
                MARKET_COLOUR,
            ),
            unsafe_allow_html=True,
        )

    with col_sat3:
        nps_colour = CI_GREEN if ins_nps is not None and ins_nps > 0 else CI_RED if ins_nps is not None and ins_nps < 0 else CI_GREY
        st.markdown(
            _card_html(
                f"{insurer} NPS",
                f"{ins_nps:+.0f}" if ins_nps is not None else "\u2014",
                "Q40b (0\u201310 scale)",
                nps_colour,
            ),
            unsafe_allow_html=True,
        )

    with col_sat4:
        mkt_nps_colour = CI_GREEN if mkt_nps is not None and mkt_nps > 0 else CI_RED if mkt_nps is not None and mkt_nps < 0 else CI_GREY
        st.markdown(
            _card_html(
                "Market NPS",
                f"{mkt_nps:+.0f}" if mkt_nps is not None else "\u2014",
                "Q40b (0\u201310 scale)",
                mkt_nps_colour,
            ),
            unsafe_allow_html=True,
        )

    st.caption(f"Base: {sentiment_ins['n']:,} switchers from {insurer}")
else:
    switcher_n = sentiment_ins["n"] if sentiment_ins else 0
    st.markdown(
        render_suppression_html(f"{insurer} (Departed Satisfaction)", switcher_n, MIN_BASE_REASON),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 8: Cohort Heat Map
# ---------------------------------------------------------------------------

_section_divider("Cohort Heat Map \u2014 Demographic Segments vs Market")

heatmap_df = calc_cohort_heatmap(df_ins, df_mkt)

if not heatmap_df.empty:
    # Pivot for display: rows = segment, columns = metric, values = delta
    for field in heatmap_df["segment_field"].unique():
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:13px; font-weight:bold; '
            f'color:{CI_GREY}; margin:12px 0 6px 0;">{field}</div>',
            unsafe_allow_html=True,
        )

        field_data = heatmap_df[heatmap_df["segment_field"] == field]
        metrics = field_data["metric"].unique()
        segments = field_data["segment_value"].unique()

        # Build table header
        header = f'<table style="width:100%; font-family:{FONT}; font-size:12px; border-collapse:collapse;">'
        header += f'<tr style="border-bottom:2px solid {CI_LIGHT_GREY};">'
        header += f'<th style="text-align:left; padding:6px 8px; color:{CI_GREY};">Segment</th>'
        for m in metrics:
            header += f'<th style="text-align:center; padding:6px 8px; color:{CI_GREY};">{m}</th>'
        header += "</tr>"

        rows_html = ""
        for seg in segments:
            rows_html += f'<tr style="border-bottom:1px solid {CI_LIGHT_GREY};">'
            rows_html += f'<td style="padding:6px 8px; color:{CI_GREY};">{seg}</td>'
            for m in metrics:
                cell = field_data[(field_data["segment_value"] == seg) & (field_data["metric"] == m)]
                if len(cell) == 0 or cell.iloc[0]["suppressed"]:
                    rows_html += f'<td style="text-align:center; padding:6px 8px; color:{CI_LIGHT_GREY};">n/a</td>'
                else:
                    delta = cell.iloc[0]["delta"]
                    if delta is not None:
                        if delta > 2:
                            bg = f"rgba(72, 162, 63, 0.15)"
                            fg = CI_GREEN
                        elif delta < -2:
                            bg = f"rgba(244, 54, 76, 0.15)"
                            fg = CI_RED
                        else:
                            bg = "transparent"
                            fg = CI_GREY
                        sign = "+" if delta > 0 else ""
                        rows_html += (
                            f'<td style="text-align:center; padding:6px 8px; background:{bg}; '
                            f'color:{fg}; font-weight:bold;">{sign}{delta:.1f}pp</td>'
                        )
                    else:
                        rows_html += f'<td style="text-align:center; padding:6px 8px; color:{CI_LIGHT_GREY};">\u2014</td>'
            rows_html += "</tr>"

        st.markdown(header + rows_html + "</table>", unsafe_allow_html=True)

    st.caption(
        f"Cells show insurer rate minus market rate (pp). "
        f"Suppressed where insurer segment n < {MIN_BASE_INDICATIVE}."
    )
else:
    st.caption("No demographic data available for cohort analysis.")

# ---------------------------------------------------------------------------
# Section 9: Next Steps Panel
# ---------------------------------------------------------------------------

_section_divider("What to Check Next")

next_steps = []

# Generate prompts based on the data
if gap_pp < -2:
    next_steps.append(
        "Retention is below market. Review pricing competitiveness at renewal "
        "and check whether recent premium changes coincide with the drop."
    )
if net < 0:
    top_dest = destinations.head(1)
    dest_name = top_dest.index[0] if len(top_dest) > 0 else "competitors"
    next_steps.append(
        f"Net flow is negative. The largest outflow is to {dest_name}. "
        f"Compare your renewal pricing and product features against this competitor."
    )
if sentiment_ins and sentiment_ins.get("nps") is not None and sentiment_ins["nps"] < 0:
    next_steps.append(
        "Departed customer NPS is negative. Review service touchpoints leading up to renewal "
        "and consider whether claims experience is a contributing factor."
    )
if trend.get("direction") == "down":
    next_steps.append(
        "Retention trend is downward. Check whether this aligns with any recent "
        "operational changes, pricing adjustments, or competitor activity."
    )

# Always include external data prompts
next_steps.append(
    "Cross-reference with internal data: renewal pricing distributions, "
    "call-centre retention rates, and advertising spend schedules."
)
next_steps.append(
    "Check competitor activity: new product launches, pricing campaigns, "
    "or PCW positioning changes that may explain flow patterns."
)

for i, step in enumerate(next_steps, 1):
    st.markdown(
        f'<div style="font-family:{FONT}; font-size:13px; padding:8px 12px; '
        f'margin-bottom:6px; background:white; border-left:4px solid {CI_MAGENTA}; '
        f'border:1px solid {CI_LIGHT_GREY}; border-left:4px solid {CI_MAGENTA}; '
        f'border-radius:2px; color:{CI_GREY};">'
        f"<b>{i}.</b> {step}</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Section 10: AI Narrative
# ---------------------------------------------------------------------------

_section_divider("AI Diagnostic Narrative")

# Assemble metrics for the narrative generator
narrative_metrics = {
    "insurer": insurer,
    "retention_rate": ins_rate_display,
    "mkt_retention_rate": mkt_rate_display,
    "shopping_rate": calc_shopping_rate(df_ins),
    "mkt_shopping_rate": calc_shopping_rate(df_mkt),
    "net_flow": net,
    "gained": gained,
    "lost": lost,
}

# Top sources / destinations as names
if len(sources) > 0:
    narrative_metrics["top_sources"] = [str(s) for s in sources.index[:3]]
if len(destinations) > 0:
    narrative_metrics["top_destinations"] = [str(d) for d in destinations.index[:3]]

# Reasons
q18_ins = calc_reason_ranking(df_mkt, "Q18", insurer, top_n=3)
if q18_ins:
    narrative_metrics["stay_reasons"] = [r["reason"] for r in q18_ins]

q31_ins = calc_reason_ranking(df_mkt, "Q31", insurer, top_n=3)
if q31_ins:
    narrative_metrics["leave_reasons"] = [r["reason"] for r in q31_ins]

# Satisfaction
if sentiment_ins:
    if sentiment_ins.get("mean_q40a") is not None:
        narrative_metrics["departed_satisfaction"] = sentiment_ins["mean_q40a"]
    if sentiment_ins.get("nps") is not None:
        narrative_metrics["departed_nps"] = sentiment_ins["nps"]

narrative = generate_diagnostic_narrative(narrative_metrics)

if narrative:
    st.markdown(
        f'<div style="font-family:{FONT}; background:white; border:1px solid {CI_LIGHT_GREY}; '
        f'border-radius:4px; padding:20px 24px;">'
        f'<div style="font-size:16px; font-weight:bold; color:{CI_MAGENTA}; margin-bottom:8px;">'
        f'{narrative.get("headline", "")}</div>'
        f'<div style="font-size:13px; color:{CI_GREY}; font-style:italic; margin-bottom:16px;">'
        f'{narrative.get("subtitle", "")}</div>',
        unsafe_allow_html=True,
    )

    findings = narrative.get("findings", [])
    if findings:
        for finding in findings:
            st.markdown(
                f'<div style="font-family:{FONT}; font-size:13px; color:{CI_GREY}; '
                f'margin-bottom:12px; padding:10px 14px; background:{CI_LIGHT_GREY}; border-radius:4px;">'
                f'<div style="margin-bottom:4px;"><b>Fact:</b> {finding.get("fact", "")}</div>'
                f'<div style="margin-bottom:4px;"><b>Observation:</b> {finding.get("observation", "")}</div>'
                f'<div><b>Investigate:</b> {finding.get("prompt", "")}</div>'
                f"</div>",
                unsafe_allow_html=True,
            )

    data_gaps = narrative.get("data_gaps", [])
    if data_gaps:
        st.markdown(
            f'<div style="font-family:{FONT}; font-size:12px; color:{CI_GREY}; '
            f'margin-top:12px; padding:8px 14px; border-left:3px solid {CI_YELLOW};">'
            f'<b>Data gaps to fill:</b> {" | ".join(data_gaps)}</div>',
            unsafe_allow_html=True,
        )

    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.caption(
        "AI narrative unavailable. Ensure ANTHROPIC_API_KEY is set and narrative generation is enabled."
    )

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.markdown("---")
st.caption(
    f"Insurer Diagnostic | {insurer} | {product} | {period} | "
    f"Insurer base: {n_ins:,} | Market base: {n_mkt:,}"
)
