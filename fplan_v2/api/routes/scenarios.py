"""
Scenario API endpoints.

Provides CRUD operations for what-if scenarios and scenario projection execution.
"""

import json
import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from fplan_v2.api.schemas import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioAction,
    ProjectionRequest,
    ProjectionResponse,
)
from fplan_v2.api.auth import get_current_user, get_current_portfolio
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import Portfolio, User
from fplan_v2.db.repositories import (
    AssetRepository,
    LoanRepository,
    HistoricalMeasurementRepository,
    ScenarioRepository,
    RevenueStreamRepository,
)
from fplan_v2.core.engine.scenario_engine import apply_scenario_actions, apply_market_crash
from fplan_v2.api.routes.projections import (
    compute_projection,
    _create_index_tracker,
    _convert_orm_asset_to_business,
    _convert_orm_loan_to_business,
    _convert_orm_revenue_stream_to_business,
)


router = APIRouter()


def _build_scenario_cache_key(
    user: User,
    scenario_id: int,
    start_date: date,
    end_date: date,
    portfolio_id: int = None,
    scenario_version=None,
) -> str:
    """
    Build a SHA-256 cache key from portfolio id, portfolio version, scenario ID/version,
    and request params.

    The key includes portfolio_version (so any portfolio change invalidates it) and the
    scenario's own updated_at (so editing the scenario's actions invalidates it — the
    scenario itself doesn't bump portfolio_version).
    """
    key_data = f"{portfolio_id}:{user.portfolio_version}:{scenario_id}:{scenario_version}:{start_date}:{end_date}"
    return hashlib.sha256(key_data.encode()).hexdigest()


def _get_cached_scenario(db: Session, scenario_id: int, cache_key: str) -> Optional[dict]:
    """Look up cached scenario result."""
    from fplan_v2.db.models import ScenarioCache
    cache_entry = db.query(ScenarioCache).filter_by(
        scenario_id=scenario_id, cache_key=cache_key
    ).first()
    return cache_entry.result_json if cache_entry else None


def _store_cached_scenario(
    db: Session,
    user_id: int,
    scenario_id: int,
    cache_key: str,
    response: ProjectionResponse,
) -> None:
    """Store a scenario result in the cache."""
    from fplan_v2.db.models import ScenarioCache
    # Upsert: delete old entry if exists, insert new
    db.query(ScenarioCache).filter_by(scenario_id=scenario_id, cache_key=cache_key).delete()
    cache_entry = ScenarioCache(
        user_id=user_id,
        scenario_id=scenario_id,
        cache_key=cache_key,
        result_json=json.loads(response.model_dump_json()),
        computed_at=response.computed_at,
    )
    db.add(cache_entry)
    db.flush()


def _scenario_to_response(scenario) -> ScenarioResponse:
    """Convert a Scenario ORM object to a ScenarioResponse."""
    actions_data = scenario.actions_json or []
    actions = [ScenarioAction(**a) for a in actions_data]
    return ScenarioResponse(
        id=scenario.id,
        user_id=scenario.user_id,
        name=scenario.name,
        description=scenario.description,
        actions=actions,
        is_active=scenario.is_active,
        created_at=scenario.created_at,
        updated_at=scenario.updated_at,
    )


