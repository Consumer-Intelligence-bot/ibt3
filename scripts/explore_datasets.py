"""
Explore Power BI Motor and Home datasets — discover tables, columns, row counts,
sample values, and question data structure. Writes findings to docs/DATASET_SCHEMA.md.

Usage:
    cd /mnt/c/users/ianch/ibt3
    python scripts/explore_datasets.py

Requires a valid MSAL token in ~/.ibt3/token.json (run the Streamlit app
once first to authenticate, then run this within the token's lifetime).
"""

import json
import os
import re
import sys
import time
from pathlib import Path

import msal
import pandas as pd
import requests

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lib.config import (
    TENANT_ID, CLIENT_ID, SCOPE,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
)

# ---------------------------------------------------------------------------
# Auth — reuse saved token or do device flow
# ---------------------------------------------------------------------------

_TOKEN_FILE = Path.home() / ".ibt3" / "token.json"


def get_token() -> str:
    """Load saved token or run MSAL device flow."""
    if _TOKEN_FILE.exists():
        try:
            data = json.loads(_TOKEN_FILE.read_text())
            if data.get("expires_at", 0) > time.time() + 300:
                print("  Using cached token from ~/.ibt3/token.json")
                return data["access_token"]
        except (json.JSONDecodeError, KeyError):
            pass

    print("  No valid cached token. Starting MSAL device flow...")
    app = msal.PublicClientApplication(
        CLIENT_ID,
        authority=f"https://login.microsoftonline.com/{TENANT_ID}",
    )
    flow = app.initiate_device_flow(scopes=SCOPE)
    print(f"\n  >>> Go to https://microsoft.com/devicelogin")
    print(f"  >>> Enter code: {flow['user_code']}")
    print(f"  >>> Waiting for authentication...\n")
    token = app.acquire_token_by_device_flow(flow)
    if "access_token" not in token:
        print(f"  ERROR: Authentication failed: {token.get('error_description', 'unknown')}")
        sys.exit(1)

    # Save token
    expires_in = token.get("expires_in", 3600)
    _TOKEN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _TOKEN_FILE.write_text(json.dumps({
        "access_token": token["access_token"],
        "expires_at": time.time() + expires_in,
    }))
    print("  Authenticated and token saved.")
    return token["access_token"]


# ---------------------------------------------------------------------------
# DAX helpers (standalone, no Streamlit dependency)
# ---------------------------------------------------------------------------

def run_dax(token: str, dax: str, workspace_id: str, dataset_id: str) -> pd.DataFrame:
    """Execute a DAX query and return DataFrame."""
    url = (
        f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
        f"/datasets/{dataset_id}/executeQueries"
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
        return pd.DataFrame()
    body = r.json()
    if "error" in body:
        return pd.DataFrame()
    try:
        rows = body["results"][0]["tables"][0].get("rows", [])
    except (KeyError, IndexError):
        return pd.DataFrame()
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows)
    df.columns = [c.split("[")[-1].replace("]", "") for c in df.columns]
    return df


def discover_tables(token, workspace_id, dataset_id):
    """Return list of table names."""
    dax = "EVALUATE INFO.TABLES()"
    df = run_dax(token, dax, workspace_id, dataset_id)
    if not df.empty:
        name_col = [c for c in df.columns if c.lower() == "name"]
        if name_col:
            return df[name_col[0]].tolist()
        return df.iloc[:, 0].tolist()

    # Probe known candidates
    candidates = ["MainData", "MainData_Motor", "MainData_Home",
                   "AllOtherData", "AllOtherData_Motor", "AllOtherData_Home"]
    found = []
    for name in candidates:
        dax_test = f"EVALUATE TOPN(0, '{name}')"
        r = requests.post(
            f"https://api.powerbi.com/v1.0/myorg/groups/{workspace_id}"
            f"/datasets/{dataset_id}/executeQueries",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            json={"queries": [{"query": dax_test}], "serializerSettings": {"includeNulls": True}},
        )
        if r.status_code == 200 and "error" not in r.json():
            found.append(name)
    return found


def discover_columns(token, table_name, workspace_id, dataset_id):
    """Return sorted list of column names for a table."""
    dax = f"EVALUATE TOPN(1, '{table_name}')"
    df = run_dax(token, dax, workspace_id, dataset_id)
    if not df.empty:
        return sorted(df.columns.tolist())

    # Fallback: INFO.COLUMNS()
    dax2 = "EVALUATE INFO.COLUMNS()"
    df2 = run_dax(token, dax2, workspace_id, dataset_id)
    if not df2.empty:
        name_col = [c for c in df2.columns if c.lower() == "explicitname"]
        table_col = [c for c in df2.columns if c.lower() == "tablename"]
        if name_col and table_col:
            mask = df2[table_col[0]].astype(str) == table_name
            return sorted(df2.loc[mask, name_col[0]].tolist())
    return []


