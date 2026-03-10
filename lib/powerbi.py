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
    MAIN_TABLE, OTHER_TABLE,
)


# ---------------------------------------------------------------------------
# Authentication — MSAL device flow
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def get_token():
    """Authenticate via MSAL device flow. Cached for session lifetime."""
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
    rows = body["results"][0]["tables"][0].get("rows", [])
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
_OTHER_TABLE_CANDIDATES = ["AllOtherData_Motor", "AllOtherData_Home", "AllOtherData"]


def _probe_table_exists(token: str, table_name: str, *,
                        workspace_id: str = WORKSPACE_ID,
                        dataset_id: str = DATASET_ID) -> bool:
    """Check if a table exists — returns True if the query succeeds."""
    dax = f"EVALUATE ROW(\"x\", COUNTROWS('{table_name}'))"
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
    return "error" not in r.json()


def discover_tables(token: str, *,
                    workspace_id: str = WORKSPACE_ID,
                    dataset_id: str = DATASET_ID) -> list[str]:
    """Return all table names in the Power BI semantic model."""
    found: set[str] = set()

    # Attempt 1: INFO.TABLES() DMV
    dax = "EVALUATE INFO.TABLES()"
    df = run_dax(token, dax, silent=True,
                 workspace_id=workspace_id, dataset_id=dataset_id)
    if not df.empty:
        name_col = [c for c in df.columns if c.lower() == "name"]
        if name_col:
            found.update(df[name_col[0]].tolist())
        else:
            found.update(df.iloc[:, 0].tolist())

    # Attempt 2: Probe known candidates
    for name in dict.fromkeys(_MAIN_TABLE_CANDIDATES + _OTHER_TABLE_CANDIDATES):
        if name not in found and _probe_table_exists(
            token, name,
            workspace_id=workspace_id, dataset_id=dataset_id,
        ):
            found.add(name)

    return list(found)


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_main_table(_token: str, *,
                   workspace_id: str = WORKSPACE_ID,
                   dataset_id: str = DATASET_ID) -> str:
    """Find the MainData table name (may be MainData, MainData_Motor, etc.)."""
    tables = discover_tables(_token, workspace_id=workspace_id, dataset_id=dataset_id)
    for t in tables:
        if t.startswith("MainData"):
            return t
    for name in _MAIN_TABLE_CANDIDATES:
        if _probe_table_exists(_token, name,
                               workspace_id=workspace_id, dataset_id=dataset_id):
            return name
    st.warning(f"Could not find MainData* table. Found: {tables}. Using fallback '{MAIN_TABLE}'.")
    return MAIN_TABLE


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_other_table(_token: str, *,
                    workspace_id: str = WORKSPACE_ID,
                    dataset_id: str = DATASET_ID) -> str | None:
    """Find the AllOtherData table name, or None if it doesn't exist."""
    tables = discover_tables(_token, workspace_id=workspace_id, dataset_id=dataset_id)
    for t in tables:
        if t.startswith("AllOtherData"):
            return t
    for name in _OTHER_TABLE_CANDIDATES:
        if _probe_table_exists(_token, name,
                               workspace_id=workspace_id, dataset_id=dataset_id):
            return name
    st.info(f"No AllOtherData table in workspace {workspace_id[:8]}… — question data unavailable.")
    return None


# ---------------------------------------------------------------------------
# Column discovery — auto-detect available columns in a table
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner=False)
def discover_columns(_token: str, table_name: str, *,
                     workspace_id: str = WORKSPACE_ID,
                     dataset_id: str = DATASET_ID) -> set[str]:
    """Return the set of column names for a table in the semantic model."""
    # Attempt 1: TOPN(1, ...)
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

    # Attempt 2: INFO.COLUMNS() DMV
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
        return required
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
    """Fetch AllOtherData EAV table for Shopping & Switching analysis."""
    if _check_required_columns(
        _token, other_table, {"UniqueID", "QuestionNumber", "Answer"}, "S&S questions",
        workspace_id=workspace_id, dataset_id=dataset_id,
    ) is None:
        return pd.DataFrame()
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                '{other_table}'[UniqueID],
                '{other_table}'[QuestionNumber],
                '{other_table}'[Answer]
            ),
            '{main_table}'[RenewalYearMonth] >= {start_month},
            '{main_table}'[RenewalYearMonth] <= {end_month}
        )
    """
    return run_dax(_token, dax, workspace_id=workspace_id, dataset_id=dataset_id)
