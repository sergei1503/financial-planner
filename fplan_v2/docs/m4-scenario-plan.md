# Milestone 4: Scenario System - Task Breakdown

## Overview

Port the v1 Streamlit scenario engine (`scenarios/`) to v2 React + FastAPI architecture.
The v1 system supports what-if analysis by applying actions (add asset, add loan, change params, etc.) to a baseline portfolio and comparing projected outcomes.

## Key Design Decisions

### Action Types (v1 -> v2 mapping)

v1 uses `EScenario` integer constants. v2 already has `ActionType` enum in `fplan_v2/core/constants.py` with string values. All 9 action types carry forward:

| v1 EScenario | v2 ActionType | Essential for MVP? | Description |
|---|---|---|---|
| `new_asset` (1) | `NEW_ASSET` | Yes | Add a hypothetical asset |
| `new_loan` (0) | `NEW_LOAN` | Yes | Add a hypothetical loan |
| `param_change` (4) | `PARAM_CHANGE` | Yes | Change appreciation rate, value, etc. |
| `repay_loan` (2) | `REPAY_LOAN` | Yes | Early loan repayment |
| `withdraw_from_asset` (5) | `WITHDRAW_FROM_ASSET` | Yes | One-time or recurring withdrawal |
| `deposit_to_asset` (6) | `DEPOSIT_TO_ASSET` | Phase 2 | Deposit into asset |
| `market_crash` (7) | `MARKET_CRASH` | Phase 2 | Market event affecting asset types |
| `add_revenue_stream` (8) | `ADD_REVENUE_STREAM` | Phase 2 | Add rent/dividend/salary stream |
| `transform_asset` (3) | `TRANSFORM_ASSET` | Phase 2 | Convert asset type |

**MVP ships 5 action types. Phase 2 adds 4 more.**

### How Scenarios Modify Projections

In v1, `User.run_scenario(actions)` takes a deep copy of the user's portfolio and applies actions before running `get_projection()`. In v2:

1. Client sends scenario with `actions_json` array to API
2. API loads user's portfolio from DB
3. Engine applies actions to a deep-copied portfolio (same pattern as v1)
4. Engine runs projection on the modified portfolio
5. Results are returned (and optionally cached in `scenario_results` table)

### Comparison UX

- **Overlay chart**: All selected scenarios + baseline on the same net worth chart (primary view)
- **Summary table**: Side-by-side metrics (final net worth, delta from baseline, % change)
- **Individual drill-down**: Click a scenario to see detailed asset/loan breakdown

### Caching Strategy

- Scenarios are run on-demand (button click)
- Results cached in `scenario_results` table with `config_hash` for invalidation
- Cache invalidated when portfolio data changes or scenario actions are edited

---

## Task Breakdown

### Layer 1: API Schemas (Pydantic)

#### Task 1.1: Scenario Action Schemas
- **File**: `fplan_v2/api/schemas.py` (append to existing)
- **Steps**:
  1. Add `ScenarioActionType` enum (string enum matching `ActionType` values)
  2. Add `ScenarioAction` schema with `action_type: ScenarioActionType` and `params: Dict[str, Any]` (JSONB-compatible)
  3. Add typed action param schemas: `NewAssetParams`, `NewLoanParams`, `ParamChangeParams`, `RepayLoanParams`, `WithdrawParams`
  4. Each param schema validates required fields for that action type
- **v1 Reference**: `scenarios/actions/action_utils.py` (validate_action), `backend/constants.py` (EScenario)
- **Verification**: Unit test that valid/invalid action payloads are accepted/rejected
- **Complexity**: Small
- **Dependencies**: None

#### Task 1.2: Scenario CRUD Schemas
- **File**: `fplan_v2/api/schemas.py` (append)
- **Steps**:
  1. `ScenarioBase`: name, description, actions (List[ScenarioAction])
  2. `ScenarioCreate(ScenarioBase)`: add user_id
  3. `ScenarioUpdate`: optional name, description, actions, is_active
  4. `ScenarioResponse(ScenarioBase)`: add id, user_id, version, parent_version, is_active, created_at, updated_at
- **v1 Reference**: `scenarios/core/scenario_engine.py` (create_and_run_new_scenario - shows scenario data shape)
- **Verification**: Unit test serialization round-trip
- **Complexity**: Small
- **Dependencies**: Task 1.1

#### Task 1.3: Scenario Result Schemas
- **File**: `fplan_v2/api/schemas.py` (append)
- **Steps**:
  1. `ScenarioResultResponse`: scenario_id, result_type, result_data (Dict), computed_at
  2. `ScenarioComparisonRequest`: scenario_ids (List[int]), include_baseline (bool)
  3. `ScenarioComparisonResponse`: baseline projection + list of scenario projections with metadata (name, delta, %)
