# CLAUDE.md — IBT3 (IBT Portal)

## Application Architecture

### Single-page router pattern
- `app.py` is a router-based single-page app using `st.session_state["active_screen"]` with conditional rendering.
- Only the active screen's code executes (not `st.tabs`, which runs all tabs on every rerun).
- Navigation: horizontal tab bar via `st.columns` + `st.button` in `lib/components/header.py`.
- Admin and Methodology accessible via sidebar links below the main controls.
- Cross-screen navigation via `lib.state.navigate_to(screen, **kwargs)`.

### File structure
```
app.py                          # Router + header + data loading
screens/                        # One module per screen, each exports render(filters)
  __init__.py                   # Screen registry (SCREENS, ADMIN_SCREENS)
  switching.py                  # Screen 5: Switching & Flows
  reasons.py                    # Screen 6: Reasons & Drivers
  shopping.py                   # Screen 3: Shopping Behaviour
  channels.py                   # Screen 4: Channels & PCWs
  pre_renewal.py                # Screen 2: Pre-Renewal Context
  awareness.py                  # Screen 1: Awareness & Consideration
  claims.py                     # Screen 8: Claims Intelligence
  satisfaction.py               # Screen 7: Satisfaction & Loyalty
  comparison.py                 # Compare Insurers overlay
  admin.py                      # Admin / Governance
  methodology.py                # Methodology documentation
lib/
  components/                   # Reusable UI components
    header.py                   # Tab bar + global controls
    kpi_cards.py                # KPI card + paired layout
    paired_bars.py              # Insurer vs market bar chart
    cohort_heatmap.py           # Demographic heat map
    narrative_panel.py          # Collapsible AI narrative
    filter_bar.py               # Cross-screen filter display
  analytics/                    # Calculation modules (unchanged from pre-migration)
    pre_renewal.py              # Q6, Q6a/Q6b, Q21 calculations
    satisfaction.py             # Q47, Q48, Q46, Q40a/Q40b
    narrative_engine.py         # Per-screen AI narrative generation
    (all other existing modules)
  state.py                      # Session state, data loading, navigate_to()
  config.py, formatting.py, db.py, powerbi.py, narrative.py  # Core libs
```

### Screen contract
Every screen module exports `render(filters: dict)`. The filters dict contains:
`insurer`, `product`, `age_band`, `region`, `payment_type`, `selected_months`, `include_other`.

### DuckDB is the single source of truth
- All data lives in DuckDB (`~/.ibt3/cache.duckdb`). Every screen reads from `st.session_state`, which is populated from DuckDB on startup.
- No screen should ever make live Power BI queries. Power BI is only accessed during an admin-triggered refresh.
- No Power BI auth token is needed on startup. The only path to Power BI auth is the "Refresh from Power BI" button on the Admin screen.
- Claims data (Q52/Q53) is cached per product: `claims_q52_motor`, `claims_q52_home`, `claims_q53_motor`, `claims_q53_home`. Pet does not have claims data.
- Every screen must check data availability via the DataFrame in session state, never gate on `token` or Power BI auth state.

### Data loading flow
1. `app.py` checks DuckDB via `has_data("df_motor")`, calls `load_from_db()` which restores df_motor, dimensions, claims tables, and time window metadata into `st.session_state`.
2. If metadata (`start_month`/`end_month`) is missing, derive from the `RenewalYearMonth` column in the cached DataFrame.
3. Admin screen "Refresh from Power BI" calls `init_ss_data()` which pulls MainData, OtherData (pivoted to wide), and Q52/Q53 claims for both Motor and Home, then saves everything to DuckDB.

### Metadata is a weak link
- `save_metadata()` can fail silently (try/except with logging). If the DataFrame save succeeds but metadata fails, you get a working cache with no period label.
- Always have a fallback for metadata. Currently app.py derives months from the DataFrame if metadata is missing.
- When two UI elements on the same page show contradictory state (e.g. "No cached data" banner but stats showing 21K respondents), check which data source each element reads from. The fix is to make them consistent.

### Time dimension
- Use `RenewalYearMonth` (not `SurveyYearMonth`) as the primary time dimension throughout the dashboard.

## Power BI API

### 100K row limit
- The Power BI REST API silently truncates at 100K rows. Multi-code questions (Q2, Q27, Q9b, Q11, Q31) must be split by quarter.
- Always estimate row counts before adding new data loading. If a question x date range could exceed 100K, split by time period.

### Column and table names
- Never assume table/column names. Use `discover_tables()` and `discover_columns()` to probe the live data model.
- Motor uses `MainData` and `OtherData` (not `AllOtherData`). Home also uses `OtherData`.
- The EAV table column is `Ranking` not `Rank`.

