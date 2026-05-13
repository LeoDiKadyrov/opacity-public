---
phase: 8
slug: interpretation-layer
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-06
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — default discovery |
| **Quick run command** | `python -m pytest tests/test_interpretation.py -p no:cov -q` |
| **Full suite command** | `python -m pytest --override-ini="addopts=--strict-markers" -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_interpretation.py -p no:cov -q`
- **After every plan wave:** Run `python -m pytest --override-ini="addopts=--strict-markers" -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | REQ-INT-01 | — | N/A | unit | `pytest tests/test_interpretation.py::test_assign_tier_lower_is_better -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | REQ-INT-01 | — | N/A | unit | `pytest tests/test_interpretation.py::test_assign_tier_higher_is_better -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | REQ-INT-01 | — | N/A | unit | `pytest tests/test_interpretation.py::test_compute_interpretation_schema -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | REQ-INT-03 | — | N/A | unit | `pytest tests/test_interpretation.py::test_peek_hold_separate_thresholds -x` | ❌ W0 | ⬜ pending |
| 08-01-05 | 01 | 1 | REQ-INT-05 | — | N/A | unit | `pytest tests/test_interpretation.py::test_rt_bottleneck_component -x` | ❌ W0 | ⬜ pending |
| 08-01-06 | 01 | 1 | D-07 | — | N/A | unit | `pytest tests/test_interpretation.py::test_fallback_thresholds_triggered -x` | ❌ W0 | ⬜ pending |
| 08-01-07 | 01 | 1 | D-12 | — | N/A | unit | `pytest tests/test_interpretation.py::test_benchmark_small_sample_label -x` | ❌ W0 | ⬜ pending |
| 08-01-08 | 01 | 1 | D-11 | — | N/A | unit | `pytest tests/test_interpretation.py::test_player_names_lookup -x` | ❌ W0 | ⬜ pending |
| 08-01-09 | 01 | 1 | D-03 | T-08-01 | int(steamid_str) guard; no SQL injection | unit | `pytest tests/test_interpretation.py::test_player_not_in_db_returns_empty -x` | ❌ W0 | ⬜ pending |
| 08-01-10 | 01 | 1 | REQ-INT-04 | — | N/A | unit | `pytest tests/test_interpretation.py::test_rt_drill_contains_caveat_ref -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 2 | REQ-INT-01 | — | N/A | integration | `pytest tests/test_interpretation.py -k "integration" -p no:cov -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 3 | REQ-INT-02 | — | N/A | manual | Streamlit: verify summary card shows worst metric at top | N/A | ⬜ pending |
| 08-03-02 | 03 | 3 | REQ-INT-04 | — | N/A | manual | Streamlit: verify survivorship bias caption visible under RT rows | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_interpretation.py` — stubs for all 10 unit tests above
- [ ] `interpretation.py` — module skeleton must exist for imports to work

*Existing `tests/conftest.py` covers shared fixtures — no new conftest needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Summary card shows worst metric at top | REQ-INT-02 | Streamlit rendering not testable in pytest | Open app.py, enter karrigan SteamID, go to Interpretation section, verify card appears above table |
| Survivorship bias caveat inline under RT rows | REQ-INT-04 | UI caption positioning not testable in pytest | Verify `st.caption("Measured on hits only...")` appears directly under RT metric rows |
| Benchmark dropdown shows "(small sample)" suffix | D-12 | Streamlit widget state not testable | Add a player with <20 demos to analytics.db; verify dropdown label includes "(small sample)" |
| Interpretation tab with no sidebar SteamID shows info message | D-03/Pitfall 2 | UI guard behavior not testable | Open app cold, go to Interpretation, verify info message not crash |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
