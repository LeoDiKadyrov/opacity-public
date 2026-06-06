---
phase: OF-2
slug: core-rebuild
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-05
---

# Phase OF-2 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|-|-|
| **Framework** | pytest |
| **Config file** | existing project pytest config (`-p no:cov` for speed) |
| **Quick run command** | `py -m pytest tests/test_outcome_first.py -p no:cov -x` |
| **Full suite command** | `py -m pytest -p no:cov` |
| **Estimated runtime** | quick ~5s / full ~60s |

---

## Sampling Rate

- **After every task commit:** Run `py -m pytest tests/test_outcome_first.py -p no:cov -x`
- **After every plan wave:** Run `py -m pytest -p no:cov`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-|-|-|-|-|-|-|-|-|-|
| (filled by planner) | — | 0 | R-1 gun-only anchor | — | N/A | unit | `pytest tests/test_outcome_first.py::test_collect_exchanges_gun_only -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | 0 | R-2 opponent from event | — | N/A | unit | `pytest tests/test_outcome_first.py::test_collect_exchanges_opponent_from_event -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | 0 | R-3 outcome correctness | — | N/A | unit | `pytest tests/test_outcome_first.py -k outcome -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | 0 | R-4 sid None-row safety | — | int64 string-path, no float64 | unit | `pytest tests/test_outcome_first.py::test_coerce_sid_none_preserves_17digit -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | 0 | R-5 multi-player split | — | N/A | unit | `pytest tests/test_outcome_first.py::test_multi_player_per_demo -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | 0 | R-6 duel_episodes DB write | — | `_ALLOWED_TABLES` whitelist updated | unit | `pytest tests/test_outcome_first.py::test_db_write_duel_episodes -x` | ❌ W0 | ⬜ pending |
| (filled by planner) | — | — | R-7 geometry-selector removed | — | N/A | integration | `py -m pytest -p no:cov` + grep for removed symbols | n/a | ⬜ pending |
| (filled by planner) | — | — | R-8 spike-baseline parity | — | N/A | integration/manual | production run on donk 81 demos vs `outcome_first_spike_results.json` | n/a | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_outcome_first.py` — RED stubs for R-1..R-6 (≥8 test functions)
- [ ] `db_utils._ALLOWED_TABLES` += `"duel_episodes"` (prerequisite for R-6 — silent-drop trap otherwise)
- [ ] `db_utils` DDL for `duel_episodes` (prerequisite for R-6)
- [ ] `config.py` constants: `UTILITY_WEAPON_NAMES`, initiator lookback ticks

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|-|-|-|-|
| Spike-baseline parity (donk 81 demos) | R-8 | needs real demo corpus, ~36min run | run production path on `for_analysis/spirit/`, compare n_episodes/won/lost/unresolved vs `outcome_first_spike_results.json` (±5% tolerance — gun-only filter reduces episodes); win-rate 40–70% band; initiator separation ≥5pp; spot-check spirit-vs-vitality-m3-dust2 won=17/lost=16 |
| Physics-bounded sanity SQL | R-8 | DB-level inspection | per-demo won≈kills, lost≈deaths (SQL in RESEARCH.md §Validation Architecture) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
