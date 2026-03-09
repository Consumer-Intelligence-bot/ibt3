"""
Customer flow analysis: switching matrix, net flow, top sources/destinations.

Spec Section 12.4: respondents whose CurrentCompany == PreviousCompany are
excluded from ALL flow calculations (likely data-entry errors).
"""
import pandas as pd

from lib.config import MIN_BASE_FLOW_CELL


def _exclude_q4_eq_q39(df: pd.DataFrame) -> pd.DataFrame:
    """Remove switchers where current insurer equals stated previous insurer."""
    if "PreviousCompany" not in df.columns or "CurrentCompany" not in df.columns:
        return df
    return df[df["CurrentCompany"] != df["PreviousCompany"]]


def calc_flow_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Pivot: rows=PreviousCompany, cols=CurrentCompany, values=count."""
    if df is None or len(df) == 0:
        return pd.DataFrame()
    switchers = df[df["IsSwitcher"]].copy()
    switchers = switchers[switchers["PreviousCompany"].notna() & (switchers["PreviousCompany"] != "")]
    switchers = _exclude_q4_eq_q39(switchers)
    if len(switchers) == 0:
        return pd.DataFrame()
    return switchers.pivot_table(
        index="PreviousCompany",
        columns="CurrentCompany",
        values="UniqueID",
        aggfunc="count",
        fill_value=0,
    )


def calc_net_flow(df: pd.DataFrame, insurer: str) -> dict:
    """Gained (switched TO) minus Lost (switched FROM)."""
    if df is None or len(df) == 0:
        return {"gained": 0, "lost": 0, "net": 0}
    switchers = _exclude_q4_eq_q39(df[df["IsSwitcher"]])
    gained = len(switchers[switchers["CurrentCompany"] == insurer])
    lost = len(switchers[switchers["PreviousCompany"] == insurer])
    return {"gained": gained, "lost": lost, "net": gained - lost}


def calc_top_sources(df: pd.DataFrame, insurer: str, n: int = 10) -> pd.Series:
    """Top n insurers sending customers to selected insurer."""
    if df is None or len(df) == 0:
        return pd.Series(dtype=int)
    switchers = _exclude_q4_eq_q39(df[(df["IsSwitcher"]) & (df["CurrentCompany"] == insurer)])
    return switchers["PreviousCompany"].value_counts().head(n)


def calc_top_destinations(df: pd.DataFrame, insurer: str, n: int = 10) -> pd.Series:
    """Top n insurers receiving customers from selected insurer."""
    if df is None or len(df) == 0:
        return pd.Series(dtype=int)
    switchers = _exclude_q4_eq_q39(df[(df["IsSwitcher"]) & (df["PreviousCompany"] == insurer)])
    return switchers["CurrentCompany"].value_counts().head(n)


def calc_flow_pct_of_lost(df: pd.DataFrame, insurer: str) -> pd.Series:
    """Distribution of where lost customers went."""
    if df is None or len(df) == 0:
        return pd.Series(dtype=float)
    lost = _exclude_q4_eq_q39(df[(df["IsSwitcher"]) & (df["PreviousCompany"] == insurer)])
    if len(lost) == 0:
        return pd.Series(dtype=float)
    return lost["CurrentCompany"].value_counts(normalize=True)


def calc_departed_sentiment(
    df: pd.DataFrame, insurer: str
) -> dict | None:
    """Mean Q40a, NPS from Q40b, mean tenure for departed customers."""
    if df is None or len(df) == 0:
        return None
    departed = _exclude_q4_eq_q39(df[(df["IsSwitcher"]) & (df["PreviousCompany"] == insurer)])
    if len(departed) == 0:
        return None
    result = {"n": len(departed)}
    if "Q40a" in departed.columns:
        result["mean_q40a"] = departed["Q40a"].mean()
    if "Q40b" in departed.columns:
        # NPS = % promoters - % detractors
        nps_vals = pd.to_numeric(departed["Q40b"], errors="coerce")
        promoters = (nps_vals >= 9).sum()
        detractors = (nps_vals <= 6).sum()
        result["nps"] = 100 * (promoters - detractors) / len(departed) if len(departed) > 0 else 0
    if "Q40" in departed.columns:
        result["mean_tenure"] = departed["Q40"].mean()
    return result


def is_flow_cell_suppressed(count: int) -> bool:
    """True if flow cell count below threshold."""
    return count < MIN_BASE_FLOW_CELL
