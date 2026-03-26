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

def kpi_vs_market_colour(
    insurer_val: float | None,
    market_val: float | None,
    lower_is_better: bool = False,
) -> str:
    """Return a CI brand colour based on insurer value vs market value.

    Parameters
    ----------
    insurer_val : float | None
        The insurer's metric value.
    market_val : float | None
        The market-average metric value.
    lower_is_better : bool
        When True, a lower insurer value is considered better (e.g. switching
        rate, churn). When False (default), higher is better (e.g. retention,
        NPS).

    Returns
    -------
    str
        CI_GREEN if insurer is better than market,
        CI_RED if insurer is worse than market,
        CI_GREY if equal or either value is None.
    """
    if insurer_val is None or market_val is None:
        return CI_GREY
    if lower_is_better:
        if insurer_val < market_val:
            return CI_GREEN
        if insurer_val > market_val:
            return CI_RED
    else:
        if insurer_val > market_val:
            return CI_GREEN
        if insurer_val < market_val:
            return CI_RED
    return CI_GREY


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


# ---------------------------------------------------------------------------
# Reason index helpers
# ---------------------------------------------------------------------------

def calc_reason_index(insurer_pct: float | None, market_pct: float | None) -> int | None:
    """
    Calculate how much an insurer over- or under-indexes on a reason relative
    to the market.

    Parameters
    ----------
    insurer_pct : float | None
        Proportion of insurer respondents citing this reason (0–1).
    market_pct : float | None
        Proportion of market respondents citing this reason (0–1).

    Returns
    -------
    int
        (insurer_pct / market_pct) * 100, rounded to nearest integer.
        100 = exactly at market average. 150 = 50% over-index.
    None
        When either input is None, or market_pct <= 0 (division-by-zero guard).
    """
    if insurer_pct is None or market_pct is None:
        return None
    if market_pct <= 0:
        return None
    return round((insurer_pct / market_pct) * 100)


def format_reason_pct(value: float | None) -> str:
    """
    Format a reason percentage proportion for display in tables.

    Parameters
    ----------
    value : float | None
        Proportion as a decimal (0–1). None means data is unavailable.

    Returns
    -------
    str
        "0%"   — exactly 0.0
        "<1%"  — 0 < value < 0.005 (rounds to 0% but is genuinely non-zero)
        "N%"   — otherwise, formatted to 0dp (e.g. "16%")
        "—"    — None input (em dash, U+2014)
    """
    if value is None:
        return "\u2014"
    if value <= 0:
        return "0%"
    if value <= 0.005:
        return "<1%"
    return f"{value * 100:.0f}%"


# ---------------------------------------------------------------------------
# Confidence interval helpers
# ---------------------------------------------------------------------------

def calc_wilson_ci(
    successes: int,
    n: int,
    z: float = 1.96,
) -> tuple[float, float] | None:
    """
    Calculate a Wilson score confidence interval for a proportion.

    Parameters
    ----------
    successes : int
        Number of successes (numerator).
    n : int
        Total observations (denominator).
    z : float
        Z-score for the desired confidence level (default 1.96 for 95% CI).

    Returns
    -------
    tuple[float, float]
        (lower, upper) as proportions in [0, 1].
    None
        When n is 0 (division-by-zero guard).
    """
    if n == 0:
        return None

    p_hat = successes / n
    z2 = z * z
    denominator = 1 + z2 / n
    centre = (p_hat + z2 / (2 * n)) / denominator
    margin = (z / denominator) * ((p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) ** 0.5)

    lower = max(0.0, centre - margin)
    upper = min(1.0, centre + margin)
    return (lower, upper)


def format_ci_range(lower: float, upper: float) -> str:
    """
    Format a confidence interval as a display string.

    Parameters
    ----------
    lower : float
        Lower bound as a proportion (e.g. 0.535).
    upper : float
        Upper bound as a proportion (e.g. 0.575).

    Returns
    -------
    str
        Formatted string, e.g. "53.5%–57.5%" (en dash separator).
    """
    return f"{lower * 100:.1f}%\u2013{upper * 100:.1f}%"


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
