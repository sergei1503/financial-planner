"""
Projection API endpoints.

Provides financial projection and portfolio analysis endpoints.
"""

import hashlib
import json
from datetime import date, datetime, timedelta
from decimal import Decimal
from typing import Dict, Any, List
from dateutil.relativedelta import relativedelta
import pandas as pd

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import (
    ProjectionRequest,
    ProjectionResponse,
    PortfolioSummary,
    TimeSeriesDataPoint,
    AssetProjection,
    LoanProjection,
    MeasurementMarker,
    CashFlowItem,
    CashFlowBreakdown,
)
from fplan_v2.api.auth import get_current_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.db.repositories import AssetRepository, LoanRepository, RevenueStreamRepository, CashFlowRepository, HistoricalMeasurementRepository
from fplan_v2.db import models

# Import business logic classes
from fplan_v2.core.models.asset import (
    Asset,
    CashAsset,
    RealEstateAsset,
    StockAsset,
    PensionAsset,
)
from fplan_v2.core.models.loan import (
    LoanFixed,
    LoanVariable,
    LoanPrimePegged,
    LoanCPIPegged,
)
from fplan_v2.core.models.revenue_stream import (
    RentRevenueStream,
    SalaryRevenueStream,
    DividendRevenueStream,
    PensionRevenueStream,
)
from fplan_v2.core.engine.index_tracker import IndexTracker
from fplan_v2.core.constants import VALUE, CASH_FLOW, EIndexType


router = APIRouter()


def _create_index_tracker() -> IndexTracker:
    """Create an IndexTracker initialized with historical rate data."""
    import os
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    tracker = IndexTracker(start_date=pd.Timestamp("2022-04-01"), duration=12 * 30)

    # Load prime rates
    prime_path = os.path.join(base_dir, "data", "prime_interest_rates.csv")
    try:
        df_prime = pd.read_csv(prime_path)
    except FileNotFoundError:
        df_prime = pd.DataFrame({"start": ["06/01/2022"], "end": ["01/01/2030"], "rate": [2.5]})

    # Load CPI rates
    cpi_path = os.path.join(base_dir, "data", "cpi_interest_rates.csv")
    try:
        df_cpi = pd.read_csv(cpi_path)
    except FileNotFoundError:
        df_cpi = pd.DataFrame({"date": ["01/22"], "cpi": [103.0], "change": [0.0], "change_percent": [0.0]})

    tracker.add_index_file(EIndexType.PRIME, df_prime)
    tracker.add_index_file(EIndexType.CPI, df_cpi)
    tracker.prepare_index_histories()
    return tracker


# Helper functions for ORM to business object conversion

def _load_cash_flows_for_asset(db: Session, user_id: int, asset_id: int) -> tuple:
    """Load deposits and withdrawals from cash_flows table for an asset."""
    repo = CashFlowRepository(db)
    cash_flows = repo.get_by_asset(user_id, asset_id)

    deposits = []
    withdrawals = []
    for cf in cash_flows:
        entry = {
            "amount": float(cf.amount),
            "from": cf.from_date.strftime("%d/%m/%Y"),
            "to": cf.to_date.strftime("%d/%m/%Y"),
            "deposit_from_own_capital": cf.from_own_capital,
        }
        if cf.flow_type == "deposit":
            deposits.append(entry)
        else:
            withdrawals.append(entry)

    return deposits, withdrawals


def _convert_orm_revenue_stream_to_business(db_stream: models.RevenueStream):
    """
    Convert ORM RevenueStream to business logic revenue stream object.

    Each stream type has a different constructor signature.
    """
    stream_type = db_stream.stream_type
    config = db_stream.config_json or {}

    if stream_type == "rent":
        return RentRevenueStream(
            id=db_stream.name,
            start_date=db_stream.start_date,
            amount=float(db_stream.amount),
            period=db_stream.period or "monthly",
            tax=float(db_stream.tax_rate or 0),
            growth_rate=float(db_stream.growth_rate or 0),
            end_date=db_stream.end_date,
        )
    elif stream_type == "salary":
        return SalaryRevenueStream(
            id=db_stream.name,
            start_date=db_stream.start_date,
            end_date=db_stream.end_date or "01/01/2070",
            amount=float(db_stream.amount),
            growth_rate=float(db_stream.growth_rate or 0),
        )
    elif stream_type == "dividend":
        return DividendRevenueStream(
            dividend_yield=float(config.get("dividend_yield", 0)),
            dividend_payout_frequency=config.get("payout_frequency", 4),
            tax=float(db_stream.tax_rate or 0),
            start_dividend_withdraw_date=db_stream.start_date if db_stream.start_date else "01/01/2200",
        )
    elif stream_type == "pension":
        return PensionRevenueStream(
            id=db_stream.name,
            start_date=db_stream.start_date,
            monthly_payout=float(db_stream.amount),
        )
    else:
        return None


