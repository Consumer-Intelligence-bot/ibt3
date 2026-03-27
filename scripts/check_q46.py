"""
Diagnostic: check Q46 data in Power BI OtherData table.

Usage: python3 scripts/check_q46.py
  - Will prompt for device flow login
  - Then queries Q46 rows and reports what it finds
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import msal
import pandas as pd
import requests

TENANT_ID = "21c877f6-eb38-45b3-82dd-a27ccad676ce"
CLIENT_ID = "9cd99ce2-4c31-46e0-bb7c-eeb8e12e73d6"
SCOPE = ["https://analysis.windows.net/powerbi/api/Dataset.Read.All"]
WORKSPACE_ID = "1c6e2798-9b81-4643-82a2-791780138db3"
DATASET_ID = "e15497a6-e022-45b3-80c3-80a5c0657ff5"  # Motor

TOKEN_FILE = os.path.expanduser("~/.ibt3/token.json")


def get_token():
    """Get a valid token, using cache or device flow."""
    if os.path.exists(TOKEN_FILE):
        data = json.load(open(TOKEN_FILE))
        if data.get("expires_at", 0) - time.time() > 300:
            print("Using cached token.")
            return data["access_token"]

    print("Token expired or missing. Starting device flow...")
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    flow = app.initiate_device_flow(scopes=SCOPE)
    print(f"\n  Go to: https://microsoft.com/devicelogin")
    print(f"  Enter code: {flow['user_code']}\n")
    token = app.acquire_token_by_device_flow(flow)
    if "access_token" not in token:
        print(f"Auth failed: {token.get('error_description', 'unknown')}")
        sys.exit(1)

    expires_in = token.get("expires_in", 3600)
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        json.dump({"access_token": token["access_token"],
                    "expires_at": time.time() + expires_in}, f)
    os.chmod(TOKEN_FILE, 0o600)
    print("Token saved.")
    return token["access_token"]


def run_dax(token, dax):
    """Execute DAX query."""
    url = (f"https://api.powerbi.com/v1.0/myorg/groups/{WORKSPACE_ID}"
           f"/datasets/{DATASET_ID}/executeQueries")
    r = requests.post(url, headers={"Authorization": f"Bearer {token}"},
                      json={"queries": [{"query": dax}], "serializerSettings": {"includeNulls": True}})
    if r.status_code != 200:
        print(f"DAX error {r.status_code}: {r.text[:500]}")
        return pd.DataFrame()
    data = r.json()
    rows = data["results"][0]["tables"][0].get("rows", [])
    return pd.DataFrame(rows) if rows else pd.DataFrame()


def main():
    token = get_token()

    # 1. Find the OtherData table name
    print("\n=== Discovering tables ===")
    df_tables = run_dax(token, "EVALUATE INFO.TABLES()")
    if not df_tables.empty:
        names = df_tables["[Name]"].tolist() if "[Name]" in df_tables.columns else []
        other_candidates = [n for n in names if "other" in n.lower()]
        print(f"  All tables: {names}")
        print(f"  OtherData candidates: {other_candidates}")
    else:
        print("  Could not discover tables")
        other_candidates = ["OtherData"]

    other_table = other_candidates[0] if other_candidates else "OtherData"

    # 2. Check columns on the OtherData table
    print(f"\n=== Columns on '{other_table}' ===")
    df_cols = run_dax(token, "EVALUATE INFO.COLUMNS()")
    if not df_cols.empty:
        tbl_cols = df_cols[df_cols["[TableName]"] == other_table]["[Name]"].tolist() if "[TableName]" in df_cols.columns else []
        print(f"  Columns: {tbl_cols}")
    else:
        tbl_cols = []

    # 3. Check if Q46 exists in the table
    print(f"\n=== Q46 rows in '{other_table}' ===")
    dax = f"""
        EVALUATE
        TOPN(20,
            FILTER('{other_table}', '{other_table}'[QuestionNumber] = "Q46")
        )
    """
    df_q46 = run_dax(token, dax)
    if df_q46.empty:
        print("  NO Q46 rows found!")

        # Try Q46 with different casings/formats
        for variant in ["q46", "Q46 ", "Q46a", "Q46b"]:
            dax2 = f"""
                EVALUATE
                TOPN(5,
                    FILTER('{other_table}', '{other_table}'[QuestionNumber] = "{variant}")
                )
            """
            df_v = run_dax(token, dax2)
            if not df_v.empty:
                print(f"  Found rows with QuestionNumber = '{variant}'!")
                print(df_v.head().to_string())

        # Check what question numbers exist near Q46
        print("\n=== Question numbers near Q46 ===")
        dax3 = f"""
            EVALUATE
            DISTINCT(
                SELECTCOLUMNS(
                    FILTER('{other_table}',
                        LEFT('{other_table}'[QuestionNumber], 3) = "Q46"
                        || LEFT('{other_table}'[QuestionNumber], 3) = "Q45"
                        || LEFT('{other_table}'[QuestionNumber], 3) = "Q47"
                    ),
                    "QN", '{other_table}'[QuestionNumber]
                )
            )
            ORDER BY [QN]
        """
        df_near = run_dax(token, dax3)
        if not df_near.empty:
            print(f"  Found: {df_near.iloc[:, 0].tolist()}")
        else:
            print("  No Q45/Q46/Q47 variants found")
    else:
        print(f"  Found {len(df_q46)} Q46 rows!")
        print(f"  Columns: {df_q46.columns.tolist()}")
        print(df_q46.head(10).to_string())

        # Check Subject column
        if any("Subject" in c for c in df_q46.columns):
            subj_col = [c for c in df_q46.columns if "Subject" in c][0]
            print(f"\n  Subject values: {df_q46[subj_col].unique().tolist()}")
            print(f"  Subject null count: {df_q46[subj_col].isna().sum()}/{len(df_q46)}")
        else:
            print("\n  WARNING: No Subject column in results!")

    # 4. Count total Q46 rows
    print(f"\n=== Q46 total row count ===")
    dax_count = f"""
        EVALUATE
        ROW("count",
            COUNTROWS(FILTER('{other_table}', '{other_table}'[QuestionNumber] = "Q46"))
        )
    """
    df_count = run_dax(token, dax_count)
    if not df_count.empty:
        print(f"  Total Q46 rows: {df_count.iloc[0, 0]}")


if __name__ == "__main__":
    main()
