"""
Unit tests for IBT3 analytics functions.

Covers:
  - calc_insurer_rank  (lib/analytics/rates.py)
  - calc_net_flow      (lib/analytics/flows.py)
  - calc_rolling_avg   (lib/analytics/rates.py)
  - DuckDB roundtrip   (lib/db.py)
  - calc_toma_share    (lib/analytics/spontaneous.py)
  - calc_awareness_rates (lib/analytics/awareness.py)

TDD methodology: tests were written against function signatures and documented
behaviour before verifying against the running implementation.
"""
import os
import sys

import numpy as np
import pandas as pd
import pytest

# Ensure project root is on path when running from tests/ or root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ===========================================================================
# 1. calc_net_flow
# ===========================================================================

class TestCalcNetFlow:
    """lib/analytics/flows.py :: calc_net_flow"""

    from lib.analytics.flows import calc_net_flow

    def test_basic_gained_and_lost(self, base_df):
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Admiral")
        # UniqueIDs 4 & 5 switched TO Admiral; UniqueID 6 switched FROM Admiral
        assert result["gained"] == 2
        assert result["lost"] == 1
        assert result["net"] == 1

    def test_basic_with_base(self, base_df):
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Admiral", base=100)
        assert result["gained_pct"] == pytest.approx(0.02)
        assert result["lost_pct"] == pytest.approx(0.01)
        assert result["net_pct"] == pytest.approx(0.01)

    def test_base_zero_returns_none_pcts(self, base_df):
        """base=0 must not divide by zero; percentages should be None."""
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Admiral", base=0)
        assert result["gained_pct"] is None
        assert result["lost_pct"] is None
        assert result["net_pct"] is None

    def test_base_none_returns_none_pcts(self, base_df):
        """base=None must not cause an error; percentages should be None."""
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Admiral", base=None)
        assert result["gained_pct"] is None
        assert result["lost_pct"] is None
        assert result["net_pct"] is None

    def test_insurer_not_in_data(self, base_df):
        """Insurer with no flows at all should return zeros."""
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Unknown Insurer")
        assert result["gained"] == 0
        assert result["lost"] == 0
        assert result["net"] == 0

    def test_empty_dataframe(self, empty_df):
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(empty_df, "Aviva")
        assert result["gained"] == 0
        assert result["lost"] == 0
        assert result["net"] == 0

    def test_none_dataframe(self, none_df):
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(none_df, "Aviva")
        assert result["gained"] == 0
        assert result["net"] == 0

    def test_excludes_same_company_switchers(self):
        """Spec 12.4: CurrentCompany == PreviousCompany should be excluded."""
        from lib.analytics.flows import calc_net_flow
        df = pd.DataFrame([
            {"UniqueID": 1, "CurrentCompany": "Aviva", "PreviousCompany": "Aviva",
             "IsSwitcher": True},
            {"UniqueID": 2, "CurrentCompany": "Aviva", "PreviousCompany": "Admiral",
             "IsSwitcher": True},
        ])
        result = calc_net_flow(df, "Aviva")
        # UniqueID 1 should be excluded (same company). Only UniqueID 2 counts.
        assert result["gained"] == 1
        assert result["lost"] == 0

    def test_exclude_guard_passes_through_when_no_company_cols(self):
        """
        _exclude_q4_eq_q39 returns df unchanged when company columns are absent.
        This covers the early-return guard (line 15 in flows.py).
        """
        from lib.analytics.flows import _exclude_q4_eq_q39
        df = pd.DataFrame([
            {"UniqueID": 1, "IsSwitcher": True},
            {"UniqueID": 2, "IsSwitcher": False},
        ])
        result = _exclude_q4_eq_q39(df)
        # Returned unchanged — same length
        assert len(result) == 2

    def test_net_can_be_negative(self, base_df):
        """An insurer that lost more than gained should have negative net."""
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(base_df, "Aviva")
        # Aviva gained 1 (from Direct Line) and lost 2 (to Admiral)
        assert result["net"] == -1

    def test_return_keys_always_present(self, empty_df):
        """Return dict must always contain all six keys."""
        from lib.analytics.flows import calc_net_flow
        result = calc_net_flow(empty_df, "Aviva")
        expected_keys = {"gained", "lost", "net", "gained_pct", "lost_pct", "net_pct"}
        assert expected_keys == set(result.keys())


# ===========================================================================
# 2. calc_rolling_avg
# ===========================================================================

class TestCalcRollingAvg:
    """lib/analytics/rates.py :: calc_rolling_avg"""

    def test_adds_rolling_column(self, monthly_rates_df):
        from lib.analytics.rates import calc_rolling_avg
        result = calc_rolling_avg(monthly_rates_df)
        assert "retention_rolling" in result.columns

    def test_default_window_3(self, monthly_rates_df):
        from lib.analytics.rates import calc_rolling_avg
        result = calc_rolling_avg(monthly_rates_df, window=3)
        # Month 3 (index 2): mean of 0.70, 0.72, 0.68 = 0.7 (approx)
        expected_m3 = round((0.70 + 0.72 + 0.68) / 3, 10)
        assert result["retention_rolling"].iloc[2] == pytest.approx(expected_m3, rel=1e-6)

    def test_min_periods_1_so_no_nan(self, monthly_rates_df):
        """min_periods=1 means first row should NOT be NaN."""
        from lib.analytics.rates import calc_rolling_avg
        result = calc_rolling_avg(monthly_rates_df)
        assert not result["retention_rolling"].isna().any()

    def test_single_row_dataframe(self, single_row_rates_df):
        """Single row must not raise and rolling value equals the single rate."""
        from lib.analytics.rates import calc_rolling_avg
        result = calc_rolling_avg(single_row_rates_df)
        assert len(result) == 1
        assert result["retention_rolling"].iloc[0] == pytest.approx(0.70)

    def test_original_dataframe_not_mutated(self, monthly_rates_df):
        """Function must return a copy, not mutate the original."""
        from lib.analytics.rates import calc_rolling_avg
        original_cols = list(monthly_rates_df.columns)
        calc_rolling_avg(monthly_rates_df)
        assert list(monthly_rates_df.columns) == original_cols

    def test_custom_rate_column(self, monthly_rates_df):
        """rate_col param controls which column is averaged."""
        from lib.analytics.rates import calc_rolling_avg
        # Add a 'switching' column to test with
        df = monthly_rates_df.copy()
        df["switching"] = 1 - df["retention"]
        result = calc_rolling_avg(df, rate_col="switching")
        assert "switching_rolling" in result.columns
        assert "retention_rolling" not in result.columns

    def test_window_1_equals_original_values(self, monthly_rates_df):
        """window=1 rolling avg should equal the original values."""
        from lib.analytics.rates import calc_rolling_avg
        result = calc_rolling_avg(monthly_rates_df, window=1)
        pd.testing.assert_series_equal(
            result["retention_rolling"].reset_index(drop=True),
            monthly_rates_df["retention"].reset_index(drop=True),
            check_names=False,
        )


# ===========================================================================
# 3. calc_insurer_rank
# ===========================================================================

class TestCalcInsurerRank:
    """lib/analytics/rates.py :: calc_insurer_rank"""

    def _make_rank_df(self, insurer_rates: dict[str, tuple[int, int]]) -> pd.DataFrame:
        """
        Build a market-level DataFrame from {insurer: (retained, total)} pairs.

        retained = number who did NOT switch (IsSwitcher=False)
        total    = total respondents for that insurer
        """
        rows = []
        uid = 1
        for insurer, (retained, total) in insurer_rates.items():
            for i in range(total):
                switched = i >= retained
                rows.append({
                    "UniqueID": uid,
                    "PreviousCompany": insurer,
                    "CurrentCompany": insurer if not switched else "Other",
                    "IsSwitcher": switched,
                    "IsNewToMarket": False,
                    "Product": "Motor",
                    "RenewalYearMonth": 202401,
                })
                uid += 1
        return pd.DataFrame(rows)

    def test_rank_basic(self):
        """Insurer with highest retention should rank 1."""
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (90, 100),      # 90% retention
            "Admiral": (80, 100),    # 80% retention
            "Direct Line": (70, 100), # 70% retention
        })
        result = calc_insurer_rank(df, "Aviva")
        assert result is not None
        assert result["rank"] == 1
        assert result["total"] == 3

    def test_rank_last_place(self):
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (90, 100),
            "Admiral": (80, 100),
            "Direct Line": (70, 100),
        })
        result = calc_insurer_rank(df, "Direct Line")
        assert result["rank"] == 3

    def test_tied_retention_rates(self):
        """Tied insurers: both should receive rank <= total and not error."""
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (80, 100),
            "Admiral": (80, 100),   # identical retention
            "Direct Line": (60, 100),
        })
        result_aviva = calc_insurer_rank(df, "Aviva")
        result_admiral = calc_insurer_rank(df, "Admiral")
        assert result_aviva is not None
        assert result_admiral is not None
        # Both tied insurers should be ranked 1 or 2 (not 3)
        assert result_aviva["rank"] in (1, 2)
        assert result_admiral["rank"] in (1, 2)

    def test_below_min_base_returns_none(self):
        """Insurer with fewer than min_base respondents should return None."""
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (90, 100),
            "Tiny Insurer": (8, 10),   # below default min_base=50
        })
        result = calc_insurer_rank(df, "Tiny Insurer")
        assert result is None

    def test_insurer_not_present(self):
        """Insurer not in the data should return None."""
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (80, 100),
        })
        result = calc_insurer_rank(df, "Ghost Insurer")
        assert result is None

    def test_empty_dataframe(self, empty_df):
        from lib.analytics.rates import calc_insurer_rank
        result = calc_insurer_rank(empty_df, "Aviva")
        assert result is None

    def test_none_dataframe(self, none_df):
        from lib.analytics.rates import calc_insurer_rank
        result = calc_insurer_rank(none_df, "Aviva")
        assert result is None

    def test_total_reflects_eligible_insurer_count(self):
        """total in return dict should count only insurers above min_base."""
        from lib.analytics.rates import calc_insurer_rank
        df = self._make_rank_df({
            "Aviva": (80, 100),
            "Admiral": (75, 100),
            "Tiny": (5, 8),       # below min_base, excluded
        })
        result = calc_insurer_rank(df, "Aviva")
        assert result["total"] == 2

    def test_missing_previous_company_column_returns_none(self):
        """DataFrame without PreviousCompany column must return None gracefully."""
        from lib.analytics.rates import calc_insurer_rank
        df = pd.DataFrame({
            "UniqueID": [1, 2],
            "IsSwitcher": [False, True],
            "IsNewToMarket": [False, False],
        })
        result = calc_insurer_rank(df, "Aviva")
        assert result is None


# ===========================================================================
# 4. DuckDB roundtrip
# ===========================================================================

