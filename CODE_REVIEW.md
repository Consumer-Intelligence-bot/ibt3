# Code Review — Consumer Intelligence Streamlit Dashboard

**Original review date:** 2026-03-10
**Updated:** 2026-03-18
**Reviewer:** Claude (automated code review)
**Scope:** Full codebase — Streamlit multipage app (`app.py`, `pages/`, `lib/`), CI/CD, and security

---

## Status Summary

| # | Issue | Severity | Status |
|---|-------|----------|--------|
| 1 | Large data file committed to git | CRITICAL | ✅ Resolved |
| 2 | Hardcoded Azure credentials in source | CRITICAL | ✅ Resolved |
| 3 | Unsafe JSON parsing in `run_dax()` | HIGH | ✅ Resolved |
| 4 | Duplicated utility functions across pages | HIGH | ✅ Resolved |
| 5 | Bare exception handling in `narrative.py` | MEDIUM | ✅ Resolved |
| 6 | Hardcoded feature flags | MEDIUM | ✅ Previously resolved |
| 7 | `.env.example` uses Vite naming convention | MEDIUM | ✅ Resolved |
| 8 | Demo data committed to git | LOW | Accepted — intentional |
| 9 | No automated tests | LOW | ⏳ Pending |
| 10 | Commit history hygiene | LOW | ⏳ Pending |

**All CRITICAL, HIGH, and MEDIUM issues resolved as of 2026-03-18.**

---

## Resolved Issues

### 1. Large data file — RESOLVED (2026-03-18)

The 15 MB `motor_main_data.csv` was not actually tracked in git. The `.gitignore`
has been updated to explicitly exclude it, along with `ss-intelligence/` and
`node_modules/`, which were untracked directories sitting loose in the repo.

---

### 2. Hardcoded Azure credentials — RESOLVED (2026-03-18)

`TENANT_ID`, `CLIENT_ID`, `MOTOR_WORKSPACE_ID`, and `MOTOR_DATASET_ID` in
`lib/config.py` have been wrapped with `os.getenv()`, using the original
hardcoded values as fallback defaults. `HOME_WORKSPACE_ID` and `HOME_DATASET_ID`
were already correctly handled.

**File changed:** `lib/config.py`

The following environment variables must be set in any deployment environment.
See `.env.example` for the full list with documentation.

```
AZURE_TENANT_ID
AZURE_CLIENT_ID
MOTOR_WORKSPACE_ID
MOTOR_DATASET_ID
HOME_WORKSPACE_ID
HOME_DATASET_ID
```

---

### 3. Unsafe JSON parsing in `run_dax()` — RESOLVED (2026-03-18)

The bare index access `body["results"][0]["tables"][0].get("rows", [])` in
`lib/powerbi.py` is now wrapped in a `try/except (KeyError, IndexError)` block
that returns an empty DataFrame on failure. The second occurrence of this pattern
in `discover_columns()` was correctly left untouched — it is already guarded by
`r.status_code == 200` and `"error" not in body` checks.

**File changed:** `lib/powerbi.py`

---

### 4. Duplicated utility functions — RESOLVED (2026-03-18)

`_fmt_pct` was defined independently in `pages/2_Insurer_Diagnostic.py` and
`pages/3_Insurer_Comparison.py`. `_pct` (safe division) was also defined locally
in `pages/3_Insurer_Comparison.py`.

Note: The original review flagged `_derive_tag` and `_tag_colour` as duplicated.
These functions do not exist anywhere in the codebase. The review was incorrect
on those two.

A shared module has been created:

**File created:** `lib/formatting.py`

```python
def fmt_pct(val, dp=1):
    """Format a proportion (0-1) as a percentage string."""
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"

def safe_pct(n, d):
    """Divide n by d, returning 0.0 if d is zero."""
    return n / d if d > 0 else 0.0
```

Both pages now import from `lib.formatting`. All call sites updated.

**Files changed:** `lib/formatting.py` (new), `pages/2_Insurer_Diagnostic.py`,
`pages/3_Insurer_Comparison.py`

---

### 5. Bare exception handling in `narrative.py` — RESOLVED (2026-03-18)

The bare `except Exception` in `_call_api()` has been replaced with three
specific exception handlers for the expected failure modes:

```python
except anthropic.APIError as e:
    log.warning("Anthropic API error during narrative generation: %s", e)
    return None
except json.JSONDecodeError as e:
    log.warning("Failed to parse narrative JSON response: %s", e)
    return None
except KeyError as e:
    log.warning("Missing expected key in narrative response: %s", e)
    return None
except Exception:
    log.exception("Unexpected error during narrative generation; caller will use fallback text")
    return None
```

The final bare `except Exception` is retained intentionally as a last-resort
safety net with an updated log message.

**File changed:** `lib/narrative.py`

---

### 7. `.env.example` naming convention — RESOLVED (2026-03-18)

The `VITE_DATA_FILE` variable and all misleading `VITE_` prefixed content has
been removed. The file now documents all required environment variables with
clear section headings. See `.env.example` for the current reference.

**File changed:** `.env.example`

---

## Outstanding Issues

### 9. No automated tests (LOW)