- **v1 Reference**: `scenarios/core/scenario_engine.py` (run_scenario_analysis - shows result shape)
- **Verification**: Unit test with mock projection data
- **Complexity**: Small
- **Dependencies**: Task 1.2

---

### Layer 2: Database Repository

#### Task 2.1: Scenario ORM Model
- **File**: `fplan_v2/db/models.py` (add to existing, or create `fplan_v2/db/models/scenario.py`)
- **Steps**:
  1. Create `Scenario` SQLAlchemy model matching `scenarios` table in schema.sql
  2. Create `ScenarioResult` SQLAlchemy model matching `scenario_results` table
  3. Add relationships (Scenario -> ScenarioResult, User -> Scenario)
- **v1 Reference**: N/A (v1 uses session state, not DB)
- **Verification**: Model can be instantiated and mapped to table
- **Complexity**: Small
- **Dependencies**: None

#### Task 2.2: Scenario Repository
- **File**: `fplan_v2/db/repositories/scenario_repository.py`
- **Steps**:
  1. Extend `BaseRepository[Scenario]`
  2. `get_by_user(user_id)` - list all scenarios for user
  3. `get_by_name(user_id, name)` - find by name (for uniqueness check)
  4. `get_active(user_id)` - list active scenarios
  5. `toggle_active(scenario_id, is_active)` - activate/deactivate
  6. `get_latest_version(user_id, name)` - for versioning support
- **v1 Reference**: `scenarios/core/scenario_data.py` (session state CRUD patterns)
- **Verification**: Integration test with test DB
- **Complexity**: Medium
- **Dependencies**: Task 2.1

#### Task 2.3: Scenario Result Repository
- **File**: `fplan_v2/db/repositories/scenario_result_repository.py`
- **Steps**:
  1. Extend `BaseRepository[ScenarioResult]`
  2. `get_by_scenario(scenario_id)` - all results for a scenario
  3. `get_by_type(scenario_id, result_type)` - specific result type
  4. `upsert_result(scenario_id, result_type, data, config_hash)` - create or update cached result
  5. `invalidate(scenario_id)` - delete cached results (for re-run)
  6. `is_valid(scenario_id, config_hash)` - check if cache is still valid
- **v1 Reference**: `scenarios/core/scenario_engine.py` (st.session_state.scenario_results)
- **Verification**: Integration test with test DB
- **Complexity**: Medium
- **Dependencies**: Task 2.1

#### Task 2.4: Register Repositories
- **File**: `fplan_v2/db/repositories/__init__.py`
- **Steps**: Export `ScenarioRepository` and `ScenarioResultRepository`
- **Complexity**: Small
- **Dependencies**: Tasks 2.2, 2.3

---

### Layer 3: Scenario Engine (Core Logic)

#### Task 3.1: Action Applier
- **File**: `fplan_v2/core/engine/action_applier.py`
- **Steps**:
  1. `apply_action(user: User, action: ScenarioAction) -> User` - dispatches to action-specific handler
  2. `_apply_new_asset(user, params)` - creates asset object, adds to user
  3. `_apply_new_loan(user, params)` - creates loan object, adds to user
  4. `_apply_param_change(user, params)` - modifies asset/loan parameters
  5. `_apply_repay_loan(user, params)` - applies loan repayment
  6. `_apply_withdraw(user, params)` - applies withdrawal
  7. Each handler converts API params to v1 backend objects (Asset, Loan, etc.)
- **v1 Reference**: `scenarios/actions/asset_actions.py`, `loan_actions.py`, `parameter_actions.py`, `market_actions.py`
- **Verification**: Unit tests applying each action type to a mock User
- **Complexity**: Large
- **Dependencies**: Tasks 1.1, 2.1

#### Task 3.2: Scenario Runner
- **File**: `fplan_v2/core/engine/scenario_runner.py`
- **Steps**:
  1. `run_scenario(user_portfolio: dict, actions: List[ScenarioAction]) -> ProjectionResult`
  2. Deep-copy the portfolio config
  3. Create User object from config (port `create_user_from_config` from v1)
  4. Apply each action via action_applier
  5. Run projection (`user.get_projection()`)
  6. Return structured result
  7. `run_comparison(user_portfolio: dict, scenarios: List[Scenario]) -> ComparisonResult`
  8. Run baseline + each scenario, compute deltas
- **v1 Reference**: `scenarios/core/scenario_engine.py` (run_scenario_analysis, create_user_from_config)
- **Verification**: Integration test with real User object and known config
- **Complexity**: Large
- **Dependencies**: Task 3.1

