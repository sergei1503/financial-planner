# ADR 0003: Integrate operating cash flow into the net-worth projection

- **Status:** SUPERSEDED — premise was incorrect (see "Correction" below). Not implemented.
- **Date:** 2026-07-16
- **Deciders:** Owner (Sergei) — chose "full integration" + "ADR first" during the expenditures design session
- **Related:** PRD `docs/prd.md`, Architecture `docs/architecture.md`, ADR-0002 (golden-master rule), Plan `docs/plan.md`, Standards `docs/standards.md#golden-master-rule`

## Correction (2026-07-16, after prototyping)

This ADR assumed the cash-flow view is **decoupled** from the net-worth line — that expenses
don't erode net worth. **That premise is wrong.** `compute_projection` already appends a
virtual **"accumulated cash" (מזומנים מצטברים)** asset = `cumsum(cash_flow_breakdown.net_series)`
and adds it to net worth (projections.py ~1204-1248). Empirically, on the current engine:
salary raises net worth +₪10k/mo, a standalone expense lowers it, and loan payments lower it.
**Operating cash flow is already integrated.**

The prototype sweep this ADR proposed therefore **double-counted** (salary showed +₪20k/mo) and
was reverted. But prototyping surfaced the **actual** defect: asset-attached flows are counted
**twice** in net worth — once in the real cash asset (`_apply_cash_conversions` folds rent/
dividends/pension/own-capital deposits into the cash `CASH_FLOW`) and again in the accumulated-
cash virtual asset (they're also in `net_series`). Verified: ₪5,000/mo rent → **+₪10,000/mo**
net worth. This overstates portfolio 1 (rental income + pension) today and is frozen into the
golden fixture.

**The real fix** (candidate for a fresh ADR-0004): make the two integration mechanisms
non-overlapping — the accumulated-cash asset should integrate only flows **not already in the
real cash asset** (loan payments + standalone revenue + standalone cash flows), excluding
asset-attached income and own-capital deposits. This is a golden-master correctness change that
**lowers** projected net-worth growth wherever there's rental/pension income → needs owner
sign-off + a witnessed golden re-baseline. Gap A (escalating cash flows) is unaffected and stands.

---

_Original proposal below is retained for the decision trail; its premise is void._

## Context

The projection has **two views that are only partially connected**:

1. **Net-worth line** = `Σ assets − Σ liabilities`. The cash asset is a running balance that
   `_apply_cash_conversions` (`api/routes/projections.py`) grows/shrinks from: asset purchases
   (−cost), sales (+proceeds), and **every non-cash asset's `CASH_FLOW` column**.
2. **Cash-flow breakdown** (income / expense / net chart).

Because asset models fold their revenue into `CASH_FLOW` (e.g. `RealEstateAsset.get_projection`
merges rent at `asset.py:635-644`; `StockAsset` dividends; `PensionAsset` payouts & deposits),
**asset-attached income and own-capital asset deposits already accumulate into cash / net worth.**
But three flow sources are computed only for the breakdown and **never touch the cash balance**,
so they are invisible to the net-worth line:

- **Standalone revenue streams** (`_project_standalone_revenue_streams`) — e.g. salary.
- **Standalone cash flows** (`_project_standalone_cash_flows`) — general expenses/income not
  linked to an asset (the household's rent-paid, kindergarten, ongoing expenses; now escalatable
  via ADR follow-on / `growth_mode`).
- **Loan payments** — the loan `CASH_FLOW` series is aggregated for display only; the liability
  amortizes independently, so **paying down a loan currently raises net worth for free** (the
  liability shrinks but no cash leaves).

Consequence: a growing rent expense, a salary, or a mortgage payment bends the cash-flow chart
but leaves the 30-year net-worth line unchanged — which defeats the point of a planner whose
core question is "does living above/below my means grow or erode my wealth?"

## Decision

Make the projection **fully integrated**: each month, the **operating cash flow that is not
already reflected in the cash balance** accumulates into the liquid-savings (cash) asset. This
extends the mechanism `_apply_cash_conversions` already uses for asset-attached flows to the
three display-only sources, so all money movements are treated consistently.

**The monthly amount swept into cash** =
`+ standalone revenue (income)  + standalone cash-flow income  − standalone cash-flow expense  − loan payments`

Sources already applied to cash (**must NOT be swept again** — enumerated to prevent
double-counting): asset purchases/sales, own-capital asset deposits, asset-attached rent,
dividends, and pension deposits/payouts.

### Why this is coherent (the accounting invariant)

After the change, the month-over-month change in net worth is exactly:

```
Δ net worth = asset appreciation (net of fees)
            − loan interest
            + (income − living expenses)
```

The loan case is the elegant part and needs no principal/interest split: sweeping the **full**
payment out of cash while the loan df **independently** amortizes the liability yields
`Δ = (−payment) − (−principal) = −interest` automatically. Own-capital asset deposits stay
net-worth-neutral (−cash already applied, +asset value), as today.

### Design (implementation shape, for the sign-off — not final code)

1. Compute the deterministic month grid and the three display-only series **before** the cash
   asset is finalized (today they are computed later, only for the breakdown). Reuse the exact
   same computed items for the breakdown so the chart and the net-worth line are guaranteed to
   agree.
2. Fold their signed monthly net into the cash asset's running balance — in / right after
   `_apply_cash_conversions`, and **before** `_apply_measurement_shifts`, so a recorded actual
   cash/savings measurement re-anchors the integrated series (consistent with the
   measurement-anchored philosophy: recorded truth overrides, projection continues from there).
3. The sink is the portfolio's cash asset. If a portfolio has no cash asset, synthesize a
   liquid-savings sink (the codebase already has an "accumulated cash" virtual-asset concept).
4. **v1 scope choices** (see "Open sub-decisions"): surplus sits as cash (no auto-invest);
   cash may go negative (a projected deficit is shown, not clamped).

### Open sub-decisions (confirm at sign-off)

- **Surplus destination:** accumulate as cash at the cash asset's own rate (~0%). *(Recommended
  for v1; "auto-invest surplus into a chosen asset at its return" is a clean future extension.)*
