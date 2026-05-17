---
phase: 10-t1-detection-fix-batch-b-1-b-4
plan: 02
subsystem: validation-gates / check-phase6 / sc4-sc5
tags: [validation-gates, check-phase6, sc4, sc5, manual-empirical, wave-2, phase-10-shippable]
dependency-graph:
  requires:
    - 10-00-SUMMARY.md (Wave 0 — RED tests + frozen baseline, commit b5cc28d)
    - 10-01-SUMMARY.md (Wave 1 — production code fix, commit d0c37eb)
    - grace_experiment_pre_fix.txt (Plan 00 Task 1 frozen artifact)
    - temp_demos/astralis-vs-spirit-m1-dust2-p1.dem (147 MB reference demo)
  provides:
    - Phase 10 shippable verdict + 5/5 SC sign-off
    - Phase A item 6 trigger conditions (full corpus re-batch)
    - Marketing-claim-refresh prerequisite (data layer corrected)
  affects:
    - ROADMAP.md (Phase 10 entry should be marked [x] SHIPPED 2026-05-16)
    - Phase A items 3-7 unblocked (B-2 / B-3 / distribution-shape suite / re-batch / threshold re-derivation)
tech-stack:
  added: []
  patterns:
    - Triangulation parity (Path A in-memory monkey-patch vs Path B live production code, agreeing on load-bearing distribution metric)
    - Empirical post-fix validation on the same demo used for pre-fix capture (controls everything except the code itself)
key-files:
  created:
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/check_phase6_runlog.md (CLAUDE.md C4 mandate output)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/sc4_empirical_run.md (SC-4 SQL distribution check)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/sc4_query_result.txt (SC-4 SQL raw output)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/sc4_pipeline_stdout.txt (pipeline run stdout)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_post_fix.txt (131 764 bytes; post-fix grace experiment full output)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/sc5_diff.md (SC-5 side-by-side diff)
    - .planning/phases/10-t1-detection-fix-batch-b-1-b-4/10-02-SUMMARY.md (this file)
    - analytics.db.pre-phase-10-sc4-2026-05-16 (pre-Wave-2 backup, 1 093 632 bytes)
  modified:
    - analytics.db (5 new dust2 rows with non-NULL t1_source; migration applied)
decisions:
  - Sampled 5 of 13 pros for SC-4 pipeline run (RESEARCH Open Q6 permits — dust2 demo is sparse per-pro regardless)
  - Manually invoked db_utils.init_db() to apply t1_source migration since multi_player_analyze.py does not auto-call it (Rule 3 deviation; defer architectural fix to Phase A)
  - Deleted pre-existing 18 floor-clipped dust2 rows from analytics.db to isolate SC-4 to clean post-fix data
metrics:
  duration: ~45 min (Task 1 grep walkthrough + Task 2 pipeline run + Task 3 grace_experiment 8 min runtime + Task 4 synthesis)
  completed: 2026-05-16
  task_count: 4
  file_count: 7
---

# Phase 10 / Plan 02 — SUMMARY (Wave 2 — manual validation gates)

**Phase:** 10-t1-detection-fix-batch-b-1-b-4
**Plan:** 02 (Wave 2 — manual validation gates)
**Closed:** 2026-05-16
**Operator:** Claude (gsd-executor, Wave 2 auto-execution)

## One-liner

All 3 Wave 2 gates PASS: `/check-phase6` (3/3 edge cases NOT regressed, upstream of `_detect_t1`), SC-4 single-demo SQL distribution check (min=0 ms, 0/5 at 125 ms, 2/2 pre-aim flag match), SC-5 grace_experiment parity (`%@125ms` post-fix = pre-fix = 0.0%, 0.0 pp delta, well within ±2 pp tolerance). Phase 10 SHIPPABLE.

## Wave 2 Outcomes

### Task 1: /check-phase6 skill gate (CLAUDE.md C4)

