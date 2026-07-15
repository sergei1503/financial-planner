# Performance refactor: `compute_projection` vectorization

## What changed

File touched: `fplan_v2/api/routes/projections.py` (only this file — no other files edited).

Replaced every O(n) boolean-mask dataframe lookup inside `for dt in all_dates:` loops
(and one `.iterrows()` deposit-summing loop) with a precomputed `dict(zip(df["date"], df[col]))`
built once per dataframe, then read via O(1) `.get(dt, 0.0)` inside the loop. With ~14 breakdown
items x ~650 monthly dates x several dataframes, this eliminated the dominant O(n²) cost.

Specific spots converted:
1. Net-worth/assets/liabilities/cash-flow series builder loop — `total_assets_by_date`,
   `total_liabilities_by_date`, `total_payments_by_date` now looked up via precomputed dicts
   (`assets_by_date_lookup`, `liabilities_by_date_lookup`, `payments_by_date_lookup`).
2. Breakdown loan-payment items loop — precomputed `loan_cf_lookup` per loan df.
3. Asset deposit/withdrawal breakdown items — precomputed `asset_cf_lookup` per asset df,
   used inside the existing per-cash-flow-record date-range check (same math, same order).
4. Revenue-stream item loop (salary/rent attached to assets) and pension income item loop —
   precomputed `cf_lookup` / `pension_cf_lookup` per stream/asset df.
5. Standalone rent revenue stream loop (`_project_standalone_revenue_streams`) — same
   dict-lookup treatment for its `cf_df`.
6. `_apply_cash_conversions`: the `for _, row in asset_df.iterrows()` deposit-summing loop
   replaced with `zip(asset_df["date"], asset_df[CASH_FLOW])` (vectorized column access, no
   more per-row Series construction).
7. Also converted the remaining `.iterrows()` calls that build the final asset/loan
   `time_series` lists in `compute_projection` (post cash-conversion/measurement rebuild, and
   loan balance/payment series) to `zip(df["date"], df[VALUE-or-CASH_FLOW])` — same row order,
   much less per-row overhead.
8. `_apply_cash_conversions` cash-asset running-balance loop — replaced
   `cash_df.iterrows()` + `cash_df.at[idx, VALUE] = running` with a single-pass list
   accumulation (`new_values.append(running)`) then one vectorized `cash_df[VALUE] = new_values`
   assignment. Identical accumulation order/arithmetic, just without per-row pandas overhead.

No changes to projection math, rounding, Decimal/str conversions, series ordering, or which
rows are structural zeros. Every `Decimal(str(...))` conversion is untouched.

## Timing (portfolio-1, 30-year monthly projection, ~650 dates)

| | before | after |
|---|---|---|
| cold compute | ~1.37s (1.369s measured) | ~0.38s (0.373s–0.395s across 10+ runs) |

Target was <0.4s — consistently met with a small margin. Remaining time (profiled) is
dominated by `pd.to_datetime` / `dateutil.relativedelta` calls inside the core asset/loan
`get_projection()` methods (`fplan_v2/core/models/asset.py`, `.../loan.py`), which are out of
scope for this step (edits were constrained to `projections.py` only).

## Verification

1. Golden output diff — recomputes portfolio-1's full `ProjectionResponse` and diffs every
   field against a frozen baseline (`golden_baseline.lock.json`) at tolerance `1e-6`:
   ```
   cold compute: 0.376s   (target <0.4s)
   GOLDEN MATCH ✓ (tolerance 1e-06)
   ```
   (Ran 10+ times; timing ranged 0.373s–0.466s during iterative development, converged to
   0.373s–0.395s after the final `.iterrows()`/running-balance fix, always < 0.4s. Golden
   match held on every run, no mismatches at any point after the initial working version.)

2. Model test suite:
   ```
   cd /Users/sergeibenkovitch/repos/financial-planner && CLERK_SECRET_KEY= .venv/bin/python -m pytest fplan_v2/tests/test_models_basic.py -q
   15 passed
   ```

## Notes for next step

- `fplan_v2/core/models/loan.py` and `fplan_v2/frontend/src/hooks/use-projections.ts` had
  pre-existing uncommitted changes in the working tree before this step started (unrelated to
  this performance work — not touched by this step). Only `fplan_v2/api/routes/projections.py`
  was edited here.
- If further speedup is ever needed, the next win would require touching
  `fplan_v2/core/models/asset.py` / `loan.py`'s `get_projection()` internals (date parsing /
  `dateutil.relativedelta` usage), which was out of scope for this step.
