---
phase: 10-t1-detection-fix-batch-b-1-b-4
plan: 01
subsystem: t1-detection / measurement-correctness / schema-migration
tags: [t1-detection, b-1-fix, b-4-fix, schema-migration, wave-1, red-to-green]
dependency-graph:
  requires:
    - 10-00-SUMMARY.md (Wave 0 RED tests landed at commit b5cc28d)
    - tests/test_ddm_analyzer_t1.py (5 RED tests staged at commit 56ce8e2)
    - .planning/phases/10-.../grace_experiment_pre_fix.txt (commit 99cb296)
  provides:
    - config.T1_GRACE_MS = 0 (B-1 floor removed)
    - ddm_analyzer._detect_t1 returns Tuple[int, str] with pre-aim branch (B-4 censorship lifted)
    - engagements.t1_source TEXT DEFAULT NULL (audit trail for branch selection)
    - 370/370 pytest GREEN (5 Wave 0 RED flipped + 365 baseline unchanged)
  affects:
    - Wave 2 Plan 02: SC-4 single-demo validation + SC-5 grace_experiment diff
    - Phase A item 6: Full corpus re-batch (will populate t1_source for legacy 4104 rows)
tech-stack:
  added: []
  patterns:
    - Pre-aim early-return branch with per-engagement source flag (mirrors _resolve_t0 / t0_source pattern)
    - Idempotent ALTER TABLE migration via _eng_migrations tuple list
    - Defensive plumbing (T1_GRACE_MS=0 keeps `grace_ticks` calculation alive for future flips)
key-files:
  created: []
  modified:
    - config.py (3 lines deleted, 11 inserted — audit-citing comment block + value flip)
    - ddm_analyzer.py (6 lines deleted, 69 inserted — signature + pre-aim branch + sentinel returns + caller + dict)
    - db_utils.py (10 inserted — 1 migration tuple + 7-line comment block)
    - tests/test_ddm_analyzer_core.py (1-line monkeypatch return value update)
    - tests/test_ddm_analyzer_quality.py (1-line monkeypatch return value update)