# ---------------------------------------------------------------------------
# Main exploration
# ---------------------------------------------------------------------------

DATASETS = {
    "Motor": {"workspace": MOTOR_WORKSPACE_ID, "dataset": MOTOR_DATASET_ID},
    "Home": {"workspace": HOME_WORKSPACE_ID, "dataset": HOME_DATASET_ID},
}


def explore_dataset(token, name, workspace_id, dataset_id):
    """Explore a single dataset and return structured info."""
    print(f"\n{'='*72}")
    print(f"  DATASET: {name}")
    print(f"  Workspace: {workspace_id}")
    print(f"  Dataset:   {dataset_id}")
    print(f"{'='*72}")

    tables = discover_tables(token, workspace_id, dataset_id)
    if not tables:
        print("  (no tables found)")
        return {"name": name, "tables": []}

    print(f"\n  Tables found: {tables}")
    dataset_info = {"name": name, "tables": []}

    for table_name in tables:
        print(f"\n  --- Table: {table_name} ---")
        table_info = {"table_name": table_name}

        # Columns
        columns = discover_columns(token, table_name, workspace_id, dataset_id)
        table_info["columns"] = columns
        print(f"  Columns ({len(columns)}): {columns}")

        # Row count
        df_count = run_dax(token, f"EVALUATE ROW(\"cnt\", COUNTROWS('{table_name}'))",
                           workspace_id, dataset_id)
        row_count = int(df_count.iloc[0, 0]) if not df_count.empty else None
        table_info["row_count"] = row_count
        print(f"  Row count: {row_count:,}" if row_count else "  Row count: unknown")

        # Sample rows
        df_sample = run_dax(token, f"EVALUATE TOPN(3, '{table_name}')",
                            workspace_id, dataset_id)
        if not df_sample.empty:
            table_info["sample_data"] = df_sample.to_dict(orient="records")
            print(f"  Sample (3 rows):")
            for i, row in df_sample.iterrows():
                non_null = {k: v for k, v in row.items() if pd.notna(v) and str(v).strip() != ""}
                print(f"    {non_null}")
        else:
            table_info["sample_data"] = []

        # Distinct values for key columns
        key_cols = [c for c in columns if c in (
            "QuestionNumber", "Subject", "Ranking", "Scale", "Answer",
            "CurrentCompany", "PreRenewalCompany", "PreviousCompany",
            "Shoppers", "Switchers", "Retained", "Claimants",
            "Region", "Age Group", "Gender", "Employment status",
            "RenewalYearMonth", "SurveyYearMonth",
            "Did you use a PCW for shopping",
            "Renewal premium change", "Renewal premium change combined",
        )]

        col_stats = {}
        for col in key_cols:
            dax_vals = f"""
                EVALUATE
                TOPN(50,
                    SUMMARIZE('{table_name}', '{table_name}'[{col}]),
                    '{table_name}'[{col}], ASC
                )
            """
            df_vals = run_dax(token, dax_vals, workspace_id, dataset_id)

            dax_nd = f"EVALUATE ROW(\"n\", DISTINCTCOUNT('{table_name}'[{col}]))"
            df_nd = run_dax(token, dax_nd, workspace_id, dataset_id)

            if not df_vals.empty:
                vals = df_vals.iloc[:, 0].dropna().astype(str).tolist()
                n_distinct = int(df_nd.iloc[0, 0]) if not df_nd.empty else len(vals)
                col_stats[col] = {"n_distinct": n_distinct, "sample_values": vals[:50]}
                print(f"  Column '{col}': {n_distinct} distinct — {vals[:10]}")

        table_info["col_stats"] = col_stats

        # Question structure analysis (for tables with QuestionNumber)
        if "QuestionNumber" in columns:
            print(f"\n  Question structure:")
            dax_qs = f"""
                EVALUATE
                ADDCOLUMNS(
                    SUMMARIZE('{table_name}', '{table_name}'[QuestionNumber]),
                    "RowCount", CALCULATE(COUNTROWS('{table_name}'))
                )
                ORDER BY '{table_name}'[QuestionNumber] ASC
            """
            df_qs = run_dax(token, dax_qs, workspace_id, dataset_id)
            if not df_qs.empty:
                q_counts = {}
                for _, qrow in df_qs.iterrows():
                    q = str(qrow.iloc[0])
                    cnt = int(qrow.iloc[1]) if len(qrow) > 1 else 0
                    q_counts[q] = cnt
                    print(f"    {q}: {cnt:,} rows")
                table_info["question_counts"] = q_counts

            # Sample a few questions to see shape
            sample_qs = ["Q2", "Q4", "Q7", "Q8", "Q15", "Q18", "Q31", "Q39",
                        "Q40a", "Q40b", "Q43", "Q46", "Q47", "Q48", "Q52", "Q53"]
            q_samples = {}
            for sq in sample_qs:
                dax_sq = f"""
                    EVALUATE
                    TOPN(5,
                        FILTER('{table_name}', '{table_name}'[QuestionNumber] = "{sq}")
                    )
                """
                df_sq = run_dax(token, dax_sq, workspace_id, dataset_id)
                if not df_sq.empty:
                    q_samples[sq] = df_sq.to_dict(orient="records")
                    print(f"\n    Sample for {sq}:")
                    for _, r in df_sq.iterrows():
                        non_null = {k: v for k, v in r.items()
                                   if pd.notna(v) and str(v).strip() != ""}
                        print(f"      {non_null}")

            table_info["question_samples"] = q_samples

        dataset_info["tables"].append(table_info)

    return dataset_info


