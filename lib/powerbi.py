"""
Power BI data layer — MSAL authentication and DAX query execution.
Shared by all pages in the unified Streamlit dashboard.
"""

import msal
import pandas as pd
import requests
import streamlit as st

from lib.config import (
    TENANT_ID, CLIENT_ID, WORKSPACE_ID, DATASET_ID, SCOPE,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
    PET_WORKSPACE_ID, PET_DATASET_ID,
    MAIN_TABLE, OTHER_TABLE,
)


# ---------------------------------------------------------------------------
# Authentication — MSAL device flow
# ---------------------------------------------------------------------------

import json
import os
import time
from pathlib import Path

_TOKEN_FILE = Path.home() / ".ehubot" / "token.json"


def _save_token(access_token: str, expires_at: float):
    """Persist token + expiry to local file with restrictive permissions."""
    try:
        _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
        _TOKEN_FILE.write_text(json.dumps({
            "access_token": access_token,
            "expires_at": expires_at,
        }))
        try:
            os.chmod(_TOKEN_FILE, 0o600)
        except OSError:
            pass  # Windows or other platforms may not support chmod
    except OSError:
        pass  # Non-critical — token still works for this session


def _load_saved_token() -> str | None:
    """Load token from local file if it exists and hasn't expired."""
    if not _TOKEN_FILE.exists():
        return None
    try:
        data = json.loads(_TOKEN_FILE.read_text())
        if data.get("expires_at", 0) > time.time() + 300:  # 5 min buffer
            return data["access_token"]
    except (json.JSONDecodeError, KeyError, OSError):
        pass
    return None


@st.cache_resource(show_spinner=False)
def get_token():
    """Authenticate via MSAL device flow. Checks local token cache first."""
    # Check for saved token
    saved = _load_saved_token()
    if saved:
        return saved

    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    flow = app.initiate_device_flow(scopes=SCOPE)
    st.info(
        f"Sign in at **https://microsoft.com/devicelogin** "
        f"with code: **{flow['user_code']}**"
    )
    token = app.acquire_token_by_device_flow(flow)
    if "access_token" not in token:
        st.error("Authentication failed.")
        st.stop()

    # Persist token for refresh survival
    expires_in = token.get("expires_in", 3600)
    _save_token(token["access_token"], time.time() + expires_in)

    return token["access_token"]


# ---------------------------------------------------------------------------
# DAX query helper
# ---------------------------------------------------------------------------

