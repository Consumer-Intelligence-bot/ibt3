# TODOS

## P2 — Extract shared formatting helpers

**What:** Move `_fmt_pct()` (and similar helpers like `_fmt_pp()`) from `pages/2_Insurer_Diagnostic.py` and `pages/3_Insurer_Comparison.py` into a shared `lib/formatting.py` module.

**Why:** DRY violation — identical function defined in two page files. `PLAN.md` already proposes this extraction. Will get worse as more pages are added.

**Effort:** S | **Priority:** P2

---

## P2 — Add logging to persistence layer

**What:** Add `logging.warning()` / `logging.info()` calls to `lib/db.py` (already partially done in rewrite) and `lib/powerbi.py` token persistence functions.

**Why:** Cache and token failures are currently silent. When things stop working, there's no diagnostic trail. A few structured log lines at each catch point would make production support possible.

**Effort:** S | **Priority:** P2

---

## P2 — Add pytest suite for analytics functions

**What:** Create `tests/test_analytics.py` with unit tests for `calc_insurer_rank`, `calc_rolling_avg`, `calc_net_flow` (with base param), and `save_dataframe`/`load_dataframe` roundtrip.

**Why:** Zero automated tests in the codebase. These functions have clear inputs/outputs and meaningful edge cases (tied ranks, window > data length, base=0, dtype preservation through DuckDB). Tests would catch regressions and serve as documentation.

**Key test cases:**
- `calc_insurer_rank` with tied retention rates
- `calc_net_flow` with `base=0` and `base=None`
- `calc_rolling_avg` with a 1-row DataFrame
- DuckDB roundtrip: verify DataFrame dtypes preserved
- Token expiry boundary at exactly `time.time() + 300`

**Effort:** M | **Priority:** P2
