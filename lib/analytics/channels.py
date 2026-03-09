"""
Channel and PCW analysis using EAV data.

Q9b = shopping channels (multi-select)
Q11 = PCWs used (multi-select)
Q11d = PCW ratings (matrix — individual columns in flat export, or EAV rows)
Q13a = quote channels (matrix)
Q13b = purchase channel
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.queries import count_mentions, query_multi, query_single, respondent_count


def calc_channel_usage(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    insurer: str | None = None,
) -> pd.Series | None:
    """
    Percentage of shoppers using each channel (Q9b).

    Multi-code so totals can exceed 100%.
    Returns Series: channel_name → usage_rate, sorted descending.
    """
    if df_questions is None or df_questions.empty:
        return _fallback_channel_usage(df_main)

    shoppers = df_main[df_main["IsShopper"]]
    if insurer:
        shoppers = shoppers[shoppers["CurrentCompany"] == insurer]
    if shoppers.empty:
        return None

    shopper_ids = shoppers["UniqueID"]
    mentions = count_mentions(df_questions, "Q9b", shopper_ids)
    if mentions.empty:
        return None

    n_shoppers = len(shopper_ids)
    return (mentions / n_shoppers).sort_values(ascending=False)


def calc_pcw_usage(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    insurer: str | None = None,
) -> pd.Series | None:
    """
    Percentage of PCW users who used each PCW (Q11).

    Returns Series: pcw_name → usage_rate, sorted descending.
    """
    if df_questions is None or df_questions.empty:
        return _fallback_pcw_usage(df_main)

    pcw_users = df_main[df_main["UsedPCW"]]
    if insurer:
        pcw_users = pcw_users[pcw_users["CurrentCompany"] == insurer]
    if pcw_users.empty:
        return None

    user_ids = pcw_users["UniqueID"]
    mentions = count_mentions(df_questions, "Q11", user_ids)
    if mentions.empty:
        return None

    n_users = len(user_ids)
    return (mentions / n_users).sort_values(ascending=False)


def calc_pcw_nps(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    pcw: str,
) -> float | None:
    """NPS for a specific PCW. Requires Q11d ratings in EAV or matrix columns."""
    if df_questions is None or df_questions.empty:
        return None

    # Q11d ratings may be stored as Q11d_<PCW> in flat export or as separate EAV rows
    q_code = f"Q11d_{pcw.replace(' ', '_')}"
    ratings = query_single(df_questions, q_code)
    if ratings.empty:
        ratings = query_single(df_questions, "Q11d")
    if ratings.empty:
        return None

    nps_vals = pd.to_numeric(ratings, errors="coerce").dropna()
    if len(nps_vals) == 0:
        return None
    promoters = (nps_vals >= 9).sum()
    detractors = (nps_vals <= 6).sum()
    return 100 * (promoters - detractors) / len(nps_vals)


def calc_quote_buy_mismatch(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
) -> float | None:
    """Percentage where Q37=2 (quoted via one method, bought via another)."""
    if df_questions is None or df_questions.empty:
        if df_main is not None and "Q37" in df_main.columns:
            valid = df_main[df_main["Q37"].notna()]
            if valid.empty:
                return None
            return (pd.to_numeric(valid["Q37"], errors="coerce") == 2).sum() / len(valid)
        return None

    vals = query_single(df_questions, "Q37")
    if vals.empty:
        return None
    numeric = pd.to_numeric(vals, errors="coerce").dropna()
    if len(numeric) == 0:
        return None
    return (numeric == 2).sum() / len(numeric)


def calc_channel_first_used(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
) -> pd.Series | None:
    """Percentage who used each channel first (Q13a rank=1 or first mention)."""
    if df_questions is None or df_questions.empty:
        return None
    shoppers = df_main[df_main["IsShopper"]]
    mentions = count_mentions(df_questions, "Q13a", shoppers["UniqueID"])
    if mentions.empty:
        return None
    return (mentions / mentions.sum()).sort_values(ascending=False)


def calc_pcw_purchase_rate(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    pcw: str,
) -> float | None:
    """% of PCW shoppers who bought via that PCW (Q36)."""
    if df_questions is None or df_questions.empty:
        return None
    pcw_users = df_main[df_main["UsedPCW"]]
    q11 = query_multi(df_questions, "Q11", pcw_users["UniqueID"])
    pcw_respondents = set(q11[q11["Answer"] == pcw]["UniqueID"])
    if not pcw_respondents:
        return None
    q36 = query_single(df_questions, "Q36", list(pcw_respondents))
    if q36.empty:
        return None
    purchased = (pd.to_numeric(q36, errors="coerce") == 1).sum()
    return purchased / len(pcw_respondents)


def calc_quote_reach(
    df_main: pd.DataFrame,
    df_questions: pd.DataFrame,
    insurer: str,
) -> int:
    """Count of shoppers who got a quote from this insurer (Q13b)."""
    shoppers = df_main[df_main["IsShopper"]]
    if df_questions is not None and not df_questions.empty:
        q13b = query_multi(df_questions, "Q13b", shoppers["UniqueID"])
        return len(q13b[q13b["Answer"].str.contains(insurer, case=False, na=False)]["UniqueID"].unique())
    if "Q13b" in df_main.columns:
        return shoppers["Q13b"].astype(str).str.contains(insurer, case=False, na=False).sum()
    return 0


# ---------------------------------------------------------------------------
# Legacy fallbacks (wide-format data without AllOtherData)
# ---------------------------------------------------------------------------

def _fallback_channel_usage(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    shoppers = df[df["IsShopper"]]
    if shoppers.empty:
        return None
    channel_cols = [c for c in df.columns if c.startswith("Q9b")]
    if not channel_cols:
        return None
    usage = {}
    for col in channel_cols:
        used = shoppers[col].fillna(0).astype(float).astype(int).sum()
        usage[col] = used / len(shoppers)
    return pd.Series(usage).sort_values(ascending=False)


def _fallback_pcw_usage(df: pd.DataFrame) -> pd.Series | None:
    if df is None or df.empty:
        return None
    pcw_users = df[df["UsedPCW"]]
    if pcw_users.empty:
        return None
    pcw_cols = [c for c in df.columns if c.startswith("Q11_")]
    if not pcw_cols:
        return None
    usage = {}
    for col in pcw_cols:
        used = pcw_users[col].fillna(0).astype(float).astype(int).sum()
        usage[col] = used / len(pcw_users)
    return pd.Series(usage).sort_values(ascending=False)
