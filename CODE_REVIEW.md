# Code Review — Shopping & Switching Intelligence

**Date:** 2026-03-06
**Reviewer:** Claude (automated code review)
**Scope:** Full codebase — React frontend (`src/`), Python Dash backend (`ss-intelligence/`), CI/CD, and security

---

## Executive Summary

This is a well-structured, dual-stack analytics dashboard for insurance market intelligence. The codebase demonstrates solid separation of concerns, a clear data governance model, and thoughtful confidence-first design. However, there are several issues that should be addressed before production delivery — most critically, **dev-only code that must be removed**, **`.env` files committed to the repo**, and **duplicated utility logic**.

### Severity Legend

- **CRITICAL** — Must fix before delivery / production
- **HIGH** — Should fix; causes bugs, security issues, or major maintainability problems
- **MEDIUM** — Recommended; improves quality, performance, or readability
- **LOW** — Suggestion; nice-to-have improvements

---

## CRITICAL Issues

### 1. `.env` files committed to version control

**Files:** `.env`, `.env.production`

Both `.env` files are tracked in git. While they currently only contain `VITE_DATA_FILE`, this sets a dangerous precedent. If secrets (API keys, auth credentials) are ever added, they will be in the git history. The `.gitignore` does **not** exclude `.env`.

**Recommendation:**
- Add `.env` and `.env.production` to `.gitignore`
- Remove from git tracking: `git rm --cached .env .env.production`
- Add a `.env.example` with placeholder values instead

### 2. Dev-only code flagged "REMOVE BEFORE DELIVERY" (7 occurrences)

Multiple `TODO: REMOVE BEFORE DELIVERY` markers exist throughout the codebase:

| Location | Description |
|----------|-------------|
| `src/App.jsx:20` | Ctrl+Shift+V validation keyboard shortcut |
| `src/App.jsx:87` | `/validation` dev-only route |
| `src/context/DashboardContext.jsx:75-87` | `devInsurerList` with n>=5 threshold |
| `src/utils/brandConstants.js:28` | `devOverride: 5` threshold constant |
| `src/components/shared/Header.jsx:54-56` | Dev-only insurer list in dropdown |
| `src/components/shared/Header.jsx:175-201` | "DEV" section in insurer dropdown UI |

**Impact:** In production, this would expose all insurers with n>=5 (far below the n>=50 publishable threshold), violating the confidence-first governance model that is central to the product.

**Recommendation:** Remove all dev-only code paths before delivery. Consider using feature flags controlled by environment variables instead of inline TODOs.

### 3. `debug=True` in Dash app entry point

**File:** `ss-intelligence/app.py:86`

```python
app.run(debug=True, host="0.0.0.0", port=8050, use_reloader=False)
```

While this only applies to `__main__` (not Gunicorn), it's still risky if someone starts the app directly. Debug mode exposes Dash's interactive debugger which can execute arbitrary Python code.

**Recommendation:** Use `debug=os.getenv("DASH_DEBUG", "false").lower() == "true"` or simply `debug=False`.

---

## HIGH Issues

### 4. Duplicated `filterByInsurer` function (4 copies)

The same `filterByInsurer` utility is defined independently in:
- `src/utils/measures/marketPulseMeasures.js:6`
- `src/utils/measures/screen1Measures.js:4`
- `src/utils/measures/screen2Measures.js:4`
- `src/utils/measures/renewalJourneyMeasures.js:6`

**Recommendation:** Extract to a shared utility module (e.g., `src/utils/measures/shared.js`) and import.

### 5. Duplicated `cardStyle` / `labelStyle` objects

`cardStyle` and `labelStyle` are defined identically in:
- `src/components/shared/KPICard.jsx:126-141`
- `src/components/screen1/MarketPulse.jsx:86-101`
- `src/components/screen2/ShopOrStay.jsx:28-43` (as `kpiCardStyle`/`kpiLabelStyle`)

**Recommendation:** Export shared styles from a single location or use CSS classes.

### 6. Top-level `await` in API index

**File:** `src/api/index.js:10-11`

```js
const api = useMocks
  ? await import('./mockApi.js').then(m => m.mockApi)
  : await import('./realApi.js');
```

