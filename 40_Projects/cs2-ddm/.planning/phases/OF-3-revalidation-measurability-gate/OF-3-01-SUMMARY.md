---
phase: OF-3-revalidation-measurability-gate
plan: "01"
subsystem: testing
tags: [pytest, sqlite, db_utils, config, tdd, reaction-timing]

# Dependency graph
requires: []
provides:
  - "config.TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS, _T0_SEARCH_PARSE_WINDOW_TICKS constants (D-02/D-05)"
  - "duel_episodes 7 timing columns via idempotent _episode_timing_migrations (D-13)"
  - "requires_db pytest marker registered in pytest.ini (D-15)"
  - "tests/test_reaction_timing.py — 7 RED tests pinning compute_timing contract (D-01/D-03/D-05/D-06)"
  - "tests/test_distribution_shape.py — two-tier (synthetic + @requires_db) distribution-shape suite scaffold"
affects: [OF-3-02, OF-3-03, OF-3-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Stub T0Detector double (find_t0 driven by a controllable visible_ticks set) for BVH-free synthetic timing tests"
    - "Two-tier test suite: Tier 1 synthetic always-on, Tier 2 @requires_db skips cleanly pre-rebatch"

key-files:
  created:
    - tests/test_reaction_timing.py
    - tests/test_distribution_shape.py
  modified:
    - config.py
    - db_utils.py
    - pytest.ini
    - tests/test_db_utils.py

key-decisions:
  - "TARGET_REACHED_THRESHOLD=3.0, T0_BACKWARD_SEARCH_CAP_TICKS=640, _T0_SEARCH_PARSE_WINDOW_TICKS=640 locked per D-02/D-05 rationale comments in config.py"
  - "duel_episodes timing columns added via _episode_timing_migrations idempotent ALTER loop, mirroring the t1_source/_eng_migrations precedent"
  - "reaction_timing.py deliberately NOT created — RED state for tests/test_reaction_timing.py and the Tier-1 synthetic test in test_distribution_shape.py is the expected Wave-0 TDD outcome"

patterns-established:
  - "Pattern: TDD Wave-0 RED tests import a not-yet-existing module at top-of-file so collection itself fails RED, pinning the contract for the next plan's GREEN implementation"
  - "Pattern: physics-bounded distribution-shape check (t1_tick==t0_tick+1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD) guards against B-5-class bugs in both synthetic and live tiers"

requirements-completed: [SC-3]

# Metrics
duration: ~25min
completed: 2026-06-11
---

# Phase OF-3 Plan 01: TDD + Schema + Config Foundation Summary

**Added OF-3 reaction-timing config constants, an idempotent duel_episodes timing-column migration, a registered requires_db pytest marker, and 8 RED tests (7 in test_reaction_timing.py + 1 in test_distribution_shape.py) pinning the new T1 "crosshair LANDS" predicate and T0 backward-search contract before any implementation exists.**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-06-11T03:55:00Z (approx)
- **Completed:** 2026-06-11T04:04:37Z
- **Tasks:** 3
- **Files modified:** 6 (4 modified, 2 created)

## Accomplishments
- config.py gains TARGET_REACHED_THRESHOLD (3.0), T0_BACKWARD_SEARCH_CAP_TICKS (640), and _T0_SEARCH_PARSE_WINDOW_TICKS (640) with full rationale comments (D-02/D-05)
- duel_episodes table gains 7 new timing columns (t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms) via an idempotent migration
- requires_db marker registered in pytest.ini for the tier-2 live-DB regression suite (D-15)
- tests/test_reaction_timing.py: 7 RED tests pinning compute_timing's T0/T1 contract using a synthetic stub T0Detector (no BVH/demo files needed)
- tests/test_distribution_shape.py: two-tier suite — Tier 1 synthetic flick-batch (RED, pending OF-3-02), Tier 2 @requires_db pinning/min-rt/physics-bound/never_landed+never_visible checks (skip cleanly pre-rebatch)
- tests/test_db_utils.py gains test_duel_episodes_timing_migration_idempotent (GREEN)

## Task Commits

Each task was committed atomically:

1. **Task 1: Add OF-3 config constants + duel_episodes timing migration + requires_db marker** - `9f8b174` (feat)
2. **Task 2: RED tests for T0 backward search + T1 LANDS predicate** - `ea2abd1` (test)
3. **Task 3: Distribution-shape synthetic tier + db_utils migration test** - `ca5a4b8` (test)

**Plan metadata:** (this commit, after STATE.md update)

_Note: Tasks 2-3 are the RED half of a TDD plan; reaction_timing.py implementation (GREEN) lands in OF-3-02._

## Files Created/Modified
- `config.py` - +3 OF-3 constants (TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS, _T0_SEARCH_PARSE_WINDOW_TICKS) with rationale comments
- `db_utils.py` - `_migrate_schema` gains `_episode_timing_migrations` ALTER loop for duel_episodes (7 new columns)
- `pytest.ini` - `requires_db` marker registered
- `tests/test_db_utils.py` - new `test_duel_episodes_timing_migration_idempotent` (GREEN)
- `tests/test_reaction_timing.py` - new file, 7 RED tests pinning `reaction_timing.compute_timing` contract
- `tests/test_distribution_shape.py` - new file, two-tier distribution-shape suite (1 RED Tier-1 test + 4 skip-clean Tier-2 @requires_db tests)

## Decisions Made
- D-02/D-05 constants locked at the values specified in OF-3-CONTEXT (3.0 / 640 / 640); A/B re-evaluation deferred to OF-3-02's N=1 staged run as documented in the rationale comments
- `_StubT0Detector` synthetic double pattern established for BVH-free timing tests — reusable in OF-3-02's implementation tests
- Tier-2 `@requires_db` tests check both `t1_source` (never_landed) and `t0_source` (never_visible) distributions, each flagged at >50%, expanding slightly on the plan's literal spec for symmetric coverage

## Deviations from Plan

None - plan executed exactly as written. Tier-2 test additions (checking `t0_source` never_visible alongside `t1_source` never_landed) are a direct, in-scope elaboration of the plan's stated behavior ("report never_landed%/never_visible%") — not a new feature.

## Issues Encountered
- ruff flagged an unused `import math` and two unused loop variables (`gap_start`/`gap_end`) in the initial draft of `tests/test_reaction_timing.py`; both removed before commit. black auto-reformatted both new test files (project hook convention).
- Initial `_load_resolved_rt` docstring contained the literal substring `pd.read_sql` (in an explanatory comment), which would have falsely matched the acceptance-criteria grep for "no pd.read_sql usage"; reworded the docstring to avoid the literal string while preserving the explanation.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- OF-3-02 can now implement `reaction_timing.py` against the pinned contract in `tests/test_reaction_timing.py` (GREEN phase of this TDD plan)
- duel_episodes schema is ready to receive timing data from OF-3-02's compute_timing output
- `tests/test_distribution_shape.py` Tier-2 suite is ready to run (skip-clean) until OF-3-03's staged re-batch populates `t0_tick`/`t1_tick`/`t1_source`/`t0_source` on duel_episodes
- No blockers identified

---
*Phase: OF-3-revalidation-measurability-gate*
*Completed: 2026-06-11*

## Self-Check: PASSED

All created files and task commits verified present.