def _convert_orm_asset_to_business(db_asset: models.Asset, db: Session = None) -> Asset:
    """
    Convert SQLAlchemy ORM Asset model to business logic Asset object.

    Args:
        db_asset: Database asset model
        db: Optional database session for loading cash flows

    Returns:
        Business logic asset instance
    """
    # Parse config_json for additional fields
    config = db_asset.config_json or {}

    # Base parameters shared by most asset types
    base_id = db_asset.external_id
    start_date = db_asset.start_date
    original_value = float(db_asset.original_value)
    appreciation = float(db_asset.appreciation_rate_annual_pct or 0)
    yearly_fee = float(db_asset.yearly_fee_pct or 0)

    # Load deposits/withdrawals from cash_flows table if session available, else fallback to config_json
    if db:
        deposits, withdrawals = _load_cash_flows_for_asset(db, db_asset.user_id, db_asset.id)
    else:
        deposits = config.get("deposits", [])
        withdrawals = config.get("withdrawals", [])

    # Create appropriate subclass based on asset_type
    # Each subclass has a different __init__ signature
    if db_asset.asset_type == "cash":
        asset = CashAsset(id=base_id, start_date=start_date, original_value=original_value)
    elif db_asset.asset_type == "real_estate":
        asset = RealEstateAsset(
            id=base_id, start_date=start_date, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None,
        )
    elif db_asset.asset_type == "stock":
        asset = StockAsset(
            id=base_id, start_date=start_date, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=deposits, withdrawals=withdrawals,
        )
    elif db_asset.asset_type == "pension":
        end_date = config.get("end_date", "2070-01-01")
        conversion_date = config.get("conversion_date", None)
        conversion_coefficient = config.get("conversion_coefficient", 200)
        asset = PensionAsset(
            id=base_id, start_date=start_date, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=deposits, end_date=end_date,
            conversion_date=conversion_date, conversion_coefficient=conversion_coefficient,
        )
    else:
        # Fallback to base Asset class
        asset = Asset(
            id=base_id, start_date=start_date, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=deposits, withdrawals=withdrawals,
        )

    # Attach revenue stream from database if available
    if db:
        revenue_repo = RevenueStreamRepository(db)
        db_streams = revenue_repo.get_by_asset(db_asset.id)
        if db_streams:
            # Attach first matching revenue stream based on asset type
            for db_stream in db_streams:
                biz_stream = _convert_orm_revenue_stream_to_business(db_stream)
                if biz_stream is not None:
                    asset.revenue_stream = biz_stream
                    break

    # Set additional attributes
    if db_asset.current_value:
        asset.value = float(db_asset.current_value)

    if db_asset.sell_date:
        asset.set_extraction_date(db_asset.sell_date)

    asset.sell_tax = float(db_asset.sell_tax or 0)

    return asset


def _convert_orm_loan_to_business(db_loan: models.Loan, index_tracker: IndexTracker = None) -> Any:
    """
    Convert SQLAlchemy ORM Loan model to business logic Loan object.

    Args:
        db_loan: Database loan model
        index_tracker: Index tracker for variable-rate loans

    Returns:
        Business logic loan instance
    """
    config = db_loan.config_json or {}

    loan_id = db_loan.external_id
    value = float(db_loan.original_value)
    rate = float(db_loan.interest_rate_annual_pct)
    duration = db_loan.duration_months
    start = db_loan.start_date
    collateral = str(db_loan.collateral_asset_id) if db_loan.collateral_asset_id else None

    # Create appropriate loan type — each has different __init__ signature
    if db_loan.loan_type == "fixed":
        loan = LoanFixed(
            id=loan_id, value=value, interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start,
            collateral_asset=collateral, history=config.get("history", []),
        )
    elif db_loan.loan_type == "variable":
        loan = LoanVariable(
            id=loan_id, value=value, base_rate_annual_pct=rate,
            margin_pct=config.get("margin_pct", 0),
            duration_months=duration, start_date=start,
            inflation_rate_annual_pct=config.get("inflation_rate", 0),
            collateral_asset=collateral,
        )
    elif db_loan.loan_type == "prime_pegged":
        if not index_tracker:
            index_tracker = IndexTracker()
        loan = LoanPrimePegged(
            loan_id=loan_id, value=value, base_interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start,
            index_tracker=index_tracker,
        )
    elif db_loan.loan_type == "cpi_pegged":
        if not index_tracker:
            index_tracker = IndexTracker()
        loan = LoanCPIPegged(
            loan_id=loan_id, value=value, base_interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start,
            index_tracker=index_tracker,
            expected_cpi_increase_percent_yearly=config.get("expected_cpi_increase", 3),
        )
    else:
        loan = LoanFixed(
            id=loan_id, value=value, interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start,
            collateral_asset=collateral,
        )

    # Set current balance if available
    if db_loan.current_balance:
        loan.value = -float(db_loan.current_balance)

    return loan


