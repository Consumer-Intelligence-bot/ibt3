"""
Page: Headline — Share Through Renewal story page.

Single-page narrative answering: Are we gaining or losing share through
renewal, and why?  Three sections — Outcome, Drivers, Competitive Exchange.

Enhanced with:
  - "Click for more" accordion deep dives on each comparison bar
  - Renewal premium change vs market (below Pre-renewal share)
  - Source of business PCW/Direct vs market (below Post-renewal share)
  - Net movement rank among all insurers (below Net movement)
"""
import logging
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import dash
import dash_bootstrap_components as dbc
from dash import Input, Output, State, callback, dcc, html

log = logging.getLogger(__name__)

from analytics.demographics import apply_filters
from analytics.narrative import generate_narrative
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
        # --- Deep-dive data ---
        "ins_shoppers": ins_shoppers,
        "ins_shop_stay": ins_shop_stay,
        "ins_new_biz": ins_new_biz,
        "shoppers": shoppers,
        "shop_stay": shop_stay,
        "new_to_market": new_to_market,
        "existing": existing,
        "switchers_to": switchers_to,
    }


def _calc_premium_change(df_mkt, insurer):
    """Premium change distribution: insurer vs market (excludes new-to-market)."""
    existing = df_mkt[~df_mkt["IsNewToMarket"]]
    col = "Renewal premium change"
    if col not in existing.columns or len(existing) == 0:
        return None

    ins_rows = existing[existing["PreviousCompany"] == insurer]
    if len(ins_rows) == 0:
        return None

    def _split(subset):
        n = len(subset)
        if n == 0:
            return {"higher": 0, "unchanged": 0, "lower": 0}
        higher = len(subset[subset[col] == "Higher"])
        unchanged = len(subset[subset[col] == "It was unchanged"])
        lower = len(subset[subset[col] == "Lower"])
        return {"higher": higher / n, "unchanged": unchanged / n, "lower": lower / n}

    return {"insurer": _split(ins_rows), "market": _split(existing)}


def _calc_channel_comparison(df_mkt, insurer):
    """PCW vs Direct/Other for shoppers: insurer vs market."""
    existing = df_mkt[~df_mkt["IsNewToMarket"]]
    shoppers = existing[existing["IsShopper"]]
    col = "Did you use a PCW for shopping"
    if col not in shoppers.columns or len(shoppers) == 0:
        return None

    ins_shoppers = shoppers[shoppers["PreviousCompany"] == insurer]
    if len(ins_shoppers) == 0:
        return None

    def _split(subset):
        n = len(subset)
        if n == 0:
            return {"pcw": 0, "direct": 0}
        pcw = len(subset[subset[col] == "Yes"])
        return {"pcw": pcw / n, "direct": (n - pcw) / n}

    return {"insurer": _split(ins_shoppers), "market": _split(shoppers)}


def _calc_net_movement_rank(df_mkt, insurer):
    """Rank insurer by net movement (post share - pre share) among all brands."""
    total = len(df_mkt)
    if total == 0:
        return None

    all_brands = set(df_mkt["PreviousCompany"].dropna().unique()) | set(df_mkt["CurrentCompany"].dropna().unique())
    movements = []
    for brand in all_brands:
        pre = len(df_mkt[df_mkt["PreviousCompany"] == brand])
        post = len(df_mkt[df_mkt["CurrentCompany"] == brand])
        delta = (post - pre) / total
        movements.append((brand, delta))
    movements.sort(key=lambda x: -x[1])

    rank = next((i + 1 for i, (b, _) in enumerate(movements) if b == insurer), None)
    if rank is None:
        return None
    ins_delta = next((d for b, d in movements if b == insurer), 0)
    return {"rank": rank, "total_brands": len(movements), "delta": ins_delta}


