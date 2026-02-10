// Enums as const objects (erasableSyntaxOnly compatible)
export const AssetType = {
  REAL_ESTATE: 'real_estate',
  STOCK: 'stock',
  PENSION: 'pension',
  CASH: 'cash',
} as const;
export type AssetType = (typeof AssetType)[keyof typeof AssetType];

export const LoanType = {
  FIXED: 'fixed',
  PRIME_PEGGED: 'prime_pegged',
  CPI_PEGGED: 'cpi_pegged',
  VARIABLE: 'variable',
} as const;
export type LoanType = (typeof LoanType)[keyof typeof LoanType];

export const RevenueStreamType = {
  RENT: 'rent',
  DIVIDEND: 'dividend',
  PENSION: 'pension',
  SALARY: 'salary',
} as const;
export type RevenueStreamType = (typeof RevenueStreamType)[keyof typeof RevenueStreamType];

export const Period = {
  MONTHLY: 'monthly',
  QUARTERLY: 'quarterly',
  YEARLY: 'yearly',
} as const;
export type Period = (typeof Period)[keyof typeof Period];

// Asset interfaces
export interface AssetCreate {
  external_id: string;
  asset_type: AssetType;
  name: string;
  start_date: string; // ISO date
  original_value: number;
  appreciation_rate_annual_pct?: number;
  yearly_fee_pct?: number;
  sell_date?: string | null;
  sell_tax?: number;
  currency?: string;
  config_json?: Record<string, unknown>;
}

export interface AssetUpdate {
  name?: string;
  current_value?: number;
  appreciation_rate_annual_pct?: number;
  yearly_fee_pct?: number;
  sell_date?: string | null;
  sell_tax?: number;
  config_json?: Record<string, unknown>;
}

export interface AssetResponse {
  id: number;
  external_id: string;
  asset_type: AssetType;
  name: string;
  start_date: string;
  original_value: number;
  appreciation_rate_annual_pct: number;
  yearly_fee_pct: number;
  sell_date: string | null;
  sell_tax: number;
  currency: string;
  config_json: Record<string, unknown>;
  user_id: number;
  current_value: number | null;
  created_at: string;
  updated_at: string;
}

// Loan interfaces
export interface LoanCreate {
  external_id: string;
  loan_type: LoanType;
  name: string;
  start_date: string;
  original_value: number;
  interest_rate_annual_pct: number;
  duration_months: number;
  collateral_asset_id?: number | null;
  config_json?: Record<string, unknown>;
}

export interface LoanUpdate {
  name?: string;
  current_balance?: number;
  interest_rate_annual_pct?: number;
  config_json?: Record<string, unknown>;
}

export interface LoanResponse {
  id: number;
  external_id: string;
  loan_type: LoanType;
  name: string;
  start_date: string;
  original_value: number;
  interest_rate_annual_pct: number;
  duration_months: number;
  collateral_asset_id: number | null;
  config_json: Record<string, unknown>;
  user_id: number;
  current_balance: number | null;
  created_at: string;
  updated_at: string;
}

// Revenue Stream interfaces
export interface RevenueStreamCreate {
  stream_type: RevenueStreamType;
  name: string;
  start_date: string;
  end_date?: string | null;
  amount: number;
  period?: Period;
  tax_rate?: number;
  growth_rate?: number;
  asset_id?: number | null;
  config_json?: Record<string, unknown>;
}

export interface RevenueStreamUpdate {
  name?: string;
  end_date?: string | null;
  amount?: number;
  tax_rate?: number;
  growth_rate?: number;
  config_json?: Record<string, unknown>;
}

export interface RevenueStreamResponse {
  id: number;
  stream_type: RevenueStreamType;
  name: string;
  start_date: string;
  end_date: string | null;
  amount: number;
  period: Period;
  tax_rate: number;
  growth_rate: number;
  asset_id: number | null;
  config_json: Record<string, unknown>;
  user_id: number;
  created_at: string;
}

// Cash Flow interfaces
export const CashFlowType = {
  DEPOSIT: 'deposit',
  WITHDRAWAL: 'withdrawal',
} as const;
export type CashFlowType = (typeof CashFlowType)[keyof typeof CashFlowType];

export interface CashFlowResponse {
  id: number;
  user_id: number;
  flow_type: CashFlowType;
  target_asset_id: number | null;
  name: string;
  amount: number;
  from_date: string;
  to_date: string;
  from_own_capital: boolean;
  created_at: string;
}

// Projection interfaces
export interface ProjectionRequest {
  start_date?: string;
  end_date?: string;
  as_of_date?: string;
  include_scenarios?: boolean;
  scenario_ids?: number[];
}

