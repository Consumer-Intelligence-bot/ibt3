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

### ~~P2 — Add pytest suite for analytics functions~~ DONE
**63 tests passing** across 6 functions: `calc_net_flow`, `calc_insurer_rank`, `calc_rolling_avg`, DuckDB roundtrip, `calc_toma_share`, `calc_awareness_rates`. See `tests/test_analytics.py`.

---

### P1 — Ann 1:1 Feedback (26 Mar 2026)

**Source:** Transcript of Ian + Ann Constantine (super user) walkthrough session.

#### System-Wide / Architectural

##### A1: Incomplete month handling
**What:** Trailing months with partial fieldwork cause misleading drops in all trend charts. Either hide the last incomplete month from client view, or show widening confidence intervals.
**Why:** Ann: "You've either got to show it and we're confident in it, or we don't show it."
**Effort:** L | **Priority:** P1
- [ ] Detect incomplete months (fieldwork count below threshold)
- [ ] Option A: Suppress last incomplete month from trend lines
- [ ] Option B: Show CI bands that widen as sample shrinks
- [ ] Apply consistently across all screens with time-series charts

##### A2: AI narrative quality overhaul
**What:** Rewrite narrative engine prompts to produce plain English headlines. Ann's test: extract all headlines into a summary, they should make sense standalone.
**Why:** Every headline reads "jargony" and "clunky." Too short and compressed, reads like American newspaper headlines.
**Effort:** M | **Priority:** P1
- [ ] Rewrite system prompts: plain English, state the "so what," always compare to market
- [ ] Always name #1 if referencing a rank position
- [ ] Always explain direction (better/worse than market, not just raw numbers)
- [ ] Test headlines standalone: do they make sense without the charts?

##### A3: Market context on every metric
**What:** Every KPI, chart, and narrative must show insurer value vs market baseline.
**Why:** Nearly every metric prompted "but how does that compare to the market?" Single most repeated theme in the session.
**Effort:** L | **Priority:** P1
- [ ] Audit all KPI cards: ensure each shows insurer vs market
- [ ] Audit all charts: ensure market comparison is visible
- [ ] Audit all narratives: ensure market context is stated

##### A4: Peer group / multi-brand comparison
**What:** Allow selecting peer groups (e.g. "brands like me" or "Direct Line vs Aviva") rather than just one insurer vs all market.
**Why:** Ann: "I would have been looking at Direct Line versus Aviva, because Aviva is our key competitor."
**Effort:** L | **Priority:** P2
- [ ] Design peer group selection UI (multi-select insurer dropdown)
- [ ] Update analytics to compute metrics for custom peer group as baseline
- [ ] Update charts and KPIs to show insurer vs peer group

##### A5: Question text on every screen
**What:** Add expandable info icon per section showing the survey question text and calculation methodology.
**Why:** Ann: "We absolutely at the top of each section have to have what the question is."
**Effort:** M | **Priority:** P1
- [ ] Create reusable info icon / eye icon component with expandable panel
- [ ] Map each screen section to its source question(s)
- [ ] Add calculation methodology where we derive values (e.g. average from bandings)

##### A6: Methodology links open in-page
**What:** "How is this calculated?" links should open as a modal or panel overlay, not navigate away.
**Why:** Clicking the link navigates off the current screen, losing context.
**Effort:** S | **Priority:** P1
- [ ] Replace navigation links with modal/overlay for methodology content

##### A7: No absolute numbers rule
**What:** System-wide policy: display percentages, percentage changes, ranks, rank changes, or indices. Never raw respondent counts in client-facing views.
**Why:** Ann: "We should not have an absolute number in any of this."
**Effort:** M | **Priority:** P1
- [ ] Audit all screens for raw respondent counts
- [ ] Convert to percentages, indices, or rank changes
- [ ] Sample sizes in tooltips only, not primary display

##### A8: Confidence indicators over sample sizes
**What:** Replace raw "n=" sample size displays with confidence badges (high/medium/low) or CI ranges.
**Why:** Ann: "I'm less interested in the sample size. I'm more interested in the confidence."
**Effort:** M | **Priority:** P1
- [ ] Define confidence thresholds (high/medium/low based on n and CI width)
- [ ] Create confidence badge component (colour-coded)
- [ ] Replace sample size displays across all screens
- [ ] Keep raw n in tooltip for internal users

##### A9: Rating factor demographics
**What:** Add key rating factors as demographic breakdowns: payment type, licence held, telematics, NCD, plus top 4 pricing drivers from Apollo/GOCO.
**Why:** Ann + Ian identified these as the most useful demographic cuts for clients.
**Effort:** M | **Priority:** P2
- [ ] Identify available rating factor columns in the data model
- [ ] Add payment type, licence held, telematics to demographic breakdowns
- [ ] Reference Apollo/GOCO top rating factors

