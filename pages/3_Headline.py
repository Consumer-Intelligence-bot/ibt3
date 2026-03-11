"""
Headline — Share Through Renewal story page with AI narrative.
"""

import plotly.graph_objects as go
import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.config import CI_GREEN, CI_GREY, CI_LIGHT_GREY, CI_MAGENTA, CI_RED, NEUTRAL_GAP_THRESHOLD
from lib.narrative import generate_narrative
from lib.state import render_global_filters, get_ss_data

st.header("Headline")

FONT = "Verdana, Geneva, sans-serif"

# ---- Filters ----
filters = render_global_filters()
df_motor, df_questions, dimensions = get_ss_data()

if df_motor.empty:
    st.warning("No S&S data loaded.")
    st.stop()

insurer = filters["insurer"]
product = filters["product"]
selected_months = filters["selected_months"]

df_mkt = apply_filters(
    df_motor, insurer=None, age_band=filters["age_band"], region=filters["region"],
    payment_type=filters["payment_type"], product=product, selected_months=selected_months,
)

if not insurer:
    st.info("Select an insurer in the sidebar to view the headline story.")
    st.stop()

if len(df_mkt) == 0:
    st.warning("No data for selected filters.")
    st.stop()


# ---- Metrics ----
def _pct(n, d):
    return n / d if d > 0 else 0


def _fmt_pct(val, dp=1):
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"


def _derive_tag(ins_val, mkt_val):
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


total = len(df_mkt)
existing = df_mkt[~df_mkt["IsNewToMarket"]]
new_to_market = df_mkt[df_mkt["IsNewToMarket"]]
shoppers = existing[existing["IsShopper"]]
non_shoppers = existing[~existing["IsShopper"]]
shop_stay = shoppers[shoppers["IsRetained"]]
shop_switch = shoppers[shoppers["IsSwitcher"]]

mkt_shop_pct = _pct(len(shoppers), len(existing)) if len(existing) > 0 else 0
mkt_new_biz_pct = _pct(len(new_to_market), total)
mkt_shop_stay_pct = _pct(len(shop_stay), len(shoppers)) if len(shoppers) > 0 else 0
mkt_retained_pct = _pct(len(non_shoppers) + len(shop_stay), total)

ins_existing = existing[existing["PreviousCompany"] == insurer]
ins_new_biz = new_to_market[new_to_market["CurrentCompany"] == insurer]
ins_non_shop = ins_existing[~ins_existing["IsShopper"]]
ins_shoppers = ins_existing[ins_existing["IsShopper"]]
ins_shop_stay = ins_shoppers[ins_shoppers["IsRetained"]]
ins_shop_switch = ins_shoppers[ins_shoppers["IsSwitcher"]]
ins_total = len(ins_existing) + len(ins_new_biz)
ins_retained = len(ins_non_shop) + len(ins_shop_stay)

# Inbound switching — customers who switched FROM other brands TO this insurer
ins_inbound = df_mkt[
    (df_mkt["IsSwitcher"]) & (df_mkt["CurrentCompany"] == insurer) & (df_mkt["PreviousCompany"] != insurer)
]
after_all = len(df_mkt[df_mkt["CurrentCompany"] == insurer])
mkt_inbound_pct = _pct(len(shop_switch), total)

if ins_total == 0:
    st.warning(f"No data for {insurer} in this selection.")
    st.stop()

pre_share = _pct(len(ins_existing), total)
after_count = len(df_mkt[df_mkt["CurrentCompany"] == insurer])
after_share = _pct(after_count, total)
share_delta = after_share - pre_share

