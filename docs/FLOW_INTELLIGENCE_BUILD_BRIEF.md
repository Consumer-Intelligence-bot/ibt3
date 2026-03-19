# Claude Code Build Brief: Flow Intelligence Page

**Project:** Consumer Intelligence IBT Portal
**File:** `pages/10_Flow_Intelligence.py`
**Date:** 2026-03-18
**Status:** Ready to build

---

## Context

This brief adds a new analytics page to the existing Streamlit multipage dashboard.
The app lives at `/mnt/c/Users/ianch/ehubot` (local dev) and will deploy to a GCP VM.

Before writing any code, read these files to understand the existing patterns:

```
lib/analytics/flows.py          — existing flow functions you will extend
lib/analytics/bayesian.py       — Bayesian smoothing pattern (reference only)
lib/analytics/suppression.py    — suppression logic (use as-is)
lib/analytics/confidence.py     — confidence assessment (use as-is)
lib/config.py                   — brand colours and thresholds
lib/formatting.py               — fmt_pct and safe_pct helpers
lib/state.py                    — render_global_filters(), get_ss_data()
pages/2_Insurer_Diagnostic.py   — layout and chart pattern to follow
```

---

## What to build

Two things only:

1. One new function in `lib/analytics/flows.py`
2. One new page `pages/10_Flow_Intelligence.py`

Do not modify any other file.

---

## Part 1: New function in `lib/analytics/flows.py`

Add the following function at the end of the file. Do not change any existing function.

### Function: `calc_flow_index`

```python
def calc_flow_index(df: pd.DataFrame, insurer: str) -> dict:
    """
    Calculate over/under index for losses and gains vs market average.

    For losses (insurer X losing to competitor Y):
        insurer_share  = count(X → Y) / count(X → any)
        market_share   = count(any → Y) / count(any → any)
        index          = (insurer_share / market_share) * 100

    For gains (insurer X winning from competitor Y):
        insurer_share  = count(Y → X) / count(any → X)
        market_share   = count(Y → any) / count(any → any)
        index          = (insurer_share / market_share) * 100

    Index of 100 = market average.
    Index > 100  = over-indexing vs market.
    Index < 100  = under-indexing vs market.

    Rows where raw_count < MIN_BASE_FLOW_CELL are excluded entirely.
    Rows where market_share == 0 are excluded (avoid division by zero).

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (all insurers, all respondents). Must contain
        IsSwitcher, CurrentCompany, PreviousCompany columns.
    insurer : str
        The selected insurer to analyse.

    Returns
    -------
    dict with keys:
        loss_index : pd.DataFrame
            columns: competitor, raw_count, insurer_share,
                     market_share, index
            sorted descending by index
        gain_index : pd.DataFrame
            columns: competitor, raw_count, insurer_share,
                     market_share, index
            sorted descending by index
        total_switchers : int
            Total switchers in the dataset (for context)
        insurer_lost : int
            Total customers lost by selected insurer
        insurer_gained : int
            Total customers gained by selected insurer
    """
```

### Implementation notes

- Call `_exclude_q4_eq_q39(df)` at the start before any calculations.
- Work only with rows where `IsSwitcher == True`.
- Exclude rows where `PreviousCompany` or `CurrentCompany` is null or empty string.
- Exclude competitor names containing "Don't Know", "Can't Remember", or "Other".
- After calculating index values, exclude any row where `raw_count < MIN_BASE_FLOW_CELL`.
- Return empty DataFrames (not None) if there is insufficient data.
- Both returned DataFrames must have exactly these columns in this order:
  `competitor`, `raw_count`, `insurer_share`, `market_share`, `index`

---

## Part 2: New page `pages/10_Flow_Intelligence.py`

### Page purpose

Shows where an insurer is over- or under-indexing on customer losses and gains
relative to the market average. Expressed as a 100 index.

This is a diagnostic tool, not a ranking. Language should reflect that.

---

### Page structure

#### Header

```
st.header("Flow Intelligence")
```

#### Global filters (sidebar)

