---
phase: 06-quality-gates-schema-migration
plan: 01
subsystem: ddm_analyzer
tags: [quality-gates, overlapping-window, teammate-gate, schema, player_steamid]
dependency_graph:
  requires: []
  provides: [overlapping-window-gate, teammate-phantom-kill-gate, player_steamid-in-return-dict]
  affects: [ddm_analyzer.py, tests/test_ddm_analyzer_quality.py]
tech_stack:
  added: []
  patterns: [last_accepted_t2_tick-state, boolean-indexing-filter, optional-int-state]
key_files:
  created: []
  modified:
    - ddm_analyzer.py
    - tests/test_ddm_analyzer_quality.py
decisions:
  - "D-07: overlapping window gate implemented via last_accepted_t2_tick state in analyze_demo()"
  - "D-08: rejected moments logged as logger.warning (no --debug needed)"
  - "D-09: teammate gate uses attacker != player_steamid heuristic; team_num refinement deferred to Phase 8"
  - "D-05: player_steamid added to return dict as Path 1 schema column"
metrics:
  duration: "3m 40s"
  completed: "2026-05-01"
  tasks_completed: 3
  files_modified: 2
  tests_added: 17
  tests_total: 232
---

# Phase 6 Plan 01: Overlapping window gate, teammate gate, player_steamid in return dict

**One-liner:** Three quality gates added to DDMAnalyzer: overlapping window rejection via last_accepted_t2_tick state, teammate phantom kill rejection via _teammate_hurt_target(), and player_steamid column in analyze_engagement_episode() return dict.

## Tasks Completed

| Task | Name | Commit | Files |
|-|-|-|-|
| RED | Failing TDD tests for all 3 tasks | 6d7f10b | tests/test_ddm_analyzer_quality.py |
| 1+2+3 | Overlapping gate + teammate gate + player_steamid | d172542 | ddm_analyzer.py |

## What Was Built

### Task 1: Overlapping window gate (D-07, D-08)
- `DDMAnalyzer.__init__`: добавлен `self.last_accepted_t2_tick: Optional[int] = None`
- `analyze_demo()`: новый gate перед `results.append()` — отвергает момент если `first_hit_tick < last_accepted_t2_tick + 300`
- После принятия момента обновляет `last_accepted_t2_tick = int(first_hit)`
- NaN guard на `first_hit` перед `int()` cast (T-06-01 mitigation)
- Логирует `logger.warning("Overlapping window rejected: ...")` при rejection (D-08)

### Task 2: Teammate phantom kill gate (D-09)
- Новый приватный метод `_teammate_hurt_target(df, t0, t2, target_enemy_id) -> bool`
- Возвращает True если в [t0..t2] любой `attacker_steamid != player_steamid` нанёс урон target
- Required-columns check перед фильтрацией (T-06-02 mitigation): возвращает False если нет `tick/user_steamid/attacker_steamid`
- Вызывается в `analyze_engagement_episode()` сразу после `is_1v1_duel()`, до velocity gate
- Логирует `logger.warning("... teammate phantom kill detected ...")`

### Task 3: player_steamid в return dict (D-05 Path 1)
- В return dict `analyze_engagement_episode()` добавлена строка: `"player_steamid": self.player_steamid`
- Поле попадает в results_df и далее в CSV через `save_results()`

## Test Results

- **Before:** 215 tests passing
- **After:** 232 tests passing (+17 new)
- **New test classes:** TestOverlappingWindowGate (8 tests), TestTeammateGate (6 tests), TestAnalyzeEpisodeReturnDict (3 tests)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — all three gates are fully wired with real logic.

## Threat Flags

No new network endpoints, auth paths, or trust boundaries introduced.
Threat register T-06-01 (NaN guard) and T-06-02 (missing columns check) both mitigated as planned.

## Self-Check: PASSED

- `ddm_analyzer.py` modified: confirmed (git commit d172542)
- `tests/test_ddm_analyzer_quality.py` modified: confirmed (git commit 6d7f10b)
- `last_accepted_t2_tick` occurrences in ddm_analyzer.py: 5 (>= 3 required)
- `Overlapping window rejected` occurrences: 1
- `_teammate_hurt_target` occurrences: 2 (definition + call)
- `teammate phantom kill` occurrences: 1
- `player_steamid` in return dict at line 684: confirmed
- 232 tests green: confirmed
