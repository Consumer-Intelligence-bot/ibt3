"""
Cohort heat map component with directional colouring.

Rows: demographic segments (Age Band, Region, Payment Type).
Columns: metrics (Shopping, Switching, Retention).
Cells: delta vs market in pp, colour-coded green (above) / red (below).
"""

import pandas as pd
import streamlit as st

from lib.config import CI_GREEN, CI_GREY, CI_LIGHT_GREY, CI_RED, MIN_BASE_INDICATIVE
from lib.formatting import FONT


def render_cohort_heatmap(heatmap_df: pd.DataFrame, insurer: str | None = None):
    """Render the cohort heat map from calc_cohort_heatmap() output.

    Parameters
    ----------
    heatmap_df : pd.DataFrame
        Output of calc_cohort_heatmap(). Columns: segment_field, segment_value,
        metric, insurer_rate, market_rate, delta, insurer_n, market_n, suppressed.
    insurer : str | None
        Insurer name for the caption. If None, shows market-only message.
    """
    if heatmap_df.empty:
        st.caption("No demographic data available for cohort analysis.")
        return

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
        header = (
            f'<table style="width:100%; font-family:{FONT}; font-size:12px; '
            f'border-collapse:collapse;">'
            f'<tr style="border-bottom:2px solid {CI_LIGHT_GREY};">'
            f'<th style="text-align:left; padding:6px 8px; color:{CI_GREY};">Segment</th>'
        )
        for m in metrics:
            header += f'<th style="text-align:center; padding:6px 8px; color:{CI_GREY};">{m}</th>'
        header += "</tr>"

        rows_html = ""
        for seg in segments:
            rows_html += f'<tr style="border-bottom:1px solid {CI_LIGHT_GREY};">'
            rows_html += f'<td style="padding:6px 8px; color:{CI_GREY};">{seg}</td>'
            for m in metrics:
                cell = field_data[
                    (field_data["segment_value"] == seg) & (field_data["metric"] == m)
                ]
                if len(cell) == 0 or cell.iloc[0]["suppressed"]:
                    rows_html += (
                        f'<td style="text-align:center; padding:6px 8px; font-size:10px; '
                        f'color:{CI_LIGHT_GREY};">Suppressed (n &lt; {MIN_BASE_INDICATIVE})</td>'
                    )
                else:
                    delta = cell.iloc[0]["delta"]
                    if delta is not None:
                        if delta > 2:
                            bg = "rgba(72, 162, 63, 0.15)"
                            fg = CI_GREEN
                        elif delta < -2:
                            bg = "rgba(244, 54, 76, 0.15)"
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
                        rows_html += (
                            f'<td style="text-align:center; padding:6px 8px; '
                            f'color:{CI_LIGHT_GREY};">\u2014</td>'
                        )
            rows_html += "</tr>"

        st.markdown(header + rows_html + "</table>", unsafe_allow_html=True)

    label = f"{insurer} vs market" if insurer else "Market segments"
    st.caption(
        f"{label}. Cells show insurer rate minus market rate (pp). "
        f"Suppressed where insurer segment n < {MIN_BASE_INDICATIVE}."
    )