Call `render_global_filters()` from `lib.state`. This provides:
- Insurer selector
- Product toggle (Motor/Home)
- Age band, region, payment type filters
- Time window slider

All filters are already implemented. Do not rebuild them.

#### Data loading

```python
df_ins, df_mkt = get_filtered_data(
    insurer=filters["insurer"],
    product=filters["product"],
    age_band=filters["age_band"],
    region=filters["region"],
    payment_type=filters["payment_type"],
    selected_months=filters["selected_months"],
)
```

If no insurer is selected, show:
```
st.info("Select an insurer from the sidebar to view Flow Intelligence.")
st.stop()
```

#### Suppression gate

Before rendering anything, check the insurer's renewal base:

```python
from lib.analytics.suppression import check_suppression
from lib.config import MIN_BASE_PUBLISHABLE

n_ins = len(df_ins)
suppressed, message = check_suppression(n_ins, MIN_BASE_PUBLISHABLE)
if suppressed:
    st.warning(message)
    st.stop()
```

---

### Section 1: Loss over-index

**Section header:** `_section_divider("Where Are We Losing Disproportionately?")`

Call `calc_flow_index(df_mkt, insurer)` once and store the result.

Use `result["loss_index"]` for this section.

If the DataFrame is empty, show:
```
st.info("Insufficient data to calculate loss over-index for the selected period.")
```

Otherwise render a horizontal bar chart using this pattern:

```python
import plotly.graph_objects as go

df_loss = result["loss_index"]  # already sorted descending by index

n = len(df_loss)
colours = [
    CI_RED if row["index"] > 120
    else CI_GREEN if row["index"] < 80
    else CI_BLUE
    for _, row in df_loss.iterrows()
]

fig = go.Figure(go.Bar(
    x=df_loss["index"],
    y=df_loss["competitor"],
    orientation="h",
    marker_color=colours,
    text=[f"{v:.0f}" for v in df_loss["index"]],
    textposition="outside",
    hovertemplate=(
        "<b>%{y}</b><br>"
        "Index: %{x:.0f}<br>"
        "Your share: %{customdata[0]:.1%}<br>"
        "Market share: %{customdata[1]:.1%}<br>"
        "Raw count: %{customdata[2]:,}"
        "<extra></extra>"
    ),
    customdata=df_loss[["insurer_share", "market_share", "raw_count"]].values,
))

fig.add_vline(
    x=100,
    line_dash="dot",
    line_color=CI_MAGENTA,
    annotation_text="Market average (100)",
    annotation_position="top right",
    annotation_font_color=CI_MAGENTA,
)

fig.update_layout(
    height=max(400, n * 30),
    xaxis=dict(
        title="Index (100 = market average)",
        gridcolor=CI_LIGHT_GREY,
    ),
    yaxis=dict(title="", autorange="reversed"),
    plot_bgcolor=CI_WHITE,
    paper_bgcolor=CI_WHITE,
    font=dict(family="Verdana, Geneva, sans-serif", size=11, color=CI_GREY),
    margin=dict(l=10, r=80, t=20, b=40),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)
```

Below the chart, add a plain-language caption:

```python
st.caption(
    "Index above 100 means you are losing a disproportionately high share "
    "of customers to that competitor vs the market average. "
    f"Based on {result['insurer_lost']:,} customers lost in the selected period."
)
```

---

### Section 2: Gain over-index

**Section header:** `_section_divider("Where Are We Winning Disproportionately?")`

Same chart pattern as Section 1 but using `result["gain_index"]`.

Colour logic is reversed:
- Index > 120: `CI_GREEN` (winning disproportionately is good)
- Index < 80: `CI_RED` (under-winning vs market is a concern)
- Otherwise: `CI_BLUE`

Caption:

```python
st.caption(
    "Index above 100 means you are winning a disproportionately high share "
    "of customers from that competitor vs the market average. "
    f"Based on {result['insurer_gained']:,} customers gained in the selected period."
)
```

---

### Section 3: Trend drill-down

**Section header:** `_section_divider("How Is This Changing Over Time?")`

Provide two selectboxes side by side:

```python
col1, col2 = st.columns(2)
with col1:
    direction = st.selectbox(
        "Flow direction",
        ["Losses (outflow)", "Gains (inflow)"],
        key="flow_direction",
    )
with col2:
    if direction == "Losses (outflow)":
        competitors = result["loss_index"]["competitor"].tolist()
    else:
        competitors = result["gain_index"]["competitor"].tolist()

    if not competitors:
        st.info("No eligible competitors to drill into.")
        st.stop()

    selected_competitor = st.selectbox(
        "Competitor",
        competitors,
        key="flow_competitor",
    )
```

For the trend calculation, compute the index month by month using the full unfiltered
dataset from session state. Call `get_ss_data()` to get `df_all` then filter by product.

For each month in the selected time window, compute:
- raw count for the selected pair
- insurer share for the pair
- market share for that destination/source
- index value

Suppress months where raw count < `MIN_BASE_FLOW_CELL`. Show as gaps in the line,
not as zero values.

Render as a line chart using Plotly:

```python
fig = go.Figure(go.Scatter(
    x=trend_df["month_label"],
    y=trend_df["index"],
    mode="lines+markers",
    line=dict(color=CI_MAGENTA, width=2),
    marker=dict(size=6, color=CI_MAGENTA),
    hovertemplate="<b>%{x}</b><br>Index: %{y:.0f}<extra></extra>",
))

fig.add_hline(
    y=100,
    line_dash="dot",
    line_color=CI_GREY,
    annotation_text="Market average (100)",
    annotation_position="right",
)

fig.update_layout(
    height=320,
    xaxis=dict(title="", gridcolor=CI_LIGHT_GREY),
    yaxis=dict(title="Index", gridcolor=CI_LIGHT_GREY),
    plot_bgcolor=CI_WHITE,
    paper_bgcolor=CI_WHITE,
    font=dict(family="Verdana, Geneva, sans-serif", size=11, color=CI_GREY),
    margin=dict(l=10, r=80, t=20, b=40),
    showlegend=False,
)

st.plotly_chart(fig, use_container_width=True)
```

If fewer than 3 non-suppressed months exist, show:
```
st.info("Insufficient monthly data to show a meaningful trend for this pair.")
```

---

### Imports to use at the top of the new page

```python
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from lib.analytics.flows import calc_flow_index
from lib.analytics.suppression import check_suppression
from lib.config import (
    CI_BLUE,
    CI_GREEN,
    CI_GREY,
    CI_LIGHT_GREY,
    CI_MAGENTA,
    CI_RED,
    CI_WHITE,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
)
from lib.formatting import fmt_pct
from lib.state import (
    format_year_month,
    get_filtered_data,
    get_ss_data,
    render_global_filters,
)
```

### Helper functions to include in the page

Copy these from `pages/2_Insurer_Diagnostic.py` — do not import from there,
just copy the definitions locally into the new page:

- `_section_divider(title)` — branded section header
- `_period_label(selected_months)` — human-readable period string

---

## What not to do

- Do not modify `lib/state.py`, `lib/db.py`, `lib/powerbi.py`, or `app.py`
- Do not modify any existing function in `lib/analytics/flows.py`
- Do not modify `pages/2_Insurer_Diagnostic.py`
- Do not add the page to any navigation config — Streamlit picks it up automatically
- Do not use `st.cache_data` on `calc_flow_index` — it runs on already-loaded data

---

## Verification steps

After building, confirm:

1. `calc_flow_index` returns two DataFrames with exactly the columns specified
2. Rows with raw count < 10 are absent from both DataFrames
3. The page renders without error when no insurer is selected (shows info message)
4. The page renders without error when an insurer with insufficient data is selected
   (shows suppression message)
5. The vertical reference line at index 100 is visible in both bar charts
6. The trend section shows gaps (not zeros) for suppressed months
7. No existing page is broken — run the app and check pages 1-9 still load

---

## Show me when done

After completing the build, show:

```
git diff --stat
```

And paste the first 50 lines of `pages/10_Flow_Intelligence.py` so I can
confirm the imports and structure before reviewing the rest.
