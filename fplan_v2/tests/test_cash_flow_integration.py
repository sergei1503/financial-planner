"""
Invariant tests for ADR-0004: operating cash flow integrated into net worth exactly ONCE.

Net worth integrates cash flow through two mechanisms — the real cash asset
(`_apply_cash_conversions`, which already holds asset-attached flows) and the virtual
"accumulated cash" asset (`cumsum` of the non-asset breakdown items). These tests lock in
that each flow is counted once: the accumulated-cash asset must EXCLUDE `entity_type=="asset"`
items (rent/dividends/pension/own-capital deposits), which are already in the real cash asset.

Fully offline: synthetic core objects + ORM stand-ins, repositories patched. The classification
was verified empirically before these were written (see ADR-0004's flow table).
"""

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from fplan_v2.core.models.asset import CashAsset, RealEstateAsset, StockAsset
from fplan_v2.core.models.revenue_stream import RentRevenueStream
from fplan_v2.core.models.loan import LoanFixed
from fplan_v2.api.routes.projections import compute_projection

# Assets start before the projection window so _apply_cash_conversions doesn't treat them as
# purchases (which would subtract original_value from cash and muddy the invariant).
ASSET_START = date(2020, 1, 1)
PROJ_START = date(2026, 1, 1)


class _DbAsset:
    def __init__(self, id, name, asset_type, start_date, original_value, sell_date=None, sell_tax=0):
        self.id, self.name, self.asset_type = id, name, asset_type
        self.start_date, self.original_value = start_date, original_value
        self.sell_date, self.sell_tax = sell_date, sell_tax


class _DbLoan:
    def __init__(self, id, name, loan_type):
        self.id, self.name, self.loan_type = id, name, loan_type


def _run(assets, db_assets, loans=(), db_loans=(), months=6, revenue_rows=(),
         cashflow_user_rows=(), cashflow_by_asset=None):
    with patch("fplan_v2.api.routes.projections.CashFlowRepository") as cf_cls, \
         patch("fplan_v2.api.routes.projections.RevenueStreamRepository") as rs_cls:
        by_asset = cashflow_by_asset or {}
        cf_cls.return_value.get_by_asset.side_effect = \
            lambda user_id, asset_id, portfolio_id=None: by_asset.get(asset_id, [])
        cf_cls.return_value.get_by_user.return_value = list(cashflow_user_rows)
        rs_cls.return_value.get_standalone.return_value = list(revenue_rows)
        rs_cls.return_value.get_by_asset.return_value = []
        end = date(PROJ_START.year + (PROJ_START.month - 1 + months) // 12,
                   (PROJ_START.month - 1 + months) % 12 + 1, 1)
        return compute_projection(
            assets=list(assets), loans=list(loans), db_assets=list(db_assets),
            db_loans=list(db_loans), measurements=[], start_date=PROJ_START, end_date=end,
            months_to_project=months, db=MagicMock(), user_id=1, portfolio_id=1,
        )


def _nw(resp):
    return [float(p.value) for p in resp.net_worth_series]


def _accumulated(resp):
    ap = next((a for a in resp.asset_projections if a.asset_name == "מזומנים מצטברים"), None)
    return [float(p.value) for p in ap.time_series] if ap else None


def _cash_only():
    return [CashAsset(id="cash", start_date=ASSET_START, original_value=100000.0)], \
           [_DbAsset(1, "Cash", "cash", ASSET_START, 100000.0)]


def _salary_row(amount):
    return SimpleNamespace(stream_type="salary", config_json={}, name="Salary",
                           start_date=ASSET_START, end_date=None, amount=amount,
                           growth_rate=0, period="monthly")


def _cashflow_row(amount, flow_type="withdrawal", target_asset_id=None, from_own_capital=False):
    return SimpleNamespace(target_asset_id=target_asset_id, flow_type=flow_type, name="cf",
                           amount=amount, from_date=ASSET_START, to_date=date(2060, 1, 1),
                           from_own_capital=from_own_capital, growth_mode="none", growth_rate=0)


