# IBT3 TODO

## OPEN

### P1 — Tenure vs Retention 100% Bug
**What:** Chart shows 100% for every tenure bucket on market view. At market level every respondent is "retained" by definition.
**Fix:** Hide the chart when no insurer is selected.
**Effort:** S | **Priority:** P1
- [ ] Conditionally hide "Tenure vs Retention" on market view

---

### P1 — AI Narrative Quality (A2)
**What:** Rewrite narrative engine prompts to produce plain English headlines.
**Why:** Both Ann and Ian flagged headlines as "jargony" and "clunky."
**Effort:** M | **Priority:** P1
- [ ] Rewrite system prompts: plain English, state the "so what," always compare to market
- [ ] Always name #1 if referencing a rank position
- [ ] Always explain direction (better/worse than market, not just raw numbers)
- [ ] Test headlines standalone: do they make sense without the charts?

---

### P1 — Market Context Audit (A3)
**What:** Every KPI, chart, and narrative must show insurer value vs market baseline.
**Why:** Single most repeated theme across both feedback sessions.
**Effort:** L | **Priority:** P1
- [ ] Audit all KPI cards: ensure each shows insurer vs market
- [ ] Audit all charts: ensure market comparison is visible
- [ ] Audit all narratives: ensure market context is stated

---

### P1 — Question Text on Every Screen (A5)
**What:** Add expandable info icon per section showing the survey question text and calculation methodology.
**Why:** Ann: "We absolutely at the top of each section have to have what the question is."
**Effort:** M | **Priority:** P1
- [ ] Create reusable info icon component with expandable panel
- [ ] Map each screen section to its source question(s)
- [ ] Add calculation methodology where we derive values

---

### P1 — No Absolute Numbers Audit (A7)
**What:** System-wide: never show raw respondent counts in client-facing views.
**Why:** Ann: "We should not have an absolute number in any of this."
**Effort:** M | **Priority:** P1
- [ ] Audit all screens for raw respondent counts
- [ ] Convert to percentages, indices, or rank changes
- [ ] Sample sizes in tooltips only, not primary display

---

### P1 — Confidence Indicators (A8)
**What:** Replace raw "n=" displays with confidence badges or CI ranges.
**Why:** Ann: "I'm less interested in the sample size. I'm more interested in the confidence."
**Effort:** M | **Priority:** P1
- [ ] Define confidence thresholds (high/medium/low)
- [ ] Replace sample size displays across all screens
- [ ] Keep raw n in tooltip for internal users

---

### P1 — Multi-Select Demographic Filters (A10)
**What:** Age band and region filters should be multi-select dropdowns, not single-value sliders.
**Effort:** M | **Priority:** P1
- [ ] Replace age band slider with multi-select dropdown
- [ ] Replace region slider with multi-select dropdown
- [ ] Update all analytics to handle multiple selected values

---

### P1 — Switching: Net Flow vs Switching Contradiction
**What:** Switching rate positive but net flow negative for some insurers. Needs investigation.
**Effort:** S | **Priority:** P1
- [ ] Investigate and document why they can diverge
- [ ] Add explanatory tooltip if expected behaviour

---

### P2 — Add Logging to powerbi.py
**What:** Add `logging.warning()` / `logging.info()` to token persistence functions.
**Effort:** S | **Priority:** P2

---

### P2 — Verify Montserrat Font Loading
**What:** Confirm Montserrat is loading via Google Fonts, not falling back to system font.
**Effort:** S | **Priority:** P2
- [ ] Verify font loading in browser dev tools
- [ ] Check fallback chain in CSS

---

### P2 — Confidence Badge Colour Clash
**What:** Green confidence badge uses same green as "% Lower" KPI accent.
**Effort:** S | **Priority:** P2
- [ ] Consider using CI_CYAN or distinct tint for badges

---

### P2 — Peer Group / Multi-Brand on All Screens (A4)
**What:** Extend multi-brand comparison beyond awareness screen to all screens.
**Effort:** L | **Priority:** P2
- [ ] Design peer group selection UI in sidebar
- [ ] Update analytics for custom peer group baseline
- [ ] Update all screens

---

### P2 — Rating Factor Demographics (A9)
**What:** Add payment type, licence held, telematics, NCD as demographic breakdowns.
**Effort:** M | **Priority:** P2
- [ ] Identify available columns in the data model
- [ ] Add to Pre-Renewal and other screens

---

### P2 — Customer Journey Flow Diagram (A11)
**What:** Recreate the old "journey map" visual showing every lifecycle stage.
**Effort:** L | **Priority:** P2
- [ ] Design journey map layout
- [ ] Implement as Streamlit component
- [ ] Show market vs brand at each stage

---

### P3 — "Last Updated: Unknown" in Context Footer
**What:** Footer shows "Last updated: Unknown". Need to store refresh timestamp.
**Effort:** S | **Priority:** P3
- [ ] Save timestamp to DuckDB metadata in init_ss_data()
- [ ] Read and display in context footer

---

### BLOCKED — Shopping Behaviour Historical Data
**What:** Ian to supply data from previous version of Shopping tab. Needed to verify current figures.
**Blocker:** Waiting on Ian.