Top-level `await` requires ES modules and can cause issues with some bundler configurations and testing frameworks. It also means the decision is made once at module load time and cannot be changed.

**Recommendation:** Consider lazy initialization or a factory pattern that defers the import.

### 7. `loadCSV` doesn't check HTTP status before parsing

**File:** `src/utils/loadCSV.js:10`

```js
const response = await fetch(`${base}data/${filename}`);
const text = await response.text();
```

If the fetch returns a 404, `response.text()` will return HTML error content, which PapaParse will silently parse into garbage data.

**Recommendation:** Add `if (!response.ok) throw new Error(...)` before parsing.

### 8. Hardcoded market composition values in market view

**File:** `src/utils/measures/renewalJourneyMeasures.js:329-330`

```js
nonShoppers: { label: 'Non Shoppers', pct: nonShoppers.length / total, marketPct: 0.168 },
retained: { label: 'Retained', pct: retainedCount / total, marketPct: 0.42 },
switchedInto: { label: 'Switched Into', pct: switchedIntoCount / total, marketPct: 0.412 },
```

These hardcoded `marketPct` values (0.168, 0.42, 0.412) will become stale when data changes. They should be derived from the actual data.

**Recommendation:** Calculate these values dynamically from the data rather than hardcoding.

---

## MEDIUM Issues

### 9. No error boundary in React app

**File:** `src/App.jsx`

If any component throws during render, the entire app crashes with a white screen. There's no `ErrorBoundary` component wrapping the routes.

**Recommendation:** Add a React error boundary around `<Routes>` to show a user-friendly fallback UI.

### 10. Sequential API calls in `WhyTheyMove`

**File:** `src/components/screen4/WhyTheyMove.jsx:51-66`

The `useEffect` calls `getReasons()` in a serial `for...of` loop:
```js
for (const s of SECTIONS) {
  const res = await getReasons({...});
}
```

This means 3 API calls are made sequentially instead of in parallel.

**Recommendation:** Use `Promise.all()` or `Promise.allSettled()` as done in `ShopOrStay.jsx:213`.

### 11. Missing `key` props using array index

**File:** `src/components/screen2/RenewalFlow.jsx:131`

```js
{brands.map((b, i) => (
  <div key={i} ...>
```

Using array index as key can cause rendering issues if the list is reordered.

**Recommendation:** Use `b.brand` as the key since brand names should be unique within the list.

### 12. `useMemo` over-usage for constant suppression checks

**File:** `src/components/screen1/MarketPulse.jsx:143-145`

```js
const shopSupp = useMemo(() => checkSuppression(n), [n]);
const switchSupp = useMemo(() => checkSuppression(n), [n]);
const shopStaySupp = useMemo(() => checkSuppression(n), [n]);
```

Three separate `useMemo` calls with the same input `n` produce identical results. One call suffices.

**Recommendation:** Compute once: `const supp = useMemo(() => checkSuppression(n), [n]);` and reuse.

### 13. `hasOwnProperty` called directly on object

**File:** `src/utils/measures/whyTheyMoveMeasures.js:14`

```js
if (d && counts.hasOwnProperty(d)) counts[d]++;
```

Calling `hasOwnProperty` directly on an object is fragile if the object has a property named `hasOwnProperty`.

**Recommendation:** Use `Object.hasOwn(counts, d)` (ES2022) or `Object.prototype.hasOwnProperty.call(counts, d)`.

### 14. Inline styles throughout — no CSS extraction

All components use inline `style` objects. While this works, it:
- Makes responsive design harder
- Prevents hover/focus states (except via state)
- Cannot leverage CSS cascade, media queries, or animations
- Increases JS bundle size

**Recommendation:** Consider migrating to CSS modules, a utility framework (e.g., Tailwind), or at minimum extracting shared styles to `src/styles/`.

### 15. `proOptions: { hideAttribution: true }` for React Flow

**File:** `src/components/screen2/RenewalFunnel.jsx:567`

This option hides the React Flow attribution watermark. Using this without a React Flow Pro license violates their terms of service.

**Recommendation:** Either obtain a React Flow Pro license or remove this option.

### 16. Backend `shared.py` loads data at import time

**File:** `ss-intelligence/shared.py:33-59`