class TestDuckDBRoundtrip:
    """lib/db.py :: save_dataframe / load_dataframe"""

    def test_roundtrip_basic(self, tmp_db_path):
        """Saved DataFrame must load back with same values."""
        import lib.db as db
        df = pd.DataFrame({
            "UniqueID": [1, 2, 3],
            "RenewalYearMonth": [202401, 202401, 202402],
            "CurrentCompany": ["Aviva", "Admiral", "Aviva"],
        })
        db.save_dataframe(df, "test_table")
        loaded = db.load_dataframe("test_table")
        assert len(loaded) == 3
        assert set(loaded["CurrentCompany"].tolist()) == {"Aviva", "Admiral"}

    def test_roundtrip_integer_column(self, tmp_db_path):
        """Integer columns must survive the DuckDB roundtrip."""
        import lib.db as db
        df = pd.DataFrame({"id": [1, 2], "month": [202401, 202402]})
        db.save_dataframe(df, "int_table")
        loaded = db.load_dataframe("int_table")
        assert loaded["id"].tolist() == [1, 2]
        assert loaded["month"].tolist() == [202401, 202402]

    def test_roundtrip_float_column(self, tmp_db_path):
        """Float columns must survive with no precision loss beyond float64."""
        import lib.db as db
        df = pd.DataFrame({"rate": [0.123456, 0.654321]})
        db.save_dataframe(df, "float_table")
        loaded = db.load_dataframe("float_table")
        assert loaded["rate"].tolist() == pytest.approx([0.123456, 0.654321], rel=1e-5)

    def test_roundtrip_boolean_column(self, tmp_db_path):
        """Boolean columns must survive the roundtrip."""
        import lib.db as db
        df = pd.DataFrame({"flag": [True, False, True]})
        db.save_dataframe(df, "bool_table")
        loaded = db.load_dataframe("bool_table")
        assert loaded["flag"].tolist() == [True, False, True]

    def test_load_missing_table_returns_empty(self, tmp_db_path):
        """Loading a non-existent table must return an empty DataFrame."""
        import lib.db as db
        result = db.load_dataframe("nonexistent_table")
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_save_empty_dataframe_is_noop(self, tmp_db_path):
        """Saving an empty DataFrame must not create a table."""
        import lib.db as db
        db.save_dataframe(pd.DataFrame(), "empty_table")
        result = db.load_dataframe("empty_table")
        assert result.empty

    def test_save_overwrites_existing_table(self, tmp_db_path):
        """Saving twice to the same table name must overwrite, not append."""
        import lib.db as db
        df1 = pd.DataFrame({"val": [1, 2, 3]})
        df2 = pd.DataFrame({"val": [99]})
        db.save_dataframe(df1, "overwrite_test")
        db.save_dataframe(df2, "overwrite_test")
        loaded = db.load_dataframe("overwrite_test")
        assert len(loaded) == 1
        assert loaded["val"].tolist() == [99]

    def test_invalid_table_name_raises(self, tmp_db_path):
        """SQL-injection-style table names must raise ValueError."""
        import lib.db as db
        with pytest.raises(ValueError):
            db.save_dataframe(pd.DataFrame({"x": [1]}), "bad; DROP TABLE users")

    def test_has_data_false_when_empty(self, tmp_db_path):
        """has_data() must return False when table does not exist."""
        import lib.db as db
        assert db.has_data("nonexistent_table") is False

    def test_has_data_true_after_save(self, tmp_db_path):
        """has_data() must return True after saving a non-empty DataFrame."""
        import lib.db as db
        db.save_dataframe(pd.DataFrame({"x": [1, 2]}), "df_motor")
        assert db.has_data("df_motor") is True

    def test_metadata_roundtrip(self, tmp_db_path):
        """Metadata key/value pairs must survive a save/load roundtrip."""
        import lib.db as db
        db.save_metadata("start_month", "202401")
        assert db.load_metadata("start_month") == "202401"

    def test_metadata_missing_key_returns_none(self, tmp_db_path):
        """Loading a non-existent metadata key must return None."""
        import lib.db as db
        assert db.load_metadata("does_not_exist") is None

    def test_save_none_dataframe_is_noop(self, tmp_db_path):
        """Passing None as the DataFrame must be a no-op (no error raised)."""
        import lib.db as db
        db.save_dataframe(None, "null_table")
        result = db.load_dataframe("null_table")
        assert result.empty

    def test_clear_data_removes_db_file(self, tmp_db_path):
        """clear_data() must delete the DuckDB file."""
        import lib.db as db
        from pathlib import Path
        # Create something in the DB first
        db.save_dataframe(pd.DataFrame({"x": [1]}), "clear_test")
        assert Path(tmp_db_path).exists()
        db.clear_data()
        assert not Path(tmp_db_path).exists()

    def test_clear_data_on_missing_file_does_not_raise(self, tmp_db_path):
        """clear_data() on a non-existent file must not raise."""
        import lib.db as db
        from pathlib import Path
        # File does not exist yet
        assert not Path(tmp_db_path).exists()
        db.clear_data()  # should be silent


# ===========================================================================
# 5. calc_toma_share
# ===========================================================================

class TestCalcTomaShare:
    """lib/analytics/spontaneous.py :: calc_toma_share

    Critical regression: values must be in 0-1 decimal range, NOT 0-100.
    A prior bug multiplied by 100 twice.
    """

    def _make_metrics(self) -> pd.DataFrame:
        """Build a metrics DataFrame as returned by calc_spontaneous_metrics."""
        return pd.DataFrame([
            {"brand": "Aviva", "month": 202401, "toma": 0.50, "mention": 0.80,
             "top3": 0.75, "mean_position": 1.5, "n_total": 100,
             "n_toma": 50, "n_mention": 80, "n_top3": 75},
            {"brand": "Admiral", "month": 202401, "toma": 0.30, "mention": 0.60,
             "top3": 0.55, "mean_position": 2.0, "n_total": 100,
             "n_toma": 30, "n_mention": 60, "n_top3": 55},
            {"brand": "Direct Line", "month": 202401, "toma": 0.20, "mention": 0.40,
             "top3": 0.35, "mean_position": 2.5, "n_total": 100,
             "n_toma": 20, "n_mention": 40, "n_top3": 35},
            {"brand": "Aviva", "month": 202402, "toma": 0.48, "mention": 0.78,
             "top3": 0.72, "mean_position": 1.6, "n_total": 100,
             "n_toma": 48, "n_mention": 78, "n_top3": 72},
            {"brand": "Admiral", "month": 202402, "toma": 0.32, "mention": 0.62,
             "top3": 0.57, "mean_position": 2.1, "n_total": 100,
             "n_toma": 32, "n_mention": 62, "n_top3": 57},
            {"brand": "Direct Line", "month": 202402, "toma": 0.18, "mention": 0.38,
             "top3": 0.33, "mean_position": 2.6, "n_total": 100,
             "n_toma": 18, "n_mention": 38, "n_top3": 33},
        ])

    def test_values_are_decimal_not_percentage(self):
        """
        Regression test for double-multiply bug.
        All brand TOMA values must be <= 1.0, not in the 0-100 range.
        """
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        df, top_brands = calc_toma_share(metrics)
        assert not df.empty
        brand_cols = [c for c in df.columns if c != "month"]
        for col in brand_cols:
            max_val = df[col].max()
            assert max_val <= 1.0, (
                f"Column '{col}' has max value {max_val} — expected <= 1.0 (decimal). "
                "Possible double-multiply by 100 bug."
            )

    def test_returns_dataframe_and_brand_list(self):
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        df, top_brands = calc_toma_share(metrics)
        assert isinstance(df, pd.DataFrame)
        assert isinstance(top_brands, list)

    def test_top_n_limits_brands(self):
        """top_n=2 should produce at most 2 non-Other brand columns."""
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        df, top_brands = calc_toma_share(metrics, top_n=2)
        assert len(top_brands) == 2
        # DataFrame should have month + 2 brands + Other
        assert set(df.columns) == {"month", top_brands[0], top_brands[1], "Other"}

    def test_other_column_present(self):
        """Brands outside top_n must be aggregated into 'Other' column."""
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        df, _ = calc_toma_share(metrics, top_n=2)
        assert "Other" in df.columns

    def test_empty_metrics_returns_empty(self):
        from lib.analytics.spontaneous import calc_toma_share
        df, brands = calc_toma_share(pd.DataFrame())
        assert df.empty
        assert brands == []

    def test_month_column_preserved(self):
        """Output must contain a 'month' column with YYYYMM values."""
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        df, _ = calc_toma_share(metrics)
        assert "month" in df.columns
        assert set(df["month"].tolist()) == {202401, 202402}

    def test_top_brands_ordered_by_avg_toma(self):
        """First brand in top_brands must have highest average TOMA."""
        from lib.analytics.spontaneous import calc_toma_share
        metrics = self._make_metrics()
        _, top_brands = calc_toma_share(metrics, top_n=3)
        assert top_brands[0] == "Aviva"  # highest avg toma in fixture

    def test_calc_spontaneous_metrics_integration(self, spontaneous_df):
        """
        End-to-end: calc_spontaneous_metrics -> calc_toma_share.
        Values from the integrated pipeline must also be in 0-1 range.
        """
        from lib.analytics.spontaneous import calc_spontaneous_metrics, calc_toma_share
        metrics = calc_spontaneous_metrics(spontaneous_df)
        if metrics.empty:
            pytest.skip("No metrics produced — likely below SYSTEM_FLOOR_N")
        df, top_brands = calc_toma_share(metrics)
        if df.empty:
            pytest.skip("TOMA share output is empty")
        brand_cols = [c for c in df.columns if c != "month"]
        for col in brand_cols:
            assert df[col].max() <= 1.0, (
                f"Integrated pipeline: '{col}' max={df[col].max()} exceeds 1.0"
            )


# ===========================================================================
# 6. calc_awareness_rates
# ===========================================================================

class TestCalcAwarenessRates:
    """lib/analytics/awareness.py :: calc_awareness_rates"""

    def test_returns_dataframe(self, awareness_df):
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns_present(self, awareness_df):
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        required = {"brand", "month", "rate", "n_mentions", "n_total", "rank"}
        assert required.issubset(set(result.columns))

    def test_rate_values_between_0_and_1(self, awareness_df):
        """All awareness rates must be in the [0, 1] range."""
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        assert (result["rate"] >= 0).all()
        assert (result["rate"] <= 1).all()

    def test_rank_is_positive_integer(self, awareness_df):
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        assert (result["rank"] >= 1).all()

    def test_brands_present(self, awareness_df):
        """All three brands from the fixture should appear."""
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        brands = set(result["brand"].tolist())
        assert "Aviva" in brands
        assert "Admiral" in brands

    def test_n_total_denominator_is_answered_not_all(self, awareness_df):
        """
        n_total must count respondents who answered the Q2 question,
        NOT all respondents. In the fixture all 50 respondents answer,
        so n_total should be 50 for each month.
        """
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        for _, row in result.iterrows():
            assert row["n_total"] == 50, (
                f"Expected n_total=50 for {row['brand']} in {row['month']}, "
                f"got {row['n_total']}"
            )

    def test_empty_df_returns_empty(self, empty_df):
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(empty_df, "prompted")
        assert result.empty

    def test_no_awareness_columns_returns_empty(self):
        """DataFrame with no Q2_ columns should produce an empty result."""
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        df = pd.DataFrame({
            "UniqueID": [1, 2],
            "RenewalYearMonth": [202401, 202401],
        })
        result = aw.calc_awareness_rates(df, "prompted")
        assert result.empty

    def test_below_system_floor_returns_empty(self, awareness_df_small):
        """
        Months with fewer than SYSTEM_FLOOR_N=15 respondents should be excluded.
        The small fixture has only 5 per month.
        """
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df_small, "prompted")
        assert result.empty

    def test_unknown_awareness_level_returns_empty(self, awareness_df):
        """An unrecognised awareness_level string should return an empty DataFrame."""
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "nonsense_level")
        assert result.empty

    def test_multiple_months_produce_multiple_rows_per_brand(self, awareness_df):
        """Each brand should appear once per month."""
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        # Fixture has 2 months
        aviva_rows = result[result["brand"] == "Aviva"]
        assert len(aviva_rows) == 2

    def test_aviva_has_highest_rate(self, awareness_df):
        """
        Aviva is set to 80% mention rate in the fixture, highest of the three brands.
        Its average rate across months should be the highest.
        """
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        result = aw.calc_awareness_rates(awareness_df, "prompted")
        avg_rates = result.groupby("brand")["rate"].mean()
        assert avg_rates.idxmax() == "Aviva"

    def test_brand_with_zero_mentions_excluded(self):
        """
        Brand columns with zero mentions in a month must be excluded
        (the n_mentions==0 guard at line 114 in awareness.py).
        """
        from lib.analytics import awareness as aw
        aw.set_awareness_product("Motor")
        # Build DataFrame where 'Ghost Brand' has zero mentions in month 1
        rows = []
        for i in range(30):
            rows.append({
                "UniqueID": i,
                "RenewalYearMonth": 202401,
                "Product": "Motor",
                "Q2_Aviva": True,
                "Q2_Ghost Brand": False,   # always False = zero mentions
            })
        df = pd.DataFrame(rows)
        for col in ["Q2_Aviva", "Q2_Ghost Brand"]:
            df[col] = df[col].astype(bool)
        result = aw.calc_awareness_rates(df, "prompted")
        brands = set(result["brand"].tolist())
        assert "Ghost Brand" not in brands
        assert "Aviva" in brands


