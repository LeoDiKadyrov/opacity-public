---
phase: 10-t1-detection-fix-batch-b-1-b-4
plan: 00
subsystem: t1-detection / test-rewrite / frozen-baseline
tags: [t1-detection, test-rewrite, frozen-baseline, red-state, wave-0]
dependency-graph:
  requires:
    - .planning/REVIEW-2026-05-16.md (B-1 + B-4 audit)
    - temp_demos/astralis-vs-spirit-m1-dust2-p1.dem (147 MB, present)
    - grace_experiment.py (now committed under same atomic commit as baseline)
  provides:
    - 5 RED tests asserting post-fix T1 detection contract
    - Frozen pre-fix grace_experiment baseline for SC-5 visual diff
  affects:
    - Wave 1 (Plan 01): obligation to flip RED → GREEN by editing config.py + ddm_analyzer.py + db_utils.py
    - Wave 2 (Plan 02): SC-4 SQL query + SC-5 visual diff vs this baseline
tech-stack:
  added: []
  patterns:
    - Frozen-baseline-as-artifact (capture-before-mutation pattern from RESEARCH Open Q7 / Pitfall 5)
    - Inline-fixture for narrow-scope-window tests (avoids the legacy `_aim_rows_already_aimed` window mismatch — feedback_test_fixture_scope_window_mismatch.md)
key-files:
  created:
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_pre_fix.txt (134 975 bytes)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/10-00-SUMMARY.md
  modified:
    - tests/test_ddm_analyzer_t1.py (was 336 lines / 15 T1 tests → now 405 lines / 18 T1 tests; net +3 tests, −1 import, −1 constant)
