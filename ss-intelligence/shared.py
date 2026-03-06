"""
Shared data and dimensions — imported by app and pages.

Loads both MainData (wide, profile) and AllOtherData (EAV, questions) on startup.
Pages access DF_MOTOR, DF_QUESTIONS, DIMENSIONS, and format_year_month from here.
"""
import logging
import pandas as pd

from data.loader import load_main, load_questions
from data.dimensions import get_all_dimensions

log = logging.getLogger(__name__)

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


# ---- Lazy data loading ----
_loaded = False
DF_MOTOR = pd.DataFrame()
DF_HOME = None
DF_QUESTIONS = pd.DataFrame()
DF_QUESTIONS_HOME = None
DIMENSIONS = {}
DF_ALL = pd.DataFrame()
DATA_METADATA = {}

_MOTOR_META = {}
_Q_META = {}


def _load_all():
    """Load all data on first access. Called once."""
    global _loaded, DF_MOTOR, DF_HOME, DF_QUESTIONS, DF_QUESTIONS_HOME
    global DIMENSIONS, DF_ALL, DATA_METADATA, _MOTOR_META, _Q_META

    if _loaded:
        return
    _loaded = True

    # MainData — wide, one row per respondent
    DF_MOTOR, _MOTOR_META = load_main("Motor")
    try:
        DF_HOME, _ = load_main("Home")
    except FileNotFoundError:
        DF_HOME = None

    # AllOtherData — EAV, one row per answer per respondent
    DF_QUESTIONS, _Q_META = load_questions("Motor")
    if DF_QUESTIONS.empty:
        log.warning(
            "AllOtherData (Motor) is empty — awareness, reasons, and channel analytics "
            "will show 'Insufficient data'. Copy the flat export CSV (e.g. "
            "ibt_motor_export_FINAL.csv) into data/raw/ and restart, or set DATA_DIR."
        )
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


def ensure_loaded():
    """Ensure data is loaded. Called by app.py on startup."""
    _load_all()


# Auto-load on import for backward compatibility with existing pages
_load_all()
