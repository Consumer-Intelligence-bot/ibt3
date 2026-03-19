"""
Unprompted Brand Awareness — Q1 Spontaneous Awareness.

Four views:
  1. Share of Mind — TOMA stacked area + bump chart
  2. Brand Deep-Dive — per-brand trends + mention decay curve
  3. Competitive Landscape — salience gap scatter + radar
  4. Data Explorer — sortable table
"""

import numpy as np
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.analytics.spontaneous import (
    calc_decay_curve,
    calc_salience_gap,
    calc_spontaneous_metrics,
    calc_toma_ranks,
    calc_toma_share,
)
from lib.config import CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, BUMP_COLOURS
from lib.state import format_year_month, get_ss_data, render_global_filters

FONT = "Verdana, Geneva, sans-serif"
NAVY = "#1A2B4A"
GOLD = "#B8933A"

# Brand colours for the top insurers
BRAND_COLOURS = {
    "Admiral": "#1A3668", "Aviva": "#FFDD00", "Direct Line": "#E31837",
    "Churchill": "#00A651", "LV": "#00563F", "Hastings": "#00B2A9",
    "Esure": "#6B2D8B", "AXA": "#003399", "NFU Mutual": "#8B6914",
    "Saga": "#C4A000", "AA": "#FFB800", "RAC": "#FF6B00",
    "Tesco": "#00BCD4", "Swinton": "#8BC34A", "Allianz": "#9C27B0",
    "Halifax": "#006B3F", "1st Central": "#FF5722",
    "Sheilas' Wheels": "#E91E63", "Co-op": "#0071CE",
}


def _brand_colour(brand: str, idx: int = 0) -> str:
    return BRAND_COLOURS.get(brand, BUMP_COLOURS[idx % len(BUMP_COLOURS)])


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

st.markdown(
    f'<div style="display:flex; align-items:center; gap:12px; margin-bottom:4px;">'
    f'<div style="width:36px; height:36px; border-radius:8px; background:{NAVY}; '
    f'display:flex; align-items:center; justify-content:center; '
    f'color:{GOLD}; font-size:16px; font-weight:800;">CI</div>'
    f'<div>'
    f'<h1 style="font-size:22px; font-weight:800; color:{NAVY}; margin:0; letter-spacing:-0.3px;">'
    f'Unprompted Brand Awareness</h1>'
    f'<p style="font-size:12px; color:#888; margin:0;">Q1: Spontaneous brand recall (free text)</p>'
    f'</div></div>',
    unsafe_allow_html=True,
)

filters = render_global_filters()
df_motor, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]
df_main = apply_filters(df_motor, product=product, selected_months=selected_months)

# Check for Q1 data
q1_cols = [c for c in df_main.columns if c.startswith("Q1_") and not c.startswith("Q1_{")]
if not q1_cols:
    st.warning("No Q1 spontaneous awareness data available. Q1 data may not have been loaded for this product.")
    st.stop()

# Compute metrics
with st.spinner("Computing spontaneous awareness metrics..."):
    metrics = calc_spontaneous_metrics(df_main)

if metrics.empty:
    st.warning("No spontaneous awareness data available for the selected period.")
    st.stop()

# Period label
months_in_data = sorted(metrics["month"].unique())
period_label = f"{format_year_month(months_in_data[0])} to {format_year_month(months_in_data[-1])}"

st.markdown(
    f'<div style="background:#F2F2F2; border-left:4px solid {NAVY}; '
    f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:14px; color:#333;">'
    f'<b>Period:</b> {period_label} &nbsp;|&nbsp; '
    f'<b>Product:</b> {product} &nbsp;|&nbsp; '
    f'<b>Brands detected:</b> {metrics["brand"].nunique()}'
    f'</div>',
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "Share of Mind", "Brand Deep-Dive", "Competitive Landscape", "Data Explorer"
])

# ---------------------------------------------------------------------------
# Tab 1: Share of Mind
# ---------------------------------------------------------------------------

