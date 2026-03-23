# TODOS

## P2 — Add logging to powerbi.py

**What:** Add `logging.warning()` / `logging.info()` calls to `lib/powerbi.py` token persistence functions. `lib/db.py` already has logging.

**Why:** Token failures are currently silent. A few structured log lines would make production support possible.

**Effort:** S | **Priority:** P2

---

## P2 — Add pytest suite for analytics functions

**What:** Create `tests/test_analytics.py` with unit tests for `calc_insurer_rank`, `calc_rolling_avg`, `calc_net_flow`, and DuckDB roundtrip.

**Why:** Zero automated tests in the codebase. These functions have clear inputs/outputs and meaningful edge cases.

**Key test cases:**
- `calc_insurer_rank` with tied retention rates
- `calc_net_flow` with `base=0` and `base=None`
- `calc_rolling_avg` with a 1-row DataFrame
- DuckDB roundtrip: verify DataFrame dtypes preserved
- Token expiry boundary at exactly `time.time() + 300`

**Effort:** M | **Priority:** P2

---

## DONE

- [x] Extract shared formatting helpers to `lib/formatting.py` (was P2)
- [x] Customer lifecycle dashboard (Sprints 1-7)
- [x] Editorial design overhaul
- [x] Pet insurance integration
- [x] EAV-to-wide migration
- [x] UI refactoring (CI logo, CSS, colours)
