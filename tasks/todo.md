# IBT3 TODO

## FIX NOW (Demo Feedback — 2026-03-27)

### Branding and Navigation

- [ ] Logo is too small and white. Needs proper brand treatment.
- [ ] Add page header with clear title (e.g. "Insurance Behaviour Tracker").
- [ ] Tabs look like text. Convert to visible, clickable buttons so users understand they are interactive.
- [ ] Add short descriptions to each section header explaining the metric and which survey question it derives from. Use consistent "about this data" wording everywhere.

### Charts and Layout

- [ ] Awareness trends chart takes only 30% of space. Flip to 50/50 with the current awareness chart.
- [ ] Add brand count slider to awareness trends chart (matching the one on current awareness chart).
- [ ] KPI summary boxes are inconsistent in size. Fix to uniform size.
- [ ] Colour coding: remove purple/black, replace with charcoal as neutral. Add legend. Red = bad, green = good, charcoal = neutral.
- [ ] Add label to confidence interval bars on satisfaction chart stating what they represent and the confidence level (95%).
- [ ] Period comparison chart label should read "most recent three months vs same period last year" rather than raw date ranges.

### AI Narrative

- [ ] Change narrative from auto-generating on page load to on-demand (user clicks button, then it generates).
- [ ] Keep refining tone. Stuart confirmed it reads well.

### Data Issues (Investigate Urgently)

- [x] Satisfaction distribution chart (Q47) showing implausible results (97% scoring 4). **Root cause: Q47 stores binary codes (2=dissatisfied, 4=satisfied), not a 1-5 scale. Fixed: chart now shows "% Satisfied / Dissatisfied", retention matrix uses proper bands. 24 new tests added.**
- [ ] Q46 data appears missing from satisfaction table. **Root cause: No Q46_* columns in DuckDB. Power BI Subject column is likely null for Q46 rows. Needs investigation during next Power BI refresh.**
- [x] Brand dropdown lists not in alphabetical order. **Already implemented: sorted() applied at dimension builder and all dropdown locations.**

### Stars Rating

- [ ] Relative performance star system needs rethink. A score of 3.82 getting 1 star is confusing. Show actual score alongside relative star rating.

---

## OPEN (Previous P2 Items)

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

---

## BACKLOG (Deferred — Second Wave)

### Comparison and Segmentation
- [ ] Side-by-side brand comparison view (two brands, metrics in parallel)
- [ ] Peer group settings (user-defined peer group, toggleable across all modules)
- [ ] Age group side-by-side view (two age groups in parallel, not just filter)
- [ ] Cross-product "all products" awareness view (motor + home + travel + pet at GI level, with methodology caveat)

### Analysis Depth
- [ ] Claims drivers analysis (which claims journey attributes drive overall satisfaction score)
- [ ] Brand conversion funnel (awareness > consideration > conversion per brand)
- [ ] Tenure by satisfaction cross-tab (does satisfaction decline at specific tenure points?)
- [ ] NPS by journey phase (new customer / renewer / departed segments)

### Data Additions
- [ ] Shopping journey module (copy from current IBT portal)
- [ ] Add-on products (windscreen, legal, etc. with same insurer)
- [ ] Smaller product lines (SME, van, landlord — Stuart to send survey instruments)
- [ ] Consumer Duty data module
- [ ] Data download / export button on chart views
