"""
Session state management for the unified Streamlit dashboard.

Handles data loading from Power BI, transformation, and filter application.
All pages read from st.session_state rather than loading data independently.
"""

import datetime
import logging

import pandas as pd
import streamlit as st

audit_log = logging.getLogger("ehubot.audit")
audit_log.setLevel(logging.DEBUG)

from lib.analytics.demographics import apply_filters
from lib.analytics.dimensions import get_all_dimensions
from lib.analytics.pivot import pivot_questions_to_wide
from lib.analytics.transforms import transform
from lib.config import (
    MAIN_TABLE, OTHER_TABLE,
    MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
    HOME_WORKSPACE_ID, HOME_DATASET_ID,
    PET_WORKSPACE_ID, PET_DATASET_ID,
    PRODUCTS,
)
from lib.db import save_dataframe, load_dataframe, has_data, clear_data, save_metadata, load_metadata
from lib.powerbi import (
    load_months, load_ss_maindata, load_ss_questions, load_q52, load_q53,
    load_pet_quarters, load_pet_maindata, load_pet_questions,
)


_MONTH_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def format_month(yyyymm: int) -> str:
    """Convert integer YYYYMM to 'Mon YYYY' label."""
    y = yyyymm // 100
    m = yyyymm % 100
    try:
        return datetime.date(y, m, 1).strftime("%b %Y")
    except ValueError:
        return str(yyyymm)


def format_year_month(ym) -> str:
    """Convert YYYYMM (e.g. 202401) to readable label (e.g. 'Jan 2024')."""
    if pd.isna(ym) or ym is None:
        return ""
    ym = int(float(ym))
    y, m = ym // 100, ym % 100
    if 1 <= m <= 12:
        return f"{_MONTH_ABBR[m]} {y}"
    return str(ym)


def format_quarter(yyyymm: int) -> str:
    """Convert YYYYMM (last month of quarter) to 'QN YYYY' label."""
    y = yyyymm // 100
    m = yyyymm % 100
    q = (m - 1) // 3 + 1
    return f"Q{q} {y}"


