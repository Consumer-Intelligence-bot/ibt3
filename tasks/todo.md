# IBT3 TODO

## OPEN

### P1 — AI Narrative Quality (A2)
**What:** Rewrite narrative engine prompts to produce plain English headlines.
**Why:** Both Ann and Ian flagged headlines as "jargony" and "clunky."
**Effort:** M | **Priority:** P1
- [ ] Rewrite system prompts: plain English, state the "so what," always compare to market
- [ ] Always name #1 if referencing a rank position
- [ ] Always explain direction (better/worse than market, not just raw numbers)
- [ ] Test headlines standalone: do they make sense without the charts?

---

### P1 — Question Text on Every Screen (A5)
**What:** Add expandable info icon per section showing the survey question text and calculation methodology.
**Why:** Ann: "We absolutely at the top of each section have to have what the question is."
**Effort:** M | **Priority:** P1
- [ ] Create reusable info icon component with expandable panel
- [ ] Map each screen section to its source question(s)
- [ ] Add calculation methodology where we derive values

---

### P1 — Multi-Select Demographic Filters (A10)
**What:** Age band and region filters should be multi-select dropdowns, not single-value sliders.
**Effort:** M | **Priority:** P1
- [ ] Replace age band slider with multi-select dropdown
- [ ] Replace region slider with multi-select dropdown
- [ ] Update all analytics to handle multiple selected values

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

### BLOCKED — Shopping Behaviour Historical Data
**What:** Ian to supply data from previous version of Shopping tab. Needed to verify current figures.
**Blocker:** Waiting on Ian.
