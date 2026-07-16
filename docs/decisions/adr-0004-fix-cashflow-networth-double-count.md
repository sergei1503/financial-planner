# ADR 0004: Fix the operating-cash-flow double-count in net worth

- **Status:** accepted (implemented 2026-07-17, branch `feat/cashflow-growth`; golden re-baselined; portfolio 1 30-yr net worth −18.6%)
- **Date:** 2026-07-16
- **Deciders:** Owner (Sergei) — chose "fix the double-count (ADR-0004)" after ADR-0003's premise was found wrong
- **Related:** ADR-0003 (superseded — the premise correction that surfaced this bug), ADR-0002 (golden-master rule), `docs/standards.md#golden-master-rule`, `docs/plan.md`, `progress.md` (open question: should the accumulated-cash virtual asset exist)

## Context

`compute_projection` integrates operating cash flow into net worth through **two mechanisms
that overlap**, so some flows are counted twice:

1. **Real cash asset** — `_apply_cash_conversions` folds buy/sell **and every non-cash asset's
   `CASH_FLOW` column** (rent, dividends, pension deposits/payouts, own-capital deposits) into
   the cash balance.
2. **Virtual "accumulated cash" (מזומנים מצטברים) asset** — `cumsum(cash_flow_breakdown.net_series)`,
   appended as a virtual asset and added to `net_worth_series` (`projections.py` ~1212-1248).
   `net_series` sums **all** breakdown items, including the same asset-attached flows.

**Verified empirically** (clean engine, 2026-07-16):

| Flow | breakdown `entity_type` | in real cash | in accumulated | net worth today |
|------|------------------------|:------------:|:--------------:|-----------------|
| Rent (attached to real-estate) | `asset` | yes (+5k/mo) | yes (+5k/mo) | **+10k/mo (double)** |
| Own-capital asset deposit | `asset` | yes (cash−, asset+) | yes (−/mo) | **wrongly falls (double)** |
| Loan payment | `loan` | no | yes | −payment (correct, single) |
| Standalone salary | `None` | no | yes | +salary (correct, single) |
| Standalone expense | `None` | no | yes | −expense (correct, single) |

So: **operating cash flow is already integrated into net worth** (expenses/salary/loans already
move it — ADR-0003's premise that they don't was wrong). The real defect is that **asset-attached
flows are double-counted**: ₪5,000/mo rent grows net worth ₪10,000/mo. This overstates portfolio 1
(rental income + pension) and is frozen into `fixtures/projection_golden.json`.

## Decision

Make the two mechanisms **non-overlapping**. The accumulated-cash virtual asset must integrate
only the flows **not already in the real cash asset** — i.e. exclude asset-attached items. The
discriminator is already present on every breakdown item and was **verified** to line up exactly
with "is it in the real cash asset":

- `entity_type == "asset"`  → already in the real cash balance → **exclude** from accumulated cash.
- `entity_type == "loan"`   → loan payment, not in cash → keep.
- `entity_type is None`     → standalone revenue / cash flow, not in cash → keep.

The **display** cash-flow breakdown (income/expense/net chart, `monthly_cash_flow_series`) stays
**gross** — it should still show rent, salary, expenses, loan payments. Only the **accumulated-cash
→ net-worth** computation changes.

### Design (localized change)

In `compute_projection`, replace the accumulated-cash source `cash_flow_breakdown.net_series`
with a net series computed over only `entity_type != "asset"` items:

```python
integ_income, integ_expense = {}, {}
for item in breakdown_loan_items + breakdown_asset_cf_items + breakdown_revenue_items:
    if item.entity_type == "asset":
        continue  # already in the real cash asset (ADR-0004) — don't double-count
    bucket = integ_income if item.source_type == "income" else integ_expense
    for pt in item.time_series:
        bucket[pt.date] = bucket.get(pt.date, 0.0) + float(pt.value)
# accumulated cash = cumsum over all_dates of (integ_income[d] - integ_expense[d])
```

Everything else (real cash asset, `_apply_cash_conversions`, the breakdown/chart) is untouched.
No schema change, no dependency change. Engine-only.

### Why not the alternatives

- **Strip asset `CASH_FLOW` out of the real cash asset instead** (let accumulated own all flow) —
  rejected: bigger blast radius (`_apply_cash_conversions` + per-asset cash display + measurement
  anchoring of the cash series all change), for the same net-worth result.
- **Remove the accumulated-cash virtual asset entirely** — rejected here (it's the mechanism that
  makes salary/expenses/loans move net worth, which is desired); it's a separate open question in
  `progress.md` and can be revisited independently.
- **Split loan payment principal/interest** — not needed; loan payment (accumulated −) + liability
  amortization (independent) already nets to −interest.

## Consequences

- **Positive:** net worth stops overstating rental/pension/own-capital-deposit growth; the two
  cash mechanisms become coherent (each flow counted once). Surgical, ~1 localized edit.
- **Negative / trade-offs:** **intentionally changes projected values** → a **witnessed golden
  re-baseline** (per `docs/standards.md`): the diff must move **only** by removing asset-attached
  flows from accumulated cash (net worth **lower** wherever there's rent/pension/own-cap deposits).
  Portfolio 1's 30-yr net-worth trajectory drops — this is a correction, and worth eyeballing the
  magnitude before re-freezing.
- **Deploy:** local-first; Neon/Vercel stays manual + owner-gated. Not auto-deployed.

## Verification strategy (verify-first, no circles)

1. **Characterization tests BEFORE the fix** (lock current behavior so the diff is intentional):
   assert today's double-count exists (rent ₪5k → nw +₪10k/mo). After the fix, flip them to the
   corrected invariant (rent ₪5k → nw +₪5k/mo).
2. **Isolated invariant tests** (no DB), each one mechanism — building on the verified table:
   - rent attached ⇒ nw +rent/mo (once);
   - own-capital asset deposit ⇒ nw flat (neutral, no double drain);
   - loan ⇒ nw −payment/mo (unchanged);
   - standalone salary ⇒ nw +salary/mo (unchanged);
   - standalone expense ⇒ nw −expense/mo (unchanged);
   - mixed portfolio ⇒ accumulated-cash series == cumsum of only non-asset items.
3. **Golden re-baseline:** regenerate `fixtures/projection_golden.json`; **review the diff** —
   net worth lower, deltas equal to the removed asset-attached flows, liabilities/asset series
   unchanged. Re-freeze only after the diff is explained.
4. **End-to-end on portfolio 1:** recompute; report the before/after 30-yr net worth so the
   magnitude of the correction is visible. Confirm perf stays within ADR-0002's budget.

## Follow-ups

- The `progress.md` question "should the accumulated-cash virtual asset always appear in
  `asset_projections`?" — orthogonal; revisit after this lands.
- Potential separate issue (out of scope): external (non-own-capital) asset deposits may inflate
  the real cash balance via asset `CASH_FLOW`; not part of this double-count fix — flag & verify later.
