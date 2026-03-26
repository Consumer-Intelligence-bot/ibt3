# IBT3 TODO

## OPEN

### P0 — Tab bar text wrapping
**What:** All 8 tab labels word-wrap into illegible fragments at default viewport width ("Pre-Ren ewal Cont ext", "Sho ppin g Beh avio ur").
**Why:** Most visible UI defect. First thing a client sees. Makes the app look broken.
**Fix:** Shorten labels, or use `white-space:nowrap` with horizontal scroll, or abbreviate at narrow widths.
**Effort:** S | **Priority:** P0
- [ ] Shorten or abbreviate tab labels to fit 8 tabs without wrapping
- [ ] Test at 1080p, 1440p, and 768p widths

---

### P1 — Visual QA Fixes

- [ ] **Tenure vs Retention 100% bug:** Chart shows 100% for every bucket on market view. Hide when no insurer selected. (Pre-Renewal screen)
- [ ] **Visual QA on 1080p:** Verify KPIs + primary chart visible without scroll on all screens.

---

### P1 — AI Narrative Quality (A2)
**What:** Rewrite narrative engine prompts to produce plain English headlines. Ann's test: extract all headlines into a summary, they should make sense standalone.
**Why:** Every headline reads "jargony" and "clunky." Both Ann and Ian flagged this independently.
**Effort:** M | **Priority:** P1
- [ ] Rewrite system prompts: plain English, state the "so what," always compare to market
- [ ] Always name #1 if referencing a rank position
- [ ] Always explain direction (better/worse than market, not just raw numbers)
- [ ] Test headlines standalone: do they make sense without the charts?
- [ ] Applies to: Pre-Renewal headline rewrite, Awareness headline rewrite

---

### P1 — Market Context Audit (A3)
**What:** Every KPI, chart, and narrative must show insurer value vs market baseline.
**Why:** "But how does that compare to the market?" was the single most repeated theme across both feedback sessions.
**Effort:** L | **Priority:** P1
- [ ] Audit all KPI cards: ensure each shows insurer vs market
- [ ] Audit all charts: ensure market comparison is visible
- [ ] Audit all narratives: ensure market context is stated

---

### P1 — Question Text on Every Screen (A5)
**What:** Add expandable info icon per section showing the survey question text and calculation methodology.
**Why:** Ann: "We absolutely at the top of each section have to have what the question is."
**Effort:** M | **Priority:** P1
- [ ] Create reusable info icon / eye icon component with expandable panel
- [ ] Map each screen section to its source question(s)
- [ ] Add calculation methodology where we derive values (e.g. average from bandings)

---

### P1 — No Absolute Numbers Audit (A7)
**What:** System-wide policy: display percentages, percentage changes, ranks, rank changes, or indices. Never raw respondent counts in client-facing views.
**Why:** Ann: "We should not have an absolute number in any of this."
**Effort:** M | **Priority:** P1
- [ ] Audit all screens for raw respondent counts
- [ ] Convert to percentages, indices, or rank changes
- [ ] Sample sizes in tooltips only, not primary display

---

### P1 — Confidence Indicators (A8)
**What:** Replace raw "n=" sample size displays with confidence badges (high/medium/low) or CI ranges.
**Why:** Ann: "I'm less interested in the sample size. I'm more interested in the confidence."
**Effort:** M | **Priority:** P1
- [ ] Define confidence thresholds (high/medium/low based on n and CI width)
- [ ] Create confidence badge component (colour-coded)
- [ ] Replace sample size displays across all screens
- [ ] Keep raw n in tooltip for internal users

---

### P1 — Multi-Select Demographic Filters (A10)
**What:** Age band and region filters should be multi-select dropdowns, not single-value sliders.
**Why:** "I might want to do 18-24 AND 25-34 AND 65+ as another group."
**Effort:** M | **Priority:** P1
- [ ] Replace age band slider with multi-select dropdown
- [ ] Replace region slider with multi-select dropdown
- [ ] Update all analytics to handle multiple selected values

---

### P1 — Switching: Net Flow vs Switching Contradiction
**What:** Switching rate positive but net flow negative for some insurers. Needs explanation or bug fix.
**Why:** Ian flagged the numbers as contradictory. Either the calculation has a bug or the display needs to explain why they can diverge.
**Effort:** S | **Priority:** P1
- [ ] Investigate and document why net flow and switching rate can diverge
- [ ] Add explanatory tooltip or caption if it's expected behaviour

---

### P2 — Add Logging to powerbi.py
**What:** Add `logging.warning()` / `logging.info()` calls to `lib/powerbi.py` token persistence functions.
**Why:** Token failures are currently silent. A few structured log lines would make production support possible.
**Effort:** S | **Priority:** P2

---

### P2 — Verify Montserrat Font Loading
**What:** Brand spec requires Montserrat (400/700). Can't confirm from screenshots whether it's loading or falling back to system font.
**Effort:** S | **Priority:** P2
- [ ] Verify Montserrat is loaded via Google Fonts or local files
- [ ] Check fallback chain in CSS font-family declaration

---

### P2 — Confidence Badge Colour Clash
**What:** Green confidence badge uses the same green as "% Lower" KPI accent on the same row.
**Why:** Two different green elements side by side could confuse the meaning.
**Effort:** S | **Priority:** P2
- [ ] Review badge colour against adjacent KPI colours
- [ ] Consider using CI_CYAN or a distinct tint for confidence badges

---

### P2 — Peer Group / Multi-Brand Comparison (A4)
**What:** Allow selecting peer groups (e.g. "brands like me" or "Direct Line vs Aviva") rather than just one insurer vs all market. Currently scoped to awareness screen only.
**Why:** Ann: "I would have been looking at Direct Line versus Aviva, because Aviva is our key competitor."
**Effort:** L | **Priority:** P2
- [ ] Extend multi-brand comparison beyond awareness screen to all screens
- [ ] Design peer group selection UI (multi-select insurer dropdown in sidebar)
- [ ] Update analytics to compute metrics for custom peer group as baseline

---

### P2 — Rating Factor Demographics (A9)
**What:** Add key rating factors as demographic breakdowns: payment type, licence held, telematics, NCD, plus top 4 pricing drivers from Apollo/GOCO.
**Why:** Ann + Ian identified these as the most useful demographic cuts for clients.
**Effort:** M | **Priority:** P2
- [ ] Identify available rating factor columns in the data model
- [ ] Add payment type, licence held, telematics to demographic breakdowns
- [ ] Reference Apollo/GOCO top rating factors
- [ ] Applies to: Pre-Renewal "Add more demographics"

---

### P2 — Customer Journey Flow Diagram (A11)
**What:** Recreate the "journey map" visual from the old system that maps every stage of the customer lifecycle with market vs brand overlay.
**Why:** Ann: "That is a very good visual that we've got in the old system."
**Effort:** L | **Priority:** P2
- [ ] Design journey map layout (stages: pre-renewal, shopping, switching, post-renewal)
- [ ] Implement as a Streamlit component or chart
- [ ] Show market vs selected brand at each stage

---

### P3 — "Last Updated: Unknown" in Context Footer
**What:** Context footer shows "Last updated: Unknown" because no refresh timestamp is stored in session state.
**Fix:** Store refresh timestamp in DuckDB metadata during `init_ss_data()` and read it back on load.
**Effort:** S | **Priority:** P3
- [ ] Save refresh timestamp to DuckDB metadata in init_ss_data()
- [ ] Read and display in context footer