---

### Layer 4: API Routes

#### Task 4.1: Scenario CRUD Routes
- **File**: `fplan_v2/api/routes/scenarios.py`
- **Steps**:
  1. `POST /scenarios/` - create scenario (validate actions, store in DB)
  2. `GET /scenarios/{id}` - get scenario by ID
  3. `GET /scenarios/?user_id=X` - list user's scenarios
  4. `PUT /scenarios/{id}` - update scenario (name, description, actions, is_active)
  5. `DELETE /scenarios/{id}` - delete scenario
  6. `PATCH /scenarios/{id}/activate` - toggle active status
  7. Follow exact same patterns as `fplan_v2/api/routes/assets.py`
- **v1 Reference**: `scenarios/core/scenario_engine.py` (create_and_run_new_scenario), `scenarios/ui/scenario_management_ui.py`
- **Verification**: API tests for each endpoint (status codes, validation errors, CRUD operations)
- **Complexity**: Medium
- **Dependencies**: Tasks 1.2, 2.2, 2.4

#### Task 4.2: Scenario Execution Routes
- **File**: `fplan_v2/api/routes/scenarios.py` (append to same file)
- **Steps**:
  1. `POST /scenarios/{id}/run` - run a single scenario, return projection result
  2. `POST /scenarios/compare` - accept ScenarioComparisonRequest, run baseline + selected scenarios, return comparison
  3. Both endpoints use scenario_runner from Task 3.2
  4. Cache results in scenario_results table
  5. Return cached results if config_hash matches
- **v1 Reference**: `scenarios/core/scenario_engine.py` (run_scenario_analysis)
- **Verification**: API test with known portfolio data, verify projection shape
- **Complexity**: Medium
- **Dependencies**: Tasks 3.2, 4.1

#### Task 4.3: Register Scenario Router
- **File**: `fplan_v2/api/routes/__init__.py` and `fplan_v2/api/main.py`
- **Steps**: Mount scenario router at `/api/scenarios`
- **Complexity**: Small
- **Dependencies**: Tasks 4.1, 4.2

---

### Layer 5: Frontend - API Client & Hooks

#### Task 5.1: Scenario API Types
- **File**: `fplan_v2/frontend/src/api/types.ts` (append)
- **Steps**:
  1. `ScenarioActionType` enum (matching backend)
  2. `ScenarioAction` interface: { action_type, params }
  3. Action param types: `NewAssetParams`, `NewLoanParams`, `ParamChangeParams`, `RepayLoanParams`, `WithdrawParams`
  4. `ScenarioCreate`, `ScenarioUpdate`, `ScenarioResponse` interfaces
  5. `ScenarioComparisonRequest`, `ScenarioComparisonResponse` interfaces
- **v1 Reference**: Derived from Task 1.1-1.3 schemas
- **Verification**: TypeScript compiles without errors
- **Complexity**: Small
- **Dependencies**: Tasks 1.1-1.3 (schema design finalized)

#### Task 5.2: Scenario API Client
- **File**: `fplan_v2/frontend/src/api/scenarios.ts`
- **Steps**:
  1. `scenariosApi.list(userId)` - GET /scenarios/?user_id=X
  2. `scenariosApi.get(id)` - GET /scenarios/{id}
  3. `scenariosApi.create(data)` - POST /scenarios/
  4. `scenariosApi.update(id, data)` - PUT /scenarios/{id}
  5. `scenariosApi.delete(id)` - DELETE /scenarios/{id}
  6. `scenariosApi.toggleActive(id, isActive)` - PATCH /scenarios/{id}/activate
  7. `scenariosApi.run(id)` - POST /scenarios/{id}/run
  8. `scenariosApi.compare(request)` - POST /scenarios/compare
  9. Follow pattern from `fplan_v2/frontend/src/api/assets.ts`
- **Verification**: TypeScript compiles, manual test with running API
- **Complexity**: Small
- **Dependencies**: Task 5.1

#### Task 5.3: Scenario React Query Hooks
- **File**: `fplan_v2/frontend/src/hooks/use-scenarios.ts`
- **Steps**:
  1. `useScenarios()` - query all scenarios for user
  2. `useScenario(id)` - query single scenario
  3. `useCreateScenario()` - mutation, invalidates scenarios list
  4. `useUpdateScenario()` - mutation, invalidates scenarios list + detail
  5. `useDeleteScenario()` - mutation, invalidates scenarios list
  6. `useToggleScenario()` - mutation for activate/deactivate
  7. `useRunScenario()` - mutation that returns projection data
  8. `useCompareScenarios()` - mutation that returns comparison data
  9. Follow pattern from `fplan_v2/frontend/src/hooks/use-assets.ts`
