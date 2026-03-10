"""
Power BI data layer — MSAL authentication and DAX query execution.
Shared by all pages in the unified Streamlit dashboard.
"""

import logging
import time

import msal
import pandas as pd
import requests
import streamlit as st

from lib.config import (
    TENANT_ID, CLIENT_ID, WORKSPACE_ID, DATASET_ID, SCOPE,
    MAIN_TABLE, OTHER_TABLE,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error classification
# ---------------------------------------------------------------------------

class _DAXError(Exception):
    pass

class _AuthError(_DAXError):
    pass

class _TransientError(_DAXError):
    def __init__(self, message, retry_after=None):
        super().__init__(message)
        self.retry_after = retry_after

class _PermanentError(_DAXError):
    pass

_TRANSIENT_AS_ERROR_CODES = {"3239575574"}

_MAX_RETRIES = 3
_BASE_DELAY = 2  # seconds


def _classify_response(r: requests.Response) -> None:
    """Raise typed exception for non-success responses."""
    if r.status_code == 200:
        return
    if r.status_code in (401, 403):
        raise _AuthError(f"Auth error {r.status_code}: {r.text[:200]}")
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", 30))
        raise _TransientError("Rate limited", retry_after=retry_after)
    if r.status_code == 400:
        body = r.text
        for code in _TRANSIENT_AS_ERROR_CODES:
            if code in body:
                raise _TransientError(
                    f"Analysis Services transient error ({code}): {body[:200]}"
                )
        raise _PermanentError(f"Bad request: {body[:300]}")
    if 500 <= r.status_code < 600:
        raise _TransientError(f"Server error {r.status_code}: {r.text[:200]}")
    raise _PermanentError(f"Unexpected error {r.status_code}: {r.text[:200]}")


# ---------------------------------------------------------------------------
# Authentication — MSAL device flow with silent token refresh
# ---------------------------------------------------------------------------

class _TokenManager:
    """Holds the MSAL app and token state so tokens can be silently refreshed."""

    def __init__(self):
        self.app = msal.PublicClientApplication(
            CLIENT_ID,
            authority=f"https://login.microsoftonline.com/{TENANT_ID}",
        )
        self._account = None

    def authenticate(self):
        """Run the interactive device-flow login."""
        flow = self.app.initiate_device_flow(scopes=SCOPE)
        st.info(
            f"Sign in at **https://microsoft.com/devicelogin** "
            f"with code: **{flow['user_code']}**"
        )
        result = self.app.acquire_token_by_device_flow(flow)
        if "access_token" not in result:
            st.error("Authentication failed.")
            st.stop()
        accounts = self.app.get_accounts()
        self._account = accounts[0] if accounts else None
        return result["access_token"]

    def get_access_token(self) -> str:
        """Return a valid access token, refreshing silently if possible."""
        if self._account:
            result = self.app.acquire_token_silent(SCOPE, account=self._account)
            if result and "access_token" in result:
                return result["access_token"]
            logger.info("Silent token refresh failed, re-authenticating...")
        return self.authenticate()


@st.cache_resource(show_spinner=False)
def _get_token_manager() -> _TokenManager:
    mgr = _TokenManager()
    mgr.authenticate()
    return mgr


def get_token() -> str:
    """Return a valid access token (refreshes silently when expired)."""
    mgr = _get_token_manager()
    return mgr.get_access_token()


# ---------------------------------------------------------------------------
# DAX query helper — with retry and error classification
# ---------------------------------------------------------------------------

def run_dax(token: str, dax: str, *, _silent: bool = False) -> pd.DataFrame:
    """Execute a DAX query against the Power BI semantic model.

    Retries transient errors with exponential backoff. On auth errors,
    refreshes the token and retries once.
    """
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    payload = {
        "queries": [{"query": dax}],
        "serializerSettings": {"includeNulls": True},
    }

    current_token = token
    auth_retried = False

    for attempt in range(_MAX_RETRIES + 1):
        r = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {current_token}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            _classify_response(r)
        except _AuthError:
            if auth_retried:
                if not _silent:
                    st.error("Authentication failed after token refresh.")
                return pd.DataFrame()
            auth_retried = True
            logger.info("Token expired, refreshing...")
            current_token = get_token()
            if "token" in st.session_state:
                st.session_state["token"] = current_token
            continue
        except _TransientError as e:
            if attempt == _MAX_RETRIES:
                if not _silent:
                    st.error(f"Query failed after {_MAX_RETRIES + 1} attempts: {e}")
                logger.warning("Query failed after retries: %s", e)
                return pd.DataFrame()
            delay = e.retry_after or (_BASE_DELAY * (2 ** attempt))
            logger.warning(
                "Transient error (attempt %d/%d), retrying in %ds: %s",
                attempt + 1, _MAX_RETRIES + 1, delay, e,
            )
            time.sleep(delay)
            continue
        except _PermanentError as e:
            if not _silent:
                st.error(f"Query failed: {e}")
            logger.error("Permanent query error: %s", e)
            return pd.DataFrame()

        # Success
        rows = r.json()["results"][0]["tables"][0].get("rows", [])
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        df.columns = [c.split("[")[-1].replace("]", "") for c in df.columns]
        return df

    return pd.DataFrame()


# ---------------------------------------------------------------------------
# Table name discovery — auto-detect renamed tables in the semantic model
# ---------------------------------------------------------------------------

_MAIN_TABLE_CANDIDATES = ["MainData_Motor", "MainData_Home", "MainData"]
_OTHER_TABLE_CANDIDATES = ["AllOtherData_Motor", "AllOtherData_Home", "AllOtherData"]

_discovered_tables_cache: list[str] | None = None


def _probe_table_exists_simple(token: str, table_name: str) -> bool:
    """Check if a table exists — returns True if the query succeeds."""
    dax = f"EVALUATE TOPN(0, '{table_name}')"
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
        f"/datasets/{DATASET_ID}/executeQueries"
    )
    current_token = get_token()
    r = requests.post(
        url,
        headers={
            "Authorization": f"Bearer {current_token}",
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
    return "error" not in body


def discover_tables(token: str) -> list[str]:
    """Return all table names in the Power BI semantic model.

    Probes known table name variants with zero-row queries.
    INFO.TABLES() is skipped because it requires admin/build permissions
    that are not available in this environment.
    """
    global _discovered_tables_cache
    if _discovered_tables_cache is not None:
        return _discovered_tables_cache

    found: list[str] = []
    all_candidates = list(dict.fromkeys(
        _MAIN_TABLE_CANDIDATES + _OTHER_TABLE_CANDIDATES
    ))
    for name in all_candidates:
        if _probe_table_exists_simple(token, name):
            found.append(name)

    _discovered_tables_cache = found
    return found


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_main_table(_token: str) -> str:
    """Find the MainData table name (may be MainData, MainData_Motor, etc.)."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("MainData"):
            return t
    # Last resort: probe candidates directly (tables list may be partial)
    for name in _MAIN_TABLE_CANDIDATES:
        if _probe_table_exists_simple(_token, name):
            return name
    st.warning(f"Could not find MainData* table. Found: {tables}. Using fallback '{MAIN_TABLE}'.")
    return MAIN_TABLE


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_other_table(_token: str) -> str:
    """Find the AllOtherData table name."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("AllOtherData"):
            return t
    # Last resort: probe candidates directly
    for name in _OTHER_TABLE_CANDIDATES:
        if _probe_table_exists_simple(_token, name):
            return name
    st.warning(f"Could not find AllOtherData* table. Found: {tables}. Using fallback '{OTHER_TABLE}'.")
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
    """Fetch all MainData columns for Shopping & Switching analysis.

    Uses CALCULATETABLE to fetch every column in the table (no
    SELECTCOLUMNS) so the query works regardless of which columns
    exist.  The downstream transforms.py handles missing columns
    gracefully.
    """
    mt = main_table
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            '{mt}',
            '{mt}'[RenewalYearMonth] >= {start_month},
            '{mt}'[RenewalYearMonth] <= {end_month}
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


# ---------------------------------------------------------------------------
# Unfiltered loaders — used by disk cache to fetch ALL data at once
# ---------------------------------------------------------------------------

def load_all_maindata(token: str, main_table: str = MAIN_TABLE) -> pd.DataFrame:
    """Fetch ALL MainData rows (no date filter) for disk caching."""
    dax = f"EVALUATE '{main_table}'"
    return run_dax(token, dax)


def load_all_questions(token: str, main_table: str = MAIN_TABLE,
                       other_table: str = OTHER_TABLE) -> pd.DataFrame:
    """Fetch ALL question data (no date filter) for disk caching."""
    dax = f"""
        EVALUATE
        SUMMARIZECOLUMNS(
            '{other_table}'[UniqueID],
            '{other_table}'[QuestionNumber],
            '{other_table}'[Answer]
        )
    """
    return run_dax(token, dax)
