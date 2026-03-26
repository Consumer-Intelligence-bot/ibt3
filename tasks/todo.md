# IBT3 TODO

## COMPLETED

### Customer Lifecycle Dashboard (Sprints 1-7)
- [x] Sprint 1: Router pattern, screen architecture, data loading
- [x] Sprint 2: Reasons & Shopping screens with cohort heat map
- [x] Sprint 3: Channels & Pre-Renewal screens
- [x] Sprint 4: Awareness & Claims screens
- [x] Sprint 5: Satisfaction screen + narrative engine
- [x] Sprint 6: Compare Insurers, Methodology, filter bar
- [x] Sprint 7: Polish, narratives, cross-screen links, cleanup

### Editorial Design Overhaul
- [x] Typography, sidebar, cards redesign
- [x] Verdana font, narrative panels on all 8 screens

### Unprompted Awareness UI/UX Fixes
- [x] Taller charts + dynamic height scaling
- [x] Direct on-chart labels (brand + share %), legend improvements
- [x] Tighter margins, reduced white space

### Pet Insurance Integration
- [x] Pet added as third product (dataset 4a1347c3)
- [x] Quarterly grain conversion to monthly YYYYMM
- [x] EAV table batching for 100K API limit
- [x] Error isolation per product in init_ss_data

### EAV-to-Wide Migration
- [x] Dashboard migrated from EAV to wide columns
- [x] Bayesian movers, Q1 spontaneous awareness, admin-triggered refresh

### UI Refactoring
- [x] Shared helpers extracted to lib/formatting.py
- [x] CI logo in sidebar, colour fix, CSS centralised

### Brand Alignment
- [x] Montserrat font (replaced DM Sans + Fraunces)
- [x] Charcoal sidebar (replaced Navy)
- [x] 6 brand colours + 60%/20% tints in config.py
- [x] Chart colour order: Cyan, Purple, Yellow, Green, Red, Charcoal
- [x] 12px border-radius standardised across all screens
- [x] Shadow-on-hover on cards
- [x] Root CLAUDE.md brand section updated

---

## OPEN

### P1 — Decision Screen Pattern
**What:** Restructure all 8 screens into the CI "Decision Screen" layout: KPI row with trend arrows and confidence badges at top, 70/30 primary viz + secondary panel split, context footer with trust indicators.

**Why:** Brand design system requires every portal page to be a decision screen: one viewport, enough context to act, drill-down in 1-2 clicks.

**Effort:** L | **Priority:** P1

#### Phase 1: Shared Components
- [x] Create `lib/components/decision_kpi.py` — KPI card with trend arrow, change value, confidence badge (n with colour coding). Plus `decision_kpi_row()` for 3-5 in a row.
- [x] Create `lib/components/context_bar.py` — Compact bar replacing ad-hoc subheader + period banner. Shows screen name, insurer, product, period, sample sizes.
- [x] Create `lib/components/context_footer.py` — Data freshness timestamp, methodology link, sample size, confidence level.
- [x] Add `render_narrative_compact()` to `lib/components/narrative_panel.py` — Compact variant: no expander, headline + 2 findings, "Show detail" for rest.
- [x] Add CSS classes for decision layout to `lib/config.py` (`.decision-kpi`, `.confidence-badge`, `.context-footer`).

**Layout note:** AI narrative goes at the TOP of each screen (below context bar, above KPIs). It sets the story before the user sees the data. All 8 screens must follow this order: context bar, narrative, KPI row, primary+secondary split, context footer.

#### Phase 2: Pilot Screen
- [x] Convert Switching (Screen 5) — KPIs: Retention, Switching, Net Flow. Primary: flow index. Secondary: sources/destinations + departed sentiment + links.
- [ ] Visual QA: KPIs + primary chart visible without scroll on 1080p.

#### Phase 3: Remaining Screens
- [x] Convert Shopping (Screen 3) — KPIs: Shopping Rate, Conversion, Retention. Primary: trend. Secondary: reasons + narrative.
- [x] Convert Pre-Renewal (Screen 2) — KPIs: % Higher, % Lower, Avg Change. Primary: price direction. Secondary: tenure + narrative.
- [x] Convert Channels (Screen 4) — KPIs: Top Channel, PCW Usage, Quote Reach. Primary: channel bars. Secondary: mismatch + narrative.
- [x] Convert Awareness (Screen 1) — KPIs: Awareness Rate, Market Avg, Rank. Primary: trend/ranking. Secondary: slopegraph + narrative.
- [x] Convert Reasons (Screen 6) — KPIs: Active Q, Top Reason, Index. Primary: reason table. Secondary: highlight + narrative.
- [x] Convert Satisfaction (Screen 7) — KPIs: Satisfaction, NPS, Departed NPS. Primary: brand perception. Secondary: matrix + narrative.
- [x] Convert Claims (Screen 8) — KPIs: Satisfaction, Market Avg, Gap. Primary: insurer bars. Secondary: stars + narrative.

#### Phase 4: Polish
- [x] Standardise chart heights (primary: 280-320px, secondary: 200px max).
- [x] Remove redundant section_divider calls (done during Phase 3).
- [ ] Full visual QA pass across all 8 screens.

---

### P2 — Add logging to powerbi.py
**What:** Add `logging.warning()` / `logging.info()` calls to `lib/powerbi.py` token persistence functions. `lib/db.py` already has logging.

**Why:** Token failures are currently silent. A few structured log lines would make production support possible.

**Effort:** S | **Priority:** P2

---

### P2 — Add pytest suite for analytics functions
**What:** Create `tests/test_analytics.py` with unit tests for `calc_insurer_rank`, `calc_rolling_avg`, `calc_net_flow`, and DuckDB roundtrip.

**Why:** Zero automated tests in the codebase. These functions have clear inputs/outputs and meaningful edge cases.

**Key test cases:**
- `calc_insurer_rank` with tied retention rates
- `calc_net_flow` with `base=0` and `base=None`
- `calc_rolling_avg` with a 1-row DataFrame
- DuckDB roundtrip: verify DataFrame dtypes preserved
- Token expiry boundary at exactly `time.time() + 300`

**Effort:** M | **Priority:** P2
