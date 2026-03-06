"""
Page: Headline — Share Through Renewal story page.

Single-page narrative answering: Are we gaining or losing share through
renewal, and why?  Three sections — Outcome, Drivers, Competitive Exchange.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, html

from analytics.demographics import apply_filters
from components.filter_bar import filter_bar
from config import CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, CI_LIGHT_GREY, NEUTRAL_GAP_THRESHOLD
from shared import DF_MOTOR, DF_HOME

dash.register_page(__name__, path="/headline", name="Headline")

FONT = "Verdana, Geneva, sans-serif"


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def _pct(n, d):
    return n / d if d > 0 else 0


def _fmt_pct(val, dp=1):
    if val is None:
        return "—"
    return f"{val * 100:.{dp}f}%"


def _calc_headline_metrics(df_mkt, insurer):
    """Compute all metrics needed for the headline story page."""
    total = len(df_mkt)
    if total == 0:
        return None

    existing = df_mkt[~df_mkt["IsNewToMarket"]]
    new_to_market = df_mkt[df_mkt["IsNewToMarket"]]
    shoppers = existing[existing["IsShopper"]]
    non_shoppers = existing[~existing["IsShopper"]]
    shop_stay = shoppers[shoppers["IsRetained"]]
    shop_switch = shoppers[shoppers["IsSwitcher"]]

    mkt_shop_pct = _pct(len(shoppers), len(existing)) if len(existing) > 0 else 0
    mkt_new_biz_pct = _pct(len(new_to_market), total)
    mkt_shop_stay_pct = _pct(len(shop_stay), len(shoppers)) if len(shoppers) > 0 else 0
    mkt_shop_switch_pct = _pct(len(shop_switch), len(shoppers)) if len(shoppers) > 0 else 0
    mkt_retained_pct = _pct(len(non_shoppers) + len(shop_stay), total)

    if not insurer:
        return None  # Headline page requires an insurer

    ins_existing = existing[existing["PreviousCompany"] == insurer]
    ins_new_biz = new_to_market[new_to_market["CurrentCompany"] == insurer]
    ins_non_shop = ins_existing[~ins_existing["IsShopper"]]
    ins_shoppers = ins_existing[ins_existing["IsShopper"]]
    ins_shop_stay = ins_shoppers[ins_shoppers["IsRetained"]]
    ins_shop_switch = ins_shoppers[ins_shoppers["IsSwitcher"]]
    ins_total = len(ins_existing) + len(ins_new_biz)
    ins_retained = len(ins_non_shop) + len(ins_shop_stay)

    pre_share = _pct(len(ins_existing), total)
    after_count = len(df_mkt[df_mkt["CurrentCompany"] == insurer])
    after_share = _pct(after_count, total)

    # Won from
    switchers_to = df_mkt[
        (df_mkt["IsSwitcher"])
        & (df_mkt["CurrentCompany"] == insurer)
        & (df_mkt["PreviousCompany"] != insurer)
    ]
    total_won = len(switchers_to) + len(ins_new_biz)
    won_counts = {}
    for _, r in switchers_to.iterrows():
        b = r.get("PreviousCompany", "Other")
        won_counts[b] = won_counts.get(b, 0) + 1
    if len(ins_new_biz) > 0:
        won_counts["New to market"] = len(ins_new_biz)
    won_from = sorted(won_counts.items(), key=lambda x: -x[1])[:3]
    won_from = [(b, _pct(c, total_won)) for b, c in won_from] if total_won > 0 else []

    # Lost to
    lost_switchers = df_mkt[
        (df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)
    ]
    lost_counts = {}
    for _, r in lost_switchers.iterrows():
        b = r.get("CurrentCompany", "Other")
        lost_counts[b] = lost_counts.get(b, 0) + 1
    total_lost = len(lost_switchers)
    lost_to = sorted(lost_counts.items(), key=lambda x: -x[1])[:3]
    lost_to = [(b, _pct(c, total_lost)) for b, c in lost_to] if total_lost > 0 else []

    return {
        "insurer": insurer,
        "pre_share": pre_share,
        "after_share": after_share,
        "share_delta": after_share - pre_share,
        "shop_pct": _pct(len(ins_shoppers), len(ins_existing)) if len(ins_existing) > 0 else 0,
        "mkt_shop_pct": mkt_shop_pct,
        "retained_pct": _pct(ins_retained, ins_total) if ins_total > 0 else 0,
        "mkt_retained_pct": mkt_retained_pct,
        "shop_stay_pct": _pct(len(ins_shop_stay), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
        "mkt_shop_stay_pct": mkt_shop_stay_pct,
        "shop_switch_pct": _pct(len(ins_shop_switch), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
        "mkt_shop_switch_pct": mkt_shop_switch_pct,
        "new_biz_pct": _pct(len(ins_new_biz), ins_total) if ins_total > 0 else 0,
        "mkt_new_biz_pct": mkt_new_biz_pct,
        "won_from": won_from,
        "lost_to": lost_to,
        "n": total,
    }


# ---------------------------------------------------------------------------
# Visual helpers
# ---------------------------------------------------------------------------

def _derive_tag(ins_val, mkt_val):
    """Return insight tag: In line, Ahead, or Below."""
    gap_pp = (ins_val - mkt_val) * 100
    if abs(gap_pp) < NEUTRAL_GAP_THRESHOLD:
        return "In line"
    return "Ahead" if gap_pp > 0 else "Below"


def _tag_colour(tag):
    if tag == "Ahead":
        return CI_GREEN
    if tag == "Below":
        return CI_RED
    return CI_GREY


def _share_card(label, value_str, colour, border_top=None):
    """Single KPI card for the outcome section."""
    style = {
        "backgroundColor": "#FFF",
        "borderRadius": 8,
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "padding": "16px 20px",
        "textAlign": "center",
        "fontFamily": FONT,
        "flex": "1 1 200px",
        "maxWidth": 260,
    }
    if border_top:
        style["borderTop"] = f"4px solid {border_top}"

    return html.Div([
        html.Div(label, style={
            "fontSize": 11, "color": "#666", "textTransform": "uppercase",
            "letterSpacing": "0.5px", "marginBottom": 6,
        }),
        html.Div(value_str, style={
            "fontSize": 36, "fontWeight": "bold", "color": colour, "lineHeight": "1.1",
        }),
    ], style=style)


def _comparison_bar(label, ins_val, mkt_val, tag, max_val=1.0):
    """One dumbbell-style comparison row: insurer bar + market marker."""
    ins_pct_width = (ins_val / max_val) * 100 if max_val > 0 else 0
    mkt_pct_width = (mkt_val / max_val) * 100 if max_val > 0 else 0
    tag_col = _tag_colour(tag)

    return html.Div([
        # Label row
        html.Div([
            html.Span(label, style={
                "fontSize": 13, "fontWeight": "bold", "color": "#4D5153",
            }),
            html.Span(tag, style={
                "fontSize": 11, "fontWeight": "bold", "color": tag_col,
                "textTransform": "uppercase", "letterSpacing": "0.5px",
            }),
        ], style={
            "display": "flex", "justifyContent": "space-between",
            "alignItems": "baseline", "marginBottom": 6,
        }),
        # Bar track
        html.Div([
            # Insurer bar
            html.Div(style={
                "position": "absolute", "left": 0, "top": 2, "bottom": 2,
                "width": f"{ins_pct_width:.1f}%",
                "backgroundColor": CI_MAGENTA, "borderRadius": 3,
                "transition": "width 0.3s ease",
            }),
            # Market marker
            html.Div(style={
                "position": "absolute", "left": f"{mkt_pct_width:.1f}%",
                "top": 0, "bottom": 0, "width": 3,
                "backgroundColor": CI_GREY, "borderRadius": 1,
            }),
        ], style={
            "position": "relative", "height": 24,
            "backgroundColor": CI_LIGHT_GREY, "borderRadius": 4,
        }),
        # Value labels
        html.Div([
            html.Span(f"{insurer_label} {_fmt_pct(ins_val)}", style={
                "fontSize": 11, "fontWeight": "bold", "color": CI_MAGENTA,
            }),
            html.Span(f"Market {_fmt_pct(mkt_val)}", style={
                "fontSize": 11, "color": CI_GREY,
            }),
        ], style={
            "display": "flex", "justifyContent": "space-between", "marginTop": 4,
        }),
    ], style={"marginBottom": 16, "fontFamily": FONT})


# Module-level placeholder updated per callback
insurer_label = "Insurer"


def _butterfly_chart(won_from, lost_to, callout=None):
    """Butterfly chart: wins left, losses right, top 3 per side."""
    all_vals = [p for _, p in won_from] + [p for _, p in lost_to]
    max_val = max(all_vals) if all_vals else 0.01

    rows = []
    n_rows = max(len(won_from), len(lost_to))
    for i in range(n_rows):
        won = won_from[i] if i < len(won_from) else None
        lost = lost_to[i] if i < len(lost_to) else None

        # Won bar (right-to-left)
        won_cell = html.Div(style={"display": "flex", "alignItems": "center", "justifyContent": "flex-end", "gap": 8})
        if won:
            won_width = (won[1] / max_val) * 100 if max_val > 0 else 0
            won_cell = html.Div([
                html.Span(_fmt_pct(won[1]), style={"fontSize": 11, "color": "#4D5153", "whiteSpace": "nowrap"}),
                html.Div(style={
                    "height": 20, "width": f"{won_width:.0f}%", "minWidth": 4,
                    "backgroundColor": CI_GREEN, "borderRadius": 3,
                }),
            ], style={"display": "flex", "alignItems": "center", "justifyContent": "flex-end", "gap": 8, "width": "100%"})

        # Brand label
        brand = won[0] if won else (lost[0] if lost else "")
        label_cell = html.Div(brand, style={
            "textAlign": "center", "fontSize": 12, "fontWeight": "bold",
            "color": "#4D5153", "padding": "0 4px", "whiteSpace": "nowrap",
        })

        # Lost bar (left-to-right)
        lost_cell = html.Div(style={"display": "flex", "alignItems": "center", "gap": 8})
        if lost:
            lost_width = (lost[1] / max_val) * 100 if max_val > 0 else 0
            lost_cell = html.Div([
                html.Div(style={
                    "height": 20, "width": f"{lost_width:.0f}%", "minWidth": 4,
                    "backgroundColor": CI_RED, "borderRadius": 3,
                }),
                html.Span(_fmt_pct(lost[1]), style={"fontSize": 11, "color": "#4D5153", "whiteSpace": "nowrap"}),
            ], style={"display": "flex", "alignItems": "center", "gap": 8, "width": "100%"})

        rows.append(dbc.Row([
            dbc.Col(won_cell, width=5),
            dbc.Col(label_cell, width=2, style={"display": "flex", "alignItems": "center", "justifyContent": "center"}),
            dbc.Col(lost_cell, width=5),
        ], className="mb-2", align="center"))

    children = [
        # Headers
        dbc.Row([
            dbc.Col(html.Div("Won from", style={
                "fontSize": 13, "fontWeight": "bold", "color": CI_GREEN, "textAlign": "right", "paddingRight": 12,
            }), width=5),
            dbc.Col(html.Div(), width=2),
            dbc.Col(html.Div("Lost to", style={
                "fontSize": 13, "fontWeight": "bold", "color": CI_RED, "textAlign": "left", "paddingLeft": 12,
            }), width=5),
        ], className="mb-3"),
        *rows,
    ]

    if callout:
        children.append(html.Div(callout, style={
            "marginTop": 16, "paddingTop": 12,
            "borderTop": f"1px solid {CI_LIGHT_GREY}",
            "fontSize": 12, "color": "#4D5153", "fontStyle": "italic",
        }))

    return html.Div(children, style={
        "backgroundColor": "#FFF", "borderRadius": 8,
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "padding": 20, "fontFamily": FONT,
    })


# ---------------------------------------------------------------------------
# Page builder
# ---------------------------------------------------------------------------

def _build_headline_page(d):
    """Build the full headline story layout from metrics dict."""
    ins = d["insurer"]
    pre_pp = d["pre_share"] * 100
    post_pp = d["after_share"] * 100
    delta_pp = d["share_delta"] * 100
    delta_sign = "+" if delta_pp >= 0 else ""
    movement_colour = CI_GREEN if delta_pp > 0 else (CI_RED if delta_pp < 0 else CI_GREY)

    # Derive tags
    shop_tag = _derive_tag(d["shop_pct"], d["mkt_shop_pct"])
    ret_tag = _derive_tag(d["retained_pct"], d["mkt_retained_pct"])
    stay_tag = _derive_tag(d["shop_stay_pct"], d["mkt_shop_stay_pct"])
    biz_tag = _derive_tag(d["new_biz_pct"], d["mkt_new_biz_pct"])

    # Auto-narrative for support line
    direction = "lifting" if delta_pp > 0 else ("dropping" if delta_pp < 0 else "holding")
    support = (
        f"Retention and acquisition both beat market, {direction} share "
        f"from {pre_pp:.1f}% to {post_pp:.1f}% through renewal."
    )

    # Dynamic callout for butterfly
    won_brands = {b for b, _ in d["won_from"]}
    lost_brands = {b for b, _ in d["lost_to"]}
    overlap = won_brands & lost_brands - {"New to market"}
    if overlap:
        top_battle = sorted(overlap, key=lambda b: next((p for bb, p in d["lost_to"] if bb == b), 0), reverse=True)[0]
        callout = f"{top_battle} is the main two-way battleground."
    elif d["won_from"]:
        callout = f"Largest source: {d['won_from'][0][0]}."
    else:
        callout = None

    # Update module-level label for comparison bars
    global insurer_label
    insurer_label = ins

    return html.Div([
        # ── HEADLINE ──────────────────────────────────────────
        html.H1(
            f"Customers shop at the market rate, but {ins} keeps more of them",
            style={
                "fontSize": 22, "fontWeight": "bold", "color": "#4D5153",
                "margin": "0 0 6px", "lineHeight": "1.3", "fontFamily": FONT,
            },
        ),
        html.P(support, style={
            "fontSize": 14, "color": CI_GREY, "margin": "0 0 20px",
            "lineHeight": "1.5", "fontFamily": FONT,
        }),

        # ── OUTCOME ───────────────────────────────────────────
        html.Div([
            _share_card("Pre-renewal share", f"{pre_pp:.1f}%", "#4D5153"),
            _share_card(
                "Net movement",
                f"{delta_sign}{delta_pp:.1f} pts",
                movement_colour,
                border_top=movement_colour,
            ),
            _share_card("Post-renewal share", f"{post_pp:.1f}%", CI_MAGENTA),
        ], style={
            "display": "flex", "gap": 16, "marginBottom": 32,
            "justifyContent": "center", "flexWrap": "wrap",
        }),

        # ── WHY THIS HAPPENED ─────────────────────────────────
        html.Div([
            html.Div("Why this happened", style={
                "fontSize": 15, "fontWeight": "bold", "color": "#4D5153", "marginBottom": 4,
            }),
            html.P(
                f"Customers are just as likely to shop around. {ins} performs better when they do.",
                style={"fontSize": 13, "color": CI_GREY, "margin": "0 0 20px", "lineHeight": "1.5"},
            ),
            _comparison_bar("Shopping rate", d["shop_pct"], d["mkt_shop_pct"], shop_tag),
            _comparison_bar("Retention", d["retained_pct"], d["mkt_retained_pct"], ret_tag),
            _comparison_bar("Shopped and stayed", d["shop_stay_pct"], d["mkt_shop_stay_pct"], stay_tag),
            _comparison_bar(
                "New business acquisition",
                d["new_biz_pct"], d["mkt_new_biz_pct"], biz_tag,
                max_val=max(d["new_biz_pct"], d["mkt_new_biz_pct"]) * 2.5 or 0.01,
            ),
        ], style={
            "backgroundColor": "#FFF", "borderRadius": 8,
            "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
            "padding": 20, "marginBottom": 32, "fontFamily": FONT,
        }),

        # ── COMPETITIVE EXCHANGE ──────────────────────────────
        html.Div([
            html.Div("Competitive exchange", style={
                "fontSize": 15, "fontWeight": "bold", "color": "#4D5153", "marginBottom": 12,
            }),
            _butterfly_chart(d["won_from"], d["lost_to"], callout),
        ], style={"marginBottom": 32}),

        # ── FOOTER ────────────────────────────────────────────
        html.Div(
            f"Base: {d['n']:,} respondents",
            style={
                "fontSize": 11, "color": CI_GREY, "textAlign": "center",
                "paddingBottom": 24, "fontFamily": FONT,
            },
        ),
    ], style={"fontFamily": FONT, "maxWidth": 900, "margin": "0 auto"})


# ---------------------------------------------------------------------------
# Layout & callback
# ---------------------------------------------------------------------------

def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[html.H1("Headline")]),
        html.Div(id="filter-bar-hl"),
        html.Div(id="headline-content"),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


@callback(
    [
        Output("filter-bar-hl", "children"),
        Output("headline-content", "children"),
    ],
    [
        Input("global-insurer", "value"),
        Input("global-age-band", "value"),
        Input("global-region", "value"),
        Input("global-payment-type", "value"),
        Input("global-product", "value"),
        Input("global-time-window", "value"),
    ],
)
def update_headline(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    selected = [int(v) for v in time_window] if time_window else None
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)

    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_mkt = apply_filters(
        df_main, insurer=None, age_band=age_band, region=region,
        payment_type=payment_type, product=product, selected_months=selected,
    )

    filter_bar_el = filter_bar(age_band, region, payment_type)

    if not insurer:
        return (
            filter_bar_el,
            html.Div([
                html.H2("Headline", style={"fontFamily": FONT, "color": "#4D5153"}),
                html.P(
                    "Select an insurer to view the headline story.",
                    style={"color": CI_GREY, "fontFamily": FONT, "fontSize": 14},
                ),
            ], style={"padding": "40px 0", "textAlign": "center"}),
        )

    if len(df_mkt) == 0:
        return (
            filter_bar_el,
            html.P("No data available for the selected filters.",
                   className="text-muted", style={"fontFamily": FONT}),
        )

    d = _calc_headline_metrics(df_mkt, insurer)
    if d is None:
        return (
            filter_bar_el,
            html.P("Insufficient data.", className="text-muted", style={"fontFamily": FONT}),
        )

    return filter_bar_el, _build_headline_page(d)
