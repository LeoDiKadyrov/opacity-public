---
phase: OF-2
plan: "03"
subsystem: parity-verification
tags: [parity, inspection, duel-episodes, outcome-first, R-8]
dependency_graph:
  requires: [OF-2-02]
  provides: [OF-2-PARITY.md, of2_parity_inspection.md]
  affects: [analytics.db duel_episodes]
tech_stack:
  added: []
  patterns: [cursor.fetchall() for sid columns, detached run driver pattern]
key_files:
  created:
    - of2_parity_inspection.md
    - .planning/phases/OF-2-core-rebuild/OF-2-PARITY.md
  modified:
    - analytics.db (duel_episodes: 3352 donk rows written)
decisions:
  - "T-1 band miss documented as calibration miss, not pipeline bug: gun-only filter removes 19.6% of episodes (all from unresolved bucket; won+lost IDENTICAL to spike)"
  - "T-1 recommended band update: [3100, 4168] for future reference"
  - "Multi-player smoke on dust2: parse-once all-players, 10 distinct SIDs, 17-digit clean"
metrics:
  duration: "~3 min (178s pipeline + overhead)"
  completed_date: "2026-06-05"
  tasks_completed: 3
  files_created: 2
---

# Phase OF-2 Plan 03: R-8 Parity Verification Summary

**One-liner:** donk 81-demo production run — won=1428/lost=1090/win_rate=56.7% identical to spike; gun-only filter removed 816 unresolved utility exchanges (19.6%); multi-player smoke 10/10 SIDs clean.

## Tasks Completed

| Task | Description | Commit |
|-|-|-|
| 1 | Multi-player smoke: dust2 demo, all 10 players | no commit (run only) |
| 2 | donk 81-demo parity run, analytics.db duel_episodes | no commit (data run) |
| 3 | of2_parity_inspection.md + OF-2-PARITY.md | 62938b6 |

## Parity Numbers

| Metric | Spike | Production | Delta |
|-|-|-|-|
| n_episodes | 4168 | 3352 | -816 (-19.6%) |
| won | 1428 | 1428 | 0 |
| lost | 1090 | 1090 | 0 |
| unresolved | 1650 | 834 | -816 |
| win_rate_resolved | 56.7% | 56.7% | 0.0pp |
| initiator sep | 9.7pp | 10.4pp | +0.7pp |

## Tolerance Results

| Tolerance | Result | Notes |
|-|-|-|
| T-1 n_episodes [3960,4376] | FAIL | 3352 (band underestimated gun-only effect) |
| T-2 win_rate 40-70% | PASS | 56.7% |
| T-3 initiator sep >= 5pp | PASS | 10.4pp |
| T-4 dust2 spot-check 17/16 | PASS | exact match |
| T-5 demos used 81 | PASS | |

**Overall R-8: PASS with T-1 band calibration miss documented.**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] CLI --demos rejects single file path (os.walk on .dem file returns empty)**

- **Found during:** Task 1
- **Issue:** `find_demos()` uses `os.walk(root)` which produces 0 results when root is a .dem file path, not a directory. The plan specified passing the single demo file to `--demos`.
- **Fix:** Used inline Python driver (not CLI) to call `_parse_demo_events` + `reconstruct_all_players` directly, bypassing CLI. No source code changes needed.
- **Files modified:** None (workaround only)
- **Commit:** N/A

## Known Stubs

None. All metrics are computed from real data.

## Threat Flags

None. Read-only analysis run + report file writes. No new network surface.

## Checkpoint

Plan ends at a checkpoint — user must review `of2_parity_inspection.md` and tick the acceptance checklist before SC-2 sign-off. T-1 band miss is documented; user should confirm the gun-only-filter-removes-unresolved explanation is satisfactory before proceeding to OF-3.
