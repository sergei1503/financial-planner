-- 004_portfolio_scoped_unique.sql
-- external_id must be unique per PORTFOLIO, not per user — otherwise a user can't hold the
-- same external_id (e.g. "house") in two portfolios, which blocks importing a copy.
-- Idempotent.

BEGIN;

-- Drop the old (user_id, external_id) uniqueness (both the auto-named and any explicit name).
ALTER TABLE assets DROP CONSTRAINT IF EXISTS assets_user_id_external_id_key;
ALTER TABLE assets DROP CONSTRAINT IF EXISTS uq_asset_user_external_id;
ALTER TABLE loans  DROP CONSTRAINT IF EXISTS loans_user_id_external_id_key;
ALTER TABLE loans  DROP CONSTRAINT IF EXISTS uq_loan_user_external_id;

-- Add portfolio-scoped uniqueness (NULL portfolio_id rows are treated as distinct, which is
-- fine — every real row carries a portfolio_id).
ALTER TABLE assets DROP CONSTRAINT IF EXISTS uq_asset_portfolio_external_id;
ALTER TABLE assets ADD  CONSTRAINT uq_asset_portfolio_external_id UNIQUE (portfolio_id, external_id);
ALTER TABLE loans  DROP CONSTRAINT IF EXISTS uq_loan_portfolio_external_id;
ALTER TABLE loans  ADD  CONSTRAINT uq_loan_portfolio_external_id UNIQUE (portfolio_id, external_id);

COMMIT;
