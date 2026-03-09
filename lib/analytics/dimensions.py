"""
Build dimension tables: AgeBand, Region, PaymentType, Insurer.
Used for filter dropdowns with sort order and display labels.
"""
import pandas as pd

# Spec order for age bands
AGE_BAND_ORDER = ["17-24", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

# Spec order for regions (UK-focused)
REGION_ORDER = [
    "uk",
    "england",
    "london",
    "south east",
    "south west",
    "midlands",
    "east anglia",
    "north west",
    "north east & yorkshire",
    "scotland",
    "wales",
    "ni",
]

# Payment type order
PAYMENT_ORDER = ["All", "Annual", "Monthly", "Other"]


def _build_dim(
    df: pd.DataFrame, col: str, key: str, order: list[str], all_label: str
) -> pd.DataFrame:
    """Build dimension DataFrame with SortOrder and Label. key = e.g. AgeBand, Region."""
    if col not in df.columns or df[col].isna().all():
        return pd.DataFrame({key: [None], "value": [None], "label": [all_label], "SortOrder": [0]})

    values = df[col].dropna().astype(str).str.strip().unique()
    values = [v for v in values if v and v.lower() != "nan"]

    rows = []
    for i, v in enumerate(sorted(values, key=lambda x: _sort_key(x, order))):
        rows.append({key: v, "value": v, "label": v, "SortOrder": i + 1})

    # Prepend "All" option
    rows.insert(0, {key: None, "value": None, "label": all_label, "SortOrder": 0})
    return pd.DataFrame(rows)


def _sort_key(val: str, order: list[str]) -> int:
    """Sort key: position in order list, else 999."""
    v_lower = val.lower()
    for i, o in enumerate(order):
        if o.lower() in v_lower or v_lower in o.lower():
            return i
    return 999


def get_dim_age_band(df: pd.DataFrame) -> pd.DataFrame:
    """DimAgeBand with SortOrder. First option = All Ages."""
    return _build_dim(df, "AgeBand", "AgeBand", AGE_BAND_ORDER, "All Ages")


def get_dim_region(df: pd.DataFrame) -> pd.DataFrame:
    """DimRegion with SortOrder. First option = All Regions."""
    return _build_dim(df, "Region", "Region", REGION_ORDER, "All Regions")


def get_dim_payment_type(df: pd.DataFrame) -> pd.DataFrame:
    """DimPaymentType with SortOrder. First option = All Payment Types."""
    return _build_dim(df, "PaymentType", "PaymentType", PAYMENT_ORDER, "All Payment Types")


def get_dim_insurer(df: pd.DataFrame) -> pd.DataFrame:
    """DimInsurer: unique CurrentCompany, sorted alphabetically."""
    if df is None or len(df) == 0 or "CurrentCompany" not in df.columns:
        return pd.DataFrame({"Insurer": [], "value": [], "label": [], "SortOrder": []})

    insurers = df["CurrentCompany"].dropna().astype(str).str.strip().unique()
    insurers = sorted([i for i in insurers if i and i.lower() != "nan"])

    rows = [
        {"Insurer": i, "value": i, "label": i, "SortOrder": idx}
        for idx, i in enumerate(insurers)
    ]
    return pd.DataFrame(rows)


def get_all_dimensions(df: pd.DataFrame) -> dict:
    """
    Return dict of dimension DataFrames.
    Keys: DimAgeBand, DimRegion, DimPaymentType, DimInsurer.
    """
    return {
        "DimAgeBand": get_dim_age_band(df),
        "DimRegion": get_dim_region(df),
        "DimPaymentType": get_dim_payment_type(df),
        "DimInsurer": get_dim_insurer(df),
    }