- **Verification**: Hooks can be called from a test component
- **Complexity**: Small
- **Dependencies**: Task 5.2

---

### Layer 6: Frontend - Pages & Components

#### Task 6.1: Scenario List Page
- **File**: `fplan_v2/frontend/src/features/scenarios/scenarios-page.tsx`
- **Steps**:
  1. Page layout following `assets-page.tsx` pattern
  2. List of scenarios with name, description, action count, active status toggle
  3. "Add Scenario" button opens form dialog
  4. Each row has edit/delete/run actions
  5. Active scenarios are visually highlighted
- **v1 Reference**: `scenarios/ui/scenario_management_ui.py`
- **Verification**: Page renders with mock data, CRUD operations work
- **Complexity**: Medium
- **Dependencies**: Task 5.3

#### Task 6.2: Scenario List Component
- **File**: `fplan_v2/frontend/src/features/scenarios/scenario-list.tsx`
- **Steps**:
  1. Table/card display of scenarios
  2. Toggle switch for active/inactive
  3. Action menu (edit, duplicate, delete, run)
  4. Show action count badge per scenario
  5. Empty state when no scenarios exist
- **Verification**: Renders correctly with 0, 1, many scenarios
- **Complexity**: Small
- **Dependencies**: Task 5.3

#### Task 6.3: Scenario Form (Create/Edit)
- **File**: `fplan_v2/frontend/src/features/scenarios/scenario-form.tsx`
- **Steps**:
  1. Dialog form following `asset-form.tsx` pattern (react-hook-form + zod)
  2. Fields: name (text), description (textarea)
  3. Actions builder section (see Task 6.4)
  4. Save button creates/updates scenario via API
  5. Validation: name required, at least 1 action required
- **v1 Reference**: `scenarios/ui/scenario_forms.py` (create_new_scenario_form)
- **Verification**: Form submits valid data, shows validation errors
- **Complexity**: Medium
- **Dependencies**: Task 5.3, Task 6.4

#### Task 6.4: Action Builder Component
- **File**: `fplan_v2/frontend/src/features/scenarios/action-builder.tsx`
- **Steps**:
  1. Sortable list of actions within a scenario
  2. "Add Action" button with action type selector dropdown
  3. Each action type renders a specific param form:
     - `NewAssetAction`: asset_type, name, value, start_date, appreciation_rate
     - `NewLoanAction`: loan_type, name, value, interest_rate, duration, start_date
     - `ParamChangeAction`: select existing asset/loan, fields to change
     - `RepayLoanAction`: select existing loan, amount, date
     - `WithdrawAction`: select existing asset, amount, date, type (one-time/monthly)
  4. Remove action button on each item
  5. Action summary display (human-readable description)
- **v1 Reference**: `scenarios/ui/scenario_forms.py` (create_scenario_action_form), `scenarios/actions/*.py`
- **Verification**: Can add/remove/reorder actions, form data validates
- **Complexity**: Large (most complex frontend component)
- **Dependencies**: Task 5.1

#### Task 6.5: Scenario Comparison Page
- **File**: `fplan_v2/frontend/src/features/scenarios/scenario-comparison.tsx`
- **Steps**:
  1. "Run Comparison" button triggers `useCompareScenarios` with active scenario IDs
  2. Loading state with progress indicator
  3. Net worth overlay chart (Recharts): baseline + each scenario as separate lines
  4. Summary metrics table: scenario name, final net worth, delta from baseline, % change
  5. Individual scenario drill-down (expandable section with asset/loan breakdown)
- **v1 Reference**: `scenarios/visualization/charts.py` (display_scenario_comparison_charts), `scenarios/ui/scenario_comparison_ui.py`
- **Verification**: Chart renders with mock data, metrics calculate correctly
- **Complexity**: Large
- **Dependencies**: Tasks 5.3, 6.1

#### Task 6.6: Register Scenario Routes in App Router
- **File**: `fplan_v2/frontend/src/App.tsx` or router config
- **Steps**:
  1. Add `/scenarios` route pointing to ScenariosPage
  2. Add `/scenarios/compare` route pointing to ScenarioComparisonPage
  3. Add nav item in sidebar
- **Complexity**: Small
- **Dependencies**: Tasks 6.1, 6.5

---

### Layer 7: Integration & Testing

#### Task 7.1: Backend Unit Tests - Schemas
- **File**: `fplan_v2/tests/test_scenario_schemas.py`
- **Steps**:
  1. Test each action param schema with valid/invalid data
  2. Test ScenarioCreate/Update/Response serialization
  3. Test ScenarioComparisonRequest/Response