def build_markdown(all_data, questions_ref):
    """Build the DATASET_SCHEMA.md content."""
    lines = [
        "# Power BI Dataset Schema — Motor & Home",
        "",
        "_Auto-generated by `scripts/explore_datasets.py`_",
        "",
        "## Purpose",
        "",
        "Documents the current table structure in both Motor and Home Power BI",
        "semantic models to inform the migration to a one-record-per-respondent",
        "database schema.",
        "",
        "---",
        "",
    ]

    for ds_name, ds_info in all_data.items():
        lines.append(f"## {ds_name} Dataset")
        lines.append("")

        for tbl in ds_info.get("tables", []):
            lines.append(f"### `{tbl['table_name']}`")
            lines.append("")
            if tbl.get("row_count") is not None:
                lines.append(f"**Row count:** {tbl['row_count']:,}")
                lines.append("")

            # Columns table
            lines.append("| Column | Distinct Values | Sample Values |")
            lines.append("|--------|----------------|---------------|")
            for col in tbl.get("columns", []):
                stats = tbl.get("col_stats", {}).get(col, {})
                n_d = stats.get("n_distinct", "—")
                samples = stats.get("sample_values", [])
                sample_str = ", ".join(str(s)[:30] for s in samples[:5])
                if len(samples) > 5:
                    sample_str += ", ..."
                lines.append(f"| `{col}` | {n_d} | {sample_str} |")
            lines.append("")

            # Sample rows
            if tbl.get("sample_data"):
                lines.append("<details>")
                lines.append("<summary>Sample rows</summary>")
                lines.append("")
                lines.append("```json")
                lines.append(json.dumps(tbl["sample_data"], indent=2, default=str))
                lines.append("```")
                lines.append("</details>")
                lines.append("")

            # Question counts
            if tbl.get("question_counts"):
                lines.append("**Question row counts:**")
                lines.append("")
                lines.append("| Question | Rows |")
                lines.append("|----------|------|")
                for q, cnt in sorted(tbl["question_counts"].items(),
                                     key=lambda x: (int(re.search(r'\d+', x[0]).group())
                                                    if re.search(r'\d+', x[0]) else 0, x[0])):
                    lines.append(f"| `{q}` | {cnt:,} |")
                lines.append("")

            # Question samples
            if tbl.get("question_samples"):
                lines.append("<details>")
                lines.append("<summary>Question data samples</summary>")
                lines.append("")
                for sq, samples in sorted(tbl["question_samples"].items()):
                    lines.append(f"**{sq}:**")
                    lines.append("```json")
                    lines.append(json.dumps(samples, indent=2, default=str))
                    lines.append("```")
                    lines.append("")
                lines.append("</details>")
                lines.append("")

        lines.append("---")
        lines.append("")

    # Question reference
    lines.append("## Question Reference (from IBT Motor questionnaire)")
    lines.append("")
    lines.append("| Question | Text | Type |")
    lines.append("|----------|------|------|")
    for q in sorted(questions_ref.keys(),
                    key=lambda x: (int(re.search(r'\d+', x).group())
                                   if re.search(r'\d+', x) else 0, x)):
        qinfo = questions_ref[q]
        text_short = qinfo["text"][:100].replace("|", "/").replace("\n", " ")
        lines.append(f"| `{q}` | {text_short} | {qinfo['type']} |")
    lines.append("")

    # Migration notes
    lines.append("## Migration Notes: One-Record-Per-Respondent Schema")
    lines.append("")
    lines.append("### Current Architecture")
    lines.append("")
    lines.append("- **MainData**: One row per respondent — profile/demographic fields")
    lines.append("- **AllOtherData**: EAV (Entity-Attribute-Value) — multiple rows per respondent,")
    lines.append("  one per (QuestionNumber, Answer/Subject/Ranking/Scale) combination")
    lines.append("")
    lines.append("### Target Architecture")
    lines.append("")
    lines.append("One wide table with one row per respondent. All question answers become columns.")
    lines.append("")
    lines.append("### Question Pivot Strategy")
    lines.append("")
    lines.append("| Type | Example Questions | Column Strategy |")
    lines.append("|------|------------------|-----------------|")
    lines.append("| **Single-code** (one answer) | Q4, Q7, Q15, Q20a, Q20b, Q21, Q30, Q34a, Q34b, Q39, Q40, Q41, Q42, Q43, Q43a | `Q{n}` — one column, value = Answer |")
    lines.append("| **Multi-code** (multiple answers) | Q2, Q5b, Q9b, Q10, Q11, Q13b, Q27, Q28, Q31, Q45, Q54 | `Q{n}_{answer}` — boolean column per option, OR `Q{n}` — JSON array |")
    lines.append("| **Ranked** (ordered selections) | Q8, Q18, Q19, Q33, Q44, Q55 | `Q{n}_rank{i}` — one column per rank position |")
    lines.append("| **Grid/scale** (rate sub-items) | Q46, Q53 | `Q{n}_{subject}` — one column per sub-item, value = Scale |")
    lines.append("| **NPS/satisfaction** (0-10 or 1-5) | Q11d, Q29, Q40a, Q40b, Q47, Q48, Q52 | `Q{n}` — one numeric column |")
    lines.append("")
    lines.append("### Key Decisions Needed")
    lines.append("")
    lines.append("1. **Multi-code storage**: Boolean columns per option vs JSON array?")
    lines.append("   Boolean is easier to query but creates many sparse columns.")
    lines.append("2. **Ranked questions**: How many rank positions to keep? (Top 3? Top 5?)")
    lines.append("3. **Grid questions**: Subject labels vary — need canonical naming.")
    lines.append("4. **Cross-product consistency**: Are Motor and Home questions identical?")
    lines.append("   If not, which columns are product-specific?")
    lines.append("")

    return "\n".join(lines)


