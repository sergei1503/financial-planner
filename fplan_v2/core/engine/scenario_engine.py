"""
Scenario engine for applying what-if actions to a portfolio.

Takes base portfolio business objects and a list of scenario actions,
returns modified objects ready for the projection pipeline.
"""

import copy
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from fplan_v2.core.constants import VALUE
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


def apply_scenario_actions(
    assets: list,
    loans: list,
    db_assets: list,
    db_loans: list,
    actions: List[Dict[str, Any]],
) -> Tuple[list, list, list, list, List[Dict[str, Any]]]:
    """
    Apply scenario actions to deep copies of portfolio objects.

    Args:
        assets: List of business Asset objects
        loans: List of business Loan objects
        db_assets: List of ORM Asset objects
        db_loans: List of ORM Loan objects
        actions: List of action dicts from the scenario

    Returns:
        Tuple of (modified_assets, modified_loans, modified_db_assets,
                  modified_db_loans, post_projection_actions)
    """
    # Deep copy everything so we don't mutate the originals
    mod_assets = copy.deepcopy(assets)
    mod_loans = copy.deepcopy(loans)
    mod_db_assets = copy.deepcopy(db_assets)
    mod_db_loans = copy.deepcopy(db_loans)

    post_projection_actions = []

    for action in actions:
        action_type = action.get("type")

        if action_type == "param_change":
            if action.get("action_date"):
                # Deferred param change — apply post-projection
                post_projection_actions.append(action)
            else:
                _apply_param_change(mod_assets, mod_loans, mod_db_assets, mod_db_loans, action)

        elif action_type == "new_asset":
            new_asset, new_db_asset = _apply_new_asset(action)
            if new_asset and new_db_asset:
                mod_assets.append(new_asset)
                mod_db_assets.append(new_db_asset)

        elif action_type == "new_loan":
            new_loan, new_db_loan = _apply_new_loan(action)
            if new_loan and new_db_loan:
                mod_loans.append(new_loan)
                mod_db_loans.append(new_db_loan)

        elif action_type == "repay_loan":
            _apply_repay_loan(mod_loans, mod_db_loans, action)

        elif action_type == "transform_asset":
            _apply_transform_asset(mod_assets, mod_db_assets, action)

        elif action_type == "withdraw_from_asset":
            _apply_withdraw_deposit(mod_assets, mod_db_assets, action, is_deposit=False)

        elif action_type == "deposit_to_asset":
            _apply_withdraw_deposit(mod_assets, mod_db_assets, action, is_deposit=True)

        elif action_type == "add_revenue_stream":
            _apply_add_revenue_stream(mod_assets, mod_db_assets, action)

        elif action_type == "market_crash":
            # Market crash is applied post-projection
            post_projection_actions.append(action)

    return mod_assets, mod_loans, mod_db_assets, mod_db_loans, post_projection_actions


def apply_market_crash(
    all_asset_dfs: List[pd.DataFrame],
    db_assets: list,
    action: Dict[str, Any],
) -> None:
    """
    Apply a market crash post-projection action.

    At crash_date, scale affected asset values by (1 - crash_pct/100)
    and all subsequent values by the same ratio.

    Args:
        all_asset_dfs: List of asset projection DataFrames (modified in-place)
        db_assets: List of ORM Asset objects
        action: Market crash action dict
    """
    crash_pct = action.get("crash_pct", 0)
    crash_date_val = action.get("crash_date")
    affected_types = action.get("affected_asset_types")  # None means all

    if not crash_date_val or crash_pct <= 0:
        return

    if isinstance(crash_date_val, str):
        crash_date_val = date.fromisoformat(crash_date_val)

    crash_ts = pd.Timestamp(crash_date_val).replace(day=1)
    scale_factor = 1.0 - (crash_pct / 100.0)

    for i, db_asset in enumerate(db_assets):
        # Check if this asset type is affected
        if affected_types is not None:
            if db_asset.asset_type not in affected_types:
                continue

        df = all_asset_dfs[i]
        if df.empty:
            continue

        # Find rows at or after crash date and scale them
        mask = df["date"] >= crash_ts
        if mask.any():
            df.loc[mask, VALUE] = df.loc[mask, VALUE].astype(float) * scale_factor


def _apply_param_change(
    assets: list,
    loans: list,
    db_assets: list,
    db_loans: list,
    action: Dict[str, Any],
) -> None:
    """Apply a parameter change to a specific entity."""
    target_type = action.get("target_type")
    target_id = action.get("target_id")
    field = action.get("field")
    value = action.get("value")

    if not target_type or target_id is None or not field:
        return

    if target_type == "asset":
        for i, db_asset in enumerate(db_assets):
            if db_asset.id == target_id:
                # Update the business object
                if hasattr(assets[i], field):
                    setattr(assets[i], field, value)
                # Also update the ORM object for consistency
                if hasattr(db_asset, field):
                    setattr(db_asset, field, value)
                break

    elif target_type == "loan":
        for i, db_loan in enumerate(db_loans):
            if db_loan.id == target_id:
                if hasattr(loans[i], field):
                    setattr(loans[i], field, value)
                if hasattr(db_loan, field):
                    setattr(db_loan, field, value)
                break


