"""
Cohort heat map analytics (Spec Section 6.9).

Computes insurer vs market rates across all available demographic segments
for rapid anomaly detection. Each cell shows the delta between insurer rate
and market rate for that segment.
"""
from __future__ import annotations

import pandas as pd

from lib.analytics.rates import calc_shopping_rate, calc_switching_rate, calc_retention_rate
from lib.config import MIN_BASE_INDICATIVE


# Demographic columns available in MainData (mapped to display labels)
DEMOGRAPHIC_FIELDS = {
    "AgeBand": "Age Band",
    "Region": "Region",
    "PaymentType": "Payment Type",
}

# Metrics to compute for each cohort
COHORT_METRICS = {
    "Shopping Rate": calc_shopping_rate,
    "Switching Rate": calc_switching_rate,
    "Retention Rate": calc_retention_rate,
}


def calc_cohort_heatmap(
    df_insurer: pd.DataFrame,
    df_market: pd.DataFrame,
) -> pd.DataFrame:
    """
    Compute insurer vs market rates across all demographic segments.

    Returns DataFrame with columns:
        segment_field, segment_value, metric, insurer_rate, market_rate,
        delta, insurer_n, market_n, suppressed
    """
    rows = []

    for col, field_label in DEMOGRAPHIC_FIELDS.items():
        if col not in df_market.columns:
            continue

        segments = df_market[col].dropna().unique()

        for segment in sorted(segments, key=str):
            seg_str = str(segment).strip()
            if not seg_str or seg_str.lower() == "nan":
                continue

            ins_seg = df_insurer[df_insurer[col] == segment] if not df_insurer.empty else pd.DataFrame()
            mkt_seg = df_market[df_market[col] == segment]

            for metric_name, calc_fn in COHORT_METRICS.items():
                ins_n = len(ins_seg)
                mkt_n = len(mkt_seg)
                suppressed = ins_n < MIN_BASE_INDICATIVE

                ins_rate = calc_fn(ins_seg) if ins_n >= MIN_BASE_INDICATIVE else None
                mkt_rate = calc_fn(mkt_seg) if mkt_n >= MIN_BASE_INDICATIVE else None

                delta = None
                if ins_rate is not None and mkt_rate is not None:
                    delta = (ins_rate - mkt_rate) * 100  # percentage points

                rows.append({
                    "segment_field": field_label,
                    "segment_value": seg_str,
                    "metric": metric_name,
                    "insurer_rate": ins_rate,
                    "market_rate": mkt_rate,
                    "delta": delta,
                    "insurer_n": ins_n,
                    "market_n": mkt_n,
                    "suppressed": suppressed,
                })

    return pd.DataFrame(rows) if rows else pd.DataFrame()