def _load_product_data(token: str, product: str, start_month: int, end_month: int,
                       main_table: str, other_table: str,
                       workspace_id: str, dataset_id: str,
                       log_fn=None):
    """Load and transform data for a single product, with wide question columns merged in."""
    def _log(msg):
        audit_log.info("[%s] %s", product, msg)
        if log_fn:
            log_fn(f"[{product}] {msg}")

    _log(f"Loading MainData ({main_table}) months {start_month}-{end_month}")
    df_raw = load_ss_maindata(
        token, start_month, end_month, main_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    _log(f"MainData returned {len(df_raw)} rows, {len(df_raw.columns)} cols")
    if df_raw.empty:
        _log("EMPTY MainData — skipping product")
        return pd.DataFrame()

    df = transform(df_raw, product)
    _log(f"After transform: {len(df)} rows, {len(df.columns)} cols")

    # Load EAV question data, pivot to wide, and merge onto main
    _log(f"Loading OtherData ({other_table}) for EAV questions")
    df_q = load_ss_questions(
        token, start_month, end_month, main_table, other_table,
        workspace_id=workspace_id, dataset_id=dataset_id,
    )
    _log(f"OtherData returned {len(df_q)} rows")
    if not df_q.empty:
        df_q["UniqueID"] = df_q["UniqueID"].astype(str)
        df_q["Answer"] = df_q["Answer"].astype(str).str.strip()
        df_q["Product"] = product

        wide = pivot_questions_to_wide(df_q)
        _log(f"Pivot produced {len(wide)} rows, {len(wide.columns)} wide cols")
        if not wide.empty:
            existing = set(df.columns)
            overlap = [c for c in wide.columns if c in existing]
            if overlap:
                _log(f"Dropping {len(overlap)} overlapping cols: {overlap[:5]}")
                wide = wide.drop(columns=overlap)
            if not wide.empty:
                df = df.merge(wide, left_on="UniqueID", right_index=True, how="left")
                _log(f"After merge: {len(df)} rows, {len(df.columns)} cols")

    _log(f"DONE — {len(df)} rows")
    return df


def _load_pet_data(token: str, pet_quarters: list[str], log_fn=None) -> pd.DataFrame:
    """Load and transform Pet insurance data from its own dataset."""
    def _log(msg):
        audit_log.info("[Pet] %s", msg)
        if log_fn:
            log_fn(f"[Pet] {msg}")

    _log(f"Loading Pet MainData for quarters {pet_quarters}")
    df_raw = load_pet_maindata(
        token, pet_quarters,
        workspace_id=PET_WORKSPACE_ID, dataset_id=PET_DATASET_ID,
    )
    _log(f"Pet MainData returned {len(df_raw)} rows")
    if df_raw.empty:
        _log("EMPTY Pet MainData — skipping product")
        return pd.DataFrame()

    df = transform(df_raw, "Pet")
    _log(f"After transform: {len(df)} rows, {len(df.columns)} cols")

    _log("Loading Pet OtherData for EAV questions")
    df_q = load_pet_questions(
        token, pet_quarters,
        workspace_id=PET_WORKSPACE_ID, dataset_id=PET_DATASET_ID,
    )
    _log(f"Pet OtherData returned {len(df_q)} rows")
    if not df_q.empty:
        df_q["UniqueID"] = df_q["UniqueID"].astype(str)
        df_q["Answer"] = df_q["Answer"].astype(str).str.strip()
        df_q["Product"] = "Pet"

        wide = pivot_questions_to_wide(df_q, product="Pet")
        _log(f"Pivot produced {len(wide)} rows, {len(wide.columns)} wide cols")
        if not wide.empty:
            existing = set(df.columns)
            overlap = [c for c in wide.columns if c in existing]
            if overlap:
                _log(f"Dropping {len(overlap)} overlapping cols")
                wide = wide.drop(columns=overlap)
            if not wide.empty:
                df = df.merge(wide, left_on="UniqueID", right_index=True, how="left")
                _log(f"After merge: {len(df)} rows, {len(df.columns)} cols")

    _log(f"DONE — {len(df)} rows")
    return df


def init_ss_data(token: str, start_month: int, end_month: int,
                 main_table: str = MAIN_TABLE, other_table: str = OTHER_TABLE,
                 home_main_table: str = MAIN_TABLE, home_other_table: str = OTHER_TABLE,
                 pet_quarters: list[str] | None = None,
                 log_fn=None):
    """Load S&S data from Power BI for all products, transform, and store in session state."""
    def _log(msg):
        audit_log.info(msg)
        if log_fn:
            log_fn(msg)

    _log(f"=== REFRESH START: months {start_month}-{end_month} ===")

    # Load motor data
    _log("--- Loading Motor ---")
    df_motor = _load_product_data(
        token, "Motor", start_month, end_month,
        main_table, other_table,
        MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID,
        log_fn=log_fn,
    )

    # Load home data
    _log("--- Loading Home ---")
    df_home = _load_product_data(
        token, "Home", start_month, end_month,
        home_main_table, home_other_table,
        HOME_WORKSPACE_ID, HOME_DATASET_ID,
        log_fn=log_fn,
    )

    # Load pet data — wrapped in try/except so Motor/Home still save on failure
    df_pet = pd.DataFrame()
    if pet_quarters:
        _log("--- Loading Pet ---")
        try:
            df_pet = _load_pet_data(token, pet_quarters, log_fn=log_fn)
        except Exception as e:
            _log(f"ERROR loading Pet data: {e}")
            audit_log.exception("Pet data load failed")
            df_pet = pd.DataFrame()
    else:
        _log("--- Pet: no quarters provided, skipping ---")

    # Combine products
    frames = [df for df in [df_motor, df_home, df_pet] if not df.empty]
    _log(f"Combining {len(frames)} non-empty product frames")
    if frames:
        df_all = pd.concat(frames, ignore_index=True)
    else:
        df_all = pd.DataFrame()

    _log(f"Combined DataFrame: {len(df_all)} rows, {len(df_all.columns)} cols")
    st.session_state["df_motor"] = df_all

    if not df_all.empty:
        st.session_state["dimensions"] = get_all_dimensions(df_all)
        _log("Saving to DuckDB cache...")
        save_dataframe(df_all, "df_motor")
        save_metadata("start_month", str(start_month))
        save_metadata("end_month", str(end_month))
        _log("DuckDB save complete")
    else:
        st.session_state["dimensions"] = {}
        _log("WARNING: Combined DataFrame is EMPTY — nothing saved to DuckDB")

    # ---- Pull and cache Claims data (Q52/Q53) per product ----
    for product_key, ws_id, ds_id, mt, ot in [
        ("motor", MOTOR_WORKSPACE_ID, MOTOR_DATASET_ID, main_table, other_table),
        ("home", HOME_WORKSPACE_ID, HOME_DATASET_ID, home_main_table, home_other_table),
    ]:
        _log(f"Loading Claims Q52/Q53 for {product_key}")
        q52 = load_q52(token, start_month, end_month, mt, ot,
                        workspace_id=ws_id, dataset_id=ds_id)
        q53 = load_q53(token, start_month, end_month, mt, ot,
                        workspace_id=ws_id, dataset_id=ds_id)
        _log(f"  Q52 {product_key}: {len(q52)} rows, Q53 {product_key}: {len(q53)} rows")
        if not q52.empty:
            save_dataframe(q52, f"claims_q52_{product_key}")
            st.session_state[f"claims_q52_{product_key}"] = q52
        if not q53.empty:
            save_dataframe(q53, f"claims_q53_{product_key}")
            st.session_state[f"claims_q53_{product_key}"] = q53

    _log(f"=== REFRESH COMPLETE: {len(df_all)} total rows ===")


def load_from_db(start_month: int | None = None, end_month: int | None = None) -> bool:
    """Attempt to load data from local DuckDB cache.

    Always loads if cached data exists. The time window parameters are
    optional — if provided and they don't match the cache, returns False.
    If omitted, loads whatever is cached regardless of time window.
    """
    audit_log.info("load_from_db: checking DuckDB for cached data")
    if not has_data("df_motor"):
        audit_log.info("load_from_db: no df_motor table in DuckDB — cache miss")
        return False

    # If time window specified, check it matches
    if start_month is not None and end_month is not None:
        cached_start = load_metadata("start_month")
        cached_end = load_metadata("end_month")
        if cached_start != str(start_month) or cached_end != str(end_month):
            audit_log.info("load_from_db: time window mismatch (wanted %s-%s, cached %s-%s)",
                           start_month, end_month, cached_start, cached_end)
            return False

    df_all = load_dataframe("df_motor")
    if df_all.empty:
        audit_log.info("load_from_db: df_motor table exists but returned empty DataFrame")
        return False

    audit_log.info("load_from_db: loaded %d rows, %d cols from DuckDB", len(df_all), len(df_all.columns))

    # Ensure derived columns exist (may be missing from older caches)
    if "How much higher" in df_all.columns and "Q6a" not in df_all.columns:
        df_all["Q6a"] = df_all["How much higher"]
    if "How much lower" in df_all.columns and "Q6b" not in df_all.columns:
        df_all["Q6b"] = df_all["How much lower"]

    st.session_state["df_motor"] = df_all
    st.session_state["dimensions"] = get_all_dimensions(df_all)

    # Restore cached time window to session state
    cached_start = load_metadata("start_month")
    cached_end = load_metadata("end_month")
    if cached_start:
        st.session_state["cached_start_month"] = int(cached_start)
    if cached_end:
        st.session_state["cached_end_month"] = int(cached_end)
    audit_log.info("load_from_db: period %s to %s", cached_start, cached_end)

    # Restore cached claims data
    for product_key in ("motor", "home"):
        for q_key in ("q52", "q53"):
            table = f"claims_{q_key}_{product_key}"
            if has_data(table):
                df_claims = load_dataframe(table)
                if not df_claims.empty:
                    st.session_state[table] = df_claims
                    audit_log.info("load_from_db: restored %s (%d rows)", table, len(df_claims))

    audit_log.info("load_from_db: cache restore complete")
    return True


def ensure_data_loaded():
    """Load cached data from DuckDB into session state if not already present.

    Called automatically by get_ss_data() so every page benefits from the cache
    even if the user navigates directly to a subpage without visiting Home first.
    """
    if st.session_state.get("data_loaded", False):
        return
    if has_data("df_motor"):
        audit_log.info("ensure_data_loaded: session state empty, restoring from DuckDB")
        loaded = load_from_db()
        if loaded:
            st.session_state["data_loaded"] = True
            # Derive time window (mirrors app.py logic)
            cached_start = st.session_state.get("cached_start_month")
            cached_end = st.session_state.get("cached_end_month")
            if cached_start and cached_end:
                st.session_state["start_month"] = cached_start
                st.session_state["end_month"] = cached_end
            else:
                df = st.session_state.get("df_motor")
                if df is not None and not df.empty and "RenewalYearMonth" in df.columns:
                    months = sorted(df["RenewalYearMonth"].dropna().unique().astype(int).tolist())
                    if months:
                        st.session_state["start_month"] = months[max(0, len(months) - 12)]
                        st.session_state["end_month"] = months[-1]
            audit_log.info("ensure_data_loaded: restore complete")


def get_ss_data():
    """Get S&S dataframes from session state.

    Returns (df_motor, dimensions). All question data is merged into df_motor
    as wide columns — there is no separate df_questions table.
    Automatically loads from DuckDB cache if session state is empty.
    """
    ensure_data_loaded()
    return (
        st.session_state.get("df_motor", pd.DataFrame()),
        st.session_state.get("dimensions", {}),
    )


def get_filtered_data(
    insurer: str | None = None,
    age_band: str | None = None,
    region: str | None = None,
    payment_type: str | None = None,
    product: str = "Motor",
    selected_months: list[int] | None = None,
):
    """Apply filters and return (df_insurer, df_market) tuple."""
    df_motor = st.session_state.get("df_motor", pd.DataFrame())
    if df_motor.empty:
        return pd.DataFrame(), pd.DataFrame()

    df_mkt = apply_filters(
        df_motor, insurer=None, age_band=age_band, region=region,
        payment_type=payment_type, product=product, selected_months=selected_months,
    )
    df_ins = apply_filters(
        df_motor, insurer=insurer, age_band=age_band, region=region,
        payment_type=payment_type, product=product, selected_months=selected_months,
    ) if insurer else df_mkt

    return df_ins, df_mkt


def navigate_to(screen: str, **kwargs):
    """Navigate to a different screen, optionally setting cross-screen filters.

    Usage:
        navigate_to("switching", flow_filter={"from": "Admiral", "to": "Churchill"})
    """
    st.session_state["active_screen"] = screen
    for key, value in kwargs.items():
        st.session_state[key] = value
    st.rerun()


def render_dual_period_selector() -> dict | None:
    """
    Render dual period selector for the Brand Awareness tab (Change 1).

    Returns dict with keys:
      period_a_months, period_b_months, period_a_label, period_b_label,
      caption
    Or None if insufficient data to build the selector.
    """
    df_motor = st.session_state.get("df_motor", pd.DataFrame())
    if df_motor.empty or "RenewalYearMonth" not in df_motor.columns:
        return None

    all_months = sorted(
        df_motor["RenewalYearMonth"].dropna().unique().astype(int).tolist()
    )
    if len(all_months) < 2:
        return None

    month_labels = {m: format_month(m) for m in all_months}

    st.sidebar.markdown("---")
    st.sidebar.subheader("Period Comparison")

    # ---- Compute smart defaults ----
    # Period B (current): last 3 months of available data
    default_b_end = all_months[-1]
    default_b_start_idx = max(0, len(all_months) - 3)
    default_b_start = all_months[default_b_start_idx]

    # Period A (baseline): same 3 months one year earlier, or earliest 3 months
    b_start_y = default_b_start // 100
    b_start_m = default_b_start % 100
    b_end_y = default_b_end // 100
    b_end_m = default_b_end % 100
    target_a_start = (b_start_y - 1) * 100 + b_start_m
    target_a_end = (b_end_y - 1) * 100 + b_end_m

    # Find closest available months to the year-ago targets
    months_before_b = [m for m in all_months if m < default_b_start]
    if months_before_b:
        # Try to find year-ago window
        a_start_candidates = [m for m in months_before_b if m <= target_a_start]
        a_end_candidates = [m for m in months_before_b if m <= target_a_end]
        if a_start_candidates and a_end_candidates:
            # Year-ago data exists — use closest matches
            default_a_start = min(months_before_b, key=lambda m: abs(m - target_a_start))
            default_a_end = min(months_before_b, key=lambda m: abs(m - target_a_end))
            if default_a_start > default_a_end:
                default_a_start, default_a_end = default_a_end, default_a_start
        else:
            # No year-ago data — use first 3 available months
            default_a_start = months_before_b[0]
            default_a_end = months_before_b[min(2, len(months_before_b) - 1)]
    else:
        default_a_start = all_months[0]
        default_a_end = all_months[min(2, len(all_months) - 1)]

    # Period A — Comparison period (baseline)
    st.sidebar.markdown("**Comparison period** (baseline)")

    period_a_start, period_a_end = st.sidebar.select_slider(
        "Comparison period",
        options=all_months,
        value=(default_a_start, default_a_end),
        format_func=lambda x: month_labels.get(x, str(x)),
        key="period_a_slider",
    )

    # Period B — Current period
    st.sidebar.markdown("**Current period** (now)")

    # Filter months that come after Period A end
    b_options = [m for m in all_months if m > period_a_end]
    if not b_options:
        st.sidebar.error("Current period must follow comparison period.")
        return None

    # Clamp Period B defaults to available options
    default_b_start_clamped = default_b_start if default_b_start in b_options else b_options[0]
    default_b_end_clamped = default_b_end if default_b_end in b_options else b_options[-1]

    period_b_start, period_b_end = st.sidebar.select_slider(
        "Current period",
        options=b_options,
        value=(default_b_start_clamped, default_b_end_clamped),
        format_func=lambda x: month_labels.get(x, str(x)),
        key="period_b_slider",
    )

    # Build month lists
    period_a_months = [m for m in all_months if period_a_start <= m <= period_a_end]
    period_b_months = [m for m in all_months if period_b_start <= m <= period_b_end]

    # Validation: at least one complete survey month each
    if not period_a_months or not period_b_months:
        st.sidebar.error("Select at least one full survey month for each period.")
        return None

    # Validation: no overlap
    if period_a_end >= period_b_start:
        st.sidebar.error("Periods overlap. Please adjust your selection.")
        return None

    period_a_label = f"{format_month(period_a_months[0])} to {format_month(period_a_months[-1])}"
    period_b_label = f"{format_month(period_b_months[0])} to {format_month(period_b_months[-1])}"
    caption = f"Comparison period: {period_a_label} | Current period: {period_b_label}"

    return {
        "period_a_months": period_a_months,
        "period_b_months": period_b_months,
        "period_a_label": period_a_label,
        "period_b_label": period_b_label,
        "caption": caption,
    }