def _calc_deep_dive_data(df_mkt, insurer, d):
    """Compute deep-dive breakdowns for each of the 4 comparison bars."""
    existing = d["existing"]
    shoppers = d["shoppers"]
    shop_stay = d["shop_stay"]
    ins_shoppers = d["ins_shoppers"]
    ins_shop_stay = d["ins_shop_stay"]
    ins_new_biz = d["ins_new_biz"]
    new_to_market = d["new_to_market"]
    switchers_to = d["switchers_to"]

    col_pc = "Renewal premium change"
    col_age = "Age Group"
    col_region = "Region"
    col_pcw = "Did you use a PCW for shopping"

    def _rate_by_group(base, group_col, condition_col, condition_val):
        """Rate of condition within each group."""
        groups = base[group_col].dropna().unique()
        result = []
        for g in sorted(groups):
            subset = base[base[group_col] == g]
            if len(subset) < 30:
                continue
            rate = _pct(len(subset[subset[condition_col] == condition_val]), len(subset))
            result.append((g, rate, len(subset)))
        return result

    # Shopping rate by premium change
    shop_by_premium = []
    if col_pc in existing.columns:
        for pc_val in ["Higher", "It was unchanged", "Lower"]:
            ins_grp = existing[(existing["PreviousCompany"] == insurer) & (existing[col_pc] == pc_val)]
            mkt_grp = existing[existing[col_pc] == pc_val]
            ins_rate = _pct(len(ins_grp[ins_grp["IsShopper"]]), len(ins_grp)) if len(ins_grp) >= 30 else None
            mkt_rate = _pct(len(mkt_grp[mkt_grp["IsShopper"]]), len(mkt_grp)) if len(mkt_grp) >= 30 else None
            shop_by_premium.append((pc_val, ins_rate, mkt_rate))

    # Shopping rate by age group
    shop_by_age = []
    if col_age in existing.columns:
        ins_existing = existing[existing["PreviousCompany"] == insurer]
        for age in sorted(existing[col_age].dropna().unique()):
            ins_grp = ins_existing[ins_existing[col_age] == age]
            mkt_grp = existing[existing[col_age] == age]
            ins_rate = _pct(len(ins_grp[ins_grp["IsShopper"]]), len(ins_grp)) if len(ins_grp) >= 30 else None
            mkt_rate = _pct(len(mkt_grp[mkt_grp["IsShopper"]]), len(mkt_grp)) if len(mkt_grp) >= 30 else None
            shop_by_age.append((age, ins_rate, mkt_rate))

    # Retention by premium change
    ret_by_premium = []
    if col_pc in existing.columns:
        for pc_val in ["Higher", "It was unchanged", "Lower"]:
            ins_grp = existing[(existing["PreviousCompany"] == insurer) & (existing[col_pc] == pc_val)]
            mkt_grp = existing[existing[col_pc] == pc_val]
            ins_rate = _pct(len(ins_grp[ins_grp["IsRetained"]]), len(ins_grp)) if len(ins_grp) >= 30 else None
            mkt_rate = _pct(len(mkt_grp[mkt_grp["IsRetained"]]), len(mkt_grp)) if len(mkt_grp) >= 30 else None
            ret_by_premium.append((pc_val, ins_rate, mkt_rate))

    # Retention by region
    ret_by_region = []
    if col_region in existing.columns:
        ins_existing = existing[existing["PreviousCompany"] == insurer]
        for region in sorted(existing[col_region].dropna().unique()):
            ins_grp = ins_existing[ins_existing[col_region] == region]
            mkt_grp = existing[existing[col_region] == region]
            ins_rate = _pct(len(ins_grp[ins_grp["IsRetained"]]), len(ins_grp)) if len(ins_grp) >= 30 else None
            mkt_rate = _pct(len(mkt_grp[mkt_grp["IsRetained"]]), len(mkt_grp)) if len(mkt_grp) >= 30 else None
            ret_by_region.append((region, ins_rate, mkt_rate))

    # Shopped-and-stayed: premium change split
    shop_stay_by_premium = []
    if col_pc in ins_shop_stay.columns and len(ins_shop_stay) > 0:
        for pc_val in ["Higher", "It was unchanged", "Lower"]:
            ins_rate = _pct(len(ins_shop_stay[ins_shop_stay[col_pc] == pc_val]), len(ins_shop_stay))
            mkt_rate = _pct(len(shop_stay[shop_stay[col_pc] == pc_val]), len(shop_stay)) if len(shop_stay) > 0 else 0
            shop_stay_by_premium.append((pc_val, ins_rate, mkt_rate))

    # Shopped-and-stayed: PCW usage
    shop_stay_pcw = None
    if col_pcw in ins_shop_stay.columns and len(ins_shop_stay) >= 30:
        ins_pcw = _pct(len(ins_shop_stay[ins_shop_stay[col_pcw] == "Yes"]), len(ins_shop_stay))
        mkt_pcw = _pct(len(shop_stay[shop_stay[col_pcw] == "Yes"]), len(shop_stay)) if len(shop_stay) > 0 else 0
        shop_stay_pcw = {"insurer": ins_pcw, "market": mkt_pcw}

    # New biz: top 5 source brands
    won_counts = {}
    for _, r in switchers_to.iterrows():
        b = r.get("PreviousCompany", "Other")
        won_counts[b] = won_counts.get(b, 0) + 1
    if len(ins_new_biz) > 0:
        won_counts["New to market"] = len(ins_new_biz)
    total_won = len(switchers_to) + len(ins_new_biz)
    new_biz_sources = sorted(won_counts.items(), key=lambda x: -x[1])[:5]
    new_biz_sources = [(b, _pct(c, total_won)) for b, c in new_biz_sources] if total_won > 0 else []

    # New biz: channel breakdown (PCW usage among those who switched to insurer)
    new_biz_channel = None
    new_arrivals = switchers_to
    if col_pcw in new_arrivals.columns and len(new_arrivals) >= 30:
        ins_pcw = _pct(len(new_arrivals[new_arrivals[col_pcw] == "Yes"]), len(new_arrivals))
        all_switchers = df_mkt[df_mkt["IsSwitcher"]]
        mkt_pcw = _pct(len(all_switchers[all_switchers[col_pcw] == "Yes"]), len(all_switchers)) if len(all_switchers) > 0 else 0
        new_biz_channel = {"insurer": ins_pcw, "market": mkt_pcw}

    return {
        "shop_by_premium": shop_by_premium,
        "shop_by_age": shop_by_age,
        "ret_by_premium": ret_by_premium,
        "ret_by_region": ret_by_region,
        "shop_stay_by_premium": shop_stay_by_premium,
        "shop_stay_pcw": shop_stay_pcw,
        "new_biz_sources": new_biz_sources,
        "new_biz_channel": new_biz_channel,
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


def _mini_paired_bar(label, ins_val, mkt_val, ins_colour=CI_MAGENTA):
    """Small paired horizontal bar for sub-cards (premium change, source of biz)."""
    max_val = max(ins_val, mkt_val, 0.01)
    ins_w = (ins_val / max_val) * 100
    mkt_w = (mkt_val / max_val) * 100
    return html.Div([
        html.Div(label, style={
            "fontSize": 10, "color": "#4D5153", "marginBottom": 3, "fontWeight": "bold",
        }),
        # Insurer bar
        html.Div([
            html.Div(style={
                "height": 10, "width": f"{ins_w:.0f}%", "minWidth": 2,
                "backgroundColor": ins_colour, "borderRadius": 2,
                "display": "inline-block",
            }),
            html.Span(f" {_fmt_pct(ins_val)}", style={"fontSize": 10, "color": ins_colour, "fontWeight": "bold"}),
        ], style={"marginBottom": 2}),
        # Market bar
        html.Div([
            html.Div(style={
                "height": 10, "width": f"{mkt_w:.0f}%", "minWidth": 2,
                "backgroundColor": CI_GREY, "borderRadius": 2, "opacity": 0.5,
                "display": "inline-block",
            }),
            html.Span(f" {_fmt_pct(mkt_val)}", style={"fontSize": 10, "color": CI_GREY}),
        ]),
    ], style={"marginBottom": 8})


def _premium_change_card(pc_data, ins_name):
    """Sub-card: renewal premium change vs market."""
    if pc_data is None:
        return html.Div()
    ins = pc_data["insurer"]
    mkt = pc_data["market"]
    return html.Div([
        html.Div("Renewal premium change", style={
            "fontSize": 10, "color": "#666", "textTransform": "uppercase",
            "letterSpacing": "0.5px", "marginBottom": 8,
        }),
        _mini_paired_bar("Higher", ins["higher"], mkt["higher"]),
        _mini_paired_bar("Unchanged", ins["unchanged"], mkt["unchanged"]),
        _mini_paired_bar("Lower", ins["lower"], mkt["lower"]),
    ], style={
        "backgroundColor": "#FFF", "borderRadius": 8,
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "padding": "12px 16px", "fontFamily": FONT, "marginTop": 8,
    })


def _source_of_business_card(ch_data, ins_name):
    """Sub-card: source of business PCW vs Direct/Other."""
    if ch_data is None:
        return html.Div()
    ins = ch_data["insurer"]
    mkt = ch_data["market"]
    return html.Div([
        html.Div("Source of business", style={
            "fontSize": 10, "color": "#666", "textTransform": "uppercase",
            "letterSpacing": "0.5px", "marginBottom": 8,
        }),
        _mini_paired_bar("PCW", ins["pcw"], mkt["pcw"]),
        _mini_paired_bar("Direct / Other", ins["direct"], mkt["direct"]),
    ], style={
        "backgroundColor": "#FFF", "borderRadius": 8,
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "padding": "12px 16px", "fontFamily": FONT, "marginTop": 8,
    })


def _rank_badge(rank_data):
    """Sub-card: net movement rank among all insurers."""
    if rank_data is None:
        return html.Div()
    rank = rank_data["rank"]
    total = rank_data["total_brands"]
    position_pct = ((rank - 1) / max(total - 1, 1)) * 100

    # Quartile colour
    if rank <= total * 0.25:
        colour = CI_GREEN
        quartile = "Top quartile"
    elif rank <= total * 0.75:
        colour = CI_GREY
        quartile = "Mid range"
    else:
        colour = CI_RED
        quartile = "Bottom quartile"

    return html.Div([
        html.Div("Movement rank", style={
            "fontSize": 10, "color": "#666", "textTransform": "uppercase",
            "letterSpacing": "0.5px", "marginBottom": 6,
        }),
        html.Div(f"#{rank} of {total}", style={
            "fontSize": 20, "fontWeight": "bold", "color": colour,
            "marginBottom": 6,
        }),
        # Position indicator bar
        html.Div([
            html.Div(style={
                "position": "absolute", "left": f"{position_pct:.0f}%",
                "top": -2, "width": 10, "height": 14,
                "backgroundColor": colour, "borderRadius": 3,
                "transform": "translateX(-50%)",
            }),
        ], style={
            "position": "relative", "height": 10,
            "backgroundColor": CI_LIGHT_GREY, "borderRadius": 5,
            "marginBottom": 4,
        }),
        html.Div(quartile, style={"fontSize": 10, "color": colour, "fontStyle": "italic"}),
    ], style={
        "backgroundColor": "#FFF", "borderRadius": 8,
        "boxShadow": "0 1px 4px rgba(0,0,0,0.10)",
        "padding": "12px 16px", "fontFamily": FONT, "textAlign": "center",
        "marginTop": 8,
    })


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
    ], style={"fontFamily": FONT})