@router.post("", response_model=ScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    data: ScenarioCreate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """Create a new scenario."""
    repo = ScenarioRepository(db)

    # Serialize actions to JSON-compatible list of dicts
    actions_json = [a.model_dump(mode="json") for a in data.actions]

    scenario = repo.create(
        user_id=current_user.id,
        portfolio_id=current_portfolio.id,
        name=data.name,
        description=data.description,
        actions_json=actions_json,
    )

    return _scenario_to_response(scenario)


@router.get("", response_model=List[ScenarioResponse])
def list_scenarios(
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """List all scenarios for the active portfolio."""
    repo = ScenarioRepository(db)
    scenarios = repo.get_by_user(current_user.id, portfolio_id=current_portfolio.id)
    return [_scenario_to_response(s) for s in scenarios]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """Get a single scenario by ID."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id or scenario.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    return _scenario_to_response(scenario)


@router.put("/{scenario_id}", response_model=ScenarioResponse)
def update_scenario(
    scenario_id: int,
    data: ScenarioUpdate,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """Update an existing scenario."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id or scenario.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    update_kwargs = {}
    if data.name is not None:
        update_kwargs["name"] = data.name
    if data.description is not None:
        update_kwargs["description"] = data.description
    if data.actions is not None:
        update_kwargs["actions_json"] = [a.model_dump(mode="json") for a in data.actions]
    if data.is_active is not None:
        update_kwargs["is_active"] = data.is_active

    if update_kwargs:
        scenario = repo.update(scenario_id, **update_kwargs)

    return _scenario_to_response(scenario)


@router.delete("/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """Delete a scenario."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id or scenario.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    repo.delete(scenario_id)
    return None


@router.post("/{scenario_id}/run", response_model=ProjectionResponse)
def run_scenario(
    scenario_id: int,
    request: ProjectionRequest = None,
    current_user: User = Depends(get_current_user),
    current_portfolio: Portfolio = Depends(get_current_portfolio),
    db: Session = Depends(get_db_session),
):
    """
    Run a scenario projection.

    Loads the base portfolio, applies scenario actions, runs the projection
    pipeline on the modified portfolio, and applies post-projection actions
    (e.g., market crash).

    Returns a standard ProjectionResponse with scenario-modified data.
    """
    # Load the scenario
    scenario_repo = ScenarioRepository(db)
    scenario = scenario_repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id or scenario.portfolio_id != current_portfolio.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    # Parse projection parameters
    if request is None:
        request = ProjectionRequest()

    start_date = request.start_date or date.today()
    end_date = request.end_date or (start_date + timedelta(days=30 * 365))

    # Check cache first
    logger.info(f"[SCENARIO_CACHE] Building cache key for scenario_id={scenario_id}, user_id={current_user.id}, portfolio_id={current_portfolio.id}, start={start_date}, end={end_date}")
    cache_key = _build_scenario_cache_key(current_user, scenario_id, start_date, end_date, portfolio_id=current_portfolio.id, scenario_version=scenario.updated_at)
    logger.info(f"[SCENARIO_CACHE] Generated cache_key: {cache_key}")

    cached_result = _get_cached_scenario(db, scenario_id, cache_key)
    logger.info(f"[SCENARIO_CACHE] Cache lookup result: {'HIT' if cached_result else 'MISS'}")

    if cached_result:
        # Cache hit - return cached result
        logger.info("[SCENARIO_CACHE] Returning cached scenario result")
        return ProjectionResponse(**cached_result)

    months_to_project = ((end_date.year - start_date.year) * 12 +
                         (end_date.month - start_date.month))

    if months_to_project <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="End date must be after start date",
        )

    # Load base portfolio
    asset_repo = AssetRepository(db)
    loan_repo = LoanRepository(db)
    revenue_stream_repo = RevenueStreamRepository(db)
    measurement_repo = HistoricalMeasurementRepository(db)

    # Load with eager loading to eliminate N+1 queries
    from fplan_v2.db.models import Asset as AssetModel, Loan as LoanModel
    db_assets = asset_repo.get_all(
        user_id=current_user.id,
        portfolio_id=current_portfolio.id,
        limit=1000,
        eager_load=[AssetModel.revenue_streams, AssetModel.cash_flows]
    )
    db_loans = loan_repo.get_all(
        user_id=current_user.id,
        portfolio_id=current_portfolio.id,
        limit=1000,
        eager_load=[LoanModel.collateral_asset]
    )
    db_revenue_streams = revenue_stream_repo.get_all(user_id=current_user.id, portfolio_id=current_portfolio.id, limit=1000)
    all_measurements = measurement_repo.get_all(user_id=current_user.id, portfolio_id=current_portfolio.id)

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
            computed_at=datetime.now(),
        )

    # Convert ORM → business objects
    index_tracker = _create_index_tracker()
    assets = [_convert_orm_asset_to_business(db_asset, db) for db_asset in db_assets]
    loans = [_convert_orm_loan_to_business(db_loan, index_tracker) for db_loan in db_loans]
    revenue_streams = [_convert_orm_revenue_stream_to_business(db_stream) for db_stream in db_revenue_streams]

    # Apply scenario actions to deep copies
    actions = scenario.actions_json or []
    (mod_assets, mod_loans, mod_db_assets, mod_db_loans,
     mod_revenue_streams, mod_db_revenue_streams, post_actions) = apply_scenario_actions(
        assets, loans, db_assets, db_loans, actions,
        revenue_streams, db_revenue_streams,
    )

    try:
        # Run projection on modified portfolio
        response = compute_projection(
            assets=mod_assets,
            loans=mod_loans,
            db_assets=mod_db_assets,
            db_loans=mod_db_loans,
            measurements=all_measurements,
            start_date=start_date,
            end_date=end_date,
            months_to_project=months_to_project,
            db=db,
            user_id=current_user.id,
            portfolio_id=current_portfolio.id,
        )

        # Apply post-projection actions (market crash, deferred param changes)
        logger.info(f"[POST_ACTIONS] Processing {len(post_actions)} post-projection actions")
        if post_actions:
            for i, post_action in enumerate(post_actions):
                action_type = post_action.get("type")
                logger.info(f"[POST_ACTIONS] Action {i+1}/{len(post_actions)}: type={action_type}")
                if action_type == "market_crash":
                    logger.info("[POST_ACTIONS] Applying market crash")
                    _apply_market_crash_to_response(response, mod_db_assets, post_action)
                elif action_type == "param_change":
                    logger.info("[POST_ACTIONS] Applying deferred param_change")
                    _apply_deferred_param_change_to_response(response, mod_db_assets, mod_db_loans,
                                                            mod_db_revenue_streams, post_action)
                else:
                    logger.warning(f"[POST_ACTIONS] Unknown action type: {action_type}")
        else:
            logger.info("[POST_ACTIONS] No post-projection actions to apply")

        # Store result in cache
        logger.info(f"[SCENARIO_CACHE] Storing scenario result in cache with key: {cache_key}")
        _store_cached_scenario(db, current_user.id, scenario_id, cache_key, response)
        logger.info(f"[SCENARIO_CACHE] Scenario result cached successfully")

        return response

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scenario projection failed: {str(e)}",
        )