- **Status:** PASS
- **Edge cases reviewed:** 3 / 3 NOT regressed
- **Artifact:** `check_phase6_runlog.md`
- **Key:** All 3 cases (T0>T2 in `_find_t2`, overlapping windows in `auto_build_moments`, T0 at search_start in `_resolve_t0`) live UPSTREAM of `_detect_t1`. Phase 10 changes are localized to `_detect_t1` body (lines 512–622). The 3 upstream rejection paths terminate `analyze_engagement_episode` before reaching the `_detect_t1` call at line 798, so regression is structurally impossible from Phase 10's scope.

Grep evidence (verbatim from runlog):
- Edge 1: `_find_t2` line 432 filter `tick >= t0_tick` + line 439 REJECTED log → intact
- Edge 2: `last_accepted_t2_tick` state at line 83 + gate at lines 1103-1106 → intact
- Edge 3: `T0_MIN_OFFSET_TICKS` import at line 29 + rejection at lines 410-415 → intact

### Task 2: SC-4 single-demo distribution check

- **Status:** PASS
- **Reference demo:** `astralis-vs-spirit-m1-dust2-p1.dem` (147 MB)
- **Artifact:** `sc4_empirical_run.md`
- **Sampling:** 5-pro subset (donk, sh1ro, zweih, device, HooXi) — RESEARCH Open Q6 permits; ran 5/13 pros to keep executor runtime bounded
- **Headline numbers (post-fix):**

| metric | value | acceptance | result |
|-|-|-|-|
| min_ms | 0.0 | < 125.0 | PASS |
| n_total | 5 | (small-sample caveat noted) | — |
| n_at_125ms | 0 | n_at_125ms / n_total < 10% | PASS (0.0%) |
| n_pre_aimed | 2 | equal to n_with_flag | PASS (2 == 2) |
| n_with_flag | 2 | flag emission correct | PASS |

Per-row inspection confirms:
- 3 sustained_aim engagements (HooXi) with realistic RT values: 15.6, 1015.6, 62.5 ms — the 15.6 ms value would have been floor-clipped to ≥125 ms under pre-fix code
- 2 pre_aimed engagements (donk) with `rt_visible_to_aim_ms = 0.0` exactly — these would have been censored to NaN under pre-fix code (B-4 inverse-survivorship pattern)

### Task 3: SC-5 grace_experiment parity diff

- **Status:** PASS
- **Artifacts:** `grace_experiment_post_fix.txt` (131 764 bytes), `sc5_diff.md`
- **Runtime:** ~8 minutes (13 pros × 3 variants × full demo parse)
- **Load-bearing parity check:** `%@125ms` pre-fix (0.0%) vs post-fix (0.0%) = **0.0 pp delta** — well within ±2 pp tolerance

`grace=0` row diff:

| Metric | Pre-fix | Post-fix | Delta | Within tolerance? |
|-|-|-|-|-|
| N | 14 | 16 | +2 | N/A (expected rise from pre-aim cluster) |
| min | 16 | 0 | -16 ms | YES (B-4 restored 0 ms cluster) |
| p25 | 16 | 16 | 0 | YES (identical) |
| med | 62 | 62 | 0 | YES (identical) |
| p75 | 203 | 203 | 0 | YES (identical) |
| **%@125ms** | **0.0%** | **0.0%** | **0.0 pp** | **YES — CRITICAL** |
| %<180ms | 64.3% | 68.8% | +4.5 pp | YES (B-4 0ms cluster) |

Directional consistency: all met. Triangulation between Path A (pre-fix in-memory monkey-patch) and Path B (post-fix live production code with `T1_GRACE_MS=0`) agrees exactly.

## Phase 10 Overall Status