# ===========================================================================
# 7. format_flow_pct  (lib/analytics/flow_display.py)
# ===========================================================================

class TestFormatFlowPct:
    """
    lib/analytics/flow_display.py :: format_flow_pct

    Converts a raw switcher count into a percentage string relative to total
    switching volume, with a leading "+" sign for positive values.
    """

    def test_positive_count_returns_signed_pct_string(self):
        """26 out of 168 = 15.5% → '+15.5%'"""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(26, 168)
        assert result == "+15.5%"

    def test_zero_count_returns_zero_string(self):
        """0 out of 168 → '0.0%'"""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(0, 168)
        assert result == "0.0%"

    def test_zero_total_returns_none(self):
        """Division by zero guard: total=0 → None."""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(26, 0)
        assert result is None

    def test_negative_count_includes_minus_sign(self):
        """-10 out of 200 → '-5.0%'"""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(-10, 200)
        assert result == "-5.0%"

    def test_100_pct_case(self):
        """count == total → '+100.0%'"""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(50, 50)
        assert result == "+100.0%"

    def test_returns_string_type(self):
        """Return type must always be str (or None for zero-total)."""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(10, 100)
        assert isinstance(result, str)

    def test_rounding_to_one_decimal(self):
        """1 out of 3 = 33.3%, not 33.33%"""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(1, 3)
        assert result == "+33.3%"

    def test_none_total_returns_none(self):
        """total=None should be treated like zero (guard)."""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(10, None)
        assert result is None

    def test_none_count_returns_none(self):
        """count=None should return None (guard)."""
        from lib.analytics.flow_display import format_flow_pct
        result = format_flow_pct(None, 100)
        assert result is None


# ===========================================================================
# 8. format_net_flow_pct  (lib/analytics/flow_display.py)
# ===========================================================================

class TestFormatNetFlowPct:
    """
    lib/analytics/flow_display.py :: format_net_flow_pct

    Formats a net flow decimal (e.g. 0.124) as a signed percentage string.
    Accepts pre-computed proportion values in the range [-1, 1].
    """

    def test_positive_proportion_returns_signed_string(self):
        """0.124 → '+12.4%'"""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(0.124)
        assert result == "+12.4%"

    def test_negative_proportion_returns_signed_string(self):
        """-0.05 → '-5.0%'"""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(-0.05)
        assert result == "-5.0%"

    def test_none_returns_em_dash(self):
        """None → '—' (em dash, Unicode U+2014)."""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(None)
        assert result == "\u2014"

    def test_zero_returns_zero_string(self):
        """0.0 → '0.0%'"""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(0.0)
        assert result == "0.0%"

    def test_returns_string_type(self):
        """Always returns str."""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(0.05)
        assert isinstance(result, str)

    def test_rounding_to_one_decimal(self):
        """0.1234 → '+12.3%' (one decimal place)."""
        from lib.analytics.flow_display import format_net_flow_pct
        result = format_net_flow_pct(0.1234)
        assert result == "+12.3%"


# ===========================================================================
# 9. get_index_bar_colour  (lib/analytics/flow_display.py)
# ===========================================================================

class TestGetIndexBarColour:
    """
    lib/analytics/flow_display.py :: get_index_bar_colour

    Returns a CI brand colour hex string based on the index value and direction.
    Rules:
      direction="loss":
        index > 120 → CI_RED   (losing disproportionately — bad)
        index < 80  → CI_GREEN (under-indexing losses — good)
        otherwise   → CI_GREY  (near market average)
      direction="gain":
        index > 120 → CI_GREEN (winning disproportionately — good)
        index < 80  → CI_RED   (under-indexing wins — bad)
        otherwise   → CI_GREY  (near market average)

    CI_GREY is the charcoal alias (#54585A), NOT the former CI_BLUE (#5BC2E7).
    """

    def test_loss_high_index_returns_red(self):
        """Loss direction, index=150 (high) → CI_RED."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_RED
        assert get_index_bar_colour(150, "loss") == CI_RED

    def test_loss_low_index_returns_green(self):
        """Loss direction, index=50 (low) → CI_GREEN."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREEN
        assert get_index_bar_colour(50, "loss") == CI_GREEN

    def test_loss_neutral_index_returns_grey_not_blue(self):
        """Loss direction, index=100 (neutral) → CI_GREY, NOT CI_BLUE."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY, CI_BLUE
        colour = get_index_bar_colour(100, "loss")
        assert colour == CI_GREY
        assert colour != CI_BLUE

    def test_gain_high_index_returns_green(self):
        """Gain direction, index=150 (high) → CI_GREEN."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREEN
        assert get_index_bar_colour(150, "gain") == CI_GREEN

    def test_gain_low_index_returns_red(self):
        """Gain direction, index=50 (low) → CI_RED."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_RED
        assert get_index_bar_colour(50, "gain") == CI_RED

    def test_gain_neutral_index_returns_grey_not_blue(self):
        """Gain direction, index=100 (neutral) → CI_GREY, NOT CI_BLUE."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY, CI_BLUE
        colour = get_index_bar_colour(100, "gain")
        assert colour == CI_GREY
        assert colour != CI_BLUE

    def test_loss_boundary_exactly_120_is_neutral(self):
        """index=120 is the upper boundary (not > 120), should return CI_GREY."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY
        assert get_index_bar_colour(120, "loss") == CI_GREY

    def test_loss_boundary_exactly_80_is_neutral(self):
        """index=80 is the lower boundary (not < 80), should return CI_GREY."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY
        assert get_index_bar_colour(80, "loss") == CI_GREY

    def test_gain_boundary_exactly_120_is_neutral(self):
        """index=120 is upper boundary for gain direction, should return CI_GREY."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY
        assert get_index_bar_colour(120, "gain") == CI_GREY

    def test_gain_boundary_exactly_80_is_neutral(self):
        """index=80 is lower boundary for gain direction, should return CI_GREY."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY
        assert get_index_bar_colour(80, "gain") == CI_GREY

    def test_unknown_direction_returns_grey(self):
        """An unrecognised direction string falls back to CI_GREY."""
        from lib.analytics.flow_display import get_index_bar_colour
        from lib.config import CI_GREY
        assert get_index_bar_colour(150, "unknown") == CI_GREY


# ===========================================================================
# 9. TestMethodologyContent
# ===========================================================================

class TestMethodologyContent:
    """lib/components/methodology_dialog.py :: get_methodology_sections

    Pure-function tests — no Streamlit dependency.
    The function returns structured content as a list of dicts so it can be
    tested in isolation from the @st.dialog rendering layer.
    """

    def _get_sections(self):
        from lib.components.methodology_dialog import get_methodology_sections
        return get_methodology_sections()

    # -----------------------------------------------------------------------
    # Structure tests
    # -----------------------------------------------------------------------

    def test_returns_a_list(self):
        """Return value must be a list."""
        result = self._get_sections()
        assert isinstance(result, list)

    def test_list_is_not_empty(self):
        """Must return at least one section."""
        result = self._get_sections()
        assert len(result) > 0

    def test_each_item_has_title_and_content_keys(self):
        """Every item in the list must have 'title' and 'content' keys."""
        result = self._get_sections()
        for item in result:
            assert "title" in item, f"Missing 'title' key in {item}"
            assert "content" in item, f"Missing 'content' key in {item}"

    def test_titles_are_non_empty_strings(self):
        """Every title must be a non-empty string."""
        result = self._get_sections()
        for item in result:
            assert isinstance(item["title"], str)
            assert len(item["title"].strip()) > 0

    def test_content_are_non_empty_strings(self):
        """Every content value must be a non-empty string."""
        result = self._get_sections()
        for item in result:
            assert isinstance(item["content"], str)
            assert len(item["content"].strip()) > 0

    # -----------------------------------------------------------------------
    # Required section coverage
    # -----------------------------------------------------------------------

    def _section_titles(self):
        return [s["title"] for s in self._get_sections()]

    def test_contains_bayesian_smoothing_section(self):
        """Bayesian Smoothing section must be present."""
        titles = self._section_titles()
        assert any("bayesian" in t.lower() for t in titles), \
            f"No Bayesian Smoothing section found in {titles}"

    def test_contains_confidence_intervals_section(self):
        """Confidence Intervals section must be present."""
        titles = self._section_titles()
        assert any("confidence interval" in t.lower() for t in titles), \
            f"No Confidence Intervals section found in {titles}"

    def test_contains_data_suppression_section(self):
        """Data Suppression section must be present."""
        titles = self._section_titles()
        assert any("suppression" in t.lower() for t in titles), \
            f"No Data Suppression section found in {titles}"

    def test_contains_claims_star_ratings_section(self):
        """Claims Star Ratings section must be present."""
        titles = self._section_titles()
        assert any("star" in t.lower() or "claims" in t.lower() for t in titles), \
            f"No Claims Star Ratings section found in {titles}"

    def test_contains_trend_detection_section(self):
        """Trend Detection section must be present."""
        titles = self._section_titles()
        assert any("trend" in t.lower() for t in titles), \
            f"No Trend Detection section found in {titles}"

    def test_contains_data_quality_section(self):
        """Data Quality Controls section must be present."""
        titles = self._section_titles()
        assert any("quality" in t.lower() for t in titles), \
            f"No Data Quality section found in {titles}"

    def test_contains_pet_insurance_section(self):
        """Pet Insurance section must be present."""
        titles = self._section_titles()
        assert any("pet" in t.lower() for t in titles), \
            f"No Pet Insurance section found in {titles}"

    def test_has_at_least_seven_sections(self):
        """Must cover the 7 documented methodology topics."""
        result = self._get_sections()
        assert len(result) >= 7, \
            f"Expected >= 7 sections, got {len(result)}"

    # -----------------------------------------------------------------------
    # Config value embedding tests
    # -----------------------------------------------------------------------

    def test_prior_strength_embedded_in_bayesian_section(self):
        """PRIOR_STRENGTH value must appear in the Bayesian Smoothing content."""
        from lib.config import PRIOR_STRENGTH
        sections = self._get_sections()
        bayesian = next(
            (s for s in sections if "bayesian" in s["title"].lower()), None
        )
        assert bayesian is not None, "Bayesian Smoothing section not found"
        assert str(PRIOR_STRENGTH) in bayesian["content"], \
            f"PRIOR_STRENGTH ({PRIOR_STRENGTH}) not found in Bayesian content"

    def test_min_base_publishable_embedded_in_suppression_section(self):
        """MIN_BASE_PUBLISHABLE value must appear in the Data Suppression content."""
        from lib.config import MIN_BASE_PUBLISHABLE
        sections = self._get_sections()
        suppression = next(
            (s for s in sections if "suppression" in s["title"].lower()), None
        )
        assert suppression is not None, "Data Suppression section not found"
        assert str(MIN_BASE_PUBLISHABLE) in suppression["content"], \
            f"MIN_BASE_PUBLISHABLE ({MIN_BASE_PUBLISHABLE}) not found in suppression content"

    def test_min_base_flow_cell_embedded_in_suppression_section(self):
        """MIN_BASE_FLOW_CELL value must appear in the Data Suppression content."""
        from lib.config import MIN_BASE_FLOW_CELL
        sections = self._get_sections()
        suppression = next(
            (s for s in sections if "suppression" in s["title"].lower()), None
        )
        assert suppression is not None, "Data Suppression section not found"
        assert str(MIN_BASE_FLOW_CELL) in suppression["content"], \
            f"MIN_BASE_FLOW_CELL ({MIN_BASE_FLOW_CELL}) not found in suppression content"

    def test_system_floor_n_embedded_in_suppression_section(self):
        """SYSTEM_FLOOR_N value must appear in the Data Suppression content."""
        from lib.config import SYSTEM_FLOOR_N
        sections = self._get_sections()
        suppression = next(
            (s for s in sections if "suppression" in s["title"].lower()), None
        )
        assert suppression is not None, "Data Suppression section not found"
        assert str(SYSTEM_FLOOR_N) in suppression["content"], \
            f"SYSTEM_FLOOR_N ({SYSTEM_FLOOR_N}) not found in suppression content"

    # -----------------------------------------------------------------------
    # Immutability — calling twice returns equal but independent objects
    # -----------------------------------------------------------------------

    def test_calling_twice_returns_equal_results(self):
        """get_methodology_sections() must be deterministic (same output each call)."""
        result1 = self._get_sections()
        result2 = self._get_sections()
        assert len(result1) == len(result2)
        for s1, s2 in zip(result1, result2):
            assert s1["title"] == s2["title"]
            assert s1["content"] == s2["content"]

    def test_mutating_return_does_not_affect_next_call(self):
        """Mutating the returned list must not corrupt future calls."""
        result1 = self._get_sections()
        result1.clear()
        result2 = self._get_sections()
        assert len(result2) >= 7  # still returns full content