def _apply_market_crash_to_response(
    response: ProjectionResponse,
    db_assets: list,
    action: dict,
) -> None:
    """
    Apply market crash post-processing directly to a ProjectionResponse.

    Scales affected asset projection time series at and after crash_date
    by (1 - crash_pct/100).
    """
    from decimal import Decimal

    crash_pct = action.get("crash_pct", 0)
    crash_date_val = action.get("crash_date")
    affected_types = action.get("affected_asset_types")

    if not crash_date_val or crash_pct <= 0:
        return

    if isinstance(crash_date_val, str):
        crash_date_val = date.fromisoformat(crash_date_val)

    scale_factor = 1.0 - (crash_pct / 100.0)

    # Build a map of asset_id → asset_type from db_assets
    asset_type_map = {}
    for db_asset in db_assets:
        asset_type_map[db_asset.id] = db_asset.asset_type

    # Scale individual asset projections
    total_delta_by_date = {}  # date → cumulative delta for net worth/total assets adjustment

    for proj in response.asset_projections:
        asset_type = asset_type_map.get(proj.asset_id)

        # Virtual assets (id=0) and unknown assets: skip
        if proj.asset_id == 0 or asset_type is None:
            continue

        # Check if this asset type is affected
        if affected_types is not None and asset_type not in affected_types:
            continue

        for i, point in enumerate(proj.time_series):
            if point.date >= crash_date_val:
                old_val = float(point.value)
                new_val = old_val * scale_factor
                delta = new_val - old_val
                proj.time_series[i] = type(point)(
                    date=point.date,
                    value=Decimal(str(round(new_val, 2))),
                )
                total_delta_by_date[point.date] = total_delta_by_date.get(point.date, 0) + delta

    # Adjust total_assets_series and net_worth_series
    for i, point in enumerate(response.total_assets_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.total_assets_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    for i, point in enumerate(response.net_worth_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.net_worth_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )


def _apply_deferred_param_change_to_response(
    response: ProjectionResponse,
    db_assets: list,
    db_loans: list,
    db_revenue_streams: list,
    action: dict,
) -> None:
    """
    Apply a deferred param_change post-projection.

    From action_date onward, recalculate the time series using the new parameter
    value, compounding monthly from the value at the action_date.

    Supports:
    - Asset: appreciation_rate_annual_pct
    - Loan: interest_rate_annual_pct (not implemented yet)
    - RevenueStream: amount (deferred to Task #3)
    """
    from decimal import Decimal
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"=== _apply_deferred_param_change_to_response called ===")
    logger.info(f"Action: {action}")

    target_type = action.get("target_type")
    target_id = action.get("target_id")
    field = action.get("field")
    new_value = action.get("value")
    action_date_val = action.get("action_date")

    logger.info(f"Parsed: target_type={target_type}, target_id={target_id}, field={field}, new_value={new_value}, action_date={action_date_val}")

    if not all([target_type, target_id is not None, field, action_date_val]):
        logger.warning(f"Missing required fields, skipping")
        return

    if isinstance(action_date_val, str):
        action_date_val = date.fromisoformat(action_date_val)

    logger.info(f"Dispatching to handler for target_type={target_type}, field={field}")

    if target_type == "asset" and field == "appreciation_rate_annual_pct":
        logger.info("Calling _recalc_asset_appreciation")
        _recalc_asset_appreciation(response, db_assets, target_id, action_date_val, float(new_value))
    elif target_type == "loan" and field == "interest_rate_annual_pct":
        logger.info("Loan rate changes not implemented")
        # Loan rate changes are more complex; for now apply as immediate
        # (would need full amortization recalculation)
        pass
    elif target_type == "revenue_stream":
        logger.info(f"Revenue stream case: field={field}")
        if field == "amount":
            logger.info("Calling _recalc_revenue_stream_amount")
            _recalc_revenue_stream_amount(response, db_revenue_streams, target_id, action_date_val, float(new_value))
        elif field == "growth_rate":
            logger.info("Calling _recalc_revenue_stream_growth")
            _recalc_revenue_stream_growth(response, db_revenue_streams, target_id, action_date_val, float(new_value))
        else:
            logger.warning(f"Unsupported revenue_stream field: {field}")
    else:
        logger.warning(f"Unsupported target_type={target_type} or field={field}")


