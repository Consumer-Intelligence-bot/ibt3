"""
Methodology screen. Ported from pages/9_Methodology.py.
Explains statistical methods in plain English.
"""

import streamlit as st

from lib.config import (
    CONFIDENCE_LEVEL, MIN_BASE_FLOW_CELL, MIN_BASE_PUBLISHABLE,
    PRIOR_STRENGTH, SYSTEM_FLOOR_N,
)


def render(filters: dict):
    """Render the Methodology screen."""
    st.header("Methodology")
    st.caption("How we calculate and present the data in this portal")

    st.subheader("Bayesian Smoothing")
    st.markdown(f"""
When an insurer has a small number of respondents, their results can appear volatile
simply due to chance rather than real change.

We apply **Bayesian smoothing** using a Beta-Binomial model. This blends the insurer's
observed data with the overall market average, giving more weight to the market when the
sample is small.

**Parameters:**
- Prior strength: **{PRIOR_STRENGTH} pseudo-observations**
- Prior mean: **Market average retention rate**
- Large insurers (n > 500) see less than 5% adjustment
- Small insurers (n < 50) see 30-50% shrinkage toward market
""")

    st.subheader("Confidence Intervals")
    st.markdown("""
Every rate shown in this portal has a confidence interval. The shaded area or error bars
show the range where the true value is most likely to fall. We use a **95% confidence level**.

**In practice:**
- Wider ranges mean less data for that insurer
- Two values with overlapping ranges may not be meaningfully different
- A difference may be statistically real but too small to matter commercially
""")

    st.subheader("Data Suppression")
    st.markdown(f"""
| Metric Type | Minimum Base | Context |
|-------------|-------------|---------|
| Insurer rate (publishable) | n >= {MIN_BASE_PUBLISHABLE} | Client-facing outputs |
| Insurer rate (indicative) | n >= 30 | Internal use only |
| Flow cell (insurer pair) | n >= {MIN_BASE_FLOW_CELL} | Customer flow tables |
| Reason percentages | n >= 30 | Q8, Q18, Q19, Q31, Q33 |
| Trend indicator | n >= 30 per period | Both periods must meet threshold |
| System floor | n >= {SYSTEM_FLOOR_N} | Absolute minimum, no exceptions |

When data does not meet these thresholds, the value is **not shown** and an explanatory
message replaces the visual.
""")

    st.subheader("Claims Star Ratings")
    st.markdown("""
| Stars | Meaning |
|-------|---------|
| 5 stars | Top quintile (top 20%) |
| 4 stars | Second quintile (60th-80th percentile) |
| 3 stars | Middle quintile (40th-60th percentile) |
| 2 stars | Fourth quintile (20th-40th percentile) |
| 1 star | Bottom quintile (bottom 20%) |

The rating is relative, not absolute. A one-star insurer may still have satisfied customers.
""")

    st.subheader("Trend Detection")
    st.markdown("""
Trend indicators (rising / stable / declining) shown only when:
1. Both comparison periods meet the minimum sample threshold (n >= 30 each)
2. The absolute change exceeds the average CI width across both periods

Small, statistically insignificant movements are shown as "stable".
""")

    st.subheader("Data Quality Controls")
    st.markdown("""
- **Q4 = Q39 flag**: Respondents where current insurer matches previous insurer are
  excluded from flow calculations (likely data entry error)
- **Q1 normalisation**: Open-text brand responses normalised to canonical names
- **Duplicate detection**: Each respondent ID must appear exactly once
- **Flow balance**: Total gained must equal total lost across all insurers
""")

    st.subheader("Pet Insurance")
    st.markdown("""
Pet uses a quarterly survey cadence. Quarterly periods are mapped to the last month
of each quarter for time-series consistency.

Key differences: data is quarterly not monthly, no claims data (Q52/Q53),
no spontaneous awareness (Q1) in the current survey wave.
""")

    st.caption("Consumer Intelligence 2026 - IBT Portal Methodology")