def run_dax(token: str, dax: str, *, silent: bool = False,
            workspace_id: str = WORKSPACE_ID,
            dataset_id: str = DATASET_ID) -> pd.DataFrame:
    """Execute a DAX query against the Power BI semantic model.

    Parameters
    ----------
    silent : bool
        If True, suppress error messages (useful for discovery queries that
        have fallback logic).
    workspace_id : str
        Power BI workspace (group) ID.
    dataset_id : str
        Power BI dataset (semantic model) ID.
    """
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
        f"/datasets/{dataset_id}/executeQueries"
    )
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    if r.status_code != 200:
        if not silent:
            st.error(f"Query failed: {r.text}")
        return pd.DataFrame()
    body = r.json()
    # Power BI may return HTTP 200 with an error payload (e.g. missing columns)
    if "error" in body:
        if not silent:
            st.error(f"Query failed: {body['error']}")
        return pd.DataFrame()
    try:
        rows = body["results"][0]["tables"][0].get("rows", [])
    except (KeyError, IndexError):
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [c.split("[")[-1].replace("]", "") for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Table name discovery — auto-detect renamed tables in the semantic model
# ---------------------------------------------------------------------------

# Known table name variants to probe when metadata queries fail.
_MAIN_TABLE_CANDIDATES = ["MainData_Motor", "MainData_Home", "MainData"]
_OTHER_TABLE_CANDIDATES = ["AllOtherData_Motor", "AllOtherData_Home", "AllOtherData", "OtherData"]


def _probe_table_exists_simple(token: str, table_name: str, *,
                               workspace_id: str = WORKSPACE_ID,
                               dataset_id: str = DATASET_ID) -> bool:
    """Check if a table exists — returns True if the query succeeds (HTTP 200, no error body)."""
    dax = f"EVALUATE TOPN(0, '{table_name}')"
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
        f"/datasets/{dataset_id}/executeQueries"
    )
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json={
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    if r.status_code != 200:
        return False
    body = r.json()
    # A successful query has no "error" key at the top level
    return "error" not in body


def discover_tables(token: str, *,
                    workspace_id: str = WORKSPACE_ID,
                    dataset_id: str = DATASET_ID) -> list[str]:
    """Return all table names in the Power BI semantic model.

    Strategy:
    1. Try INFO.TABLES() DMV (requires admin/build permissions).
    2. If that fails, probe known table name variants with zero-row queries.
    """
    # --- Attempt 1: INFO.TABLES() (needs admin perms; may fail silently) ---
    dax = "EVALUATE INFO.TABLES()"
    df = run_dax(token, dax, silent=True,
                 workspace_id=workspace_id, dataset_id=dataset_id)
    if not df.empty:
        name_col = [c for c in df.columns if c.lower() == "name"]
        if not name_col:
            return df.iloc[:, 0].tolist()
        return df[name_col[0]].tolist()

    # --- Attempt 2: Probe known table name candidates ---
    found: list[str] = []
    all_candidates = list(dict.fromkeys(
        _MAIN_TABLE_CANDIDATES + _OTHER_TABLE_CANDIDATES
    ))
    for name in all_candidates:
        if _probe_table_exists_simple(token, name,
                                      workspace_id=workspace_id,
                                      dataset_id=dataset_id):
            found.append(name)
    if found:
        return found

    return []


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_main_table(_token: str, *,
                   workspace_id: str = WORKSPACE_ID,
                   dataset_id: str = DATASET_ID) -> str:
    """Find the MainData table name (may be MainData, MainData_Motor, etc.)."""
    tables = discover_tables(_token, workspace_id=workspace_id, dataset_id=dataset_id)
    for t in tables:
        if t.startswith("MainData"):
            return t
    # Last resort: probe candidates directly (tables list may be partial)
    for name in _MAIN_TABLE_CANDIDATES:
        if _probe_table_exists_simple(_token, name,
                                      workspace_id=workspace_id,
                                      dataset_id=dataset_id):
            return name
    st.warning(f"Could not find MainData* table. Found: {tables}. Using fallback '{MAIN_TABLE}'.")
    return MAIN_TABLE


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_other_table(_token: str, *,
                    workspace_id: str = WORKSPACE_ID,
                    dataset_id: str = DATASET_ID) -> str:
    """Find the AllOtherData table name."""
    tables = discover_tables(_token, workspace_id=workspace_id, dataset_id=dataset_id)
    for t in tables:
        if t.startswith("AllOtherData"):
            return t
    # Last resort: probe candidates directly
    for name in _OTHER_TABLE_CANDIDATES:
        if _probe_table_exists_simple(_token, name,
                                      workspace_id=workspace_id,
                                      dataset_id=dataset_id):
            return name
    st.warning(f"Could not find AllOtherData* table. Found: {tables}. Using fallback '{OTHER_TABLE}'.")
    return OTHER_TABLE


# ---------------------------------------------------------------------------
# Column discovery — auto-detect available columns in a table
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def discover_columns(_token: str, table_name: str, *,
                     workspace_id: str = WORKSPACE_ID,
                     dataset_id: str = DATASET_ID) -> set[str]:
    """Return the set of column names for a table in the semantic model.

    Strategy:
    1. TOPN(1, ...) — parse column names from result row keys.
    2. INFO.COLUMNS() DMV — filter client-side by table name.
    """
    # --- Attempt 1: TOPN(1, ...) ---
    dax = f"EVALUATE TOPN(1, '{table_name}')"
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
        f"/datasets/{dataset_id}/executeQueries"
    )
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {_token}",
            "Content-Type": "application/json",
        },
        json={
            "queries": [{"query": dax}],
            "serializerSettings": {"includeNulls": True},
        },
    )
    if r.status_code == 200:
        body = r.json()
        if "error" not in body:
            rows = body["results"][0]["tables"][0].get("rows", [])
            if rows:
                return {k.split("[")[-1].rstrip("]") for k in rows[0].keys()}

    # --- Attempt 2: INFO.COLUMNS() DMV (needs admin perms; may fail silently) ---
    dax_info = "EVALUATE INFO.COLUMNS()"
    df = run_dax(_token, dax_info, silent=True,
                 workspace_id=workspace_id, dataset_id=dataset_id)
    if not df.empty:
        name_col = [c for c in df.columns if c.lower() == "explicitname"]
        table_col = [c for c in df.columns if c.lower() == "tablename"]
        if name_col and table_col:
            mask = df[table_col[0]].astype(str) == table_name
            return set(df.loc[mask, name_col[0]].tolist())

    return set()


