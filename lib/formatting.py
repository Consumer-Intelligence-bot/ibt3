"""
Shared formatting utilities for Consumer Intelligence dashboard pages.
"""


def fmt_pct(val, dp=1):
    """Format a proportion (0-1) as a percentage string."""
    if val is None:
        return "\u2014"
    return f"{val * 100:.{dp}f}%"


def safe_pct(n, d):
    """Divide n by d, returning 0.0 if d is zero."""
    return n / d if d > 0 else 0.0