def _recalc_asset_appreciation(
    response: ProjectionResponse,
    db_assets: list,
    target_id: int,
    action_date_val: date,
    new_annual_rate: float,
) -> None:
    """
    Recalculate an asset's time series from action_date using a new appreciation rate.

    The value at action_date is kept as-is, then each subsequent month compounds
    at the new monthly rate.
    """
    from decimal import Decimal

    new_monthly_rate = (1 + new_annual_rate / 100) ** (1 / 12) - 1

    for proj in response.asset_projections:
        if proj.asset_id != target_id:
            continue

        ts = proj.time_series
        if not ts:
            break

        # Find the first index at or after action_date
        start_idx = None
        for i, point in enumerate(ts):
            if point.date >= action_date_val:
                start_idx = i
                break

        if start_idx is None:
            break

        # Recalculate from start_idx+1 onward using new rate
        # Keep the value at start_idx as the pivot
        total_delta_by_date = {}
        for i in range(start_idx + 1, len(ts)):
            old_val = float(ts[i].value)
            # Compound from pivot value
            months_from_pivot = i - start_idx
            base_val = float(ts[start_idx].value)
            new_val = base_val * ((1 + new_monthly_rate) ** months_from_pivot)
            delta = new_val - old_val
            ts[i] = type(ts[i])(
                date=ts[i].date,
                value=Decimal(str(round(new_val, 2))),
            )
            total_delta_by_date[ts[i].date] = total_delta_by_date.get(ts[i].date, 0) + delta

        # Adjust total_assets_series and net_worth_series
        for series in [response.total_assets_series, response.net_worth_series]:
            for i, point in enumerate(series):
                delta = total_delta_by_date.get(point.date, 0)
                if delta != 0:
                    new_val = float(point.value) + delta
                    series[i] = type(point)(
                        date=point.date,
                        value=Decimal(str(round(new_val, 2))),
                    )
        break


