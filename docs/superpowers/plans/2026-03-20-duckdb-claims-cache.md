# DuckDB Claims Cache — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DuckDB the single source of truth for all data including Claims (Q52/Q53). No Power BI auth needed on startup — only when admin triggers a refresh.

**Architecture:** During "Refresh from Power BI", pull Q52/Q53 claims data alongside the existing S&S data and persist all of it to DuckDB. On startup and page load, every page reads from DuckDB/session state only. The Claims page stops doing live Power BI queries and instead reads cached claims DataFrames. The Admin page cache banner is fixed to check actual data presence rather than metadata alone.

**Tech Stack:** Python, Streamlit, DuckDB, pandas

---

## File Map

| File | Action | Responsibility |
|------|--------|---------------|
| `lib/state.py` | Modify (lines 90-126, 128-160) | Add claims pull to `init_ss_data()`, add claims load to `load_from_db()` |
| `pages/7_Claims_Intelligence.py` | Modify (lines 54-76) | Load from session state cache instead of live Power BI |
| `pages/4_Admin_Governance.py` | Modify (lines 81-87) | Fix "No cached data" banner logic |
| `app.py` | Modify (lines 60-89) | Fallback: derive start/end months from cached DataFrame when metadata missing |

---

### Task 1: Add claims data to the Power BI refresh flow

**Files:**
- Modify: `lib/state.py:54-126`

The `init_ss_data()` function currently pulls MainData + OtherData (S&S questions) and saves to DuckDB. It needs to also pull Q52/Q53 claims summaries for both Motor and Home, and save those as separate DuckDB tables.

- [ ] **Step 1: Add claims pull to `init_ss_data()`**

In `lib/state.py`, add the Q52/Q53 imports at the top and extend `init_ss_data()` to pull and cache claims data. Add after line 23 (existing imports from `lib.powerbi`):

```python
from lib.powerbi import load_months, load_ss_maindata, load_ss_questions, load_q52, load_q53
```

Then at the end of `init_ss_data()`, after the existing `save_metadata` calls (after line 123), add:

```python
    # ---- Pull and cache Claims data (Q52/Q53) per product ----
    for product_key, ws_id, ds_id, mt, ot in [
        ("motor", MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID, main_table, other_table),
        ("home", HOME_WORKSPACE_ID, HOME_DATASET_ID, home_main_table, home_other_table),
    ]:
        q52 = load_q52(token, start_month, end_month, mt, ot,
                        workspace_id=ws_id, dataset_id=ds_id)
        q53 = load_q53(token, start_month, end_month, mt, ot,
                        workspace_id=ws_id, dataset_id=ds_id)
        if not q52.empty:
            save_dataframe(q52, f"claims_q52_{product_key}")
            st.session_state[f"claims_q52_{product_key}"] = q52
        if not q53.empty:
            save_dataframe(q53, f"claims_q53_{product_key}")
            st.session_state[f"claims_q53_{product_key}"] = q53
```

- [ ] **Step 2: Add claims load to `load_from_db()`**

In `lib/state.py`, extend `load_from_db()` to also restore claims tables into session state. Add after line 157 (before `return True`):

```python
    # Restore cached claims data
    for product_key in ("motor", "home"):
        for q_key in ("q52", "q53"):
            table = f"claims_{q_key}_{product_key}"
            if has_data(table):
                df_claims = load_dataframe(table)
                if not df_claims.empty:
                    st.session_state[table] = df_claims
```

- [ ] **Step 3: Commit**

```bash
git add lib/state.py
git commit -m "feat: pull and cache Q52/Q53 claims data in DuckDB during refresh"
```

---

### Task 2: Claims page reads from cache instead of live Power BI

**Files:**
- Modify: `pages/7_Claims_Intelligence.py:54-76`

The Claims page currently requires `token`, `start_month`, `end_month` in session state and does live DAX queries. Change it to read from session state cache. Only show a "no data" warning if claims tables are missing from cache.

- [ ] **Step 1: Replace the auth gate and live queries**

Replace lines 54-76 (from `# ---- Get shared state ----` through the `load_q53` call) with:

```python
# ---- Get cached claims data ----
product_key = product.lower()  # "motor" or "home"
q52_key = f"claims_q52_{product_key}"
q53_key = f"claims_q53_{product_key}"

q52_df = st.session_state.get(q52_key, pd.DataFrame())
q53_df = st.session_state.get(q53_key, pd.DataFrame())

start_month = st.session_state.get("start_month")
end_month = st.session_state.get("end_month")

if q52_df.empty:
    st.warning(
        "No claims data cached. Go to **Admin / Governance** and click "
        "**Refresh from Power BI** to pull data."
    )
    st.stop()
```

Also remove the now-unused imports. At the top of the file, remove these from the `lib.config` import:
- `MOTOR_WORKSPACE_ID`, `MOTOR_DATASET_ID`, `HOME_WORKSPACE_ID`, `HOME_DATASET_ID`

Remove the import line:
```python
from lib.powerbi import load_q52, load_q53
```