- **Complexity**: Small
- **Dependencies**: Layer 1

#### Task 7.2: Backend Unit Tests - Action Applier
- **File**: `fplan_v2/tests/test_action_applier.py`
- **Steps**:
  1. Test each MVP action type against a known User object
  2. Verify portfolio state changes after each action
  3. Test invalid action params raise appropriate errors
- **v1 Reference**: Can port test data from `tests/test_scenarios_2025_july_corrected.json`
- **Complexity**: Medium
- **Dependencies**: Task 3.1

#### Task 7.3: Backend Integration Tests - Scenario API
- **File**: `fplan_v2/tests/test_scenario_api.py`
- **Steps**:
  1. Test full CRUD lifecycle (create, read, update, delete)
  2. Test scenario run with known portfolio, verify projection shape
  3. Test comparison endpoint with multiple scenarios
  4. Test caching (run twice, verify second uses cache)
  5. Test cache invalidation
- **Complexity**: Medium
- **Dependencies**: Layer 4

#### Task 7.4: Frontend Component Tests
- **File**: `fplan_v2/frontend/src/features/scenarios/__tests__/`
- **Steps**:
  1. Scenario list renders scenarios
  2. Scenario form validates and submits
  3. Action builder can add/remove actions
  4. Comparison chart renders with mock data
- **Complexity**: Medium
- **Dependencies**: Layer 6

#### Task 7.5: E2E Scenario Workflow Test
- **File**: `fplan_v2/tests/test_scenario_e2e.py`
- **Steps**:
  1. Create user with assets and loans via API
  2. Create scenario with actions
  3. Run scenario, verify projection differs from baseline
  4. Create second scenario, run comparison
  5. Verify comparison response structure
- **Complexity**: Medium
- **Dependencies**: All layers

---

## Dependency Graph

```
Layer 1 (Schemas)
  1.1 -> 1.2 -> 1.3

Layer 2 (Repository)
  2.1 -> 2.2 -> 2.4
  2.1 -> 2.3 -> 2.4

Layer 3 (Engine)
  1.1 + 2.1 -> 3.1 -> 3.2

Layer 4 (Routes)
  1.2 + 2.2 + 2.4 -> 4.1 -> 4.3
  3.2 + 4.1 -> 4.2 -> 4.3

Layer 5 (Frontend API)
  1.1-1.3 -> 5.1 -> 5.2 -> 5.3

Layer 6 (Frontend Pages)
  5.1 -> 6.4
  5.3 -> 6.1, 6.2, 6.3, 6.5
  6.4 -> 6.3
  6.1 + 6.5 -> 6.6

Layer 7 (Tests)
  L1 -> 7.1
  3.1 -> 7.2
  L4 -> 7.3
  L6 -> 7.4
  All -> 7.5
```

## Recommended Execution Order

**Phase A - Foundation (can parallelize backend + frontend types):**
1. Task 1.1 (action schemas)
2. Task 1.2 (CRUD schemas)
3. Task 1.3 (result schemas)
4. Task 2.1 (ORM models) -- parallel with 1.x
5. Task 5.1 (TS types) -- parallel with 1.x once schema shape is agreed

**Phase B - Backend Core (sequential):**
6. Task 2.2 (scenario repo)
7. Task 2.3 (result repo)
8. Task 2.4 (register repos)
9. Task 3.1 (action applier)
10. Task 3.2 (scenario runner)

**Phase C - API + Frontend Client (parallel):**
11. Task 4.1 (CRUD routes) + Task 5.2 (API client)
12. Task 4.2 (execution routes) + Task 5.3 (hooks)
13. Task 4.3 (register router)

**Phase D - Frontend Pages (mostly parallel):**
14. Task 6.4 (action builder) -- start first, it's the hardest
15. Task 6.2 (list component) -- parallel with 6.4
16. Task 6.1 (list page) -- after 6.2
17. Task 6.3 (form) -- after 6.4
18. Task 6.5 (comparison page) -- parallel with 6.3
19. Task 6.6 (register routes)

**Phase E - Testing:**
20. Tasks 7.1-7.4 (unit + integration tests, parallel)
21. Task 7.5 (E2E test)

## Estimated Total: 21 tasks
- Small: 9 tasks (1.1, 1.2, 1.3, 2.1, 2.4, 4.3, 5.1, 5.2, 6.6)
- Medium: 8 tasks (2.2, 2.3, 4.1, 4.2, 5.3, 6.1, 6.2, 6.3)
- Large: 4 tasks (3.1, 3.2, 6.4, 6.5)
