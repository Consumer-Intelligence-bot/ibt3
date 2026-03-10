# Code Review — Consumer Intelligence Streamlit Dashboard

**Date:** 2026-03-10
**Reviewer:** Claude (automated code review)
**Scope:** Full codebase — Streamlit multipage app (`app.py`, `pages/`, `lib/`), CI/CD, and security

---

## Executive Summary

This is a well-structured Streamlit multipage analytics dashboard for insurance market intelligence. The codebase has solid separation of concerns (pages → lib → analytics), a clear confidence-first data governance model, and good use of Streamlit session state for shared filters. Several issues should be addressed before production delivery.

### Severity Legend

- **CRITICAL** — Must fix before delivery / production
- **HIGH** — Should fix; causes bugs, security issues, or major maintainability problems
- **MEDIUM** — Recommended; improves quality, performance, or readability
- **LOW** — Suggestion; nice-to-have improvements

---

## CRITICAL Issues

### 1. Large data file committed to git

**File:** `public/data/motor_main_data.csv` (15 MB, ~74K rows)

A full production-scale CSV is tracked in git alongside the small demo file. This bloats the repo and may contain sensitive respondent data.

**Recommendation:**
- `git rm --cached public/data/motor_main_data.csv`
- Add `public/data/motor_main_data.csv` to `.gitignore` (keep only the demo file)
- Consider `git filter-branch` or BFG to remove from history if the data is sensitive

### 2. Hardcoded Azure credentials in source

**File:** `lib/config.py:9-13`

```python
TENANT_ID = "21c877f6-..."
CLIENT_ID = "9cd99ce2-..."
WORKSPACE_ID = "db6f5221-..."
DATASET_ID = "646c070f-..."
```

While these are application IDs (not secrets), they identify specific Azure resources and should not be in source code.

**Recommendation:** Move to environment variables with fallback defaults:
```python
TENANT_ID = os.getenv("AZURE_TENANT_ID", "21c877f6-...")
```

---

## HIGH Issues

### 3. Unsafe JSON parsing in `run_dax()`

**File:** `lib/powerbi.py`

```python
rows = r.json()["results"][0]["tables"][0].get("rows", [])
```

No validation of response structure. A malformed Power BI response will crash with `KeyError` or `IndexError` rather than returning an empty DataFrame gracefully.

**Recommendation:** Wrap in try/except and validate the response shape before indexing.

### 4. Duplicated utility functions across pages

**Files:** `pages/3_Headline.py` and others

`_pct()`, `_fmt_pct()`, `_derive_tag()`, `_tag_colour()` are defined independently in multiple pages.

**Recommendation:** Extract to a shared module (e.g., `lib/formatting.py`) and import.

---

## MEDIUM Issues

### 5. Bare exception handling in narrative generation

**File:** `lib/narrative.py`

```python
except Exception:
    log.exception("Narrative generation failed")
    return None
```

Catches all exceptions including `SystemExit` and `KeyboardInterrupt`. Should catch specific exceptions (`anthropic.APIError`, `json.JSONDecodeError`, `KeyError`).

### 6. ~~Hardcoded feature flags~~ (RESOLVED)

`NARRATIVE_MODEL` and `NARRATIVE_ENABLED` are now environment-variable driven via `os.getenv()` in `lib/config.py`, with sensible defaults.

### 7. `.env.example` uses React/Vite naming convention

**File:** `.env.example`

```
VITE_DATA_FILE=motor_main_data.csv
```

The `VITE_` prefix is a React/Vite convention and misleading in a Streamlit project. This variable also doesn't appear to be used anywhere in the codebase.

---

## LOW Issues

### 8. Demo data committed to git

**File:** `public/data/motor_main_data_demo.csv`

While small (33 KB) and intentionally for fallback, committing data files to git is generally avoided. Consider documenting this as an intentional design choice or hosting externally.

### 9. No automated tests

The CI pipeline (`ci.yml`) only checks that imports resolve. There are no unit tests for the analytics modules, which contain non-trivial statistical logic (Bayesian smoothing, suppression rules, confidence intervals).

**Recommendation:** Add `pytest` with tests for at least `lib/analytics/bayesian.py`, `lib/analytics/suppression.py`, and `lib/analytics/confidence.py`.

### 10. Commit history hygiene

Recent commits include messages like `"wefyguywefgyu"`, `"jiedjieijji"`. Consider squashing before merging to main.

---

## Security Summary

| Area | Status | Notes |
|------|--------|-------|
| `.env` in git | OK | `.gitignore` correctly excludes `.env` files |
| Azure credentials | **Fix needed** | Hardcoded in `lib/config.py` |
| Data exposure | **Fix needed** | Large CSV committed to repo |
| Auth | OK | MSAL device flow properly implemented |
| Debug mode | OK | No debug flags enabled |
| XSS | Low risk | Streamlit auto-escapes; limited `unsafe_allow_html` usage for CSS only |
| Dependencies | Review | No `pip audit` in CI pipeline |

---

## Architecture Strengths

1. **Confidence-first governance** — Three-layer suppression model (system floor, CI-width, user preference) consistently applied
2. **Clean multipage structure** — 9 well-scoped Streamlit pages with shared state via `st.session_state`
3. **Bayesian smoothing** — Proper Beta-Binomial implementation for rate stabilisation
4. **Graceful degradation** — Falls back to demo data when Power BI is unavailable
5. **AI narratives** — Claude-powered headline generation with fallback text

---

## Recommended Priority Order

1. Remove large data file from git **(CRITICAL)**
2. Move Azure credentials to env vars **(CRITICAL)**
3. Add defensive parsing in `run_dax()` **(HIGH)**
4. Deduplicate shared utility functions **(HIGH)**
5. Catch specific exceptions in narrative.py **(MEDIUM)**
6. Add pytest for analytics modules **(LOW)**
