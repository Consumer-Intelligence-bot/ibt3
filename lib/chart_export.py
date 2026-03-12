"""
Export-readiness utilities for Plotly charts.

Every chart must be usable as a static image in a board pack without manual
annotation. This module adds title, period, base size, and question reference
to any Plotly figure (Spec Section 15).
"""
from __future__ import annotations

import plotly.graph_objects as go

from lib.question_ref import QUESTION_WORDING

# Re-export for backward compatibility (chart footers use shorter refs)
QUESTION_REF = {k: f"{k}: {v}" for k, v in QUESTION_WORDING.items()}

# ---------------------------------------------------------------------------
# Tooltip heading helper — renders a section heading with an (i) icon
# that shows the underlying survey question on hover.
# ---------------------------------------------------------------------------

_TOOLTIP_CSS = (
    "display:inline-block; margin-left:8px; width:18px; height:18px; "
    "border-radius:50%; background:#E9EAEB; text-align:center; "
    "line-height:18px; font-size:11px; font-weight:bold; color:#54585A; "
    "cursor:help; vertical-align:middle; font-style:normal;"
)


def heading_with_tooltip(title: str, q_code: str | None = None, level: str = "subheader") -> str:
    """Return HTML for a section heading with an (i) tooltip showing the question wording.

    Parameters
    ----------
    title : str
        The visible heading text.
    q_code : str | None
        Question code (e.g. "Q8"). If None or not found, no tooltip is shown.
    level : str
        Visual size: "header" (h2), "subheader" (h3), or "small" (h4).

    Returns
    -------
    str
        HTML string — call st.markdown(..., unsafe_allow_html=True) to render.
    """
    tag = {"header": "h2", "subheader": "h3", "small": "h4"}.get(level, "h3")
    font_size = {"header": "22px", "subheader": "17px", "small": "15px"}.get(level, "17px")

    tooltip_html = ""
    if q_code:
        wording = QUESTION_WORDING.get(q_code, "")
        if wording:
            # Escape quotes for HTML title attribute
            escaped = wording.replace('"', '&quot;').replace("'", "&#39;")
            tooltip_html = (
                f'<span style="{_TOOLTIP_CSS}" title="{escaped}">i</span>'
            )

    return (
        f'<{tag} style="font-family:Verdana,sans-serif; font-size:{font_size}; '
        f'color:#54585A; margin:24px 0 12px 0; font-weight:bold;">'
        f'{title}{tooltip_html}</{tag}>'
    )


def apply_export_metadata(
    fig: go.Figure,
    *,
    title: str,
    period: str,
    base: int | str,
    question: str | None = None,
    subtitle: str | None = None,
) -> go.Figure:
    """Add export-ready metadata to a Plotly figure.

    Adds title, period, base size, and question reference as annotations
    that are visible both interactively and in static exports.
    """
    # Build title text
    title_parts = [f"<b>{title}</b>"]
    if subtitle:
        title_parts.append(f"<br><span style='font-size:11px;color:#54585A'>{subtitle}</span>")

    fig.update_layout(
        title=dict(
            text="".join(title_parts),
            font=dict(family="Verdana", size=13),
            x=0,
            xanchor="left",
        ),
    )

    # Build footer text
    base_str = f"n={base:,}" if isinstance(base, int) else f"n={base}"
    footer_parts = [period, base_str]
    if question:
        q_ref = QUESTION_REF.get(question, question)
        footer_parts.append(q_ref)
    footer_text = " | ".join(footer_parts)

    # Add footer annotation
    fig.add_annotation(
        text=footer_text,
        xref="paper", yref="paper",
        x=0, y=-0.15,
        xanchor="left", yanchor="top",
        showarrow=False,
        font=dict(family="Verdana", size=9, color="#54585A"),
    )

    return fig


def suppression_message(entity: str, n: int, min_base: int = 50) -> str:
    """Standard suppression message per spec Section 17.3."""
    return (
        f"Insufficient data for {entity}. "
        f"Minimum {min_base} renewals required. "
        f"{n} responses available in the selected period."
    )


def render_suppression_html(entity: str, n: int, min_base: int = 50) -> str:
    """Render suppression message as styled HTML per spec Section 17.3."""
    msg = suppression_message(entity, n, min_base)
    return (
        f'<div style="background:#E9EAEB; border-left:4px solid #FFCD00; '
        f'padding:12px 16px; margin:8px 0; font-family:Verdana; font-size:13px; '
        f'color:#54585A;">{msg}</div>'
    )


def confidence_tooltip(context: str) -> str:
    """Plain-English confidence explanations per spec Section 13.6."""
    tooltips = {
        "ci": (
            "The shaded area shows the range where the true value is most likely "
            "to fall. Wider ranges mean we have less data. Two values with "
            "overlapping ranges may not be meaningfully different."
        ),
        "suppressed": (
            "We do not have enough responses to show a reliable figure for this "
            "insurer. We need at least 50 to report with confidence."
        ),
        "stars": (
            "Stars reflect how an insurer's claims satisfaction compares to the "
            "rest of the market. Five stars means top quintile. One star means "
            "bottom quintile. The rating is relative, not absolute: a one-star "
            "insurer may still have generally satisfied customers."
        ),
        "practical": (
            "A difference between two scores may be statistically real but too "
            "small to matter in practice. We highlight differences only when they "
            "are large enough to be commercially meaningful."
        ),
    }
    return tooltips.get(context, "")