decisions:
  - Tightened pre-aim gate from `>= T1_SUSTAINED_AIM_TICKS` to `>= T1_SUSTAINED_AIM_TICKS + 1` (Rule 1 fix on top of plan spec — see Deviation #1)
  - Updated 2 pre-existing `_detect_t1` monkeypatch return values from int to tuple (Rule 3 fix — see Deviation #2)
  - Kept the `T1_GRACE_MS` constant alive (value 0) per RESEARCH Pattern 1 "defensive plumbing"
metrics:
  duration: ~30 min (3 atomic commits + 1 inline algorithm bugfix discovery)
  completed: 2026-05-16
  task_count: 3
  file_count: 5
---

# Phase 10 Plan 01: T1 detection fix batch (Wave 1) Summary

Wave 1 ships the production code that flips the 5 Wave 0 RED tests GREEN. Three files modified across three atomic commits, plus two follow-on test-fixture fixes for downstream monkeypatch breakage caused by the signature change. The 125ms hard floor (B-1) is removed; the pre-aim left-tail censorship (B-4) is eliminated and tagged via the new `t1_source` enum column.

## One-liner

`T1_GRACE_MS 120→0` + `_detect_t1: Tuple[int, str]` with pre-aim early-return branch + `engagements.t1_source` schema migration → 370/370 pytest GREEN, all 5 Wave 0 RED tests flipped.

## The 4 edits applied

| Edit | File | Lines | Change |
|-|-|-|-|
| **A** | `config.py` | 122-124 → 122-132 | Value flip `T1_GRACE_MS: int = 120 → 0` + 10-line audit-citing comment block (REVIEW-2026-05-16.md B-1, 3 semantic filters, "1145 engagements pinned" evidence) |
| **B** | `ddm_analyzer.py` | 512-516 → 512-528 | `_detect_t1` signature `int → Tuple[int, str]` with 13-line docstring explaining `t1_source ∈ {sustained_aim, pre_aimed, none}` and pre-aim contract |
| **C** | `ddm_analyzer.py` | 519-557 (insert) | Pre-aim branch inserted after `aim_search_start = t0_tick + grace_ticks`, before `player_aim_ticks` slice. Uses `get_desired_angles` + `angular_diff` helpers, returns `(t0_tick, "pre_aimed")` on hit, falls through otherwise. **Rule 1 deviation:** gate uses `>= T1_SUSTAINED_AIM_TICKS + 1` (3 rows) not `>= T1_SUSTAINED_AIM_TICKS` (2 rows) — see Deviation #1. |
| **D.1** | `ddm_analyzer.py` | line 565 | Empty-window sentinel `return -1` → `return -1, "none"` |
| **D.2** | `ddm_analyzer.py` | line 618 | Sustained-aim hit `return potential_t1` → `return potential_t1, "sustained_aim"` |
| **D.3** | `ddm_analyzer.py` | line 622 | Loop-exit sentinel `return -1` → `return -1, "none"` |
| **D.4** | `ddm_analyzer.py` | line 778 | Caller destructure `t1_tick = self._detect_t1(...)` → `t1_tick, t1_source = self._detect_t1(...)` |
| **D.5** | `ddm_analyzer.py` | line 850-855 | Result dict append: `"t1_source": t1_source` with 3-line comment block (B-4 citation + enum) |
| **E** | `db_utils.py` | line 96 (insert) | `_eng_migrations` append `("t1_source", "TEXT DEFAULT NULL")` with 7-line comment block (REVIEW-2026-05-16.md B-4 + enum + legacy-NULL semantics + no-backfill note) |

## Wave 0 RED → GREEN confirmation

```
$ python -m pytest tests/test_ddm_analyzer_t1.py \
    --override-ini="addopts=--strict-markers" \
    -k "no_grace or pre_aimed or source_field or pre_aim_falls or source_none" \
    -v
collected 18 items / 13 deselected / 5 selected

tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_field_present_for_sustained_aim PASSED [ 20%]
tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aimed_returns_t0_with_source_flag PASSED [ 40%]
tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_no_grace_early_aim_passes_through PASSED [ 60%]
tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aim_falls_through_when_enemy_missing_at_t0 PASSED [ 80%]
tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_none_when_t1_not_found PASSED [100%]

====================== 5 passed, 13 deselected in 0.54s =======================
```

All 5 Wave 0 RED tests now GREEN. The 13 untouched T1 tests also remain GREEN (verified via separate run = 18 passed in 0.70s).

## Full suite count delta

| Phase | Count | Status |
|-|-|-|
| Wave 0 baseline (commit b5cc28d) | 370 | 5 RED + 365 GREEN |
| Wave 1 close (commit 0f2681e) | 370 | 370 GREEN, 0 RED |

```
$ python -m pytest --override-ini="addopts=--strict-markers"
============================= 370 passed in 6.37s =============================
```

SC-3 satisfied. Net file delta = 0 (same 370 tests in both states; only pass/fail flipped).

## Deviations from plan

### 1. Pre-aim gate tightened from `>= T1_SUSTAINED_AIM_TICKS` to `>= T1_SUSTAINED_AIM_TICKS + 1` (Rule 1)

**Trigger:** After applying Edit B verbatim per plan, 11 of 18 T1 tests failed because the pre-aim branch fired spuriously on the 2-row velocity-seed produced by `_make_ticks()`. The fixture seeds player rows at T0 and T0+1 with `yaw=0, pitch=0`; enemy at `(100, 0, 0)` makes those rows on-target by definition (dist=0 ≤ T1_NOT_AIMED_THRESHOLD=1.0). With only 2 rows in the [T0, T0+2] window, the plan's `len(pre_aim_window) >= T1_SUSTAINED_AIM_TICKS` (= 2) gate passed; `head(3)` iterated over those 2 rows; pre-aim fired. Result: every test calling `_make_ticks` with non-pre-aim semantics got T1=T0.

**Root cause:** The plan's behavior spec says "AND enemy row present at every tick in that window". The window is `[T0, T0+T1_SUSTAINED_AIM_TICKS] = [T0, T0+2]` — **3 ticks**. But the gate `>=T1_SUSTAINED_AIM_TICKS` only required 2 rows present. That allows the predicate to be silently satisfied without all 3 ticks being verifiable. The plan's `head(T1_SUSTAINED_AIM_TICKS + 1)` slicing already expected 3 rows; the gate was off-by-one.

**Fix:** Changed `if len(pre_aim_window) >= T1_SUSTAINED_AIM_TICKS:` to `if len(pre_aim_window) >= T1_SUSTAINED_AIM_TICKS + 1:` with an 8-line comment citing this deviation and the project-memory feedback file `feedback_test_fixture_scope_window_mismatch.md`.

**Verification:** All 18 T1 tests pass under tightened gate. Wave 0's pre-aim positive test (`test_t1_pre_aimed_returns_t0_with_source_flag`) provides 3 explicit aim rows at T0/T0+1/T0+2 plus 2 velocity-seed rows = 5 total in the window → `5 >= 3` → gate passes → fires correctly. Wave 0's fall-through test (`test_t1_pre_aim_falls_through_when_enemy_missing_at_t0`) omits enemy at T0 → break inside iteration → falls through correctly.

**Impact:** Algorithm now requires the player to actually be present at T0, T0+1, AND T0+2 (all 3 of the inclusive window) before pre-aim activates. Matches plan's spec wording. Stricter than plan's literal pseudocode. Fix lives in production code, not in tests.

### 2. Two pre-existing `_detect_t1` monkeypatch return values updated for new tuple signature (Rule 3)

**Trigger:** After committing Task 2 (signature change), full-suite run produced 4 unexpected failures with `TypeError: cannot unpack non-iterable int object` at the caller line. Tests `test_result_dict_includes_round_number` (1 test in test_ddm_analyzer_core.py) and `test_return_dict_contains_player_steamid_key` / `test_player_steamid_value_equals_instance_steamid` / `test_player_steamid_with_simple_id` (3 tests in test_ddm_analyzer_quality.py) all use `patch.object(analyzer, "_detect_t1", return_value=...)` with a scalar int (`-1` or `2520`).

**Fix:** Two single-line edits updating monkeypatch return values from int to tuple:
- `tests/test_ddm_analyzer_core.py:1011`: `return_value=2520` → `return_value=(2520, "sustained_aim")`
- `tests/test_ddm_analyzer_quality.py:311`: `return_value=-1` → `return_value=(-1, "none")`

**Rationale:** Pre-existing tests that aren't part of the algorithm-under-test were silently broken by the signature change. RESEARCH Pitfall 3 anticipates this exact case but only enumerates the direct caller fix (Edit D); the monkeypatched tests were not enumerated. Pattern: when a private method signature changes, all `patch.object(..., return_value=...)` references must be updated. The fix preserves each test's intent (T1 found vs not found) by selecting a tuple-shape value that round-trips correctly through `int(t1_tick) if t1_tick != -1 else np.nan` and `"t1_source": t1_source` downstream.

**Impact:** No test intent changed. No production code changed. Removes the regression introduced by Task 2 in test files outside Plan 01's stated `<files>` scope.

### 3. No `/check-phase6` skill invocation (out-of-scope per plan's Task list)

Plan 01 does not include a `/check-phase6` task. RESEARCH Pitfall 6 + C4 from CLAUDE.md lists `/check-phase6` as a constraint, but the planner scoped it into Wave 2 Plan 02 Task 10-02-01 (see VALIDATION.md Per-Task Verification Map). Wave 1 does not invoke the skill.

**Resolution:** Not a deviation — explicit deferral per phase structure. Wave 2 will run the skill before any operator-side validation.

## DB column note

`t1_source` registered via idempotent ALTER TABLE in `db_utils._migrate_schema`. Effects:

- **Fresh `analytics.db`** (created post-Wave-1): column present from inception, default NULL until pipeline emits a value.
- **Existing `analytics.db`** (4104 legacy rows pre-Wave-1): column added on next `init_db()` invocation; existing rows get NULL. Per RESEARCH Open Q3: NULL is interpretable as "legacy — sustained_aim under old grace=120 algorithm". No retroactive UPDATE in Wave 1; Phase A item 6 (full corpus re-batch, ~20h overnight, separate phase) regenerates labels from raw demos.
- **Pipeline post-Wave-1** emits one of `{"sustained_aim", "pre_aimed", "none"}` per engagement in the return dict, which `db_utils.save_to_db` writes verbatim into the new column.

Wave 2 Plan 02 SC-4 validates on ONE demo (re-analyze and SQL probe). Phase 10 itself does NOT mutate existing rows.

## Commits

| Commit | Subject | Files |
|-|-|-|
| `7b606de` | fix(config): T1_GRACE_MS 120 to 0 removes 125ms floor (B-1, Wave 1) | config.py |
| `e29d95b` | fix(ddm_analyzer): _detect_t1 pre-aim branch + t1_source schema (B-1+B-4, Wave 1) | ddm_analyzer.py |
| `0f2681e` | feat(db): t1_source column migration + full suite GREEN (Wave 1 close) | db_utils.py + 2 test files |

## Self-Check: PASSED

- `config.py` exists with `T1_GRACE_MS: int = 0` and "REVIEW-2026-05-16.md B-1" + "1145 engagements pinned" citations — verified via Python count
- `ddm_analyzer.py` exists with `Tuple[int, str]` signature, 3 sentinel returns, pre-aim branch, caller destructure, dict emit — verified via 10-criteria grep
- `db_utils.py` exists with `("t1_source", "TEXT DEFAULT NULL")` migration entry + REVIEW-2026-05-16.md B-4 citation — verified via grep
- Fresh DB has `t1_source` column — verified via `PRAGMA table_info` round-trip
- Commits `7b606de`, `e29d95b`, `0f2681e` exist on main — verified via `git log --oneline`
- 370 pytest pass, 0 fail — verified via full-suite run
- 5 Wave 0 RED tests flipped GREEN — verified via -k pytest run pasted above