def _check_required_columns(
    token: str, table_name: str, required: set[str], context: str, *,
    workspace_id: str = WORKSPACE_ID, dataset_id: str = DATASET_ID,
) -> set[str] | None:
    """Return available columns if all *required* are present, else warn and return None."""
    available = discover_columns(token, table_name,
                                 workspace_id=workspace_id, dataset_id=dataset_id)
    if not available:
        st.warning(f"{context}: could not discover columns for '{table_name}'.")
        return None
    missing = required - available
    if missing:
        st.warning(f"{context}: missing columns in '{table_name}': {missing}")
        return None
    return available


def _build_select_columns(table: str, columns: list[str], available: set[str]) -> str:
    """Build SELECTCOLUMNS pairs, skipping columns not in *available*."""
    parts = []
    for col in columns:
        if col in available:
            parts.append(f'"{col}", \'{table}\'[{col}]')
    return ",\n                ".join(parts)


# ---------------------------------------------------------------------------
# Claims DAX queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading months...")
def load_months(_token, main_table: str = MAIN_TABLE, *,
                workspace_id: str = WORKSPACE_ID, dataset_id: str = DATASET_ID):
    if _check_required_columns(
        _token, main_table, {"RenewalYearMonth"}, "Month discovery",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return []
    dax = f"""
        EVALUATE
        SUMMARIZE(
            '{main_table}',
            '{main_table}'[RenewalYearMonth]
        )
        ORDER BY '{main_table}'[RenewalYearMonth] ASC
    """
    df = run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)
    if df.empty:
        return []
    return sorted(df["RenewalYearMonth"].dropna().unique().astype(int).tolist())


@st.cache_data(ttl=3600, show_spinner="Loading Q52 data...")
def load_q52(_token, start_month: int, end_month: int,
             main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE, *,
             workspace_id: str = WORKSPACE_ID, dataset_id: str = DATASET_ID):
    if _check_required_columns(
        _token, other_table, {"QuestionNumber", "Scale"}, "Q52 analysis",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return pd.DataFrame()
    if _check_required_columns(
        _token, main_table, {"CurrentCompany", "Claimants", "RenewalYearMonth"}, "Q52 analysis",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return pd.DataFrame()
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                '{main_table}'[CurrentCompany],
                "Q52_n", CALCULATE(
                    COUNTROWS('{other_table}'),
                    '{other_table}'[QuestionNumber] = "Q52"
                ),
                "Q52_mean", CALCULATE(
                    AVERAGEX('{other_table}', VALUE('{other_table}'[Scale])),
                    '{other_table}'[QuestionNumber] = "Q52"
                ),
                "Q52_std", CALCULATE(
                    STDEVX.P('{other_table}', VALUE('{other_table}'[Scale])),
                    '{other_table}'[QuestionNumber] = "Q52"
                )
            ),
            '{main_table}'[Claimants] = "Claimant",
            '{main_table}'[RenewalYearMonth] >= {start_month},
            '{main_table}'[RenewalYearMonth] <= {end_month}
        )
        ORDER BY [Q52_n] DESC
    """
    return run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)


@st.cache_data(ttl=3600, show_spinner="Loading Q53 data...")
def load_q53(_token, start_month: int, end_month: int,
             main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE, *,
             workspace_id: str = WORKSPACE_ID, dataset_id: str = DATASET_ID):
    if _check_required_columns(
        _token, other_table, {"QuestionNumber", "Subject", "Ranking", "Scale"}, "Q53 analysis",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return pd.DataFrame()
    if _check_required_columns(
        _token, main_table, {"CurrentCompany", "Claimants", "RenewalYearMonth"}, "Q53 analysis",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return pd.DataFrame()
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                '{main_table}'[CurrentCompany],
                '{other_table}'[Subject],
                '{other_table}'[Ranking],
                "Q53_n", COUNTROWS('{other_table}'),
                "Q53_mean", AVERAGEX('{other_table}', VALUE('{other_table}'[Scale])),
                "Q53_std", STDEVX.P('{other_table}', VALUE('{other_table}'[Scale]))
            ),
            '{other_table}'[QuestionNumber] = "Q53",
            '{main_table}'[Claimants] = "Claimant",
            '{main_table}'[RenewalYearMonth] >= {start_month},
            '{main_table}'[RenewalYearMonth] <= {end_month}
        )
        ORDER BY '{main_table}'[CurrentCompany] ASC, '{other_table}'[Ranking] ASC
    """
    return run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)


