---
phase: 07-parallel-batch-runner-data-accumulation
plan: "01"
subsystem: db_utils
tags: [sqlite, wal, schema-migration, idempotency, batch-runner]
dependency_graph:
  requires: []
  provides:
    - db_utils.init_db
    - db_utils._migrate_schema
    - db_utils.is_processed
    - db_utils.mark_processed
    - db_utils.get_next_match_id
    - db_utils.force_reprocess_demo
    - config.DEFAULT_BATCH_WORKERS
    - for_analysis/ directory
  affects:
    - analytics.db (WAL mode, new tables, new columns)
tech_stack:
  added: []
  patterns:
    - "SQLite WAL mode via PRAGMA journal_mode=WAL + busy_timeout=10000"
    - "Idempotent schema migration: CREATE TABLE IF NOT EXISTS + ALTER TABLE ADD COLUMN guarded by PRAGMA table_info"
    - "INSERT OR REPLACE for processed_matches idempotency"
    - "MAX across two tables for match_id auto-increment"
key_files:
  created:
    - for_analysis/.gitkeep
    - .planning/phases/07-parallel-batch-runner-data-accumulation/07-01-SUMMARY.md
  modified:
    - db_utils.py
    - config.py
    - tests/test_db_utils.py
decisions:
  - "engagements table created by _migrate_schema (CREATE TABLE IF NOT EXISTS) rather than only altered — enables test isolation with fresh DBs"
  - "force_reprocess_demo implemented in Task 1 commit alongside other db_utils functions (D-12 locked decision)"
  - "busy_timeout=10000ms set on every connection to handle parallel WAL lock contention"
metrics:
  duration: "~15 min"
  completed: "2026-05-05"
  tasks_completed: 3
  files_changed: 4
---

# Phase 7 Plan 01: DB Foundation (WAL + Schema Migration) Summary

SQLite WAL mode + schema migration foundation for Phase 7 parallel batch runner: 6 new db_utils functions, 13 new TDD tests (22 total), analytics.db migrated to WAL with demo_name/player_steamid columns.

## Tasks Completed

| Task | Name | Commit | Files |
|-|-|-|-|
| 1 (RED) | Failing tests for init_db etc | 1c40448 | tests/test_db_utils.py |
| 1 (GREEN) | Implement 5+1 db_utils functions | d2f40be | db_utils.py |
| 2 | config constants + for_analysis/ | add2448 | config.py, for_analysis/.gitkeep |
| 3 | force_reprocess_demo | d2f40be | db_utils.py (included in Task 1 commit) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] engagements table not created in fresh test DB**
- **Found during:** Task 1 GREEN — test_get_next_match_id_from_engagements failed
- **Issue:** _migrate_schema only ALTER'd engagements if it already existed; fresh temp DBs had no engagements table, so INSERT in test failed
- **Fix:** Changed to `CREATE TABLE IF NOT EXISTS engagements` before ALTER TABLE checks — engagements is now always created by init_db()
- **Files modified:** db_utils.py
- **Commit:** d2f40be

**2. [Rule 2 - Missing functionality] force_reprocess_demo included in Task 1**
- Task 3 was implemented alongside Task 1 since all functions belong in db_utils.py; no separate commit needed

## Success Criteria Validation

1. `PRAGMA journal_mode` on analytics.db → `wal` — PASSED
2. Tables `processed_matches`, `duel_attempts` exist in analytics.db — PASSED
3. Columns `demo_name` and `player_steamid` in engagements (NULL for 3 old rows) — PASSED
4. `is_processed` / `mark_processed` round-trip — PASSED (test_is_processed_returns_true_after_mark)
5. `get_next_match_id` → 1 on empty DB — PASSED
6. `DEFAULT_BATCH_WORKERS == 8` importable from config — PASSED
7. `for_analysis/` directory exists — PASSED
8. `python -m pytest tests/test_db_utils.py` → 22 passed — PASSED

## Known Stubs

None.

## Threat Flags

None — all SQL uses parameterized queries; table/column names are hardcoded literals, not user input.

## Self-Check: PASSED

- db_utils.py: exists with init_db, _migrate_schema, is_processed, mark_processed, get_next_match_id, force_reprocess_demo
- config.py: DEFAULT_BATCH_WORKERS = 8
- for_analysis/.gitkeep: exists
- Commits 1c40448, d2f40be, add2448: exist in git log
- 41 tests pass (22 test_db_utils + 19 test_config)
