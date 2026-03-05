"""
Plotly chart wrapper with CI brand standards (Spec Section 11).
"""
from __future__ import annotations

import plotly.graph_objects as go
import plotly.io as pio

from config import (
    BUMP_COLOURS,
    CI_BLUE,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_YELLOW,
)

_FONT = "Verdana, Geneva, sans-serif"


def _create_ci_template():
    """Register CI brand template with Plotly."""
    ci_template = go.layout.Template(
        layout=go.Layout(
            font=dict(family=_FONT, color=CI_GREY, size=12),
            plot_bgcolor="white",
            paper_bgcolor="white",
            colorway=[CI_MAGENTA, CI_GREY, CI_GREEN, CI_RED, CI_BLUE, CI_YELLOW],
            title_font=dict(size=16, color=CI_GREY, family=_FONT),
            xaxis=dict(
                showgrid=False,
                zeroline=False,
                tickfont=dict(size=11),
            ),
            yaxis=dict(
                gridcolor=CI_LIGHT_GREY,
                gridwidth=1,
                zeroline=False,
                tickfont=dict(size=11),
            ),
        )
    )
    pio.templates["ci_brand"] = ci_template


_create_ci_template()
pio.templates.default = "ci_brand"


def create_branded_figure(
    fig: go.Figure,
    title: str = "",
    show_market_line: bool = False,
    market_value: float | None = None,
    market_label: str | None = None,
) -> go.Figure:
    """Apply CI branding to a Plotly figure with optional market reference line."""
    fig.update_layout(
        template="ci_brand",
        title=title,
        font=dict(family=_FONT, color=CI_GREY),
        margin=dict(l=50, r=20, t=50, b=40),
    )
    if show_market_line and market_value is not None:
        label = market_label or f"Market: {market_value:.0%}"
        fig.add_hline(
            y=market_value,
            line_dash="dash",
            line_color=CI_GREY,
            line_width=1.5,
            annotation_text=label,
            annotation_font_size=11,
            annotation_font_color=CI_GREY,
        )
    return fig


def create_bump_chart(
    df,
    x_col: str = "month",
    y_col: str = "rank",
    brand_col: str = "brand",
    title: str = "",
) -> go.Figure:
    """
    Bump chart: rank over time, one line per brand.

    Y axis inverted (1 = top). Colours from BUMP_COLOURS sequence.
    Gaps where data is missing (no interpolation).
    """
    fig = go.Figure()
    brands = df[brand_col].unique()

    for i, brand in enumerate(brands):
        brand_data = df[df[brand_col] == brand].sort_values(x_col)
        colour = BUMP_COLOURS[i % len(BUMP_COLOURS)]
        fig.add_trace(go.Scatter(
            x=brand_data[x_col],
            y=brand_data[y_col],
            mode="lines+markers",
            name=brand,
            line=dict(color=colour, width=2.5),
            marker=dict(size=7, color=colour),
            connectgaps=False,
            hovertemplate=f"<b>{brand}</b><br>Rank: %{{y}}<br>%{{x}}<extra></extra>",
        ))

    fig.update_layout(
        template="ci_brand",
        title=title,
        font=dict(family=_FONT, color=CI_GREY),
        margin=dict(l=50, r=20, t=50, b=40),
        yaxis=dict(
            autorange="reversed",
            dtick=1,
            title="Rank",
            gridcolor=CI_LIGHT_GREY,
        ),
        xaxis=dict(title=""),
        legend=dict(
            orientation="h",
            yanchor="top",
            y=-0.15,
            font=dict(size=11),
        ),
        hovermode="x unified",
    )
    return fig


def add_ci_whiskers(
    fig: go.Figure,
    x_values,
    y_values,
    ci_lower,
    ci_upper,
    colour: str = CI_MAGENTA,
    name: str = "",
    horizontal: bool = False,
) -> go.Figure:
    """Add error bars (CI whiskers) to a bar or scatter chart.

    For horizontal bar charts (orientation="h"), set horizontal=True so the
    whiskers are drawn along the x-axis using error_x instead of error_y.
    """
    ci_lower = [float(v) for v in ci_lower]
    ci_upper = [float(v) for v in ci_upper]

    if horizontal:
        x_num = [float(v) for v in x_values]
        error_kwarg = dict(error_x=dict(
            type="data",
            symmetric=False,
            array=[u - x for u, x in zip(ci_upper, x_num)],
            arrayminus=[x - l for l, x in zip(ci_lower, x_num)],
            color=colour,
            thickness=1.5,
            width=4,
        ))
    else:
        y_num = [float(v) for v in y_values]
        error_kwarg = dict(error_y=dict(
            type="data",
            symmetric=False,
            array=[u - y for u, y in zip(ci_upper, y_num)],
            arrayminus=[y - l for l, y in zip(ci_lower, y_num)],
            color=colour,
            thickness=1.5,
            width=4,
        ))

    fig.add_trace(go.Scatter(
        x=x_values,
        y=y_values,
        **error_kwarg,
        mode="markers",
        marker=dict(size=0, color=colour),
        name=name,
        showlegend=False,
        hoverinfo="skip",
    ))
    return fig