def _apply_new_asset(action: Dict[str, Any]) -> Tuple[Optional[Asset], Optional[Any]]:
    """Create a new business Asset from action params."""
    params = action.get("params", {})
    if not params:
        return None, None

    asset_type = params.get("asset_type", "stock")
    base_id = params.get("external_id", f"scenario_{id(action)}")
    start_date_val = params.get("start_date", date.today())
    if isinstance(start_date_val, str):
        start_date_val = date.fromisoformat(start_date_val)
    original_value = float(params.get("original_value", 0))
    appreciation = float(params.get("appreciation_rate_annual_pct", 0))
    yearly_fee = float(params.get("yearly_fee_pct", 0))
    name = params.get("name", "Scenario Asset")

    # Create the business object
    if asset_type == "cash":
        asset = CashAsset(id=base_id, start_date=start_date_val, original_value=original_value)
    elif asset_type == "real_estate":
        asset = RealEstateAsset(
            id=base_id, start_date=start_date_val, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None,
        )
    elif asset_type == "stock":
        asset = StockAsset(
            id=base_id, start_date=start_date_val, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=[], withdrawals=[],
        )
    elif asset_type == "pension":
        asset = PensionAsset(
            id=base_id, start_date=start_date_val, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=[], end_date=params.get("end_date", "2070-01-01"),
            conversion_date=params.get("conversion_date"),
            conversion_coefficient=params.get("conversion_coefficient", 200),
        )
    else:
        asset = Asset(
            id=base_id, start_date=start_date_val, original_value=original_value,
            appreciation_rate_annual_pct=appreciation, yearly_fee_pct=yearly_fee,
            revenue_stream=None, deposits=[], withdrawals=[],
        )

    # Create a mock DB asset object for projection pipeline compatibility
    mock_db_asset = _MockDbEntity(
        id=-abs(hash(base_id)) % 100000,  # Negative-derived ID to avoid collisions
        user_id=0,
        external_id=base_id,
        name=name,
        asset_type=asset_type,
        start_date=start_date_val,
        original_value=original_value,
        current_value=None,
        appreciation_rate_annual_pct=appreciation,
        yearly_fee_pct=yearly_fee,
        sell_date=params.get("sell_date"),
        sell_tax=float(params.get("sell_tax", 0)),
        config_json=params.get("config_json", {}),
    )

    return asset, mock_db_asset


def _apply_new_loan(action: Dict[str, Any]) -> Tuple[Optional[Any], Optional[Any]]:
    """Create a new business Loan from action params."""
    params = action.get("params", {})
    if not params:
        return None, None

    loan_type = params.get("loan_type", "fixed")
    loan_id = params.get("external_id", f"scenario_loan_{id(action)}")
    start_date_val = params.get("start_date", date.today())
    if isinstance(start_date_val, str):
        start_date_val = date.fromisoformat(start_date_val)
    value = float(params.get("original_value", 0))
    rate = float(params.get("interest_rate_annual_pct", 0))
    duration = int(params.get("duration_months", 240))
    name = params.get("name", "Scenario Loan")

    if loan_type == "fixed":
        loan = LoanFixed(
            id=loan_id, value=value, interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start_date_val,
            collateral_asset=None,
        )
    elif loan_type == "variable":
        loan = LoanVariable(
            id=loan_id, value=value, base_rate_annual_pct=rate,
            margin_pct=float(params.get("margin_pct", 0)),
            duration_months=duration, start_date=start_date_val,
            inflation_rate_annual_pct=float(params.get("inflation_rate", 0)),
            collateral_asset=None,
        )
    else:
        # Default to fixed for other types in scenario context
        loan = LoanFixed(
            id=loan_id, value=value, interest_rate_annual_pct=rate,
            duration_months=duration, start_date=start_date_val,
            collateral_asset=None,
        )

    mock_db_loan = _MockDbEntity(
        id=-abs(hash(loan_id)) % 100000,
        user_id=0,
        external_id=loan_id,
        name=name,
        loan_type=loan_type,
        start_date=start_date_val,
        original_value=value,
        current_balance=None,
        interest_rate_annual_pct=rate,
        duration_months=duration,
        collateral_asset_id=None,
        config_json=params.get("config_json", {}),
    )

    return loan, mock_db_loan


