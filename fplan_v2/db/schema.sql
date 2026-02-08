-- FPlan v2 PostgreSQL Schema for Neon Serverless Deployment
-- ============================================================
--
-- This schema is designed for:
-- - Neon serverless PostgreSQL (connection pooling via PgBouncer)
-- - Vercel serverless functions (10-second timeout)
-- - Multi-user support (future-ready)
-- - Historical tracking and audit trails
--
-- Key PostgreSQL Features:
-- - SERIAL for auto-increment primary keys
-- - TIMESTAMP WITH TIME ZONE for dates
-- - JSONB for flexible configuration storage
-- - Proper indexing for query performance
-- - Foreign key constraints for referential integrity

-- ======================
-- Core Tables
-- ======================

-- Users & Settings
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    email TEXT UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    settings JSONB DEFAULT '{}'::jsonb,  -- {locale: "he"/"en", currency: "ILS", preferences: {...}}
    is_active BOOLEAN DEFAULT true
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_is_active ON users(is_active);

-- Assets
CREATE TABLE assets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,  -- User-facing ID like "house", "hishtalmut"
    asset_type TEXT NOT NULL,   -- 'real_estate', 'stock', 'pension', 'cash'
    name TEXT NOT NULL,
    start_date DATE NOT NULL,   -- Always 1st of month (enforced in app layer)
    original_value NUMERIC(15, 2) NOT NULL,
    current_value NUMERIC(15, 2),
    appreciation_rate_annual_pct NUMERIC(5, 2) DEFAULT 0,
    yearly_fee_pct NUMERIC(5, 2) DEFAULT 0,
    sell_date DATE,
    sell_tax NUMERIC(5, 2) DEFAULT 0,
    currency TEXT DEFAULT 'ILS',
    config_json JSONB DEFAULT '{}'::jsonb,  -- Additional config (revenue_stream details, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, external_id),
    CHECK (asset_type IN ('real_estate', 'stock', 'pension', 'cash'))
);

CREATE INDEX idx_assets_user_id ON assets(user_id);
CREATE INDEX idx_assets_external_id ON assets(user_id, external_id);
CREATE INDEX idx_assets_type ON assets(asset_type);
CREATE INDEX idx_assets_start_date ON assets(start_date);
CREATE INDEX idx_assets_config_json ON assets USING GIN(config_json);  -- For JSONB queries

-- Loans
CREATE TABLE loans (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    external_id TEXT NOT NULL,
    loan_type TEXT NOT NULL,    -- 'fixed', 'prime_pegged', 'cpi_pegged', 'variable'
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    original_value NUMERIC(15, 2) NOT NULL,
    current_balance NUMERIC(15, 2),
    interest_rate_annual_pct NUMERIC(5, 2) NOT NULL,
    duration_months INTEGER NOT NULL,
    collateral_asset_id INTEGER REFERENCES assets(id) ON DELETE SET NULL,
    config_json JSONB DEFAULT '{}'::jsonb,  -- Loan-specific config (margin, expected_cpi, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, external_id),
    CHECK (loan_type IN ('fixed', 'prime_pegged', 'cpi_pegged', 'variable')),
    CHECK (duration_months > 0)
);

CREATE INDEX idx_loans_user_id ON loans(user_id);
CREATE INDEX idx_loans_external_id ON loans(user_id, external_id);
CREATE INDEX idx_loans_type ON loans(loan_type);
CREATE INDEX idx_loans_collateral ON loans(collateral_asset_id);
CREATE INDEX idx_loans_config_json ON loans USING GIN(config_json);

-- Revenue Streams (rent, dividends, pension payouts, salary)
CREATE TABLE revenue_streams (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,  -- NULL for standalone salary
    stream_type TEXT NOT NULL,  -- 'rent', 'dividend', 'pension', 'salary'
    name TEXT NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    amount NUMERIC(15, 2) NOT NULL,
    period TEXT DEFAULT 'monthly',  -- 'monthly', 'quarterly', 'yearly'
    tax_rate NUMERIC(5, 2) DEFAULT 0,
    growth_rate NUMERIC(5, 2) DEFAULT 0,
    config_json JSONB DEFAULT '{}'::jsonb,  -- Additional config (dividend_yield, payout_frequency, etc.)
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (stream_type IN ('rent', 'dividend', 'pension', 'salary')),
    CHECK (period IN ('monthly', 'quarterly', 'yearly'))
);

CREATE INDEX idx_revenue_streams_user_id ON revenue_streams(user_id);
CREATE INDEX idx_revenue_streams_asset_id ON revenue_streams(asset_id);
CREATE INDEX idx_revenue_streams_type ON revenue_streams(stream_type);
CREATE INDEX idx_revenue_streams_dates ON revenue_streams(start_date, end_date);

