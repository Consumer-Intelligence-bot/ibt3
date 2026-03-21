"""
Export-readiness utilities for Plotly charts.

Every chart must be usable as a static image in a board pack without manual
annotation. This module adds title, period, base size, and question reference
to any Plotly figure (Spec Section 15).
"""
from __future__ import annotations

import plotly.graph_objects as go


# Question reference mapping (full wording)
QUESTION_REF = {
    "Q1": "Q1: Which companies come to mind that sell motor/home insurance? (Spontaneous, open-text)",
    "Q2": "Q2: Which of these companies are you aware of selling motor/home insurance? (Prompted, multi-select)",
    "Q4": "Q4: Which company is your current motor/home insurance with?",
    "Q7": "Q7: Did you shop around at your most recent renewal?",
    "Q8": "Q8: What were your reasons for shopping around? (Ranked)",
    "Q9b": "Q9b: Which channels did you use to shop around? (Multi-select)",
    "Q11": "Q11: Which price comparison websites did you use? (Multi-select)",
    "Q15": "Q15: Did you switch insurer at your most recent renewal?",
    "Q18": "Q18: What were your reasons for staying with your insurer after shopping? (Ranked)",
    "Q19": "Q19: What were your reasons for not shopping around? (Ranked)",
    "Q27": "Q27: Which of these companies would you consider buying insurance from? (Multi-select)",
    "Q31": "Q31: What were your reasons for switching away? (Multi-select)",
    "Q33": "Q33: What were your reasons for choosing your new insurer? (Ranked)",
    "Q39": "Q39: Which company were you previously insured with?",
    "Q40a": "Q40a: How satisfied were you with your previous insurer overall? (1-5)",
    "Q40b": "Q40b: How likely would you be to recommend your previous insurer? (0-10, NPS)",
    "Q52": "Q52: How satisfied were you with the claims process overall? (1-5)",
    "Q53": "Q53: How would you rate the following aspects of your claims experience? (1-5)",
}


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
            font=dict(family="DM Sans, sans-serif", size=13),
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
        x=0, y=-0.10,
        xanchor="left", yanchor="top",
        showarrow=False,
        font=dict(family="DM Sans, sans-serif", size=9, color="#54585A"),
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
