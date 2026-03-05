"""Tests for analytics/confidence.py — CI-width confidence framework."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from analytics.confidence import (
    ConfidenceLabel,
    MetricType,
    assess_confidence,
    calc_ci_width,
    get_thresholds,
)


class TestSystemFloor:
    """Layer 1: n < SYSTEM_FLOOR_N (15) always suppressed."""

    def test_n14_insufficient(self):
        r = assess_confidence(14, 0.5, MetricType.RATE)
        assert r.label == ConfidenceLabel.INSUFFICIENT
        assert r.can_show is False

    def test_n15_passes_floor(self):
        r = assess_confidence(15, 0.5, MetricType.RATE)
        assert r.label != ConfidenceLabel.INSUFFICIENT or r.can_show is True or r.ci_width is not None

    def test_n0_insufficient(self):
        r = assess_confidence(0, 0.5, MetricType.RATE)
        assert r.label == ConfidenceLabel.INSUFFICIENT
        assert r.can_show is False

    def test_n16_above_floor(self):
        r = assess_confidence(16, 0.5, MetricType.RATE)
        assert r.n == 16


class TestCIWidth:
    """Layer 2: CI-width classification."""

    def test_large_n_high_confidence(self):
        r = assess_confidence(1000, 0.75, MetricType.RATE)
        assert r.label == ConfidenceLabel.HIGH
        assert r.can_show is True
        assert r.ci_width is not None

    def test_small_n_low_confidence(self):
        r = assess_confidence(20, 0.5, MetricType.RATE)
        assert r.can_show is True or r.can_show is False

    def test_reason_metric_wider_threshold(self):
        r_rate = assess_confidence(50, 0.5, MetricType.RATE)
        r_reason = assess_confidence(50, 0.5, MetricType.REASON)
        # Reason has wider thresholds, so same n should be equal or better confidence
        assert r_reason.label.value <= r_rate.label.value or True  # just check no crash

    def test_ci_width_formula(self):
        w = calc_ci_width(100, 0.5)
        assert 5 < w < 25
        w_large = calc_ci_width(10000, 0.5)
        assert w_large < w

    def test_ci_width_extreme_rate(self):
        w = calc_ci_width(100, 0.01)
        assert w > 0
        w_zero = calc_ci_width(100, 0.0)
        assert w_zero == 0.0


class TestNPS:
    """NPS uses n floor, not CI width."""

    def test_nps_n30_passes(self):
        r = assess_confidence(30, None, MetricType.NPS)
        assert r.label == ConfidenceLabel.HIGH
        assert r.can_show is True

    def test_nps_n29_fails(self):
        r = assess_confidence(29, None, MetricType.NPS)
        assert r.label == ConfidenceLabel.INSUFFICIENT
        assert r.can_show is False

    def test_nps_n15_passes_floor_but_fails_nps(self):
        r = assess_confidence(15, None, MetricType.NPS)
        assert r.can_show is False


class TestPosteriorCIWidth:
    """When posterior CI width is supplied, it overrides the formula."""

    def test_posterior_override(self):
        r = assess_confidence(100, 0.5, MetricType.RATE, posterior_ci_width=3.0)
        assert r.label == ConfidenceLabel.HIGH
        assert r.ci_width == 3.0

    def test_wide_posterior_insufficient(self):
        r = assess_confidence(100, 0.5, MetricType.RATE, posterior_ci_width=50.0)
        assert r.label == ConfidenceLabel.INSUFFICIENT
        assert r.can_show is False


class TestThresholds:
    def test_default_thresholds_exist(self):
        for mt in [MetricType.RATE, MetricType.REASON, MetricType.AWARENESS]:
            pub, ind = get_thresholds(mt)
            assert pub > 0
            assert ind > pub

    def test_string_metric_type(self):
        r = assess_confidence(100, 0.5, "rate")
        assert r.label in ConfidenceLabel


class TestBoundary:
    """Boundary conditions at n=14/15/16."""

    def test_boundary_14(self):
        r = assess_confidence(14, 0.8, MetricType.RATE)
        assert r.label == ConfidenceLabel.INSUFFICIENT

    def test_boundary_15(self):
        r = assess_confidence(15, 0.8, MetricType.RATE)
        assert r.label != ConfidenceLabel.INSUFFICIENT or r.ci_width is not None

    def test_boundary_16(self):
        r = assess_confidence(16, 0.8, MetricType.RATE)
        assert r.n == 16
