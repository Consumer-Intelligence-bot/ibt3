# Headline Page Enhancement Plan

## Overview

Add four features to the Headline page (`pages/3_Headline.py`) in the Streamlit app:

1. **"Click for more" deep dive panels** — expandable sections below each of the 4 comparison bars
2. **Renewal premium change vs market** — new sub-section below Pre-renewal share card
3. **Source of business (PCW / Direct / Other)** — new sub-section below Post-renewal share card
4. **Net movement rank** — rank badge below Net movement card

---

## Wireframe

```
┌─────────────────────────────────────────────────────────────────────────┐
│  Customers shop at the market rate, but AA keeps more of them          │
│  Retention and acquisition both beat market, lifting share from        │
│  8.9% to 9.7% through renewal.                                        │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ PRE-RENEWAL SHARE│  │  NET MOVEMENT    │  │POST-RENEWAL SHARE│      │
│  │     8.9%         │  │   +0.8 pts       │  │     9.7%         │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐      │
│  │ PREMIUM CHANGE   │  │  MOVEMENT RANK   │  │ SOURCE OF        │      │
│  │ vs MARKET  [NEW] │  │  #3 of 24  [NEW] │  │ BUSINESS   [NEW] │      │
│  │                  │  │                  │  │                  │      │
│  │ Higher:          │  │  ████░░░░░░░░░░  │  │ PCW:             │      │
│  │ AA ████  42%     │  │  Top quartile    │  │ AA ██████  62%   │      │
│  │ Mkt ███  38%     │  │                  │  │ Mkt █████  58%   │      │
│  │                  │  │                  │  │                  │      │
│  │ Unchanged:       │  │                  │  │ Direct:          │      │
│  │ AA ███  31%      │  │                  │  │ AA ████  32%     │      │
│  │ Mkt ████  35%    │  │                  │  │ Mkt ████  34%    │      │
│  │                  │  │                  │  │                  │      │
│  │ Lower:           │  │                  │  │ Other:           │      │
│  │ AA ███  27%      │  │                  │  │ AA █  6%         │      │
│  │ Mkt ███  27%     │  │                  │  │ Mkt █  8%        │      │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘      │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Why this happened                                                      │
│  Customers are just as likely to shop around. AA performs better.       │
│                                                                         │
│  ▶ Shopping rate — AA 68.3% vs Market 71.1% — Below                    │
│    (st.expander with deep dive charts)                                  │
│                                                                         │
│  ▶ Retention — AA 67.1% vs Market 64.0% — Ahead                       │
│    (st.expander with deep dive charts)                                  │
│                                                                         │
│  ▶ Shopped and stayed — AA 54.0% vs Market 50.3% — Ahead              │
│    (st.expander with deep dive charts)                                  │
│                                                                         │
│  ▶ New business acquisition — AA 2.2% vs Market 1.1% — Ahead          │
│    (st.expander with deep dive charts)                                  │
│                                                                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Competitive exchange                                                   │
│                                                                         │
│           Won from                              Lost to                 │
│  14.6% ████████████     Admiral     ████████████████ 23.4%             │
│  11.4% ██████████       Aviva       ████████████ 16.9%                 │
│   8.8% ██████           Allianz     ██████ 8.8%                        │
│                                                                         │
│  Aviva is the main two-way battleground.                               │
├─────────────────────────────────────────────────────────────────────────┤
│                     Base: 10,545 respondents                           │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Steps

### Phase 1: Shared Utilities

#### Step 1.1: Create `lib/formatting.py`

Extract duplicated helpers from `pages/3_Headline.py` and `pages/4_Renewal_Flow.py`:
- `pct(n, d)` — safe percentage calculation
- `fmt_pct(val, dp=1)` — format as percentage string
- `derive_tag(ins_val, mkt_val)` — "Ahead" / "Below" / "In line"
- `tag_colour(tag)` — CI colour for tag

#### Step 1.2: Add analytics helpers to `lib/analytics/`

New functions (can go in existing modules or a new `lib/analytics/headline.py`):
- `calc_premium_change_comparison(df, insurer)` — Higher/Unchanged/Lower distribution, insurer vs market
- `calc_channel_comparison(df, insurer)` — PCW/Direct/Other distribution, insurer vs market
- `calc_net_movement_rank(df, insurer)` — rank insurer among all brands by net share movement

### Phase 2: Deep Dive Enhancements to `pages/3_Headline.py`

The page already uses `st.expander()` for each comparison metric. Enhance the content inside each expander:

#### Step 2.1: Shopping rate deep dive
- Shopping rate by premium change (Higher/Unchanged/Lower) — horizontal bar chart
- Shopping rate by age group — horizontal bar chart

#### Step 2.2: Retention deep dive
- Retention by premium change — horizontal bar chart
- Retention by region — horizontal bar chart

#### Step 2.3: Shopped and stayed deep dive
- Premium change distribution for shop-stay segment
- PCW usage: insurer vs market

#### Step 2.4: New business acquisition deep dive
- Top 5 source brands with percentages
- Channel breakdown (PCW/Direct/Other)

### Phase 3: New Sub-Cards

#### Step 3.1: Premium change vs market (below Pre-renewal share)
- Three paired horizontal bars: Higher / Unchanged / Lower
- Insurer bars in CI Magenta, market bars in CI Grey
- Uses `calc_premium_change_comparison()`

#### Step 3.2: Source of business (below Post-renewal share)
- Three paired horizontal bars: PCW / Direct / Other
- Data from shopping channel column
- Uses `calc_channel_comparison()`

#### Step 3.3: Net movement rank (below Net movement card)
- "Ranked #X of Y" badge
- Colour coded: green (top quartile), grey (middle), red (bottom quartile)
- Uses `calc_net_movement_rank()`

### Phase 4: Deep Dive Content Detail

Each deep dive panel contains 2-3 compact Plotly visualisations in `st.columns()`:

| Metric | Left column | Right column |
|--------|------------|--------------|
| Shopping rate | By premium change (Higher/Unchanged/Lower) | By age group (horizontal bars) |
| Retention | By premium change | By region |
| Shopped and stayed | Premium change distribution for shop-stay | PCW usage: insurer vs market |
| New business acquisition | Top 5 source brands with % | Channel breakdown (PCW/Direct/Other) |

All deep dive sub-breakdowns respect sample size governance (n >= 30 to display, n >= 50 for "publishable").

---

## Files to Create

| File | Purpose |
|------|---------|
| `lib/formatting.py` | Shared formatting utilities (extracted from pages) |
| `lib/analytics/headline.py` | Premium change, channel, and rank calculations |

## Files to Modify

| File | Change |
|------|--------|
| `pages/3_Headline.py` | Add deep dives, premium change card, source of business card, rank badge |
| `pages/4_Renewal_Flow.py` | Import shared utilities from `lib/formatting.py` instead of defining locally |

---

## Design Notes

- **Colour scheme**: Insurer data in CI Magenta (#981D97), market in CI Grey (#54585A), positive in CI Green (#48A23F), negative in CI Red (#F4364C)
- **Font**: Verdana, Geneva, sans-serif (matches `lib/config.py` CSS)
- **Charts**: Plotly `go.Bar` with horizontal orientation, matching existing pattern in `pages/3_Headline.py`
- **Layout**: `st.columns()` for side-by-side cards, `st.expander()` for deep dives (already in use)
- **Suppression**: All deep dive breakdowns check n >= 30 before rendering