def _recalc_revenue_stream_amount(
    response: ProjectionResponse,
    db_revenue_streams: list,
    target_id: int,
    action_date_val: date,
    new_amount: float,
) -> None:
    """
    Recalculate a revenue stream's cash flow from action_date using a new amount.

    The cash flow at action_date is updated to the new amount, and all subsequent
    months use the new amount with existing growth rate applied from that point.
    """
    from decimal import Decimal
    import pandas as pd
    import logging

    logger = logging.getLogger(__name__)
    logger.info(f"=== _recalc_revenue_stream_amount called ===")
    logger.info(f"Target ID: {target_id}, New amount: {new_amount}, Action date: {action_date_val}")

    # Find the target revenue stream to get its period and growth rate
    target_stream = None
    for db_stream in db_revenue_streams:
        if db_stream.id == target_id:
            target_stream = db_stream
            break

    if not target_stream:
        logger.warning(f"Target revenue stream {target_id} not found!")
        return

    logger.info(f"Found stream: {target_stream.name}, current amount: {target_stream.amount}, type: {target_stream.stream_type}")

    # Only handle salary streams for now (most common case)
    if target_stream.stream_type != "salary":
        logger.info(f"Stream type {target_stream.stream_type} not supported, skipping")
        return

    period = target_stream.period or "monthly"
    growth_rate = float(target_stream.growth_rate or 0) / 100.0

    # Convert period amount to monthly
    if period == "yearly":
        monthly_amount = new_amount / 12.0
    elif period == "quarterly":
        monthly_amount = new_amount / 3.0
    else:  # monthly
        monthly_amount = new_amount

    logger.info(f"Period: {period}, Growth rate: {growth_rate*100}%, Monthly amount: {monthly_amount}")

    # Find the cash flow item for this revenue stream in the breakdown
    if not response.cash_flow_breakdown:
        logger.warning("No cash_flow_breakdown in response!")
        return

    stream_item = None
    for item in response.cash_flow_breakdown.items:
        # Match by checking if this is a salary item (category=salary)
        # We need to match by stream ID, but CashFlowItem doesn't have revenue_stream_id
        # So we match by name instead
        if item.category == "salary" and target_stream.name in item.source_name:
            stream_item = item
            break

    if not stream_item:
        logger.warning(f"Stream item not found in cash_flow_breakdown! Looking for: {target_stream.name}")
        logger.info(f"Available items: {[item.source_name for item in response.cash_flow_breakdown.items]}")
        return

    logger.info(f"Found cash flow item: {stream_item.source_name}")

    # Find the first index at or after action_date
    ts = stream_item.time_series
    start_idx = None
    for i, point in enumerate(ts):
        if point.date >= action_date_val:
            start_idx = i
            break

    if start_idx is None:
        logger.warning(f"No time series point found on or after {action_date_val}")
        return

    logger.info(f"Starting recalculation at index {start_idx}, date {ts[start_idx].date}")

    # Recalculate from start_idx onward
    # At start_idx, set to new monthly amount
    # For subsequent months, apply growth rate from start_idx
    action_date_ts = pd.Timestamp(action_date_val)
    total_delta_by_date = {}

    for i in range(start_idx, len(ts)):
        old_val = float(ts[i].value)
        current_date = pd.Timestamp(ts[i].date)

        # Calculate years elapsed from action date
        years_elapsed = (current_date.year - action_date_ts.year) + (current_date.month - action_date_ts.month) / 12.0
        new_val = monthly_amount * ((1 + growth_rate) ** years_elapsed)

        delta = new_val - old_val

        if i == start_idx:
            logger.info(f"First point: date={current_date.date()}, old={old_val}, new={new_val}, delta={delta}")

        ts[i] = type(ts[i])(
            date=ts[i].date,
            value=Decimal(str(round(new_val, 2))),
        )
        total_delta_by_date[ts[i].date] = delta

    logger.info(f"Recalculated {len(total_delta_by_date)} points with total delta sum: {sum(total_delta_by_date.values())}")

    # Update total income series in breakdown
    for i, point in enumerate(response.cash_flow_breakdown.total_income_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.cash_flow_breakdown.total_income_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    # Update net series in breakdown
    for i, point in enumerate(response.cash_flow_breakdown.net_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.cash_flow_breakdown.net_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    # Update monthly_cash_flow_series in main response
    for i, point in enumerate(response.monthly_cash_flow_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.monthly_cash_flow_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    # Update net worth by accumulating the cash flow changes
    # Net worth increases by the cumulative sum of cash flow deltas
    cumulative_delta = 0.0
    for i, point in enumerate(response.net_worth_series):
        date_delta = total_delta_by_date.get(point.date, 0)
        cumulative_delta += date_delta
        if cumulative_delta != 0:
            new_val = float(point.value) + cumulative_delta
            response.net_worth_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )


def _recalc_revenue_stream_growth(
    response: ProjectionResponse,
    db_revenue_streams: list,
    target_id: int,
    action_date_val: date,
    new_growth_rate: float,
) -> None:
    """
    Recalculate a revenue stream's cash flow from action_date using a new growth rate.

    The cash flow at action_date is kept as-is (pivot point), then subsequent months
    compound at the new growth rate from that base.
    """
    from decimal import Decimal
    import pandas as pd

    # Find the target revenue stream
    target_stream = None
    for db_stream in db_revenue_streams:
        if db_stream.id == target_id:
            target_stream = db_stream
            break

    if not target_stream:
        return

    # Only handle salary streams for now
    if target_stream.stream_type != "salary":
        return

    new_growth_rate_decimal = new_growth_rate / 100.0

    # Find the cash flow item for this revenue stream
    if not response.cash_flow_breakdown:
        return

    stream_item = None
    for item in response.cash_flow_breakdown.items:
        if item.category == "salary" and target_stream.name in item.source_name:
            stream_item = item
            break

    if not stream_item:
        return

    # Find the first index at or after action_date
    ts = stream_item.time_series
    start_idx = None
    for i, point in enumerate(ts):
        if point.date >= action_date_val:
            start_idx = i
            break

    if start_idx is None:
        return

    # Keep the value at start_idx as pivot, recalculate subsequent months
    action_date_ts = pd.Timestamp(action_date_val)
    pivot_value = float(ts[start_idx].value)
    total_delta_by_date = {}

    for i in range(start_idx + 1, len(ts)):
        old_val = float(ts[i].value)
        current_date = pd.Timestamp(ts[i].date)

        # Calculate years elapsed from action date
        years_elapsed = (current_date.year - action_date_ts.year) + (current_date.month - action_date_ts.month) / 12.0
        new_val = pivot_value * ((1 + new_growth_rate_decimal) ** years_elapsed)

        delta = new_val - old_val
        ts[i] = type(ts[i])(
            date=ts[i].date,
            value=Decimal(str(round(new_val, 2))),
        )
        total_delta_by_date[ts[i].date] = delta

    # Update all the series similar to _recalc_revenue_stream_amount
    for i, point in enumerate(response.cash_flow_breakdown.total_income_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.cash_flow_breakdown.total_income_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    for i, point in enumerate(response.cash_flow_breakdown.net_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.cash_flow_breakdown.net_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    for i, point in enumerate(response.monthly_cash_flow_series):
        delta = total_delta_by_date.get(point.date, 0)
        if delta != 0:
            new_val = float(point.value) + delta
            response.monthly_cash_flow_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )

    cumulative_delta = 0.0
    for i, point in enumerate(response.net_worth_series):
        date_delta = total_delta_by_date.get(point.date, 0)
        cumulative_delta += date_delta
        if cumulative_delta != 0:
            new_val = float(point.value) + cumulative_delta
            response.net_worth_series[i] = type(point)(
                date=point.date,
                value=Decimal(str(round(new_val, 2))),
            )