- **Negative cash:** allow the cash balance to go negative when expenses exceed income+savings
  (honest deficit) rather than clamping at 0. *(Recommended — clamping hides the problem.)*
- **Loan payments cost cash:** yes (this is the point). Confirms that historical/",already-paid"
  loans and future loans both draw cash over their term.

## Alternatives considered

- **Partial integration (sweep expenses/standalone only, leave loan payments free)** — rejected:
  leaves loans under-costed; net worth still overstated for anyone with a mortgage. Not coherent.
- **Sweep the breakdown's `net_series` wholesale into cash** — rejected: double-counts every
  asset-attached flow already in cash (rent, dividends, pension, own-capital deposits). The
  source-scoped sweep above is the same idea done without double-counting.
- **Leave it decoupled; add expenses to the chart only** — rejected by the owner: the whole
  goal is for expenditures (and income) to move the 30-year wealth line.
- **Split each loan payment into principal/interest and only expense the interest** — rejected as
  needless: the full-payment sweep + independent amortization already nets to −interest.

## Consequences

- **Positive:** the net-worth line finally responds to the household's monthly surplus/deficit;
  salary builds savings, expenses erode them, mortgages cost real money. The chart and the
  net-worth line are computed from one set of series, so they can't disagree.
- **Negative / trade-offs:** this **intentionally changes projected values** → a **full golden
  re-baseline** for portfolio 1 (per `docs/standards.md`), and the synthetic golden fixture is
  re-frozen with new numbers. Requires reordering part of `compute_projection` (compute the three
  series up front). Reviewer must confirm no double-count against `_apply_cash_conversions`.
- **Migration/deploy:** engine-only; no schema change. Local-first; Neon/Vercel deploy stays
  manual and owner-gated.

## Verification strategy

- **Invariant unit tests** (no DB, `test_models_basic` style), each isolating one mechanism:
  - salary-only + flat expense ⇒ `net_worth(t) = initial + t·(salary − expense)`;
  - loan-only ⇒ `Δ net worth per month = −interest_that_month` (and total = −Σinterest);
  - own-capital asset deposit ⇒ net worth unchanged beyond the asset's own growth (no double-count);
  - asset-attached rent ⇒ unchanged vs. today (already in cash);
  - deficit ⇒ cash goes negative, not clamped.
- **Golden:** re-baseline `fixtures/projection_golden.json`; the diff is reviewed and must move
  **only** by the three newly-integrated sources (a witnessed, explained re-baseline, not a blind
  overwrite).
- **End-to-end:** portfolio 1 recompute — sanity-check the new net-worth trajectory against the
  known salary/expense/loan set; confirm cold-recompute perf stays within ADR-0002's budget.

## Follow-ups

- `cpi` growth mode for cash flows (grow with inflation via the existing `IndexTracker`).
- Optional "auto-invest monthly surplus into asset X at its return" once v1 lands.
- Revisit whether asset-attached revenue should also be surfaced as a togglable savings vs.
  spend flow (currently always accumulates).