def _apply_cash_conversions(
    assets: list,
    db_assets: list,
    all_asset_dfs: List[pd.DataFrame],
    start_date: date,
) -> None:
    """
    Apply sell→cash and purchase→cash conversions to the CashAsset projection.

    Modifies the cash asset DataFrame in all_asset_dfs in-place:
    1. For each non-cash asset with a sell_date: add proceeds (value * (1 - sell_tax/100)) to cash
    2. For each non-cash asset starting within projection: subtract original_value from cash
    3. Sum per-asset CASH_FLOW columns into the cash asset's running balance
    """
    # Find the cash asset index
    cash_idx = None
    for i, db_asset in enumerate(db_assets):
        if db_asset.asset_type == "cash":
            cash_idx = i
            break

    if cash_idx is None or all_asset_dfs[cash_idx].empty:
        return

    cash_df = all_asset_dfs[cash_idx]
    sentinel = pd.Timestamp(year=2100, month=1, day=1)
    start_ts = pd.Timestamp(start_date.replace(day=1))

    # Build adjustment series
    adjustments: Dict[pd.Timestamp, float] = {}

    for i, (asset, db_asset) in enumerate(zip(assets, db_assets)):
        if db_asset.asset_type == "cash":
            continue

        asset_df = all_asset_dfs[i]
        if asset_df.empty:
            continue

        # Purchase adjustment: if asset starts within projection period
        asset_start = pd.Timestamp(db_asset.start_date).replace(day=1)
        if asset_start >= start_ts:
            adj_date = asset_start
            adjustments[adj_date] = adjustments.get(adj_date, 0) - float(db_asset.original_value)

        # Sale adjustment: if sell_date is set and before sentinel
        if db_asset.sell_date:
            sell_ts = pd.Timestamp(db_asset.sell_date).replace(day=1)
            if sell_ts < sentinel and sell_ts >= start_ts:
                # Find asset value at sell date
                sell_rows = asset_df[asset_df["date"] == sell_ts]
                if not sell_rows.empty:
                    sale_value = float(sell_rows[VALUE].iloc[0])
                else:
                    # Use last known value before sell date
                    before_sell = asset_df[asset_df["date"] <= sell_ts]
                    sale_value = float(before_sell[VALUE].iloc[-1]) if not before_sell.empty else 0

                sell_tax = float(db_asset.sell_tax or 0) / 100
                proceeds = sale_value * (1 - sell_tax)
                adjustments[sell_ts] = adjustments.get(sell_ts, 0) + proceeds

        # Deposit cash flow impact: sum per-asset cash flows into adjustments
        if CASH_FLOW in asset_df.columns:
            for _, row in asset_df.iterrows():
                cf_val = float(row[CASH_FLOW])
                if cf_val != 0:
                    dt = row["date"]
                    adjustments[dt] = adjustments.get(dt, 0) + cf_val

    # Apply adjustments to cash asset projection
    if adjustments:
        # Recalculate cash as running balance from initial value + all monthly adjustments
        cash_df = cash_df.sort_values("date").reset_index(drop=True)
        initial_value = float(cash_df[VALUE].iloc[0])
        running = initial_value

        for idx, row in cash_df.iterrows():
            dt = row["date"]
            adj = adjustments.get(dt, 0)
            if idx == 0:
                running = initial_value + adj
            else:
                running += adj
            cash_df.at[idx, VALUE] = running

        all_asset_dfs[cash_idx] = cash_df


def _project_standalone_revenue_streams(
    db: Session, user_id: int, all_dates: list,
) -> List[CashFlowItem]:
    """
    Project standalone revenue streams (not attached to any asset, e.g. salary).

    Returns a list of CashFlowItem objects for the breakdown.
    """
    revenue_repo = RevenueStreamRepository(db)
    standalone_streams = revenue_repo.get_standalone(user_id)
    items: List[CashFlowItem] = []

    for db_stream in standalone_streams:
        biz_stream = _convert_orm_revenue_stream_to_business(db_stream)
        if biz_stream is None:
            continue

        # Salary and Rent streams support get_cash_flow()
        # PensionRevenueStream.get_cash_flow() raises RuntimeError — skip standalone pension
        # DividendRevenueStream has no get_cash_flow — skip standalone dividend
        if isinstance(biz_stream, (SalaryRevenueStream, RentRevenueStream)):
            try:
                cf_df = biz_stream.get_cash_flow()
            except Exception:
                continue

            if cf_df.empty:
                continue

            # Build time series aligned to projection dates
            series = []
            for dt in all_dates:
                ts = pd.Timestamp(dt)
                matching = cf_df[cf_df["date"] == ts]
                if not matching.empty:
                    val = float(matching[CASH_FLOW].iloc[0])
                else:
                    val = 0.0
                series.append(TimeSeriesDataPoint(
                    date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                    value=Decimal(str(val)),
                ))

            items.append(CashFlowItem(
                source_name=db_stream.name,
                source_type="income",
                category=db_stream.stream_type,
                time_series=series,
                entity_id=None,  # Standalone streams not linked to assets
                entity_type=None,
            ))

    return items


def _project_standalone_cash_flows(
    db: Session, user_id: int, all_dates: list,
) -> List[CashFlowItem]:
    """
    Project standalone cash flows (not attached to any asset).

    These are general income/expense items like rent payments, utilities,
    side income, etc. that the user added without linking to an asset.

    Returns a list of CashFlowItem objects for the breakdown.
    """
    repo = CashFlowRepository(db)
    all_cfs = repo.get_by_user(user_id)
    standalone_cfs = [cf for cf in all_cfs if cf.target_asset_id is None]

    items: List[CashFlowItem] = []
    for cf in standalone_cfs:
        cf_start = pd.Timestamp(cf.from_date).replace(day=1)
        cf_end = pd.Timestamp(cf.to_date).replace(day=1)
        amount = float(cf.amount)

        series = []
        for dt in all_dates:
            ts = dt if isinstance(dt, pd.Timestamp) else pd.Timestamp(dt)
            val = amount if cf_start <= ts <= cf_end else 0.0
            series.append(TimeSeriesDataPoint(
                date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                value=Decimal(str(val)),
            ))

        if cf.flow_type == "deposit":
            if cf.from_own_capital:
                source_type = "expense"
                category = "deposit"
            else:
                source_type = "income"
                category = "external_deposit"
        else:
            source_type = "expense"
            category = "withdrawal"

        items.append(CashFlowItem(
            source_name=cf.name,
            source_type=source_type,
            category=category,
            time_series=series,
            entity_id=None,
            entity_type=None,
        ))

    return items


