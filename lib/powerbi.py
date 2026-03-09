"""
Power BI data layer — MSAL authentication and DAX query execution.
Shared by all pages in the unified Streamlit dashboard.
"""

import json

import msal
import pandas as pd
import requests
import streamlit as st

from lib.config import (
    APP_VERSION, TENANT_ID, CLIENT_ID, WORKSPACE_ID, DATASET_ID, SCOPE,
    MAIN_TABLE, OTHER_TABLE,
)


# ---------------------------------------------------------------------------
# Authentication — MSAL device flow with silent refresh
# ---------------------------------------------------------------------------

@st.cache_resource(show_spinner=False)
def _get_msal_app():
    """Create and cache the MSAL app so the token cache persists for refresh."""
    return msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )


def get_token():
    """Authenticate via MSAL device flow, with silent refresh for expired tokens."""
    app = _get_msal_app()

    # Try silent renewal first (uses MSAL's in-memory token cache)
    accounts = app.get_accounts()
    if accounts:
        result = app.acquire_token_silent(SCOPE, account=accounts[0])
        if result and "access_token" in result:
            return result["access_token"]

    # Fall back to interactive device flow
    flow = app.initiate_device_flow(scopes=SCOPE)
    st.info(
        f"Sign in at **https://microsoft.com/devicelogin** "
        f"with code: **{flow['user_code']}**\n\n"
        f"App version: **{APP_VERSION}**"
    )
    token = app.acquire_token_by_device_flow(flow)
    if "access_token" not in token:
        st.error("Authentication failed.")
        st.stop()
    return token["access_token"]


# ---------------------------------------------------------------------------
# DAX query helper
# ---------------------------------------------------------------------------

# Known Analysis Services error codes → user-friendly messages
_KNOWN_AS_ERRORS = {
    "3239575574": (
        "Permission denied — your account needs **Build permission** on this "
        "dataset in Power BI. Ask your workspace admin to grant Build access."
    ),
    "3241803779": "Table not found in the semantic model.",
}


def _parse_dax_error(text: str) -> str:
    """Extract a user-friendly message from a Power BI error response."""
    try:
        body = json.loads(text)
        details = (
            body.get("error", {})
            .get("pbi.error", {})
            .get("details", [])
        )
        for d in details:
            code = d.get("detail", {}).get("value", "")
            if code in _KNOWN_AS_ERRORS:
                return _KNOWN_AS_ERRORS[code]
            # Surface the human-readable detail message
            if d.get("code") == "DetailsMessage":
                return d["detail"]["value"]
    except Exception:
        pass
    return text


def run_dax(token: str, dax: str, *, silent: bool = False) -> pd.DataFrame:
    """Execute a DAX query against the Power BI semantic model.

    When *silent* is True, non-200 responses are swallowed without showing
    an error in the UI (used for discovery/probe queries).
    """
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
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
            st.error(f"Query failed: {_parse_dax_error(r.text)}")
        return pd.DataFrame()
    rows = r.json()["results"][0]["tables"][0].get("rows", [])
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [c.split("[")[-1].replace("]", "") for c in df.columns]
    return df


# ---------------------------------------------------------------------------
# Table name discovery — auto-detect renamed tables in the semantic model
# ---------------------------------------------------------------------------

# Bump this to invalidate Streamlit's cached discovery results after code changes.
_DISCOVERY_VERSION = 3

# Known table name variants to probe when metadata queries fail.
_MAIN_TABLE_CANDIDATES = ["MainData_Motor", "MainData_Home", "MainData"]
_OTHER_TABLE_CANDIDATES = ["AllOtherData_Motor", "AllOtherData_Home", "AllOtherData"]


def _check_dataset_accessible(token: str) -> bool:
    """Verify the dataset exists and is accessible with the current token."""
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}"
    )
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    return r.status_code == 200


def _discover_tables_rest_api(token: str) -> list[str]:
    """Attempt table discovery via the Power BI REST API /tables endpoint.

    Works for push/streaming datasets. Returns 404 for imported/DirectQuery
    models — that is expected and handled silently.
    """
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/tables"
    )
    r = requests.get(url, headers={"Authorization": f"Bearer {token}"})
    if r.status_code != 200:
        return []
    try:
        return [t["name"] for t in r.json().get("value", [])]
    except (KeyError, TypeError):
        return []


def _probe_table_exists(token: str, table_name: str) -> bool:
    """Check if a table exists by running a zero-row DAX query against it.

    We cannot use run_dax() here because both a successful zero-row result and
    a DAX error return an empty DataFrame.  Instead we inspect the raw HTTP
    response: 200 with no top-level "error" key means the table exists.
    """
    dax = f"EVALUATE TOPN(0, '{table_name}')"
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
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