def _apply_repay_loan(
    loans: list,
    db_loans: list,
    action: Dict[str, Any],
) -> None:
    """Modify a loan to end at the repay date."""
    target_id = action.get("target_id")
    repay_date = action.get("action_date") or action.get("date")

    if target_id is None or not repay_date:
        return

    if isinstance(repay_date, str):
        repay_date = date.fromisoformat(repay_date)

    for i, db_loan in enumerate(db_loans):
        if db_loan.id == target_id:
            # Calculate remaining months from start to repay date
            start = db_loan.start_date
            if isinstance(start, str):
                start = date.fromisoformat(start)
            months_remaining = (
                (repay_date.year - start.year) * 12 +
                (repay_date.month - start.month)
            )
            if months_remaining > 0:
                # Update duration on both business and DB objects
                if hasattr(loans[i], 'duration_months'):
                    loans[i].duration_months = months_remaining
                if hasattr(db_loan, 'duration_months'):
                    db_loan.duration_months = months_remaining
            break


def _apply_transform_asset(
    assets: list,
    db_assets: list,
    action: Dict[str, Any],
) -> None:
    """Apply multiple field changes to an asset."""
    target_id = action.get("target_id")
    changes = action.get("changes", {})

    if target_id is None or not changes:
        return

    for i, db_asset in enumerate(db_assets):
        if db_asset.id == target_id:
            for field, value in changes.items():
                if hasattr(assets[i], field):
                    setattr(assets[i], field, value)
                if hasattr(db_asset, field):
                    setattr(db_asset, field, value)
            break


def _apply_withdraw_deposit(
    assets: list,
    db_assets: list,
    action: Dict[str, Any],
    is_deposit: bool,
) -> None:
    """Inject a cash flow entry (withdraw or deposit) into an asset."""
    target_id = action.get("target_id")
    amount = action.get("amount")
    action_date = action.get("action_date") or action.get("date")

    if target_id is None or amount is None or not action_date:
        return

    if isinstance(action_date, str):
        action_date = date.fromisoformat(action_date)

    date_str = action_date.strftime("%d/%m/%Y")

    for i, db_asset in enumerate(db_assets):
        if db_asset.id == target_id:
            entry = {
                "amount": float(amount),
                "from": date_str,
                "to": date_str,
                "deposit_from_own_capital": True,
            }
            if is_deposit:
                if hasattr(assets[i], 'deposits') and isinstance(assets[i].deposits, list):
                    assets[i].deposits.append(entry)
            else:
                if hasattr(assets[i], 'withdrawals') and isinstance(assets[i].withdrawals, list):
                    assets[i].withdrawals.append(entry)
            break


def _apply_add_revenue_stream(
    assets: list,
    db_assets: list,
    action: Dict[str, Any],
) -> None:
    """Create and attach a revenue stream to an asset."""
    target_id = action.get("target_id")
    params = action.get("params", {})

    if not params:
        return

    stream_type = params.get("stream_type", "rent")
    stream_name = params.get("name", "Scenario Stream")
    start_date_val = params.get("start_date", date.today())
    if isinstance(start_date_val, str):
        start_date_val = date.fromisoformat(start_date_val)
    end_date_val = params.get("end_date")
    if isinstance(end_date_val, str):
        end_date_val = date.fromisoformat(end_date_val)
    amount = float(params.get("amount", 0))

    # Create the business revenue stream
    if stream_type == "rent":
        stream = RentRevenueStream(
            id=stream_name,
            start_date=start_date_val,
            amount=amount,
            period=params.get("period", "monthly"),
            tax=float(params.get("tax_rate", 0)),
            growth_rate=float(params.get("growth_rate", 0)),
            end_date=end_date_val,
        )
    elif stream_type == "salary":
        stream = SalaryRevenueStream(
            id=stream_name,
            start_date=start_date_val,
            end_date=end_date_val or "01/01/2070",
            amount=amount,
            growth_rate=float(params.get("growth_rate", 0)),
        )
    elif stream_type == "pension":
        stream = PensionRevenueStream(
            id=stream_name,
            start_date=start_date_val,
            monthly_payout=amount,
        )
    else:
        return

    # Attach to target asset if specified, otherwise to first asset
    if target_id is not None:
        for i, db_asset in enumerate(db_assets):
            if db_asset.id == target_id:
                assets[i].revenue_stream = stream
                break
    elif assets:
        assets[0].revenue_stream = stream


class _MockDbEntity:
    """
    Lightweight mock for ORM entity objects used by the projection pipeline.

    When a scenario creates a new asset or loan, the projection pipeline
    needs db_asset/db_loan objects for metadata (name, type, id, etc.).
    This class provides those attributes without requiring a real DB record.
    """

    def __init__(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
