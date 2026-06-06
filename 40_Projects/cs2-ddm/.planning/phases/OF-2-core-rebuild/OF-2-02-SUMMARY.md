---
phase: OF-2
plan: "02"
subsystem: duel-reconstruction
tags: [deletion, cleanup, outcome-first, geometry-selector]
dependency_graph:
  requires: [OF-2-01]
  provides: [OF-2-03]
  affects: [batch_runner, multi_player_analyze, app, kill_rate_analysis, duel_attempts, t0_detector]
tech_stack:
  added: []
  patterns: [outcome-first episode write replaces geometry attempts write in all callers]
key_files:
  modified:
    - duel_attempts.py
    - t0_detector.py
    - ddm_analyzer.py
    - batch_runner.py
    - multi_player_analyze.py
    - app.py
    - kill_rate_analysis.py
    - tests/test_duel_attempts.py
    - tests/test_ddm_analyzer_core.py
  deleted:
    - tests/test_t0_detector_first_visible_window.py
decisions:
  - "DuelAttempt dataclass retained for legacy typing; DuelAttemptFinder deleted"
  - "attempts_mode param removed from analyze_demo; tuple shape kept with hardcoded []"
  - "app.py _run_analysis: all_attempts UI block removed, attempts_df always empty"
  - "kill_rate_analysis: deprecated docstring added, module kept for DuelAttempt typing"
metrics:
  duration: "~25 minutes"
  completed: "2026-06-05"
  tasks_completed: 3
  files_modified: 10
  files_deleted: 1
---

# Phase OF-2 Plan 02: Geometry Selector Deletion + Episode Wiring Summary

**One-liner:** Geometry-first DuelAttemptFinder + find_first_visible_enemy_in_window deleted; all 5 callers wired to reconstruct_all_players; 365 tests GREEN.

## Tasks Completed

| Task | Commit | Description |
|-|-|-|
| Task 1 | 2427e9a | Delete DuelAttemptFinder from duel_attempts.py + find_first_visible_enemy_in_window from t0_detector.py |
| Task 2 | f1e7f19 | Remove attempts_mode from ddm_analyzer; wire batch_runner/multi_player_analyze/app/kill_rate_analysis to episodes |
| Task 3 | 0787319 | Delete geometry selector test suite; survivors intact; 365 tests GREEN |

## Decisions Made

1. `DuelAttempt` dataclass retained as-is -- kill_rate_analysis.py + test_db_utils + test_kill_rate_analysis all import it for legacy typing.
2. `analyze_demo` return type kept as `Tuple[pd.DataFrame, List[DuelAttempt]]` with `attempts=[]` hardcoded -- avoids cascade of caller signature changes across 5 files.
3. `app.py` kills/misses/kill_pct display block removed entirely (was geometry-attempts-only UI); `attempts_df` session state preserved as empty DataFrame for compat.
4. `kill_rate_analysis.py` deprecated but not deleted -- still used for DuelAttempt type + CSV loading in `--load-only` mode.
5. `dataclasses` import removed from batch_runner.py and multi_player_analyze.py (no longer needed after DuelAttempt.asdict calls gone).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Cleanup] Removed unused `dataclasses` imports**
- **Found during:** Task 2
- **Issue:** After removing `att_df = pd.DataFrame([dataclasses.asdict(a) for a in attempts])` calls, `import dataclasses` became a dead import in batch_runner.py and multi_player_analyze.py.
- **Fix:** Removed the imports to keep ruff clean.
- **Files modified:** batch_runner.py, multi_player_analyze.py
- **Commit:** f1e7f19

**2. [Rule 1 - Correctness] test_analyze_demo_parses_player_death deleted (not just the 3-line stub)**
- **Found during:** Task 3
- **Issue:** Plan said "delete the whole function, not just 3 lines" but the function (L1060-L1102) tested `find_all_duel_attempts` via `fake_find_all` monkey-patch + `attempts_mode=True`. Both are now gone -- keeping the test would fail on import.
- **Fix:** Deleted the full 43-line function.
- **Files modified:** tests/test_ddm_analyzer_core.py
- **Commit:** 0787319

**3. [Rule 2 - Correctness] TestDuelAttemptPlayerSteamid.test_finder_propagates_player_steamid_to_attempt deleted**
- **Found during:** Task 3 (reading test_duel_attempts.py L348-366)
- **Issue:** This test exercised `DuelAttemptFinder` directly -- deleted as part of the DuelAttemptFinder section. The surviving tests cover `DuelAttempt` dataclass behavior only.
- **Commit:** 0787319

## Test Suite

- Before: 379 tests
- After: 365 tests (-14 = DuelAttemptFinder tests deleted, as expected)
- Status: 365 GREEN

## Known Stubs

None. The `attempts=[]` in `analyze_demo` is an explicit architectural choice documented in the return comment, not a UI-blocking stub.

## Threat Flags

None -- net code deletion, no new attack surface.

## Self-Check: PASSED

- duel_attempts.py: DuelAttempt importable, DuelAttemptFinder not
- t0_detector.py: find_first_visible_enemy_in_window absent, find_t0 present
- grep attempts_mode across *.py: 0 hits (excluding docstrings/spike)
- batch_runner.py: reconstruct_all_players present (2 hits)
- multi_player_analyze.py: reconstruct_all_players present (2 hits)
- tests/test_t0_detector_first_visible_window.py: deleted
- Full suite: 365/365 GREEN
- Commits: 2427e9a, f1e7f19, 0787319 all present in git log