metrics = {
    "insurer": insurer,
    "pre_share": pre_share,
    "after_share": after_share,
    "share_delta": share_delta,
    "shop_pct": _pct(len(ins_shoppers), len(ins_existing)) if len(ins_existing) > 0 else 0,
    "mkt_shop_pct": mkt_shop_pct,
    "retained_pct": _pct(ins_retained, ins_total) if ins_total > 0 else 0,
    "mkt_retained_pct": mkt_retained_pct,
    "shop_stay_pct": _pct(len(ins_shop_stay), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
    "mkt_shop_stay_pct": mkt_shop_stay_pct,
    "shop_switch_pct": _pct(len(ins_shop_switch), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0,
    "mkt_shop_switch_pct": _pct(len(shop_switch), len(shoppers)) if len(shoppers) > 0 else 0,
    "new_biz_pct": _pct(len(ins_new_biz), ins_total) if ins_total > 0 else 0,
    "mkt_new_biz_pct": mkt_new_biz_pct,
    "inbound_switch_pct": _pct(len(ins_inbound), after_all) if after_all > 0 else 0,
    "mkt_inbound_switch_pct": mkt_inbound_pct,
    "n": total,
}

# ---- AI Narrative ----
narrative = generate_narrative(metrics)

if narrative:
    st.markdown(f"### {narrative['headline']}")
    st.markdown(f"*{narrative['subtitle']}*")
    st.markdown(narrative["paragraph"])
else:
    direction = "lifting" if share_delta > 0 else ("dropping" if share_delta < 0 else "holding")
    st.markdown(f"### Customers shop at the market rate, but {insurer} keeps more of them")
    st.markdown(
        f"*Retention and acquisition both beat market, {direction} share "
        f"from {pre_share * 100:.1f}% to {after_share * 100:.1f}% through renewal.*"
    )

st.markdown("---")

# ---- Outcome Cards ----
pre_pp = pre_share * 100
post_pp = after_share * 100
delta_pp = share_delta * 100
delta_sign = "+" if delta_pp >= 0 else ""
movement_colour = CI_GREEN if delta_pp > 0 else (CI_RED if delta_pp < 0 else CI_GREY)

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Pre-renewal share", f"{pre_pp:.1f}%")
with col2:
    st.metric("Net movement", f"{delta_sign}{delta_pp:.1f} pts", delta_color="normal")
with col3:
    st.metric("Post-renewal share", f"{post_pp:.1f}%")

# ---- Comparison bars with deep dives ----
st.markdown("### Why this happened")

descriptions = narrative.get("descriptions", {}) if narrative else {}

comparison_metrics = [
    ("Shopping rate", metrics["shop_pct"], metrics["mkt_shop_pct"], "shopping_rate"),
    ("Retention", metrics["retained_pct"], metrics["mkt_retained_pct"], "retention"),
    ("Shopped and stayed", metrics["shop_stay_pct"], metrics["mkt_shop_stay_pct"], "shopped_and_stayed"),
    ("New business acquisition", metrics["new_biz_pct"], metrics["mkt_new_biz_pct"], "new_business"),
    ("Inbound switching", metrics["inbound_switch_pct"], metrics["mkt_inbound_switch_pct"], "inbound_switching"),
]

for label, ins_val, mkt_val, desc_key in comparison_metrics:
    tag = _derive_tag(ins_val, mkt_val)
    tag_col = _tag_colour(tag)

    max_val = max(ins_val, mkt_val, 0.01)
    ins_w = (ins_val / max_val) * 100
    mkt_w = (mkt_val / max_val) * 100

    with st.expander(f"**{label}** — {insurer}: {_fmt_pct(ins_val)} vs Market: {_fmt_pct(mkt_val)} — *{tag}*"):
        desc = descriptions.get(desc_key)
        if desc:
            st.markdown(desc)
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=[f"{insurer}", "Market"],
            x=[ins_val, mkt_val],
            orientation="h",
            marker_color=[CI_MAGENTA, CI_GREY],
            text=[_fmt_pct(ins_val), _fmt_pct(mkt_val)],
            textposition="outside",
        ))
        fig.update_layout(
            height=120, margin=dict(l=150, r=50, t=10, b=10),
            xaxis_tickformat=".0%", showlegend=False,
            font=dict(family="Verdana"), plot_bgcolor="white", paper_bgcolor="white",
        )
        st.plotly_chart(fig, width="stretch")

# ---- Competitive Exchange (Butterfly) ----
st.markdown("### Competitive exchange")

# Won from
switchers_to = ins_inbound
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
lost_switchers = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
lost_counts = {}
for _, r in lost_switchers.iterrows():
    b = r.get("CurrentCompany", "Other")
    lost_counts[b] = lost_counts.get(b, 0) + 1
total_lost = len(lost_switchers)
lost_to = sorted(lost_counts.items(), key=lambda x: -x[1])[:3]
lost_to = [(b, _pct(c, total_lost)) for b, c in lost_to] if total_lost > 0 else []

col_won, col_lost = st.columns(2)
with col_won:
    st.markdown(f"**Won from**")
    for brand, pct in won_from:
        st.markdown(f"- {brand}: **{_fmt_pct(pct)}**")

with col_lost:
    st.markdown(f"**Lost to**")
    for brand, pct in lost_to:
        st.markdown(f"- {brand}: **{_fmt_pct(pct)}**")

# ---- Footer ----
st.caption(f"Base: {total:,} respondents")