export interface TimeSeriesDataPoint {
  date: string;
  value: number;
}

export interface MeasurementMarker {
  date: string;
  actual_value: number;
  entity_type: 'asset' | 'loan';
  entity_id: number;
  entity_name: string;
}

export interface AssetProjection {
  asset_id: number;
  asset_name: string;
  asset_type: AssetType;
  time_series: TimeSeriesDataPoint[];
  measurements: MeasurementMarker[];
}

export interface LoanProjection {
  loan_id: number;
  loan_name: string;
  loan_type: LoanType;
  balance_series: TimeSeriesDataPoint[];
  payment_series: TimeSeriesDataPoint[];
  measurements: MeasurementMarker[];
}

export interface CashFlowItem {
  source_name: string;
  source_type: 'income' | 'expense';
  category: string; // salary, rent, dividend, pension, loan_payment, deposit, withdrawal
  time_series: TimeSeriesDataPoint[];
  entity_id: number | null;
  entity_type: 'asset' | 'loan' | null;
}

export interface CashFlowBreakdown {
  items: CashFlowItem[];
  total_income_series: TimeSeriesDataPoint[];
  total_expense_series: TimeSeriesDataPoint[];
  net_series: TimeSeriesDataPoint[];
}

export interface ProjectionResponse {
  user_id: number;
  start_date: string;
  end_date: string;
  net_worth_series: TimeSeriesDataPoint[];
  total_assets_series: TimeSeriesDataPoint[];
  total_liabilities_series: TimeSeriesDataPoint[];
  monthly_cash_flow_series: TimeSeriesDataPoint[];
  cash_flow_breakdown?: CashFlowBreakdown | null;
  asset_projections: AssetProjection[];
  loan_projections: LoanProjection[];
  measurement_markers: MeasurementMarker[];
  is_historical: boolean;
  historical_as_of_date?: string | null;
  computed_at: string;
}

export interface PortfolioSummary {
  user_id: number;
  total_assets: number;
  total_liabilities: number;
  net_worth: number;
  monthly_revenue: number;
  monthly_loan_payments: number;
  monthly_net_cash_flow: number;
  asset_count: number;
  loan_count: number;
  revenue_stream_count: number;
  as_of_date: string;
}

// Historical Measurement interfaces
export interface HistoricalMeasurementCreate {
  entity_type: 'asset' | 'loan';
  entity_id: number;
  measurement_date: string; // ISO date
  actual_value: number;
  rate_at_time?: number | null;
  notes?: string | null;
  source?: 'manual' | 'import' | 'auto';
}

export interface HistoricalMeasurementUpdate {
  measurement_date?: string;
  actual_value?: number;
  rate_at_time?: number | null;
  notes?: string | null;
  source?: 'manual' | 'import' | 'auto';
}

export interface HistoricalMeasurementResponse {
  id: number;
  user_id: number;
  entity_type: 'asset' | 'loan';
  entity_id: number;
  measurement_date: string;
  actual_value: number;
  rate_at_time: number | null;
  notes: string | null;
  source: string;
  recorded_at: string;
}

// Scenario types
export const ScenarioActionType = {
  PARAM_CHANGE: 'param_change',
  NEW_ASSET: 'new_asset',
  NEW_LOAN: 'new_loan',
  REPAY_LOAN: 'repay_loan',
  TRANSFORM_ASSET: 'transform_asset',
  WITHDRAW_FROM_ASSET: 'withdraw_from_asset',
  DEPOSIT_TO_ASSET: 'deposit_to_asset',
  MARKET_CRASH: 'market_crash',
  ADD_REVENUE_STREAM: 'add_revenue_stream',
} as const;
export type ScenarioActionType = (typeof ScenarioActionType)[keyof typeof ScenarioActionType];

export interface ScenarioAction {
  type: ScenarioActionType;
  target_type?: string | null;
  target_id?: number | null;
  field?: string | null;
  value?: unknown;
  changes?: Record<string, unknown> | null;
  params?: Record<string, unknown> | null;
  crash_pct?: number | null;
  crash_date?: string | null;
  affected_asset_types?: string[] | null;
  amount?: number | null;
  action_date?: string | null;
}

export interface ScenarioCreate {
  name: string;
  description?: string | null;
  actions: ScenarioAction[];
}

export interface ScenarioUpdate {
  name?: string;
  description?: string | null;
  actions?: ScenarioAction[];
  is_active?: boolean;
}

export interface ScenarioResponse {
  id: number;
  user_id: number;
  name: string;
  description: string | null;
  actions: ScenarioAction[];
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string;
  type?: string;
}
