"""
Renewal Flow — Pre-Renewal → Renewal → Post-Renewal visual.
"""

import streamlit as st

from lib.analytics.demographics import apply_filters
from lib.config import CI_BLUE, CI_GREEN, CI_GREY, CI_MAGENTA, CI_RED
from lib.state import render_global_filters, get_ss_data

st.header("Renewal Flow")

FONT = "Verdana, Geneva, sans-serif"

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

if len(df_mkt) == 0:
    st.warning("No data for selected filters.")
    st.stop()


def _pct(n, d):
    return n / d if d > 0 else 0


def _fmt_pct(val, dp=1):
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"


# ---- Compute flow metrics ----
total = len(df_mkt)
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
    share_delta = after_share - pre_share

    heading = f"Renewal Flow \u2014 {insurer}"
    st.subheader(heading)
    if ins_total > 0:
        st.caption(f"Based on {ins_total} respondents")
else:
    pre_share = 1.0
    after_share = 1.0
    share_delta = 0
    ins_total = total
    ins_retained = len(non_shoppers) + len(shop_stay)
    st.subheader("Renewal Flow \u2014 Market View")


# ---- Build 3-column flow diagram ----
def _card_html(title, value, benchmark=None, color=CI_MAGENTA, icon=""):
    bench_line = f'<div style="font-size:9px; color:{CI_GREY};">({benchmark})</div>' if benchmark else ""
    bg_map = {CI_GREEN: "#F8FCF9", CI_RED: "#FDF5F5", CI_BLUE: "#F5F9FD", CI_MAGENTA: "#FBF5FB"}
    border_map = {CI_GREEN: "#B8DFC0", CI_RED: "#F0B8B8", CI_BLUE: "#B8D4EF", CI_MAGENTA: "#D4A8D3"}
    return (
        f'<div style="background:{bg_map.get(color, "#FFF")}; border-radius:7px; padding:8px 10px; '
        f'text-align:center; box-shadow:0 2px 8px rgba(0,0,0,0.10); '
        f'border:1.5px solid {border_map.get(color, "#D8DCE3")}; font-family:{FONT}; margin-bottom:8px;">'
        f'{f"<div style=font-size:18px>{icon}</div>" if icon else ""}'
        f'<div style="font-size:10px; font-weight:600; color:{color};">{title}</div>'
        f'<div style="font-size:16px; font-weight:700; color:{color};">{value}</div>'
        f'{bench_line}</div>'
    )


col_pre, col_ren, col_post = st.columns([2, 5, 5])