-- Cash Flows (deposits and withdrawals)
CREATE TABLE cash_flows (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    flow_type TEXT NOT NULL,    -- 'deposit' or 'withdrawal'
    target_asset_id INTEGER REFERENCES assets(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    amount NUMERIC(15, 2) NOT NULL,
    from_date DATE NOT NULL,
    to_date DATE NOT NULL,
    from_own_capital BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (flow_type IN ('deposit', 'withdrawal')),
    CHECK (from_date <= to_date)
);

CREATE INDEX idx_cash_flows_user_id ON cash_flows(user_id);
CREATE INDEX idx_cash_flows_asset_id ON cash_flows(target_asset_id);
CREATE INDEX idx_cash_flows_type ON cash_flows(flow_type);
CREATE INDEX idx_cash_flows_dates ON cash_flows(from_date, to_date);

-- ======================
-- Historical Tracking
-- ======================

-- Historical Measurements (actual values vs projections)
CREATE TABLE historical_measurements (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,      -- 'asset' or 'loan'
    entity_id INTEGER NOT NULL,
    measurement_date DATE NOT NULL, -- Always 1st of month
    actual_value NUMERIC(15, 2) NOT NULL,
    rate_at_time NUMERIC(5, 2),     -- Rate when measurement was taken
    notes TEXT,
    source TEXT DEFAULT 'manual',   -- 'manual', 'import', 'auto'
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(entity_type, entity_id, measurement_date),
    CHECK (entity_type IN ('asset', 'loan')),
    CHECK (source IN ('manual', 'import', 'auto'))
);

CREATE INDEX idx_measurements_user_id ON historical_measurements(user_id);
CREATE INDEX idx_measurements_entity ON historical_measurements(entity_type, entity_id);
CREATE INDEX idx_measurements_date ON historical_measurements(measurement_date);
CREATE INDEX idx_measurements_recorded_at ON historical_measurements(recorded_at);

-- ======================
-- Audit Trail
-- ======================

-- Operations Log (all mutations tracked)
CREATE TABLE operations_log (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    operation_type TEXT NOT NULL,  -- 'add_asset', 'modify_loan', 'repay_loan', etc.
    entity_type TEXT,              -- 'asset', 'loan', 'revenue_stream', 'scenario', NULL
    entity_id INTEGER,
    parameters JSONB NOT NULL,     -- Full action parameters as JSON
    description TEXT,
    source TEXT DEFAULT 'ui',      -- 'ui', 'nlp', 'import', 'api', 'scenario'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (source IN ('ui', 'nlp', 'import', 'api', 'scenario'))
);

CREATE INDEX idx_operations_log_user_id ON operations_log(user_id);
CREATE INDEX idx_operations_log_type ON operations_log(operation_type);
CREATE INDEX idx_operations_log_entity ON operations_log(entity_type, entity_id);
CREATE INDEX idx_operations_log_created_at ON operations_log(created_at DESC);
CREATE INDEX idx_operations_log_parameters ON operations_log USING GIN(parameters);

-- ======================
-- Index Data (Prime & CPI)
-- ======================

-- Index Data (economic indicators)
CREATE TABLE index_data (
    id SERIAL PRIMARY KEY,
    index_type TEXT NOT NULL,      -- 'prime', 'cpi'
    date DATE NOT NULL,             -- 1st of month
    value NUMERIC(10, 4) NOT NULL,
    change NUMERIC(10, 4),
    change_percent NUMERIC(10, 4),
    source_url TEXT,
    fetched_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(index_type, date),
    CHECK (index_type IN ('prime', 'cpi'))
);

CREATE INDEX idx_index_data_type ON index_data(index_type);
CREATE INDEX idx_index_data_date ON index_data(date DESC);
CREATE INDEX idx_index_data_fetched_at ON index_data(fetched_at);

-- Index Notifications (alert users to changes)
CREATE TABLE index_notifications (
    id SERIAL PRIMARY KEY,
    index_type TEXT NOT NULL,
    change_date DATE NOT NULL,
    old_value NUMERIC(10, 4),
    new_value NUMERIC(10, 4),
    change_percent NUMERIC(10, 4),
    acknowledged BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CHECK (index_type IN ('prime', 'cpi'))
);

CREATE INDEX idx_index_notifications_type ON index_notifications(index_type);
CREATE INDEX idx_index_notifications_acknowledged ON index_notifications(acknowledged);
CREATE INDEX idx_index_notifications_created_at ON index_notifications(created_at DESC);

-- ======================
-- Scenarios
-- ======================

-- Scenarios (what-if analysis)
CREATE TABLE scenarios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    version INTEGER NOT NULL DEFAULT 1,
    parent_version INTEGER,        -- For scenario branching
    actions_json JSONB NOT NULL,   -- Array of action objects
    is_active BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, name, version),
    CHECK (version > 0)
);

