"""
Golden-master regression test for compute_projection().

Builds a small, fully synthetic, DB-free portfolio directly from the core business
models (fplan_v2.core.models) and locks in compute_projection()'s output against a
committed fixture (fixtures/projection_golden.json). Any unintended change in the
projection engine's math will fail this test — guarding future refactors.

Fully offline: no database, no network, no wall-clock dependency (the DB session is a
MagicMock and the repository lookups compute_projection makes are patched to return
empty lists; the only wall-clock field, `computed_at`, is popped before comparison).

Run: python -m pytest fplan_v2/tests/test_projection_golden.py -q
"""

import json
import math
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from fplan_v2.core.models.asset import (
    CashAsset,
    RealEstateAsset,
    StockAsset,
    PensionAsset,
)
from fplan_v2.core.models.loan import (
    LoanFixed,
    LoanInterestOnly,
    LoanPrimePegged,
    LoanCPIPegged,
)
from fplan_v2.core.models.revenue_stream import RentRevenueStream
from fplan_v2.api.routes.projections import compute_projection, _create_index_tracker


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "projection_golden.json"

# Fixed, small window — deterministic and fast (25 monthly points).
START_DATE = date(2026, 1, 1)
END_DATE = date(2028, 1, 1)
MONTHS_TO_PROJECT = (END_DATE.year - START_DATE.year) * 12 + (END_DATE.month - START_DATE.month)


class _DbAsset:
    """
    Lightweight stand-in for an ORM Asset row, exposing exactly the attributes
    compute_projection() reads: id, name, asset_type, start_date, original_value,
    sell_date, sell_tax.
    """

    def __init__(self, id, name, asset_type, start_date, original_value, sell_date=None, sell_tax=0):
        self.id = id
        self.name = name
        self.asset_type = asset_type
        self.start_date = start_date
        self.original_value = original_value
        self.sell_date = sell_date
        self.sell_tax = sell_tax


class _DbLoan:
    """
    Lightweight stand-in for an ORM Loan row, exposing exactly the attributes
    compute_projection() reads: id, name, loan_type.
    """

    def __init__(self, id, name, loan_type):
        self.id = id
        self.name = name
        self.loan_type = loan_type


