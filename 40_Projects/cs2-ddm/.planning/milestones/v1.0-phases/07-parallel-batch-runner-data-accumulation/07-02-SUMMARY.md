---
phase: 07-parallel-batch-runner-data-accumulation
plan: "02"
subsystem: batch-runner
tags: [batch, multiprocessing, ProcessPoolExecutor, idempotency, windows-spawn]

dependency_graph:
  requires: ["07-01"]
  provides: ["batch_runner.py", "analyze_demo_worker", "BatchRunner"]
  affects: ["app.py (07-03 will wire BatchRunner into Streamlit UI)"]

tech_stack:
  added: ["concurrent.futures.ProcessPoolExecutor"]
  patterns: ["top-level worker function for Windows spawn", "pre-assigned match_ids to avoid race conditions", "log-and-continue error isolation"]

key_files:
  created:
    - batch_runner.py
    - tests/test_batch_runner.py
  modified: []

decisions:
  - "Worker imports DDMAnalyzer internally to avoid pickling issues (Windows spawn requires top-level function + picklable args)"
  - "match_ids pre-assigned in main thread via pre_assign_match_ids() before pool.submit() — prevents SELECT MAX race conditions"
  - "WAL pragma skipped for :memory: db_path in worker (avoids spurious failure in tests)"
  - "progress_callback wrapped in try/except — UI callback crash must never abort the runner"

metrics:
  duration: "~20 minutes"
  completed: "2026-05-05"
  tasks_completed: 1
  tasks_total: 1
  files_created: 2
  files_modified: 0
  tests_added: 16
  tests_total: 285
---

# Phase 7 Plan 02: Batch Runner (analyze_demo_worker + BatchRunner) Summary

**One-liner:** Top-level ProcessPoolExecutor worker + BatchRunner class with pre-assigned match_ids, idempotency filter, and log-and-continue error isolation for Windows spawn.

## Tasks Completed

| Task | Name | Commit | Files |
|-|-|-|-|
| RED | Failing tests for worker + BatchRunner | 6a20241 | tests/test_batch_runner.py |
| GREEN | Implement batch_runner.py | 29b922d | batch_runner.py |

## What Was Built

`batch_runner.py` provides two public APIs:

**`analyze_demo_worker(args)`** — top-level picklable function for ProcessPoolExecutor:
- Args tuple: `(demo_path, player_steamid, match_id, db_path, tickrate)` — all primitives
- Instantiates DDMAnalyzer inside the worker process (avoids pickling)
- Returns `{status, match_id, demo, engagements, attempts}` on success
- Returns `{status: "error", traceback: ...}` on any exception — never raises
- Calls `mark_processed()` after all writes succeed (D-10)

**`BatchRunner`** class:
- `scan_demos(dir)`: sorted `.dem` glob, creates dir if missing
- `filter_unprocessed(demos, steamid, force)`: skips already-processed via `is_processed()`; force=True deletes prior rows (D-12)
- `pre_assign_match_ids(demos)`: sequential IDs from `get_next_match_id()` in main thread
- `run(demos, steamid, ...)`: `init_db` → filter → pre-assign → `ProcessPoolExecutor.submit` → log results → `progress_callback`

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

- RED gate: commit `6a20241` — `test(07-02): add failing tests for analyze_demo_worker + BatchRunner`
- GREEN gate: commit `29b922d` — `feat(07-02): implement batch_runner.py`
- All 16 new tests pass; 285 total (no regressions)

## Known Stubs

None — no hardcoded empty values or placeholder text.

## Threat Flags

None — no new network endpoints or auth paths introduced. T-07-04 (path injection) mitigated: `Path(demo_path).stem` for demo_name, only parameterized SQLite queries used.

## Self-Check: PASSED

- `batch_runner.py` exists: FOUND
- `tests/test_batch_runner.py` exists: FOUND
- RED commit 6a20241: FOUND
- GREEN commit 29b922d: FOUND
- 285 tests pass, no regressions
