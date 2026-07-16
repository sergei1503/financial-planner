-- 005_cash_flow_growth.sql
-- Give cash_flows the same escalation vocabulary revenue_streams already has, so an
-- expenditure (e.g. "rent we pay") can grow over time instead of staying flat.
--   growth_mode = 'none'    -> flat amount (today's behavior; the default)
--               = 'smooth'  -> amount * (1 + growth_rate/100)^years, compounded monthly
--               = 'stepped' -> same but steps once per year on the anniversary (flat within
--                              each year), matching the stepped-lease model on rent income.
-- Backward-compatible: existing rows default to growth_mode='none' / growth_rate=0, so the
-- projection is byte-identical until a growth mode is chosen.
-- Idempotent: safe to run more than once.

BEGIN;

ALTER TABLE cash_flows ADD COLUMN IF NOT EXISTS growth_rate NUMERIC(5, 2) DEFAULT 0;
ALTER TABLE cash_flows ADD COLUMN IF NOT EXISTS growth_mode TEXT DEFAULT 'none';

-- Backfill any pre-existing NULLs (shouldn't occur given the DEFAULTs, but be safe).
UPDATE cash_flows SET growth_rate = 0 WHERE growth_rate IS NULL;
UPDATE cash_flows SET growth_mode = 'none' WHERE growth_mode IS NULL;

ALTER TABLE cash_flows DROP CONSTRAINT IF EXISTS ck_cash_flow_growth_mode;
ALTER TABLE cash_flows ADD  CONSTRAINT ck_cash_flow_growth_mode
    CHECK (growth_mode IN ('none', 'smooth', 'stepped'));

COMMIT;