def _build_portfolio():
    """Build a small synthetic portfolio: business objects + matching DB stand-ins."""
    index_tracker = _create_index_tracker()

    # --- Assets ---------------------------------------------------------------
    cash = CashAsset(id="cash", start_date=START_DATE, original_value=20000.0)
    db_cash = _DbAsset(id=1, name="Cash", asset_type="cash", start_date=START_DATE, original_value=20000.0)

    stock = StockAsset(
        id="stock1", start_date=START_DATE, original_value=100000.0,
        appreciation_rate_annual_pct=6.0, yearly_fee_pct=0.5, revenue_stream=None,
        deposits=[{
            "amount": 500.0, "from": "01/01/2026", "to": "01/01/2028",
            "deposit_from_own_capital": True,
        }],
        withdrawals=[],
    )
    db_stock = _DbAsset(id=2, name="Stock", asset_type="stock", start_date=START_DATE, original_value=100000.0)

    re_smooth = RealEstateAsset(
        id="re_smooth", start_date=START_DATE, original_value=800000.0,
        appreciation_rate_annual_pct=3.0, yearly_fee_pct=0.0,
        revenue_stream=RentRevenueStream(
            id="rent_smooth", start_date=START_DATE, amount=4000.0, period="monthly",
            tax=10.0, growth_rate=3.0, step_growth=False,
        ),
    )
    db_re_smooth = _DbAsset(
        id=3, name="RE Smooth", asset_type="real_estate", start_date=START_DATE, original_value=800000.0,
    )

    re_stepped = RealEstateAsset(
        id="re_stepped", start_date=START_DATE, original_value=600000.0,
        appreciation_rate_annual_pct=2.5, yearly_fee_pct=0.0,
        revenue_stream=RentRevenueStream(
            id="rent_stepped", start_date=START_DATE, amount=3500.0, period="monthly",
            tax=10.0, growth_rate=4.0, step_growth=True,
        ),
    )
    db_re_stepped = _DbAsset(
        id=4, name="RE Stepped", asset_type="real_estate", start_date=START_DATE, original_value=600000.0,
    )

    pension = PensionAsset(
        id="pension1", start_date=START_DATE, original_value=150000.0,
        appreciation_rate_annual_pct=4.0, yearly_fee_pct=0.3, revenue_stream=None,
        deposits=[{
            "amount": 1000.0, "from": "01/01/2026", "to": "01/01/2070",
            "deposit_from_own_capital": True,
        }],
        end_date=date(2070, 1, 1),
        conversion_date=date(2027, 1, 1),
        conversion_coefficient=180.0,
    )
    db_pension = _DbAsset(
        id=5, name="Pension", asset_type="pension", start_date=START_DATE, original_value=150000.0,
    )

    assets = [cash, stock, re_smooth, re_stepped, pension]
    db_assets = [db_cash, db_stock, db_re_smooth, db_re_stepped, db_pension]

    # --- Loans ------------------------------------------------------------------
    loan_fixed = LoanFixed(
        id="loan_fixed", value=200000.0, interest_rate_annual_pct=4.0,
        duration_months=24, start_date=START_DATE,
    )
    db_loan_fixed = _DbLoan(id=101, name="Fixed Loan", loan_type="fixed")

    # Non-amortizing (interest-only) loan: balance ACCRUES/grows, no repayments.
    loan_io = LoanInterestOnly(
        id="loan_io", value=50000.0, interest_rate_annual_pct=10.0,
        duration_months=24, start_date=START_DATE,
    )
    # Production convention: the DB row's loan_type stays "fixed" — the non-amortizing
    # behavior comes from the business-object class, not this label (see
    # _convert_orm_loan_to_business, which checks config_json["non_amortizing"] first).
    db_loan_io = _DbLoan(id=102, name="Interest Only Loan", loan_type="fixed")

    # LoanPrimePegged needs a duration long enough to extend past the IndexTracker's
    # synthetic mean-reversion rows (added ~1/2/3 years after the last real CSV rate
    # change) — otherwise a segment whose start lands after this loan's own end date
    # gets a negative "duration_till_end_of_loan" and produces an empty per-period
    # DataFrame, which crashes get_projection(). 48 months safely clears that tail.
    loan_prime = LoanPrimePegged(
        loan_id="loan_prime", value=300000.0, base_interest_rate_annual_pct=2.0,
        duration_months=48, start_date=START_DATE, index_tracker=index_tracker,
    )
    db_loan_prime = _DbLoan(id=103, name="Prime Loan", loan_type="prime_pegged")

    loan_cpi = LoanCPIPegged(
        loan_id="loan_cpi", value=250000.0, base_interest_rate_annual_pct=3.0,
        duration_months=24, start_date=START_DATE, index_tracker=index_tracker,
        expected_cpi_increase_percent_yearly=3.0,
    )
    db_loan_cpi = _DbLoan(id=104, name="CPI Loan", loan_type="cpi_pegged")

    loans = [loan_fixed, loan_io, loan_prime, loan_cpi]
    db_loans = [db_loan_fixed, db_loan_io, db_loan_prime, db_loan_cpi]

    return assets, db_assets, loans, db_loans


