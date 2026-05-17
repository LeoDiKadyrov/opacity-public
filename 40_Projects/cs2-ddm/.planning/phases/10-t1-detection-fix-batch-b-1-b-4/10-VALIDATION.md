---
phase: 10
slug: t1-detection-fix-batch-b-1-b-4
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-16
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Phase scope: BLOCKERs B-1 (T1_GRACE_MS floor) + B-4 (pre-aim censorship) from `.planning/REVIEW-2026-05-16.md`.

---

## Test Infrastructure

| Property | Value |
|-|-|
| **Framework** | pytest 7.x (configured in `pytest.ini` with `--cov`; CLAUDE.md requires `--override-ini="addopts=--strict-markers"` to bypass missing pytest-cov) |
| **Config file** | `pytest.ini` (root) |
| **Quick run command** | `python -m pytest tests/test_ddm_analyzer_t1.py --override-ini="addopts=--strict-markers" -x` |
| **Full suite command** | `python -m pytest --override-ini="addopts=--strict-markers"` |
| **Estimated runtime** | ~5s quick / ~30s full (367+ tests) |

---

## Sampling Rate

- **After every task commit:** Run quick command (~5s)
- **After every plan wave:** Run full suite command (~30s)
- **Before `/gsd-verify-work`:** Full suite green + SC-4 SQL query passes + SC-5 grace_experiment diff matches
- **Max feedback latency:** 30 seconds (full suite)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-|-|-|-|-|-|-|-|-|-|
| 10-00-01 | 00 | 0 | SC-1 (Wave 0) | — | N/A (internal data layer) | unit (rewrite) | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_no_grace_early_aim_passes_through --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (rename + rewrite) | ⬜ pending |
| 10-00-02 | 00 | 0 | SC-2 (Wave 0) | — | N/A | unit (rewrite) | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aimed_returns_t0_with_source_flag --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (rename + rewrite of test_t1_not_found_already_aimed_at_enemy) | ⬜ pending |
| 10-00-03 | 00 | 0 | SC-2 (new) | — | N/A | unit (new) | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_field_present_for_sustained_aim --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (new test) | ⬜ pending |
| 10-00-04 | 00 | 0 | SC-2 (new) | — | N/A | unit (new) | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aim_falls_through_when_enemy_missing_at_t0 --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (new test) | ⬜ pending |
| 10-00-05 | 00 | 0 | SC-2 (new) | — | N/A | unit (new) | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_source_none_when_t1_not_found --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (new test — covers `"none"` sentinel branch of t1_source) | ⬜ pending |
| 10-01-01 | 01 | 1 | SC-1 | — | N/A | unit (constant edit) | quick command + grep `T1_GRACE_MS = 0` in config.py | ❌ (config.py edit) | ⬜ pending |
| 10-01-02 | 01 | 1 | SC-2 | — | N/A | unit (algorithm) | `python -m pytest tests/test_ddm_analyzer_t1.py --override-ini="addopts=--strict-markers" -x` | ❌ (ddm_analyzer.py edit) | ⬜ pending |
| 10-01-03 | 01 | 1 | SC-2 (DB schema) | — | N/A | unit (migration) | `python -m pytest tests/test_db_utils.py --override-ini="addopts=--strict-markers" -x` + manual `PRAGMA table_info(engagements)` showing `t1_source` column | ❌ (db_utils.py edit) | ⬜ pending |
| 10-01-04 | 01 | 1 | SC-3 | — | N/A | full suite | `python -m pytest --override-ini="addopts=--strict-markers"` (must show 368+ pass) | ✅ (existing tests) | ⬜ pending |
| 10-02-01 | 02 | 2 | gate | — | N/A | manual skill | `/check-phase6` skill output reviewed against 3 known edge cases per CLAUDE.md C4 | ✅ (.claude/skills/check-phase6/) | ⬜ pending |
| 10-02-02 | 02 | 2 | SC-4 | — | N/A | manual + SQL | `python run_analysis.py` on reference demo + SC-4 SQL query (`min<125ms`, `n_at_125ms/n_total<0.10`, `n_pre_aimed==n_with_flag`) | ✅ (run_analysis.py + analytics.db) | ⬜ pending |
| 10-02-03 | 02 | 2 | SC-5 | — | N/A | manual | `python grace_experiment.py` post-fix; diff vs `grace_experiment_pre_fix.txt` shows production matches `grace=0` row | ✅ (grace_experiment.py exists) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_ddm_analyzer_t1.py` — rewrite `test_t1_grace_period_excludes_early_ticks` (rename to `test_t1_no_grace_early_aim_passes_through`); assert qualifying aim before old T0+grace boundary now produces sustained-aim hit instead of NaN. Covers SC-1.
- [ ] `tests/test_ddm_analyzer_t1.py` — rewrite `test_t1_not_found_already_aimed_at_enemy` (rename to `test_t1_pre_aimed_returns_t0`); assert pre-aim case returns `T1=T0`, `rt_visible_to_aim_ms=0`, `t1_source='pre_aimed'`. Covers SC-2 + B-4.
- [ ] `tests/test_ddm_analyzer_t1.py` — add `test_t1_source_field_present_for_sustained_aim`; assert non-pre-aim path emits `t1_source='sustained_aim'`. Covers SC-2.
- [ ] `tests/test_ddm_analyzer_t1.py` — add `test_t1_pre_aim_falls_through_when_enemy_missing_at_t0`; assert pre-aim block aborts cleanly and sustained-aim loop takes over when enemy row missing at T0. Covers fallback case from RESEARCH Open Q2.
- [ ] `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_pre_fix.txt` — save current pre-fix grace_experiment.py output as frozen baseline (per RESEARCH Open Q7) before any code edits land.

*Test framework infrastructure already exists (367 baseline pass). Only test additions/rewrites + baseline-output capture needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|-|-|-|-|
| `/check-phase6` skill gate before committing `ddm_analyzer.py` edits | CLAUDE.md C4 | Skill is a 3-edge-case checklist that requires human review of changed code semantics; not a test. | After editing `_detect_t1` and BEFORE `git commit`: invoke `/check-phase6` skill; reviewer confirms no regression on (a) T0>T2 flash, (b) overlapping windows, (c) T0 at search_start boundary. Document outcome in execution log. |
| SC-4 distribution-shape check on reference demo | ROADMAP SC-4 | Requires running the pipeline on a specific demo file (operator-side artifact) and SQL-querying analytics.db; not unit-testable. | After Wave 1: `python run_analysis.py <reference_demo>` (default: `astralis-vs-spirit-m1-dust2-p1.dem` if `spirit-vs-the-mongolz-m2-ancient.dem` unavailable per RESEARCH A3). Run SC-4 SQL from RESEARCH Code Examples; assert `min_ms < 125`, `n_at_125ms / n_total < 0.10`, `n_pre_aimed == n_with_flag`. |
| SC-5 grace_experiment.py production parity | ROADMAP SC-5 | Cross-check between in-memory experiment and production-code behavior — production run vs `grace=0` experiment row. | `python grace_experiment.py` post-fix; visual diff against `grace_experiment_pre_fix.txt` baseline. Production %@125ms distribution must match the `grace=0` row of the experiment within ±2 percentage points. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0/1 auto, Wave 2 `checkpoint:human-verify` exempt)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (quick command runs after each Wave 0/1 task; full suite at Wave 1 close)
- [x] Wave 0 covers all MISSING references (now 6 test work items: 5 tests + frozen baseline capture)
- [x] No watch-mode flags
- [x] Feedback latency < 30s (full suite ~30s, quick ~5s)
- [x] `nyquist_compliant: true` set in frontmatter (substantively complete; `wave_0_complete: false` flips to true at end of Wave 0 execution)

**Approval:** approved 2026-05-16 (planner + plan-checker reviewed; ready for execute-phase Wave 0)