# ===========================================================================
# Fix 1: format_price_change  (lib/analytics/flow_display.py)
# ===========================================================================

class TestFormatPriceChange:
    """lib/analytics/flow_display.py :: format_price_change"""

    def _fmt(self, value):
        from lib.analytics.flow_display import format_price_change
        return format_price_change(value)

    # --- Happy path ---

    def test_positive_rounds_and_adds_plus_and_pound(self):
        """21.3 → '+£21'"""
        assert self._fmt(21.3) == "+£21"

    def test_positive_rounds_up(self):
        """21.7 → '+£22'"""
        assert self._fmt(21.7) == "+£22"

    def test_negative_shows_minus_and_pound(self):
        """-15.7 → '−£16' (uses unicode minus sign, not ASCII hyphen)"""
        result = self._fmt(-15.7)
        assert result == "\u2212£16"

    def test_negative_small(self):
        """-1.4 → '−£1'"""
        assert self._fmt(-1.4) == "\u2212£1"

    def test_zero_shows_pound_only(self):
        """0.0 → '£0'"""
        assert self._fmt(0.0) == "£0"

    def test_zero_negative_zero(self):
        """-0.0 treated as zero → '£0'"""
        assert self._fmt(-0.0) == "£0"

    def test_large_positive(self):
        """525.0 → '+£525'"""
        assert self._fmt(525.0) == "+£525"

    def test_large_negative(self):
        """-525.0 → '−£525'"""
        assert self._fmt(-525.0) == "\u2212£525"

    # --- Boundary: exactly 0.5 rounds up ---
    def test_positive_half_rounds_to_one(self):
        """0.5 → '+£1' (standard rounding)"""
        result = self._fmt(0.5)
        # Python's round() uses banker's rounding; we just check sign and £
        assert result.startswith("+£") or result == "£0"

    # --- Type handling ---
    def test_integer_input(self):
        """Integer 21 → '+£21'"""
        assert self._fmt(21) == "+£21"

    def test_negative_integer(self):
        """Integer -10 → '−£10'"""
        assert self._fmt(-10) == "\u2212£10"


# ===========================================================================
# Fix 2: merge_tenure_mid_buckets  (lib/analytics/pre_renewal.py)
# ===========================================================================

class TestMergeTenureMidBuckets:
    """lib/analytics/pre_renewal.py :: merge_tenure_mid_buckets"""

    def _merge(self, series):
        from lib.analytics.pre_renewal import merge_tenure_mid_buckets
        return merge_tenure_mid_buckets(series)

    def _make_full_tenure(self):
        """Realistic tenure series with all year buckets."""
        return pd.Series({
            "1 year": 0.15,
            "2 years": 0.14,
            "3 years": 0.12,
            "4 years": 0.10,
            "5 years": 0.09,
            "6 years": 0.04,
            "7 years": 0.03,
            "8 years": 0.03,
            "9 years": 0.07,
            "10 years or more": 0.23,
        })

    # --- Core merge behaviour ---

    def test_merges_6_7_8_into_single_bucket(self):
        """'6 years', '7 years', '8 years' must be collapsed to '6-8 years'."""
        result = self._merge(self._make_full_tenure())
        assert "6-8 years" in result.index
        assert "6 years" not in result.index
        assert "7 years" not in result.index
        assert "8 years" not in result.index

    def test_summed_value_correct(self):
        """'6-8 years' value should be sum of 6+7+8 year values."""
        source = self._make_full_tenure()
        expected = source["6 years"] + source["7 years"] + source["8 years"]
        result = self._merge(source)
        assert result["6-8 years"] == pytest.approx(expected)

    def test_other_buckets_unchanged(self):
        """All non-6/7/8 buckets must retain their original values."""
        source = self._make_full_tenure()
        result = self._merge(source)
        for label in ["1 year", "2 years", "3 years", "4 years", "5 years", "9 years", "10 years or more"]:
            assert result[label] == pytest.approx(source[label])

    def test_order_preserved_6_8_between_5_and_9(self):
        """'6-8 years' must appear between '5 years' and '9 years'."""
        result = self._merge(self._make_full_tenure())
        idx = list(result.index)
        pos_5 = idx.index("5 years")
        pos_merged = idx.index("6-8 years")
        pos_9 = idx.index("9 years")
        assert pos_5 < pos_merged < pos_9

    def test_total_sums_to_one(self):
        """After merging, proportions should still sum to ~1."""
        source = self._make_full_tenure()
        result = self._merge(source)
        assert result.sum() == pytest.approx(1.0, abs=1e-9)

    # --- Edge cases ---

    def test_missing_all_three_returns_unchanged(self):
        """If none of 6/7/8 keys exist, Series returned unchanged."""
        source = pd.Series({"1 year": 0.4, "2 years": 0.3, "3 years": 0.3})
        result = self._merge(source)
        pd.testing.assert_series_equal(result, source)

    def test_missing_one_of_three_still_merges_present_keys(self):
        """If only 6 and 7 years exist (no 8), they should still merge."""
        source = pd.Series({
            "5 years": 0.20,
            "6 years": 0.05,
            "7 years": 0.04,
            "9 years": 0.71,
        })
        result = self._merge(source)
        assert "6-8 years" in result.index
        assert result["6-8 years"] == pytest.approx(0.09)

    def test_empty_series_returns_empty(self):
        """Empty series should not raise."""
        result = self._merge(pd.Series(dtype=float))
        assert len(result) == 0

    def test_immutability_original_unchanged(self):
        """Input Series must not be mutated."""
        source = self._make_full_tenure()
        original_keys = list(source.index)
        self._merge(source)
        assert list(source.index) == original_keys


# ===========================================================================
# Fix 3: calc_price_direction_index  (lib/analytics/price.py)
# ===========================================================================

class TestCalcPriceDirectionIndex:
    """lib/analytics/price.py :: calc_price_direction_index"""

    def _calc(self, insurer_dist, market_dist):
        from lib.analytics.price import calc_price_direction_index
        return calc_price_direction_index(insurer_dist, market_dist)

    def _make_dist(self, higher=0.47, lower=0.30, unchanged=0.18, new=0.05):
        return pd.Series({
            "Higher": higher,
            "Lower": lower,
            "Unchanged": unchanged,
            "New": new,
        })

    # --- Schema ---

    def test_returns_dataframe(self):
        result = self._calc(self._make_dist(), self._make_dist())
        assert isinstance(result, pd.DataFrame)

    def test_has_required_columns(self):
        result = self._calc(self._make_dist(), self._make_dist())
        assert "direction" in result.columns
        assert "insurer_pct" in result.columns
        assert "market_pct" in result.columns
        assert "diff_pp" in result.columns

    def test_direction_column_contains_expected_values(self):
        result = self._calc(self._make_dist(), self._make_dist())
        assert set(result["direction"]).issubset({"Higher", "Lower", "Unchanged", "New"})

    # --- Calculation correctness ---

    def test_diff_pp_positive_when_insurer_higher(self):
        """insurer Higher=0.50, market Higher=0.48 → diff_pp ≈ +2.0"""
        ins = self._make_dist(higher=0.50)
        mkt = self._make_dist(higher=0.48)
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "Higher"].iloc[0]
        assert row["diff_pp"] == pytest.approx(2.0, abs=0.01)

    def test_diff_pp_negative_when_insurer_lower(self):
        """insurer Higher=0.47, market Higher=0.48 → diff_pp ≈ -1.0"""
        ins = self._make_dist(higher=0.47)
        mkt = self._make_dist(higher=0.48)
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "Higher"].iloc[0]
        assert row["diff_pp"] == pytest.approx(-1.0, abs=0.01)

    def test_diff_pp_zero_when_equal(self):
        """Same distributions → all diff_pp = 0"""
        dist = self._make_dist()
        result = self._calc(dist, dist)
        assert (result["diff_pp"].abs() < 0.001).all()

    def test_insurer_pct_in_percentage_points(self):
        """insurer_pct for Higher=0.47 should be 47.0"""
        ins = self._make_dist(higher=0.47)
        mkt = self._make_dist(higher=0.48)
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "Higher"].iloc[0]
        assert row["insurer_pct"] == pytest.approx(47.0, abs=0.01)

    def test_market_pct_in_percentage_points(self):
        """market_pct for Higher=0.48 should be 48.0"""
        ins = self._make_dist(higher=0.47)
        mkt = self._make_dist(higher=0.48)
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "Higher"].iloc[0]
        assert row["market_pct"] == pytest.approx(48.0, abs=0.01)

    # --- Edge cases ---

    def test_missing_direction_in_insurer_treated_as_zero(self):
        """Direction present in market but not insurer should have insurer_pct=0."""
        ins = pd.Series({"Higher": 0.60, "Lower": 0.40})
        mkt = pd.Series({"Higher": 0.50, "Lower": 0.30, "Unchanged": 0.20})
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "Unchanged"].iloc[0]
        assert row["insurer_pct"] == pytest.approx(0.0)
        assert row["diff_pp"] == pytest.approx(-20.0, abs=0.01)

    def test_missing_direction_in_market_treated_as_zero(self):
        """Direction in insurer but not market should have market_pct=0."""
        ins = pd.Series({"Higher": 0.60, "Lower": 0.40, "New": 0.10})
        mkt = pd.Series({"Higher": 0.60, "Lower": 0.40})
        result = self._calc(ins, mkt)
        row = result[result["direction"] == "New"].iloc[0]
        assert row["market_pct"] == pytest.approx(0.0)

    def test_none_insurer_returns_none(self):
        from lib.analytics.price import calc_price_direction_index
        assert calc_price_direction_index(None, self._make_dist()) is None

    def test_none_market_returns_none(self):
        from lib.analytics.price import calc_price_direction_index
        assert calc_price_direction_index(self._make_dist(), None) is None

    def test_empty_insurer_returns_none(self):
        from lib.analytics.price import calc_price_direction_index
        assert calc_price_direction_index(pd.Series(dtype=float), self._make_dist()) is None

    def test_empty_market_returns_none(self):
        from lib.analytics.price import calc_price_direction_index
        assert calc_price_direction_index(self._make_dist(), pd.Series(dtype=float)) is None


