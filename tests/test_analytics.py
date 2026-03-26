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
