"""
Pydantic schemas for API request/response validation.

These schemas provide:
- Input validation for API requests
- Response serialization
- OpenAPI documentation generation
- Type safety
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Optional, Dict, Any, List
from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, field_validator


# ======================
# Enums
# ======================


class AssetType(str, Enum):
    """Asset type enumeration."""

    REAL_ESTATE = "real_estate"
    STOCK = "stock"
    PENSION = "pension"
    CASH = "cash"


class LoanType(str, Enum):
    """Loan type enumeration."""

    FIXED = "fixed"
    PRIME_PEGGED = "prime_pegged"
    CPI_PEGGED = "cpi_pegged"
    VARIABLE = "variable"


class RevenueStreamType(str, Enum):
    """Revenue stream type enumeration."""

    RENT = "rent"
    DIVIDEND = "dividend"
    PENSION = "pension"
    SALARY = "salary"


class Period(str, Enum):
    """Period enumeration for revenue streams."""

    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class CashFlowType(str, Enum):
    """Cash flow type enumeration."""

    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"


# ======================
# Base Schemas
# ======================


class BaseSchema(BaseModel):
    """Base schema with common configuration."""

    model_config = ConfigDict(
        from_attributes=True,  # Enable ORM mode for SQLAlchemy
        validate_assignment=True,
        use_enum_values=True,
        json_encoders={
            Decimal: lambda v: float(v),
            date: lambda v: v.isoformat(),
            datetime: lambda v: v.isoformat(),
        },
    )


# ======================
# Asset Schemas
# ======================


class AssetBase(BaseSchema):
    """Base asset schema with common fields."""

    external_id: str = Field(..., description="User-defined unique identifier")
    asset_type: AssetType
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    original_value: Decimal = Field(..., ge=0)
    appreciation_rate_annual_pct: Decimal = Field(default=0, ge=-100, le=1000)
    yearly_fee_pct: Decimal = Field(default=0, ge=0, le=100)
    sell_date: Optional[date] = None
    sell_tax: Decimal = Field(default=0, ge=0, le=100)
    currency: str = Field(default="ILS", max_length=3)
    config_json: Dict[str, Any] = Field(default_factory=dict)


class AssetCreate(AssetBase):
    """Schema for creating a new asset."""

    pass


class AssetUpdate(BaseSchema):
    """Schema for updating an asset (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    current_value: Optional[Decimal] = Field(None, ge=0)
    appreciation_rate_annual_pct: Optional[Decimal] = Field(None, ge=-100, le=1000)
    yearly_fee_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    sell_date: Optional[date] = None
    sell_tax: Optional[Decimal] = Field(None, ge=0, le=100)
    config_json: Optional[Dict[str, Any]] = None


class AssetResponse(AssetBase):
    """Schema for asset responses."""

    id: int
    user_id: int
    current_value: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


# ======================
# Loan Schemas
# ======================


class LoanBase(BaseSchema):
    """Base loan schema with common fields."""

    external_id: str = Field(..., description="User-defined unique identifier")
    loan_type: LoanType
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    original_value: Decimal = Field(..., ge=0)
    interest_rate_annual_pct: Decimal = Field(..., ge=0, le=100)
    duration_months: int = Field(..., gt=0)
    collateral_asset_id: Optional[int] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)


class LoanCreate(LoanBase):
    """Schema for creating a new loan."""

    pass