def _build_cash_flow_breakdown(
    all_dates: list,
    loan_items: List[CashFlowItem],
    asset_cf_items: List[CashFlowItem],
    revenue_items: List[CashFlowItem],
) -> CashFlowBreakdown:
    """Build a CashFlowBreakdown from individual items."""
    all_items = loan_items + asset_cf_items + revenue_items

    # Aggregate totals per date
    income_by_date: Dict[Any, float] = {}
    expense_by_date: Dict[Any, float] = {}

    for item in all_items:
        for point in item.time_series:
            val = float(point.value)
            if item.source_type == "income":
                income_by_date[point.date] = income_by_date.get(point.date, 0) + val
            else:
                expense_by_date[point.date] = expense_by_date.get(point.date, 0) + val

    total_income_series = []
    total_expense_series = []
    net_series = []

    for dt in all_dates:
        d = dt.date() if isinstance(dt, pd.Timestamp) else dt
        income = income_by_date.get(d, 0)
        expense = expense_by_date.get(d, 0)
        total_income_series.append(TimeSeriesDataPoint(date=d, value=Decimal(str(income))))
        total_expense_series.append(TimeSeriesDataPoint(date=d, value=Decimal(str(expense))))
        net_series.append(TimeSeriesDataPoint(date=d, value=Decimal(str(income - expense))))

    return CashFlowBreakdown(
        items=all_items,
        total_income_series=total_income_series,
        total_expense_series=total_expense_series,
        net_series=net_series,
    )


def _apply_measurement_shifts(
    asset_dfs: List[pd.DataFrame],
    db_assets: list,
    loan_dfs: List[pd.DataFrame],
    db_loans: list,
    measurements: list,
) -> tuple:
    """
    Apply historical measurement shifts to projection DataFrames.

    At each measurement date, replace the projected value with the actual measured value
    and shift all subsequent projected values by the delta. This creates a realistic
    projection that incorporates real-world data.

    Also returns MeasurementMarker lists for each asset and loan.

    Returns:
        Tuple of (asset_measurement_markers_by_index, loan_measurement_markers_by_index)
    """
    # Index measurements by (entity_type, entity_id)
    measurement_map: Dict[tuple, list] = {}
    for m in measurements:
        key = (m.entity_type, m.entity_id)
        measurement_map.setdefault(key, []).append(m)

    # Sort each group by date
    for key in measurement_map:
        measurement_map[key].sort(key=lambda x: x.measurement_date)

    asset_markers: Dict[int, List[MeasurementMarker]] = {}
    loan_markers: Dict[int, List[MeasurementMarker]] = {}

    # Apply shifts to asset projections
    for i, db_asset in enumerate(db_assets):
        key = ("asset", db_asset.id)
        entity_measurements = measurement_map.get(key, [])
        if not entity_measurements or asset_dfs[i].empty:
            continue

        markers = []
        df = asset_dfs[i].sort_values("date").reset_index(drop=True)

        for m in entity_measurements:
            m_date = pd.Timestamp(m.measurement_date).replace(day=1)
            actual_value = float(m.actual_value)

            markers.append(MeasurementMarker(
                date=m.measurement_date,
                actual_value=Decimal(str(actual_value)),
                entity_type="asset",
                entity_id=db_asset.id,
                entity_name=db_asset.name,
            ))

            # Find the row at or nearest after the measurement date
            matching_rows = df[df["date"] == m_date]
            if matching_rows.empty:
                # Find nearest date after measurement
                after_rows = df[df["date"] > m_date]
                if after_rows.empty:
                    continue
                match_idx = after_rows.index[0]
            else:
                match_idx = matching_rows.index[0]

            projected_value = float(df.at[match_idx, VALUE])
            delta = actual_value - projected_value

            # Shift this point and all subsequent points by the delta
            df.loc[match_idx:, VALUE] = df.loc[match_idx:, VALUE].astype(float) + delta

        asset_dfs[i] = df
        asset_markers[i] = markers

    # Apply shifts to loan projections
    for i, db_loan in enumerate(db_loans):
        key = ("loan", db_loan.id)
        entity_measurements = measurement_map.get(key, [])
        if not entity_measurements or loan_dfs[i].empty:
            continue

        markers = []
        df = loan_dfs[i].sort_values("date").reset_index(drop=True)

        for m in entity_measurements:
            m_date = pd.Timestamp(m.measurement_date).replace(day=1)
            actual_value = float(m.actual_value)

            markers.append(MeasurementMarker(
                date=m.measurement_date,
                actual_value=Decimal(str(actual_value)),
                entity_type="loan",
                entity_id=db_loan.id,
                entity_name=db_loan.name,
            ))

            matching_rows = df[df["date"] == m_date]
            if matching_rows.empty:
                after_rows = df[df["date"] > m_date]
                if after_rows.empty:
                    continue
                match_idx = after_rows.index[0]
            else:
                match_idx = matching_rows.index[0]

            # Loan values are negative in projections
            projected_value = abs(float(df.at[match_idx, VALUE]))
            delta = actual_value - projected_value

            # Shift balance (VALUE column) for this and subsequent points
            # Loans use negative values, so shift the absolute values
            for idx in range(match_idx, len(df)):
                current = float(df.at[idx, VALUE])
                # Shift in the direction of the sign
                if current <= 0:
                    df.at[idx, VALUE] = current - delta
                else:
                    df.at[idx, VALUE] = current + delta

        loan_dfs[i] = df
        loan_markers[i] = markers

    return asset_markers, loan_markers


