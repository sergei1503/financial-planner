"""
Unit tests for escalating standalone cash flows (expenditures that grow over time).

Exercises `_project_standalone_cash_flows` directly with synthetic CashFlow rows, no DB:
`CashFlowRepository` is patched so `get_by_user` returns hand-built objects. Verifies the
three growth modes ('none' flat, 'smooth' monthly-compounded, 'stepped' anniversary steps)
and the active-window gating, plus the growth-factor helper in isolation.

Run: python -m pytest fplan_v2/tests/test_cash_flow_growth.py -q
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

from fplan_v2.api.routes.projections import (
    _cash_flow_growth_factor,
    _project_standalone_cash_flows,
)


def _months(start: date, n: int):
    """n monthly month-start timestamps beginning at `start`."""
    return list(pd.date_range(start=pd.Timestamp(start), periods=n, freq="MS"))


def _cf(**kw):
    """A minimal stand-in for an ORM CashFlow row (standalone: target_asset_id=None)."""
    defaults = dict(
        target_asset_id=None,
        flow_type="withdrawal",
        name="Rent (paid)",
        amount=8000.0,
        from_date=date(2026, 1, 1),
        to_date=date(2036, 1, 1),
        from_own_capital=False,
        growth_mode="none",
        growth_rate=0,
    )
    defaults.update(kw)
    return SimpleNamespace(**defaults)


def _project(cfs, all_dates):
    """Run _project_standalone_cash_flows with CashFlowRepository patched to return `cfs`."""
    with patch("fplan_v2.api.routes.projections.CashFlowRepository") as repo_cls:
        repo_cls.return_value.get_by_user.return_value = cfs
        return _project_standalone_cash_flows(MagicMock(), user_id=1, all_dates=all_dates)


def _values(item):
    return [float(p.value) for p in item.time_series]


class TestGrowthFactorHelper:
    def test_none_is_flat(self):
        start = pd.Timestamp("2026-01-01")
        for ts in _months(date(2026, 1, 1), 24):
            assert _cash_flow_growth_factor("none", 5.0, start, ts) == 1.0

    def test_zero_rate_is_flat_even_when_mode_set(self):
        start = pd.Timestamp("2026-01-01")
        assert _cash_flow_growth_factor("smooth", 0, start, pd.Timestamp("2030-01-01")) == 1.0

    def test_smooth_compounds_monthly(self):
        start = pd.Timestamp("2026-01-01")
        # one full year -> exactly one annual step
        assert _cash_flow_growth_factor("smooth", 3.0, start, pd.Timestamp("2027-01-01")) == pytest.approx(1.03)
        # half a year -> square root of the annual factor
        assert _cash_flow_growth_factor("smooth", 3.0, start, pd.Timestamp("2026-07-01")) == pytest.approx(1.03 ** 0.5)

    def test_stepped_floors_to_whole_years(self):
        start = pd.Timestamp("2026-01-01")
        # anywhere inside year 0 -> factor 1.0
        assert _cash_flow_growth_factor("stepped", 4.0, start, pd.Timestamp("2026-11-01")) == pytest.approx(1.0)
        # first anniversary -> one step
        assert _cash_flow_growth_factor("stepped", 4.0, start, pd.Timestamp("2027-01-01")) == pytest.approx(1.04)
        # mid year 1 -> still one step (flat within the year)
        assert _cash_flow_growth_factor("stepped", 4.0, start, pd.Timestamp("2027-06-01")) == pytest.approx(1.04)


class TestStandaloneCashFlowProjection:
    def test_flat_by_default(self):
        dates = _months(date(2026, 1, 1), 25)
        items = _project([_cf(amount=8000.0)], dates)
        assert len(items) == 1
        item = items[0]
        assert item.source_type == "expense"
        assert item.category == "withdrawal"
        assert all(v == 8000.0 for v in _values(item))

    def test_smooth_growth_reaches_annual_factor_at_month_12(self):
        dates = _months(date(2026, 1, 1), 25)
        items = _project([_cf(amount=8000.0, growth_mode="smooth", growth_rate=3.0)], dates)
        vals = _values(items[0])
        assert vals[0] == pytest.approx(8000.0)
        assert vals[12] == pytest.approx(8000.0 * 1.03)          # exactly one year on
        assert vals[6] == pytest.approx(8000.0 * (1.03 ** 0.5))  # smooth mid-year

    def test_stepped_growth_is_flat_within_year_then_steps(self):
        dates = _months(date(2026, 1, 1), 25)
        items = _project([_cf(amount=8000.0, growth_mode="stepped", growth_rate=4.0)], dates)
        vals = _values(items[0])
        assert len(set(round(v, 6) for v in vals[:12])) == 1     # flat within year 0
        assert vals[0] == pytest.approx(8000.0)
        assert vals[12] == pytest.approx(8000.0 * 1.04)          # steps on the anniversary
        assert vals[12] == pytest.approx(vals[23])               # flat within year 1

    def test_growth_only_inside_active_window(self):
        dates = _months(date(2026, 1, 1), 25)
        cf = _cf(amount=5000.0, growth_mode="smooth", growth_rate=10.0,
                 from_date=date(2026, 6, 1), to_date=date(2026, 12, 1))
        vals = _values(_project([cf], dates)[0])
        assert vals[0] == 0.0            # Jan 2026: before window
        assert vals[5] == pytest.approx(5000.0)  # Jun 2026: window start, factor 1.0
        assert vals[6] > vals[5]         # Jul 2026: grown
        assert vals[12] == 0.0           # Jan 2027: after window