CREATE INDEX idx_scenarios_user_id ON scenarios(user_id);
CREATE INDEX idx_scenarios_name ON scenarios(user_id, name);
CREATE INDEX idx_scenarios_active ON scenarios(is_active);
CREATE INDEX idx_scenarios_actions ON scenarios USING GIN(actions_json);

-- Scenario Results (cached analysis outputs)
CREATE TABLE scenario_results (
    id SERIAL PRIMARY KEY,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    result_type TEXT NOT NULL,     -- 'net_worth', 'cash_flow', 'asset_projection', etc.
    result_data JSONB NOT NULL,    -- Serialized DataFrame as JSON
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    config_hash TEXT,              -- For cache invalidation
    CHECK (result_type IN ('net_worth', 'cash_flow', 'asset_projection', 'loan_schedule'))
);

CREATE INDEX idx_scenario_results_scenario_id ON scenario_results(scenario_id);
CREATE INDEX idx_scenario_results_type ON scenario_results(result_type);
CREATE INDEX idx_scenario_results_computed_at ON scenario_results(computed_at DESC);
CREATE INDEX idx_scenario_results_hash ON scenario_results(config_hash);

-- ======================
-- Updated At Trigger
-- ======================

-- Function to automatically update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Apply trigger to relevant tables
CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_assets_updated_at BEFORE UPDATE ON assets
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_loans_updated_at BEFORE UPDATE ON loans
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_scenarios_updated_at BEFORE UPDATE ON scenarios
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ======================
-- Views for Common Queries
-- ======================

-- View: User Portfolio Summary
CREATE VIEW user_portfolio_summary AS
SELECT
    u.id AS user_id,
    u.name,
    COUNT(DISTINCT a.id) AS total_assets,
    COUNT(DISTINCT l.id) AS total_loans,
    SUM(a.current_value) AS total_asset_value,
    SUM(l.current_balance) AS total_loan_balance,
    SUM(a.current_value) - COALESCE(SUM(l.current_balance), 0) AS net_worth
FROM users u
LEFT JOIN assets a ON u.id = a.user_id
LEFT JOIN loans l ON u.id = l.user_id
GROUP BY u.id, u.name;

-- View: Active Revenue Streams
CREATE VIEW active_revenue_streams AS
SELECT
    rs.id,
    rs.user_id,
    rs.stream_type,
    rs.name,
    rs.amount,
    rs.period,
    a.name AS asset_name
FROM revenue_streams rs
LEFT JOIN assets a ON rs.asset_id = a.id
WHERE rs.end_date IS NULL OR rs.end_date >= CURRENT_DATE;

-- ======================
-- Initial Data
-- ======================

-- Default user for migration from v1 (single-user mode)
INSERT INTO users (id, name, email, settings) VALUES
(1, 'Default User', NULL, '{"locale": "he", "currency": "ILS"}'::jsonb);

-- Reset sequence to start at 2 for future users
SELECT setval('users_id_seq', 1);

-- ======================
-- Comments for Documentation
-- ======================

COMMENT ON TABLE users IS 'User accounts and preferences';
COMMENT ON TABLE assets IS 'User assets (real estate, stocks, pension, cash)';
COMMENT ON TABLE loans IS 'User loans with various interest rate models';
COMMENT ON TABLE revenue_streams IS 'Income streams from assets or standalone (salary)';
COMMENT ON TABLE cash_flows IS 'Deposits and withdrawals over time';
COMMENT ON TABLE historical_measurements IS 'Actual historical values for tracking vs projections';
COMMENT ON TABLE operations_log IS 'Audit trail of all portfolio changes';
COMMENT ON TABLE index_data IS 'Economic indicators (Prime interest rate, CPI)';
COMMENT ON TABLE index_notifications IS 'Alerts for significant index changes';
COMMENT ON TABLE scenarios IS 'What-if scenarios for financial planning';
COMMENT ON TABLE scenario_results IS 'Cached scenario analysis results';

COMMENT ON COLUMN assets.external_id IS 'User-facing identifier (e.g., "house", "pension")';
COMMENT ON COLUMN assets.config_json IS 'Additional configuration specific to asset type';
COMMENT ON COLUMN loans.config_json IS 'Loan-specific parameters (margin, expected_cpi, etc.)';
COMMENT ON COLUMN historical_measurements.entity_type IS 'Type of entity being measured';
COMMENT ON COLUMN operations_log.parameters IS 'Full action parameters as JSONB';
COMMENT ON COLUMN scenarios.actions_json IS 'Array of action objects defining the scenario';
COMMENT ON COLUMN scenario_results.config_hash IS 'Hash for cache invalidation';
