---
phase: OF-3-revalidation-measurability-gate
plan: "02"
subsystem: analysis-pipeline
tags: [reaction-timing, t0-backward-search, t1-lands, outcome-first, b5-fix]

# Dependency graph
requires:
  - "OF-3-01: config constants, duel_episodes timing columns, RED tests"
provides:
  - "reaction_timing.py — compute_timing: T0 backward-continuity search + T1 LANDS detector (D-01/D-03/D-05/D-06)"
  - "outcome_first.reconstruct_all_players runs timing pass per episode, writes 7 timing columns (D-08)"
  - "TARGET_REACHED_THRESHOLD locked at fixed 3.0deg via D-02 A/B + user checkpoint"
  - "of3_threshold_ab.py + of3_threshold_ab.md — A/B comparison artifact"
affects: [OF-3-03, OF-3-04]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "T0 second backward-continuity pass: find run-start of continuous visibility containing first event, capped by T0_BACKWARD_SEARCH_CAP_TICKS, cap hit -> long_visible label (never clamp)"
    - "T1 LANDS predicate: first tick angular_dist <= TARGET_REACHED_THRESHOLD sustained T1_SUSTAINED_AIM_TICKS more ticks; geometry reused from ddm_analyzer (no reimplementation)"

key-files:
  created:
    - reaction_timing.py
    - of3_threshold_ab.py
    - of3_threshold_ab.md
  modified:
    - outcome_first.py

key-decisions:
  - "D-02 LOCKED (user checkpoint 2026-06-11, response 'продолжай' = approve recommended): TARGET_REACHED_THRESHOLD stays fixed 3.0deg. A/B on spirit-vs-the-mongolz-m2-ancient (80 episodes): fixed 3.0 -> 3.2% pinning / 0 b5-class impossible rows / never_landed 21.2%; distance-scaled strictly worse (10.5% pinning, 27.5% never_landed, 0 additional impossible rows resolved). Locked rule applied, no config change needed."
  - "Old _detect_t1 + engagements path untouched (D-04/D-16) — grep guards in acceptance criteria verified"

patterns-established:
  - "A/B threshold comparison into scratch DB (never analytics.db) with locked decision rule written BEFORE the run — no moving goalposts"

requirements-completed: [SC-3 partial — T1/T0 methodology component]

# Metrics
duration: ~25min execution + checkpoint
completed: 2026-06-11
---

# Phase OF-3 Plan 02: reaction_timing.py (T0 backward + T1 LANDS) Summary

**Implemented the B-5 fix: new reaction_timing.py module with T0 backward-continuity search and T1 crosshair-LANDS detector, wired into reconstruct_all_players for ALL episodes; D-02 threshold A/B run and locked at fixed 3.0deg via user checkpoint.**

## Accomplishments
- `reaction_timing.py`: compute_timing turns all 7 OF-3-01 RED tests GREEN; T0 second backward-continuity pass (run-start, not first-ever-visible); never_visible/never_landed/long_visible label semantics (D-03/D-05/D-06)
- `outcome_first.py`: timing pass per episode inside reconstruct_all_players, selective parse_ticks window covers backward cap (_T0_SEARCH_PARSE_WINDOW_TICKS), writes 7 timing columns to duel_episodes (D-08)
- Geometry reused: get_desired_angles/angular_diff imported from ddm_analyzer, not duplicated
- Full suite GREEN: 374 passed, 4 skipped (requires_db tier-2, pre-rebatch)
- D-02 A/B: fixed 3.0 vs distance-scaled on 1 demo (80 episodes), table in of3_threshold_ab.md; fixed 3.0 wins per locked rule; 0 b5-class impossible rows (acceptance smell-test PASS)

## Task Commits

1. **Task 1: Implement reaction_timing.py (T0/T1 GREEN)** - `16b0265` (feat)
2. **Task 2: Wire timing pass into reconstruct_all_players** - `4d79748` (feat)
3. **Task 3 (prep): D-02 A/B comparison run** - `973dbc6` (feat)
4. **Task 3 (checkpoint): D-02 locked fixed 3.0** — user approved at checkpoint, config.py already at 3.0, no code change

## D-02 A/B Table (checkpoint evidence)

| Metric | Fixed 3.0deg | Distance-scaled |
|-|-|-|
| n episodes | 80 | 80 |
| n resolved (lands) | 62 | 57 |
| %@tick-quantum pinning | 3.2% | 10.5% |
| min rt_visible_to_land_ms | 0.0 | 0.0 |
| p10 rt_visible_to_land_ms | 0.0 | 31.25 |
| never_landed% | 21.2% | 27.5% |
| n b5-class impossible rows | 0 | 0 |

## Deviations from Plan

None — checkpoint resolved with the plan's default recommendation (fixed 3.0), per the locked decision rule.

## Next Phase Readiness
- OF-3-03 staged re-batch N=1→5→81 can run with the locked threshold
- Tier-2 @requires_db distribution-shape tests ready to activate post-rebatch

---
*Phase: OF-3-revalidation-measurability-gate*
*Completed: 2026-06-11*

## Self-Check: PASSED

reaction_timing.py + outcome_first.py wiring verified by executor; checkpoint approved by user; suite 374 GREEN / 4 skip.