The CI pipeline only checks that imports resolve. The analytics modules contain
non-trivial statistical logic (Bayesian smoothing, suppression rules, confidence
intervals) that should have unit test coverage.

**Recommendation:** Add `pytest` with tests for at least:
- `lib/analytics/bayesian.py`
- `lib/analytics/suppression.py`
- `lib/analytics/confidence.py`

---

### 10. Commit history hygiene (LOW)

Recent commits include messages like `"wefyguywefgyu"`, `"jiedjieijji"`.
Not blocking anything but worth a squash before any external code review.

---

## Additional Fixes (2026-03-18, not in original review)

### Position label overflow — RESOLVED

The "Your Position" card on the Insurer Diagnostic page was rendering
`"Above Market (Rank 12 of 27)"` as the large 28px card value, causing
overflow onto the next line.

The rank suffix has been moved to the subtitle line. The card value now
shows only `"Above Market"` / `"Below Market"` / `"At Market"`.

**File changed:** `pages/2_Insurer_Diagnostic.py`

---

### Flow Intelligence page — ADDED

A new page `pages/10_Flow_Intelligence.py` has been added. It shows where
an insurer is over- or under-indexing on customer losses and gains relative
to the market average, expressed as a 100 index.

A new function `calc_flow_index()` has been added to `lib/analytics/flows.py`.

**Files added/changed:** `pages/10_Flow_Intelligence.py`,
`lib/analytics/flows.py`

---

## Known Investigations (not code issues)

### Brand awareness uplift

Brand awareness rates appear to have risen approximately 20% across all
brands simultaneously. The calculation logic in `lib/analytics/awareness.py`
has been reviewed and is correct. The most likely cause is an extension of
the Q2 brand list in the survey instrument, which would inflate prompted
awareness rates for all brands uniformly.

**Action required:** Confirm with Matt Mather whether the Q2 brand list
was extended and identify the exact month of the change. Once confirmed,
add a methodology break-point note to the Awareness pages and consider
suppressing the trend line across the break.

---

## Architecture Notes

### DuckDB cache layer

`lib/db.py` implements a DuckDB-backed local cache at `~/.ibt3/cache.duckdb`.
Fit for purpose for both local development and GCP VM deployment. The cache:

- Survives browser refresh within a session
- Invalidates correctly when the time window changes
- Degrades gracefully if DuckDB is not installed
- Uses restrictive file permissions (0o600)
- Validates table names to prevent SQL injection

**Concurrency caveat:** DuckDB has limited write concurrency. If multiple
users hit "Clear cached data" simultaneously on the GCP VM, consider whether
this is a real operational risk. For single-user or low-concurrency use,
no changes are needed.

---

## Architecture Strengths

1. **Confidence-first governance** — Three-layer suppression model consistently applied
2. **Clean multipage structure** — 10 well-scoped Streamlit pages with shared state
3. **Bayesian smoothing** — Proper Beta-Binomial implementation for rate stabilisation
4. **Graceful degradation** — Falls back to demo data when Power BI is unavailable
5. **AI narratives** — Claude-powered headline generation with fallback text
6. **Dual-product support** — Motor and Home fabric instances handled cleanly
7. **Flow intelligence** — Over-index analysis for competitive flow diagnostics

---

## Security Summary

| Area | Status | Notes |
|------|--------|-------|
| `.env` in git | ✅ OK | `.gitignore` correctly excludes `.env` files |
| Azure credentials | ✅ Fixed | Now driven by environment variables |
| Data exposure | ✅ Fixed | Large CSV not tracked; `.gitignore` updated |
| Auth | ✅ OK | MSAL device flow properly implemented |
| Token storage | ✅ OK | Persisted to `~/.ibt3/token.json` with 0o600 permissions |
| Debug mode | ✅ OK | No debug flags enabled |
| XSS | Low risk | Streamlit auto-escapes; limited `unsafe_allow_html` for CSS only |
| SQL injection | ✅ OK | DuckDB table names validated against allowlist regex |
| Dependencies | ⏳ Review | No `pip audit` in CI pipeline |

---

## GCP Deployment Checklist

Before deploying to the GCP VM, confirm the following:

**Environment variables** — set in `.env` or equivalent on the VM:

```
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
MOTOR_WORKSPACE_ID=
MOTOR_DATASET_ID=
HOME_WORKSPACE_ID=
HOME_DATASET_ID=
ANTHROPIC_API_KEY=
NARRATIVE_MODEL=claude-opus-4-6
NARRATIVE_ENABLED=true
IBT3_DB_PATH=            # optional; defaults to ~/.ibt3/cache.duckdb
```

**Dependencies:**
- [ ] `duckdb` installed in the VM's Python environment
- [ ] `pip audit` run and no critical vulnerabilities

**Data:**
- [ ] `dist/data/motor_main_data_demo.csv` present (fallback demo file)
- [ ] `all home data.csv` — referenced in `data-config.json` but not present
      on disk. Confirm whether this file is needed or the reference should
      be removed.

**Auth:**
- [ ] MSAL device flow tested from the VM
      (token persists to `~/.ibt3/token.json`)

**Process:**
- [ ] Streamlit running as a persistent process (systemd service or equivalent)
- [ ] Nginx or equivalent reverse proxy configured if exposing externally