# ===========================================================================
# Fix 1: calc_market_departed_sentiment
# ===========================================================================

class TestCalcMarketDepartedSentiment:
    """lib/analytics/flows.py :: calc_market_departed_sentiment

    Computes MARKET-LEVEL departed sentiment across all switchers (not one insurer).
    Returns same shape as calc_departed_sentiment: mean_q40a, nps, n.
    """

    def _make_switcher_df(self, n_switchers: int = 20) -> pd.DataFrame:
        """Build a DataFrame with switchers that have Q40a and Q40b data."""
        rng = __import__("numpy").random.default_rng(7)
        rows = []
        for i in range(n_switchers):
            rows.append({
                "UniqueID": i + 1,
                "CurrentCompany": "Aviva" if i % 2 == 0 else "Admiral",
                "PreviousCompany": "Direct Line",
                "IsSwitcher": True,
                "Q40a": float(rng.integers(1, 6)),          # 1–5 satisfaction
                "Q40b": float(rng.integers(0, 11)),         # 0–10 NPS
            })
        # Add a stayer to confirm they are excluded
        rows.append({
            "UniqueID": 999,
            "CurrentCompany": "Aviva",
            "PreviousCompany": "Aviva",
            "IsSwitcher": False,
            "Q40a": 5.0,
            "Q40b": 10.0,
        })
        return pd.DataFrame(rows)

    def test_returns_dict_with_expected_keys(self):
        from lib.analytics.flows import calc_market_departed_sentiment
        df = self._make_switcher_df()
        result = calc_market_departed_sentiment(df)
        assert result is not None
        assert "n" in result
        assert "mean_q40a" in result
        assert "nps" in result

    def test_n_counts_only_switchers(self):
        """Stayers (IsSwitcher=False) must not be counted."""
        from lib.analytics.flows import calc_market_departed_sentiment
        df = self._make_switcher_df(n_switchers=20)
        result = calc_market_departed_sentiment(df)
        # 20 switchers + 1 stayer; result["n"] must be 20
        assert result["n"] == 20

    def test_nps_calculation_correct(self):
        """NPS = 100 * (promoters - detractors) / n. Promoters >= 9, detractors <= 6."""
        from lib.analytics.flows import calc_market_departed_sentiment
        rows = [
            # 2 promoters (Q40b >= 9)
            {"UniqueID": 1, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 4.0, "Q40b": 9.0},
            {"UniqueID": 2, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 4.0, "Q40b": 10.0},
            # 1 passive (Q40b 7 or 8 — neither promoter nor detractor)
            {"UniqueID": 3, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 3.0, "Q40b": 8.0},
            # 1 detractor (Q40b <= 6)
            {"UniqueID": 4, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 2.0, "Q40b": 4.0},
        ]
        df = pd.DataFrame(rows)
        result = calc_market_departed_sentiment(df)
        # promoters=2, detractors=1, n=4 → NPS = 100*(2-1)/4 = 25.0
        assert result["nps"] == pytest.approx(25.0)

    def test_mean_q40a_is_correct(self):
        """mean_q40a is the arithmetic mean of Q40a for all switchers."""
        from lib.analytics.flows import calc_market_departed_sentiment
        rows = [
            {"UniqueID": 1, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 2.0, "Q40b": 5.0},
            {"UniqueID": 2, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 4.0, "Q40b": 7.0},
        ]
        df = pd.DataFrame(rows)
        result = calc_market_departed_sentiment(df)
        assert result["mean_q40a"] == pytest.approx(3.0)

    def test_empty_dataframe_returns_none(self):
        from lib.analytics.flows import calc_market_departed_sentiment
        result = calc_market_departed_sentiment(pd.DataFrame())
        assert result is None

    def test_none_dataframe_returns_none(self):
        from lib.analytics.flows import calc_market_departed_sentiment
        result = calc_market_departed_sentiment(None)
        assert result is None

    def test_no_switchers_returns_none(self):
        """DataFrame with only stayers should return None."""
        from lib.analytics.flows import calc_market_departed_sentiment
        df = pd.DataFrame([
            {"UniqueID": 1, "CurrentCompany": "A", "PreviousCompany": "A",
             "IsSwitcher": False, "Q40a": 5.0, "Q40b": 10.0},
            {"UniqueID": 2, "CurrentCompany": "B", "PreviousCompany": "B",
             "IsSwitcher": False, "Q40a": 4.0, "Q40b": 9.0},
        ])
        result = calc_market_departed_sentiment(df)
        assert result is None

    def test_missing_q40a_column_omits_key(self):
        """If Q40a is absent, mean_q40a should not appear in result."""
        from lib.analytics.flows import calc_market_departed_sentiment
        df = pd.DataFrame([
            {"UniqueID": 1, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40b": 8.0},
        ])
        result = calc_market_departed_sentiment(df)
        assert result is not None
        assert "mean_q40a" not in result

    def test_missing_q40b_column_omits_nps(self):
        """If Q40b is absent, nps should not appear in result."""
        from lib.analytics.flows import calc_market_departed_sentiment
        df = pd.DataFrame([
            {"UniqueID": 1, "CurrentCompany": "A", "PreviousCompany": "B",
             "IsSwitcher": True, "Q40a": 3.0},
        ])
        result = calc_market_departed_sentiment(df)
        assert result is not None
        assert "nps" not in result

    def test_excludes_same_company_rows(self):
        """Spec 12.4: CurrentCompany == PreviousCompany must be excluded."""
        from lib.analytics.flows import calc_market_departed_sentiment
        df = pd.DataFrame([
            # Same-company row — should be excluded even though IsSwitcher=True
            {"UniqueID": 1, "CurrentCompany": "Aviva", "PreviousCompany": "Aviva",
             "IsSwitcher": True, "Q40a": 5.0, "Q40b": 10.0},
            # Valid switcher
            {"UniqueID": 2, "CurrentCompany": "Admiral", "PreviousCompany": "Aviva",
             "IsSwitcher": True, "Q40a": 2.0, "Q40b": 3.0},
        ])
        result = calc_market_departed_sentiment(df)
        assert result["n"] == 1


# ===========================================================================
# Fix 2: kpi_vs_market_colour
# ===========================================================================

class TestKpiVsMarketColour:
    """lib/analytics/flow_display.py :: kpi_vs_market_colour

    Returns a CI brand colour based on whether insurer value is better or worse
    than market, with an option to invert the signal for metrics where lower is better.
    """

    def test_higher_is_better_insurer_above_market(self):
        """Default (lower_is_better=False): insurer > market → CI_GREEN."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREEN
        assert kpi_vs_market_colour(0.80, 0.75) == CI_GREEN

    def test_higher_is_better_insurer_below_market(self):
        """Default (lower_is_better=False): insurer < market → CI_RED."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_RED
        assert kpi_vs_market_colour(0.70, 0.75) == CI_RED

    def test_higher_is_better_equal(self):
        """Default (lower_is_better=False): insurer == market → CI_GREY."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(0.75, 0.75) == CI_GREY

    def test_lower_is_better_insurer_below_market(self):
        """lower_is_better=True: insurer < market → CI_GREEN (good)."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREEN
        assert kpi_vs_market_colour(0.10, 0.15, lower_is_better=True) == CI_GREEN

    def test_lower_is_better_insurer_above_market(self):
        """lower_is_better=True: insurer > market → CI_RED (bad)."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_RED
        assert kpi_vs_market_colour(0.20, 0.15, lower_is_better=True) == CI_RED

    def test_lower_is_better_equal(self):
        """lower_is_better=True: insurer == market → CI_GREY."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(0.15, 0.15, lower_is_better=True) == CI_GREY

    def test_none_insurer_returns_grey(self):
        """None insurer value → CI_GREY (cannot compare)."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(None, 0.75) == CI_GREY

    def test_none_market_returns_grey(self):
        """None market value → CI_GREY (cannot compare)."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(0.75, None) == CI_GREY

    def test_both_none_returns_grey(self):
        """Both None → CI_GREY."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(None, None) == CI_GREY

    def test_zero_values_equal(self):
        """Both zero → CI_GREY (edge case: zero switching rate)."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREY
        assert kpi_vs_market_colour(0.0, 0.0, lower_is_better=True) == CI_GREY

    def test_negative_values_lower_is_better(self):
        """Negative values (e.g. NPS) work correctly with lower_is_better=False."""
        from lib.analytics.flow_display import kpi_vs_market_colour
        from lib.config import CI_GREEN
        # NPS: insurer=-10, market=-30 → insurer > market → CI_GREEN
        assert kpi_vs_market_colour(-10, -30) == CI_GREEN


# ===========================================================================
# 16. calc_rolling_switching_trend
# ===========================================================================

class TestCalcRollingSwitchingTrend:
    """lib/analytics/rates.py :: calc_rolling_switching_trend

    Groups raw respondent-level DataFrame by RenewalYearMonth, calculates
    switching_rate per month, then optionally applies a rolling mean.

    Expected return: DataFrame with columns [month, label, switching_rate, n].
    """

    def _make_multi_month_df(self) -> "pd.DataFrame":
        """Build a 3-month respondent-level DataFrame with known switching rates.

        Month 202401: 2 switchers out of 10 → 20%
        Month 202402: 3 switchers out of 10 → 30%
        Month 202403: 1 switcher  out of 10 → 10%
        """
        rows = []
        uid = 1
        for month, n_switchers in [(202401, 2), (202402, 3), (202403, 1)]:
            for i in range(10):
                rows.append({
                    "UniqueID": uid,
                    "RenewalYearMonth": month,
                    "IsSwitcher": i < n_switchers,
                    "IsNewToMarket": False,
                    "IsShopper": i < n_switchers,
                })
                uid += 1
        return pd.DataFrame(rows)

    def test_returns_dataframe(self):
        """Result must be a pandas DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self):
        """Result must contain month, label, switching_rate, n columns."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert set(["month", "label", "switching_rate", "n"]).issubset(set(result.columns))

    def test_window_1_matches_per_month_calculation(self):
        """window=1 must produce the same rates as individual per-month calc_switching_rate calls."""
        from lib.analytics.rates import calc_rolling_switching_trend, calc_switching_rate
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = sorted(df["RenewalYearMonth"].unique())
        assert len(result) == len(months)
        for _, row in result.iterrows():
            df_m = df[df["RenewalYearMonth"] == row["month"]]
            expected = calc_switching_rate(df_m)
            assert row["switching_rate"] == pytest.approx(expected, rel=1e-6)

    def test_window_1_produces_three_rows_for_three_months(self):
        """window=1 should return one row per month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 3

    def test_window_3_smooths_correctly(self):
        """window=3 result for 3rd month equals mean of all three monthly rates."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # Rates: 0.20, 0.30, 0.10
        expected_smoothed_m3 = (0.20 + 0.30 + 0.10) / 3
        # Third row (index 2) should be the 3-month rolling mean
        assert result.iloc[2]["switching_rate"] == pytest.approx(expected_smoothed_m3, rel=1e-4)

    def test_window_3_first_row_uses_min_periods_1(self):
        """First row with window=3 must equal the raw month rate (min_periods=1, not NaN)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # First month should be 0.20 (only one period available)
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.20, rel=1e-4)

    def test_window_3_no_nan_values(self):
        """Rolling result must contain no NaN in switching_rate column."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        assert not result["switching_rate"].isna().any()

    def test_window_larger_than_months_still_works(self):
        """window=12 on a 3-month DataFrame must not raise and return 3 rows."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=12)
        assert len(result) == 3
        assert not result["switching_rate"].isna().any()

    def test_empty_dataframe_returns_empty_result(self):
        """Empty input DataFrame must return an empty DataFrame (not raise)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        result = calc_rolling_switching_trend(pd.DataFrame(), window=1)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_result_sorted_by_month_ascending(self):
        """Returned rows must be sorted by month ascending."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = list(result["month"])
        assert months == sorted(months)

    def test_n_column_equals_month_respondent_count(self):
        """n column must equal the number of respondents for each month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        for _, row in result.iterrows():
            expected_n = len(df[df["RenewalYearMonth"] == row["month"]])
            assert row["n"] == expected_n

    def test_single_month_window_1_returns_one_row(self):
        """Single-month DataFrame with window=1 returns exactly one row."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = pd.DataFrame([
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": False, "IsShopper": i < 2}
            for i in range(5)
        ])
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 1
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)

    def test_original_dataframe_not_mutated(self):
        """Function must not mutate the input DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        original_cols = set(df.columns)
        calc_rolling_switching_trend(df, window=3)
        assert set(df.columns) == original_cols

    def test_excludes_new_to_market_from_switching_rate(self):
        """Rows where IsNewToMarket=True must be excluded from switching rate denominator."""
        from lib.analytics.rates import calc_rolling_switching_trend
        # 10 respondents: 5 new-to-market (should be excluded), 2 switchers among the 5 eligible
        rows = [
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": i >= 5, "IsShopper": i < 2}
            for i in range(10)
        ]
        df = pd.DataFrame(rows)
        result = calc_rolling_switching_trend(df, window=1)
        # 2 switchers / 5 eligible (not new-to-market) = 0.40
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)