def _build_cache_key(user: User, request: ProjectionRequest) -> str:
    """Build a SHA-256 cache key from portfolio version and request params."""
    key_data = f"{user.portfolio_version}:{request.start_date}:{request.end_date}:{request.as_of_date}"
    return hashlib.sha256(key_data.encode()).hexdigest()


def _get_cached_projection(db: Session, user_id: int, cache_key: str):
    """Look up cached projection result."""
    from fplan_v2.db.models import ProjectionCache
    return db.query(ProjectionCache).filter_by(
        user_id=user_id, cache_key=cache_key
    ).first()


def _store_cached_projection(db: Session, user_id: int, cache_key: str, response: ProjectionResponse):
    """Store a projection result in the cache."""
    from fplan_v2.db.models import ProjectionCache
    # Upsert: delete old entry if exists, insert new
    db.query(ProjectionCache).filter_by(user_id=user_id, cache_key=cache_key).delete()
    cache_entry = ProjectionCache(
        user_id=user_id,
        cache_key=cache_key,
        result_json=json.loads(response.model_dump_json()),
        computed_at=response.computed_at,
    )
    db.add(cache_entry)
    db.flush()


@router.post("/run", response_model=ProjectionResponse)
def run_projection(
    request: ProjectionRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Run financial projections for a user's portfolio.

    Loads all assets and loans for the user, converts them to business logic objects,
    runs projections, and aggregates the results into time series.

    Args:
        request: Projection parameters
        db: Database session

    Returns:
        Projection results with time series data

    Raises:
        HTTPException: 404 if user has no portfolio data
        HTTPException: 500 if projection calculation fails
    """
    # Set default dates if not provided
    # If as_of_date is provided, use it as start_date (historical projection mode)
    is_historical = request.as_of_date is not None
    historical_as_of_date = request.as_of_date

    if is_historical:
        start_date = request.as_of_date
    else:
        start_date = request.start_date or date.today()

    end_date = request.end_date or (start_date + timedelta(days=30 * 365))  # 30 years default

    # Calculate months to project
    months_to_project = ((end_date.year - start_date.year) * 12 +
                        (end_date.month - start_date.month))

    if months_to_project <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    # Check projection cache
    cache_key = _build_cache_key(current_user, request)
    cached = _get_cached_projection(db, current_user.id, cache_key)
    if cached:
        return ProjectionResponse(**cached.result_json)

    # Initialize repositories
    asset_repo = AssetRepository(db)
    loan_repo = LoanRepository(db)
    measurement_repo = HistoricalMeasurementRepository(db)

    # Load user's portfolio from database
    db_assets = asset_repo.get_all(user_id=current_user.id, limit=1000)
    db_loans = loan_repo.get_all(user_id=current_user.id, limit=1000)

    # Load historical measurements - filter by as_of_date if in historical mode
    if is_historical:
        all_measurements = [
            m for m in measurement_repo.get_all(user_id=current_user.id)
            if m.measurement_date <= historical_as_of_date
        ]
    else:
        all_measurements = measurement_repo.get_all(user_id=current_user.id)

    if not db_assets and not db_loans:
        return ProjectionResponse(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            net_worth_series=[],
            total_assets_series=[],
            total_liabilities_series=[],
            monthly_cash_flow_series=[],
            asset_projections=[],
            loan_projections=[],
            is_historical=is_historical,
            historical_as_of_date=historical_as_of_date,
            computed_at=datetime.now(),
        )

    # Create index tracker for variable-rate loans (with historical data)
    index_tracker = _create_index_tracker()

    # Convert ORM models to business objects
    assets = [_convert_orm_asset_to_business(db_asset, db) for db_asset in db_assets]
    loans = [_convert_orm_loan_to_business(db_loan, index_tracker) for db_loan in db_loans]

    # Note: all_measurements already loaded above with proper filtering for historical mode

    try:
        # Run projections for each asset
        asset_projections_list: List[AssetProjection] = []
        all_asset_dfs: List[pd.DataFrame] = []

        for asset in assets:
            df = asset.get_projection(months_to_project=months_to_project)
            all_asset_dfs.append(df)

        # Apply sell→cash conversions and deposit cash flow impact
        _apply_cash_conversions(assets, db_assets, all_asset_dfs, start_date)

        # Run projections for each loan
        loan_projections_list: List[LoanProjection] = []
        all_loan_dfs: List[pd.DataFrame] = []

        for loan in loans:
            df = loan.get_projection()
            all_loan_dfs.append(df)

        # Apply historical measurement shifts to projections
        asset_markers_map, loan_markers_map = _apply_measurement_shifts(
            all_asset_dfs, db_assets, all_loan_dfs, db_loans, all_measurements,
        )

        # Rebuild asset time series after cash conversion and measurement adjustments
        asset_projections_list = []
        for i, asset_df in enumerate(all_asset_dfs):
            time_series = [
                TimeSeriesDataPoint(
                    date=row["date"].date(),
                    value=Decimal(str(row[VALUE]))
                )
                for _, row in asset_df.iterrows()
            ]
            asset_projections_list.append(AssetProjection(
                asset_id=db_assets[i].id,
                asset_name=db_assets[i].name,
                asset_type=db_assets[i].asset_type,
                time_series=time_series,
                measurements=asset_markers_map.get(i, []),
            ))

        # Build loan projection response objects
        for i, loan_df in enumerate(all_loan_dfs):
            balance_series = [
                TimeSeriesDataPoint(
                    date=row["date"].date(),
                    value=Decimal(str(abs(row[VALUE])))
                )
                for _, row in loan_df.iterrows()
            ]

            payment_series = [
                TimeSeriesDataPoint(
                    date=row["date"].date(),
                    value=Decimal(str(abs(row[CASH_FLOW])))
                )
                for _, row in loan_df.iterrows()
            ]

            loan_projections_list.append(LoanProjection(
                loan_id=db_loans[i].id,
                loan_name=db_loans[i].name,
                loan_type=db_loans[i].loan_type,
                balance_series=balance_series,
                payment_series=payment_series,
                measurements=loan_markers_map.get(i, []),
            ))

        # Build all measurement markers for the response
        all_markers: List[MeasurementMarker] = []
        for markers in asset_markers_map.values():
            all_markers.extend(markers)
        for markers in loan_markers_map.values():
            all_markers.extend(markers)

        # Aggregate time series data
        # Combine all asset projections
        if all_asset_dfs:
            combined_assets = pd.concat(all_asset_dfs, ignore_index=True)
            total_assets_by_date = combined_assets.groupby("date")[VALUE].sum().reset_index()
        else:
            # Create empty DataFrame with proper structure
            total_assets_by_date = pd.DataFrame(columns=["date", VALUE])

        # Combine all loan projections
        if all_loan_dfs:
            combined_loans = pd.concat(all_loan_dfs, ignore_index=True)
            total_liabilities_by_date = combined_loans.groupby("date")[VALUE].sum().reset_index()
            loan_payments_by_date = combined_loans.groupby("date")[CASH_FLOW].sum().reset_index()
        else:
            total_liabilities_by_date = pd.DataFrame(columns=["date", VALUE])
            loan_payments_by_date = pd.DataFrame(columns=["date", CASH_FLOW])

        # Aggregate asset cash flows (deposits/withdrawals impacting monthly flow)
        asset_cf_dfs = [df[["date", CASH_FLOW]] for df in all_asset_dfs if CASH_FLOW in df.columns and not df.empty]
        if asset_cf_dfs:
            combined_asset_cf = pd.concat(asset_cf_dfs, ignore_index=True)
            asset_cf_by_date = combined_asset_cf.groupby("date")[CASH_FLOW].sum().reset_index()
        else:
            asset_cf_by_date = pd.DataFrame(columns=["date", CASH_FLOW])

        # Merge loan payments + asset cash flows into total monthly cash flow
        if not loan_payments_by_date.empty and not asset_cf_by_date.empty:
            total_payments_by_date = loan_payments_by_date.merge(
                asset_cf_by_date, on="date", how="outer", suffixes=("_loan", "_asset")
            )
            total_payments_by_date = total_payments_by_date.fillna(0)
            total_payments_by_date[CASH_FLOW] = (
                total_payments_by_date.get(f"{CASH_FLOW}_loan", 0) +
                total_payments_by_date.get(f"{CASH_FLOW}_asset", 0)
            )
        elif not loan_payments_by_date.empty:
            total_payments_by_date = loan_payments_by_date
        elif not asset_cf_by_date.empty:
            total_payments_by_date = asset_cf_by_date
        else:
            total_payments_by_date = pd.DataFrame(columns=["date", CASH_FLOW])

        # Create unified date range
        all_dates = set()
        if not total_assets_by_date.empty:
            all_dates.update(total_assets_by_date["date"].tolist())
        if not total_liabilities_by_date.empty:
            all_dates.update(total_liabilities_by_date["date"].tolist())

        if not all_dates:
            # Generate date range if no projections available
            all_dates = [start_date + relativedelta(months=i) for i in range(months_to_project)]

        all_dates = sorted(list(all_dates))

        # Build response time series
        net_worth_series: List[TimeSeriesDataPoint] = []
        total_assets_series: List[TimeSeriesDataPoint] = []
        total_liabilities_series: List[TimeSeriesDataPoint] = []
        cash_flow_series: List[TimeSeriesDataPoint] = []

        for dt in all_dates:
            # Get asset value for this date
            if not total_assets_by_date.empty:
                asset_row = total_assets_by_date[total_assets_by_date["date"] == dt]
                asset_value = float(asset_row[VALUE].iloc[0]) if not asset_row.empty else 0.0
            else:
                asset_value = 0.0

            # Get liability value for this date
            if not total_liabilities_by_date.empty:
                liability_row = total_liabilities_by_date[total_liabilities_by_date["date"] == dt]
                liability_value = abs(float(liability_row[VALUE].iloc[0])) if not liability_row.empty else 0.0
            else:
                liability_value = 0.0

            # Get cash flow for this date
            if not total_payments_by_date.empty:
                payment_row = total_payments_by_date[total_payments_by_date["date"] == dt]
                payment_value = abs(float(payment_row[CASH_FLOW].iloc[0])) if not payment_row.empty else 0.0
            else:
                payment_value = 0.0

            # Calculate net worth
            net_worth = asset_value - liability_value

            # Add to series
            net_worth_series.append(TimeSeriesDataPoint(
                date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                value=Decimal(str(net_worth))
            ))

            total_assets_series.append(TimeSeriesDataPoint(
                date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                value=Decimal(str(asset_value))
            ))

            total_liabilities_series.append(TimeSeriesDataPoint(
                date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                value=Decimal(str(liability_value))
            ))

            cash_flow_series.append(TimeSeriesDataPoint(
                date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                value=Decimal(str(-payment_value))  # Negative because it's an outflow
            ))

        # Build cash flow breakdown with per-source attribution
        breakdown_loan_items: List[CashFlowItem] = []
        breakdown_asset_cf_items: List[CashFlowItem] = []
        breakdown_revenue_items: List[CashFlowItem] = []

        # Loan payment items (expenses)
        for i, loan_df in enumerate(all_loan_dfs):
            if loan_df.empty:
                continue
            series = []
            for dt in all_dates:
                matching = loan_df[loan_df["date"] == dt]
                val = abs(float(matching[CASH_FLOW].iloc[0])) if not matching.empty else 0.0
                series.append(TimeSeriesDataPoint(
                    date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                    value=Decimal(str(val)),
                ))
            breakdown_loan_items.append(CashFlowItem(
                source_name=db_loans[i].name,
                source_type="expense",
                category="loan_payment",
                time_series=series,
                entity_id=db_loans[i].id,
                entity_type="loan",
            ))

        # Asset deposit/withdrawal items - split by from_own_capital
        cash_flow_repo = CashFlowRepository(db)
        for i, asset_df in enumerate(all_asset_dfs):
            if asset_df.empty or CASH_FLOW not in asset_df.columns:
                continue
            has_nonzero = asset_df[CASH_FLOW].abs().sum() > 0
            if not has_nonzero:
                continue

            # Get cash flow records for this asset to check from_own_capital flag
            asset_cash_flows = cash_flow_repo.get_by_asset(
                user_id=current_user.id,
                asset_id=db_assets[i].id
            )

            # Group cash flows by from_own_capital flag
            cash_flows_by_flag = {}
            for cf in asset_cash_flows:
                flag = cf.from_own_capital
                if flag not in cash_flows_by_flag:
                    cash_flows_by_flag[flag] = []
                cash_flows_by_flag[flag].append(cf)

            # Create breakdown items only for own capital deposits (employer deposits don't affect cash flow)
            for from_own_capital, cfs in cash_flows_by_flag.items():
                if not from_own_capital:
                    continue  # Skip employer deposits - they don't pass through your bank account
                # Build time series for this classification
                series = []
                for dt in all_dates:
                    # Sum up all cash flows for this date that match this flag
                    val = 0.0
                    for cf in cfs:
                        # Check if this date falls within the cash flow period
                        cf_start = pd.Timestamp(cf.from_date).replace(day=1)
                        cf_end = pd.Timestamp(cf.to_date).replace(day=1)
                        if cf_start <= dt <= cf_end:
                            # Get value from asset_df for this date
                            matching = asset_df[asset_df["date"] == dt]
                            if not matching.empty:
                                val += float(matching[CASH_FLOW].iloc[0])

                    series.append(TimeSeriesDataPoint(
                        date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                        value=Decimal(str(abs(val))),
                    ))

                # Classify by from_own_capital flag
                if from_own_capital:
                    # from_own_capital=True → category="deposit", source_type="expense"
                    category = "deposit"
                    source_type = "expense"
                    source_name = f"{db_assets[i].name} - Own Capital"
                else:
                    # from_own_capital=False → category="external_deposit", source_type="income"
                    category = "external_deposit"
                    source_type = "income"
                    source_name = f"{db_assets[i].name} - External Deposit"

                breakdown_asset_cf_items.append(CashFlowItem(
                    source_name=source_name,
                    source_type=source_type,
                    category=category,
                    time_series=series,
                    entity_id=db_assets[i].id,
                    entity_type="asset",
                ))

        # Revenue stream items (income) — from assets with attached streams
        for i, asset in enumerate(assets):
            if not hasattr(asset, 'revenue_stream') or asset.revenue_stream is None:
                continue
            stream = asset.revenue_stream
            # Salary and Rent streams support get_cash_flow()
            if isinstance(stream, (SalaryRevenueStream, RentRevenueStream)):
                try:
                    cf_df = stream.get_cash_flow()
                except Exception:
                    continue
                if cf_df.empty:
                    continue
                series = []
                for dt in all_dates:
                    ts = pd.Timestamp(dt)
                    matching = cf_df[cf_df["date"] == ts]
                    val = float(matching[CASH_FLOW].iloc[0]) if not matching.empty else 0.0
                    series.append(TimeSeriesDataPoint(
                        date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                        value=Decimal(str(val)),
                    ))
                category = "rent" if isinstance(stream, RentRevenueStream) else "salary"
                breakdown_revenue_items.append(CashFlowItem(
                    source_name=f"{db_assets[i].name} - {category.title()}",
                    source_type="income",
                    category=category,
                    time_series=series,
                    entity_id=db_assets[i].id,
                    entity_type="asset",
                ))

        # Pension income items — extract from PensionAsset CASH_FLOW
        for i, asset in enumerate(assets):
            if not isinstance(asset, PensionAsset):
                continue
            asset_df = all_asset_dfs[i]
            if asset_df.empty or CASH_FLOW not in asset_df.columns:
                continue
            series = []
            for dt in all_dates:
                ts = pd.Timestamp(dt)
                matching = asset_df[asset_df["date"] == ts]
                val = float(matching[CASH_FLOW].iloc[0]) if not matching.empty else 0.0
                series.append(TimeSeriesDataPoint(
                    date=dt.date() if isinstance(dt, pd.Timestamp) else dt,
                    value=Decimal(str(val)),
                ))
            breakdown_revenue_items.append(CashFlowItem(
                source_name=f"{db_assets[i].name} - Pension",
                source_type="income",
                category="pension",
                time_series=series,
                entity_id=db_assets[i].id,
                entity_type="asset",
            ))

        # Standalone revenue streams (salary, rent not attached to assets)
        standalone_items = _project_standalone_revenue_streams(db, current_user.id, all_dates)
        breakdown_revenue_items.extend(standalone_items)

        # Standalone cash flows (expenditures/incomes not attached to any asset)
        standalone_cf_items = _project_standalone_cash_flows(db, current_user.id, all_dates)
        breakdown_asset_cf_items.extend(standalone_cf_items)

        cash_flow_breakdown = _build_cash_flow_breakdown(
            all_dates, breakdown_loan_items, breakdown_asset_cf_items, breakdown_revenue_items,
        )

        # Update net cash flow series to include revenue income
        if cash_flow_breakdown.net_series:
            cash_flow_series = cash_flow_breakdown.net_series

        # Build accumulated cash asset from cumulative net cash flow
        # This represents the running sum of surplus (or deficit) cash over time
        if cash_flow_breakdown.net_series:
            accumulated_cash_series: List[TimeSeriesDataPoint] = []
            cumulative = 0.0
            for point in cash_flow_breakdown.net_series:
                cumulative += float(point.value)
                # Allow negative values to show when strategy leads to bank overdraft
                accumulated_cash_series.append(TimeSeriesDataPoint(
                    date=point.date,
                    value=Decimal(str(round(cumulative, 2))),
                ))

            # Add as a virtual asset projection (use id=0 for virtual)
            asset_projections_list.append(AssetProjection(
                asset_id=0,
                asset_name="מזומנים מצטברים",
                asset_type="cash",
                time_series=accumulated_cash_series,
            ))

            # Update total_assets_series and net_worth_series to include accumulated cash
            for i, point in enumerate(accumulated_cash_series):
                if i < len(total_assets_series):
                    old_asset_val = float(total_assets_series[i].value)
                    new_asset_val = old_asset_val + float(point.value)
                    total_assets_series[i] = TimeSeriesDataPoint(
                        date=total_assets_series[i].date,
                        value=Decimal(str(round(new_asset_val, 2))),
                    )
                if i < len(net_worth_series):
                    old_nw_val = float(net_worth_series[i].value)
                    new_nw_val = old_nw_val + float(point.value)
                    net_worth_series[i] = TimeSeriesDataPoint(
                        date=net_worth_series[i].date,
                        value=Decimal(str(round(new_nw_val, 2))),
                    )

        # Build response and cache it
        response = ProjectionResponse(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            net_worth_series=net_worth_series,
            total_assets_series=total_assets_series,
            total_liabilities_series=total_liabilities_series,
            monthly_cash_flow_series=cash_flow_series,
            cash_flow_breakdown=cash_flow_breakdown,
            asset_projections=asset_projections_list,
            loan_projections=loan_projections_list,
            measurement_markers=all_markers,
            is_historical=is_historical,
            historical_as_of_date=historical_as_of_date,
            computed_at=datetime.now(),
        )

        # Store in cache
        _store_cached_projection(db, current_user.id, cache_key, response)

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Projection calculation failed: {str(e)}",
        )


@router.get("/portfolio/summary", response_model=PortfolioSummary)
def get_portfolio_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Get current portfolio summary statistics.

    Calculates current state of user's portfolio including:
    - Total assets
    - Total liabilities
    - Net worth
    - Monthly cash flows
    """
    user_id = current_user.id
    asset_repo = AssetRepository(db)
    loan_repo = LoanRepository(db)
    revenue_repo = RevenueStreamRepository(db)

    # Get current totals
    total_assets = asset_repo.calculate_total_value(user_id)
    total_liabilities = loan_repo.calculate_total_balance(user_id)
    net_worth = total_assets - total_liabilities

    # Get monthly cash flows
    monthly_revenue = revenue_repo.calculate_monthly_revenue(user_id)
    monthly_loan_payments = loan_repo.calculate_monthly_payments(user_id)
    monthly_net_cash_flow = monthly_revenue - monthly_loan_payments

    # Get counts
    asset_count = asset_repo.count(user_id)
    loan_count = loan_repo.count(user_id)
    revenue_stream_count = revenue_repo.count(user_id)

    return PortfolioSummary(
        user_id=user_id,
        total_assets=Decimal(str(total_assets)),
        total_liabilities=Decimal(str(total_liabilities)),
        net_worth=Decimal(str(net_worth)),
        monthly_revenue=Decimal(str(monthly_revenue)),
        monthly_loan_payments=Decimal(str(monthly_loan_payments)),
        monthly_net_cash_flow=Decimal(str(monthly_net_cash_flow)),
        asset_count=asset_count,
        loan_count=loan_count,
        revenue_stream_count=revenue_stream_count,
        as_of_date=date.today(),
    )


@router.get("/health")
def projection_health_check() -> Dict[str, Any]:
    """Health check for projection service."""
    return {
        "status": "ready",
        "service": "projections",
        "backend_integration": "complete",
        "features": {
            "asset_projections": True,
            "loan_projections": True,
            "portfolio_summary": True,
            "time_series_aggregation": True,
        },
        "note": "Projection engine fully operational",
    }
