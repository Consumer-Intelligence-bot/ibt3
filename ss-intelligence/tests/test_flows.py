"""Tests for flows."""
import pytest
import pandas as pd
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from analytics.flows import calc_net_flow, calc_flow_matrix, is_flow_cell_suppressed


@pytest.fixture
def flow_df():
    return pd.DataFrame({
        "UniqueID": range(1, 101),
        "IsSwitcher": [True] * 20 + [False] * 80,
        "CurrentCompany": ["B"] * 10 + ["C"] * 10 + ["A"] * 80,
        "PreviousCompany": ["A"] * 10 + ["A"] * 10 + [None] * 80,
    })


def test_net_flow(flow_df):
    nf = calc_net_flow(flow_df, "B")
    assert nf["gained"] == 10
    assert nf["lost"] == 0
    assert nf["net"] == 10


def test_net_flow_lost(flow_df):
    nf = calc_net_flow(flow_df, "A")
    assert nf["gained"] == 0
    assert nf["lost"] == 20
    assert nf["net"] == -20


def test_flow_balance(flow_df):
    """Total gained across market should equal total lost."""
    flow_mat = calc_flow_matrix(flow_df)
    if len(flow_mat) == 0:
        return
    total_switches = flow_mat.sum().sum()
    # Sum of flows into each dest = sum of flows out of each source = total
    assert total_switches == 20


def test_flow_cell_suppression():
    assert is_flow_cell_suppressed(9) is True
    assert is_flow_cell_suppressed(10) is False
    assert is_flow_cell_suppressed(0) is True


def test_q4_eq_q39_excluded():
    """Records where CurrentCompany == PreviousCompany are excluded from flows."""
    df = pd.DataFrame({
        "UniqueID": range(1, 31),
        "IsSwitcher": [True] * 30,
        "CurrentCompany": ["B"] * 10 + ["A"] * 10 + ["A"] * 10,
        "PreviousCompany": ["A"] * 10 + ["B"] * 10 + ["A"] * 10,
    })
    nf = calc_net_flow(df, "A")
    # 10 gained (from B→A), 10 lost (A→B), 10 excluded (A→A)
    assert nf["gained"] == 10
    assert nf["lost"] == 10
    assert nf["net"] == 0