Data is loaded as module-level code during import. This means:
- Import errors crash the entire app on startup
- No way to reload data without restarting
- Testing requires data files to exist

**Recommendation:** Consider lazy loading with a `get_data()` function pattern or at minimum wrapping in more granular try/except blocks.

---

## LOW Issues

### 17. Inconsistent naming between frontend and backend

- Frontend uses `Shoppers === 'Shoppers'` (string comparison)
- Backend uses `IsShopper` (boolean derived field)
- Frontend: `checkSuppression(n)` returns `{ show, level, message }`
- Backend: `check_suppression(df_insurer, df_market)` returns `SuppressionResult`

While these operate independently, consistent naming would ease future API integration.

### 18. Magic numbers in SVG flow diagram

**File:** `src/components/screen2/RenewalFlow.jsx:167-223`

The `FlowArrows` component has dozens of hardcoded SVG coordinates. Any layout change requires manually updating all coordinates.

**Recommendation:** Consider computing positions from card positions or using a layout library.

### 19. `excludeNewToMarket` inconsistency

- `src/utils/measures/screen1Measures.js:12-15` — Filters by exact string match: `"I didn't have a motor insurance policy before my recent renewal/purchase"`
- `src/utils/measures/marketPulseMeasures.js:11-13` — Filters by `Switchers !== 'New-to-market'`

These are conceptually the same filter but use different criteria, which could produce different results.

### 20. No tests for frontend

The `ss-intelligence/tests/` directory has solid test coverage for the Python backend, but there are no unit tests for the React frontend's measure calculations, derived fields, or governance logic.

**Recommendation:** Add tests for critical utility functions (at minimum: `governance.js`, `deriveFields.js`, measure files).

### 21. `Placeholder` and `PlaceholderScreen` unused imports/components

`PlaceholderScreen` is only used for the "Brand Lens" placeholder route. Several `Placeholder` usages reference "Requires response data file" which is a developer-facing message, not user-facing.

**Recommendation:** Replace with user-friendly messaging (e.g., "Coming soon" or "This feature requires additional data configuration").

### 22. Commit history hygiene

Recent commits include messages like `"wefyguywefgyu"`, `"jiedjieijji"`, `"rijririrtjoji"`, `"uer reer erui"`. Consider squashing or rebasing before merging to main for a cleaner history.

---

## Security Summary

| Area | Status | Notes |
|------|--------|-------|
| `.env` in git | **Fix needed** | Not in `.gitignore` |
| Auth (backend) | Basic | Optional basic auth via env vars; no session management |
| Auth (frontend) | None | No authentication on the React SPA |
| XSS | Low risk | React auto-escapes; no `dangerouslySetInnerHTML` usage |
| CSRF | N/A | Read-only dashboard, no state-modifying endpoints |
| Data exposure | **Review** | Demo CSV data committed in `public/data/` |
| Debug mode | **Fix needed** | `debug=True` in `app.py` |
| Dockerfile | OK | Uses slim base, no root user issues |
| Dependencies | Review | No `npm audit` / `pip audit` visible in CI |

---

## Architecture Strengths

1. **Confidence-first governance** — The three-layer suppression model (system floor, CI-width, user preference) is well-designed and consistently applied
2. **Dual data pipeline** — Support for both flat exports and dual-table (MainData + AllOtherData) formats
3. **Bayesian smoothing** — Proper Beta-Binomial implementation with configurable prior strength
4. **Graceful degradation** — Proxy measures when API data is unavailable, demo data fallback
5. **Clean component structure** — Shared components (KPICard, ConfidenceBanner, SuppressionMessage) promote consistency

---

## Recommended Priority Order

1. Remove all "REMOVE BEFORE DELIVERY" dev code **(CRITICAL)**
2. Fix `.env` in git and `debug=True` **(CRITICAL)**
3. Fix `loadCSV` missing HTTP status check **(HIGH)**
4. Remove hardcoded market composition values **(HIGH)**
5. Deduplicate `filterByInsurer` and shared styles **(HIGH)**
6. Add React error boundary **(MEDIUM)**
7. Add frontend unit tests **(LOW)**
8. Improve commit hygiene **(LOW)**