with col_pre:
    st.markdown(
        f'<div style="background:#ECEDF2; border-radius:8px 0 0 8px; padding:24px 12px; '
        f'min-height:400px; display:flex; flex-direction:column; align-items:center; justify-content:center;">'
        f'<div style="font-size:20px; margin-bottom:8px;">\u2709</div>'
        f'<div style="font-size:9px; color:{CI_GREY}; text-align:center; margin-bottom:16px;">Renewal notice</div>'
        f'<div style="background:transparent; border-radius:7px; padding:8px 10px; text-align:center; '
        f'border:2.5px solid {CI_GREEN};">'
        f'<div style="font-size:10px; font-weight:600; color:{CI_GREEN};">Pre-renewal share</div>'
        f'<div style="font-size:22px; font-weight:700; color:{CI_GREEN};">{_fmt_pct(pre_share)}</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

with col_ren:
    if insurer:
        new_biz_val = _fmt_pct(_pct(len(ins_new_biz), ins_total) if ins_total > 0 else 0)
        new_biz_bench = _fmt_pct(mkt_new_biz_pct)
        nonshop_val = _fmt_pct(_pct(len(ins_non_shop), len(ins_existing)) if len(ins_existing) > 0 else 0)
        nonshop_bench = _fmt_pct(mkt_nonshop_pct)
        shop_val = _fmt_pct(_pct(len(ins_shoppers), len(ins_existing)) if len(ins_existing) > 0 else 0)
        shop_bench = _fmt_pct(mkt_shop_pct)
        stay_val = _fmt_pct(_pct(len(ins_shop_stay), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0)
        stay_bench = _fmt_pct(mkt_shop_stay_pct)
        switch_val = _fmt_pct(_pct(len(ins_shop_switch), len(ins_shoppers)) if len(ins_shoppers) > 0 else 0)
        switch_bench = _fmt_pct(mkt_shop_switch_pct)
    else:
        new_biz_val = _fmt_pct(mkt_new_biz_pct)
        new_biz_bench = None
        nonshop_val = _fmt_pct(mkt_nonshop_pct)
        nonshop_bench = None
        shop_val = _fmt_pct(mkt_shop_pct)
        shop_bench = None
        stay_val = _fmt_pct(mkt_shop_stay_pct)
        stay_bench = None
        switch_val = _fmt_pct(mkt_shop_switch_pct)
        switch_bench = None

    st.markdown(
        _card_html("New business", new_biz_val, new_biz_bench, CI_MAGENTA, "\U0001F464+"),
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(_card_html("Non-shoppers", nonshop_val, nonshop_bench, CI_BLUE, "\U0001F4DE"), unsafe_allow_html=True)
    with c2:
        st.markdown(_card_html("Shoppers", shop_val, shop_bench, "#C47A00", "\U0001F6D2"), unsafe_allow_html=True)
    c3, c4 = st.columns(2)
    with c3:
        st.markdown(_card_html("Stayed", stay_val, stay_bench, CI_GREEN, "\U0001F49A"), unsafe_allow_html=True)
    with c4:
        st.markdown(_card_html("Switched", switch_val, switch_bench, CI_RED, "\U0001F504"), unsafe_allow_html=True)

with col_post:
    retained_pct = _pct(ins_retained, ins_total) if ins_total > 0 else 0
    st.markdown(
        _card_html("Retained", _fmt_pct(retained_pct), _fmt_pct(mkt_retained_pct) if insurer else None, CI_GREEN, "\u2705"),
        unsafe_allow_html=True,
    )

    delta_sign = "+" if share_delta > 0 else ""
    delta_bg = "#D4EDDA" if share_delta > 0 else ("#FDDEDE" if share_delta < 0 else CI_GREY)
    delta_col = CI_GREEN if share_delta > 0 else (CI_RED if share_delta < 0 else CI_GREY)
    delta_badge = (
        f'<span style="font-size:9px; font-weight:700; padding:1px 6px; border-radius:8px; '
        f'background:{delta_bg}; color:{delta_col};">{delta_sign}{share_delta * 100:.1f}%</span>'
        if share_delta != 0 else ""
    )

    st.markdown(
        f'<div style="background:#F8FCF9; border-radius:7px; padding:8px 10px; text-align:center; '
        f'box-shadow:0 2px 8px rgba(0,0,0,0.10); border:1.5px solid #B8DFC0; margin-bottom:8px;">'
        f'<div style="font-size:10px; font-weight:600; color:{CI_GREEN};">After renewal share</div>'
        f'<div style="font-size:22px; font-weight:700; color:{CI_GREEN};">{_fmt_pct(after_share)}</div>'
        f'{delta_badge}</div>',
        unsafe_allow_html=True,
    )

    # Won from / Lost to
    if insurer:
        switchers_to = df_mkt[
            (df_mkt["IsSwitcher"]) & (df_mkt["CurrentCompany"] == insurer) & (df_mkt["PreviousCompany"] != insurer)
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

        lost_switchers = df_mkt[(df_mkt["IsSwitcher"]) & (df_mkt["PreviousCompany"] == insurer)]
        lost_counts = {}
        for _, r in lost_switchers.iterrows():
            b = r.get("CurrentCompany", "Other")
            lost_counts[b] = lost_counts.get(b, 0) + 1
        total_lost = len(lost_switchers)
        lost_to = sorted(lost_counts.items(), key=lambda x: -x[1])[:3]
        lost_to = [(b, _pct(c, total_lost)) for b, c in lost_to] if total_lost > 0 else []

        if won_from:
            st.markdown(f"**Won from** (top 3)")
            for b, p in won_from:
                st.markdown(f"- {b}: **{_fmt_pct(p)}**")
        if lost_to:
            st.markdown(f"**Lost to** (top 3)")
            for b, p in lost_to:
                st.markdown(f"- {b}: **{_fmt_pct(p)}**")

# Phase labels
c1, c2, c3 = st.columns([2, 5, 5])
with c1:
    st.caption("PRE-RENEWAL")
with c2:
    st.caption("RENEWAL")
with c3:
    st.caption("POST-RENEWAL")
