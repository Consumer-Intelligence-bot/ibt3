"""
Unprompted Brand Awareness — Q1 Spontaneous Awareness.

Four views:
  1. Share of Mind — TOMA stacked area + bump chart
  2. Brand Deep-Dive — per-brand trends + mention decay curve
  3. Competitive Landscape — salience gap scatter + radar
  4. Data Explorer — sortable table
"""

import pandas as pd
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
from lib.chart_export import apply_export_metadata
from lib.config import (
    BUMP_COLOURS,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    MARKET_COLOUR,
)
from lib.formatting import FONT, render_header, card_html, section_divider
from lib.state import format_year_month, get_ss_data, render_global_filters

_card_html = card_html
_section_divider = section_divider


def _brand_colour(brand: str, idx: int = 0) -> str:
    return BUMP_COLOURS[idx % len(BUMP_COLOURS)]


# ---------------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------------

render_header()
st.header("Unprompted Brand Awareness")

filters = render_global_filters()
df_motor, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded. Check Power BI connection.")
    st.stop()

product = filters["product"]
if product == "Pet":
    st.info("Unprompted awareness is not available for Pet insurance (coming in 2026 survey).")
    st.stop()

product = filters["product"]
selected_months = filters["selected_months"]
df_main = apply_filters(df_motor, product=product, selected_months=selected_months)

n = len(df_main)
if n == 0:
    st.warning("No data for selected filters.")
    st.stop()

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
min_ym = months_in_data[0]
max_ym = months_in_data[-1]
period_label = f"{format_year_month(min_ym)} to {format_year_month(max_ym)}"

# Active period banner
st.markdown(
    f'<div style="background:#F2F2F2; border-left:4px solid {CI_MAGENTA}; '
    f'padding:10px 16px; margin-bottom:16px; font-family:{FONT}; font-size:14px; '
    f'color:#333;">'
    f'<b>Active period:</b> {period_label} &nbsp;|&nbsp; '
    f'<b>Product:</b> {product or "All"} &nbsp;|&nbsp; '
    f'<b>Base:</b> n\u2009=\u2009{n:,} &nbsp;|&nbsp; '
    f'<b>Brands detected:</b> {metrics["brand"].nunique()}'
    f'</div>',
    unsafe_allow_html=True,
)

