---
phase: OF-2
plan: "00"
subsystem: outcome-first
tags: [tdd, red, test-contract, outcome-first]
dependency_graph:
  requires: []
  provides: [Wave-0 RED test contract for outcome_first module]
  affects: [tests/test_outcome_first.py]
tech_stack:
  added: []
  patterns: [TDD RED-first, synthetic DataFrames with real 17-digit SteamIDs]
key_files:
  created: [tests/test_outcome_first.py]
  modified: []
decisions:
  - Weapon filtering asserted in collect_exchanges (gun-only anchor per OF-2-CONTEXT R-1)
  - _coerce_sid test uses real 17-digit SteamIDs + None row as float64-precision regression guard
  - test_db_write_duel_episodes deliberately tests against non-whitelisted table (RED via ValueError -- OF-2-01 adds whitelist entry)
metrics:
  duration: "5 min"
  completed: "2026-06-05"
  tasks_completed: 1
  tasks_total: 1
  files_changed: 1
---

# Phase OF-2 Plan 00: Wave-0 RED Contract Summary

**One-liner:** 9-test RED contract for outcome_first module covering _coerce_sid float64-precision guard, gun-only collect_exchanges, gap/opponent-change episode splitting, and duel_episodes DB write.

## Tasks Completed

| Task | Name | Commit | Files |
|-|-|-|-|
| 1 | Write tests/test_outcome_first.py -- 9 RED tests | cf4b62a | tests/test_outcome_first.py (created) |

## Verification Results

- `py -m pytest tests/test_outcome_first.py -p no:cov --override-ini="addopts="` -- ModuleNotFoundError: No module named 'outcome_first' (RED confirmed)
- `py -m pytest -p no:cov --override-ini="addopts=" --ignore=tests/test_outcome_first.py` -- 370/370 PASS (GREEN confirmed)
- `grep -c "def test_" tests/test_outcome_first.py` -- 9
- `grep "pd.to_numeric" tests/test_outcome_first.py` -- 0 hits

## TDD Gate Compliance

RED gate: PASS (test commit cf4b62a; ModuleNotFoundError on collection).
GREEN gate: pending OF-2-01 implementation.
REFACTOR gate: N/A at this stage.

## Deviations from Plan

None -- plan executed exactly as written.

The spike's collect_exchanges does not filter by weapon (it was a proof-of-concept). The production API tested here adds gun-only filtering per the R-1 locked decision. This is expected; the test defines the production contract, not a port of the spike.

## Self-Check: PASSED

- tests/test_outcome_first.py: FOUND
- Commit cf4b62a: verified via git log
- 9 test functions, 0 pd.to_numeric hits: confirmed
- No unexpected deletions in commit
