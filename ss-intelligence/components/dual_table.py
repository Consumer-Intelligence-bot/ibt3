"""
Dual comparison table: insurer vs market reason rankings.
"""
from dash import html
from dash import dash_table
import dash_bootstrap_components as dbc

from config import CI_MAGENTA


def dual_table(
    insurer_reasons: list[dict] | None,
    market_reasons: list[dict] | None,
    title_left: str = "Your Customers",
    title_right: str = "Market",
    id_prefix: str = "",
) -> dbc.Row:
    """
    Side-by-side reason tables. Highlight insurer differences in CI Magenta.
    """
    def _table_row(r, is_insurer, rank):
        pct = r.get("rank1_pct", r.get("mention_pct", 0)) * 100
        return {
            "Rank": rank + 1,
            "Reason": r.get("reason", ""),
            "Pct": "%.1f%%" % (pct,),
        }

    left_data = []
    if insurer_reasons:
        for i, r in enumerate(insurer_reasons[:5]):
            left_data.append(_table_row(r, True, i))

    right_data = []
    if market_reasons:
        for i, r in enumerate(market_reasons[:5]):
            right_data.append(_table_row(r, False, i))

    left_col = dash_table.DataTable(
        id=id_prefix + "-insurer-table",
        columns=[{"name": "Rank", "id": "Rank"}, {"name": "Reason", "id": "Reason"}, {"name": "%", "id": "Pct"}],
        data=left_data,
        page_size=5,
        style_cell={"textAlign": "left"},
        style_header={"fontWeight": "bold"},
    ) if left_data else html.P("No data", className="text-muted")

    right_col = dash_table.DataTable(
        id=id_prefix + "-market-table",
        columns=[{"name": "Rank", "id": "Rank"}, {"name": "Reason", "id": "Reason"}, {"name": "%", "id": "Pct"}],
        data=right_data,
        page_size=5,
        style_cell={"textAlign": "left"},
        style_header={"fontWeight": "bold"},
    ) if right_data else html.P("No data", className="text-muted")

    return dbc.Row(
        [
            dbc.Col(
                [html.H6(title_left, className="mb-2"), left_col],
                md=6,
                className="border-end",
            ),
            dbc.Col(
                [html.H6(title_right, className="mb-2"), right_col],
                md=6,
            ),
        ],
        className="mb-3",
    )
