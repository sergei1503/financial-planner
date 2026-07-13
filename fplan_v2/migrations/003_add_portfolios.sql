-- 003_add_portfolios.sql
-- Introduce first-class portfolios. A user owns one or more portfolios; assets, loans,
-- revenue streams, cash flows, historical measurements and scenarios belong to a portfolio.
-- Backfills one default portfolio per existing user and assigns all their rows to it.
-- Idempotent: safe to run more than once.

BEGIN;

CREATE TABLE IF NOT EXISTS portfolios (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    is_default BOOLEAN NOT NULL DEFAULT FALSE,
    portfolio_version INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_portfolios_user_id ON portfolios(user_id);

ALTER TABLE assets                  ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;
ALTER TABLE loans                   ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;
ALTER TABLE revenue_streams         ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;
ALTER TABLE cash_flows              ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;
ALTER TABLE historical_measurements ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;
ALTER TABLE scenarios               ADD COLUMN IF NOT EXISTS portfolio_id INTEGER REFERENCES portfolios(id) ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_assets_portfolio_id                  ON assets(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_loans_portfolio_id                   ON loans(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_revenue_streams_portfolio_id         ON revenue_streams(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_cash_flows_portfolio_id              ON cash_flows(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_historical_measurements_portfolio_id ON historical_measurements(portfolio_id);
CREATE INDEX IF NOT EXISTS idx_scenarios_portfolio_id               ON scenarios(portfolio_id);

-- One default portfolio per user (only if the user has none yet)
INSERT INTO portfolios (user_id, name, is_default)
SELECT u.id, 'My Portfolio', TRUE
FROM users u
WHERE NOT EXISTS (SELECT 1 FROM portfolios p WHERE p.user_id = u.id);

-- Backfill portfolio_id on all existing rows -> the owner's default portfolio
UPDATE assets a                  SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = a.user_id AND p.is_default AND a.portfolio_id IS NULL;
UPDATE loans l                   SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = l.user_id AND p.is_default AND l.portfolio_id IS NULL;
UPDATE revenue_streams r         SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = r.user_id AND p.is_default AND r.portfolio_id IS NULL;
UPDATE cash_flows c              SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = c.user_id AND p.is_default AND c.portfolio_id IS NULL;
UPDATE historical_measurements h SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = h.user_id AND p.is_default AND h.portfolio_id IS NULL;
UPDATE scenarios s               SET portfolio_id = p.id FROM portfolios p WHERE p.user_id = s.user_id AND p.is_default AND s.portfolio_id IS NULL;

COMMIT;
