-- Migration: Add scenario_cache table for caching scenario simulation results
-- Created: 2026-02-11
-- Purpose: Improve scenario re-run performance from 3000ms to <100ms

CREATE TABLE IF NOT EXISTS scenario_cache (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    scenario_id INTEGER NOT NULL REFERENCES scenarios(id) ON DELETE CASCADE,
    cache_key TEXT NOT NULL,
    result_json JSONB NOT NULL,
    computed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT uq_scenario_cache_scenario_key UNIQUE (scenario_id, cache_key)
);

CREATE INDEX IF NOT EXISTS idx_scenario_cache_user ON scenario_cache(user_id);
CREATE INDEX IF NOT EXISTS idx_scenario_cache_scenario ON scenario_cache(scenario_id);

COMMENT ON TABLE scenario_cache IS 'Caches scenario simulation results keyed by portfolio_version, scenario_id, and date range';
COMMENT ON COLUMN scenario_cache.cache_key IS 'SHA-256 hash of portfolio_version:scenario_id:start_date:end_date';
COMMENT ON COLUMN scenario_cache.result_json IS 'Full ProjectionResponse as JSON';