# Module-level placeholder updated per callback
insurer_label = "Insurer"


def _deep_dive_breakdown_row(label, ins_val, mkt_val):
    """Single row in deep-dive: label + insurer % + market %."""
    if ins_val is None and mkt_val is None:
        return html.Div()
    return html.Div([
        html.Span(label, style={"fontSize": 12, "color": "#4D5153", "minWidth": 120, "display": "inline-block"}),
        html.Span(
            _fmt_pct(ins_val) if ins_val is not None else "n<30",
            style={"fontSize": 12, "fontWeight": "bold", "color": CI_MAGENTA, "minWidth": 60, "display": "inline-block"},
        ),
        html.Span(
            f"Mkt {_fmt_pct(mkt_val)}" if mkt_val is not None else "Mkt n<30",
            style={"fontSize": 11, "color": CI_GREY},
        ),
    ], style={"marginBottom": 4})


def _deep_dive_content(metric_key, dd, ins_name):
    """Build the deep-dive panel content for a given metric."""
    panel_style = {
        "backgroundColor": "#FAFAFA", "borderRadius": 6,
        "padding": 16, "marginTop": 8, "marginBottom": 16,
        "borderLeft": f"3px solid {CI_MAGENTA}",
        "fontFamily": FONT,
    }

    if metric_key == "shopping":
        left = [html.Div("By premium change", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for pc_val, ins_rate, mkt_rate in dd.get("shop_by_premium", []):
            left.append(_deep_dive_breakdown_row(pc_val, ins_rate, mkt_rate))

        right = [html.Div("By age group", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for age, ins_rate, mkt_rate in dd.get("shop_by_age", []):
            right.append(_deep_dive_breakdown_row(age, ins_rate, mkt_rate))

        return html.Div([
            dbc.Row([
                dbc.Col(html.Div(left), width=6),
                dbc.Col(html.Div(right), width=6),
            ]),
        ], style=panel_style)

    if metric_key == "retention":
        left = [html.Div("By premium change", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for pc_val, ins_rate, mkt_rate in dd.get("ret_by_premium", []):
            left.append(_deep_dive_breakdown_row(pc_val, ins_rate, mkt_rate))

        right = [html.Div("By region", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for region, ins_rate, mkt_rate in dd.get("ret_by_region", []):
            right.append(_deep_dive_breakdown_row(region, ins_rate, mkt_rate))

        return html.Div([
            dbc.Row([
                dbc.Col(html.Div(left), width=6),
                dbc.Col(html.Div(right), width=6),
            ]),
        ], style=panel_style)

    if metric_key == "shopped_stayed":
        left = [html.Div("Premium change split", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for pc_val, ins_rate, mkt_rate in dd.get("shop_stay_by_premium", []):
            left.append(_deep_dive_breakdown_row(pc_val, ins_rate, mkt_rate))

        right = [html.Div("PCW usage", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        pcw = dd.get("shop_stay_pcw")
        if pcw:
            right.append(_deep_dive_breakdown_row(f"{ins_name}", pcw["insurer"], None))
            right.append(_deep_dive_breakdown_row("Market", pcw["market"], None))
        else:
            right.append(html.Div("Insufficient data", style={"fontSize": 11, "color": CI_GREY, "fontStyle": "italic"}))

        return html.Div([
            dbc.Row([
                dbc.Col(html.Div(left), width=6),
                dbc.Col(html.Div(right), width=6),
            ]),
        ], style=panel_style)

    if metric_key == "new_biz":
        left = [html.Div("Top source brands", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        for i, (brand, pct_val) in enumerate(dd.get("new_biz_sources", []), 1):
            left.append(html.Div([
                html.Span(f"{i}. {brand}", style={"fontSize": 12, "color": "#4D5153", "minWidth": 140, "display": "inline-block"}),
                html.Span(_fmt_pct(pct_val), style={"fontSize": 12, "fontWeight": "bold", "color": CI_MAGENTA}),
            ], style={"marginBottom": 4}))

        right = [html.Div("Channel", style={"fontSize": 12, "fontWeight": "bold", "marginBottom": 8, "color": "#4D5153"})]
        ch = dd.get("new_biz_channel")
        if ch:
            right.append(_deep_dive_breakdown_row("PCW", ch["insurer"], ch["market"]))
            right.append(_deep_dive_breakdown_row("Direct / Other", 1 - ch["insurer"], 1 - ch["market"]))
        else:
            right.append(html.Div("Insufficient data", style={"fontSize": 11, "color": CI_GREY, "fontStyle": "italic"}))

        return html.Div([
            dbc.Row([
                dbc.Col(html.Div(left), width=6),
                dbc.Col(html.Div(right), width=6),
            ]),
        ], style=panel_style)

    return html.Div()


def _comparison_bar_with_deepdive(label, ins_val, mkt_val, tag, metric_key, dd, ins_name, max_val=1.0):
    """Comparison bar with a 'Click for more' accordion deep-dive."""
    bar = _comparison_bar(label, ins_val, mkt_val, tag, max_val)
    btn_id = f"btn-deepdive-{metric_key}"
    collapse_id = f"collapse-deepdive-{metric_key}"

    return html.Div([
        # Bar + Click for more button
        html.Div([
            html.Div(bar, style={"flex": 1}),
            html.Button(
                "Click for more ▼",
                id=btn_id,
                n_clicks=0,
                style={
                    "background": "none", "border": "none", "cursor": "pointer",
                    "color": CI_MAGENTA, "fontSize": 11, "fontWeight": "bold",
                    "fontFamily": FONT, "whiteSpace": "nowrap", "padding": "0 0 0 12px",
                    "alignSelf": "flex-start", "marginTop": 2,
                },
            ),
        ], style={"display": "flex", "alignItems": "flex-start"}),
        # Collapsible deep dive
        dbc.Collapse(
            _deep_dive_content(metric_key, dd, ins_name),
            id=collapse_id,
            is_open=False,
        ),
    ], style={"marginBottom": 16})


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
# Data-driven narrative (always available — no API key needed)
# ---------------------------------------------------------------------------

def _gap_desc(ins_val, mkt_val, label, inverted=False):
    """Return a phrase describing how the insurer compares to market."""
    gap = (ins_val - mkt_val) * 100
    abs_gap = abs(gap)
    if abs_gap < NEUTRAL_GAP_THRESHOLD:
        return f"{label} is in line with the wider market"
    if inverted:
        # Shopping rate: higher is worse
        if gap > 0:
            return f"{label} is {abs_gap:.1f} pts above the market average, signalling higher churn intent"
        return f"{label} is {abs_gap:.1f} pts below market, suggesting less inclination to shop"
    else:
        if gap > 0:
            return f"{label} is {abs_gap:.1f} pts ahead of market ({ins_val * 100:.1f}% vs {mkt_val * 100:.1f}%)"
        return f"{label} is {abs_gap:.1f} pts behind market ({ins_val * 100:.1f}% vs {mkt_val * 100:.1f}%)"


def _build_data_narrative(d, ins, pre_pp, post_pp, delta_pp,
                          shop_tag, ret_tag, stay_tag, biz_tag):
    """Build headline, subtitle, and paragraph purely from the numbers."""

    # ── Headline: lead with net share outcome ──
    if delta_pp > NEUTRAL_GAP_THRESHOLD:
        headline = (
            f"{ins} grew share through renewal, up {delta_pp:.1f} pts "
            f"to {post_pp:.1f}%"
        )
    elif delta_pp < -NEUTRAL_GAP_THRESHOLD:
        headline = (
            f"{ins} lost share through renewal, down {abs(delta_pp):.1f} pts "
            f"to {post_pp:.1f}%"
        )
    else:
        headline = (
            f"{ins} held share steady through renewal at {post_pp:.1f}%"
        )

    # ── Subtitle: name the primary driver and the market context ──
    ret_gap = (d["retained_pct"] - d["mkt_retained_pct"]) * 100
    biz_gap = (d["new_biz_pct"] - d["mkt_new_biz_pct"]) * 100
    shop_gap = (d["shop_pct"] - d["mkt_shop_pct"]) * 100

    drivers = []
    if abs(ret_gap) >= NEUTRAL_GAP_THRESHOLD:
        word = "stronger" if ret_gap > 0 else "weaker"
        drivers.append(f"{word} retention")
    if abs(biz_gap) >= NEUTRAL_GAP_THRESHOLD:
        word = "higher" if biz_gap > 0 else "lower"
        drivers.append(f"{word} new business acquisition")

    if drivers:
        subtitle = f"Driven primarily by {' and '.join(drivers)}, relative to the market."
    else:
        subtitle = "Retention and acquisition are both broadly in line with the market average."

    # ── Paragraph: the full story with numbers ──
    sentences = []

    # 1. Outcome and magnitude
    if delta_pp > NEUTRAL_GAP_THRESHOLD:
        sentences.append(
            f"{ins} moved from {pre_pp:.1f}% to {post_pp:.1f}% share through "
            f"the renewal process — a net gain of {delta_pp:.1f} percentage points."
        )
    elif delta_pp < -NEUTRAL_GAP_THRESHOLD:
        sentences.append(
            f"{ins} moved from {pre_pp:.1f}% to {post_pp:.1f}% share through "
            f"the renewal process — a net loss of {abs(delta_pp):.1f} percentage points."
        )
    else:
        sentences.append(
            f"{ins} entered the renewal window at {pre_pp:.1f}% share and "
            f"emerged at {post_pp:.1f}%, holding broadly steady."
        )

    # 2. Shopping rate context (inverted metric)
    shop_ins = d["shop_pct"] * 100
    shop_mkt = d["mkt_shop_pct"] * 100
    if shop_gap > NEUTRAL_GAP_THRESHOLD:
        sentences.append(
            f"Shopping rate among {ins} customers is elevated at {shop_ins:.1f}% "
            f"versus {shop_mkt:.1f}% market-wide, indicating higher dissatisfaction "
            f"and churn intent than peers."
        )
    elif shop_gap < -NEUTRAL_GAP_THRESHOLD:
        sentences.append(
            f"Fewer {ins} customers shop around ({shop_ins:.1f}% vs "
            f"{shop_mkt:.1f}% market), suggesting relatively stronger satisfaction "
            f"at renewal."
        )
    else:
        sentences.append(
            f"Shopping rates are comparable to the market ({shop_ins:.1f}% vs "
            f"{shop_mkt:.1f}%), so the story plays out in what happens next."
        )

    # 3. Retention and shopped-and-stayed
    ret_ins = d["retained_pct"] * 100
    ret_mkt = d["mkt_retained_pct"] * 100
    stay_ins = d["shop_stay_pct"] * 100
    stay_mkt = d["mkt_shop_stay_pct"] * 100

    if ret_gap >= NEUTRAL_GAP_THRESHOLD:
        ret_phrase = f"Retention is a strength — {ret_ins:.1f}% of customers stay versus {ret_mkt:.1f}% market-wide"
    elif ret_gap <= -NEUTRAL_GAP_THRESHOLD:
        ret_phrase = f"Retention is a pressure point at {ret_ins:.1f}% versus {ret_mkt:.1f}% market"
    else:
        ret_phrase = f"Retention is in line with market at {ret_ins:.1f}%"

    stay_gap = (d["shop_stay_pct"] - d["mkt_shop_stay_pct"]) * 100
    if abs(stay_gap) >= NEUTRAL_GAP_THRESHOLD:
        stay_word = "outperforms" if stay_gap > 0 else "underperforms"
        ret_phrase += (
            f", and among those who do shop, {ins} {stay_word} "
            f"at converting them back ({stay_ins:.1f}% vs {stay_mkt:.1f}% market)"
        )
    ret_phrase += "."
    sentences.append(ret_phrase)

    # 4. New business — the offsetting or compounding factor
    biz_ins = d["new_biz_pct"] * 100
    biz_mkt = d["mkt_new_biz_pct"] * 100
    if biz_gap >= NEUTRAL_GAP_THRESHOLD:
        sentences.append(
            f"New business inflows provide a further boost, with {ins} "
            f"acquiring at {biz_ins:.1f}% versus {biz_mkt:.1f}% market — "
            f"explore the competitive exchange below to see where these "
            f"customers are coming from."
        )
    elif biz_gap <= -NEUTRAL_GAP_THRESHOLD:
        if biz_ins < 0.5:
            sentences.append(
                f"New business is negligible at {biz_ins:.1f}%, well below "
                f"the {biz_mkt:.1f}% market rate, leaving retention losses "
                f"largely unrecovered."
            )
        else:
            sentences.append(
                f"New business acquisition at {biz_ins:.1f}% trails the "
                f"{biz_mkt:.1f}% market rate, meaning inflows are not fully "
                f"offsetting any retention shortfall."
            )
    else:
        sentences.append(
            f"New business acquisition is broadly in line with the market "
            f"({biz_ins:.1f}% vs {biz_mkt:.1f}%)."
        )

    return {
        "headline": headline,
        "subtitle": subtitle,
        "paragraph": " ".join(sentences),
    }


# ---------------------------------------------------------------------------
# Page builder
# ---------------------------------------------------------------------------

def _build_headline_page(d, pc_data=None, ch_data=None, rank_data=None, dd=None, narrative=None):
    """Build the full headline story layout from metrics dict."""
    log.info("Building headline page: narrative=%s", "AI" if narrative else "fallback")
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

    # Narrative text: use AI-generated if available, else data-driven fallback
    fallback = _build_data_narrative(d, ins, pre_pp, post_pp, delta_pp,
                                     shop_tag, ret_tag, stay_tag, biz_tag)
    headline_text = narrative["headline"] if narrative else fallback["headline"]
    support = narrative["subtitle"] if narrative else fallback["subtitle"]
    why_text = narrative["paragraph"] if narrative else fallback["paragraph"]

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
            headline_text,
            style={
                "fontSize": 22, "fontWeight": "bold", "color": "#4D5153",
                "margin": "0 0 6px", "lineHeight": "1.3", "fontFamily": FONT,
            },
        ),
        html.P(support, style={
            "fontSize": 14, "color": CI_GREY, "margin": "0 0 16px",
            "lineHeight": "1.5", "fontFamily": FONT,
        }),

        # ── NARRATIVE PARAGRAPH ───────────────────────────────
        html.Div(
            html.P(why_text, style={
                "fontSize": 13, "color": "#4D5153", "margin": 0,
                "lineHeight": "1.65",
            }),
            style={
                "backgroundColor": "#F7F7F8", "borderRadius": 8,
                "borderLeft": f"3px solid {CI_MAGENTA}",
                "padding": "14px 18px", "marginBottom": 24,
                "fontFamily": FONT,
            },
        ),

        # ── OUTCOME (3-column grid: KPI card + sub-card) ─────
        html.Div([
            # Column 1: Pre-renewal share + Premium change
            html.Div([
                _share_card("Pre-renewal share", f"{pre_pp:.1f}%", "#4D5153"),
                _premium_change_card(pc_data, ins),
            ], style={"flex": "1 1 260px", "maxWidth": 280}),
            # Column 2: Net movement + Rank
            html.Div([
                _share_card(
                    "Net movement",
                    f"{delta_sign}{delta_pp:.1f} pts",
                    movement_colour,
                    border_top=movement_colour,
                ),
                _rank_badge(rank_data),
            ], style={"flex": "1 1 260px", "maxWidth": 280}),
            # Column 3: Post-renewal share + Source of business
            html.Div([
                _share_card("Post-renewal share", f"{post_pp:.1f}%", CI_MAGENTA),
                _source_of_business_card(ch_data, ins),
            ], style={"flex": "1 1 260px", "maxWidth": 280}),
        ], style={
            "display": "flex", "gap": 16, "marginBottom": 32,
            "justifyContent": "center", "flexWrap": "wrap",
        }),

        # ── WHY THIS HAPPENED (with deep-dive accordions) ────
        html.Div([
            html.Div("Why this happened", style={
                "fontSize": 15, "fontWeight": "bold", "color": "#4D5153", "marginBottom": 16,
            }),
            _comparison_bar_with_deepdive(
                "Shopping rate", d["shop_pct"], d["mkt_shop_pct"], shop_tag,
                "shopping", dd, ins,
            ),
            _comparison_bar_with_deepdive(
                "Retention", d["retained_pct"], d["mkt_retained_pct"], ret_tag,
                "retention", dd, ins,
            ),
            _comparison_bar_with_deepdive(
                "Shopped and stayed", d["shop_stay_pct"], d["mkt_shop_stay_pct"], stay_tag,
                "shopped_stayed", dd, ins,
            ),
            _comparison_bar_with_deepdive(
                "New business acquisition",
                d["new_biz_pct"], d["mkt_new_biz_pct"], biz_tag,
                "new_biz", dd, ins,
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
        dcc.Loading(
            id="headline-loading",
            type="dot",
            color=CI_MAGENTA,
            children=html.Div(id="headline-content"),
        ),
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

    # New metric computations
    pc_data = _calc_premium_change(df_mkt, insurer)
    ch_data = _calc_channel_comparison(df_mkt, insurer)
    rank_data = _calc_net_movement_rank(df_mkt, insurer)
    dd = _calc_deep_dive_data(df_mkt, insurer, d)

    # AI narrative generation
    log.info("Generating AI narrative for insurer=%s", insurer)
    narrative = generate_narrative(d)
    if narrative:
        log.info("AI narrative generated: headline=%r", narrative.get("headline", ""))
    else:
        log.warning("AI narrative returned None — using hardcoded fallback")

    return filter_bar_el, _build_headline_page(d, pc_data, ch_data, rank_data, dd, narrative=narrative)


# ---------------------------------------------------------------------------
# Deep-dive accordion toggle callbacks
# ---------------------------------------------------------------------------

def _make_toggle_callback(metric_key):
    """Factory for deep-dive accordion toggle callbacks."""
    @callback(
        Output(f"collapse-deepdive-{metric_key}", "is_open"),
        Input(f"btn-deepdive-{metric_key}", "n_clicks"),
        State(f"collapse-deepdive-{metric_key}", "is_open"),
        prevent_initial_call=True,
    )
    def toggle(n_clicks, is_open):
        return not is_open
    toggle.__name__ = f"toggle_{metric_key}"
    return toggle


_toggle_shopping = _make_toggle_callback("shopping")
_toggle_retention = _make_toggle_callback("retention")
_toggle_shopped_stayed = _make_toggle_callback("shopped_stayed")
_toggle_new_biz = _make_toggle_callback("new_biz")
