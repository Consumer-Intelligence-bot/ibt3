"""
Power BI data layer — MSAL authentication and DAX query execution.
Shared by all pages in the unified Streamlit dashboard.
"""

import msal
import pandas as pd
import requests
import streamlit as st

from lib.config import TENANT_ID, CLIENT_ID, WORKSPACE_ID, DATASET_ID, SCOPE


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
# Claims DAX queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading months...")
def load_months(_token):
    dax = """
        EVALUATE
        SUMMARIZE(
            MainData,
            MainData[RenewalYearMonth]
        )
        ORDER BY MainData[RenewalYearMonth] ASC
    """
    df = run_dax(_token, dax)
    if df.empty:
        return []
    return sorted(df["RenewalYearMonth"].dropna().unique().astype(int).tolist())


@st.cache_data(ttl=3600, show_spinner="Loading Q52 data...")
def load_q52(_token, start_month: int, end_month: int):
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                MainData[CurrentCompany],
                "Q52_n", CALCULATE(
                    COUNTROWS(AllOtherData),
                    AllOtherData[QuestionNumber] = "Q52"
                ),
                "Q52_mean", CALCULATE(
                    AVERAGEX(AllOtherData, VALUE(AllOtherData[Scale])),
                    AllOtherData[QuestionNumber] = "Q52"
                ),
                "Q52_std", CALCULATE(
                    STDEVX.P(AllOtherData, VALUE(AllOtherData[Scale])),
                    AllOtherData[QuestionNumber] = "Q52"
                )
            ),
            MainData[Claimants] = "Claimant",
            MainData[RenewalYearMonth] >= {start_month},
            MainData[RenewalYearMonth] <= {end_month}
        )
        ORDER BY [Q52_n] DESC
    """
    return run_dax(_token, dax)


@st.cache_data(ttl=3600, show_spinner="Loading Q53 data...")
def load_q53(_token, start_month: int, end_month: int):
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                MainData[CurrentCompany],
                AllOtherData[Subject],
                AllOtherData[Ranking],
                "Q53_n", COUNTROWS(AllOtherData),
                "Q53_mean", AVERAGEX(AllOtherData, VALUE(AllOtherData[Scale])),
                "Q53_std", STDEVX.P(AllOtherData, VALUE(AllOtherData[Scale]))
            ),
            AllOtherData[QuestionNumber] = "Q53",
            MainData[Claimants] = "Claimant",
            MainData[RenewalYearMonth] >= {start_month},
            MainData[RenewalYearMonth] <= {end_month}
        )
        ORDER BY MainData[CurrentCompany] ASC, AllOtherData[Ranking] ASC
    """
    return run_dax(_token, dax)


# ---------------------------------------------------------------------------
# Shopping & Switching DAX queries
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600, show_spinner="Loading S&S main data...")
def load_ss_maindata(_token, start_month: int, end_month: int):
    """Fetch MainData profile columns for Shopping & Switching analysis."""
    dax = f"""
        EVALUATE
        FILTER(
            SELECTCOLUMNS(
                MainData,
                "UniqueID", MainData[UniqueID],
                "RenewalYearMonth", MainData[RenewalYearMonth],
                "SurveyYearMonth", MainData[SurveyYearMonth],
                "CurrentCompany", MainData[CurrentCompany],
                "PreRenewalCompany", MainData[PreRenewalCompany],
                "Region", MainData[Region],
                "Age Group", MainData[Age Group],
                "Gender", MainData[Gender],
                "Shoppers", MainData[Shoppers],
                "Switchers", MainData[Switchers],
                "Retained", MainData[Retained],
                "Renewal premium change", MainData[Renewal premium change],
                "How much higher", MainData[How much higher],
                "How much lower", MainData[How much lower],
                "Did you use a PCW for shopping", MainData[Did you use a PCW for shopping],
                "Claimants", MainData[Claimants],
                "Employment status", MainData[Employment status]
            ),
            [RenewalYearMonth] >= {start_month} && [RenewalYearMonth] <= {end_month}
        )
    """
    return run_dax(_token, dax)


@st.cache_data(ttl=3600, show_spinner="Loading S&S question data...")
def load_ss_questions(_token, start_month: int, end_month: int):
    """Fetch AllOtherData EAV table for Shopping & Switching analysis."""
    dax = f"""
        EVALUATE
        CALCULATETABLE(
            SUMMARIZECOLUMNS(
                AllOtherData[UniqueID],
                AllOtherData[QuestionNumber],
                AllOtherData[Answer]
            ),
            MainData[RenewalYearMonth] >= {start_month},
            MainData[RenewalYearMonth] <= {end_month}
        )
    """
    return run_dax(_token, dax)
