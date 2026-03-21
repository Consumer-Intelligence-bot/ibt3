"""
Methodology Transparency — Client-facing (Spec Section 19.4 P3).

Explains the statistical methods used in the IBT Portal in plain English.
"""

import streamlit as st

from lib.config import (
    CONFIDENCE_LEVEL, MIN_BASE_FLOW_CELL, MIN_BASE_PUBLISHABLE,
    PRIOR_STRENGTH, SYSTEM_FLOOR_N, Z_SCORE,
)
from lib.formatting import render_header


def _ci_explanation() -> str:
    """Plain-English CI explanation."""
    return (
        "The shaded area or error bars on charts show the range where the true "
        "value is most likely to fall. We use a **95% confidence level**, meaning "
        "that if we repeated the survey many times, the true value would fall "
        "within this range 95 times out of 100."
    )


render_header()
st.header("Methodology")
st.caption("How we calculate and present the data in this portal")

# ---- Bayesian Smoothing ----
st.subheader("Bayesian Smoothing")
st.markdown(f"""
When an insurer has a small number of respondents, their results can appear volatile
— jumping around from month to month simply due to chance rather than real change.

To address this, we apply **Bayesian smoothing** using a Beta-Binomial model.
This technique blends the insurer's observed data with the overall market average,
giving more weight to the market average when the sample is small and more weight
to the observed data when the sample is large.

**Parameters:**
- Prior strength: **{PRIOR_STRENGTH} pseudo-observations** (equivalent to roughly one month of data for a small insurer)
- Prior mean: **Market average retention rate** (we shrink toward the market, not toward 50%)
- Large insurers (n > 500) see less than 5% adjustment
- Small insurers (n < 50) see 30–50% shrinkage toward market
""")

# ---- Confidence Intervals ----
st.subheader("Confidence Intervals")
st.markdown(f"""
Every rate shown in this portal has a confidence interval — a range within which
the true value most likely falls.

{_ci_explanation()}

**What does this mean in practice?**
- Wider ranges mean we have less data for that insurer
- Two values with overlapping ranges may not be meaningfully different
- A difference between two scores may be statistically real but too small to matter commercially
""")

# ---- Suppression Rules ----
st.subheader("Data Suppression")
st.markdown(f"""
We apply strict suppression rules to prevent unreliable data from being shown:

| Metric Type | Minimum Base | Context |
|-------------|-------------|---------|
| Insurer rate (publishable) | n ≥ {MIN_BASE_PUBLISHABLE} | All client-facing outputs |
| Insurer rate (indicative) | n ≥ 30 | Internal use only, with caveat |
| Flow cell (insurer-to-insurer pair) | n ≥ {MIN_BASE_FLOW_CELL} | Customer flow tables |
| Reason percentages | n ≥ 30 | Q8, Q18, Q19, Q31, Q33 |
| Trend indicator | n ≥ 30 per period | Both periods must independently meet threshold |
| System floor | n ≥ {SYSTEM_FLOOR_N} | Absolute minimum, no exceptions |

When data does not meet these thresholds:
- The value is **not shown** — not even greyed out or blurred
- An explanatory message replaces the visual entirely
- There is no way to override this suppression
""")

# ---- Star Ratings ----
st.subheader("Claims Star Ratings")
st.markdown("""
Stars reflect how an insurer's claims satisfaction compares to the rest of the market.

| Stars | Meaning |
|-------|---------|
| 5 stars | Top quintile (top 20%) |
| 4 stars | Second quintile (60th–80th percentile) |
| 3 stars | Middle quintile (40th–60th percentile) |
| 2 stars | Fourth quintile (20th–40th percentile) |
| 1 star | Bottom quintile (bottom 20%) |

**Important:** The rating is relative, not absolute. A one-star insurer may still
have generally satisfied customers — they simply rank lower than their peers.
The market overall delivers above-average satisfaction.
""")

# ---- Trend Detection ----
st.subheader("Trend Detection")
st.markdown("""
We show trend indicators (rising / stable / declining) only when:
1. Both comparison periods meet the minimum sample threshold (n ≥ 30 each)
2. The absolute change exceeds the average confidence interval width across both periods

This prevents us from flagging random noise as a meaningful trend.
Small, statistically insignificant movements are shown as "stable" rather than
as false signals of change.
""")

# ---- Data Quality ----
st.subheader("Data Quality Controls")
st.markdown("""
Several quality controls are applied before any data reaches the portal:

- **Q4 = Q39 flag**: If a respondent's current insurer matches their stated previous
  insurer, they are excluded from all customer flow calculations (likely data entry error)
- **Q1 normalisation**: Open-text brand responses are normalised to canonical brand names
  using fuzzy matching, with a target coverage of 80%+ of unique raw values
- **Duplicate detection**: Each respondent ID must appear exactly once in the dataset
- **Flow balance**: Total customers gained across all insurers must equal total customers lost
""")

# ---- Pet Insurance Notes ----
st.subheader("Pet Insurance")
st.markdown("""
Pet insurance data uses a quarterly survey cadence (not monthly like Motor and Home).
Quarterly periods are mapped to the last month of each quarter for time-series consistency
(e.g. Q4 2024 is shown as December 2024).

**Key differences from Motor/Home:**
- Data is collected quarterly, not monthly. Each data point represents a full quarter of fieldwork.
- Claims data (Q52/Q53) is not available for Pet.
- Spontaneous awareness (Q1) is not available in the current survey wave (pre-2026).
- The question set differs from Motor/Home. Some sections (e.g. shopping reasons, channel usage)
  may show "No data available" when the corresponding Pet questions have not been mapped.
""")

st.caption("© Consumer Intelligence 2026 — IBT Portal Methodology")
