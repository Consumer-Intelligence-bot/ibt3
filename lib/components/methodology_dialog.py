"""
In-page methodology dialog component.

Provides:
  - get_methodology_sections()  — pure function, no Streamlit dep, fully testable
  - show_methodology_dialog()   — @st.dialog decorated renderer
  - render_methodology_button() — button that triggers the dialog
"""

from __future__ import annotations

import streamlit as st

from lib.config import (
    CONFIDENCE_LEVEL,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
    PRIOR_STRENGTH,
    SYSTEM_FLOOR_N,
)


def get_methodology_sections() -> list[dict]:
    """Return methodology content as a list of ``{"title": str, "content": str}`` dicts.

    Pure function — no Streamlit calls. Safe to call in unit tests and outside
    a Streamlit session. Each call returns a fresh list.
    """
    return [
        {
            "title": "Bayesian Smoothing",
            "content": (
                f"When an insurer has a small number of respondents their results can appear "
                f"volatile simply due to chance rather than real change.\n\n"
                f"We apply **Bayesian smoothing** using a Beta-Binomial model. This blends the "
                f"insurer's observed data with the overall market average, giving more weight to "
                f"the market when the sample is small.\n\n"
                f"**Parameters:**\n"
                f"- Prior strength: **{PRIOR_STRENGTH} pseudo-observations**\n"
                f"- Prior mean: **Market average retention rate**\n"
                f"- Large insurers (n > 500) see less than 5% adjustment\n"
                f"- Small insurers (n < 50) see 30-50% shrinkage toward market"
            ),
        },
        {
            "title": "Confidence Intervals",
            "content": (
                "Every rate shown in this portal has a confidence interval. The shaded area or "
                "error bars show the range where the true value is most likely to fall. "
                "We use a **95% confidence level**.\n\n"
                "**In practice:**\n"
                "- Wider ranges mean less data for that insurer\n"
                "- Two values with overlapping ranges may not be meaningfully different\n"
                "- A difference may be statistically real but too small to matter commercially"
            ),
        },
        {
            "title": "Data Suppression",
            "content": (
                f"| Metric Type | Minimum Base | Context |\n"
                f"|-------------|-------------|--------|\n"
                f"| Insurer rate (publishable) | n >= {MIN_BASE_PUBLISHABLE} | Client-facing outputs |\n"
                f"| Insurer rate (indicative) | n >= 30 | Internal use only |\n"
                f"| Flow cell (insurer pair) | n >= {MIN_BASE_FLOW_CELL} | Customer flow tables |\n"
                f"| Reason percentages | n >= 30 | Q8, Q18, Q19, Q31, Q33 |\n"
                f"| Trend indicator | n >= 30 per period | Both periods must meet threshold |\n"
                f"| System floor | n >= {SYSTEM_FLOOR_N} | Absolute minimum, no exceptions |\n\n"
                "When data does not meet these thresholds the value is **not shown** and an "
                "explanatory message replaces the visual."
            ),
        },
        {
            "title": "Claims Star Ratings",
            "content": (
                "| Stars | Meaning |\n"
                "|-------|--------|\n"
                "| 5 stars | Top quintile (top 20%) |\n"
                "| 4 stars | Second quintile (60th-80th percentile) |\n"
                "| 3 stars | Middle quintile (40th-60th percentile) |\n"
                "| 2 stars | Fourth quintile (20th-40th percentile) |\n"
                "| 1 star | Bottom quintile (bottom 20%) |\n\n"
                "The rating is relative, not absolute. "
                "A one-star insurer may still have satisfied customers."
            ),
        },
        {
            "title": "Trend Detection",
            "content": (
                "Trend indicators (rising / stable / declining) shown only when:\n"
                "1. Both comparison periods meet the minimum sample threshold (n >= 30 each)\n"
                "2. The absolute change exceeds the average CI width across both periods\n\n"
                'Small, statistically insignificant movements are shown as "stable".'
            ),
        },
        {
            "title": "Data Quality Controls",
            "content": (
                "- **Q4 = Q39 flag**: Respondents where current insurer matches previous "
                "insurer are excluded from flow calculations (likely data entry error)\n"
                "- **Q1 normalisation**: Open-text brand responses normalised to canonical names\n"
                "- **Duplicate detection**: Each respondent ID must appear exactly once\n"
                "- **Flow balance**: Total gained must equal total lost across all insurers"
            ),
        },
        {
            "title": "Pet Insurance",
            "content": (
                "Pet uses a quarterly survey cadence. Quarterly periods are mapped to the last "
                "month of each quarter for time-series consistency.\n\n"
                "Key differences: data is quarterly not monthly, no claims data (Q52/Q53), "
                "no spontaneous awareness (Q1) in the current survey wave."
            ),
        },
    ]


@st.dialog("How is this calculated?", width="large")
def show_methodology_dialog() -> None:
    """Render the methodology sections inside a Streamlit dialog popup."""
    for section in get_methodology_sections():
        st.markdown(f"**{section['title']}**")
        st.markdown(section["content"])
        st.divider()
    st.caption("Consumer Intelligence 2026 - IBT Portal Methodology")


def render_methodology_button(screen_name: str = "") -> None:
    """Render a tertiary button that opens the methodology dialog on click.

    Parameters
    ----------
    screen_name : str
        Used to make the button key unique per screen, avoiding Streamlit
        duplicate-key errors when multiple screens are mounted simultaneously.
    """
    if st.button(
        "How is this calculated?",
        key=f"methodology_dialog_btn_{screen_name}",
        type="tertiary",
    ):
        show_methodology_dialog()