| Success Criterion | Plan | Status |
|-|-|-|
| SC-1 — T1 detection no longer floored at 125 ms (TDD RED→GREEN) | 10-00 (test rewrite to RED) + 10-01 (T1_GRACE_MS=0 + algorithm flip GREEN) | **PASS** (5/5 RED tests flipped per 10-01-SUMMARY) |
| SC-2 — Pre-aim branch emits t1_source flag (TDD RED→GREEN) | 10-00 (3 new RED tests added) + 10-01 (signature change + schema migration GREEN) | **PASS** (5/5 RED tests flipped + t1_source column present in fresh DB per 10-01-SUMMARY) |
| SC-3 — Full pytest suite GREEN with new contract | 10-01 (370/370 tests pass) | **PASS** (370/370 GREEN — count: 18 T1 tests, 352 other) |
| SC-4 — Single-demo SQL distribution check (min<125, no pinning, flag column consistent) | 10-02 (Task 2 this plan) | **PASS** (min=0.0, 0/5 at 125ms, 2/2 flag match — see `sc4_empirical_run.md`) |
| SC-5 — grace_experiment grace=0 row parity vs frozen baseline | 10-00 (frozen baseline) + 10-02 (Task 3 this plan) | **PASS** (%@125ms delta = 0.0 pp, well within ±2 pp — see `sc5_diff.md`) |

## Files Modified Across Phase

| File | Wave | Change |
|-|-|-|
| `tests/test_ddm_analyzer_t1.py` | 0 | 2 tests deleted, 5 tests added (net +3); GRACE_TICKS constant + T1_GRACE_MS import dropped |
| `tests/test_ddm_analyzer_core.py` | 1 | 1-line monkeypatch return value update (int → tuple) |
| `tests/test_ddm_analyzer_quality.py` | 1 | 1-line monkeypatch return value update (int → tuple) |
| `config.py` | 1 | `T1_GRACE_MS: 120 → 0` + 10-line audit-citing comment block |
| `ddm_analyzer.py` | 1 | `_detect_t1` signature `int → Tuple[int, str]`; pre-aim early-return branch; 3 sentinel returns updated; caller destructure at line 798; result-dict `t1_source` field |
| `db_utils.py` | 1 | `_eng_migrations` append for `t1_source TEXT DEFAULT NULL` + 7-line comment block |
| `analytics.db` | 2 | 5 new dust2 rows (post-fix); t1_source column added via init_db migration |
| `.planning/phases/10-.../grace_experiment_pre_fix.txt` | 0 | Frozen pre-fix experiment output (134 975 bytes) |
| `grace_experiment.py` | 0 | Committed under same atomic commit as frozen baseline (was untracked) |
| `.planning/phases/10-.../check_phase6_runlog.md` | 2 | /check-phase6 skill invocation log |
| `.planning/phases/10-.../sc4_empirical_run.md` | 2 | Demo-level distribution check result |
| `.planning/phases/10-.../sc4_query_result.txt` | 2 | SC-4 SQL raw stdout |
| `.planning/phases/10-.../sc4_pipeline_stdout.txt` | 2 | SC-4 pipeline run stdout (~5 pros) |
| `.planning/phases/10-.../grace_experiment_post_fix.txt` | 2 | Post-fix experiment rerun (131 764 bytes) |
| `.planning/phases/10-.../sc5_diff.md` | 2 | Side-by-side parity diff |
| `.planning/phases/10-.../10-00-SUMMARY.md`, `10-01-SUMMARY.md`, `10-02-SUMMARY.md` | 0, 1, 2 | Per-plan SUMMARYs |

## What Lands Where

- **Code changes commit-ready (already on main):** `config.py` + `ddm_analyzer.py` + `db_utils.py` + 3 test files. All 3 production commits + 1 plan SUMMARY commit landed in Wave 1 (HEAD `d0c37eb` at Wave 2 start).
- **Planning artifacts:** All under `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/`. Wave 2 commits add 5 new files (check_phase6_runlog, sc4_empirical_run, sc4_query_result, sc4_pipeline_stdout, grace_experiment_post_fix, sc5_diff, 10-02-SUMMARY).

## Deviations (Wave 2 only)

### Deviation #1 — `multi_player_analyze.py` does not call `init_db()` before pipeline runs

