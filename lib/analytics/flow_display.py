"""
Display helpers for the Switching & Flows screen.

Converts raw switching counts to percentage strings and determines
bar chart colours based on flow index values and direction.

All client-facing values must be percentages or indices — never raw counts.
"""
from __future__ import annotations

from lib.config import CI_GREEN, CI_GREY, CI_RED


# ---------------------------------------------------------------------------
# Percentage formatting helpers
# ---------------------------------------------------------------------------

def format_flow_pct(count: int | None, total: int | None) -> str | None:
    """
    Format a switcher count as a percentage of total switching volume.

    Parameters
    ----------
    count : int | None
        Number of switchers for this insurer/flow cell.
    total : int | None
        Total switching volume (denominator).

    Returns
    -------
    str
        Formatted percentage string, e.g. "+15.5%" or "-5.0%" or "0.0%".
    None
        When total is None or zero (division-by-zero guard), or count is None.
    """
    if count is None or total is None:
        return None
    if total == 0:
        return None
    pct = (count / total) * 100
    if count > 0:
        return f"+{pct:.1f}%"
    elif count < 0:
        return f"{pct:.1f}%"
    else:
        return "0.0%"


def format_net_flow_pct(net_pct: float | None) -> str:
    """
    Format a pre-computed net flow proportion as a signed percentage string.

    Parameters
    ----------
    net_pct : float | None
        Net flow as a decimal proportion, e.g. 0.124 for +12.4%, or None.

    Returns
    -------
    str
        Formatted string, e.g. "+12.4%", "-5.0%", "0.0%", or "—" if None.
    """
    if net_pct is None:
        return "\u2014"  # em dash
    pct = net_pct * 100
    if pct > 0:
        return f"+{pct:.1f}%"
    elif pct < 0:
        return f"{pct:.1f}%"
    else:
        return "0.0%"


# ---------------------------------------------------------------------------
# Index bar colour helper
# ---------------------------------------------------------------------------

_HIGH_THRESHOLD = 120
_LOW_THRESHOLD = 80


def format_price_change(value: float) -> str:
    """
    Format a signed average price change as a display string with £ sign.

    Parameters
    ----------
    value : float
        Signed price change, e.g. 21.3 or -15.7.

    Returns
    -------
    str
        Formatted string:
        - Positive: '+£21'  (leading plus, £ symbol, rounded to integer)
        - Negative: '−£16'  (unicode minus U+2212, £ symbol, rounded to integer)
        - Zero:     '£0'
    """
    rounded = round(float(value))
    if rounded > 0:
        return f"+\u00a3{rounded}"
    if rounded < 0:
        return f"\u2212\u00a3{abs(rounded)}"
    return f"\u00a30"


def get_index_bar_colour(index_value: float, direction: str) -> str:
    """
    Return a CI brand colour for a flow index bar based on value and direction.

    Rules
    -----
    direction="loss":
        index > 120 → CI_RED   (losing disproportionately — bad)
        index < 80  → CI_GREEN (under-indexing losses — good)
        80–120      → CI_GREY  (at expected rate)

    direction="gain":
        index > 120 → CI_GREEN (winning disproportionately — good)
        index < 80  → CI_RED   (under-indexing wins — bad)
        80–120      → CI_GREY  (at expected rate)

    Any other direction string falls back to CI_GREY.

    Parameters
    ----------
    index_value : float
        The flow index (100 = market average).
    direction : str
        "loss" or "gain".

    Returns
    -------
    str
        A CI brand colour hex string.
    """
    if direction == "loss":
        if index_value > _HIGH_THRESHOLD:
            return CI_RED
        if index_value < _LOW_THRESHOLD:
            return CI_GREEN
        return CI_GREY

    if direction == "gain":
        if index_value > _HIGH_THRESHOLD:
            return CI_GREEN
        if index_value < _LOW_THRESHOLD:
            return CI_RED
        return CI_GREY

    return CI_GREY
