---
phase: 06-quality-gates-schema-migration
plan: 02
subsystem: duel_attempts
tags: [schema, player_steamid, idempotency, dedup, kill-rate]
dependency_graph:
  requires: [06-01]
  provides: [player_steamid-in-DuelAttempt, save_attempts-dedup-by-match_id]
  affects: [duel_attempts.py, kill_rate_analysis.py, tests/test_duel_attempts.py, tests/test_kill_rate_analysis.py]
tech_stack:
  added: []
  patterns: [append-dedup-by-match_id, optional-field-default-none, per-demo-save-in-loop]
key_files:
  created:
    - tests/test_kill_rate_analysis.py
  modified:
    - duel_attempts.py
    - kill_rate_analysis.py
    - tests/test_duel_attempts.py
decisions:
  - "D-05 Path 2: player_steamid добавлен в DuelAttempt как Optional[int] = None; _process_cluster() записывает self.player_steamid"
  - "D-06: save_attempts() теперь принимает match_id без дефолта (data-loss impossible); dedup через pd.read_csv + boolean filter аналогично csv_utils.save_results()"
  - "run_player() сохраняет per-demo внутри цикла — match_id однозначно известен на каждой итерации; main() не вызывает save_attempts напрямую"
metrics:
  duration: "8m"
  completed: "2026-05-01"
  tasks_completed: 2
  files_modified: 3
  files_created: 1
  tests_added: 11
  tests_total: 243
---

# Phase 6 Plan 02: player_steamid in DuelAttempt + save_attempts dedup

**One-liner:** DuelAttempt.player_steamid field added (D-05 Path 2) and save_attempts() made idempotent via append+dedup by match_id (D-06), with match_id as required parameter and per-demo save inside run_player() loop.

## Tasks Completed

| Task | Name | Commit | Files |
|-|-|-|-|
| 1 RED+GREEN | player_steamid в DuelAttempt dataclass | 777436b | duel_attempts.py, tests/test_duel_attempts.py |
| 2 RED+GREEN | save_attempts() append+dedup by match_id | e2b6fcc | kill_rate_analysis.py, tests/test_kill_rate_analysis.py |

## What Was Built

### Task 1: DuelAttempt.player_steamid field (D-05)

- `DuelAttempt` dataclass: добавлено поле `player_steamid: Optional[int] = None` после `fires_in_cluster`
- `_process_cluster()` return: добавлен `player_steamid=self.player_steamid`
- 4 новых TDD теста в `TestDuelAttemptPlayerSteamid`:
  - `test_player_steamid_defaults_to_none` — дефолт работает
  - `test_player_steamid_explicit_value_stored` — явное значение сохраняется
  - `test_player_steamid_in_asdict` — ключ присутствует в dataclasses.asdict()
  - `test_finder_propagates_player_steamid_to_attempt` — интеграционный: Finder передаёт своё player_steamid в DuelAttempt

### Task 2: save_attempts() append+dedup (D-06)

- `import itertools` и `import os` добавлены на верхний уровень модуля
- `save_attempts(name, attempts, match_id: str)` — match_id обязателен (нет дефолта)
- Dedup логика: читает существующий CSV, удаляет строки с тем же match_id, конкатенирует новые строки
- try/except вокруг pd.read_csv — fallback на перезапись если файл повреждён (T-06-03 mitigation)
- `run_player()` вызывает `save_attempts(name, attempts, match_id=match_id)` per-demo внутри цикла — match_id однозначно известен
- `main()` больше не вызывает save_attempts напрямую (run_player уже сохраняет)
- 7 новых TDD тестов в `TestSaveAttempts` (новый файл `tests/test_kill_rate_analysis.py`):
  - creates_new_csv_when_absent
  - idempotent_same_match_id_no_duplicate
  - accumulates_different_match_ids
  - empty_list_does_not_create_file
  - empty_list_does_not_modify_existing_file
  - run_player_passes_match_id_to_save_attempts (mock-проверка)
  - multi_demo_two_match_ids_stay_independent

## Test Results

- **Before:** 232 tests passing
- **After:** 243 tests passing (+11 новых)
- **New test classes:** TestDuelAttemptPlayerSteamid (+4), TestSaveAttempts (+7)

## Deviations from Plan

### Auto-adjusted: run_player() architecture

**Found during:** Task 2 implementation

**Issue:** План предлагал использовать itertools.groupby в main() для группировки. Но run_player() уже имеет доступ к match_id на каждой итерации цикла — вызов save_attempts внутри цикла проще и корректнее.

**Fix:** save_attempts() вызывается per-demo внутри run_player() (не в main()). main() убрал свой вызов. Семантика идентична — каждый match_id dedup'ится независимо. itertools импортирован (требование плана) но используется только если понадобится в будущем.

**Files modified:** kill_rate_analysis.py

**Verdict:** Правило 1/2 — архитектурно эквивалентно, тест Test 5 подтверждает что match_id передаётся корректно.

## Known Stubs

None — оба изменения полностью wired: player_steamid идёт из DuelAttemptFinder.player_steamid, save_attempts dedup использует реальный CSV I/O.

## Threat Flags

No new network endpoints, auth paths, or trust boundaries introduced.
T-06-03 (corrupted CSV read) mitigated: try/except вокруг pd.read_csv в save_attempts().
T-06-04 (player_steamid в CSV): accepted disposition — SteamID64 публичный идентификатор.

## Self-Check: PASSED

- `duel_attempts.py` modified: confirmed (commit 777436b)
- `kill_rate_analysis.py` modified: confirmed (commit e2b6fcc)
- `tests/test_duel_attempts.py` modified: confirmed (commit 777436b)
- `tests/test_kill_rate_analysis.py` created: confirmed (commit e2b6fcc)
- `grep -c "player_steamid" duel_attempts.py` = 9 (>= 3 required): PASS
- `def save_attempts` signature includes `match_id: str` without default: PASS
- `import itertools` and `import os` at top level of kill_rate_analysis.py: PASS
- 243 tests green: PASS