with tab1:
    col_area, col_bump = st.columns(2)

    # -- TOMA Share stacked area --
    with col_area:
        st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">TOMA Share Over Time</h3>', unsafe_allow_html=True)
        st.caption("Top-of-mind awareness as % of all first mentions")

        share_result = calc_toma_share(metrics, top_n=8)
        if share_result and not share_result[0].empty:
            share_df, top_brands = share_result
            fig_area = go.Figure()

            for brand in reversed(top_brands + ["Other"]):
                if brand not in share_df.columns:
                    continue
                colour = _brand_colour(brand, top_brands.index(brand) if brand in top_brands else 99)
                if brand == "Other":
                    colour = "#cccccc"
                fig_area.add_trace(go.Scatter(
                    x=[format_year_month(m) for m in share_df["month"]],
                    y=share_df[brand],
                    name=brand,
                    mode="lines",
                    stackgroup="one",
                    line=dict(width=0.5, color=colour),
                    fillcolor=colour,
                    hovertemplate=f"<b>{brand}</b><br>TOMA: %{{y:.1f}}%<br>%{{x}}<extra></extra>",
                ))

            fig_area.update_layout(
                yaxis_title="TOMA Share %", height=380,
                font=dict(family=FONT), plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(font_size=10), margin=dict(l=50, r=10, t=10, b=50),
            )
            st.plotly_chart(fig_area, use_container_width=True)
        else:
            st.info("Insufficient data for TOMA share chart.")

    # -- TOMA Bump Chart --
    with col_bump:
        st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">TOMA Rank (Bump Chart)</h3>', unsafe_allow_html=True)
        st.caption("Rank position by top-of-mind share each month")

        rank_result = calc_toma_ranks(metrics, top_n=8)
        if rank_result and not rank_result[0].empty:
            rank_df, top_brands_r = rank_result
            fig_bump = go.Figure()

            for i, brand in enumerate(top_brands_r):
                if brand not in rank_df.columns:
                    continue
                fig_bump.add_trace(go.Scatter(
                    x=[format_year_month(m) for m in rank_df["month"]],
                    y=rank_df[brand],
                    name=brand,
                    mode="lines+markers",
                    line=dict(width=2.5, color=_brand_colour(brand, i)),
                    marker=dict(size=6, color=_brand_colour(brand, i)),
                    hovertemplate=f"<b>{brand}</b><br>Rank: %{{y}}<br>%{{x}}<extra></extra>",
                ))

            fig_bump.update_layout(
                yaxis=dict(autorange="reversed", title="Rank", dtick=1),
                height=380, font=dict(family=FONT),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(font_size=10), margin=dict(l=50, r=10, t=10, b=50),
            )
            st.plotly_chart(fig_bump, use_container_width=True)
        else:
            st.info("Insufficient data for bump chart.")

# ---------------------------------------------------------------------------
# Tab 2: Brand Deep-Dive
# ---------------------------------------------------------------------------