class LoanUpdate(BaseSchema):
    """Schema for updating a loan (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    current_balance: Optional[Decimal] = Field(None, ge=0)
    interest_rate_annual_pct: Optional[Decimal] = Field(None, ge=0, le=100)
    config_json: Optional[Dict[str, Any]] = None


class LoanResponse(LoanBase):
    """Schema for loan responses."""

    id: int
    user_id: int
    current_balance: Optional[Decimal] = None
    created_at: datetime
    updated_at: datetime


# ======================
# Revenue Stream Schemas
# ======================


class RevenueStreamBase(BaseSchema):
    """Base revenue stream schema."""

    stream_type: RevenueStreamType
    name: str = Field(..., min_length=1, max_length=255)
    start_date: date
    end_date: Optional[date] = None
    amount: Decimal = Field(..., ge=0)
    period: Period = Field(default=Period.MONTHLY)
    tax_rate: Decimal = Field(default=0, ge=0, le=100)
    growth_rate: Decimal = Field(default=0, ge=-100, le=1000)
    asset_id: Optional[int] = None
    config_json: Dict[str, Any] = Field(default_factory=dict)


class RevenueStreamCreate(RevenueStreamBase):
    """Schema for creating a revenue stream."""

    pass


class RevenueStreamUpdate(BaseSchema):
    """Schema for updating a revenue stream."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    end_date: Optional[date] = None
    amount: Optional[Decimal] = Field(None, ge=0)
    tax_rate: Optional[Decimal] = Field(None, ge=0, le=100)
    growth_rate: Optional[Decimal] = Field(None, ge=-100, le=1000)
    config_json: Optional[Dict[str, Any]] = None


class RevenueStreamResponse(RevenueStreamBase):
    """Schema for revenue stream responses."""

    id: int
    user_id: int
    created_at: datetime


# ======================
# Cash Flow Schemas
# ======================


class CashFlowCreate(BaseSchema):
    """Schema for creating a new cash flow."""

    flow_type: CashFlowType
    name: str = Field(..., min_length=1, max_length=255)
    amount: Decimal = Field(..., ge=0)
    from_date: date
    to_date: date
    target_asset_id: Optional[int] = None
    from_own_capital: bool = True


