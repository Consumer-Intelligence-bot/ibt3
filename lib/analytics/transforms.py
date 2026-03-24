"""
Derived fields, cleaning, and mapping for MainData.

Produces a consistent set of columns regardless of source format:
  Profile:   Product, CurrentCompany, PreRenewalCompany, PreviousCompany
  Time:      RenewalYearMonth, SurveyYearMonth
  Segments:  IsShopper, IsSwitcher, IsNewToMarket, IsRetained
  Demo:      AgeBand, Region, PaymentType
  Derived:   PriceDirection, UsedPCW
"""
from __future__ import annotations

import pandas as pd


def _quarter_to_yyyymm(sq: str) -> int | None:
    """Convert 'YYYY QN' to YYYYMM (last month of quarter). E.g. '2024 Q4' -> 202412."""
    try:
        year, q = sq.split(" Q")
        month = int(q) * 3
        return int(year) * 100 + month
    except (ValueError, AttributeError):
        return None


def _derive_price_direction(row: pd.Series) -> str | None:
    change = row.get("Renewal premium change combined") or row.get("Renewal premium change") or ""
    s = str(change).lower().strip()
    if not s or s == "nan":
        return None
    if "higher" in s or s == "up":
        return "Higher"
    if "lower" in s or s == "down":
        return "Lower"
    if "unchanged" in s:
        return "Unchanged"
    if "didn't have" in s or "new" in s or "purchase" in s:
        return "New"
    return None


def _derive_age_band(age_group: str) -> str | None:
    if pd.isna(age_group) or not str(age_group).strip():
        return None
    s = str(age_group).strip()
    if s in ("17-24", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"):
        return s
    return s


def _derive_used_pcw(row: pd.Series) -> bool:
    val = row.get("Did you use a PCW for shopping")
    return val in ("Yes", "1", True, "yes", "true")


def transform(df: pd.DataFrame, product: str = "Motor") -> pd.DataFrame:
    """
    Clean and derive fields from MainData.

    Returns DataFrame with standardised columns. Safe to call on both
    legacy 25-column and new flat-export profile data.
    """
    if df is None or len(df) == 0:
        return df

    out = df.copy()

    # Product
    out["Product"] = product

    # Pet-specific column renames and time conversion
    if product == "Pet":
        out = out.rename(columns={
            "ResultSkey": "UniqueID",
            "Who is your current pet insurance provider?": "CurrentCompany",
            "Who was your previous pet insurance provider?": "PreviousCompany",
            "Payment method": "PaymentType",
            "Was the renewal price higher or lower than what you were paying previous year?": "Renewal premium change",
            "Recommendation score": "NPS",
        })
        # Convert "2024 Q4" -> 202412
        if "Survey Quarter" in out.columns:
            out["RenewalYearMonth"] = out["Survey Quarter"].apply(_quarter_to_yyyymm)

    # Column aliases
    if "PreRenewalCompany" in out.columns and "PreviousCompany" not in out.columns:
        out["PreviousCompany"] = out["PreRenewalCompany"]

    # RenewalYearMonth as numeric
    if "RenewalYearMonth" in out.columns:
        out["RenewalYearMonth"] = pd.to_numeric(out["RenewalYearMonth"], errors="coerce")

    # UniqueID as string
    if "UniqueID" in out.columns:
        out["UniqueID"] = out["UniqueID"].astype(str)

    # Shoppers → IsShopper
    if "Shoppers" in out.columns:
        out["IsShopper"] = out["Shoppers"].astype(str).str.strip().str.lower() == "shoppers"
    else:
        out["IsShopper"] = False

    # Switchers → IsSwitcher, IsNewToMarket, IsRetained
    if "Switchers" in out.columns:
        sw = out["Switchers"].astype(str).str.strip().str.lower()
        out["IsSwitcher"] = sw == "switcher"
        out["IsNewToMarket"] = sw.str.contains("new-to-market", na=False)
        out["IsRetained"] = sw.isin(("retained", "non-switcher"))
    elif "Retained" in out.columns:
        out["IsRetained"] = out["Retained"].astype(str).str.strip().str.lower().isin(("true", "1", "yes", "retained"))
        out["IsSwitcher"] = ~out["IsRetained"]
        out["IsNewToMarket"] = False
    else:
        out["IsSwitcher"] = False
        out["IsNewToMarket"] = False
        out["IsRetained"] = True

    # AgeBand
    if "Age Group" in out.columns:
        out["AgeBand"] = out["Age Group"].apply(_derive_age_band)
    elif "AgeBand" not in out.columns:
        out["AgeBand"] = None

    # Region
    if "Region" not in out.columns:
        out["Region"] = None

    # PaymentType
    if "PaymentType" not in out.columns and "Q43" in out.columns:
        out["PaymentType"] = out["Q43"].astype(str)
    elif "PaymentType" not in out.columns:
        out["PaymentType"] = "All"

    # Q6a / Q6b (price magnitude bands)
    if "How much higher" in out.columns:
        out["Q6a"] = out["How much higher"]
    if "How much lower" in out.columns:
        out["Q6b"] = out["How much lower"]

    # PriceDirection
    out["PriceDirection"] = out.apply(_derive_price_direction, axis=1)

    # UsedPCW
    out["UsedPCW"] = out.apply(_derive_used_pcw, axis=1)

    # Derive 'Renewal premium change combined' if missing (needed for PriceDirection in some paths)
    if "Renewal premium change combined" not in out.columns and "Renewal premium change" in out.columns:
        out["Renewal premium change combined"] = out["Renewal premium change"]

    return out