def parse_questionnaire():
    """Parse questions from the docx questionnaire."""
    try:
        from docx import Document
    except ImportError:
        print("  WARNING: python-docx not installed, skipping questionnaire parsing")
        return {}

    doc_path = "/mnt/c/Users/ianch/OneDrive - CONSUMER INTELLIGENCE LTD/IBT Motor (REDUCED) -V2.docx"
    if not os.path.exists(doc_path):
        print(f"  WARNING: Questionnaire not found at {doc_path}")
        return {}

    doc = Document(doc_path)
    questions = {}
    current_q = None
    current_text = []
    current_type = ""

    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            continue

        m = re.match(r'^(Q\d+\w?)[\.\s](.+)', text)
        if m:
            if current_q:
                questions[current_q] = {"text": " ".join(current_text), "type": current_type}
            current_q = m.group(1)
            current_text = [m.group(2).strip()]
            current_type = ""
        elif current_q:
            if text.startswith(("SINGLE CODE", "MULTICODE", "OE ", "NUM ", "SCALE", "GRID")):
                current_type = text.split("[")[0].strip()

    if current_q:
        questions[current_q] = {"text": " ".join(current_text), "type": current_type}

    return questions


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("Power BI Dataset Explorer")
    print("=" * 40)

    token = get_token()

    all_data = {}
    for ds_name, ds_config in DATASETS.items():
        print(f"\nExploring {ds_name}...")
        all_data[ds_name] = explore_dataset(
            token, ds_name, ds_config["workspace"], ds_config["dataset"]
        )

    # Parse questionnaire
    print("\nParsing questionnaire...")
    questions_ref = parse_questionnaire()
    print(f"  Found {len(questions_ref)} questions")

    # Write markdown
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
    os.makedirs(output_dir, exist_ok=True)

    md_content = build_markdown(all_data, questions_ref)
    md_path = os.path.join(output_dir, "DATASET_SCHEMA.md")
    with open(md_path, "w") as f:
        f.write(md_content)
    print(f"\nMarkdown report written to: {md_path}")

    # Save raw JSON
    json_path = os.path.join(output_dir, "DATASET_SCHEMA.json")
    with open(json_path, "w") as f:
        json.dump(all_data, f, indent=2, default=str)
    print(f"Raw JSON data written to: {json_path}")

    print("\nDone.")
