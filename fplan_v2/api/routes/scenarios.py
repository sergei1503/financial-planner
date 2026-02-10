"""
Scenario API endpoints.

Provides CRUD operations for what-if scenarios and scenario projection execution.
"""

import json
from datetime import date, datetime, timedelta
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from fplan_v2.api.schemas import (
    ScenarioCreate,
    ScenarioUpdate,
    ScenarioResponse,
    ScenarioAction,
    ProjectionRequest,
    ProjectionResponse,
)
from fplan_v2.api.auth import get_current_user
from fplan_v2.db.connection import get_db_session
from fplan_v2.db.models import User
from fplan_v2.db.repositories import (
    AssetRepository,
    LoanRepository,
    HistoricalMeasurementRepository,
    ScenarioRepository,
)
from fplan_v2.core.engine.scenario_engine import apply_scenario_actions, apply_market_crash
from fplan_v2.api.routes.projections import (
    compute_projection,
    _create_index_tracker,
    _convert_orm_asset_to_business,
    _convert_orm_loan_to_business,
)


router = APIRouter()


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
    db: Session = Depends(get_db_session),
):
    """Create a new scenario."""
    repo = ScenarioRepository(db)

    # Serialize actions to JSON-compatible list of dicts
    actions_json = [a.model_dump(mode="json") for a in data.actions]

    scenario = repo.create(
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        actions_json=actions_json,
    )

    return _scenario_to_response(scenario)


@router.get("", response_model=List[ScenarioResponse])
def list_scenarios(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """List all scenarios for the current user."""
    repo = ScenarioRepository(db)
    scenarios = repo.get_by_user(current_user.id)
    return [_scenario_to_response(s) for s in scenarios]


@router.get("/{scenario_id}", response_model=ScenarioResponse)
def get_scenario(
    scenario_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """Get a single scenario by ID."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id:
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
    db: Session = Depends(get_db_session),
):
    """Update an existing scenario."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id:
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
    db: Session = Depends(get_db_session),
):
    """Delete a scenario."""
    repo = ScenarioRepository(db)
    scenario = repo.get_by_id(scenario_id)

    if not scenario or scenario.user_id != current_user.id:
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

    if not scenario or scenario.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found",
        )

    # Parse projection parameters
    if request is None:
        request = ProjectionRequest()

    start_date = request.start_date or date.today()
    end_date = request.end_date or (start_date + timedelta(days=30 * 365))
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
    measurement_repo = HistoricalMeasurementRepository(db)

    db_assets = asset_repo.get_all(user_id=current_user.id, limit=1000)
    db_loans = loan_repo.get_all(user_id=current_user.id, limit=1000)
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
            computed_at=datetime.now(),
        )

    # Convert ORM → business objects
    index_tracker = _create_index_tracker()
    assets = [_convert_orm_asset_to_business(db_asset, db) for db_asset in db_assets]
    loans = [_convert_orm_loan_to_business(db_loan, index_tracker) for db_loan in db_loans]

    # Apply scenario actions to deep copies
    actions = scenario.actions_json or []
    mod_assets, mod_loans, mod_db_assets, mod_db_loans, post_actions = apply_scenario_actions(
        assets, loans, db_assets, db_loans, actions,
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
        )

        # Apply post-projection actions (market crash, deferred param changes)
        if post_actions:
            for post_action in post_actions:
                if post_action.get("type") == "market_crash":
                    _apply_market_crash_to_response(response, mod_db_assets, post_action)
                elif post_action.get("type") == "param_change":
                    _apply_deferred_param_change_to_response(response, mod_db_assets, mod_db_loans, post_action)

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
    action: dict,
) -> None:
    """
    Apply a deferred param_change post-projection.

    From action_date onward, recalculate the time series using the new parameter
    value, compounding monthly from the value at the action_date.

    Supports appreciation_rate_annual_pct and interest_rate_annual_pct changes.
    """
    from decimal import Decimal

    target_type = action.get("target_type")
    target_id = action.get("target_id")
    field = action.get("field")
    new_value = action.get("value")
    action_date_val = action.get("action_date")

    if not all([target_type, target_id is not None, field, action_date_val]):
        return

    if isinstance(action_date_val, str):
        action_date_val = date.fromisoformat(action_date_val)

    if target_type == "asset" and field == "appreciation_rate_annual_pct":
        _recalc_asset_appreciation(response, db_assets, target_id, action_date_val, float(new_value))
    elif target_type == "loan" and field == "interest_rate_annual_pct":
        # Loan rate changes are more complex; for now apply as immediate
        # (would need full amortization recalculation)
        pass


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