def discover_tables(token: str) -> list[str]:
    """Return table names from the Power BI semantic model.

    Three-tier strategy (each tier is silent on failure):
    1. REST API /tables endpoint — fast, no DAX needed.
    2. INFO.TABLES() DMV via DAX — requires admin/Build permissions.
    3. Probe known candidate table names with TOPN(0, ...) zero-row queries.
    """
    # Pre-check: is the dataset reachable at all?
    if not _check_dataset_accessible(token):
        st.error(
            f"Cannot access Power BI dataset.\n\n"
            f"**Workspace ID:** `{WORKSPACE_ID}`\n\n"
            f"**Dataset ID:** `{DATASET_ID}`\n\n"
            f"Verify these IDs are correct and that your account has "
            f"Dataset.Read.All permission."
        )
        return []

    # Tier 1: REST API /tables
    tables = _discover_tables_rest_api(token)
    if tables:
        return tables

    # Tier 2: INFO.TABLES() DMV (silent — suppresses permission errors)
    df = run_dax(token, "EVALUATE INFO.TABLES()", silent=True)
    if not df.empty:
        name_col = [c for c in df.columns if c.lower() == "name"]
        if not name_col:
            return df.iloc[:, 0].tolist()
        return df[name_col[0]].tolist()

    # Tier 3: Probe known candidate table names
    found: list[str] = []
    all_candidates = list(dict.fromkeys(
        _MAIN_TABLE_CANDIDATES + _OTHER_TABLE_CANDIDATES
    ))
    for name in all_candidates:
        if _probe_table_exists(token, name):
            found.append(name)
    if found:
        return found

    return []


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_main_table(_token: str, _version: int = _DISCOVERY_VERSION) -> str:
    """Find the MainData table name (may be MainData, MainData_Motor, etc.)."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("MainData"):
            return t
    # Last resort: probe candidates directly (tables list may be partial)
    for name in _MAIN_TABLE_CANDIDATES:
        if _probe_table_exists(_token, name):
            return name
    st.warning(
        f"Could not auto-discover table names (REST API, INFO.TABLES(), and "
        f"probe queries all failed). Using fallback name '{MAIN_TABLE}'.\n\n"
        f"If queries fail, verify the actual table name in Power BI Desktop "
        f"and update MAIN_TABLE in lib/config.py."
    )
    return MAIN_TABLE


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_other_table(_token: str, _version: int = _DISCOVERY_VERSION) -> str:
    """Find the AllOtherData table name."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("AllOtherData"):
            return t
    for name in _OTHER_TABLE_CANDIDATES:
        if _probe_table_exists(_token, name):
            return name
    st.warning(
        f"Could not auto-discover table names (REST API, INFO.TABLES(), and "
        f"probe queries all failed). Using fallback name '{OTHER_TABLE}'.\n\n"
        f"If queries fail, verify the actual table name in Power BI Desktop "
        f"and update OTHER_TABLE in lib/config.py."
    )
    return OTHER_TABLE


# ---------------------------------------------------------------------------
# Claims DAX queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading months...")
def load_months(_token, main_table: str = MAIN_TABLE):
    dax = f"""
        EVALUATE
        SUMMARIZE(
            '{main_table}',
            '{main_table}'[RenewalYearMonth]
        )
        ORDER BY '{main_table}'[RenewalYearMonth] ASC
    """
    df = run_dax(_token, dax)
    if df.empty:
        return []
    return sorted(df["RenewalYearMonth"].dropna().unique().astype(int).tolist())


@st.cache_data(ttl=3600, show_spinner="Loading Q52 data...")
def load_q52(_token, start_month: int, end_month: int,
             main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE):
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
    return run_dax(_token, dax)


@st.cache_data(ttl=3600, show_spinner="Loading Q53 data...")
def load_q53(_token, start_month: int, end_month: int,
             main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE):
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
    return run_dax(_token, dax)


# ---------------------------------------------------------------------------
# Shopping & Switching DAX queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading S&S main data...")
def load_ss_maindata(_token, start_month: int, end_month: int,
                     main_table: str = MAIN_TABLE):
    """Fetch MainData profile columns for Shopping & Switching analysis."""
    mt = main_table
    dax = f"""
        EVALUATE
        FILTER(
            SELECTCOLUMNS(
                '{mt}',
                "UniqueID", '{mt}'[UniqueID],
                "RenewalYearMonth", '{mt}'[RenewalYearMonth],
                "SurveyYearMonth", '{mt}'[SurveyYearMonth],
                "CurrentCompany", '{mt}'[CurrentCompany],
                "PreRenewalCompany", '{mt}'[PreRenewalCompany],
                "Region", '{mt}'[Region],
                "Age Group", '{mt}'[Age Group],
                "Gender", '{mt}'[Gender],
                "Shoppers", '{mt}'[Shoppers],
                "Switchers", '{mt}'[Switchers],
                "Retained", '{mt}'[Retained],
                "Renewal premium change", '{mt}'[Renewal premium change],
                "How much higher", '{mt}'[How much higher],
                "How much lower", '{mt}'[How much lower],
                "Did you use a PCW for shopping", '{mt}'[Did you use a PCW for shopping],
                "Claimants", '{mt}'[Claimants],
                "Employment status", '{mt}'[Employment status]
            ),
            [RenewalYearMonth] >= {start_month} && [RenewalYearMonth] <= {end_month}
        )
    """
    return run_dax(_token, dax)


@st.cache_data(ttl=3600, show_spinner="Loading S&S question data...")
def load_ss_questions(_token, start_month: int, end_month: int,
                      main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE):
    """Fetch AllOtherData EAV table for Shopping & Switching analysis."""
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
    return run_dax(_token, dax)