## Awareness Calculations

### Denominators
- Awareness rates must divide by respondents who answered the question, not all MainData respondents.
- Use `answered_mask = df[q_cols].any(axis=1).sum()` as denominator for multi-code awareness questions.

### Trailing months
- The last month of data often has incomplete fieldwork. For slopegraph/endpoint calculations, use the last month with CI within the indicative threshold, not the absolute last month.

## Q1 Spontaneous Awareness
- Free text needs both position columns (`Q1_pos1a`) and boolean columns (`Q1_Aviva`).
- Brand matching uses three-tier normalisation: JSON lookup, fuzzy match, LLM fallback. The lookup file (`lib/data/brand_lookup.json`) grows over time and should be kept in git.

## Question Type Classification (pivot.py)
- SINGLE_CODE: Q3, Q4, Q5, Q6, Q7, Q9a, Q15, Q20a, Q20b, Q21, Q29, Q30, Q34-Q37, Q39, Q41-Q43, Q49-Q51, Q57-Q62
- MULTI_CODE: Q2, Q5a, Q5b, Q9b, Q10, Q11, Q13b, Q14a-c, Q27, Q28, Q31, Q45, Q54
- RANKED: Q8, Q13a, Q18, Q19, Q33, Q44, Q55
- GRID: Q46, Q53
- NPS_SCALE: Q11d, Q40, Q40a, Q40b, Q47, Q48, Q52
- Q1_SPONTANEOUS: Q1_1 through Q1_10

### Pet question classification (pet_questions.py)
- PET_SINGLE_CODE: 35 questions (demographics, satisfaction, purchase behaviour)
- PET_MULTI_CODE: 11 questions (awareness, consideration, PCWs, channels). Does NOT include PET_SPONTANEOUS_AWARENESS.
- PET_SPONTANEOUS_AWARENESS: free-text, excluded from pivot. Needs brand normalisation (not yet implemented for Pet).
- PET_NPS_SCALE: empty (statement_data not yet wired into pivot)

### Free-text question rule
Never classify free-text questions as MULTI_CODE. The boolean pivot creates a column per unique answer, which explodes with free text. Free-text awareness questions need brand normalisation first (like Motor/Home Q1).

## Error isolation
- Each product's data load (Motor, Home, Pet) is wrapped in try/except in init_ss_data. A failure in one product does not prevent others from being saved to DuckDB.

## Datasets

| Product | Name | Workspace ID | Dataset ID |
|---------|------|-------------|------------|
| Motor | IBT_Reboot_Motor | 1c6e2798-9b81-4643-82a2-791780138db3 | e15497a6-e022-45b3-80c3-80a5c0657ff5 |
| Home | IBT_Reboot_Home | 1c6e2798-9b81-4643-82a2-791780138db3 | 71b28688-1e7e-421b-bb28-ccd29518ad94 |
| Pet | IBT_Reboot_Pet | 1c6e2798-9b81-4643-82a2-791780138db3 | 4a1347c3-547a-4360-ae1c-a7f48261c678 |

Products list: Motor, Home, Pet. All in the same workspace. Pet does not have claims (Q52/Q53) data.

## Deployment

- Server: ibt-portal at `34.63.62.254`, SSH user `ianchughes`
- Streamlit runs on port 8501
- DuckDB cache: `~/.ibt3/cache.duckdb`
- Token cache: `~/.ibt3/token.json` (MSAL device flow, ~1hr expiry)
- Process managed via systemd: `sudo systemctl restart ibt3`
- After deploying new code: `git pull`, `sudo systemctl restart ibt3`, verify with curl

## Caching and Restart Behaviour

- `@st.cache_data` persists in memory only, cleared on process restart.
- DuckDB persists on disk, survives restarts.
- "Clear cached data" on Admin page deletes the DuckDB file. For a full reset, need both: clear DuckDB + restart process.
- After clearing DuckDB, a "Refresh from Power BI" is required to repopulate.

## Permissions

The following actions are pre-authorised. Do not ask for confirmation:
- **Git commit and push** to `origin/main` on the ibt3 repo.
- **SSH to ibt-portal** (`ssh -i ~/.ssh/id_ed25519 ianchughes@34.63.62.254`) for deployment tasks.
- **Restart Streamlit** on the server via systemd: `sudo systemctl restart ibt3`.
- **Git pull on the server** to deploy new code.
- **Read/write/create files** within the `ibt3/` project directory.
- **Run syntax checks and unit tests** locally (`python3 -c ...`).