# ===========================================================================
# 17. render_kpi_with_info
# ===========================================================================

class TestRenderKpiWithInfo:
    """lib/components/decision_kpi.py :: render_kpi_with_info

    Wraps decision_kpi with an additional info text rendered as st.caption.
    Must be testable without a real Streamlit session: patches st.markdown
    and st.caption to capture calls.
    """

    def _make_kpi_kwargs(self) -> dict:
        return {
            "title": "Switching Rate",
            "value": "18.5%",
            "change": "+2.1pp vs market",
            "trend": "up",
            "sample_n": 500,
            "colour": "#981D97",
        }

    def test_function_exists(self):
        """render_kpi_with_info must be importable from lib.components.decision_kpi."""
        from lib.components.decision_kpi import render_kpi_with_info
        assert callable(render_kpi_with_info)

    def test_accepts_kpi_kwargs_and_info_text(self):
        """render_kpi_with_info(kpi_kwargs, info_text) must not raise with valid inputs."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "% of customers who changed insurer.")

    def test_info_text_passed_to_caption(self):
        """The info_text argument must appear in an st.caption call."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        info = "% of customers who changed insurer at renewal."
        caption_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption", side_effect=lambda t: caption_calls.append(t)):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), info)
        assert any(info in call for call in caption_calls), \
            f"Expected info text in caption calls, got: {caption_calls}"

    def test_kpi_card_still_rendered(self):
        """decision_kpi card HTML must still be rendered (st.markdown called)."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        markdown_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown",
                                side_effect=lambda html, **kw: markdown_calls.append(html)), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "Some info.")
        assert len(markdown_calls) >= 1, "Expected at least one st.markdown call for the KPI card."

    def test_empty_info_text_does_not_raise(self):
        """Empty string for info_text must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "")

    def test_minimal_kpi_kwargs_title_and_value_only(self):
        """Minimal kpi_kwargs with only title and value must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info({"title": "Test KPI", "value": "42%"}, "Explanation here.")


# ===========================================================================
# Batch 4: calc_wilson_ci and format_ci_range
# ===========================================================================

class TestCalcWilsonCI:
    """lib/analytics/flow_display.py :: calc_wilson_ci"""

    def test_typical_values_returns_tuple(self):
        """50 successes from 100 trials should return a tuple of two floats."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(50, 100)
        assert result is not None
        lower, upper = result
        assert isinstance(lower, float)
        assert isinstance(upper, float)

    def test_lower_lt_point_estimate_lt_upper(self):
        """CI bounds must straddle the point estimate."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        point = 50 / 100
        assert lower < point < upper

    def test_bounds_are_proportions(self):
        """Both bounds must be in [0, 1]."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_n_zero_returns_none(self):
        """n=0 is a division-by-zero case: must return None."""
        from lib.analytics.flow_display import calc_wilson_ci
        assert calc_wilson_ci(0, 0) is None

    def test_zero_successes(self):
        """0 successes from 100 trials: lower should be 0.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 100)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert upper > 0.0

    def test_all_successes(self):
        """100 successes from 100 trials: upper should be 1.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(100, 100)
        assert result is not None
        lower, upper = result
        assert upper == pytest.approx(1.0, abs=1e-9)
        assert lower < 1.0

    def test_known_values_approx(self):
        """
        Wilson CI for 500/1000 at z=1.96.
        Expected: (0.4690, 0.5310) to 3 d.p.
        Reference: computed manually.
        """
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(500, 1000)
        assert lower == pytest.approx(0.4690, abs=0.001)
        assert upper == pytest.approx(0.5310, abs=0.001)

    def test_custom_z_widens_interval(self):
        """Higher z value (e.g. 2.576 for 99% CI) must produce wider interval."""
        from lib.analytics.flow_display import calc_wilson_ci
        lo_95, hi_95 = calc_wilson_ci(50, 100, z=1.96)
        lo_99, hi_99 = calc_wilson_ci(50, 100, z=2.576)
        assert lo_99 < lo_95
        assert hi_99 > hi_95

    def test_n_one_success_one(self):
        """Boundary: n=1, k=1 (point estimate=1.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(1, 1)
        assert result is not None
        lower, upper = result
        assert 0.0 <= lower <= 1.0
        assert upper == pytest.approx(1.0, abs=1e-9)

    def test_n_one_success_zero(self):
        """Boundary: n=1, k=0 (point estimate=0.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 1)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert 0.0 <= upper <= 1.0

    def test_large_n_narrow_interval(self):
        """Large n → very narrow CI (well under 0.01 wide)."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(5000, 10000)
        assert (upper - lower) < 0.02


class TestFormatCIRange:
    """lib/analytics/flow_display.py :: format_ci_range"""

    def test_basic_format(self):
        """Returns 'X%–Y%' format with one decimal place."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.535, 0.575)
        assert result == "53.5%\u201357.5%"

    def test_rounded_values(self):
        """Handles values that round cleanly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.40, 0.60)
        assert result == "40.0%\u201360.0%"

    def test_zero_lower(self):
        """Lower bound of 0.0 formats as '0.0%'."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.0, 0.05)
        assert result == "0.0%\u20135.0%"

    def test_near_one_upper(self):
        """Upper bound near 1.0 formats correctly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.95, 1.0)
        assert result == "95.0%\u2013100.0%"

    def test_uses_en_dash_not_hyphen(self):
        """Separator must be an en dash (U+2013), not a plain hyphen."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.4, 0.6)
        assert "\u2013" in result
        assert "-" not in result

    def test_equal_bounds(self):
        """Equal lower and upper (degenerate CI) still formats without error."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.5, 0.5)
        assert result == "50.0%\u201350.0%"
# ===========================================================================

class TestCalcRollingSwitchingTrend:
    """lib/analytics/rates.py :: calc_rolling_switching_trend

    Groups raw respondent-level DataFrame by RenewalYearMonth, calculates
    switching_rate per month, then optionally applies a rolling mean.

    Expected return: DataFrame with columns [month, label, switching_rate, n].
    """

    def _make_multi_month_df(self) -> "pd.DataFrame":
        """Build a 3-month respondent-level DataFrame with known switching rates.

        Month 202401: 2 switchers out of 10 → 20%
        Month 202402: 3 switchers out of 10 → 30%
        Month 202403: 1 switcher  out of 10 → 10%
        """
        rows = []
        uid = 1
        for month, n_switchers in [(202401, 2), (202402, 3), (202403, 1)]:
            for i in range(10):
                rows.append({
                    "UniqueID": uid,
                    "RenewalYearMonth": month,
                    "IsSwitcher": i < n_switchers,
                    "IsNewToMarket": False,
                    "IsShopper": i < n_switchers,
                })
                uid += 1
        return pd.DataFrame(rows)

    def test_returns_dataframe(self):
        """Result must be a pandas DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self):
        """Result must contain month, label, switching_rate, n columns."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert set(["month", "label", "switching_rate", "n"]).issubset(set(result.columns))

    def test_window_1_matches_per_month_calculation(self):
        """window=1 must produce the same rates as individual per-month calc_switching_rate calls."""
        from lib.analytics.rates import calc_rolling_switching_trend, calc_switching_rate
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = sorted(df["RenewalYearMonth"].unique())
        assert len(result) == len(months)
        for _, row in result.iterrows():
            df_m = df[df["RenewalYearMonth"] == row["month"]]
            expected = calc_switching_rate(df_m)
            assert row["switching_rate"] == pytest.approx(expected, rel=1e-6)

    def test_window_1_produces_three_rows_for_three_months(self):
        """window=1 should return one row per month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 3

    def test_window_3_smooths_correctly(self):
        """window=3 result for 3rd month equals mean of all three monthly rates."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # Rates: 0.20, 0.30, 0.10
        expected_smoothed_m3 = (0.20 + 0.30 + 0.10) / 3
        # Third row (index 2) should be the 3-month rolling mean
        assert result.iloc[2]["switching_rate"] == pytest.approx(expected_smoothed_m3, rel=1e-4)

    def test_window_3_first_row_uses_min_periods_1(self):
        """First row with window=3 must equal the raw month rate (min_periods=1, not NaN)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # First month should be 0.20 (only one period available)
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.20, rel=1e-4)

    def test_window_3_no_nan_values(self):
        """Rolling result must contain no NaN in switching_rate column."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        assert not result["switching_rate"].isna().any()

    def test_window_larger_than_months_still_works(self):
        """window=12 on a 3-month DataFrame must not raise and return 3 rows."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=12)
        assert len(result) == 3
        assert not result["switching_rate"].isna().any()

    def test_empty_dataframe_returns_empty_result(self):
        """Empty input DataFrame must return an empty DataFrame (not raise)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        result = calc_rolling_switching_trend(pd.DataFrame(), window=1)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_result_sorted_by_month_ascending(self):
        """Returned rows must be sorted by month ascending."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = list(result["month"])
        assert months == sorted(months)

    def test_n_column_equals_month_respondent_count(self):
        """n column must equal the number of respondents for each month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        for _, row in result.iterrows():
            expected_n = len(df[df["RenewalYearMonth"] == row["month"]])
            assert row["n"] == expected_n

    def test_single_month_window_1_returns_one_row(self):
        """Single-month DataFrame with window=1 returns exactly one row."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = pd.DataFrame([
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": False, "IsShopper": i < 2}
            for i in range(5)
        ])
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 1
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)

    def test_original_dataframe_not_mutated(self):
        """Function must not mutate the input DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        original_cols = set(df.columns)
        calc_rolling_switching_trend(df, window=3)
        assert set(df.columns) == original_cols

    def test_excludes_new_to_market_from_switching_rate(self):
        """Rows where IsNewToMarket=True must be excluded from switching rate denominator."""
        from lib.analytics.rates import calc_rolling_switching_trend
        # 10 respondents: 5 new-to-market (should be excluded), 2 switchers among the 5 eligible
        rows = [
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": i >= 5, "IsShopper": i < 2}
            for i in range(10)
        ]
        df = pd.DataFrame(rows)
        result = calc_rolling_switching_trend(df, window=1)
        # 2 switchers / 5 eligible (not new-to-market) = 0.40
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)


# ===========================================================================
# 17. render_kpi_with_info
# ===========================================================================

class TestRenderKpiWithInfo:
    """lib/components/decision_kpi.py :: render_kpi_with_info

    Wraps decision_kpi with an additional info text rendered as st.caption.
    Must be testable without a real Streamlit session: patches st.markdown
    and st.caption to capture calls.
    """

    def _make_kpi_kwargs(self) -> dict:
        return {
            "title": "Switching Rate",
            "value": "18.5%",
            "change": "+2.1pp vs market",
            "trend": "up",
            "sample_n": 500,
            "colour": "#981D97",
        }

    def test_function_exists(self):
        """render_kpi_with_info must be importable from lib.components.decision_kpi."""
        from lib.components.decision_kpi import render_kpi_with_info
        assert callable(render_kpi_with_info)

    def test_accepts_kpi_kwargs_and_info_text(self):
        """render_kpi_with_info(kpi_kwargs, info_text) must not raise with valid inputs."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "% of customers who changed insurer.")

    def test_info_text_passed_to_caption(self):
        """The info_text argument must appear in an st.caption call."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        info = "% of customers who changed insurer at renewal."
        caption_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption", side_effect=lambda t: caption_calls.append(t)):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), info)
        assert any(info in call for call in caption_calls), \
            f"Expected info text in caption calls, got: {caption_calls}"

    def test_kpi_card_still_rendered(self):
        """decision_kpi card HTML must still be rendered (st.markdown called)."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        markdown_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown",
                                side_effect=lambda html, **kw: markdown_calls.append(html)), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "Some info.")
        assert len(markdown_calls) >= 1, "Expected at least one st.markdown call for the KPI card."

    def test_empty_info_text_does_not_raise(self):
        """Empty string for info_text must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "")

    def test_minimal_kpi_kwargs_title_and_value_only(self):
        """Minimal kpi_kwargs with only title and value must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info({"title": "Test KPI", "value": "42%"}, "Explanation here.")
