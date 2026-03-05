"""Tests for suppression module (updated for CI-width framework)."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd
from analytics.suppression import check_suppression, get_confidence_level
from analytics.confidence import ConfidenceLabel, MetricType


class TestCheckSuppression:
    def test_below_floor_suppressed(self):
        df_ins = pd.DataFrame({"x": range(14)})
        df_mkt = pd.DataFrame({"x": range(500)})
        r = check_suppression(df_ins, df_mkt)
        assert r.can_show_insurer is False
        assert r.confidence.label == ConfidenceLabel.INSUFFICIENT

    def test_above_floor_with_good_rate(self):
        df_ins = pd.DataFrame({"x": range(1000)})
        df_mkt = pd.DataFrame({"x": range(5000)})
        r = check_suppression(df_ins, df_mkt, rate=0.7)
        assert r.can_show_insurer is True

    def test_market_below_floor(self):
        df_ins = pd.DataFrame({"x": range(100)})
        df_mkt = pd.DataFrame({"x": range(10)})
        r = check_suppression(df_ins, df_mkt, rate=0.5)
        assert r.can_show_market is False

    def test_suppression_message_present(self):
        df_ins = pd.DataFrame({"x": range(5)})
        df_mkt = pd.DataFrame({"x": range(500)})
        r = check_suppression(df_ins, df_mkt)
        assert r.message is not None

    def test_active_filters_warning(self):
        df_ins = pd.DataFrame({"x": range(100)})
        df_mkt = pd.DataFrame({"x": range(500)})
        r = check_suppression(df_ins, df_mkt, rate=0.5, active_filters={"AgeBand": "25-34", "Region": "London"})
        assert r.warning is not None

    def test_metric_type_forwarded(self):
        df_ins = pd.DataFrame({"x": range(50)})
        df_mkt = pd.DataFrame({"x": range(500)})
        r = check_suppression(df_ins, df_mkt, metric_type=MetricType.REASON, rate=0.3)
        assert r.confidence is not None


class TestGetConfidenceLevel:
    def test_large_n_high(self):
        label = get_confidence_level(2000, rate=0.7)
        assert label == ConfidenceLabel.HIGH

    def test_below_floor(self):
        label = get_confidence_level(10, rate=0.5)
        assert label == ConfidenceLabel.INSUFFICIENT

    def test_nps_metric(self):
        label = get_confidence_level(30, metric_type=MetricType.NPS)
        assert label == ConfidenceLabel.HIGH
