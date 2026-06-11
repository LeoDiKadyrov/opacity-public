---
phase: OF-3
slug: revalidation-measurability-gate
status: planned
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-10
---

# Phase OF-3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|-|-|
| **Framework** | pytest (365 tests GREEN as of OF-2 close) |
| **Config file** | pytest.ini (note: `requires_db` marker must be registered in Wave 0) |
| **Quick run command** | `py -m pytest --override-ini="addopts=--strict-markers" -q <target test file>` |
| **Full suite command** | `py -m pytest --override-ini="addopts=--strict-markers" -q` |
| **Estimated runtime** | ~60 seconds full suite |

---

## Sampling Rate

- **After every task commit:** Run quick command on the touched test file
- **After every plan wave:** Run full suite
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 90 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-|-|-|-|-|-|-|-|-|-|
| OF-3-01-01 | 01 | 1 | D-13, D-15 | — | N/A | unit | `py -m pytest tests/test_db_utils.py --override-ini="addopts=--strict-markers" -q` | ✅ | ⬜ pending |
| OF-3-01-02 | 01 | 1 | D-01, D-05 (RED) | — | N/A | unit | `py -m pytest tests/test_reaction_timing.py --override-ini="addopts=--strict-markers" -q` | ❌ W0 | ⬜ pending |
| OF-3-01-03 | 01 | 1 | D-15 tier-1 | — | N/A | unit | `py -m pytest tests/test_db_utils.py tests/test_distribution_shape.py -m "not requires_db" --override-ini="addopts=--strict-markers" -q` | ❌ W0 | ⬜ pending |
| OF-3-02-01 | 02 | 2 | D-05, D-06 | — | N/A | unit | `py -m pytest tests/test_reaction_timing.py --override-ini="addopts=--strict-markers" -q` | ❌ W0 | ⬜ pending |
| OF-3-02-02 | 02 | 2 | D-01, D-03, D-08 | — | N/A | unit | `py -m pytest tests/test_reaction_timing.py --override-ini="addopts=--strict-markers" -q` | ❌ W0 | ⬜ pending |
| OF-3-02-03 | 02 | 2 | D-02 checkpoint | — | N/A | manual | — (checkpoint:human-verify) | — | ⬜ pending |
| OF-3-03-01 | 03 | 3 | D-14 (N=1 smoke) | — | N/A | integration | driver run + distribution-shape SQL grep | — | ⬜ pending |
| OF-3-03-02 | 03 | 3 | D-14 (N=5 + inspection) | — | N/A | integration | inspection generator run, physics-bounded column grep | — | ⬜ pending |
| OF-3-03-03 | 03 | 3 | D-14 checkpoint | — | N/A | manual | — (checkpoint:human-verify, user reviews inspection) | — | ⬜ pending |
| OF-3-03-04 | 03 | 3 | D-15 tier-2 | — | N/A | integration | `py -m pytest tests/test_distribution_shape.py -m requires_db --override-ini="addopts=--strict-markers" -q` | ❌ W0 | ⬜ pending |
| OF-3-04-01 | 04 | 4 | D-10 checkpoint | — | N/A | manual | — (checkpoint:decision, thresholds locked pre-run) | — | ⬜ pending |
| OF-3-04-02 | 04 | 4 | D-09, D-12 | — | N/A | integration | `py of3_gate.py --gate A/B --db analytics.db` | — | ⬜ pending |
| OF-3-04-03 | 04 | 4 | D-11 checkpoint | — | N/A | manual | — (checkpoint:decision, Gate-B verdict routing) | — | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_reaction_timing.py` — RED stubs for new T1 LANDS predicate + T0 backward search (TDD convention; OF-2 precedent 9 RED tests)
- [ ] `tests/test_distribution_shape.py` — synthetic-tier stubs (tick-quantum pinning, never_landed/never_visible labels)
- [ ] `pytest.ini` — register `requires_db` marker (does not exist yet)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|-|-|-|-|
| N=5 inspection artifact review | D-14 | Trust-but-verify checkpoint; physics-bounded columns reviewed by user | User reviews inspection .md before 81-demo run |
| Gate threshold pre-run approval | D-10 | Gate numbers locked with user checkpoint BEFORE gate run | Present Gate-A/Gate-B thresholds + rationale; user approves |
| Gate-B FAIL decision | D-11 | STOP + checkpoint; user decides park / win-rate-only / iterate | Present verdict, await decision |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (checkpoints exempt)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_reaction_timing.py, test_distribution_shape.py, requires_db marker)
- [x] No watch-mode flags
- [x] Feedback latency < 90s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-10 (plan-checker PASS, 0 blockers)