class CashFlowUpdate(BaseSchema):
    """Schema for updating a cash flow (all fields optional)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255)
    amount: Optional[Decimal] = Field(None, ge=0)
    from_date: Optional[date] = None
    to_date: Optional[date] = None
    target_asset_id: Optional[int] = None
    from_own_capital: Optional[bool] = None


class CashFlowResponse(BaseSchema):
    """Schema for cash flow responses."""

    id: int
    user_id: int
    flow_type: CashFlowType
    target_asset_id: Optional[int] = None
    name: str
    amount: Decimal
    from_date: date
    to_date: date
    from_own_capital: bool = False
    created_at: datetime


# ======================
# Projection Schemas
# ======================


class ProjectionRequest(BaseSchema):
    """Schema for projection calculation requests."""

    start_date: Optional[date] = Field(None, description="Projection start date (defaults to today)")
    end_date: Optional[date] = Field(None, description="Projection end date (defaults to 30 years from start)")
    as_of_date: Optional[date] = Field(None, description="Run projection as of this past date (for historical comparison)")
    include_scenarios: bool = Field(default=False, description="Include scenario comparisons")
    scenario_ids: Optional[List[int]] = Field(None, description="Specific scenario IDs to include")


class TimeSeriesDataPoint(BaseSchema):
    """Single data point in a time series."""

    date: date
    value: Decimal


class MeasurementMarker(BaseSchema):
    """A single historical measurement marker for overlay on charts."""

    date: date
    actual_value: Decimal
    entity_type: str = Field(..., description="'asset' or 'loan'")
    entity_id: int
    entity_name: str


class AssetProjection(BaseSchema):
    """Projection data for a single asset."""

    asset_id: int
    asset_name: str
    asset_type: AssetType
    time_series: List[TimeSeriesDataPoint]
    measurements: List[MeasurementMarker] = []


class LoanProjection(BaseSchema):
    """Projection data for a single loan."""

    loan_id: int
    loan_name: str
    loan_type: LoanType
    balance_series: List[TimeSeriesDataPoint]
    payment_series: List[TimeSeriesDataPoint]
    measurements: List[MeasurementMarker] = []


class CashFlowItem(BaseSchema):
    """A single cash flow source in the breakdown."""

    source_name: str = Field(..., description="e.g. 'Salary - Main Job'")
    source_type: str = Field(..., description="'income' or 'expense'")
    category: str = Field(..., description="salary, rent, dividend, pension, loan_payment, deposit, withdrawal")
    time_series: List[TimeSeriesDataPoint]
    entity_id: Optional[int] = Field(None, description="ID of linked asset or loan (null for salaries)")
    entity_type: Optional[str] = Field(None, description="'asset' or 'loan' or null")


class CashFlowBreakdown(BaseSchema):
    """Detailed cash flow breakdown by source."""

    items: List[CashFlowItem]
    total_income_series: List[TimeSeriesDataPoint]
    total_expense_series: List[TimeSeriesDataPoint]
    net_series: List[TimeSeriesDataPoint]


class ProjectionResponse(BaseSchema):
    """Schema for projection results."""

    user_id: int
    start_date: date
    end_date: date
    net_worth_series: List[TimeSeriesDataPoint]
    total_assets_series: List[TimeSeriesDataPoint]
    total_liabilities_series: List[TimeSeriesDataPoint]
    monthly_cash_flow_series: List[TimeSeriesDataPoint]
    cash_flow_breakdown: Optional[CashFlowBreakdown] = None
    asset_projections: List[AssetProjection]
    loan_projections: List[LoanProjection]
    measurement_markers: List[MeasurementMarker] = []
    is_historical: bool = Field(default=False, description="True if this is a historical projection")
    historical_as_of_date: Optional[date] = Field(None, description="The as_of_date used for historical projection")
    computed_at: datetime


# ======================
# Portfolio Summary Schemas
# ======================


class PortfolioSummary(BaseSchema):
    """Current portfolio summary statistics."""

    user_id: int
    total_assets: Decimal
    total_liabilities: Decimal
    net_worth: Decimal
    monthly_revenue: Decimal
    monthly_loan_payments: Decimal
    monthly_net_cash_flow: Decimal
    asset_count: int
    loan_count: int
    revenue_stream_count: int
    as_of_date: date


# ======================
# Historical Measurement Schemas
# ======================


class EntityType(str, Enum):
    """Entity type for historical measurements."""

    ASSET = "asset"
    LOAN = "loan"


class MeasurementSource(str, Enum):
    """Source of a historical measurement."""

    MANUAL = "manual"
    IMPORT = "import"
    AUTO = "auto"


class HistoricalMeasurementCreate(BaseSchema):
    """Schema for creating a historical measurement."""

    entity_type: EntityType
    entity_id: int = Field(..., description="ID of the asset or loan")
    measurement_date: date
    actual_value: Decimal = Field(..., ge=0)
    rate_at_time: Optional[Decimal] = None
    notes: Optional[str] = None
    source: MeasurementSource = Field(default=MeasurementSource.MANUAL)


class HistoricalMeasurementUpdate(BaseSchema):
    """Schema for updating a historical measurement (all fields optional)."""

    measurement_date: Optional[date] = None
    actual_value: Optional[Decimal] = None
    rate_at_time: Optional[Decimal] = None
    notes: Optional[str] = None
    source: Optional[MeasurementSource] = None


class HistoricalMeasurementResponse(BaseSchema):
    """Schema for historical measurement responses."""

    id: int
    user_id: int
    entity_type: EntityType
    entity_id: int
    measurement_date: date
    actual_value: Decimal
    rate_at_time: Optional[Decimal] = None
    notes: Optional[str] = None
    source: str
    recorded_at: datetime


# ======================
# Error Response Schema
# ======================


class ErrorResponse(BaseSchema):
    """Standard error response schema."""

    error: str = Field(..., description="Error message")
    detail: Optional[str] = Field(None, description="Detailed error information")
    type: Optional[str] = Field(None, description="Error type/class")
