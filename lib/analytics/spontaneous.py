"""
Spontaneous (unprompted) brand awareness analytics from Q1 data.

Q1 is a grid question where respondents type brand names:
  - Rows 1-5 = mention order (1 = first mentioned / TOMA)
  - Column 1 & Column 2 per row = two mention slots at same rank

Metrics:
  - TOMA: % mentioning brand in row 1 (first to mind)
  - Total Mention: % mentioning brand at any position
  - Top-3: % mentioning brand in rows 1-3
  - Mean Position: average row where brand appears (lower = more salient)
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from lib.config import SYSTEM_FLOOR_N


# Map Q1 sub-questions to row numbers (mention rank)
_Q1_ROW_MAP = {
    "Q1_1": 1, "Q1_2": 1,   # Row 1 (TOMA)
    "Q1_3": 2, "Q1_4": 2,   # Row 2
    "Q1_5": 3, "Q1_6": 3,   # Row 3
    "Q1_7": 4, "Q1_8": 4,   # Row 4
    "Q1_9": 5, "Q1_10": 5,  # Row 5
}


def calc_spontaneous_metrics(
    df_main: pd.DataFrame,
    time_col: str = "RenewalYearMonth",
) -> pd.DataFrame:
    """
    Compute per-brand per-month spontaneous awareness metrics.

    Returns DataFrame with columns:
      brand, month, toma, mention, top3, mean_position, n_total, n_toma, n_mention, n_top3
    """
    q1_cols = [c for c in df_main.columns if c.startswith("Q1_") and not c.startswith("Q1_{")]
    if not q1_cols:
        return pd.DataFrame()

    months = sorted(df_main[time_col].dropna().unique())
    rows = []

    for month in months:
        month_data = df_main[df_main[time_col] == month]
        # Denominator: respondents who mentioned at least one brand
        answered = month_data[q1_cols].any(axis=1)
        n_total = int(answered.sum())
        if n_total < SYSTEM_FLOOR_N:
            continue

        # Collect all brand mentions with their row positions
        mentions = []
        for col in q1_cols:
            if col not in month_data.columns:
                continue
            vals = month_data[["UniqueID", col]].dropna(subset=[col])
            vals = vals[vals[col].astype(str).str.strip() != ""]
            vals = vals[vals[col].astype(str) != "False"]
            vals = vals[vals[col].astype(str) != "nan"]
            if vals.empty:
                continue
            vals = vals.rename(columns={col: "Brand"})
            vals["Brand"] = vals["Brand"].astype(str).str.strip()
            vals["row"] = _Q1_ROW_MAP.get(col, 99)
            mentions.append(vals)

        if not mentions:
            continue

        all_mentions = pd.concat(mentions, ignore_index=True)
        # Remove rows where Brand is boolean False (from Q1 boolean columns)
        all_mentions = all_mentions[~all_mentions["Brand"].isin(["False", "True", "nan", ""])]

        if all_mentions.empty:
            continue

        # Group by brand
        for brand, brand_data in all_mentions.groupby("Brand"):
            unique_respondents = brand_data["UniqueID"].nunique()
            toma_respondents = brand_data[brand_data["row"] == 1]["UniqueID"].nunique()
            top3_respondents = brand_data[brand_data["row"] <= 3]["UniqueID"].nunique()
            mean_pos = brand_data.groupby("UniqueID")["row"].min().mean()

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


def calc_toma_share(metrics: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    """
    TOMA share over time for stacked area chart.

    Returns DataFrame with months as rows, brand names as columns,
    values = TOMA % share. Includes "Other" column.
    """
    if metrics.empty:
        return pd.DataFrame()

    # Identify top brands by average TOMA
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
                row[r["brand"]] = round(r["toma"] * 100, 1)
            else:
                other += r["toma"] * 100
        row["Other"] = round(other, 1)
        rows.append(row)

    return pd.DataFrame(rows), top_brands


def calc_toma_ranks(metrics: pd.DataFrame, top_n: int = 8) -> pd.DataFrame:
    """
    TOMA rank by month for bump chart.

    Returns DataFrame with months as rows, brand names as columns,
    values = rank position (1 = highest TOMA).
    """
    if metrics.empty:
        return pd.DataFrame()

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
    q1_cols = [c for c in df_main.columns if c.startswith("Q1_") and not c.startswith("Q1_{")]
    if not q1_cols:
        return pd.DataFrame()

    data = df_main.copy()
    if selected_months:
        data = data[data[time_col].isin(selected_months)]

    answered = data[q1_cols].any(axis=1)
    n_total = int(answered.sum())
    if n_total == 0:
        return pd.DataFrame()

    rows = []
    for pos in range(1, 6):
        # Find Q1 sub-questions for this row
        pos_cols = [c for c, r in _Q1_ROW_MAP.items() if r == pos and c in data.columns]
        n_at_pos = 0
        for col in pos_cols:
            vals = data[col].astype(str).str.strip()
            n_at_pos += (vals == brand).sum()
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