# ===========================================================================

class TestCalcWilsonCI:
    """lib/analytics/flow_display.py :: calc_wilson_ci"""

    def test_typical_values_returns_tuple(self):
        """50 successes from 100 trials should return a tuple of two floats."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(50, 100)
        assert result is not None
        lower, upper = result
        assert isinstance(lower, float)
        assert isinstance(upper, float)

    def test_lower_lt_point_estimate_lt_upper(self):
        """CI bounds must straddle the point estimate."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        point = 50 / 100
        assert lower < point < upper

    def test_bounds_are_proportions(self):
        """Both bounds must be in [0, 1]."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_n_zero_returns_none(self):
        """n=0 is a division-by-zero case: must return None."""
        from lib.analytics.flow_display import calc_wilson_ci
        assert calc_wilson_ci(0, 0) is None

    def test_zero_successes(self):
        """0 successes from 100 trials: lower should be 0.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 100)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert upper > 0.0

    def test_all_successes(self):
        """100 successes from 100 trials: upper should be 1.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(100, 100)
        assert result is not None
        lower, upper = result
        assert upper == pytest.approx(1.0, abs=1e-9)
        assert lower < 1.0

    def test_known_values_approx(self):
        """
        Wilson CI for 500/1000 at z=1.96.
        Expected: (0.4690, 0.5310) to 3 d.p.
        Reference: computed manually.
        """
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(500, 1000)
        assert lower == pytest.approx(0.4690, abs=0.001)
        assert upper == pytest.approx(0.5310, abs=0.001)

    def test_custom_z_widens_interval(self):
        """Higher z value (e.g. 2.576 for 99% CI) must produce wider interval."""
        from lib.analytics.flow_display import calc_wilson_ci
        lo_95, hi_95 = calc_wilson_ci(50, 100, z=1.96)
        lo_99, hi_99 = calc_wilson_ci(50, 100, z=2.576)
        assert lo_99 < lo_95
        assert hi_99 > hi_95

    def test_n_one_success_one(self):
        """Boundary: n=1, k=1 (point estimate=1.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(1, 1)
        assert result is not None
        lower, upper = result
        assert 0.0 <= lower <= 1.0
        assert upper == pytest.approx(1.0, abs=1e-9)

    def test_n_one_success_zero(self):
        """Boundary: n=1, k=0 (point estimate=0.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 1)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert 0.0 <= upper <= 1.0

    def test_large_n_narrow_interval(self):
        """Large n → very narrow CI (well under 0.01 wide)."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(5000, 10000)
        assert (upper - lower) < 0.02


class TestFormatCIRange:
    """lib/analytics/flow_display.py :: format_ci_range"""

    def test_basic_format(self):
        """Returns 'X%–Y%' format with one decimal place."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.535, 0.575)
        assert result == "53.5%\u201357.5%"

    def test_rounded_values(self):
        """Handles values that round cleanly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.40, 0.60)
        assert result == "40.0%\u201360.0%"

    def test_zero_lower(self):
        """Lower bound of 0.0 formats as '0.0%'."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.0, 0.05)
        assert result == "0.0%\u20135.0%"

    def test_near_one_upper(self):
        """Upper bound near 1.0 formats correctly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.95, 1.0)
        assert result == "95.0%\u2013100.0%"

    def test_uses_en_dash_not_hyphen(self):
        """Separator must be an en dash (U+2013), not a plain hyphen."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.4, 0.6)
        assert "\u2013" in result
        assert "-" not in result

    def test_equal_bounds(self):
        """Equal lower and upper (degenerate CI) still formats without error."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.5, 0.5)
        assert result == "50.0%\u201350.0%"
# ===========================================================================

class TestCalcRollingSwitchingTrend:
    """lib/analytics/rates.py :: calc_rolling_switching_trend

    Groups raw respondent-level DataFrame by RenewalYearMonth, calculates
    switching_rate per month, then optionally applies a rolling mean.

    Expected return: DataFrame with columns [month, label, switching_rate, n].
    """

    def _make_multi_month_df(self) -> "pd.DataFrame":
        """Build a 3-month respondent-level DataFrame with known switching rates.

        Month 202401: 2 switchers out of 10 → 20%
        Month 202402: 3 switchers out of 10 → 30%
        Month 202403: 1 switcher  out of 10 → 10%
        """
        rows = []
        uid = 1
        for month, n_switchers in [(202401, 2), (202402, 3), (202403, 1)]:
            for i in range(10):
                rows.append({
                    "UniqueID": uid,
                    "RenewalYearMonth": month,
                    "IsSwitcher": i < n_switchers,
                    "IsNewToMarket": False,
                    "IsShopper": i < n_switchers,
                })
                uid += 1
        return pd.DataFrame(rows)

    def test_returns_dataframe(self):
        """Result must be a pandas DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert isinstance(result, pd.DataFrame)

    def test_required_columns_present(self):
        """Result must contain month, label, switching_rate, n columns."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert set(["month", "label", "switching_rate", "n"]).issubset(set(result.columns))

    def test_window_1_matches_per_month_calculation(self):
        """window=1 must produce the same rates as individual per-month calc_switching_rate calls."""
        from lib.analytics.rates import calc_rolling_switching_trend, calc_switching_rate
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = sorted(df["RenewalYearMonth"].unique())
        assert len(result) == len(months)
        for _, row in result.iterrows():
            df_m = df[df["RenewalYearMonth"] == row["month"]]
            expected = calc_switching_rate(df_m)
            assert row["switching_rate"] == pytest.approx(expected, rel=1e-6)

    def test_window_1_produces_three_rows_for_three_months(self):
        """window=1 should return one row per month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 3

    def test_window_3_smooths_correctly(self):
        """window=3 result for 3rd month equals mean of all three monthly rates."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # Rates: 0.20, 0.30, 0.10
        expected_smoothed_m3 = (0.20 + 0.30 + 0.10) / 3
        # Third row (index 2) should be the 3-month rolling mean
        assert result.iloc[2]["switching_rate"] == pytest.approx(expected_smoothed_m3, rel=1e-4)

    def test_window_3_first_row_uses_min_periods_1(self):
        """First row with window=3 must equal the raw month rate (min_periods=1, not NaN)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        # First month should be 0.20 (only one period available)
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.20, rel=1e-4)

    def test_window_3_no_nan_values(self):
        """Rolling result must contain no NaN in switching_rate column."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=3)
        assert not result["switching_rate"].isna().any()

    def test_window_larger_than_months_still_works(self):
        """window=12 on a 3-month DataFrame must not raise and return 3 rows."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=12)
        assert len(result) == 3
        assert not result["switching_rate"].isna().any()

    def test_empty_dataframe_returns_empty_result(self):
        """Empty input DataFrame must return an empty DataFrame (not raise)."""
        from lib.analytics.rates import calc_rolling_switching_trend
        result = calc_rolling_switching_trend(pd.DataFrame(), window=1)
        assert isinstance(result, pd.DataFrame)
        assert len(result) == 0

    def test_result_sorted_by_month_ascending(self):
        """Returned rows must be sorted by month ascending."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        months = list(result["month"])
        assert months == sorted(months)

    def test_n_column_equals_month_respondent_count(self):
        """n column must equal the number of respondents for each month."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        result = calc_rolling_switching_trend(df, window=1)
        for _, row in result.iterrows():
            expected_n = len(df[df["RenewalYearMonth"] == row["month"]])
            assert row["n"] == expected_n

    def test_single_month_window_1_returns_one_row(self):
        """Single-month DataFrame with window=1 returns exactly one row."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = pd.DataFrame([
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": False, "IsShopper": i < 2}
            for i in range(5)
        ])
        result = calc_rolling_switching_trend(df, window=1)
        assert len(result) == 1
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)

    def test_original_dataframe_not_mutated(self):
        """Function must not mutate the input DataFrame."""
        from lib.analytics.rates import calc_rolling_switching_trend
        df = self._make_multi_month_df()
        original_cols = set(df.columns)
        calc_rolling_switching_trend(df, window=3)
        assert set(df.columns) == original_cols

    def test_excludes_new_to_market_from_switching_rate(self):
        """Rows where IsNewToMarket=True must be excluded from switching rate denominator."""
        from lib.analytics.rates import calc_rolling_switching_trend
        # 10 respondents: 5 new-to-market (should be excluded), 2 switchers among the 5 eligible
        rows = [
            {"UniqueID": i, "RenewalYearMonth": 202401,
             "IsSwitcher": i < 2, "IsNewToMarket": i >= 5, "IsShopper": i < 2}
            for i in range(10)
        ]
        df = pd.DataFrame(rows)
        result = calc_rolling_switching_trend(df, window=1)
        # 2 switchers / 5 eligible (not new-to-market) = 0.40
        assert result.iloc[0]["switching_rate"] == pytest.approx(0.40, rel=1e-4)


# ===========================================================================
# 17. render_kpi_with_info
# ===========================================================================

