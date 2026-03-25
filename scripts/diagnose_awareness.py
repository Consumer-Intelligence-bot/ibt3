"""
Awareness data diagnostic — checks whether the uniform upward trend in
prompted awareness (Q2) is real or an artefact of sample/methodology.

Run from ibt3 root:
    python scripts/diagnose_awareness.py

Produces a text report to stdout with numbered findings.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Allow imports from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lib.powerbi import run_dax, get_main_table, get_other_table, discover_columns
from lib.config import MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID


def get_token() -> str:
    tf = Path.home() / ".ibt3" / "token.json"
    data = json.loads(tf.read_text())
    return data["access_token"]


def load_awareness_data(token: str, main: str, other: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load Q2 mentions and respondent counts per month."""
    ws, ds = MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID

    # Total respondents per month (from MainData)
    dax_resp = f"""
        EVALUATE
        SUMMARIZECOLUMNS(
            '{main}'[RenewalYearMonth],
            "n_respondents", COUNTROWS('{main}'),
            "n_unique", DISTINCTCOUNT('{main}'[UniqueID])
        )
        ORDER BY '{main}'[RenewalYearMonth]
    """
    df_resp = run_dax(token, dax_resp, silent=True, workspace_id=ws, dataset_id=ds)

    # Q2 mentions: UniqueID, Answer (brand), month
    # Batch to avoid 100K limit
    dax_q2 = f"""
        EVALUATE
        CALCULATETABLE(
            SELECTCOLUMNS(
                '{other}',
                '{other}'[UniqueID],
                '{other}'[Answer]
            ),
            '{other}'[QuestionNumber] = "Q2"
        )
    """
    df_q2 = run_dax(token, dax_q2, silent=True, workspace_id=ws, dataset_id=ds)

    # We also need the month for each respondent
    dax_months = f"""
        EVALUATE
        SELECTCOLUMNS(
            '{main}',
            '{main}'[UniqueID],
            '{main}'[RenewalYearMonth]
        )
    """
    df_months = run_dax(token, dax_months, silent=True, workspace_id=ws, dataset_id=ds)

    if not df_q2.empty and not df_months.empty:
        df_q2["UniqueID"] = df_q2["UniqueID"].astype(str)
        df_months["UniqueID"] = df_months["UniqueID"].astype(str)
        df_q2 = df_q2.merge(df_months, on="UniqueID", how="left")

    return df_resp, df_q2


