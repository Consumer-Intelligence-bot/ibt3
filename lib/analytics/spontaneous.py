"""
Spontaneous (unprompted) brand awareness analytics from Q1 data.

Q1 is a grid question where respondents type brand names:
  - Rows 1-5 = mention order (1 = first mentioned / TOMA)
  - Column a & b per row = two mention slots at same rank

After pivot, the data lives as:
  - Q1_pos{row}{a|b} columns: normalised brand name (text)
  - Q1_{brand} columns: boolean mention flags

Metrics:
  - TOMA: % mentioning brand at position 1 (first to mind)
  - Total Mention: % mentioning brand at any position
  - Top-3: % mentioning brand at positions 1-3
  - Mean Position: average position where brand appears (lower = more salient)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lib.config import SYSTEM_FLOOR_N

# Position columns created by pivot: Q1_pos{row}{slot}
_POS_COLS = {
    1: ["Q1_pos1a", "Q1_pos1b"],
    2: ["Q1_pos2a", "Q1_pos2b"],
    3: ["Q1_pos3a", "Q1_pos3b"],
    4: ["Q1_pos4a", "Q1_pos4b"],
    5: ["Q1_pos5a", "Q1_pos5b"],
}


def _get_available_pos_cols(df: pd.DataFrame) -> dict[int, list[str]]:
    """Return {position: [col_names]} for columns that exist on df."""
    return {
        pos: [c for c in cols if c in df.columns]
        for pos, cols in _POS_COLS.items()
        if any(c in df.columns for c in cols)
    }


def _extract_mentions(df: pd.DataFrame, pos_cols: dict[int, list[str]]) -> pd.DataFrame:
    """Extract (UniqueID, Brand, position) triples from the position columns.

    Deduplicates so each respondent counts only once per brand per position.
    """
    parts = []
    for pos, cols in pos_cols.items():
        for col in cols:
            chunk = df[["UniqueID", col]].copy()
            chunk = chunk.rename(columns={col: "Brand"})
            chunk["Brand"] = chunk["Brand"].astype(str).str.strip()
            chunk = chunk[chunk["Brand"].notna() & ~chunk["Brand"].isin(["", "nan", "None", "False"])]
            if not chunk.empty:
                chunk["position"] = pos
                parts.append(chunk)
    if not parts:
        return pd.DataFrame(columns=["UniqueID", "Brand", "position"])
    result = pd.concat(parts, ignore_index=True)
    # Deduplicate: each respondent counts once per brand per position
    result = result.drop_duplicates(subset=["UniqueID", "Brand", "position"])
    return result


def calc_spontaneous_metrics(
    df_main: pd.DataFrame,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Compute per-brand per-month spontaneous awareness metrics.

    Returns DataFrame with columns:
      brand, month, toma, mention, top3, mean_position, n_total, n_toma, n_mention, n_top3
    """
    pos_cols = _get_available_pos_cols(df_main)
    if not pos_cols:
        return pd.DataFrame()

    all_pos_col_names = [c for cols in pos_cols.values() for c in cols]
    if not all_pos_col_names:
        return pd.DataFrame()

    months = sorted(df_main[time_col].dropna().unique())
    rows = []

    for month in months:
        month_data = df_main[df_main[time_col] == month]

        # Denominator: respondents who mentioned at least one brand
        answered = month_data[all_pos_col_names].apply(
            lambda row: any(
                pd.notna(v) and str(v).strip() not in ("", "nan", "None", "False")
                for v in row
            ), axis=1
        )
        n_total = int(answered.sum())
        if n_total < SYSTEM_FLOOR_N:
            continue

        mentions = _extract_mentions(month_data, pos_cols)
        if mentions.empty:
            continue

        for brand, brand_data in mentions.groupby("Brand"):
            unique_respondents = brand_data["UniqueID"].nunique()
            toma_respondents = brand_data[brand_data["position"] == 1]["UniqueID"].nunique()
            top3_respondents = brand_data[brand_data["position"] <= 3]["UniqueID"].nunique()
            mean_pos = brand_data.groupby("UniqueID")["position"].min().mean()

            rows.append({
                "brand": brand,
                "month": month,
                "toma": toma_respondents / n_total,
                "mention": unique_respondents / n_total,
                "top3": top3_respondents / n_total,
                "mean_position": mean_pos,
                "n_total": n_total,
                "n_toma": toma_respondents,
                "n_mention": unique_respondents,
                "n_top3": top3_respondents,
            })

    if not rows:
        return pd.DataFrame()

    return pd.DataFrame(rows)