def _run_projection() -> dict:
    """Run compute_projection() fully offline: MagicMock db + repo lookups patched to []."""
    assets, db_assets, loans, db_loans = _build_portfolio()
    mock_db = MagicMock()

    # compute_projection() constructs CashFlowRepository(db) and RevenueStreamRepository(db)
    # internally (for standalone revenue streams / cash flows, and asset cash-flow lookups).
    # Patch both classes so every lookup they perform returns an empty list — no DB required.
    with patch("fplan_v2.api.routes.projections.CashFlowRepository") as mock_cf_repo_cls, \
         patch("fplan_v2.api.routes.projections.RevenueStreamRepository") as mock_rs_repo_cls:
        mock_cf_repo_cls.return_value.get_by_asset.return_value = []
        mock_cf_repo_cls.return_value.get_by_user.return_value = []
        mock_rs_repo_cls.return_value.get_standalone.return_value = []
        mock_rs_repo_cls.return_value.get_by_asset.return_value = []

        response = compute_projection(
            assets=assets,
            loans=loans,
            db_assets=db_assets,
            db_loans=db_loans,
            measurements=[],
            start_date=START_DATE,
            end_date=END_DATE,
            months_to_project=MONTHS_TO_PROJECT,
            db=mock_db,
            user_id=1,
            portfolio_id=1,
        )

    result = json.loads(response.model_dump_json())
    result.pop("computed_at", None)
    return result


def _assert_close(actual, expected, path="root", tol=1e-6):
    """Recursively compare dict/list/scalar JSON structures with float tolerance."""
    if isinstance(expected, dict):
        assert isinstance(actual, dict), f"{path}: expected dict, got {type(actual)}"
        assert set(actual.keys()) == set(expected.keys()), (
            f"{path}: key mismatch: {sorted(actual.keys())} != {sorted(expected.keys())}"
        )
        for key in expected:
            _assert_close(actual[key], expected[key], f"{path}.{key}", tol)
    elif isinstance(expected, list):
        assert isinstance(actual, list), f"{path}: expected list, got {type(actual)}"
        assert len(actual) == len(expected), f"{path}: length mismatch: {len(actual)} != {len(expected)}"
        for i, (a_item, e_item) in enumerate(zip(actual, expected)):
            _assert_close(a_item, e_item, f"{path}[{i}]", tol)
    elif isinstance(expected, (int, float)) and not isinstance(expected, bool):
        assert isinstance(actual, (int, float)) and not isinstance(actual, bool), (
            f"{path}: expected numeric, got {type(actual)}"
        )
        assert math.isclose(float(actual), float(expected), abs_tol=tol, rel_tol=tol), (
            f"{path}: {actual} != {expected} (tol={tol})"
        )
    else:
        assert actual == expected, f"{path}: {actual!r} != {expected!r}"


class TestProjectionGolden:
    """Locks in compute_projection()'s output against a committed golden fixture."""

    def test_projection_matches_golden_fixture(self):
        result = _run_projection()

        # --- Sanity checks (independent of the fixture; would catch a broken engine
        # even if the fixture were stale or accidentally regenerated) --------------
        assert result["net_worth_series"], "net_worth_series must not be empty"

        loan_io = next(
            lp for lp in result["loan_projections"] if lp["loan_name"] == "Interest Only Loan"
        )
        io_balances = [float(p["value"]) for p in loan_io["balance_series"]]
        assert len(io_balances) >= 2
        assert io_balances[-1] > io_balances[0], (
            f"LoanInterestOnly balance must grow: first={io_balances[0]} last={io_balances[-1]}"
        )

        rent_item = next(
            item for item in result["cash_flow_breakdown"]["items"]
            if item["source_name"] == "RE Stepped - Rent"
        )
        rent_values = [float(p["value"]) for p in rent_item["time_series"]]
        first_year = rent_values[:12]
        assert len(set(round(v, 6) for v in first_year)) == 1, (
            f"stepped rent should be flat within its first year: {first_year}"
        )
        if len(rent_values) > 12:
            assert rent_values[12] > first_year[0], (
                "stepped rent should step up after a full year"
            )

        # --- Golden fixture comparison ---------------------------------------------
        if not FIXTURE_PATH.exists():
            FIXTURE_PATH.parent.mkdir(parents=True, exist_ok=True)
            FIXTURE_PATH.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
            expected = result  # first run seeds the fixture; compare trivially and pass
        else:
            expected = json.loads(FIXTURE_PATH.read_text())

        _assert_close(result, expected)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