with tab2:
    all_brands = sorted(metrics["brand"].unique().tolist())
    # Default to brand with highest average TOMA
    brand_avg = metrics.groupby("brand")["toma"].mean().sort_values(ascending=False)
    default_brand = brand_avg.index[0] if not brand_avg.empty else all_brands[0]

    selected = st.selectbox("Select brand", all_brands, index=all_brands.index(default_brand) if default_brand in all_brands else 0, key="q1_brand")

    brand_data = metrics[metrics["brand"] == selected].sort_values("month")

    if brand_data.empty:
        st.info(f"No data for {selected}.")
    else:
        latest = brand_data.iloc[-1]
        prev = brand_data.iloc[-2] if len(brand_data) >= 2 else None

        # KPI cards
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            delta = f"{(latest['toma'] - prev['toma']) * 100:+.1f}pp" if prev is not None else None
            st.metric("TOMA", f"{latest['toma']:.1%}", delta=delta)
        with col2:
            delta = f"{(latest['mention'] - prev['mention']) * 100:+.1f}pp" if prev is not None else None
            st.metric("Total Awareness", f"{latest['mention']:.1%}", delta=delta)
        with col3:
            st.metric("Top-3 Rate", f"{latest['top3']:.1%}")
        with col4:
            st.metric("Mean Position", f"{latest['mean_position']:.1f}")

        col_trend, col_decay = st.columns(2)

        # Trend chart
        with col_trend:
            st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">Awareness Trends</h3>', unsafe_allow_html=True)
            st.caption("TOMA, total mention, and top-3 rates over time")

            fig_trend = go.Figure()
            x = [format_year_month(m) for m in brand_data["month"]]
            fig_trend.add_trace(go.Scatter(x=x, y=brand_data["mention"] * 100, name="Total Awareness",
                                            mode="lines+markers", line=dict(color=_brand_colour(selected), width=2.5),
                                            marker=dict(size=4)))
            fig_trend.add_trace(go.Scatter(x=x, y=brand_data["top3"] * 100, name="Top-3 Rate",
                                            mode="lines+markers", line=dict(color=GOLD, width=2, dash="dash"),
                                            marker=dict(size=4)))
            fig_trend.add_trace(go.Scatter(x=x, y=brand_data["toma"] * 100, name="TOMA",
                                            mode="lines+markers", line=dict(color=NAVY, width=2.5),
                                            marker=dict(size=4)))
            fig_trend.update_layout(
                yaxis_title="Rate %", height=300, font=dict(family=FONT),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="top", y=-0.15, font_size=10),
                margin=dict(l=50, r=10, t=10, b=60),
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        # Decay curve
        with col_decay:
            st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">Mention Decay Curve</h3>', unsafe_allow_html=True)
            st.caption("% of respondents mentioning at each position slot")

            decay = calc_decay_curve(df_main, selected, selected_months)
            if not decay.empty:
                colours = [NAVY if p == 1 else GOLD if p <= 3 else "rgba(26,43,74,0.25)" for p in decay["position"]]
                fig_decay = go.Figure(go.Bar(
                    x=decay["position"], y=decay["pct"],
                    marker_color=colours,
                    text=[f"{v:.1f}%" for v in decay["pct"]],
                    textposition="outside",
                    hovertemplate="Position %{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_decay.update_layout(
                    xaxis_title="Mention Position", yaxis_title="% of respondents",
                    height=300, font=dict(family=FONT),
                    plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=50, r=10, t=10, b=60),
                )
                st.plotly_chart(fig_decay, use_container_width=True)
            else:
                st.info("No decay data available.")

# ---------------------------------------------------------------------------
# Tab 3: Competitive Landscape
# ---------------------------------------------------------------------------

