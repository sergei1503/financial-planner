# ADR 0002: Projection performance strategy

- **Status:** accepted
- **Date:** 2026-07-14
- **Deciders:** Owner (Sergei) — recorded during sdlc-kit onboarding / M1 planning
- **Related:** PRD `docs/prd.md#success-criteria`, Architecture `docs/architecture.md`, ADR-0001, Plan `docs/plan.md` (M1 item 1)

## Context
Warm projection reads are already fast because results are cached on a `portfolio_version`
bump (ADR-0001). The remaining pain is the **cold recompute after an edit**: ~1.44s of a
~1.9s cold request. Profiling points at O(n²) work inside `compute_projection`
(`fplan_v2/api/routes/projections.py`): per-month loops over ~360 months × many
assets/loans/cash-flow items, each doing `df[df["date"] == dt]` scans and `iterrows` in the
per-date series builders, `_build_cash_flow_breakdown`, and `_apply_cash_conversions`. The
projection math is golden-master; users need it to *feel instant*, not to change.

## Decision
We will make projections faster by **vectorizing the per-date aggregation** — replacing
repeated `df[df["date"] == dt]` scans and `iterrows` with dict / reindex lookups and vector
operations — **not** by changing the cache or invalidation model, which already works. The
refactor is **pure speed: byte-identical `ProjectionResponse` output** is a hard constraint,
guarded by a golden snapshot test taken before the change. Target: cold recompute < 0.4s.

## Alternatives considered
- **Change caching (finer keys, warm-on-write, TTL)** — rejected: caching is already the
  reason warm reads are fast; the bottleneck is the recompute itself, and touching cache
  keys risks correctness for no speed gain on the cold path.
- **Background/precompute worker** — rejected: adds infra and complexity for a single-user
  app; doesn't help the first recompute after an edit, which is the felt latency.
- **Rewrite the engine (async, Rust/Numba, parallelism)** — rejected as premature: a
  straightforward vectorization is expected to clear the <0.4s target without changing the
  language, the golden-master semantics, or the deploy model.

## Consequences
- **Positive:** the cold path drops from ~1.44s toward <0.4s, so editing feels live; no cache
  or schema changes; math is provably unchanged via the golden test.
- **Negative / trade-offs:** vectorized code is denser than the current row-loops and needs
  careful review to preserve exact ordering/rounding; the golden test must be authored first
  or the guarantee is unverifiable.
- **Follow-ups:** if <0.4s isn't reached by vectorization alone, revisit (profiling-led)
  before considering heavier options — do not jump to a rewrite. Correctness items (M1 items
  3–5) intentionally change results and carry their own tests, separate from this speed work.
