"""
Rate calculations: shopping, switching, retention, conversion.
"""
import numpy as np
import pandas as pd

from lib.config import Z_SCORE


def calc_shopping_rate(df: pd.DataFrame) -> float | None:
    """Shopping rate = % where IsShopper is True."""
    if df is None or len(df) == 0:
        return None
    return df["IsShopper"].sum() / len(df)


def calc_switching_rate(df: pd.DataFrame) -> float | None:
    """Switching rate = % where IsSwitcher is True (exclude new-to-market)."""
    if df is None or len(df) == 0:
        return None
    # Exclude new-to-market for switching rate
    base = df[~df.get("IsNewToMarket", False)]
    if len(base) == 0:
        return None
    return base["IsSwitcher"].sum() / len(base)


def calc_retention_rate(df: pd.DataFrame) -> float | None:
    """Retention rate = 1 - switching rate."""
    sw = calc_switching_rate(df)
    if sw is None:
        return None
    return 1 - sw


def calc_conversion_rate(df: pd.DataFrame) -> float | None:
    """Conversion rate = switchers / shoppers."""
    if df is None or len(df) == 0:
        return None
    shoppers = df[df["IsShopper"]]
    if len(shoppers) == 0:
        return None
    switchers = shoppers[shoppers["IsSwitcher"]]
    return len(switchers) / len(shoppers)


def _wilson_score(successes: int, n: int, z: float = Z_SCORE) -> tuple[float, float]:
    """Wilson score interval for binomial proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    margin = (z / denom) * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return (max(0, centre - margin), min(1, centre + margin))


def calc_rate_with_ci(
    df: pd.DataFrame, col: str = "IsShopper"
) -> dict | None:
    """Rate + Wilson 95% CI. col is the boolean column name."""
    if df is None or len(df) == 0:
        return None
    successes = df[col].sum()
    n = len(df)
    rate = successes / n
    ci_lower, ci_upper = _wilson_score(int(successes), n)
    return {
        "rate": rate,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "n": n,
    }