class TestNoDoubleCount:
    def test_attached_rent_counts_once(self):
        """THE regression guard: rent 5000 attached to a property raises net worth +5000/mo,
        not +10000/mo. Rent is already in the real cash asset, so accumulated cash excludes it."""
        cash, db_cash = _cash_only()[0][0], _cash_only()[1][0]
        rent = RentRevenueStream(id="r", start_date=ASSET_START, amount=5000.0,
                                 period="monthly", tax=0.0, growth_rate=0.0)
        re = RealEstateAsset(id="re", start_date=ASSET_START, original_value=800000.0,
                             appreciation_rate_annual_pct=0.0, yearly_fee_pct=0.0, revenue_stream=rent)
        resp = _run([cash, re], [db_cash, _DbAsset(2, "House", "real_estate", ASSET_START, 800000.0)])
        nw = _nw(resp)
        deltas = [round(nw[k] - nw[k - 1], 2) for k in range(1, len(nw))]
        assert all(d == pytest.approx(5000.0) for d in deltas), deltas   # once, not 10000
        assert all(v == pytest.approx(0.0) for v in _accumulated(resp))  # rent not re-integrated

    def test_own_capital_asset_deposit_is_networth_neutral(self):
        """Own-capital deposit moves cash -> asset (already in real cash); it must NOT also
        drain accumulated cash, so net worth stays flat (0% appreciation)."""
        cash, db_cash = _cash_only()[0][0], _cash_only()[1][0]
        stock = StockAsset(id="s", start_date=ASSET_START, original_value=50000.0,
                           appreciation_rate_annual_pct=0.0, yearly_fee_pct=0.0, revenue_stream=None,
                           deposits=[{"amount": 1000.0, "from": "01/01/2020", "to": "01/01/2060",
                                      "deposit_from_own_capital": True}], withdrawals=[])
        dep = _cashflow_row(1000.0, flow_type="deposit", target_asset_id=2, from_own_capital=True)
        resp = _run([cash, stock], [db_cash, _DbAsset(2, "Stock", "stock", ASSET_START, 50000.0)],
                    cashflow_by_asset={2: [dep]})
        nw = _nw(resp)
        assert all(v == pytest.approx(nw[0], abs=1.0) for v in nw), nw        # flat
        assert all(v == pytest.approx(0.0) for v in _accumulated(resp))       # not double-drained


class TestSingleCountedFlowsUnchanged:
    def test_standalone_salary_accumulates(self):
        assets, db_assets = _cash_only()
        nw = _nw(_run(assets, db_assets, revenue_rows=[_salary_row(10000.0)]))
        deltas = [round(nw[k] - nw[k - 1], 2) for k in range(1, len(nw))]
        assert all(d == pytest.approx(10000.0) for d in deltas), deltas

    def test_standalone_expense_drains(self):
        assets, db_assets = _cash_only()
        nw = _nw(_run(assets, db_assets, cashflow_user_rows=[_cashflow_row(3000.0)]))
        deltas = [round(nw[k] - nw[k - 1], 2) for k in range(1, len(nw))]
        assert all(d == pytest.approx(-3000.0) for d in deltas), deltas

    def test_loan_payments_drain_net_worth(self):
        assets, db_assets = _cash_only()
        loan = LoanFixed(id="l", value=50000.0, interest_rate_annual_pct=6.0,
                         duration_months=24, start_date=PROJ_START)
        resp = _run(assets, db_assets, [loan], [_DbLoan(101, "Loan", "fixed")], months=12)
        nw = _nw(resp)
        assert nw[-1] < nw[0]                                    # loan costs money
        acc = _accumulated(resp)
        assert acc[-1] < acc[0] <= 0                             # accumulated goes negative (payments)


class TestAccumulatedExcludesAssetItems:
    def test_accumulated_equals_cumsum_of_non_asset_items_only(self):
        """Mixed portfolio: accumulated-cash == cumsum of ONLY the entity_type != 'asset'
        breakdown items (loan + standalone), never the asset-attached ones."""
        cash, db_cash = _cash_only()[0][0], _cash_only()[1][0]
        rent = RentRevenueStream(id="r", start_date=ASSET_START, amount=4000.0,
                                 period="monthly", tax=0.0, growth_rate=0.0)
        re = RealEstateAsset(id="re", start_date=ASSET_START, original_value=800000.0,
                             appreciation_rate_annual_pct=0.0, yearly_fee_pct=0.0, revenue_stream=rent)
        resp = _run([cash, re], [db_cash, _DbAsset(2, "House", "real_estate", ASSET_START, 800000.0)],
                    revenue_rows=[_salary_row(9000.0)], cashflow_user_rows=[_cashflow_row(2000.0)])
        # Expected per-month integrated net = salary(+9000) - expense(2000) = +7000; rent excluded.
        acc = _accumulated(resp)
        expected = [round(7000.0 * (k + 1), 2) for k in range(len(acc))]
        assert [round(v, 2) for v in acc] == expected, (acc[:4], expected[:4])