with tab3:
    month_options = sorted(metrics["month"].unique().astype(int).tolist())
    selected_month = st.select_slider(
        "Month", options=month_options, value=month_options[-1],
        format_func=lambda m: format_year_month(m), key="landscape_month",
    )

    col_scatter, col_radar = st.columns(2)

    # Salience gap scatter
    with col_scatter:
        st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">Salience Gap Analysis</h3>', unsafe_allow_html=True)
        st.caption("X = total awareness, Y = TOMA. Above diagonal = punching above weight.")

        gap = calc_salience_gap(metrics, selected_month)
        if not gap.empty:
            fig_scatter = go.Figure()
            for i, (_, row) in enumerate(gap.iterrows()):
                fig_scatter.add_trace(go.Scatter(
                    x=[row["mention_pct"] * 100], y=[row["toma_pct"] * 100],
                    mode="markers+text",
                    marker=dict(size=12, color=_brand_colour(row["brand"], i)),
                    text=[row["brand"]], textposition="top center",
                    textfont=dict(size=9, color=CI_GREY),
                    name=row["brand"],
                    hovertemplate=(
                        f"<b>{row['brand']}</b><br>"
                        f"Total: {row['mention_pct'] * 100:.1f}%<br>"
                        f"TOMA: {row['toma_pct'] * 100:.1f}%<br>"
                        f"Mean Pos: {row['mean_position']:.1f}<extra></extra>"
                    ),
                    showlegend=False,
                ))

            # Reference diagonal
            max_val = max(gap["mention_pct"].max() * 100, gap["toma_pct"].max() * 100) + 5
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_val], y=[0, max_val],
                mode="lines", line=dict(color=CI_GREY, dash="dot", width=1),
                showlegend=False, hoverinfo="skip",
            ))

            fig_scatter.update_layout(
                xaxis_title="Total Awareness %", yaxis_title="TOMA %",
                height=400, font=dict(family=FONT),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=50, r=10, t=10, b=60),
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("No data for selected month.")

    # Radar chart (top 5)
    with col_radar:
        st.markdown(f'<h3 style="font-size:15px; font-weight:700; color:{NAVY}; margin:0 0 6px;">Top 5 Radar</h3>', unsafe_allow_html=True)
        st.caption("Normalised awareness metrics for top 5 brands")

        month_data = metrics[metrics["month"] == selected_month]
        if not month_data.empty:
            top5 = month_data.sort_values("toma", ascending=False).head(5)
            categories = ["TOMA", "Total Awareness", "Top-3 Rate"]
            max_vals = {
                "TOMA": top5["toma"].max(),
                "Total Awareness": top5["mention"].max(),
                "Top-3 Rate": top5["top3"].max(),
            }

            fig_radar = go.Figure()
            for i, (_, row) in enumerate(top5.iterrows()):
                vals = [
                    row["toma"] / max_vals["TOMA"] * 100 if max_vals["TOMA"] > 0 else 0,
                    row["mention"] / max_vals["Total Awareness"] * 100 if max_vals["Total Awareness"] > 0 else 0,
                    row["top3"] / max_vals["Top-3 Rate"] * 100 if max_vals["Top-3 Rate"] > 0 else 0,
                ]
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],  # close the polygon
                    theta=categories + [categories[0]],
                    name=row["brand"],
                    line=dict(color=_brand_colour(row["brand"], i), width=2),
                    fill="toself", fillcolor=_brand_colour(row["brand"], i),
                    opacity=0.15,
                ))

            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 105], tickfont_size=9)),
                height=400, font=dict(family=FONT),
                legend=dict(font_size=10),
                margin=dict(l=60, r=60, t=30, b=30),
            )
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("No data for selected month.")

# ---------------------------------------------------------------------------
# Tab 4: Data Explorer
# ---------------------------------------------------------------------------

with tab4:
    explorer_month = st.selectbox(
        "Month", month_options, index=len(month_options) - 1,
        format_func=lambda m: format_year_month(m), key="explorer_month",
    )

    month_data = metrics[metrics["month"] == explorer_month].copy()
    if not month_data.empty:
        display = month_data[["brand", "toma", "mention", "top3", "mean_position", "n_toma", "n_mention", "n_total"]].copy()
        display["toma"] = (display["toma"] * 100).round(1)
        display["mention"] = (display["mention"] * 100).round(1)
        display["top3"] = (display["top3"] * 100).round(1)
        display["mean_position"] = display["mean_position"].round(1)
        display.columns = ["Brand", "TOMA %", "Total Awareness %", "Top-3 %", "Mean Position", "TOMA n", "Mention n", "Base n"]
        display = display.sort_values("TOMA %", ascending=False).reset_index(drop=True)

        st.dataframe(display, use_container_width=True, hide_index=True)
        st.caption(f"Base: {int(month_data['n_total'].iloc[0]):,} respondents who mentioned at least one brand")
    else:
        st.info("No data for selected month.")

# Footer
st.caption(
    f"Q1: Spontaneous brand awareness (free text) | {period_label} | "
    f"{metrics['brand'].nunique()} brands | {product}"
)