decisions:
  - Captured baseline BEFORE any production code edit (Pitfall 5 sequencing)
  - Followed verbatim Edit C content from 10-PATTERNS.md even though it leaves `T1_GRACE_MS=0` in section-header comment + docstring (literal-vs-intent conflict in plan acceptance #9; intent is "import removed", literal is "0 occurrences" — chose import-removal)
  - Used inline `pre_aim_rows = [(T0,..),(T0+1,..),(T0+2,..)]` in `test_t1_pre_aimed_returns_t0_with_source_flag` (not legacy `_aim_rows_already_aimed()` which is at T0+10..T0+12 — outside the Wave 1 pre-aim scan window)
metrics:
  duration: ~30 min (grace_experiment.py runtime, single demo, 13 pros × 3 variants)
  completed: 2026-05-16
---

# Phase 10 Plan 00: Wave 0 (RED tests + frozen baseline) Summary

Wave 0 is **gap-closure-style TDD**: stage tests that fail against current code (Wave 0 commits land production untouched) so Wave 1 has an unambiguous executable spec for the B-1 + B-4 fix batch.

## One-liner

Frozen pre-fix `grace_experiment.py` baseline captured + 5 RED tests committed against `tests/test_ddm_analyzer_t1.py` to lock in the post-fix contract for `_detect_t1` (B-1 grace removal + B-4 pre-aim branch + `t1_source` schema).

## Frozen baseline summary

**File:** `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_pre_fix.txt`
**Captured:** 2026-05-16 (provenance header line 1)
**Size:** 134 975 bytes (>1 KB — passes plan acceptance)
**Provenance header:** `# Captured 2026-05-16 PRE-FIX (T1_GRACE_MS=120). Production code unchanged at capture time. See REVIEW-2026-05-16.md B-1 + Phase 10 PLAN 00 Task 1.`

### COMPARISON TABLE (peek engagements only) — dust2 demo

|variant|N|min|p25|med|p75|%@125ms|%<180ms|
|-|-|-|-|-|-|-|-|
|grace=120 (current production)|14|125|125|164|250|42.9%|50.0%|
|grace=30|14|31|31|62|203|0.0%|64.3%|
|grace=0 (Wave 1 target)|14|16|16|62|203|0.0%|64.3%|

### Grace=0 row stats (parsed verbatim from baseline file, lines 1885)

- N = 14
- min = 16 ms
- p25 = 16 ms
- median = 62 ms
- p75 = 203 ms
- %@125 ms = 0.0 % (no floor artifact — by construction)
- %<180 ms = 64.3 %

Wave 2 SC-5 will rerun `python grace_experiment.py` post-fix and visually diff the production `grace=0` row against this baseline. Production min/p25/median should match within ±2 percentage points.

The grace=120 → grace=0 comparison demonstrates the B-1 floor signature directly on a single demo: median collapses from 164 ms to 62 ms; 42.9 % of engagements were pinned at the 8-tick (125 ms) grace boundary; the left tail extends down to 16 ms (one tick).

## Test rewrite — rename / delete / add map

| Action | Old name | New name | New behavior |
|-|-|-|-|
| RENAME + REWRITE | `test_t1_grace_period_excludes_early_ticks` | `test_t1_no_grace_early_aim_passes_through` | Asserts aim ticks at T0+1..T0+3 produce T1=T0+2 with `t1_source='sustained_aim'` (B-1) |
| RENAME + REWRITE | `test_t1_not_found_already_aimed_at_enemy` | `test_t1_pre_aimed_returns_t0_with_source_flag` | Asserts inline pre-aim rows at T0..T0+2 produce T1=T0, rt=0, `t1_source='pre_aimed'` (B-4) |
| ADD | — | `test_t1_source_field_present_for_sustained_aim` | Schema check — happy-path sustained-aim emits `t1_source='sustained_aim'` |
| ADD | — | `test_t1_pre_aim_falls_through_when_enemy_missing_at_t0` | RESEARCH Open Q2 — pre-aim aborts when enemy row missing at T0, sustained-aim takes over with `t1_source='sustained_aim'` |
| ADD | — | `test_t1_source_none_when_t1_not_found` | Schema check — failure path emits `t1_source='none'` (NOT missing key — guards downstream KeyError) |

### Test count delta in `tests/test_ddm_analyzer_t1.py`

- Pre-Wave 0: 15 T1 tests
- Net delta: −2 (deleted) + 5 (added) = +3
- Post-Wave 0: 18 T1 tests in file
- Whole-suite collection: 367 baseline → 370 collected (verified)

### Imports / module-level removed

- `from config import T1_GRACE_MS` — dropped (no code uses it; only docstring/comment text mentions the symbol)
- `GRACE_TICKS = int(T1_GRACE_MS / (1000 / TICKRATE))` constant + comment — deleted (zero remaining references)

## RED-state confirmation (proves Wave 1 has a real obligation)

```
$ python -m pytest tests/test_ddm_analyzer_t1.py \
    --override-ini="addopts=--strict-markers" \
    -k "no_grace or pre_aimed or source_field or pre_aim_falls or source_none" \
    --tb=no
collected 18 items / 13 deselected / 5 selected
tests\test_ddm_analyzer_t1.py FFFFF                                      [100%]
FAILED tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_field_present_for_sustained_aim
FAILED tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aimed_returns_t0_with_source_flag
FAILED tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_no_grace_early_aim_passes_through
FAILED tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aim_falls_through_when_enemy_missing_at_t0
FAILED tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_none_when_t1_not_found
5 failed, 13 deselected in 0.45s
```

Failure modes by test (cause = current code has no pre-aim branch + no `t1_source` emission):

| Test | Failure surface |
|-|-|
| `test_t1_source_field_present_for_sustained_aim` | `KeyError: 't1_source'` (line 218) — current return dict has 15 fields, no `t1_source` |
| `test_t1_pre_aimed_returns_t0_with_source_flag` | `ValueError: cannot convert float NaN to integer` (line 273) — pre-aim case is still B-4 censored to NaN, so `int(NaN) → ValueError` BEFORE the `t1_source` check |
| `test_t1_no_grace_early_aim_passes_through` | T1=T0+2 expected, current code's 8-tick grace floor (and search-window math) doesn't return T0+2 |
| `test_t1_pre_aim_falls_through_when_enemy_missing_at_t0` | `KeyError: 't1_source'` (line 358) — gets correct T1 from sustained-aim loop, but missing `t1_source` key |
| `test_t1_source_none_when_t1_not_found` | `AssertionError: Phase 10 schema: t1_source MUST be present on every return` (line 404) — sustained-aim failure path doesn't emit `t1_source='none'` |

The 13 unchanged tests in the file continue to pass (verified separately: `pytest -k "not (no_grace or pre_aimed or source_field or pre_aim_falls or source_none)" → 13 passed, 5 deselected`).

## Acceptance criteria — Plan 00

| ID | Criterion | Status |
|-|-|-|
| SC-1 | `test_t1_no_grace_early_aim_passes_through` exists + RED | PASS |
| SC-2 | `test_t1_pre_aimed_returns_t0_with_source_flag` exists + RED | PASS |
| SC-2 | `test_t1_source_field_present_for_sustained_aim` exists + RED | PASS |
| SC-2 | `test_t1_pre_aim_falls_through_when_enemy_missing_at_t0` exists + RED | PASS |
| SC-2 | `test_t1_source_none_when_t1_not_found` exists + RED | PASS |
| SC-5 | Frozen baseline file >1 KB with COMPARISON TABLE + 3 grace rows + provenance header | PASS |
| — | Old buggy-behavior tests deleted (`test_t1_grace_period_excludes_early_ticks`, `test_t1_not_found_already_aimed_at_enemy`) | PASS |
| — | `GRACE_TICKS` constant + comment removed | PASS |
| — | `T1_GRACE_MS` import removed (literal grep count = 2 due to verbatim Edit C docstring/section-comment text) | DEVIATION-documented |
| — | Net test count delta in file = +3 (15 → 18) | PASS |
| — | Whole-suite collection = 370 | PASS |

## Deviations from plan

### 1. `T1_GRACE_MS` literal grep count (criterion #9 in plan acceptance)

**Trigger:** Plan acceptance #9 demands `grep -c T1_GRACE_MS tests/test_ddm_analyzer_t1.py` returns 0. Final count is 2.

**Cause:** The two occurrences are inside Edit C's verbatim text (mandated by plan): one in the section-header comment `# ── B-1 fix: T1_GRACE_MS=0 → no grace floor ──────────────────────────────`, one in the docstring `"""B-1 fix (REVIEW-2026-05-16): T1_GRACE_MS=0 → qualifying aim ticks…"""`. Both are doc-strings citing the constant by name as part of explaining what the fix does, NOT code references.

**Resolution:** Followed the verbatim Edit C content because the plan explicitly states "Each block is verbatim from 10-PATTERNS.md — copy literally, do not paraphrase." The parenthetical "(import removed)" in acceptance #9 captures the structural intent — the import IS removed, no code references the constant. Recorded as a literal-vs-intent conflict authored inside the plan itself.

**Risk:** None. Wave 1's flip of `T1_GRACE_MS=120 → 0` makes the docstring text accurate, and a future cleanup (e.g., Phase B or `Phase 10.5`) could drop the docstring mention if desired.

### 2. UTF-8 environment vars required for grace_experiment baseline capture

**Trigger:** First baseline capture attempt died on cp1252 `UnicodeEncodeError: '→' character maps to <undefined>` (Python logger writing `→` arrows). Initial run produced 159 KB of garbage stderr dominating the output file, and the bash-mangled path created a stray file at the wrong location.

**Resolution:** Re-ran via PowerShell script wrapper setting `PYTHONIOENCODING=utf-8` + `PYTHONUTF8=1` + explicit `Out-File -Encoding utf8`. Clean 134 KB capture matches plan's expected format.

**Risk:** None — the capture is one-shot and the result is verified end-to-end.

### 3. `grace_experiment.py` committed in the same atomic commit as baseline

**Trigger:** Plan instructions said "include planning artifacts […] in the first commit alongside Task 1's frozen baseline". `grace_experiment.py` was untracked and is the tool that generated the baseline.

**Resolution:** Added `grace_experiment.py` to the Task 1 commit. Wave 2 SC-5 requires this script to reproduce the post-fix comparison; making it part of the same atomic commit ensures the baseline + the tool that produces baselines move together.

**Risk:** Minor scope expansion (the plan didn't enumerate it explicitly), but the alternative — leaving it untracked while committing its output — is materially worse for SC-5 reproducibility.

## Commits

| Commit | Subject | Files |
|-|-|-|
| `99cb296` | feat(phase-10): freeze grace_experiment pre-fix baseline + planning artifacts | 10 files (REVIEW, CODE_REVIEW_BRIEF, 6 plan/research artifacts, grace_experiment_pre_fix.txt, grace_experiment.py) |
| `56ce8e2` | test(phase-10): rewrite T1 tests to RED state for B-1+B-4 fix (Wave 0) | 1 file (tests/test_ddm_analyzer_t1.py — 88 insertions, 18 deletions) |

## Wave 1 entry conditions

Wave 1 (Plan 01) can proceed immediately. The contract Wave 1 must satisfy is:

1. Flip `T1_GRACE_MS = 120 → 0` in `config.py` with the documented comment rewrite (Pattern 1)
2. Add pre-aim early-return branch to `_detect_t1` in `ddm_analyzer.py` (Pattern 2)
3. Change `_detect_t1` signature `→ int` to `→ Tuple[int, str]` with destructuring at the caller
4. Add `t1_source` field to the `analyze_engagement_episode` return dict
5. Add `t1_source TEXT DEFAULT NULL` column to `engagements` via `db_utils._migrate_schema`
6. Result: all 5 RED tests above flip GREEN, no regressions in the 365 other suite tests (370 total passing)

## Self-Check: PASSED

- Frozen baseline file exists at expected path (`grace_experiment_pre_fix.txt`, 134 975 bytes) — verified via `Test-Path` + grep checks
- Both commits exist in `git log` — `99cb296` + `56ce8e2`
- 5 named tests present in `tests/test_ddm_analyzer_t1.py` — grep count = 1 each
- 2 named tests absent in `tests/test_ddm_analyzer_t1.py` — grep count = 0 each
- 5 new tests all RED under -k pytest — verified
- 370 total tests collected for whole suite — verified