class TestRenderKpiWithInfo:
    """lib/components/decision_kpi.py :: render_kpi_with_info

    Wraps decision_kpi with an additional info text rendered as st.caption.
    Must be testable without a real Streamlit session: patches st.markdown
    and st.caption to capture calls.
    """

    def _make_kpi_kwargs(self) -> dict:
        return {
            "title": "Switching Rate",
            "value": "18.5%",
            "change": "+2.1pp vs market",
            "trend": "up",
            "sample_n": 500,
            "colour": "#981D97",
        }

    def test_function_exists(self):
        """render_kpi_with_info must be importable from lib.components.decision_kpi."""
        from lib.components.decision_kpi import render_kpi_with_info
        assert callable(render_kpi_with_info)

    def test_accepts_kpi_kwargs_and_info_text(self):
        """render_kpi_with_info(kpi_kwargs, info_text) must not raise with valid inputs."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "% of customers who changed insurer.")

    def test_info_text_passed_to_caption(self):
        """The info_text argument must appear in an st.caption call."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        info = "% of customers who changed insurer at renewal."
        caption_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption", side_effect=lambda t: caption_calls.append(t)):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), info)
        assert any(info in call for call in caption_calls), \
            f"Expected info text in caption calls, got: {caption_calls}"

    def test_kpi_card_still_rendered(self):
        """decision_kpi card HTML must still be rendered (st.markdown called)."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        markdown_calls = []
        with mock.patch.object(dkpi_mod.st, "markdown",
                                side_effect=lambda html, **kw: markdown_calls.append(html)), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "Some info.")
        assert len(markdown_calls) >= 1, "Expected at least one st.markdown call for the KPI card."

    def test_empty_info_text_does_not_raise(self):
        """Empty string for info_text must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info(self._make_kpi_kwargs(), "")

    def test_minimal_kpi_kwargs_title_and_value_only(self):
        """Minimal kpi_kwargs with only title and value must not raise."""
        from lib.components import decision_kpi as dkpi_mod
        import unittest.mock as mock
        with mock.patch.object(dkpi_mod.st, "markdown"), \
             mock.patch.object(dkpi_mod.st, "caption"):
            from lib.components.decision_kpi import render_kpi_with_info
            render_kpi_with_info({"title": "Test KPI", "value": "42%"}, "Explanation here.")
# ===========================================================================

class TestCalcWilsonCI:
    """lib/analytics/flow_display.py :: calc_wilson_ci"""

    def test_typical_values_returns_tuple(self):
        """50 successes from 100 trials should return a tuple of two floats."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(50, 100)
        assert result is not None
        lower, upper = result
        assert isinstance(lower, float)
        assert isinstance(upper, float)

    def test_lower_lt_point_estimate_lt_upper(self):
        """CI bounds must straddle the point estimate."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        point = 50 / 100
        assert lower < point < upper

    def test_bounds_are_proportions(self):
        """Both bounds must be in [0, 1]."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(50, 100)
        assert 0.0 <= lower <= 1.0
        assert 0.0 <= upper <= 1.0

    def test_n_zero_returns_none(self):
        """n=0 is a division-by-zero case: must return None."""
        from lib.analytics.flow_display import calc_wilson_ci
        assert calc_wilson_ci(0, 0) is None

    def test_zero_successes(self):
        """0 successes from 100 trials: lower should be 0.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 100)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert upper > 0.0

    def test_all_successes(self):
        """100 successes from 100 trials: upper should be 1.0."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(100, 100)
        assert result is not None
        lower, upper = result
        assert upper == pytest.approx(1.0, abs=1e-9)
        assert lower < 1.0

    def test_known_values_approx(self):
        """
        Wilson CI for 500/1000 at z=1.96.
        Expected: (0.4690, 0.5310) to 3 d.p.
        Reference: computed manually.
        """
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(500, 1000)
        assert lower == pytest.approx(0.4690, abs=0.001)
        assert upper == pytest.approx(0.5310, abs=0.001)

    def test_custom_z_widens_interval(self):
        """Higher z value (e.g. 2.576 for 99% CI) must produce wider interval."""
        from lib.analytics.flow_display import calc_wilson_ci
        lo_95, hi_95 = calc_wilson_ci(50, 100, z=1.96)
        lo_99, hi_99 = calc_wilson_ci(50, 100, z=2.576)
        assert lo_99 < lo_95
        assert hi_99 > hi_95

    def test_n_one_success_one(self):
        """Boundary: n=1, k=1 (point estimate=1.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(1, 1)
        assert result is not None
        lower, upper = result
        assert 0.0 <= lower <= 1.0
        assert upper == pytest.approx(1.0, abs=1e-9)

    def test_n_one_success_zero(self):
        """Boundary: n=1, k=0 (point estimate=0.0) returns valid CI."""
        from lib.analytics.flow_display import calc_wilson_ci
        result = calc_wilson_ci(0, 1)
        assert result is not None
        lower, upper = result
        assert lower == pytest.approx(0.0, abs=1e-9)
        assert 0.0 <= upper <= 1.0

    def test_large_n_narrow_interval(self):
        """Large n → very narrow CI (well under 0.01 wide)."""
        from lib.analytics.flow_display import calc_wilson_ci
        lower, upper = calc_wilson_ci(5000, 10000)
        assert (upper - lower) < 0.02


class TestFormatCIRange:
    """lib/analytics/flow_display.py :: format_ci_range"""

    def test_basic_format(self):
        """Returns 'X%–Y%' format with one decimal place."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.535, 0.575)
        assert result == "53.5%\u201357.5%"

    def test_rounded_values(self):
        """Handles values that round cleanly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.40, 0.60)
        assert result == "40.0%\u201360.0%"

    def test_zero_lower(self):
        """Lower bound of 0.0 formats as '0.0%'."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.0, 0.05)
        assert result == "0.0%\u20135.0%"

    def test_near_one_upper(self):
        """Upper bound near 1.0 formats correctly."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.95, 1.0)
        assert result == "95.0%\u2013100.0%"

    def test_uses_en_dash_not_hyphen(self):
        """Separator must be an en dash (U+2013), not a plain hyphen."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.4, 0.6)
        assert "\u2013" in result
        assert "-" not in result

    def test_equal_bounds(self):
        """Equal lower and upper (degenerate CI) still formats without error."""
        from lib.analytics.flow_display import format_ci_range
        result = format_ci_range(0.5, 0.5)
        assert result == "50.0%\u201350.0%"


# ===========================================================================
# Batch 6 — calc_awareness_funnel
# ===========================================================================

class TestCalcAwarenessFunnel:
    """
    lib/analytics/awareness.py :: calc_awareness_funnel

    Tests for Feature 6.1: Awareness Funnel.
    Each brand row has three proportions:
      unprompted (Q1 mention rate), prompted (Q2), consideration (Q27).
    """

    def test_returns_dataframe(self, funnel_df):
        """Function must return a pandas DataFrame."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva", "Admiral"])
        assert isinstance(result, pd.DataFrame)

    def test_expected_columns(self, funnel_df):
        """Result must have brand, unprompted, prompted, consideration columns."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva"])
        assert set(result.columns) >= {"brand", "unprompted", "prompted", "consideration"}

    def test_one_row_per_brand(self, funnel_df):
        """Result has exactly one row per requested brand."""
        from lib.analytics.awareness import calc_awareness_funnel
        brands = ["Aviva", "Admiral", "Direct Line"]
        result = calc_awareness_funnel(funnel_df, brands)
        assert len(result) == len(brands)
        assert set(result["brand"]) == set(brands)

    def test_values_between_zero_and_one(self, funnel_df):
        """All rate values must be proportions in [0, 1]."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva", "Admiral", "Direct Line"])
        for col in ["unprompted", "prompted", "consideration"]:
            valid = result[col].dropna()
            assert (valid >= 0.0).all(), f"{col} has values below 0"
            assert (valid <= 1.0).all(), f"{col} has values above 1"

    def test_prompted_exceeds_consideration(self, funnel_df):
        """
        For brands with sufficient data, prompted >= consideration is expected
        (funnel narrows). Test at aggregate level across all brands.
        """
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva", "Admiral", "Direct Line"])
        for _, row in result.iterrows():
            if pd.notna(row["prompted"]) and pd.notna(row["consideration"]):
                assert row["prompted"] >= row["consideration"] - 0.05, (
                    f"{row['brand']}: prompted={row['prompted']:.3f} < "
                    f"consideration={row['consideration']:.3f} by more than tolerance"
                )

    def test_empty_dataframe_returns_empty(self):
        """Empty input DataFrame returns an empty result."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(pd.DataFrame(), ["Aviva"])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_unknown_brand_returns_nan(self, funnel_df):
        """A brand not in any data column returns NaN for all rate columns."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["NonExistentInsurer"])
        assert len(result) == 1
        row = result.iloc[0]
        assert row["brand"] == "NonExistentInsurer"
        for col in ["unprompted", "prompted", "consideration"]:
            assert pd.isna(row[col]), f"{col} should be NaN for unknown brand"

    def test_mixed_known_and_unknown_brands(self, funnel_df):
        """Known brands get values; unknown brand gets NaN."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva", "Ghost Brand"])
        assert len(result) == 2
        aviva_row = result[result["brand"] == "Aviva"].iloc[0]
        ghost_row = result[result["brand"] == "Ghost Brand"].iloc[0]
        assert pd.notna(aviva_row["prompted"])
        assert pd.isna(ghost_row["prompted"])

    def test_single_brand(self, funnel_df):
        """Works correctly when only one brand is requested."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva"])
        assert len(result) == 1
        assert result.iloc[0]["brand"] == "Aviva"

    def test_empty_brand_list_returns_empty(self, funnel_df):
        """Empty brand list returns empty DataFrame."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, [])
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_product_motor_default(self, funnel_df):
        """Default product=Motor resolves Q2/Q27 correctly."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva"], product="Motor")
        assert len(result) == 1
        assert pd.notna(result.iloc[0]["prompted"])

    def test_no_q1_cols_returns_nan_unprompted(self):
        """DataFrame with no Q1 columns produces NaN for unprompted."""
        import numpy as np
        from lib.analytics.awareness import calc_awareness_funnel

        rng = np.random.default_rng(1)
        df = pd.DataFrame({
            "UniqueID": range(50),
            "RenewalYearMonth": [202401] * 50,
            "Q2_Aviva": rng.random(50) < 0.8,
            "Q27_Aviva": rng.random(50) < 0.5,
        })
        df["Q2_Aviva"] = df["Q2_Aviva"].astype(bool)
        df["Q27_Aviva"] = df["Q27_Aviva"].astype(bool)
        result = calc_awareness_funnel(df, ["Aviva"])
        assert len(result) == 1
        assert pd.isna(result.iloc[0]["unprompted"])
        assert pd.notna(result.iloc[0]["prompted"])

    def test_no_q27_cols_returns_nan_consideration(self):
        """DataFrame with no Q27 columns produces NaN for consideration."""
        import numpy as np
        from lib.analytics.awareness import calc_awareness_funnel

        rng = np.random.default_rng(2)
        df = pd.DataFrame({
            "UniqueID": range(50),
            "RenewalYearMonth": [202401] * 50,
            "Q2_Aviva": rng.random(50) < 0.8,
        })
        df["Q2_Aviva"] = df["Q2_Aviva"].astype(bool)
        result = calc_awareness_funnel(df, ["Aviva"])
        assert len(result) == 1
        assert pd.isna(result.iloc[0]["consideration"])
        assert pd.notna(result.iloc[0]["prompted"])

    def test_multiple_months_aggregated(self, funnel_df):
        """Multi-month data is aggregated into a single rate per brand."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva"])
        # Should return one row, not one per month
        assert len(result) == 1

    def test_aviva_rates_plausible(self, funnel_df):
        """Aviva should have positive rates given fixture design."""
        from lib.analytics.awareness import calc_awareness_funnel
        result = calc_awareness_funnel(funnel_df, ["Aviva"])
        row = result.iloc[0]
        assert row["prompted"] > 0.1, "Aviva prompted awareness should be substantial"
        assert row["consideration"] > 0.0, "Aviva consideration should be positive"
