# Headline Page Enhancement Plan

## Overview

Add four features to the Headline page on **both** the Python Dash (`ss-intelligence/pages/headline.py`) and React (`src/`) frontends:

1. **"Click for more" deep dive buttons** — accordion-expand panels below each of the 4 comparison bars
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
│  Shopping rate                              BELOW    [Click for more ▼] │
│  ████████████████████████████████████████░░░░│░░░░░░░░░░░░░░░░░░░░░░░  │
│  AA 68.3%                                           Market 71.1%       │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │
│  │  DEEP DIVE: Shopping Rate (accordion expand)                      │ │
│  │                                                                    │ │
│  │  By premium change:              Trend over time:                 │ │
│  │  ┌────────────────────┐          ┌────────────────────┐           │ │
│  │  │ Higher  → 82% shop │          │  ___/‾‾\___/‾‾‾   │           │ │
│  │  │ Unchanged → 55%    │          │ /                   │           │ │
│  │  │ Lower   → 48% shop │          │  J F M A M J J     │           │ │
│  │  └────────────────────┘          └────────────────────┘           │ │
│  │                                                                    │ │
│  │  By age group:                                                    │ │
│  │  18-24: ████████  78%    35-44: ██████  65%                       │ │
│  │  25-34: ███████  72%     45-54: █████  58%                        │ │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │
│                                                                         │
│  Retention                                  AHEAD    [Click for more ▼] │
│  ████████████████████████████████████████████│░░░░░░░░░░░░░░░░░░░░░░░  │
│  AA 67.1%                                           Market 64.0%       │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │
│  │  DEEP DIVE: Retention                                             │ │
│  │                                                                    │ │
│  │  Retention by premium change:     By region:                      │ │
│  │  Higher → 52% retained            North: 70%                      │ │
│  │  Unchanged → 85% retained         South: 63%                      │ │
│  │  Lower → 78% retained             Midlands: 68%                   │ │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │
│                                                                         │
│  Shopped and stayed                         AHEAD    [Click for more ▼] │
│  ██████████████████████████████████████│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  AA 54.0%                                           Market 50.3%       │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │
│  │  DEEP DIVE: Shopped and Stayed                                    │ │
│  │                                                                    │ │
│  │  Premium change for those who     PCW usage:                      │ │
│  │  shopped and stayed:              AA: 74% used PCW                │ │
│  │  Higher → 38%                     Mkt: 70% used PCW               │ │
│  │  Unchanged → 35%                                                  │ │
│  │  Lower → 27%                                                      │ │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │
│                                                                         │
│  New business acquisition                   AHEAD    [Click for more ▼] │
│  ██████████████│░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  │
│  AA 2.2%                                            Market 1.1%       │
│  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐ │
│  │  DEEP DIVE: New Business Acquisition                              │ │
│  │                                                                    │ │
│  │  Top source brands:              Channel:                         │ │
│  │  1. Admiral  → 28%               PCW: 68%                         │ │
│  │  2. Aviva    → 19%               Direct: 25%                      │ │
│  │  3. Allianz  → 12%               Other: 7%                        │ │
│  │  4. Direct Line → 9%                                              │ │
│  │  5. LV       → 7%                                                 │ │
│  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘ │
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

### Phase 1: Data Layer

#### Step 1.1: Create `src/utils/measures/headlineMeasures.js` (React)
- `calcHeadlineMetrics(data, insurer)` — core metrics (pre/post share, shopping rate, retention, etc.)
- `calcPremiumChangeComparison(data, insurer)` — reuses `priceUpPct`/`priceDownPct`/`priceUnchangedPct` from `screen1Measures.js`
- `calcChannelComparison(data, insurer)` — PCW vs Direct/Other, insurer vs market
- `calcNetMovementRank(data, insurer)` — rank among all insurers by net movement
- Deep dive helpers: `shoppingRateByPremiumChange()`, `shoppingRateByAge()`, `retentionByPremiumChange()`, `retentionByRegion()`, `shopStayByPremiumChange()`, `shopStayPCWUsage()`, `newBizSourceBrands()`, `newBizChannelBreakdown()`

#### Step 1.2: Export `buildChannelBreakdown` from `src/utils/measures/renewalJourneyMeasures.js`
- One-line change: add `export` keyword

#### Step 1.3: Add equivalent Python metrics to `headline.py`
- `_calc_premium_change_comparison()` — insurer vs market premium change distribution
- `_calc_channel_comparison()` — PCW/Direct/Other distribution for insurer vs market
- `_calc_net_movement_rank()` — rank insurer among all brands
- Deep dive breakdown functions for each of the 4 metrics

### Phase 2: Python Dash Implementation

#### Step 2.1: Add "Click for more" accordion to `headline.py`
- Replace each `_comparison_bar()` call with a new `_comparison_bar_with_deepdive()` that includes:
  - The existing bar
  - A "Click for more ▼" button (Dash `html.Button`)
  - A collapsible `dbc.Collapse` section with deep dive content
