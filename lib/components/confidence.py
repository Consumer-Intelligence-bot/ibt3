"""
Shared confidence indicator utilities.

Provides a single source of truth for the n-based confidence thresholds used
across all KPI components (decision_kpi, context_footer, etc.).

Thresholds:
  n >= 100  → High confidence (CI Cyan)
  n >= 30   → Indicative     (CI Yellow)
  n < 30    → Low confidence (CI Red)
"""

from lib.config import CI_CYAN, CI_RED, CI_YELLOW


def confidence_label(n: int) -> str:
    """Return a human-readable confidence label for a given sample size.

    Parameters
    ----------
    n : int
        Sample count. Zero and negative values map to "Low confidence".

    Returns
    -------
    str
        One of "High confidence", "Indicative", or "Low confidence".
    """
    if n >= 100:
        return "High confidence"
    if n >= 30:
        return "Indicative"
    return "Low confidence"


def confidence_colour(n: int) -> str:
    """Return the CI brand colour hex string for a given sample size.

    Parameters
    ----------
    n : int
        Sample count.

    Returns
    -------
    str
        Hex colour string: CI_CYAN, CI_YELLOW, or CI_RED.
    """
    if n >= 100:
        return CI_CYAN
    if n >= 30:
        return CI_YELLOW
    return CI_RED