# ---------------------------------------------------------------------------
# Shopping & Switching DAX queries
# ---------------------------------------------------------------------------

_SS_REQUIRED_COLUMNS = {"UniqueID", "RenewalYearMonth"}
_SS_DESIRED_COLUMNS = [
    "UniqueID", "RenewalYearMonth", "SurveyYearMonth",
    "CurrentCompany", "PreRenewalCompany",
    "Region", "Age Group", "Gender",
    "Shoppers", "Switchers", "Retained",
    "Renewal premium change", "How much higher", "How much lower",
    "Did you use a PCW for shopping", "Claimants", "Employment status",
]


@st.cache_data(ttl=3600, show_spinner="Loading S&S main data...")
def load_ss_maindata(_token, start_month: int, end_month: int,
                     main_table: str = MAIN_TABLE, *,
                     workspace_id: str = WORKSPACE_ID,
                     dataset_id: str = DATASET_ID):
    """Fetch MainData profile columns for Shopping & Switching analysis."""
    available = discover_columns(_token, main_table,
                                 workspace_id=workspace_id, dataset_id=dataset_id)
    if available:
        missing_req = _SS_REQUIRED_COLUMNS - available
        if missing_req:
            st.warning(f"S&S data unavailable — missing required columns in "
                       f"'{main_table}': {missing_req}")
            return pd.DataFrame()
        select_expr = _build_select_columns(main_table, _SS_DESIRED_COLUMNS, available)
    else:
        # Column discovery failed — fall back to full hardcoded list
        select_expr = _build_select_columns(
            main_table, _SS_DESIRED_COLUMNS, set(_SS_DESIRED_COLUMNS))

    mt = main_table
    dax = f"""
        EVALUATE
        FILTER(
            SELECTCOLUMNS(
                '{mt}',
                {select_expr}
            ),
            [RenewalYearMonth] >= {start_month} && [RenewalYearMonth] <= {end_month}
        )
    """
    return run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)