##### A10: Multi-select demographic filters
**What:** Age band and region filters should be multi-select dropdowns, not single-value sliders.
**Why:** "I might want to do 18-24 AND 25-34 AND 65+ as another group."
**Effort:** M | **Priority:** P1
- [ ] Replace age band slider with multi-select dropdown
- [ ] Replace region slider with multi-select dropdown
- [ ] Update all analytics to handle multiple selected values

##### A11: Customer journey flow diagram
**What:** Recreate the "journey map" visual from the old system that maps every stage of the customer lifecycle with market vs brand overlay.
**Why:** Ann: "That is a very good visual that we've got in the old system."
**Effort:** L | **Priority:** P2
- [ ] Design journey map layout (stages: pre-renewal, shopping, switching, post-renewal)
- [ ] Implement as a Streamlit component or chart
- [ ] Show market vs selected brand at each stage

---

#### Screen 2: Pre-Renewal Context

- [ ] **Font size:** Increase AI narrative and facts section font size (currently "almost impossible to read")
- [ ] **Headline rewrite:** Replace jargony AI headlines with plain English (e.g. "First Central customers are more likely to shop around if their price goes up")
- [ ] **Facts need market comparison:** Show insurer % alongside market % explicitly (e.g. "47% higher vs market 48%")
- [ ] **Tenure chart layout:** Move from right-hand side to more prominent position
- [ ] **Tenure 6-8 year buckets:** Merge into single band (sample artefact causing 1% dip)
- [ ] **Q6A/Q6B combine charts:** Merge "higher by how much" and "lower by how much" into single plus/minus chart
- [ ] **Price banding white space:** Tighten axis, remove gaps between bandings
- [ ] **Price direction as index:** Replace two side-by-side bars with single index value (insurer vs market)
- [ ] **Add pound sign:** Show "£21" not "+21" on average price change
- [ ] **Age/region side by side:** Reduce white space, place demographic breakdowns in columns
- [ ] **Add more demographics:** Payment type, tenure, licence held, telematics (see A9)
- [ ] **Page title clarity:** Show "[Insurer]'s pre-renewal price analysis" at top of page

---

#### Screen 1: Awareness & Consideration

- [x] **Fix 12,000% share of TOM:** Calculation bug producing nonsense percentage
- [x] **Restore top-N slider:** Default to top 10, allow user to adjust (top 8 is a weird metric)
- [x] **Ranking chart date labels:** Rotated -45 degrees for readability
- [x] **Remove or fix TOM vs Total scatter:** Removed (unreadable, agreed not needed)
- [x] **Fix sub-tab naming:** Renamed to "Prompted Awareness" / "Unprompted (Q1)"
- [ ] **Remove mystery white box:** Unexplained white box with purple border below tab header
- [x] **Increase narrative font size:** Same issue as Pre-Renewal
- [ ] **Rewrite prompted awareness headline:** Make plain English, less clunky
- [ ] **Equalise KPI box sizes:** "Aviva Awareness 63.3" and "Market Average 22.4" boxes should be same width
- [x] **Show who is #1:** If narrative says "second place," always state who is first
- [x] **Fix period comparison key error:** "change PP" key error appearing on screen
- [x] **Fix age band filter:** Changing age band slider does not update awareness ranking
- [ ] **Multi-select demographic filters:** Replace sliders with multi-select dropdowns (see A10)

---

#### Screen 5: Switching & Flows

- [ ] **Add journey map visual:** Recreate old-system flow diagram (see A11)
- [x] **Top movers: show % not absolute:** Now shows % of total flow volume
- [x] **Net flow: show % only:** KPI value is now percentage only, raw count in subtitle
- [ ] **Investigate net flow vs switching contradiction:** Switching rate positive but net flow negative needs explanation or bug fix
- [x] **Simplify bar colours:** Red/green for over/under index, CI_GREY for neutral (removed CI_BLUE)
- [x] **Index line: remove duplicate label:** Removed annotation text, kept axis title only
- [ ] **Index line: align label to line:** Label should sit exactly on the dotted line position
- [ ] **Index line: make thicker:** Currently too thin and hard to spot
- [x] **Fix "market average" label:** Renamed to "Expected rate"
- [ ] **Departed sentiment box:** Make larger, add market comparison for NPS
- [ ] **KPI colour logic:** Remove purple for "same." Use green = better, red = worse, grey = on par
- [ ] **Arrow direction clarity:** Disambiguate: does arrow mean trend direction or vs-market direction? Be consistent across all KPIs
