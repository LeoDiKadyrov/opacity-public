---
phase: OF-2
plan: "01"
subsystem: outcome-first
tags: [tdd, sqlite, event-driven, multi-player]
dependency_graph:
  requires: [OF-2-00]
  provides: [outcome_first.py, duel_episodes table]
  affects: [db_utils.py, config.py, analytics.db]
tech_stack:
  added: [outcome_first.py]
  patterns: [gun-only episode anchoring, event-derived opponent identity, parse-once multi-player]
key_files:
  created: [outcome_first.py]
  modified: [config.py, db_utils.py, tests/test_db_utils.py]
decisions:
  - "group_episodes returns n_hits_P_on_E/n_hits_E_on_P (mixed-case, matches test contract); reconstruct_all_players renames to n_hits_p_on_e/n_hits_e_on_p for DB DDL"
  - "opponent key kept in group_episodes output for test backward-compat; stripped before save_to_db"
  - "UTILITY_WEAPON_NAMES contains 11 strings (plan text said 10, but code block listed 11; code block is authoritative)"
metrics:
  duration: "~25 min"
  completed: "2026-06-05"
  tasks_completed: 3
  files_changed: 4
---

# Phase OF-2 Plan 01: Production Outcome-First Module Summary

**One-liner:** Ported spike logic to `outcome_first.py` with gun-only anchor, multi-player `reconstruct_all_players` API, `duel_episodes` SQLite table, and all 9 Wave-0 RED tests turned GREEN.

## Tasks Completed

| Task | Commit | Description |
|-|-|-|
| 1: config.py constants | 13758e6 | UTILITY_WEAPON_NAMES (11 strings) + _INITIATOR_LOOKBACK_TICKS=128 |
| 2: db_utils.py quad-touch | f797199 | duel_episodes DDL, whitelist, match_id scan, force-reprocess cleanup |
| 3: outcome_first.py | 8598c04 | Production module -- 379 tests pass |

## Verification Results

- `py -m pytest tests/test_outcome_first.py -p no:cov`: 9/9 PASS
- `py -m pytest -p no:cov`: 379/379 PASS (full suite)
- `py -c "from db_utils import init_db; init_db('analytics.db'); init_db('analytics.db')"`: idempotent OK
- `grep -c duel_episodes db_utils.py`: 8 (>= 5 acceptance criterion)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Whitelist guard] Updated test_allowed_tables_set in test_db_utils.py**
- **Found during:** Task 2
- **Issue:** `test_allowed_tables_set` pinned `_ALLOWED_TABLES == {"engagements", "duel_attempts"}` as a Phase 10a leak guard. Adding `duel_episodes` caused the test to fail.
- **Fix:** Updated the test's expected set and docstring to include `duel_episodes`. The old guard was superseded by OF-2's plan requirement.
- **Files modified:** `tests/test_db_utils.py`
- **Commit:** f797199

**2. [Rule 1 - Schema key naming] group_episodes keeps mixed-case keys for test compatibility**
- **Found during:** Task 3 (test analysis pre-implementation)
- **Issue:** `test_group_episodes_outcome_won_lost_unresolved` accesses `n_hits_P_on_E` / `n_hits_E_on_P` (spike naming). DB DDL uses lowercase `n_hits_p_on_e` / `n_hits_e_on_p`. Renaming in group_episodes would break the test; the plan says "DO NOT modify the test file".
- **Fix:** `group_episodes` returns both `opponent` (test contract) and `opponent_steamid` (DB schema); `n_hits_P_on_E`/`n_hits_E_on_P` kept in dict. `reconstruct_all_players` renames to DB column names before `save_to_db` and drops the `opponent` alias. Zero test changes needed.
- **Files modified:** `outcome_first.py`

## Known Stubs

None. All public API functions are fully implemented and wired to real data.

## Threat Flags

None beyond what the plan already addressed: `duel_episodes` table is local SQLite, table name never from user input (whitelist CR-01 guards it).

## Self-Check: PASSED

- `outcome_first.py` exists: FOUND
- `config.py` has UTILITY_WEAPON_NAMES and _INITIATOR_LOOKBACK_TICKS: FOUND
- `db_utils.py` duel_episodes count >= 5: 8 occurrences
- Commits 13758e6, f797199, 8598c04: all present in git log
- Full test suite: 379 PASS