@st.cache_data(ttl=3600, show_spinner="Loading S&S question data...")
def load_ss_questions(_token, start_month: int, end_month: int,
                      main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE, *,
                      workspace_id: str = WORKSPACE_ID,
                      dataset_id: str = DATASET_ID):
    """Fetch AllOtherData EAV table for Shopping & Switching analysis.

    Fetches all columns needed by pivot.py: UniqueID, QuestionNumber, Answer,
    plus Ranking (for ranked Qs), Scale (for NPS/grid), and Subject (for grid).

    The Power BI REST API caps results at 100K rows per query, so we batch
    questions into groups to avoid truncation.
    """
    available = discover_columns(
        _token, other_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    if not available:
        st.warning(f"S&S questions: could not discover columns for '{other_table}'.")
        return pd.DataFrame()
    required = {"UniqueID", "QuestionNumber", "Answer"}
    missing = required - available
    if missing:
        st.warning(f"S&S questions: missing columns in '{other_table}': {missing}")
        return pd.DataFrame()

    # Build column list: always fetch core columns, add optional ones if present
    core = ["UniqueID", "QuestionNumber", "Answer"]
    optional = ["Ranking", "Scale", "Subject"]
    cols = core + [c for c in optional if c in available]
    select_expr = ", ".join(f"'{other_table}'[{c}]" for c in cols)

    # The Power BI REST API caps results at 100K rows per query.
    # Large multi-code questions (Q2, Q27) can have 500K+ rows across
    # the full date range, so we query per-question AND per-quarter
    # to stay safely under the limit.
    from lib.analytics.pivot import ALL_KNOWN, MULTI_CODE
    question_list = sorted(ALL_KNOWN)

    # Build quarterly date ranges
    all_months = list(range(start_month, end_month + 1))
    # Filter to valid YYYYMM values
    all_months = [m for m in all_months if 1 <= m % 100 <= 12]
    # Chunk into quarters (3 months each)
    quarter_size = 3
    quarters = []
    for i in range(0, len(all_months), quarter_size):
        chunk = all_months[i:i + quarter_size]
        if chunk:
            quarters.append((chunk[0], chunk[-1]))
    if not quarters:
        quarters = [(start_month, end_month)]

    frames = []
    for q in question_list:
        # Large multi-code questions need per-quarter splitting
        if q in MULTI_CODE:
            for q_start, q_end in quarters:
                dax = f"""
                    EVALUATE
                    CALCULATETABLE(
                        SELECTCOLUMNS(
                            '{other_table}',
                            {select_expr}
                        ),
                        '{other_table}'[QuestionNumber] = "{q}",
                        '{main_table}'[RenewalYearMonth] >= {q_start},
                        '{main_table}'[RenewalYearMonth] <= {q_end}
                    )
                """
                df_q = run_dax(
                    _token, dax, silent=True,
                    workspace_id=workspace_id, dataset_id=dataset_id,
                )
                if not df_q.empty:
                    frames.append(df_q)
        else:
            # Single-code, ranked, NPS, grid — fit in one query
            dax = f"""
                EVALUATE
                CALCULATETABLE(
                    SELECTCOLUMNS(
                        '{other_table}',
                        {select_expr}
                    ),
                    '{other_table}'[QuestionNumber] = "{q}",
                    '{main_table}'[RenewalYearMonth] >= {start_month},
                    '{main_table}'[RenewalYearMonth] <= {end_month}
                )
            """
            df_q = run_dax(
                _token, dax, silent=True,
                workspace_id=workspace_id, dataset_id=dataset_id,
            )
            if not df_q.empty:
                frames.append(df_q)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


# ---------------------------------------------------------------------------
# Pet insurance loaders
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading Pet quarters...")
def load_pet_quarters(_token, *,
                      workspace_id: str = PET_WORKSPACE_ID,
                      dataset_id: str = PET_DATASET_ID) -> list[str]:
    """Discover available Survey Quarter values in Pet main_data."""
    dax = """
        EVALUATE
        DISTINCT(SELECTCOLUMNS('main_data', "q", 'main_data'[Survey Quarter]))
        ORDER BY [q] ASC
    """
    df = run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)
    if df.empty:
        return []
    return sorted(df["q"].dropna().unique().tolist())


@st.cache_data(ttl=3600, show_spinner="Loading Pet main data...")
def load_pet_maindata(_token, quarters: list[str], *,
                      workspace_id: str = PET_WORKSPACE_ID,
                      dataset_id: str = PET_DATASET_ID) -> pd.DataFrame:
    """Fetch Pet main_data for specified quarters.

    Pet main_data has ~60 wide columns already. We SELECT all columns
    filtered by Survey Quarter using an IN-list.
    """
    if not quarters:
        return pd.DataFrame()

    # Build IN-list filter: {"2024 Q4", "2024 Q3", ...}
    in_values = ", ".join(f'"{q}"' for q in quarters)

    # Pet main_data may exceed 100K rows across all quarters.
    # Batch per quarter to stay under the API limit.
    frames = []
    for q in quarters:
        dax = f"""
            EVALUATE
            FILTER(
                'main_data',
                'main_data'[Survey Quarter] = "{q}"
            )
        """
        df_q = run_dax(_token, dax, silent=True,
                       workspace_id=workspace_id, dataset_id=dataset_id)
        if not df_q.empty:
            frames.append(df_q)

    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


