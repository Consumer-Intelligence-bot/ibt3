"""
Channel and PCW analysis using wide-format question data.

Q9b = shopping channels (multi-select boolean columns)
Q11 = PCWs used (multi-select boolean columns)
Q11d = PCW NPS rating (numeric column)
Q13a = quote channels (ranked columns)
Q13b = purchase channel (multi-select boolean columns)
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.queries import count_mentions, query_multi, query_ranked, query_single


def calc_channel_usage(
    df_main: pd.DataFrame,
    insurer: str | None = None,
) -> pd.Series | None:
    """
    Percentage of shoppers using each channel (Q9b).

    Multi-code so totals can exceed 100%.
    Returns Series: channel_name -> usage_rate, sorted descending.
    """
    shoppers = df_main[df_main["IsShopper"]]
    if insurer:
        shoppers = shoppers[shoppers["CurrentCompany"] == insurer]
    if shoppers.empty:
        return None

    shopper_ids = shoppers["UniqueID"]
    mentions = count_mentions(df_main, "Q9b", shopper_ids)
    if mentions.empty:
        return None

    n_shoppers = len(shopper_ids)
    return (mentions / n_shoppers).sort_values(ascending=False)


def calc_pcw_usage(
    df_main: pd.DataFrame,
    insurer: str | None = None,
) -> pd.Series | None:
    """
    Percentage of PCW users who used each PCW (Q11).

    Returns Series: pcw_name -> usage_rate, sorted descending.
    """
    pcw_users = df_main[df_main["UsedPCW"]]
    if insurer:
        pcw_users = pcw_users[pcw_users["CurrentCompany"] == insurer]
    if pcw_users.empty:
        return None

    user_ids = pcw_users["UniqueID"]
    mentions = count_mentions(df_main, "Q11", user_ids)
    if mentions.empty:
        return None

    n_users = len(user_ids)
    return (mentions / n_users).sort_values(ascending=False)


def calc_pcw_nps(
    df_main: pd.DataFrame,
    pcw: str,
) -> float | None:
    """NPS for a specific PCW. Uses Q11d numeric column."""
    # Try PCW-specific column first (grid pivot may create Q11d_{pcw})
    q_code = f"Q11d_{pcw.replace(' ', '_')}"
    if q_code in df_main.columns:
        nps_vals = pd.to_numeric(df_main[q_code], errors="coerce").dropna()
    elif "Q11d" in df_main.columns:
        nps_vals = pd.to_numeric(df_main["Q11d"], errors="coerce").dropna()
    else:
        return None

    if len(nps_vals) == 0:
        return None
    promoters = (nps_vals >= 9).sum()
    detractors = (nps_vals <= 6).sum()
    return 100 * (promoters - detractors) / len(nps_vals)


def calc_quote_buy_mismatch(
    df_main: pd.DataFrame,
) -> float | None:
    """Percentage where Q37=2 (quoted via one method, bought via another)."""
    if "Q37" not in df_main.columns:
        return None
    valid = df_main[df_main["Q37"].notna()]
    if valid.empty:
        return None
    numeric = pd.to_numeric(valid["Q37"], errors="coerce").dropna()
    if len(numeric) == 0:
        return None
    return (numeric == 2).sum() / len(numeric)


def calc_channel_first_used(
    df_main: pd.DataFrame,
) -> pd.Series | None:
    """Percentage who used each channel first (Q13a rank=1)."""
    shoppers = df_main[df_main["IsShopper"]]
    ranked = query_ranked(df_main, "Q13a", shoppers["UniqueID"])
    if ranked.empty:
        return None
    first_used = ranked[ranked["Rank"] == 1]
    if first_used.empty:
        return None
    counts = first_used["Answer"].value_counts()
    return (counts / counts.sum()).sort_values(ascending=False)


def calc_pcw_purchase_rate(
    df_main: pd.DataFrame,
    pcw: str,
) -> float | None:
    """% of PCW shoppers who bought via that PCW (Q36)."""
    pcw_users = df_main[df_main["UsedPCW"]]
    q11 = query_multi(df_main, "Q11", pcw_users["UniqueID"])
    pcw_respondents = set(q11[q11["Answer"] == pcw]["UniqueID"])
    if not pcw_respondents:
        return None
    if "Q36" not in df_main.columns:
        return None
    q36_data = df_main[df_main["UniqueID"].isin(pcw_respondents)][["UniqueID", "Q36"]]
    q36_data = q36_data[q36_data["Q36"].notna()]
    if q36_data.empty:
        return None
    purchased = (pd.to_numeric(q36_data["Q36"], errors="coerce") == 1).sum()
    return purchased / len(pcw_respondents)


def calc_quote_reach(
    df_main: pd.DataFrame,
    insurer: str,
) -> int:
    """Count of shoppers who got a quote from this insurer (Q13b)."""
    shoppers = df_main[df_main["IsShopper"]]
    q13b = query_multi(df_main, "Q13b", shoppers["UniqueID"])
    if not q13b.empty:
        return len(q13b[q13b["Answer"].str.contains(insurer, case=False, na=False)]["UniqueID"].unique())
    # Fallback to direct column
    if "Q13b" in df_main.columns:
        return shoppers["Q13b"].astype(str).str.contains(insurer, case=False, na=False).sum()
    return 0
