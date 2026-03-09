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

def run_dax(token: str, dax: str) -> pd.DataFrame:
    """Execute a DAX query against the Power BI semantic model."""
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
        st.error(f"Query failed: {r.text}")
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

def discover_tables(token: str) -> list[str]:
    """Return all table names in the Power BI semantic model."""
    dax = "EVALUATE INFO.TABLES()"
    df = run_dax(token, dax)
    if df.empty:
        return []
    # INFO.TABLES() returns a column named "Name" (after bracket stripping)
    name_col = [c for c in df.columns if c.lower() == "name"]
    if not name_col:
        return df.iloc[:, 0].tolist()
    return df[name_col[0]].tolist()


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_main_table(_token: str) -> str:
    """Find the MainData table name (may be MainData, MainData_Motor, etc.)."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("MainData"):
            return t
    st.warning(f"Could not find MainData* table. Found: {tables}. Using fallback '{MAIN_TABLE}'.")
    return MAIN_TABLE


@st.cache_data(ttl=3600, show_spinner="Discovering tables...")
def get_other_table(_token: str) -> str:
    """Find the AllOtherData table name."""
    tables = discover_tables(_token)
    for t in tables:
        if t.startswith("AllOtherData"):
            return t
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