@st.cache_data(ttl=3600, show_spinner="Loading Pet question data...")
def load_pet_questions(_token, quarters: list[str], *,
                       workspace_id: str = PET_WORKSPACE_ID,
                       dataset_id: str = PET_DATASET_ID) -> pd.DataFrame:
    """Load all 4 Pet EAV tables and normalise to standard format.

    Returns DataFrame with columns: UniqueID, QuestionNumber, Answer,
    plus optional Ranking and AnswerCode.
    """
    from lib.pet_questions import PET_QUESTION_ALIASES

    if not quarters:
        return pd.DataFrame()

    # The 4 EAV tables and their column mappings
    eav_tables = [
        {
            "table": "pet_data_new",
            "id_col": "ResultSkey",
            "question_col": "question",
            "answer_col": "answer",
            "extra_cols": [],
        },
        {
            "table": "provider_data",
            "id_col": "ResultSkey",
            "question_col": "question",
            "answer_col": "answer",
            "extra_cols": ["answer_number"],
        },
        {
            "table": "remaining_data",
            "id_col": "ResultSkey",
            "question_col": "question",
            "answer_col": "answer",
            "extra_cols": [],
        },
        {
            "table": "statement_data",
            "id_col": "ResultSkey",
            "question_col": "statement",
            "answer_col": "AnswerText",
            "extra_cols": ["AnswerCode"],
        },
    ]

    all_frames = []

    for spec in eav_tables:
        table = spec["table"]
        id_col = spec["id_col"]
        q_col = spec["question_col"]
        a_col = spec["answer_col"]
        extras = spec["extra_cols"]

        # Build select columns
        select_parts = [
            f'"{id_col}", \'{table}\'[{id_col}]',
            f'"{q_col}", \'{table}\'[{q_col}]',
            f'"{a_col}", \'{table}\'[{a_col}]',
        ]
        for ec in extras:
            select_parts.append(f'"{ec}", \'{table}\'[{ec}]')
        select_expr = ", ".join(select_parts)

        # Batch by quarter to respect 100K row limit
        for q in quarters:
            # Filter via main_data relationship or direct quarter column
            # Pet EAV tables are related to main_data via ResultSkey,
            # and main_data has Survey Quarter. Use CALCULATETABLE.
            dax = f"""
                EVALUATE
                CALCULATETABLE(
                    SELECTCOLUMNS(
                        '{table}',
                        {select_expr}
                    ),
                    'main_data'[Survey Quarter] = "{q}"
                )
            """
            df_batch = run_dax(_token, dax, silent=True,
                               workspace_id=workspace_id,
                               dataset_id=dataset_id)
            if not df_batch.empty:
                # Normalise column names
                rename_map = {
                    id_col: "UniqueID",
                    q_col: "QuestionRaw",
                    a_col: "Answer",
                }
                if "answer_number" in df_batch.columns:
                    rename_map["answer_number"] = "Ranking"
                if "AnswerCode" in df_batch.columns:
                    rename_map["AnswerCode"] = "Scale"
                df_batch = df_batch.rename(columns=rename_map)

                # Map full-text question names to short aliases
                df_batch["QuestionNumber"] = df_batch["QuestionRaw"].map(
                    PET_QUESTION_ALIASES
                ).fillna(df_batch["QuestionRaw"])

                df_batch["UniqueID"] = df_batch["UniqueID"].astype(str)
                all_frames.append(df_batch)

    if not all_frames:
        return pd.DataFrame()
    return pd.concat(all_frames, ignore_index=True)