Remove the `_PRODUCT_FABRIC` dictionary (lines 33-46) as it is no longer needed.

- [ ] **Step 2: Fix the period label fallback**

The period label at line 68 will fail if `start_month`/`end_month` are None. Replace:

```python
period_label = f"{format_month(start_month)} to {format_month(end_month)}"
```

With:

```python
if start_month and end_month:
    period_label = f"{format_month(start_month)} to {format_month(end_month)}"
else:
    period_label = "All cached data"
```

- [ ] **Step 3: Commit**

```bash
git add pages/7_Claims_Intelligence.py
git commit -m "feat: claims page reads from DuckDB cache, no live Power BI auth needed"
```

---

### Task 3: Fix the Admin page "No cached data" banner

**Files:**
- Modify: `pages/4_Admin_Governance.py:81-87`

The banner reads `_metadata` from DuckDB for start/end months. If metadata save failed but data exists, this shows "No cached data" while stats display below. Fix it to use `has_data()` as the primary check, with metadata as a bonus for the period label.

- [ ] **Step 1: Fix the cache info logic**

Add `has_data` to the import on line 29:

```python
from lib.db import clear_data, has_data, load_metadata
```

Replace lines 81-83 with:

```python
cached_start = load_metadata("start_month")
cached_end = load_metadata("end_month")
if cached_start and cached_end:
    cache_info = f"Cached period: {format_year_month(int(cached_start))} to {format_year_month(int(cached_end))}"
elif has_data("df_motor"):
    cache_info = "Cached data available (period metadata missing)"
else:
    cache_info = "No cached data"
```

- [ ] **Step 2: Commit**

```bash
git add pages/4_Admin_Governance.py
git commit -m "fix: admin cache banner checks actual data presence, not just metadata"
```

---

### Task 4: Fix app.py startup — derive months from cached DataFrame when metadata missing

**Files:**
- Modify: `app.py:60-89`

If metadata is missing but the DataFrame loaded successfully, derive start/end months from the `RenewalYearMonth` column. This eliminates the need for any Power BI auth on startup.

- [ ] **Step 1: Replace the time window resolution block**

Replace lines 60-89 with:

```python
# ---- Resolve time window from cache ----
start_month = None
end_month = None

cached_start = st.session_state.get("cached_start_month")
cached_end = st.session_state.get("cached_end_month")

if cached_start and cached_end:
    start_month = cached_start
    end_month = cached_end
else:
    # Derive from cached DataFrame if metadata was missing
    df_motor = st.session_state.get("df_motor")
    if df_motor is not None and not df_motor.empty and "RenewalYearMonth" in df_motor.columns:
        months = sorted(df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist())
        if months:
            start_month = months[max(0, len(months) - 12)]
            end_month = months[-1]

# ---- Store time window in session state ----
if start_month and end_month:
    st.session_state["start_month"] = start_month
    st.session_state["end_month"] = end_month
```

This removes the fallback that tried to authenticate with Power BI on startup. The only path to Power BI auth is now the Admin page refresh button.

- [ ] **Step 2: Remove unused Power BI import attempt**

The `from lib.powerbi import get_token, get_main_table, load_months` import (old lines 73) is no longer needed and has been removed by the replacement above. Confirm `lib.powerbi` is not imported anywhere else in `app.py`.

- [ ] **Step 3: Commit**

```bash
git add app.py
git commit -m "fix: startup derives months from cached data, never attempts Power BI auth"
```

---

### Task 5: Verify end-to-end on server

- [ ] **Step 1: Push changes to GitHub**

```bash
cd /mnt/c/users/ianch/ibt3
git push origin main
```

- [ ] **Step 2: Deploy to ibt-portal server**

```bash
ssh -i ~/.ssh/id_ed25519 ianchughes@34.63.62.254 << 'SSHEOF'
cd ~/ibt3
git pull
source venv/bin/activate
pip install -r requirements.txt 2>/dev/null
pkill -f streamlit 2>/dev/null
sleep 2
nohup streamlit run app.py --server.port 8501 --server.address 0.0.0.0 </dev/null > streamlit.log 2>&1 &
disown
SSHEOF
```

- [ ] **Step 3: Verify startup loads from DuckDB without auth**

Wait 15 seconds, then check the server is responding:

```bash
ssh -i ~/.ssh/id_ed25519 ianchughes@35.246.107.130 "curl -s -o /dev/null -w 'HTTP %{http_code}' http://localhost:8501"
```

Expected: `HTTP 200`

- [ ] **Step 4: User verifies in browser**

1. Open `http://35.246.107.130:8501` — should show "Data loaded: 21,478 respondents"
2. Navigate to Admin / Governance — should show "Cached data available" or the period, NOT "No cached data"
3. Navigate to Claims Intelligence — should load from cache, no "Please authenticate" message
4. If claims data is empty (first time after code change), click "Refresh from Power BI" on Admin page to populate claims cache

**Note:** The first refresh after this change will pull Q52/Q53 data and cache it. Subsequent restarts will load everything from DuckDB with zero Power BI auth.
