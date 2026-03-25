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

---

## OPEN

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