def calc_toma_share(metrics: pd.DataFrame, top_n: int = 8):
    """
    TOMA share over time for stacked area chart.

    Returns (DataFrame, top_brands_list) or (empty DataFrame, []).
    DataFrame has months as rows, brand names + "Other" as columns, values = TOMA %.
    """
    if metrics.empty:
        return pd.DataFrame(), []

    brand_avg = metrics.groupby("brand")["toma"].mean().sort_values(ascending=False)
    top_brands = brand_avg.head(top_n).index.tolist()

    months = sorted(metrics["month"].unique())
    rows = []
    for month in months:
        month_data = metrics[metrics["month"] == month]
        row = {"month": month}
        other = 0
        for _, r in month_data.iterrows():
            if r["brand"] in top_brands:
                row[r["brand"]] = round(r["toma"], 4)
            else:
                other += r["toma"]
        row["Other"] = round(other, 4)
        rows.append(row)

    return pd.DataFrame(rows), top_brands


def calc_toma_ranks(metrics: pd.DataFrame, top_n: int = 8):
    """
    TOMA rank by month for bump chart.

    Returns (DataFrame, top_brands_list) or (empty DataFrame, []).
    DataFrame has months as rows, brand names as columns, values = rank.
    """
    if metrics.empty:
        return pd.DataFrame(), []

    brand_avg = metrics.groupby("brand")["toma"].mean().sort_values(ascending=False)
    top_brands = brand_avg.head(top_n).index.tolist()

    months = sorted(metrics["month"].unique())
    rows = []
    for month in months:
        month_data = metrics[metrics["month"] == month]
        month_data = month_data[month_data["brand"].isin(top_brands)]
        ranked = month_data.sort_values("toma", ascending=False)
        row = {"month": month}
        for rank, (_, r) in enumerate(ranked.iterrows(), 1):
            row[r["brand"]] = rank
        rows.append(row)

    return pd.DataFrame(rows), top_brands


def calc_decay_curve(
    df_main: pd.DataFrame,
    brand: str,
    selected_months: list[int] | None = None,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Mention decay curve: % of respondents mentioning brand at each position.

    Returns DataFrame with columns: position (1-5), pct.
    """
    pos_cols = _get_available_pos_cols(df_main)
    if not pos_cols:
        return pd.DataFrame()

    data = df_main.copy()
    if selected_months:
        data = data[data[time_col].isin(selected_months)]

    all_pos_col_names = [c for cols in pos_cols.values() for c in cols]
    answered = data[all_pos_col_names].apply(
        lambda row: any(
            pd.notna(v) and str(v).strip() not in ("", "nan", "None", "False")
            for v in row
        ), axis=1
    )
    n_total = int(answered.sum())
    if n_total == 0:
        return pd.DataFrame()

    rows = []
    for pos, cols in sorted(pos_cols.items()):
        n_at_pos = 0
        for col in cols:
            n_at_pos += (data[col].astype(str).str.strip() == brand).sum()
        rows.append({"position": pos, "pct": round(n_at_pos / n_total * 100, 1)})

    return pd.DataFrame(rows)


def calc_salience_gap(metrics: pd.DataFrame, month: int | None = None) -> pd.DataFrame:
    """
    Salience gap: scatter data with total awareness vs TOMA.

    Returns DataFrame with: brand, mention_pct, toma_pct, mean_position.
    """
    if metrics.empty:
        return pd.DataFrame()

    if month is None:
        month = metrics["month"].max()

    data = metrics[metrics["month"] == month].copy()
    if data.empty:
        return pd.DataFrame()

    return data[["brand", "mention", "toma", "mean_position"]].rename(
        columns={"mention": "mention_pct", "toma": "toma_pct"}
    )