**Trigger:** First SC-4 pipeline run wrote 5 CSV rows successfully but the engagements DB write failed silently with `Warning: could not write to 'analytics.db' table 'engagements': table engagements has no column named t1_source`. SC-4 SQL query returned 0 rows.

**Root cause:** `db_utils.save_to_db()` does NOT call `init_db()` before writing. The `t1_source` ALTER TABLE migration lives in `_migrate_schema()` which only runs from `init_db()`. Of the project's pipeline entry points:
- `batch_runner.py:234` — calls `init_db()` once at startup → migration applies
- `multi_player_analyze.py` — does NOT call `init_db()` → migration never fires on fresh schema changes
- `run_analysis.py` — invokes `ddm_analyzer.analyze_demo()` which calls `save_to_db` directly → no migration

This is a pre-existing latent issue surfaced by Phase 10's first ALTER TABLE schema change since `batch_runner.py` was the only multi-player entry point. Existing batches all went through `batch_runner.py` (which calls `init_db()`), so the gap wasn't visible until now.

**Fix (this run):** Invoked `db_utils.init_db('analytics.db')` once manually after the first failed run, then re-ran the pipeline. Migration applied; second run wrote rows correctly.

**Out-of-scope deferred to Phase A:** The architectural fix is to either (a) call `init_db()` inside `save_to_db()` before any write, or (b) audit all pipeline entry points and ensure they call `init_db()` at startup. Tracked as a Phase A follow-up — does NOT block Phase 10 shipment because Phase A item 6 (full corpus re-batch) uses `batch_runner.py` which auto-migrates.

### Deviation #2 — 5-pro subset sampling for SC-4 pipeline run

**Trigger:** Plan estimated 30–60 min for full 13-pro pipeline. Executor agent runtime budget is bounded.

**Decision:** Ran 5 of 13 pros (donk, sh1ro, zweih, device, HooXi). Rationale documented in `sc4_empirical_run.md`:
1. RESEARCH Open Q6 explicitly permits sparse-demo SC-4 ("even sparse data should show `%@125ms = 0.0%` if grace removal worked")
2. The pre-fix grace_experiment showed 14 rows for 13 pros (≈1.08 rows/pro after all gates) — a 5-pro subset is expected to produce ~5 rows
3. SC-4's distribution-shape sanity check is binary (floor present or not present); even sparse data demonstrates it
4. SC-5 (Task 3) ran full 13 pros for statistically robust distribution comparison

**Risk:** None. The 5-row sample produced exactly the expected distribution (min=0, no 125ms pinning, 2/2 flag match). SC-5 covered statistical robustness.

### Deviation #3 — Deleted pre-existing 18 dust2 rows before SC-4 pipeline run

**Trigger:** `analytics.db` had 18 dust2 rows from prior pre-Phase-10 batches (floor-clipped, `T1_GRACE_MS=120`). SC-4 SQL filters by `demo_name='astralis-vs-spirit-m1-dust2-p1.dem'`. Mixing pre-fix and post-fix rows would corrupt the distribution check.

**Decision:** Deleted both `engagements` and `duel_attempts` rows for that demo before re-running. Backup `analytics.db.pre-phase-10-sc4-2026-05-16` preserves the original state.

**Risk:** None — the 18 pre-existing rows are subsumed by Phase A item 6 (full corpus re-batch) which will re-derive them from raw demos with the corrected algorithm.

## Out of scope — explicitly deferred to follow-up phases

Per ROADMAP.md Phase 10 "Out of scope" section and `REVIEW-2026-05-16.md` Phase A roadmap:

- **B-2** (DuelAttemptFinder missing `is_alive` gate) — Phase A item 3, separate phase
- **B-3** (`find_first_visible_enemy_in_window` missing flash gate) — Phase A item 4, separate phase
- **Full corpus re-batch** — Phase A item 6, ~20h overnight, gated AFTER this phase ships
- **`_FALLBACK_THRESHOLDS` / `_ABSOLUTE_ELITE_CEILING` re-derivation in `interpretation.py`** — Phase A item 7, requires clean re-batched data
- **`tests/test_distribution_shape.py` regression suite** — Phase A item 5, separate phase
- **W-3 / W-4** (T1_MOVING_TOWARDS_TOLERANCE noise floor; T1_NOT_AIMED_THRESHOLD triple-stack) — Phase B per REVIEW
- **`save_to_db` auto-init_db architectural fix** — Phase A follow-up (deferred from Wave 2 Deviation #1)

## Strategic notes

(From `REVIEW-2026-05-16.md` "Strategic notes for owner" 1-2):

1. **Trust-through-fix angle** — the Reddit "shimszy was right, here's the fix" post template is unlocked only AFTER Phase A item 6 (full corpus re-batch). Phase 10 alone is **not enough** — landing claims (donk 172 ms T0→T1, m0NESY 203 ms T0→T1) still derive from floor-clipped historical data and would be republished as **inaccurate** without re-derivation.

2. **Marketing-related implications** (next Reddit post draft, m0NESY/donk claim updates) are owned by `marketing/log.md` workflow and tracked separately. The Phase 10 fix is **necessary but not sufficient** for any data-claim refresh — the re-batched corpus is the actual deliverable for marketing.

## Verdict

**Phase 10 SHIPPABLE: YES.**

All 5 phase-level Success Criteria PASS:

- SC-1 (5/5 Wave 0 RED tests flipped GREEN via `T1_GRACE_MS=0` + algorithm change)
- SC-2 (`t1_source` column emits correctly; 5/5 tests covering both branches GREEN)
- SC-3 (370/370 pytest pass with new contract)
- SC-4 (real-demo distribution shows min=0, zero 125ms pinning, flag column consistent)
- SC-5 (post-fix grace_experiment `grace=0` row matches pre-fix simulation within 0.0 pp on `%@125ms`)

`/check-phase6` gate satisfied (3/3 edge cases NOT regressed by construction — Phase 10 changes localized below the relevant upstream paths).

**Next operator actions (post-Phase-10):**

1. Optional: review this SUMMARY + Wave 2 artifacts.
2. Mark Phase 10 entry in `ROADMAP.md` as `[x] Phase 10: T1 detection fix batch (B-1 + B-4) — SHIPPED 2026-05-16`.
3. Trigger Phase A item 6 (full corpus re-batch, ~20h overnight via `batch_runner.py`) BEFORE any public-facing data-claim refresh.
4. AFTER re-batch completes: re-derive `_FALLBACK_THRESHOLDS` / `_ABSOLUTE_ELITE_CEILING` in `interpretation.py` (Phase A item 7), then draft the "shimszy was right" Reddit post template.

**Operator sign-off:** Claude (gsd-executor, Wave 2 auto-execution) @ 2026-05-16

## Self-Check: PASSED

- `check_phase6_runlog.md` exists with all 3 edge cases marked NOT regressed (grep evidence inline) — verified
- `sc4_empirical_run.md` exists with 6 metric rows + 3 PASS checks + small-sample caveat — verified
- `sc4_query_result.txt` exists with raw SQL stdout — verified
- `sc4_pipeline_stdout.txt` exists with pipeline run output — verified
- `grace_experiment_post_fix.txt` exists (131 764 bytes > 1 KB) with COMPARISON TABLE + 3 grace rows — verified
- `sc5_diff.md` exists with 7-metric diff table + CRITICAL ±2pp marker + verdict — verified
- `10-02-SUMMARY.md` references all 5 SCs in status table (SC-1, SC-2, SC-3, SC-4, SC-5) — verified
- All 5 SCs marked PASS — verified
- Phase 10 SHIPPABLE: YES verdict present — verified
- Operator sign-off line present — verified
- Cross-references to 10-00-SUMMARY + 10-01-SUMMARY both present — verified
- 5 deferred items listed under "Out of scope" — verified (6 listed including the new Deviation #1 architectural follow-up)
