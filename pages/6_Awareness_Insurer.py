"""
Brand Awareness — Insurer View.
Slopegraph panels, trend lines with market percentile band,
confidence banner, and co-awareness panel (Spec Sections 10.1-10.5).
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.awareness import (
    Q1_GATING_MESSAGE,
    calc_awareness_market_bands,
    calc_awareness_rates,
    calc_awareness_slopegraph,
)
from lib.analytics.demographics import apply_filters
from lib.chart_export import apply_export_metadata, confidence_tooltip, heading_with_tooltip
from lib.config import (
    BUMP_COLOURS, CI_BLUE, CI_GREEN, CI_GREY, CI_LIGHT_GREY,
    CI_MAGENTA, CI_RED, MIN_BASE_PUBLISHABLE,
)
from lib.state import format_year_month, render_global_filters, get_ss_data

st.header("Brand Awareness \u2014 Insurer View")

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
df_main = apply_filters(df_motor, product=product, selected_months=selected_months)

# ---- Confidence Banner (Spec 10.2) ----
prompted_rates_all = calc_awareness_rates(df_main, df_questions, "prompted")
insurer_months = prompted_rates_all[prompted_rates_all["brand"] == insurer] if not prompted_rates_all.empty else None

if insurer_months is not None and not insurer_months.empty:
    median_n = insurer_months["n_total"].median()
    if median_n >= 100:
        banner_colour = CI_GREEN
        banner_text = "HIGH confidence"
    elif median_n >= 50:
        banner_colour = "#FFCD00"
        banner_text = "MEDIUM confidence"
    else:
        banner_colour = CI_RED
        banner_text = "LOW confidence"

    st.markdown(
        f'<div style="padding:12px; border-left:4px solid {banner_colour}; '
        f'background:{CI_LIGHT_GREY}; margin-bottom:16px; font-family:Verdana;">'
        f"<strong>{insurer}</strong> &mdash; "
        f"<strong style='color:{banner_colour}'>{banner_text}</strong> &nbsp;|&nbsp; "
        f"Median monthly respondents: <strong>{int(median_n):,}</strong>"
        f"</div>",
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        f'<div style="padding:12px; border-left:4px solid {CI_RED}; '
        f'background:{CI_LIGHT_GREY}; margin-bottom:16px; font-family:Verdana;">'
        f"No awareness data available for <strong>{insurer}</strong> in this period."
        f"</div>",
        unsafe_allow_html=True,
    )
    st.stop()

# ---- Slopegraph panels (Spec 10.3) ----
st.markdown(heading_with_tooltip("Awareness Funnel", "Q2", level="subheader"), unsafe_allow_html=True)
prompted_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "prompted")
consideration_slope = calc_awareness_slopegraph(df_main, df_questions, insurer, "consideration")

col1, col2, col3 = st.columns(3)

with col1:
    st.markdown(heading_with_tooltip("Spontaneous", "Q1", level="small"), unsafe_allow_html=True)
    st.info(Q1_GATING_MESSAGE)

for col, title, data, colour, qc in [
    (col2, "Prompted", prompted_slope, CI_BLUE, "Q2"),
    (col3, "Consideration", consideration_slope, CI_GREEN, "Q27"),
]:
    with col:
        st.markdown(heading_with_tooltip(title, qc, level="small"), unsafe_allow_html=True)
        if data and data.get("can_show"):
            arrows = {"up": "\u2191", "down": "\u2193", "flat": "\u2192"}
            arrow = arrows.get(data["direction"], "\u2192")
            delta_sign = "+" if data["change"] > 0 else ""

            st.metric(
                format_year_month(data["start_month"]),
                f"{data['start_rate']:.1%}",
            )
            st.markdown(f"### {arrow}")
            st.metric(
                format_year_month(data["end_month"]),
                f"{data['end_rate']:.1%}",
                delta=f"{delta_sign}{data['change']:.1%}",
            )
            # Market context
            if data.get("start_market_rate") is not None:
                st.caption(f"Market: {data['start_market_rate']:.1%} \u2192 {data['end_market_rate']:.1%}")
        else:
            st.info("Insufficient data")

# Diagnostic note (Spec 10.4)
if prompted_slope and consideration_slope:
    if (prompted_slope.get("can_show") and consideration_slope.get("can_show")):
        p_change = prompted_slope["change"]
        c_change = consideration_slope["change"]
        if p_change > 0.01 and c_change < 0.005:
            st.info(
                "Prompted awareness is rising but consideration is flat. "
                "The widening gap suggests brand recognition is not converting to active purchase intent. "
                "This is the key diagnostic for conversion effectiveness."
            )

# ---- Trend chart with market bands (Spec 10.4) ----
st.markdown(heading_with_tooltip("Awareness Trend vs Market", "Q2", level="subheader"), unsafe_allow_html=True)

prompted_rates = calc_awareness_rates(df_main, df_questions, "prompted")
consideration_rates = calc_awareness_rates(df_main, df_questions, "consideration")
prompted_bands = calc_awareness_market_bands(df_main, df_questions, "prompted")
consideration_bands = calc_awareness_market_bands(df_main, df_questions, "consideration")

fig = go.Figure()

# Market percentile bands
for bands_df, band_colour, band_label in [
    (prompted_bands, "rgba(91, 194, 231, 0.15)", "Market 25th\u201375th (Prompted)"),
    (consideration_bands, "rgba(72, 162, 63, 0.15)", "Market 25th\u201375th (Consideration)"),
]:
    if not bands_df.empty:
        months_label = [format_year_month(m) for m in bands_df["month"]]
        fig.add_trace(go.Scatter(
            x=months_label, y=bands_df["p75"],
            mode="lines", line=dict(width=0), showlegend=False, hoverinfo="skip",
        ))
        fig.add_trace(go.Scatter(
            x=months_label, y=bands_df["p25"],
            mode="lines", line=dict(width=0), fill="tonexty",
            fillcolor=band_colour, name=band_label, hoverinfo="skip", showlegend=False,
        ))

# Insurer lines
for level, rates_df, colour, label in [
    ("prompted", prompted_rates, CI_BLUE, "Prompted"),
    ("consideration", consideration_rates, CI_GREEN, "Consideration"),
]:
    if rates_df.empty:
        continue
    brand_data = rates_df[rates_df["brand"] == insurer].sort_values("month")
    if brand_data.empty:
        continue
    x = [format_year_month(m) for m in brand_data["month"]]
    fig.add_trace(go.Scatter(
        x=x, y=brand_data["rate"],
        mode="lines+markers", name=label,
        line=dict(color=colour, width=2.5),
        marker=dict(size=6, color=colour),
        hovertemplate=f"<b>{label}</b><br>Rate: %{{y:.1%}}<br>%{{x}}<extra></extra>",
    ))

fig.update_layout(
    yaxis_tickformat=".0%", yaxis_title="Awareness Rate", yaxis_range=[0, 1],
    legend=dict(orientation="h", yanchor="top", y=-0.12),
    height=400, font=dict(family="Verdana"),
    plot_bgcolor="white", paper_bgcolor="white",
)
st.plotly_chart(fig, use_container_width=True)

st.caption(confidence_tooltip("ci"))

# ---- Co-Awareness Panel (Spec 10.5) ----
st.markdown("---")
st.markdown(heading_with_tooltip("Co-Awareness", "Q2", level="subheader"), unsafe_allow_html=True)
st.caption(
    f"Of people who are aware of {insurer}, which other brands do they also recognise?"
)

# Compute co-awareness from prompted awareness (Q2)
if not prompted_rates.empty and not df_questions.empty:
    from lib.analytics.queries import query_multi

    q2_mentions = query_multi(df_questions, "Q2")
    if not q2_mentions.empty:
        # Find respondents aware of the selected insurer
        insurer_aware_ids = set(
            q2_mentions[q2_mentions["Answer"] == insurer]["UniqueID"].unique()
        )

        if insurer_aware_ids:
            # Among those respondents, count mentions of other brands
            co_mentions = q2_mentions[
                (q2_mentions["UniqueID"].isin(insurer_aware_ids))
                & (q2_mentions["Answer"] != insurer)
            ]
            co_counts = co_mentions.groupby("Answer")["UniqueID"].nunique()
            total_aware = len(insurer_aware_ids)
            co_rates = (co_counts / total_aware).sort_values(ascending=False)

            # Sort options
            co_sort = st.radio(
                "Sort by",
                ["Current co-awareness", "By movement"],
                horizontal=True,
                key="co_sort",
            )

            n_show = st.slider(
                "Brands to show", min_value=5, max_value=30, value=10, key="co_n",
            )

            co_display = co_rates.head(n_show)

            if not co_display.empty:
                fig_co = go.Figure(go.Bar(
                    y=co_display.index[::-1],
                    x=co_display.values[::-1],
                    orientation="h",
                    marker_color=CI_BLUE,
                    text=[f"{v:.0%}" for v in co_display.values[::-1]],
                    textposition="outside",
                    hovertemplate="<b>%{y}</b><br>Co-awareness: %{x:.1%}<extra></extra>",
                ))
                fig_co.update_layout(
                    xaxis_tickformat=".0%",
                    xaxis_title="Co-awareness rate",
                    height=max(300, len(co_display) * 30),
                    margin=dict(l=180, r=60, t=10),
                    font=dict(family="Verdana"),
                    plot_bgcolor="white",
                    paper_bgcolor="white",
                )
                st.plotly_chart(fig_co, use_container_width=True)
                st.caption(
                    f"Base: {total_aware:,} respondents aware of {insurer}. "
                    f"Shows percentage who also recognise each other brand."
                )
            else:
                st.info("No co-awareness data available.")
        else:
            st.info(f"No respondents aware of {insurer} in this period.")
    else:
        st.info("Prompted awareness data (Q2) not available.")
else:
    st.info("Insufficient awareness data for co-awareness analysis.")
