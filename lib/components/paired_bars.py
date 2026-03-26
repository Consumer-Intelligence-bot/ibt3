"""
Reusable insurer-vs-market paired horizontal bar chart.

Insurer bar in CI_PURPLE, market bar in CI_CHARCOAL, sorted descending.
"""

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.config import CI_CHARCOAL, CI_CHARCOAL_20, CI_PURPLE, CI_WHITE, FONT

# Legacy aliases
CI_GREY = CI_CHARCOAL
CI_LIGHT_GREY = CI_CHARCOAL_20
CI_VIOLET = CI_PURPLE


def paired_bar_chart(
    labels: list[str],
    insurer_values: list[float],
    market_values: list[float],
    *,
    insurer_label: str = "Insurer",
    market_label: str = "Market",
    value_format: str = ".1%",
    title: str = "",
    height: int | None = None,
    insurer_colour: str = CI_VIOLET,
    market_colour: str = CI_GREY,
):
    """Render a paired horizontal bar chart (insurer vs market).

    Parameters
    ----------
    labels : list[str]
        Category labels (y-axis).
    insurer_values, market_values : list[float]
        Values for each category.
    value_format : str
        Python format spec for hover/text values.
    """
    if not labels:
        st.info("No data available for this chart.")
        return

    # Sort descending by insurer values
    sorted_data = sorted(
        zip(labels, insurer_values, market_values),
        key=lambda x: x[1],
    )
    labels_sorted = [d[0] for d in sorted_data]
    ins_sorted = [d[1] for d in sorted_data]
    mkt_sorted = [d[2] for d in sorted_data]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            y=labels_sorted,
            x=mkt_sorted,
            orientation="h",
            name=market_label,
            marker_color=market_colour,
            opacity=0.5,
            text=[f"{v:{value_format}}" for v in mkt_sorted],
            textposition="outside",
        )
    )

    fig.add_trace(
        go.Bar(
            y=labels_sorted,
            x=ins_sorted,
            orientation="h",
            name=insurer_label,
            marker_color=insurer_colour,
            text=[f"{v:{value_format}}" for v in ins_sorted],
            textposition="outside",
        )
    )

    chart_height = height or max(300, len(labels) * 40 + 80)
    fig.update_layout(
        barmode="group",
        height=chart_height,
        title=dict(text=f"<b>{title}</b>", font=dict(family=FONT, size=13)) if title else None,
        xaxis=dict(gridcolor=CI_LIGHT_GREY, tickformat=value_format),
        yaxis=dict(title=""),
        plot_bgcolor=CI_WHITE,
        paper_bgcolor=CI_WHITE,
        font=dict(family=FONT, size=11, color=CI_GREY),
        margin=dict(l=10, r=80, t=40 if title else 20, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)
