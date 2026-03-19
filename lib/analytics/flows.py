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


def calc_net_flow(df: pd.DataFrame, insurer: str, base: int | None = None) -> dict:
    """Gained (switched TO) minus Lost (switched FROM).

    If *base* is provided (e.g. renewal base for this insurer), also returns
    gained_pct, lost_pct, and net_pct as proportions of base.
    """
    if df is None or len(df) == 0:
        return {"gained": 0, "lost": 0, "net": 0,
                "gained_pct": None, "lost_pct": None, "net_pct": None}
    switchers = _exclude_q4_eq_q39(df[df["IsSwitcher"]])
    gained = len(switchers[switchers["CurrentCompany"] == insurer])
    lost = len(switchers[switchers["PreviousCompany"] == insurer])
    net = gained - lost

    # Percentage of base
    if base and base > 0:
        gained_pct = gained / base
        lost_pct = lost / base
        net_pct = net / base
    else:
        gained_pct = None
        lost_pct = None
        net_pct = None

    return {
        "gained": gained, "lost": lost, "net": net,
        "gained_pct": gained_pct, "lost_pct": lost_pct, "net_pct": net_pct,
    }


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


def calc_flow_index(df: pd.DataFrame, insurer: str) -> dict:
    """
    Calculate over/under index for losses and gains vs market average.

    For losses (insurer X losing to competitor Y):
        insurer_share  = count(X → Y) / count(X → any)
        market_share   = count(any → Y) / count(any → any)
        index          = (insurer_share / market_share) * 100

    For gains (insurer X winning from competitor Y):
        insurer_share  = count(Y → X) / count(any → X)
        market_share   = count(Y → any) / count(any → any)
        index          = (insurer_share / market_share) * 100

    Index of 100 = market average.
    Index > 100  = over-indexing vs market.
    Index < 100  = under-indexing vs market.

    Rows where raw_count < MIN_BASE_FLOW_CELL are excluded entirely.
    Rows where market_share == 0 are excluded (avoid division by zero).

    Parameters
    ----------
    df : pd.DataFrame
        Full dataset (all insurers, all respondents). Must contain
        IsSwitcher, CurrentCompany, PreviousCompany columns.
    insurer : str
        The selected insurer to analyse.

    Returns
    -------
    dict with keys:
        loss_index : pd.DataFrame
            columns: competitor, raw_count, insurer_share,
                     market_share, index
            sorted descending by index
        gain_index : pd.DataFrame
            columns: competitor, raw_count, insurer_share,
                     market_share, index
            sorted descending by index
        total_switchers : int
            Total switchers in the dataset (for context)
        insurer_lost : int
            Total customers lost by selected insurer
        insurer_gained : int
            Total customers gained by selected insurer
    """
    _cols = ["competitor", "raw_count", "insurer_share", "market_share", "index"]
    empty = pd.DataFrame(columns=_cols)

    df = _exclude_q4_eq_q39(df)

    # Work only with switchers
    switchers = df[df["IsSwitcher"]].copy()

    # Exclude null/empty PreviousCompany and CurrentCompany
    switchers = switchers[
        switchers["PreviousCompany"].notna() & (switchers["PreviousCompany"] != "")
        & switchers["CurrentCompany"].notna() & (switchers["CurrentCompany"] != "")
    ]

    # Exclude vague/unknown categories
    exclude_pattern = r"Don't Know|Can't Remember|Other"
    switchers = switchers[
        ~switchers["PreviousCompany"].str.contains(exclude_pattern, case=False, na=False)
        & ~switchers["CurrentCompany"].str.contains(exclude_pattern, case=False, na=False)
    ]

    total_switchers = len(switchers)

    if total_switchers == 0:
        return {
            "loss_index": empty,
            "gain_index": empty,
            "total_switchers": 0,
            "insurer_lost": 0,
            "insurer_gained": 0,
        }

    # --- LOSSES: insurer losing to competitors ---
    lost = switchers[switchers["PreviousCompany"] == insurer]
    insurer_lost = len(lost)

    loss_rows = []
    if insurer_lost > 0:
        lost_to = lost["CurrentCompany"].value_counts()
        market_to = switchers["CurrentCompany"].value_counts()

        for competitor, raw_count in lost_to.items():
            insurer_share = raw_count / insurer_lost
            mkt_share = market_to.get(competitor, 0) / total_switchers
            if mkt_share == 0:
                continue
            loss_rows.append({
                "competitor": competitor,
                "raw_count": raw_count,
                "insurer_share": insurer_share,
                "market_share": mkt_share,
                "index": (insurer_share / mkt_share) * 100,
            })

    loss_df = pd.DataFrame(loss_rows, columns=_cols)
    if not loss_df.empty:
        loss_df = loss_df[loss_df["raw_count"] >= MIN_BASE_FLOW_CELL]
        loss_df = loss_df.sort_values("index", ascending=False).reset_index(drop=True)

    # --- GAINS: insurer winning from competitors ---
    gained = switchers[switchers["CurrentCompany"] == insurer]
    insurer_gained = len(gained)

    gain_rows = []
    if insurer_gained > 0:
        won_from = gained["PreviousCompany"].value_counts()
        market_from = switchers["PreviousCompany"].value_counts()

        for competitor, raw_count in won_from.items():
            insurer_share = raw_count / insurer_gained
            mkt_share = market_from.get(competitor, 0) / total_switchers
            if mkt_share == 0:
                continue
            gain_rows.append({
                "competitor": competitor,
                "raw_count": raw_count,
                "insurer_share": insurer_share,
                "market_share": mkt_share,
                "index": (insurer_share / mkt_share) * 100,
            })

    gain_df = pd.DataFrame(gain_rows, columns=_cols)
    if not gain_df.empty:
        gain_df = gain_df[gain_df["raw_count"] >= MIN_BASE_FLOW_CELL]
        gain_df = gain_df.sort_values("index", ascending=False).reset_index(drop=True)

    return {
        "loss_index": loss_df,
        "gain_index": gain_df,
        "total_switchers": total_switchers,
        "insurer_lost": insurer_lost,
        "insurer_gained": insurer_gained,
    }
