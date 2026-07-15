"""
Regression tests for LoanPrimePegged.get_projection() (fplan_v2/core/models/loan.py).

Covers two bugs found via the golden test (fplan_v2/tests/test_projection_golden.py):

1. IndexError on short-duration prime loans: the IndexTracker's prime rate-change
   history always includes synthetic mean-reversion rows ~1/2/3 years past the last
   real CSV rate change. Any such segment starting on/after the loan's own end date
   produced a non-positive `duration_till_end_of_loan`, an empty per-period DataFrame,
   and a later `.iloc[]` lookup on that empty frame raised IndexError.
2. Non-chronological output: per-segment frames were concatenated latest-segment-first,
   so the returned DataFrame's rows were not in date order.

DB-free: builds an IndexTracker via the same helper production code uses
(`_create_index_tracker`), no database or network required.

Run: python -m pytest fplan_v2/tests/test_loan_prime_pegged.py -q
"""

from datetime import date

import pytest

from fplan_v2.core.models.loan import LoanPrimePegged
from fplan_v2.core.constants import VALUE
from fplan_v2.api.routes.projections import _create_index_tracker


def _assert_chronological(df):
    dates = df["date"].tolist()
    assert dates == sorted(dates), "date column must be in chronological order"
    assert len(set(dates)) == len(dates), "date column must be strictly increasing (no duplicates)"


def test_short_duration_prime_loan_does_not_raise():
    """
    Bug-1 repro: a 24-month prime-pegged loan's projection window is shorter than the
    IndexTracker's synthetic mean-reversion tail (~1/2/3 years past the last real CSV
    rate change), so at least one rate-change segment starts on/after this loan's end
    date. Before the fix, this raised IndexError; get_projection() must now succeed.
    """
    index_tracker = _create_index_tracker()

    loan = LoanPrimePegged(
        loan_id="loan_prime_short",
        value=300000.0,
        base_interest_rate_annual_pct=5.0,
        duration_months=24,
        start_date=date(2026, 1, 1),
        index_tracker=index_tracker,
    )

    df = loan.get_projection()  # must not raise IndexError (this was the bug-1 repro)

    _assert_chronological(df)

    balances = df[VALUE].abs().tolist()
    assert len(balances) >= 2
    assert all(
        balances[i] > balances[i + 1] for i in range(len(balances) - 1)
    ), f"balance must amortize monotonically toward 0: {balances}"


def test_longer_prime_loan_is_chronological_and_amortizes():
    """A longer (120-month) prime loan also projects fine and stays in date order."""
    index_tracker = _create_index_tracker()

    loan = LoanPrimePegged(
        loan_id="loan_prime_long",
        value=300000.0,
        base_interest_rate_annual_pct=5.0,
        duration_months=120,
        start_date=date(2026, 1, 1),
        index_tracker=index_tracker,
    )

    df = loan.get_projection()

    _assert_chronological(df)

    balances = df[VALUE].abs().tolist()
    assert len(balances) >= 2
    assert all(
        balances[i] > balances[i + 1] for i in range(len(balances) - 1)
    ), f"balance must amortize monotonically toward 0: {balances}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
