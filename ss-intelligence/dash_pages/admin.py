"""
Page 4: Admin / Governance (Spec Section 8).

Internal-only page. Hidden from navigation. Accessed via /admin URL only.
Data quality monitoring, confidence threshold management, parameter audit log.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import json
from datetime import datetime, timezone

import dash
import dash_bootstrap_components as dbc
import pandas as pd
import plotly.graph_objects as go
from dash import Input, Output, State, callback, dash_table, dcc, html

from analytics.bayesian import bayesian_smooth_rate
from analytics.confidence import MetricType, assess_confidence, calc_ci_width
from analytics.demographics import apply_filters
from analytics.flows import calc_flow_matrix
from components.branded_chart import create_branded_figure
from components.ci_card import ci_stat_card
from config import (
    CI_GREEN,
    CI_GREY,
    CI_RED,
    CI_WIDTH_INDICATIVE_AWARENESS,
    CI_WIDTH_INDICATIVE_RATE,
    CI_WIDTH_INDICATIVE_REASON,
    CI_WIDTH_PUBLISHABLE_AWARENESS,
    CI_WIDTH_PUBLISHABLE_RATE,
    CI_WIDTH_PUBLISHABLE_REASON,
    CI_YELLOW,
    CONFIDENCE_LEVEL,
    MARKET_CI_ALERT_THRESHOLD,
    MIN_BASE_FLOW_CELL,
    MIN_BASE_PUBLISHABLE,
    NPS_MIN_N,
    PRIOR_STRENGTH,
    SYSTEM_FLOOR_N,
    TREND_NOISE_THRESHOLD,
)
from data.loader import PROCESSED_DIR
from shared import DF_MOTOR, DF_QUESTIONS, DIMENSIONS, format_year_month

dash.register_page(__name__, path="/admin", name="Admin")

_CHANGELOG_PATH = PROCESSED_DIR / "param_changelog.json"


def _load_changelog() -> list[dict]:
    if _CHANGELOG_PATH.exists():
        return json.loads(_CHANGELOG_PATH.read_text(encoding="utf-8"))
    return []


def _save_changelog(entries: list[dict]):
    _CHANGELOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CHANGELOG_PATH.write_text(json.dumps(entries, indent=2, default=str), encoding="utf-8")


def _default_thresholds() -> list[dict]:
    return [
        {"metric_type": "Retention / Shopping / Switching", "name": "CI Width: Publishable", "value": CI_WIDTH_PUBLISHABLE_RATE, "description": "Max 95% posterior CI width for client output"},
        {"metric_type": "Retention / Shopping / Switching", "name": "CI Width: Indicative", "value": CI_WIDTH_INDICATIVE_RATE, "description": "Max CI width for internal indicative results"},
        {"metric_type": "Reason Percentages", "name": "CI Width: Publishable", "value": CI_WIDTH_PUBLISHABLE_REASON, "description": "Reason %s are noisier; wider threshold"},
        {"metric_type": "Reason Percentages", "name": "CI Width: Indicative", "value": CI_WIDTH_INDICATIVE_REASON, "description": "Internal indicative for reason analysis"},
        {"metric_type": "Awareness Rates", "name": "CI Width: Publishable", "value": CI_WIDTH_PUBLISHABLE_AWARENESS, "description": "Same as binary rate metrics at insurer level"},
        {"metric_type": "Awareness Rates", "name": "CI Width: Indicative", "value": CI_WIDTH_INDICATIVE_AWARENESS, "description": "Internal indicative for awareness"},
        {"metric_type": "NPS (Q40b)", "name": "Minimum n", "value": NPS_MIN_N, "description": "NPS uses n floor, not CI width"},
        {"metric_type": "All metrics", "name": "Absolute n floor", "value": SYSTEM_FLOOR_N, "description": "Floor below which no result shown (hardcoded)"},
    ]


def _data_freshness_days(df: pd.DataFrame) -> int | None:
    if "RenewalYearMonth" not in df.columns:
        return None
    max_ym = df["RenewalYearMonth"].max()
    if pd.isna(max_ym):
        return None
    y, m = int(max_ym // 100), int(max_ym % 100)
    latest = datetime(y, m, 1, tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - latest).days


def _calc_insurer_quality(df: pd.DataFrame) -> pd.DataFrame:
    """One row per insurer with confidence metrics."""
    insurers = df["CurrentCompany"].dropna().unique()
    rows = []
    market_ret = df["IsRetained"].mean() if "IsRetained" in df.columns else 0.5

    for ins in sorted(insurers):
        ins_df = df[df["CurrentCompany"] == ins]
        n = len(ins_df)
        if n == 0:
            continue
        retained = ins_df["IsRetained"].sum() if "IsRetained" in ins_df.columns else 0
        rate = retained / n if n > 0 else 0

        smoothed = bayesian_smooth_rate(int(retained), n, market_ret)
        ci_w = (smoothed["ci_upper"] - smoothed["ci_lower"]) * 100

        conf = assess_confidence(n, rate, MetricType.RATE, posterior_ci_width=ci_w)

        # QC: Q4=Q39 flag
        qc_flags = ""
        if not DF_QUESTIONS.empty:
            switchers = ins_df[ins_df["IsSwitcher"]]["UniqueID"]
            if len(switchers) > 0:
                q4_vals = DF_QUESTIONS[
                    (DF_QUESTIONS["QuestionNumber"] == "Q4") & DF_QUESTIONS["UniqueID"].isin(switchers)
                ].set_index("UniqueID")["Answer"]
                q39_vals = DF_QUESTIONS[
                    (DF_QUESTIONS["QuestionNumber"] == "Q39") & DF_QUESTIONS["UniqueID"].isin(switchers)
                ].set_index("UniqueID")["Answer"]
                common = q4_vals.index.intersection(q39_vals.index)
                flags = (q4_vals.loc[common] == q39_vals.loc[common]).sum()
                if flags > 0:
                    qc_flags = f"Q4=Q39: {flags}"

        rows.append({
            "Insurer": ins,
            "n": n,
            "CI Width (pp)": round(ci_w, 1),
            "Confidence": conf.label.value,
            "Weight": f"{smoothed['weight']:.0%}",
            "QC Flags": qc_flags,
        })

    return pd.DataFrame(rows)


def _qc_flags_by_month(df: pd.DataFrame) -> pd.DataFrame:
    """Q4=Q39 flag count and rate per month."""
    if DF_QUESTIONS.empty or "RenewalYearMonth" not in df.columns:
        return pd.DataFrame()

    switchers = df[df["IsSwitcher"]][["UniqueID", "RenewalYearMonth"]].copy()
    if switchers.empty:
        return pd.DataFrame()

    q4 = DF_QUESTIONS[DF_QUESTIONS["QuestionNumber"] == "Q4"][["UniqueID", "Answer"]].rename(columns={"Answer": "Q4"})
    q39 = DF_QUESTIONS[DF_QUESTIONS["QuestionNumber"] == "Q39"][["UniqueID", "Answer"]].rename(columns={"Answer": "Q39"})

    merged = switchers.merge(q4, on="UniqueID", how="left").merge(q39, on="UniqueID", how="left")
    merged["flagged"] = merged["Q4"] == merged["Q39"]

    by_month = merged.groupby("RenewalYearMonth").agg(
        total=("UniqueID", "count"),
        flagged=("flagged", "sum"),
    ).reset_index()
    by_month["flag_rate"] = by_month["flagged"] / by_month["total"]
    return by_month


def _run_data_validation(df: pd.DataFrame) -> list[dict]:
    results = []
    if df is None or df.empty:
        return [{"check": "Data", "status": "FAIL", "message": "No data"}]

    dup = df["UniqueID"].duplicated().sum() if "UniqueID" in df.columns else 0
    results.append({"check": "No duplicate IDs", "status": "PASS" if dup == 0 else "FAIL", "message": f"{dup} duplicates" if dup else "OK"})

    for col in ("AgeBand", "Region"):
        if col in df.columns:
            missing = df[col].isna().sum()
            results.append({"check": f"{col} complete", "status": "PASS" if missing == 0 else "WARN", "message": f"{missing} missing" if missing else "OK"})

    flow_mat = calc_flow_matrix(df)
    if len(flow_mat) > 0:
        total_out = flow_mat.sum().sum()
        total_in = flow_mat.sum(axis=1).sum()
        balanced = abs(total_out - total_in) < 1
        results.append({"check": "Flow balance", "status": "PASS" if balanced else "FAIL", "message": "OK" if balanced else f"Out={total_out:.0f} In={total_in:.0f}"})

    return results


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[
            html.H1("Admin / Governance"),
            html.P("Internal page — not visible to clients", className="text-muted small"),
        ]),

        # Summary KPIs
        dbc.Row(id="admin-kpis", className="mb-4"),

        # Confidence threshold table + change log
        dbc.Row([
            dbc.Col([
                html.H2("Confidence Thresholds"),
                html.Div(id="admin-threshold-table"),
                dbc.InputGroup([
                    dbc.Input(id="admin-rationale-input", placeholder="Rationale for change (required)", type="text"),
                    dbc.Button("Save Changes", id="admin-save-btn", color="primary", size="sm"),
                ], className="mt-2"),
                html.Div(id="admin-save-feedback", className="mt-1"),
            ], md=6),
            dbc.Col([
                html.H2("Parameter Change Log"),
                html.Div(id="admin-changelog"),
            ], md=6),
        ], className="mb-4"),

        # Governance parameters (Spec 8.6)
        dbc.Row([
            dbc.Col([
                html.H2("Governance Parameters"),
                html.Div(id="admin-params-display"),
            ], md=12),
        ], className="mb-4"),

        # Market confidence + QC flags
        dbc.Row([
            dbc.Col([
                html.H2("Market-Level Confidence"),
                dbc.Row(id="admin-market-ci", className="mb-3"),
            ], md=6),
            dbc.Col([
                html.H2("QC Flags: Q4=Q39"),
                html.Div(id="admin-qc-chart"),
            ], md=6),
        ], className="mb-4"),

        # Data distribution + insurer quality + validation
        dbc.Row([
            dbc.Col([
                html.H2("Respondents by Month"),
                html.Div(id="admin-distribution"),
            ], md=6),
            dbc.Col([
                html.H2("Data Validation"),
                html.Div(id="admin-validation"),
            ], md=6),
        ], className="mb-4"),

        dbc.Row([
            dbc.Col([
                html.H2("Insurer Data Quality"),
                html.Div(id="admin-insurer-quality", style={"maxHeight": "500px", "overflowY": "auto"}),
            ], md=12),
        ]),

        dcc.Store(id="admin-threshold-store", data=_default_thresholds()),
    ], fluid=True)


@callback(
    [
        Output("admin-kpis", "children"),
        Output("admin-threshold-table", "children"),
        Output("admin-changelog", "children"),
        Output("admin-params-display", "children"),
        Output("admin-market-ci", "children"),
        Output("admin-qc-chart", "children"),
        Output("admin-distribution", "children"),
        Output("admin-validation", "children"),
        Output("admin-insurer-quality", "children"),
    ],
    [Input("url", "pathname")],
    prevent_initial_call=False,
)
def update_admin(_path):
    total = len(DF_MOTOR)
    insurers = DIMENSIONS["DimInsurer"]["Insurer"].dropna().astype(str).tolist()
    eligible = sum(1 for ins in insurers if len(DF_MOTOR[DF_MOTOR["CurrentCompany"] == ins]) >= MIN_BASE_PUBLISHABLE)
    suppressed = len(insurers) - eligible
    freshness = _data_freshness_days(DF_MOTOR)
    fresh_alert = freshness is not None and freshness > 45

    kpis = [
        dbc.Col(ci_stat_card("Total Respondents", total, fmt="{:,}"), md=3),
        dbc.Col(ci_stat_card("Eligible Insurers", eligible, fmt="{:,}", alert=eligible < 15), md=3),
        dbc.Col(ci_stat_card("Suppressed", suppressed, fmt="{:,}", alert=suppressed > 10), md=3),
        dbc.Col(ci_stat_card(
            "Data Freshness",
            f"{freshness} days" if freshness else "N/A",
            alert=fresh_alert,
            subtitle="Alert: > 45 days" if fresh_alert else None,
        ), md=3),
    ]

    # Threshold table
    thresholds = _default_thresholds()
    threshold_table = dash_table.DataTable(
        id="admin-param-table",
        data=thresholds,
        columns=[
            {"name": "Metric Type", "id": "metric_type", "editable": False},
            {"name": "Threshold", "id": "name", "editable": False},
            {"name": "Value", "id": "value", "editable": True, "type": "numeric"},
            {"name": "Description", "id": "description", "editable": False},
        ],
        style_table={"overflowX": "auto"},
        style_header={"backgroundColor": "#E9EAEB", "fontWeight": 600, "fontSize": "12px"},
        style_cell={"fontSize": "13px", "padding": "8px", "textAlign": "left"},
        style_data_conditional=[
            {"if": {"column_id": "value"}, "backgroundColor": "#FFFDE7"},
        ],
        editable=True,
    )

    # Change log
    log_entries = _load_changelog()
    if log_entries:
        log_df = pd.DataFrame(log_entries[-20:])
        changelog = dash_table.DataTable(
            data=log_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in log_df.columns],
            style_table={"overflowX": "auto", "maxHeight": "300px", "overflowY": "auto"},
            style_header={"backgroundColor": "#E9EAEB", "fontWeight": 600, "fontSize": "11px"},
            style_cell={"fontSize": "12px", "padding": "6px"},
        )
    else:
        changelog = html.P("No parameter changes recorded.", className="text-muted small")

    # Governance parameters — read-only display (Spec 8.6)
    market_ret = DF_MOTOR["IsRetained"].mean() if "IsRetained" in DF_MOTOR.columns else 0.5
    params_table = dbc.Table(
        [
            html.Thead(html.Tr([html.Th("Parameter"), html.Th("Value"), html.Th("Description")])),
            html.Tbody([
                html.Tr([html.Td("Minimum base (publishable)"), html.Td(str(MIN_BASE_PUBLISHABLE)), html.Td("n \u2265 50 for client-facing outputs")]),
                html.Tr([html.Td("Minimum base (indicative)"), html.Td("30"), html.Td("n \u2265 30 for internal review with caveat")]),
                html.Tr([html.Td("Minimum base (flow cell)"), html.Td(str(MIN_BASE_FLOW_CELL)), html.Td("n \u2265 10 for insurer-to-insurer pairs")]),
                html.Tr([html.Td("Bayesian prior strength"), html.Td(str(PRIOR_STRENGTH)), html.Td("Pseudo-observations (one month of small-insurer data)")]),
                html.Tr([html.Td("Bayesian prior mean"), html.Td(f"{market_ret:.1%}"), html.Td("Market average retention rate")]),
                html.Tr([html.Td("Confidence interval"), html.Td(f"{CONFIDENCE_LEVEL:.0%}"), html.Td("Credible interval level")]),
                html.Tr([html.Td("Trend noise threshold"), html.Td(f"{TREND_NOISE_THRESHOLD:.1f}pp"), html.Td("Change must exceed avg CI width of comparison periods")]),
            ]),
        ],
        striped=True, size="sm", className="ci-table",
    )

    # Market-level CI
    from analytics.rates import calc_retention_rate, calc_shopping_rate, calc_switching_rate
    market_metrics = []
    for label, calc_fn in [("Retention", calc_retention_rate), ("Shopping", calc_shopping_rate), ("Switching", calc_switching_rate)]:
        rate = calc_fn(DF_MOTOR)
        ci_w = calc_ci_width(total, rate) if rate else None
        alert = ci_w is not None and ci_w > MARKET_CI_ALERT_THRESHOLD
        market_metrics.append(dbc.Col(ci_stat_card(
            f"Market {label} CI",
            f"{ci_w:.2f}pp" if ci_w else "N/A",
            alert=alert,
            subtitle=f"Alert: > {MARKET_CI_ALERT_THRESHOLD}pp" if alert else None,
        ), md=4))

    # QC flags chart — plot as RATE per month, with 2% threshold (Spec 12.4)
    qc_data = _qc_flags_by_month(DF_MOTOR)
    if not qc_data.empty:
        qc_data["month_label"] = qc_data["RenewalYearMonth"].apply(format_year_month)
        fig_qc = go.Figure()
        fig_qc.add_trace(go.Bar(
            x=qc_data["month_label"],
            y=qc_data["flag_rate"],
            name="Flag Rate",
            marker_color=CI_GREY,
            text=[f"{r:.1%}" for r in qc_data["flag_rate"]],
            textposition="outside",
        ))
        fig_qc.add_hline(y=0.02, line_dash="dash", line_color=CI_RED, annotation_text="2% threshold")
        fig_qc = create_branded_figure(fig_qc, title="")
        fig_qc.update_layout(height=250, margin=dict(t=30), yaxis_tickformat=".1%")
        qc_chart = dcc.Graph(figure=fig_qc, config={"displayModeBar": False})
    else:
        qc_chart = html.P("No QC flag data available.", className="text-muted small")

    # Distribution chart
    by_month = DF_MOTOR.groupby("RenewalYearMonth").size().reset_index(name="count")
    by_month["month_label"] = by_month["RenewalYearMonth"].apply(format_year_month)
    fig_dist = go.Figure(go.Bar(x=by_month["month_label"], y=by_month["count"], marker_color=CI_GREY))
    fig_dist = create_branded_figure(fig_dist, title="")
    fig_dist.update_layout(height=250, margin=dict(t=30))
    dist_div = dcc.Graph(figure=fig_dist, config={"displayModeBar": False})

    # Data validation
    val_results = _run_data_validation(DF_MOTOR)
    val_rows = [
        html.Tr([
            html.Td(r["check"]),
            html.Td(
                r["status"],
                className="text-ci-green" if r["status"] == "PASS" else "text-ci-red" if r["status"] == "FAIL" else "",
                style={"fontWeight": 600},
            ),
            html.Td(r["message"]),
        ])
        for r in val_results
    ]
    val_table = dbc.Table(
        [html.Thead(html.Tr([html.Th("Check"), html.Th("Status"), html.Th("Detail")])), html.Tbody(val_rows)],
        striped=True, size="sm", className="ci-table",
    )

    # Insurer quality table
    quality_df = _calc_insurer_quality(DF_MOTOR)
    if not quality_df.empty:
        quality_table = dash_table.DataTable(
            data=quality_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in quality_df.columns],
            sort_action="native",
            style_table={"overflowX": "auto"},
            style_header={"backgroundColor": "#E9EAEB", "fontWeight": 600, "fontSize": "12px"},
            style_cell={"fontSize": "13px", "padding": "6px"},
            style_data_conditional=[
                {"if": {"filter_query": "{Confidence} = HIGH"}, "color": CI_GREEN},
                {"if": {"filter_query": "{Confidence} = MEDIUM"}, "color": CI_YELLOW},
                {"if": {"filter_query": "{Confidence} = LOW"}, "color": "#E65100"},
                {"if": {"filter_query": "{Confidence} = INSUFFICIENT"}, "color": CI_RED},
                {"if": {"filter_query": "{n} < 50"}, "backgroundColor": "#FFEBEE"},
                {"if": {"filter_query": "{n} < 100 && {n} >= 50"}, "backgroundColor": "#FFFDE7"},
            ],
        )
    else:
        quality_table = html.P("No insurer quality data.", className="text-muted")

    return kpis, threshold_table, changelog, params_table, market_metrics, qc_chart, dist_div, val_table, quality_table


@callback(
    Output("admin-save-feedback", "children"),
    [Input("admin-save-btn", "n_clicks")],
    [State("admin-param-table", "data"), State("admin-rationale-input", "value"), State("admin-threshold-store", "data")],
    prevent_initial_call=True,
)
def save_threshold_changes(n_clicks, table_data, rationale, stored):
    if not rationale or not rationale.strip():
        return dbc.Alert("Rationale is required.", color="warning", duration=3000, className="small")

    changes = []
    for new, old in zip(table_data, stored):
        if new["value"] != old["value"]:
            changes.append({
                "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"),
                "parameter": new["name"],
                "metric_type": new["metric_type"],
                "old_value": old["value"],
                "new_value": new["value"],
                "changed_by": "Admin",
                "rationale": rationale.strip(),
            })

    if not changes:
        return dbc.Alert("No changes detected.", color="info", duration=3000, className="small")

    log = _load_changelog()
    log.extend(changes)
    _save_changelog(log)
    return dbc.Alert(f"{len(changes)} change(s) saved.", color="success", duration=3000, className="small")
