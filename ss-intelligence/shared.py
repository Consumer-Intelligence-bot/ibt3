"""
Shared data and dimensions — imported by app and pages.

Loads both MainData (wide, profile) and AllOtherData (EAV, questions) on startup.
Pages access DF_MOTOR, DF_QUESTIONS, DIMENSIONS, and format_year_month from here.
"""
import pandas as pd

from data.loader import load_main, load_questions
from data.dimensions import get_all_dimensions

_MONTH_ABBR = [
    "", "Jan", "Feb", "Mar", "Apr", "May", "Jun",
    "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
]


def format_year_month(ym) -> str:
    """Convert YYYYMM (e.g. 202401) to readable label (e.g. 'Jan 2024')."""
    if pd.isna(ym) or ym is None:
        return ""
    ym = int(float(ym))
    y, m = ym // 100, ym % 100
    if 1 <= m <= 12:
        return f"{_MONTH_ABBR[m]} {y}"
    return str(ym)


# MainData — wide, one row per respondent
DF_MOTOR, _MOTOR_META = load_main("Motor")
try:
    DF_HOME, _ = load_main("Home")
except FileNotFoundError:
    DF_HOME = None

# AllOtherData — EAV, one row per answer per respondent
DF_QUESTIONS, _Q_META = load_questions("Motor")
try:
    DF_QUESTIONS_HOME, _ = load_questions("Home")
except FileNotFoundError:
    DF_QUESTIONS_HOME = None

DIMENSIONS = get_all_dimensions(DF_MOTOR)

# Combined Motor + Home MainData (legacy alias)
DF_ALL = DF_MOTOR.copy()
if DF_HOME is not None and len(DF_HOME) > 0:
    m = DF_MOTOR.loc[:, ~DF_MOTOR.columns.duplicated()]
    h = DF_HOME.loc[:, ~DF_HOME.columns.duplicated()]
    DF_ALL = pd.concat([m, h], ignore_index=True)

# Metadata for Admin page
DATA_METADATA = {
    "motor": _MOTOR_META,
    "questions": _Q_META,
    "has_questions": len(DF_QUESTIONS) > 0,
}
