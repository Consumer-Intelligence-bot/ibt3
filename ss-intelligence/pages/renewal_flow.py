"""
Page: Renewal Flow — Pre-Renewal → Renewal → Post-Renewal visual.

Visual flow diagram showing the customer journey from pre-renewal market share
through shopping/non-shopping behaviour to post-renewal outcomes.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, callback, html

from analytics.demographics import apply_filters
from components.filter_bar import filter_bar
from config import CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED, CI_BLUE
from shared import DF_MOTOR, DF_HOME

dash.register_page(__name__, path="/renewal-flow", name="Renewal Flow")

FONT = "Verdana, Geneva, sans-serif"
PHASE_PRE = "#ECEDF2"
PHASE_REN = "#FFFFFF"
PHASE_POST = "#E8F3EA"


def _pct(n, d):
    return n / d if d > 0 else 0


def _fmt_pct(val, dp=1):
    if val is None:
        return "—"
    return f"{val * 100:.{dp}f}%"


def _calc_flow_metrics(df_ins, df_mkt, insurer):
    """Compute all renewal flow metrics from filtered data."""
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
    mkt_nonshop_pct = _pct(len(non_shoppers), len(existing)) if len(existing) > 0 else 0
    mkt_new_biz_pct = _pct(len(new_to_market), total)
    mkt_shop_stay_pct = _pct(len(shop_stay), len(shoppers)) if len(shoppers) > 0 else 0
    mkt_shop_switch_pct = _pct(len(shop_switch), len(shoppers)) if len(shoppers) > 0 else 0
    mkt_retained_pct = _pct(len(non_shoppers) + len(shop_stay), total)

    if insurer:
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

        switchers_to = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["CurrentCompany"] == insurer) & (df_mkt["PreviousCompany"] != insurer)]
        total_won = len(switchers_to) + len(ins_new_biz)
        won_counts = {}
        for _, r in switchers_to.iterrows():
            b = r.get("PreviousCompany", "Other")
            won_counts[b] = won_counts.get(b, 0) + 1
        if len(ins_new_biz) > 0:
            won_counts["New to market"] = len(ins_new_biz)
        won_from = sorted(won_counts.items(), key=lambda x: -x[1])[:3]
        won_from = [(b, _pct(c, total_won)) for b, c in won_from] if total_won > 0 else []

        lost_switchers = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
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
            "new_biz_pct": _pct(len(ins_new_biz), ins_total) if ins_total > 0 else 0,
            "mkt_new_biz_pct": mkt_new_biz_pct,
            "nonshop_pct": _pct(len(ins_non_shop), len(ins_existing)) if len(ins_existing) > 0 else 0,
            "mkt_nonshop_pct": mkt_nonshop_pct,
            "shop_pct": _pct(len(ins_shoppers), len(ins_existing)) if len(ins_existing) > 0 else 0,
            "mkt_shop_pct": mkt_shop_pct,
            "shop_stay_pct": _pct(len(ins_shop_stay), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
            "mkt_shop_stay_pct": mkt_shop_stay_pct,
            "shop_switch_pct": _pct(len(ins_shop_switch), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
            "mkt_shop_switch_pct": mkt_shop_switch_pct,
            "retained_pct": _pct(ins_retained, ins_total) if ins_total > 0 else 0,
            "mkt_retained_pct": mkt_retained_pct,
            "after_share": after_share,
            "share_delta": after_share - pre_share,
            "cust_base_retained": _pct(ins_retained, ins_total) if ins_total > 0 else 0,
            "cust_base_new": _pct(len(ins_new_biz), ins_total) if ins_total > 0 else 0,
            "won_from": won_from,
            "lost_to": lost_to,
            "n": ins_total,
        }

    return {
        "insurer": None,
        "pre_share": 1.0,
        "new_biz_pct": mkt_new_biz_pct,
        "mkt_new_biz_pct": None,
        "nonshop_pct": mkt_nonshop_pct,
        "mkt_nonshop_pct": None,
        "shop_pct": mkt_shop_pct,
        "mkt_shop_pct": None,
        "shop_stay_pct": mkt_shop_stay_pct,
        "mkt_shop_stay_pct": None,
        "shop_switch_pct": mkt_shop_switch_pct,
        "mkt_shop_switch_pct": None,
        "retained_pct": mkt_retained_pct,
        "mkt_retained_pct": None,
        "after_share": 1.0,
        "share_delta": 0,
        "cust_base_retained": mkt_retained_pct,
        "cust_base_new": mkt_new_biz_pct,
        "won_from": [],
        "lost_to": [],
        "n": total,
    }


def _flow_card(title, value, benchmark=None, color=CI_MAGENTA, icon=None):
    """Single metric card in the flow diagram."""
    children = []
    if icon:
        children.append(html.Div(icon, style={"fontSize": 20, "marginBottom": 2}))
    children.append(html.Div(title, style={
        "fontSize": 10, "fontWeight": 600, "color": color, "lineHeight": "1.2", "marginBottom": 2,
    }))
    children.append(html.Div(value, style={
        "fontFamily": FONT, "fontSize": 16, "fontWeight": 700, "color": color,
    }))
    if benchmark is not None:
        children.append(html.Div(f"({benchmark})", style={"fontSize": 9, "color": CI_GREY}))

    border_map = {
        CI_GREEN: "#B8DFC0", CI_RED: "#F0B8B8", CI_BLUE: "#B8D4EF",
        CI_MAGENTA: "#D4A8D3",
    }
    bg_map = {
        CI_GREEN: "#F8FCF9", CI_RED: "#FDF5F5", CI_BLUE: "#F5F9FD",
        CI_MAGENTA: "#FBF5FB",
    }

    return html.Div(children, style={
        "background": bg_map.get(color, "#FFF"),
        "borderRadius": 7,
        "padding": "8px 10px",
        "textAlign": "center",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.10)",
        "border": f"1.5px solid {border_map.get(color, '#D8DCE3')}",
        "fontFamily": FONT,
    })


def _outline_card(title, value):
    return html.Div([
        html.Div(title, style={
            "fontSize": 10, "fontWeight": 600, "color": CI_GREEN, "lineHeight": "1.2", "marginBottom": 2,
        }),
        html.Div(value, style={
            "fontFamily": FONT, "fontSize": 22, "fontWeight": 700, "color": CI_GREEN,
        }),
    ], style={
        "background": "transparent",
        "borderRadius": 7,
        "padding": "8px 10px",
        "textAlign": "center",
        "border": f"2.5px solid {CI_GREEN}",
        "fontFamily": FONT,
    })


def _brand_list(title, brands, color):
    border = "#B8DFC0" if color == CI_GREEN else "#F0B8B8"
    bg = "#F8FCF9" if color == CI_GREEN else "#FDF5F5"
    rows = [
        html.Div([
            html.Span(b, style={"color": CI_GREY, "fontSize": 10}),
            html.Span(_fmt_pct(p), style={"fontWeight": 700, "color": color, "fontSize": 10, "fontFamily": FONT}),
        ], style={"display": "flex", "justifyContent": "space-between", "padding": "2px 0"})
        for b, p in brands
    ]
    return html.Div([
        html.Div([
            html.Span(title, style={"fontWeight": 600, "color": color, "fontSize": 10}),
            html.Span(" (top 3)", style={"fontWeight": 400, "color": CI_GREY, "fontSize": 9}),
        ]),
        html.Div(rows, style={"marginTop": 4}),
    ], style={
        "background": bg, "borderRadius": 7, "padding": "8px 10px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.10)",
        "border": f"1.5px solid {border}", "fontFamily": FONT,
    })


def _delta_badge(delta):
    if delta is None or delta == 0:
        return None
    bg = "#D4EDDA" if delta > 0 else "#FDDEDE"
    col = CI_GREEN if delta > 0 else CI_RED
    sign = "+" if delta > 0 else ""
    return html.Span(f"{sign}{delta * 100:.1f}%", style={
        "fontSize": 9, "fontWeight": 700, "padding": "1px 6px",
        "borderRadius": 8, "background": bg, "color": col,
    })


def _comp_bar(retained_pct, new_pct):
    return html.Div([
        html.Div("Customer base", style={"fontSize": 10, "fontWeight": 600, "color": CI_GREY, "marginBottom": 4}),
        html.Div([
            html.Div(style={"width": f"{retained_pct * 100:.0f}%", "background": CI_GREEN, "height": 6}),
            html.Div(style={"width": f"{new_pct * 100:.0f}%", "background": CI_BLUE, "height": 6}),
        ], style={"display": "flex", "borderRadius": 3, "overflow": "hidden"}),
        html.Div([
            html.Span([
                html.Span(style={"display": "inline-block", "width": 6, "height": 6, "borderRadius": "50%", "background": CI_GREEN, "marginRight": 2, "verticalAlign": "middle"}),
                f"Ret. {_fmt_pct(retained_pct)}",
            ], style={"fontSize": 8}),
            html.Span([
                html.Span(style={"display": "inline-block", "width": 6, "height": 6, "borderRadius": "50%", "background": CI_BLUE, "marginRight": 2, "verticalAlign": "middle"}),
                f"New {_fmt_pct(new_pct)}",
            ], style={"fontSize": 8}),
        ], style={"display": "flex", "justifyContent": "space-between", "marginTop": 3, "color": CI_GREY}),
    ], style={
        "background": "#FFF", "borderRadius": 7, "padding": "8px 10px",
        "boxShadow": "0 2px 8px rgba(0,0,0,0.10)",
        "border": "1.5px solid #D8DCE3", "fontFamily": FONT,
    })


def _icon_circle(emoji, bg):
    return html.Div(emoji, style={
        "width": 36, "height": 36, "borderRadius": "50%", "display": "flex",
        "alignItems": "center", "justifyContent": "center", "fontSize": 16,
        "background": bg, "margin": "0 auto 4px",
    })


def _build_flow_diagram(d):
    """Build the full renewal flow layout from metrics dict."""
    is_insurer = d["insurer"] is not None

    # PRE-RENEWAL column
    pre_col = html.Div([
        html.Div([
            _icon_circle("✉", "#DCE5F0"),
            html.Div("Renewal notice", style={"fontSize": 9, "color": CI_GREY, "textAlign": "center"}),
        ], style={"marginBottom": 12}),
        html.Div([
            _icon_circle("👥", "#EDE7F6"),
            html.Div("Existing customers", style={"fontSize": 9, "color": CI_GREY, "textAlign": "center"}),
        ], style={"marginBottom": 12}),
        html.Div([
            _icon_circle("❓", "#FFF3E0"),
        ], style={"marginBottom": 20}),
        _outline_card("Pre-renewal market share", _fmt_pct(d["pre_share"])),
    ], style={
        "background": PHASE_PRE, "borderRadius": "8px 0 0 8px", "padding": "24px 12px",
        "display": "flex", "flexDirection": "column", "alignItems": "center", "justifyContent": "center",
        "position": "relative", "minHeight": 440,
    })

    # RENEWAL column
    ren_cards = [
        html.Div(
            _flow_card("New business acquisition", _fmt_pct(d["new_biz_pct"]),
                       _fmt_pct(d["mkt_new_biz_pct"]) if d["mkt_new_biz_pct"] is not None else None,
                       CI_MAGENTA, "👤+"),
            style={"marginBottom": 12},
        ),
        html.Div([
            html.Div(
                _flow_card("Non-shoppers", _fmt_pct(d["nonshop_pct"]),
                           _fmt_pct(d["mkt_nonshop_pct"]) if d["mkt_nonshop_pct"] is not None else None,
                           CI_BLUE, "📞"),
                style={"flex": 1},
            ),
            html.Div(style={"width": 12}),
            html.Div(
                _flow_card("Shoppers", _fmt_pct(d["shop_pct"]),
                           _fmt_pct(d["mkt_shop_pct"]) if d["mkt_shop_pct"] is not None else None,
                           "#C47A00", "🛒"),
                style={"flex": 1},
            ),
        ], style={"display": "flex", "marginBottom": 12}),
        html.Div([
            html.Div(
                _flow_card("Shopped then stayed", _fmt_pct(d["shop_stay_pct"]),
                           _fmt_pct(d["mkt_shop_stay_pct"]) if d["mkt_shop_stay_pct"] is not None else None,
                           CI_GREEN, "💚"),
                style={"flex": 1},
            ),
            html.Div(style={"width": 12}),
            html.Div(
                _flow_card("Shopped then switched", _fmt_pct(d["shop_switch_pct"]),
                           _fmt_pct(d["mkt_shop_switch_pct"]) if d["mkt_shop_switch_pct"] is not None else None,
                           CI_RED, "🔄"),
                style={"flex": 1},
            ),
        ], style={"display": "flex"}),
    ]

    ren_col = html.Div(ren_cards, style={
        "background": PHASE_REN, "padding": "24px 16px",
        "display": "flex", "flexDirection": "column", "justifyContent": "center",
        "minHeight": 440,
    })

    # POST-RENEWAL column
    post_items = []

    if d.get("won_from") and len(d["won_from"]) > 0:
        post_items.append(html.Div(
            _brand_list("Won from", d["won_from"], CI_GREEN),
            style={"marginBottom": 12},
        ))

    post_items.append(html.Div(
        _flow_card("Retained", _fmt_pct(d["retained_pct"]),
                   _fmt_pct(d["mkt_retained_pct"]) if d["mkt_retained_pct"] is not None else None,
                   CI_GREEN, "✅"),
        style={"marginBottom": 12},
    ))

    after_children = [
        html.Div("After renewal market share", style={
            "fontSize": 10, "fontWeight": 600, "color": CI_GREEN, "lineHeight": "1.2", "marginBottom": 2,
        }),
        html.Div(_fmt_pct(d["after_share"]), style={
            "fontFamily": FONT, "fontSize": 22, "fontWeight": 700, "color": CI_GREEN,
        }),
    ]
    badge = _delta_badge(d.get("share_delta"))
    if badge:
        after_children.append(badge)

    post_items.append(html.Div(after_children, style={
        "background": "#F8FCF9", "borderRadius": 7, "padding": "8px 10px",
        "textAlign": "center", "boxShadow": "0 2px 8px rgba(0,0,0,0.10)",
        "border": f"1.5px solid #B8DFC0", "fontFamily": FONT, "marginBottom": 12,
    }))

    post_items.append(html.Div(
        _comp_bar(d["cust_base_retained"], d["cust_base_new"]),
        style={"marginBottom": 12},
    ))

    if d.get("lost_to") and len(d["lost_to"]) > 0:
        post_items.append(_brand_list("Lost to", d["lost_to"], CI_RED))

    post_col = html.Div(post_items, style={
        "background": PHASE_POST, "borderRadius": "0 8px 8px 0", "padding": "24px 12px",
        "display": "flex", "flexDirection": "column", "justifyContent": "center",
        "minHeight": 440,
    })

    # Phase labels
    def phase_label(text, color):
        return html.Div(text, style={
            "fontFamily": FONT, "fontSize": 9, "fontWeight": 700,
            "letterSpacing": 1.5, "textTransform": "uppercase",
            "textAlign": "center", "color": color, "padding": "6px 0",
        })

    return html.Div([
        dbc.Row([
            dbc.Col(pre_col, md=2, sm=12),
            dbc.Col(ren_col, md=5, sm=12),
            dbc.Col(post_col, md=5, sm=12),
        ], className="g-0"),
        dbc.Row([
            dbc.Col(phase_label("PRE-RENEWAL", "#8890B8"), md=2),
            dbc.Col(phase_label("RENEWAL", "#BBB"), md=5),
            dbc.Col(phase_label("POST-RENEWAL", CI_GREEN), md=5),
        ], className="g-0"),
    ], style={
        "borderRadius": 8, "overflow": "hidden",
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "background": "#FFF",
    })


def layout():
    return dbc.Container([
        html.Div(className="ci-page-header", children=[html.H1("Renewal Flow")]),
        html.Div(id="filter-bar-rf"),
        html.Div(id="renewal-flow-heading"),
        html.Div(id="renewal-flow-content"),
    ], fluid=True)


def _norm(val):
    return None if val in (None, "ALL", "") else val


@callback(
    [
        Output("filter-bar-rf", "children"),
        Output("renewal-flow-heading", "children"),
        Output("renewal-flow-content", "children"),
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
def update_renewal_flow(insurer, age_band, region, payment_type, product, time_window):
    product = product or "Motor"
    tw = int(time_window or 24)
    age_band, region, payment_type = _norm(age_band), _norm(region), _norm(payment_type)

    df_main = DF_MOTOR if product == "Motor" else (DF_HOME if DF_HOME is not None and len(DF_HOME) > 0 else DF_MOTOR)
    df_mkt = apply_filters(
        df_main, insurer=None, age_band=age_band, region=region,
        payment_type=payment_type, product=product, time_window_months=tw,
    )
    df_ins = apply_filters(
        df_main, insurer=insurer, age_band=age_band, region=region,
        payment_type=payment_type, product=product, time_window_months=tw,
    ) if insurer else df_mkt

    filter_bar_el = filter_bar(age_band, region, payment_type)

    if len(df_mkt) == 0:
        return (
            filter_bar_el,
            html.H2("Renewal Flow"),
            html.P("No data available for the selected filters.", className="text-muted"),
        )

    d = _calc_flow_metrics(df_ins, df_mkt, insurer)
    if d is None:
        return (
            filter_bar_el,
            html.H2("Renewal Flow"),
            html.P("Insufficient data.", className="text-muted"),
        )

    heading_text = f"Renewal Flow — {insurer}" if insurer else "Renewal Flow — Market View"
    heading = html.H2(heading_text, style={"fontFamily": FONT, "marginBottom": 16})

    if insurer and d["n"] > 0:
        n_text = html.Div(
            f"Based on {d['n']} respondents",
            style={"fontSize": 12, "color": CI_GREY, "marginBottom": 8},
        )
        heading = html.Div([heading, n_text])

    diagram = _build_flow_diagram(d)

    return filter_bar_el, heading, diagram