def run_diagnostics():
    token = get_token()
    ws, ds = MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID
    main = get_main_table(token, workspace_id=ws, dataset_id=ds)
    other = get_other_table(token, workspace_id=ws, dataset_id=ds)

    print("=" * 70)
    print("AWARENESS DATA DIAGNOSTIC — Q2 (Prompted)")
    print(f"Tables: main={main}, other={other}")
    print("=" * 70)

    df_resp, df_q2 = load_awareness_data(token, main, other)

    if df_resp.empty or df_q2.empty:
        print("ERROR: Could not load data. Check token/permissions.")
        return

    df_resp["RenewalYearMonth"] = df_resp["RenewalYearMonth"].astype(int)
    df_q2["RenewalYearMonth"] = pd.to_numeric(df_q2["RenewalYearMonth"], errors="coerce")
    df_q2 = df_q2.dropna(subset=["RenewalYearMonth"])
    df_q2["RenewalYearMonth"] = df_q2["RenewalYearMonth"].astype(int)

    months = sorted(df_resp["RenewalYearMonth"].unique())

    # ------------------------------------------------------------------
    # CHECK 1: Respondent counts per month (denominator stability)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 1: Respondent counts per month (denominator)")
    print("-" * 70)
    print(f"{'Month':<12} {'Total rows':>12} {'Unique IDs':>12}")
    for _, row in df_resp.sort_values("RenewalYearMonth").iterrows():
        ym = int(row["RenewalYearMonth"])
        n = int(row.get("n_respondents", 0))
        u = int(row.get("n_unique", 0))
        print(f"{ym:<12} {n:>12,} {u:>12,}")

    n_vals = df_resp["n_respondents"].values if "n_respondents" in df_resp.columns else df_resp["n_unique"].values
    cv = np.std(n_vals) / np.mean(n_vals) if np.mean(n_vals) > 0 else 0
    print(f"\nCoefficient of variation: {cv:.2%}")
    if cv > 0.3:
        print("** WARNING: High variability in sample size across months.")
        print("   This alone can cause awareness rates to fluctuate.")

    # ------------------------------------------------------------------
    # CHECK 2: Average brands selected per respondent per month
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 2: Average brands selected per respondent per month")
    print("-" * 70)
    print("If this increases over time, ALL brands go up mechanically.")
    print(f"{'Month':<12} {'Respondents':>12} {'Q2 mentions':>12} {'Avg brands':>12}")

    avg_brands_by_month = []
    for month in months:
        month_mentions = df_q2[df_q2["RenewalYearMonth"] == month]
        n_mentions = len(month_mentions)
        n_respondents_q2 = month_mentions["UniqueID"].nunique()
        avg = n_mentions / n_respondents_q2 if n_respondents_q2 > 0 else 0
        avg_brands_by_month.append({"month": month, "avg_brands": avg,
                                     "n_resp": n_respondents_q2, "n_mentions": n_mentions})
        print(f"{month:<12} {n_respondents_q2:>12,} {n_mentions:>12,} {avg:>12.2f}")

    ab = pd.DataFrame(avg_brands_by_month)
    if len(ab) >= 3:
        corr = np.corrcoef(range(len(ab)), ab["avg_brands"])[0, 1]
        print(f"\nTrend correlation (avg brands vs time): {corr:.3f}")
        if corr > 0.5:
            print("** FINDING: Average brands per respondent is INCREASING over time.")
            print("   This is the most likely cause of the uniform upward trend.")
            print("   When respondents tick more brands, every brand's rate goes up.")
        elif corr < -0.5:
            print("   Average brands is decreasing — not the cause.")
        else:
            print("   No strong trend in average brands selected.")

    # ------------------------------------------------------------------
    # CHECK 3: Q2 response rate (% of respondents who answered Q2)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 3: Q2 response rate (% of MainData respondents who answered Q2)")
    print("-" * 70)
    print(f"{'Month':<12} {'MainData n':>12} {'Q2 resp':>12} {'Q2 rate':>12}")

    resp_lookup = dict(zip(df_resp["RenewalYearMonth"],
                           df_resp.get("n_unique", df_resp.get("n_respondents"))))
    for month in months:
        n_main = int(resp_lookup.get(month, 0))
        n_q2 = df_q2[df_q2["RenewalYearMonth"] == month]["UniqueID"].nunique()
        rate = n_q2 / n_main if n_main > 0 else 0
        print(f"{month:<12} {n_main:>12,} {n_q2:>12,} {rate:>12.1%}")

    # ------------------------------------------------------------------
    # CHECK 4: Cross-brand correlation (are all brands moving together?)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 4: Cross-brand correlation matrix (top 10 brands)")
    print("-" * 70)
    print("If all correlations are very high (>0.8), it confirms a")
    print("systematic/denominator issue rather than real brand movement.")

    # Build brand x month rate matrix
    rates = {}
    for month in months:
        month_data = df_q2[df_q2["RenewalYearMonth"] == month]
        n_total = int(resp_lookup.get(month, 0))
        if n_total == 0:
            continue
        brand_counts = month_data.groupby("Answer")["UniqueID"].nunique()
        for brand, count in brand_counts.items():
            if brand not in rates:
                rates[brand] = {}
            rates[brand][month] = count / n_total

    rate_df = pd.DataFrame(rates).fillna(0)
    # Top 10 by latest month
    if not rate_df.empty:
        latest = rate_df.iloc[-1].sort_values(ascending=False)
        top10 = latest.head(10).index.tolist()
        top_rates = rate_df[top10]

        corr_matrix = top_rates.corr()
        # Average pairwise correlation (excluding diagonal)
        mask = np.ones(corr_matrix.shape, dtype=bool)
        np.fill_diagonal(mask, False)
        avg_corr = corr_matrix.values[mask].mean()

        print(f"\nAverage pairwise correlation among top 10 brands: {avg_corr:.3f}")
        if avg_corr > 0.7:
            print("** FINDING: Brands are highly correlated — strong evidence of a")
            print("   systematic issue (denominator, survey methodology, or data processing).")
        elif avg_corr > 0.4:
            print("   Moderate correlation — some systematic component likely.")
        else:
            print("   Low correlation — brands are moving independently (expected).")

        print("\nCorrelation matrix:")
        print(corr_matrix.round(2).to_string())

    # ------------------------------------------------------------------
    # CHECK 5: Direction agreement (% months where all brands move same way)
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 5: Direction agreement (do all brands move the same way?)")
    print("-" * 70)

    if not rate_df.empty and len(rate_df) >= 2:
        changes = rate_df[top10].diff().iloc[1:]  # month-on-month change
        n_months = len(changes)
        all_up = (changes > 0).all(axis=1).sum()
        all_down = (changes < 0).all(axis=1).sum()
        mixed = n_months - all_up - all_down

        print(f"Months where ALL top 10 moved up:   {all_up}/{n_months}")
        print(f"Months where ALL top 10 moved down:  {all_down}/{n_months}")
        print(f"Months with mixed movement:          {mixed}/{n_months}")

        if (all_up + all_down) / n_months > 0.6:
            print("** FINDING: Brands move in unison too often — systematic cause likely.")

    # ------------------------------------------------------------------
    # CHECK 6: Duplicate UniqueIDs within a month
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 6: Duplicate respondent IDs (data integrity)")
    print("-" * 70)

    dupes_per_month = []
    for month in months:
        month_main = df_q2[df_q2["RenewalYearMonth"] == month]
        # Check if same UniqueID + Answer appears multiple times
        dupes = month_main.duplicated(subset=["UniqueID", "Answer"]).sum()
        if dupes > 0:
            dupes_per_month.append((month, dupes))

    if dupes_per_month:
        print("Duplicate (UniqueID, Answer) pairs found:")
        for month, count in dupes_per_month:
            print(f"  {month}: {count} duplicates")
    else:
        print("No duplicate (UniqueID, Answer) pairs. Data is clean.")

    # ------------------------------------------------------------------
    # CHECK 7: Month-on-month rate change summary
    # ------------------------------------------------------------------
    print("\n" + "-" * 70)
    print("CHECK 7: Month-on-month rate change (top 10 brands)")
    print("-" * 70)

    if not rate_df.empty:
        print(f"{'Month':<12}", end="")
        for brand in top10:
            print(f" {brand[:8]:>9}", end="")
        print()
        for i, month in enumerate(rate_df.index):
            print(f"{int(month):<12}", end="")
            for brand in top10:
                val = rate_df.loc[month, brand]
                if i == 0:
                    print(f" {val:>8.1%}", end="")
                else:
                    prev = rate_df.iloc[i - 1][brand]
                    delta = val - prev
                    print(f" {delta:>+8.1%}", end="")
            print()

    # ------------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------------
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    if len(ab) >= 3:
        corr_brands = np.corrcoef(range(len(ab)), ab["avg_brands"])[0, 1]
        if corr_brands > 0.5:
            print("PRIMARY SUSPECT: Average brands per respondent is increasing")
            print("over time. This mechanically inflates ALL brands' awareness.")
            print()
            print("Possible causes:")
            print("  1. Survey presentation changed (more brands shown?)")
            print("  2. Respondent profile shifted (more engaged respondents?)")
            print("  3. 'Select all that apply' interpretation changed")
            print("  4. Data processing change (how multi-select is coded)")
            print()
            print("Recommended action:")
            print("  - Check with the fieldwork team whether Q2 options changed")
            print("  - Compare respondent demographics across months")
            print("  - Check if the number of brand options in Q2 changed")
        elif avg_corr > 0.7:
            print("PRIMARY SUSPECT: High cross-brand correlation suggests a")
            print("denominator issue. Check sample sizes and Q2 response rates.")
        else:
            print("No single clear cause identified. Review individual checks above.")


if __name__ == "__main__":
    run_diagnostics()