# Summary KPIs
latest_month = metrics["month"].max()
latest = metrics[metrics["month"] == latest_month]
if not latest.empty:
    top_brand = latest.loc[latest["toma"].idxmax()]
    avg_mention = latest["mention"].mean()
    n_brands = latest["brand"].nunique()

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(
            _card_html("Top of Mind Leader", top_brand["brand"],
                       f"TOMA: {top_brand['toma']:.1%}", CI_MAGENTA),
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            _card_html("Brands Tracked", f"{n_brands}", "", CI_GREY),
            unsafe_allow_html=True,
        )
    with col3:
        st.markdown(
            _card_html("Avg Mention Rate", f"{avg_mention:.1%}",
                       f"Across {n_brands} brands", MARKET_COLOUR),
            unsafe_allow_html=True,
        )
    with col4:
        st.markdown(
            _card_html("Data Period", format_year_month(latest_month),
                       f"n = {int(top_brand['n_total']):,}", CI_GREY),
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
    # ---- TOMA Share — stacked area (full width, normalised to 100%) ----
    share_result = calc_toma_share(metrics, top_n=8)
    if share_result and not share_result[0].empty:
        share_df, top_brands = share_result

        # Normalise each row so stacked areas sum to 100%
        brand_cols = [b for b in top_brands + ["Other"] if b in share_df.columns]
        row_totals = share_df[brand_cols].sum(axis=1)
        share_norm = share_df.copy()
        for col in brand_cols:
            share_norm[col] = share_df[col] / row_totals * 100

        fig_area = go.Figure()
        for i, brand in enumerate(reversed(top_brands + ["Other"])):
            if brand not in share_norm.columns:
                continue
            colour = CI_LIGHT_GREY if brand == "Other" else _brand_colour(brand, len(top_brands) - 1 - i)
            fig_area.add_trace(go.Scatter(
                x=[format_year_month(m) for m in share_norm["month"]],
                y=share_norm[brand],
                name=brand,
                mode="lines",
                stackgroup="one",
                groupnorm="",
                line=dict(width=0.5, color=colour),
                fillcolor=colour,
                hovertemplate=f"<b>{brand}</b><br>Share: %{{y:.1f}}%<br>%{{x}}<extra></extra>",
            ))

        # Direct on-chart labels at last data point for each brand
        x_labels = [format_year_month(m) for m in share_norm["month"]]
        last_x = x_labels[-1]
        annotations = []
        for i, brand in enumerate(reversed(top_brands + ["Other"])):
            if brand not in share_norm.columns:
                continue
            last_y = share_norm[brand].iloc[-1]
            # Stack midpoint: sum of all series below + half of this one
            below_brands = list(reversed(top_brands + ["Other"]))[:list(reversed(top_brands + ["Other"])).index(brand)]
            cumulative = sum(share_norm[b].iloc[-1] for b in below_brands if b in share_norm.columns)
            mid_y = cumulative + last_y / 2
            if last_y > 3:  # Only label if slice is wide enough to read
                annotations.append(dict(
                    x=last_x, y=mid_y,
                    text=f"<b>{brand}</b> {last_y:.0f}%",
                    showarrow=False, xanchor="left", xshift=6,
                    font=dict(family=FONT, size=10, color="#333"),
                ))

        fig_area.update_layout(
            yaxis=dict(title="TOMA Share %", ticksuffix="%", range=[0, 100]),
            xaxis=dict(tickangle=0),
            height=520, font=dict(family=FONT, size=12),
            plot_bgcolor="white", paper_bgcolor="white",
            showlegend=False,
            margin=dict(l=50, r=120, t=40, b=50),
            annotations=annotations,
        )
        apply_export_metadata(
            fig_area, title="TOMA Share Over Time",
            period=period_label, base=n, question="Q1",
            subtitle="Top-of-mind awareness as % of all first mentions (normalised to 100%)",
        )
        st.plotly_chart(fig_area, use_container_width=True)
    else:
        st.info("Insufficient data for TOMA share chart.")

    # ---- TOMA Rank — bump chart (full width, cleaner) ----
    rank_result = calc_toma_ranks(metrics, top_n=8)
    if rank_result and not rank_result[0].empty:
        rank_df, top_brands_r = rank_result
        fig_bump = go.Figure()

        for i, brand in enumerate(top_brands_r):
            if brand not in rank_df.columns:
                continue
            colour = _brand_colour(brand, i)
            fig_bump.add_trace(go.Scatter(
                x=[format_year_month(m) for m in rank_df["month"]],
                y=rank_df[brand],
                name=brand,
                mode="lines+markers",
                line=dict(width=2.5, color=colour),
                marker=dict(size=7, color=colour),
                hovertemplate=f"<b>{brand}</b><br>Rank: %{{y}}<br>%{{x}}<extra></extra>",
            ))

        max_rank = int(rank_df[top_brands_r].max().max()) if not rank_df.empty else 8
        bump_height = max(500, 300 + max_rank * 30)
        fig_bump.update_layout(
            yaxis=dict(autorange="reversed", title="Rank", dtick=1,
                       range=[0.5, max_rank + 0.5],
                       gridcolor=CI_LIGHT_GREY, gridwidth=0.5),
            xaxis=dict(tickangle=0),
            height=bump_height, font=dict(family=FONT, size=12),
            plot_bgcolor="white", paper_bgcolor="white",
            legend=dict(font_size=11, orientation="v", yanchor="top", y=1,
                        xanchor="left", x=1.02, tracegroupgap=2),
            margin=dict(l=50, r=140, t=40, b=50),
        )
        apply_export_metadata(
            fig_bump, title="TOMA Rank — Bump Chart",
            period=period_label, base=n, question="Q1",
        )
        st.plotly_chart(fig_bump, use_container_width=True)
    else:
        st.info("Insufficient data for bump chart.")

# ---------------------------------------------------------------------------
# Tab 2: Brand Deep-Dive
# ---------------------------------------------------------------------------

with tab2:
    all_brands = sorted(metrics["brand"].unique().tolist())
    brand_avg = metrics.groupby("brand")["toma"].mean().sort_values(ascending=False)
    default_brand = brand_avg.index[0] if not brand_avg.empty else all_brands[0]

    selected = st.selectbox(
        "Select brand", all_brands,
        index=all_brands.index(default_brand) if default_brand in all_brands else 0,
        key="q1_brand",
    )

    brand_data = metrics[metrics["brand"] == selected].sort_values("month")

    if brand_data.empty:
        st.info(f"No data for {selected}.")
    else:
        latest_b = brand_data.iloc[-1]
        prev_b = brand_data.iloc[-2] if len(brand_data) >= 2 else None

        # KPI cards
        col1, col2, col3, col4 = st.columns(4)
        toma_delta = (latest_b["toma"] - prev_b["toma"]) * 100 if prev_b is not None else None
        mention_delta = (latest_b["mention"] - prev_b["mention"]) * 100 if prev_b is not None else None

        with col1:
            sub = f"{toma_delta:+.1f}pp vs prev" if toma_delta is not None else ""
            st.markdown(
                _card_html("TOMA", f"{latest_b['toma']:.1%}", sub, CI_MAGENTA),
                unsafe_allow_html=True,
            )
        with col2:
            sub = f"{mention_delta:+.1f}pp vs prev" if mention_delta is not None else ""
            st.markdown(
                _card_html("Total Awareness", f"{latest_b['mention']:.1%}", sub, MARKET_COLOUR),
                unsafe_allow_html=True,
            )
        with col3:
            st.markdown(
                _card_html("Top-3 Rate", f"{latest_b['top3']:.1%}", "", CI_GREEN),
                unsafe_allow_html=True,
            )
        with col4:
            st.markdown(
                _card_html("Mean Position", f"{latest_b['mean_position']:.1f}", "Lower = more salient", CI_GREY),
                unsafe_allow_html=True,
            )

        col_trend, col_decay = st.columns(2)

        with col_trend:
            _section_divider("Awareness Trends")
            st.caption("TOMA, total mention, and top-3 rates over time")

            fig_trend = go.Figure()
            x = [format_year_month(m) for m in brand_data["month"]]
            fig_trend.add_trace(go.Scatter(
                x=x, y=brand_data["mention"] * 100, name="Total Awareness",
                mode="lines+markers", line=dict(color=CI_MAGENTA, width=2.5),
                marker=dict(size=6, color=CI_MAGENTA),
                hovertemplate="Total: %{y:.1f}%<br>%{x}<extra></extra>",
            ))
            fig_trend.add_trace(go.Scatter(
                x=x, y=brand_data["top3"] * 100, name="Top-3 Rate",
                mode="lines+markers", line=dict(color=CI_GREEN, width=2, dash="dash"),
                marker=dict(size=6, color=CI_GREEN),
                hovertemplate="Top-3: %{y:.1f}%<br>%{x}<extra></extra>",
            ))
            fig_trend.add_trace(go.Scatter(
                x=x, y=brand_data["toma"] * 100, name="TOMA",
                mode="lines+markers", line=dict(color=MARKET_COLOUR, width=2.5),
                marker=dict(size=6, color=MARKET_COLOUR),
                hovertemplate="TOMA: %{y:.1f}%<br>%{x}<extra></extra>",
            ))
            fig_trend.update_layout(
                yaxis=dict(title="Rate %", ticksuffix="%"),
                xaxis=dict(tickangle=0),
                height=380, font=dict(family=FONT, size=12),
                plot_bgcolor="white", paper_bgcolor="white",
                legend=dict(orientation="h", yanchor="top", y=-0.12,
                            xanchor="center", x=0.5, font_size=10),
                margin=dict(l=50, r=20, t=30, b=80),
            )
            apply_export_metadata(
                fig_trend, title=f"{selected} — Awareness Trends",
                period=period_label, base=int(latest_b["n_total"]), question="Q1",
            )
            st.plotly_chart(fig_trend, use_container_width=True)

        with col_decay:
            _section_divider("Mention Decay Curve")
            st.caption("% of respondents mentioning at each position slot")

            decay = calc_decay_curve(df_main, selected, selected_months)
            if not decay.empty:
                colours = [
                    CI_MAGENTA if p == 1 else CI_GREEN if p <= 3 else CI_LIGHT_GREY
                    for p in decay["position"]
                ]
                fig_decay = go.Figure(go.Bar(
                    x=decay["position"], y=decay["pct"],
                    marker_color=colours,
                    text=[f"{v:.1f}%" for v in decay["pct"]],
                    textposition="outside",
                    textfont=dict(family=FONT, size=11),
                    hovertemplate="Position %{x}: %{y:.1f}%<extra></extra>",
                ))
                fig_decay.update_layout(
                    xaxis=dict(title="Mention Position", dtick=1),
                    yaxis=dict(title="% of respondents", ticksuffix="%"),
                    height=380, font=dict(family=FONT, size=12),
                    plot_bgcolor="white", paper_bgcolor="white",
                    margin=dict(l=50, r=20, t=30, b=80),
                )
                apply_export_metadata(
                    fig_decay, title=f"{selected} — Mention Decay Curve",
                    period=period_label, base=int(latest_b["n_total"]), question="Q1",
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

    with col_scatter:
        _section_divider("Salience Gap Analysis")
        st.caption("X = total awareness, Y = TOMA. Above diagonal = punching above weight.")

        gap = calc_salience_gap(metrics, selected_month)
        if not gap.empty:
            # Only show top 15 brands for readability
            gap = gap.sort_values("mention_pct", ascending=False).head(15)

            fig_scatter = go.Figure()
            for i, (_, row) in enumerate(gap.iterrows()):
                fig_scatter.add_trace(go.Scatter(
                    x=[row["mention_pct"] * 100], y=[row["toma_pct"] * 100],
                    mode="markers+text",
                    marker=dict(size=10, color=_brand_colour(row["brand"], i),
                                line=dict(width=1, color="white")),
                    text=[row["brand"]], textposition="top center",
                    textfont=dict(size=9, color=CI_GREY, family=FONT),
                    name=row["brand"],
                    hovertemplate=(
                        f"<b>{row['brand']}</b><br>"
                        f"Total: {row['mention_pct'] * 100:.1f}%<br>"
                        f"TOMA: {row['toma_pct'] * 100:.1f}%<br>"
                        f"Mean Pos: {row['mean_position']:.1f}<extra></extra>"
                    ),
                    showlegend=False,
                ))

            max_val = max(gap["mention_pct"].max() * 100, gap["toma_pct"].max() * 100) + 5
            fig_scatter.add_trace(go.Scatter(
                x=[0, max_val], y=[0, max_val],
                mode="lines", line=dict(color=CI_LIGHT_GREY, dash="dot", width=1),
                showlegend=False, hoverinfo="skip",
            ))

            fig_scatter.update_layout(
                xaxis=dict(title="Total Awareness %", ticksuffix="%"),
                yaxis=dict(title="TOMA %", ticksuffix="%"),
                height=420, font=dict(family=FONT, size=12),
                plot_bgcolor="white", paper_bgcolor="white",
                margin=dict(l=50, r=20, t=30, b=80),
            )
            apply_export_metadata(
                fig_scatter, title="Salience Gap Analysis",
                period=format_year_month(selected_month), base=n, question="Q1",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)
        else:
            st.info("No data for selected month.")

    with col_radar:
        _section_divider("Top 5 Radar")
        st.caption("Normalised awareness metrics for top 5 brands")

        month_data = metrics[metrics["month"] == selected_month]
        if not month_data.empty:
            top5 = month_data.sort_values("toma", ascending=False).head(5)
            categories = ["TOMA", "Total Awareness", "Top-3 Rate"]
            max_vals = {
                "TOMA": max(top5["toma"].max(), 0.001),
                "Total Awareness": max(top5["mention"].max(), 0.001),
                "Top-3 Rate": max(top5["top3"].max(), 0.001),
            }

            fig_radar = go.Figure()
            for i, (_, row) in enumerate(top5.iterrows()):
                vals = [
                    row["toma"] / max_vals["TOMA"] * 100,
                    row["mention"] / max_vals["Total Awareness"] * 100,
                    row["top3"] / max_vals["Top-3 Rate"] * 100,
                ]
                colour = _brand_colour(row["brand"], i)
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=categories + [categories[0]],
                    name=row["brand"],
                    line=dict(color=colour, width=2),
                    fill="toself", fillcolor=colour,
                    opacity=0.12,
                ))

            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(visible=True, range=[0, 105],
                                    tickfont=dict(size=9, color=CI_GREY)),
                    angularaxis=dict(tickfont=dict(size=11, color=CI_GREY)),
                ),
                height=420, font=dict(family=FONT),
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
    _section_divider("Spontaneous Awareness Data")

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
        display.columns = [
            "Brand", "TOMA %", "Total Awareness %", "Top-3 %",
            "Mean Position", "TOMA n", "Mention n", "Base n",
        ]
        display = display.sort_values("TOMA %", ascending=False).reset_index(drop=True)

        st.dataframe(display, use_container_width=True, hide_index=True)
        st.caption(
            f"Base: {int(month_data['n_total'].iloc[0]):,} respondents who mentioned at least one brand | "
            f"Source: Q1 spontaneous recall"
        )
    else:
        st.info("No data for selected month.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------

st.caption(
    f"Data period: {period_label} | n = {n:,} | "
    f"Q1: Spontaneous brand awareness (free text) | "
    f"\u00a9 Consumer Intelligence 2026"
)