- Use Dash `callback` with `State` to toggle each panel open/closed
- Add component IDs: `deepdive-shopping`, `deepdive-retention`, `deepdive-shopped-stayed`, `deepdive-new-biz`

#### Step 2.2: Add Premium Change vs Market below Pre-renewal share
- New helper `_premium_change_card()` rendering three paired horizontal bars (Higher/Unchanged/Lower)
- Insurer bars in magenta, market bars in grey
- Insert into the outcome flex row below the Pre-renewal card

#### Step 2.3: Add Source of Business below Post-renewal share
- New helper `_source_of_business_card()` rendering PCW/Direct/Other paired bars
- Data from `Did you use a PCW for shopping` column (Yes = PCW, No = Direct/Other)
- Insert into the outcome flex row below the Post-renewal card

#### Step 2.4: Add Net Movement Rank below Net movement card
- New helper `_rank_badge()` showing "Ranked #X of Y"
- Color coded: green for top quartile, grey for middle, red for bottom quartile
- Small position indicator bar showing where insurer sits

### Phase 3: React Implementation

#### Step 3.1: Create `src/components/headline/ComparisonBar.jsx`
- Port `_comparison_bar` from Python with inline styles
- Add `onClickMore` prop for the "Click for more" button
- Uses brand constants for colours

#### Step 3.2: Create `src/components/headline/ButterflyChart.jsx`
- Port `_butterfly_chart` from Python
- Pure HTML/CSS horizontal bars (no Recharts needed)

#### Step 3.3: Create `src/components/headline/DeepDivePanel.jsx`
- Accordion-style expand with CSS `max-height` transition
- Props: `metric`, `isOpen`, `data`, `insurer`
- Renders metric-specific deep dive content:
  - **Shopping rate**: By premium change, trend over time (sparkline), by age group
  - **Retention**: By premium change, by region
  - **Shopped and stayed**: Premium change split, PCW usage comparison
  - **New business acquisition**: Top source brands, channel breakdown

#### Step 3.4: Create `src/components/headline/PremiumChangeVsMarket.jsx`
- Small sub-card showing Higher/Unchanged/Lower paired bars

#### Step 3.5: Create `src/components/headline/SourceOfBusiness.jsx`
- Small sub-card showing PCW/Direct/Other paired bars

#### Step 3.6: Create `src/components/headline/HeadlinePage.jsx`
- Main page component assembling all sections
- Uses `useDashboard()` context for data + filters
- `useMemo` for all metric calculations
- Manages accordion open/closed state

#### Step 3.7: Add route and tab navigation
- `src/App.jsx` — add `/headline` route
- `src/components/shared/TabNavigation.jsx` — add "Headline" tab

### Phase 4: Deep Dive Content Detail

Each deep dive panel contains 2-3 compact visualizations:

| Metric | Left column | Right column |
|--------|------------|--------------|
| Shopping rate | Shopping rate by premium change (Higher/Unchanged/Lower) | Shopping rate by age group (horizontal bars) |
| Retention | Retention by premium change | Retention by region |
| Shopped and stayed | Premium change distribution for shop-stay segment | PCW usage: insurer vs market |
| New business acquisition | Top 5 source brands with % | Channel breakdown (PCW/Direct/Other) |

All deep dive sub-breakdowns respect sample size governance (n >= 30 to display, n >= 50 for "publishable").

---

## Files to Create

| File | Purpose |
|------|---------|
| `src/utils/measures/headlineMeasures.js` | All headline metric calculations + deep dive helpers |
| `src/components/headline/HeadlinePage.jsx` | Main headline page component |
| `src/components/headline/ComparisonBar.jsx` | Insurer vs market comparison bar |
| `src/components/headline/ButterflyChart.jsx` | Won from / Lost to butterfly chart |
| `src/components/headline/DeepDivePanel.jsx` | Accordion deep dive panel |
| `src/components/headline/PremiumChangeVsMarket.jsx` | Premium change sub-card |
| `src/components/headline/SourceOfBusiness.jsx` | Source of business sub-card |

## Files to Modify

| File | Change |
|------|--------|
| `ss-intelligence/pages/headline.py` | Add all 4 features (deep dives, premium change, source of biz, rank) |
| `src/utils/measures/renewalJourneyMeasures.js` | Export `buildChannelBreakdown` |
| `src/App.jsx` | Add `/headline` route |
| `src/components/shared/TabNavigation.jsx` | Add "Headline" tab |

---

## Design Notes

- **Colour scheme**: Insurer data in CI Magenta (#981D97), market in CI Grey (#54585A), positive in CI Green (#48A23F), negative in CI Red (#F4364C)
- **Font**: Verdana, Geneva, sans-serif throughout
- **Inline styles only** — matching existing codebase pattern (no CSS modules)
- **Accordion animation**: CSS `max-height` + `overflow: hidden` + `transition: max-height 0.3s ease`
- **"Click for more" button**: Small text-style button, CI Magenta colour, with ▼/▲ chevron indicator
- **Suppression**: All deep dive breakdowns check n >= 30 before rendering
