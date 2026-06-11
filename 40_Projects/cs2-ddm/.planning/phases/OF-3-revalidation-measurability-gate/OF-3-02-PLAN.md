---
phase: OF-3
plan: "02"
type: tdd
wave: 2
depends_on: ["OF-3-01"]
files_modified:
  - reaction_timing.py
  - outcome_first.py
  - config.py
autonomous: false
requirements: [SC-3]
user_setup: []
must_haves:
  truths:
    - "T1 = crosshair LANDS within TARGET_REACHED_THRESHOLD, sustained; a 30deg flick never yields T1=T0+1 (D-01, kills B-5)"
    - "Crosshair never reaches threshold -> t1_source='never_landed', T1=NULL, row kept (D-03)"
    - "T0 = start of the continuous visibility run containing the first event; cap hit -> 'long_visible' label, never a clamp (D-05)"
    - "Enemy never visible -> t0_source='never_visible', T0=NULL, row kept (D-06)"
    - "Timing computed for ALL episodes incl. unresolved (D-08)"
    - "D-02 threshold A/B (fixed 3.0 vs distance-scaled) resolved on 1 demo by distribution shape"
    - "D-04: old _detect_t1 + engagements timing path DEPRECATED, untouched — new detector lives only in reaction_timing.py (grep guard enforced)"
    - "D-07: correctness first, no upfront BVH optimization (share/cache) — profile on staged run; optimize only if 81-demo re-batch impractical"
  artifacts:
    - path: "reaction_timing.py"
      provides: "compute_timing: T0 backward search wrapper + T1 LANDS detector (D-01,D-03,D-05,D-06)"
      contains: "def compute_timing"
      min_lines: 80
    - path: "outcome_first.py"
      provides: "per-episode timing pass wired into reconstruct_all_players before save_to_db (D-08)"
      contains: "compute_timing"
  key_links:
    - from: "outcome_first.reconstruct_all_players"
      to: "reaction_timing.compute_timing"
      via: "per-episode call after group_episodes, before save_to_db; parse_ticks window sized to _T0_SEARCH_PARSE_WINDOW_TICKS"
      pattern: "compute_timing\\("
    - from: "reaction_timing.compute_timing"
      to: "t0_detector.find_t0"
      via: "backward search search_start=first_event_tick - cap, then second backward-continuity pass"
      pattern: "find_t0\\("
    - from: "reaction_timing.compute_timing"
      to: "ddm_analyzer.get_desired_angles"
      via: "reused geometry for angular_dist (no reimplementation)"
      pattern: "get_desired_angles|angular_diff"
---

<objective>
Implement `reaction_timing.py` to turn the RED tests from OF-3-01 GREEN: a T0 backward-search wrapper around `find_t0` (D-05) and the new T1 "crosshair LANDS" detector (D-01) that kills B-5. Wire it into `outcome_first.reconstruct_all_players` as a per-episode timing pass (D-08), with a `parse_ticks` window sized to cover the backward search cap (Pitfall 2). Run the D-02 threshold A/B comparison on one demo and lock the chosen `TARGET_REACHED_THRESHOLD` value.

Purpose: This is the methodology-revival core (user mandate: «выбирай то, что считаешь, что реально исправит ситуацию и оживит проект»). The new predicate must produce 0 rows of the b5_smoking_gun class (1-tick T1 at large crosshair angle).
Output: `reaction_timing.py`, wired `outcome_first.py`, a locked `TARGET_REACHED_THRESHOLD`, the D-02 A/B comparison table, and a GREEN suite.

CHECKPOINT: this plan is `autonomous: false` because Task 3 contains a `checkpoint:human-verify` on the D-02 A/B distribution-shape result before the constant is locked for the OF-3-03 staged re-batch.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-01-SUMMARY.md
@b5_smoking_gun.md

<interfaces>
Implement EXACTLY the contract the OF-3-01 RED tests import:

reaction_timing.compute_timing(episode: Dict, ticks_df: pd.DataFrame, t0_detector,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None) -> Dict
  episode keys used: player_steamid, opponent_steamid, first_event_tick (==T2), last_event_tick
  returns snake_case keys = NEW duel_episodes columns:
    t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg,
    rt_visible_to_land_ms, rt_visible_to_hit_ms
  t0_source ∈ {"BVH+AABB","long_visible","never_visible"}; t1_source ∈ {"lands","never_landed","no_t0"}

REUSE (do NOT reimplement / do NOT edit these files):
  t0_detector.find_t0(all_ticks_df, player_steamid, enemy_steamid, search_start_tick,
      search_end_tick, active_smokes=None, flash_intervals=None, ticks_by_sid=None) -> (Optional[int], str)
  t0_detector.is_visible(...) / find_visible_enemies_at_tick(...) for the second backward-continuity pass
  ddm_analyzer.DDMAnalyzer.get_desired_angles(px,py,pz,ex,ey,ez) -> (pitch, yaw)  [staticmethod]
  ddm_analyzer.DDMAnalyzer.angular_diff(a1,a2) -> signed [-180,180]  [staticmethod]
  outcome_first._coerce_sid  (for any sid handling)
  config: TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS, _T0_SEARCH_PARSE_WINDOW_TICKS, T1_SUSTAINED_AIM_TICKS

DEPRECATED — DO NOT edit or import from: ddm_analyzer._detect_t1, config.T0_MIN_OFFSET_TICKS, config.T0_TO_T2_MAX_TICKS (old engagement-window framing, D-04/D-16).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Implement reaction_timing.py — T0 backward search + T1 LANDS detector</name>
  <files>reaction_timing.py</files>
  <read_first>
    - tests/test_reaction_timing.py (the RED contract this task must satisfy — read it fully; the tests ARE the spec)
    - t0_detector.py (lines 75-260: find_t0, is_visible, find_visible_enemies_at_tick — the primitives to wrap; understand the smoke/flash suppression args)
    - ddm_analyzer.py (lines 105-122: get_desired_angles, angular_diff — import & call, do not duplicate)
    - outcome_first.py (lines 1-61: import style, _coerce_sid; lines 240-339: parse + reconstruct loop for integration context)
    - config.py (the OF-3 constants added in OF-3-01)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md (Pattern 1 steps 1-4, Pattern 2 predicate, Pitfall 3 second-pass requirement)
  </read_first>
  <behavior>
    Make every test in tests/test_reaction_timing.py and TestSyntheticDistributionShape GREEN:
    - flick 30deg@T0 -> t1_tick != t0_tick+1
    - pre-aimed@T0 -> t1_tick == t0_tick, t1_source == "lands"
    - never lands -> t1_tick None, t1_source "never_landed"
    - backward run start (not first-ever-visible) -> t0_tick == run-start B
    - cap hit -> t0_source "long_visible", t0_tick == first_event_tick - cap (no clamp)
    - never visible -> t0_tick None, t0_source "never_visible", t1_source "no_t0"
    - rt columns derived via MS_PER_TICK=15.625
  </behavior>
  <action>
Create `reaction_timing.py`. Module skeleton (imports per PATTERNS analog):

```python
from __future__ import annotations
import logging
import math
from typing import Dict, Optional, Tuple
import pandas as pd
from config import (
    TARGET_REACHED_THRESHOLD,
    T0_BACKWARD_SEARCH_CAP_TICKS,
    T1_SUSTAINED_AIM_TICKS,
)
from ddm_analyzer import DDMAnalyzer

logger = logging.getLogger(__name__)
MS_PER_TICK = 1000.0 / 64.0  # 15.625
```

**T0 backward search (D-05, Pattern 1 + Pitfall 3):**
1. `search_start = first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS`, `search_end = first_event_tick`.
2. Call `t0_detector.find_t0(ticks_df, player_sid, opponent_sid, search_start, search_end, ticks_by_sid=ticks_by_sid)` (pass smoke/flash args through if the caller provides them; for the unit tests a stub detector supplies these — accept `**kwargs` or explicit optionals so both work).
3. If returns `(None, _)` → `t0_tick=None`, `t0_source="never_visible"` (D-06). Skip T1 (set `t1_source="no_t0"`, `t1_tick=None`).
4. Else `t0_candidate` found. **Second backward-continuity pass (Pitfall 3 — the genuinely new code):** starting from `first_event_tick`, walk BACKWARD tick-by-tick (or via repeated `is_visible`/`find_visible_enemies_at_tick` checks) while the opponent stays continuously visible, until visibility breaks OR `search_start` is reached. The earliest still-visible tick in that unbroken run = the real `t0_tick`.
   - If the run reaches `search_start` (the cap) → `t0_source="long_visible"`, `t0_tick=search_start` (label, NOT a clamp masquerading as measurement).
   - Else → `t0_source="BVH+AABB"`, `t0_tick=run_start`.
   - NOTE: this must return the start of the run CONTAINING first_event_tick, NOT the first-ever-visible tick (that's what `find_t0`'s forward scan would give). The unit test `test_t0_backward_run_start_not_first_visible` pins this exactly.

**T1 LANDS detector (D-01/D-02/D-03, Pattern 2):**
For each tick t in `[t0_tick, first_event_tick]`: compute desired (pitch,yaw) via `DDMAnalyzer.get_desired_angles(player xyz at t, enemy xyz at t)`, then `angular_dist(t) = hypot(angular_diff(yaw_actual, yaw_desired), angular_diff(pitch_actual, pitch_desired))`.
  - `on_target(t) = angular_dist(t) <= TARGET_REACHED_THRESHOLD`.
  - `t1_tick` = first t such that `on_target(t), on_target(t+1), ..., on_target(t + T1_SUSTAINED_AIM_TICKS)` are ALL true (window = `T1_SUSTAINED_AIM_TICKS + 1` = 3 ticks total — the off-by-one lesson from Phase 10; the inclusive `[t0,first_event]` upper bound naturally covers the pre-aimed@T0 case with no separate branch).
  - If found → `t1_source="lands"`. If never → `t1_tick=None`, `t1_source="never_landed"` (D-03).

**crosshair_angle_at_t0_deg:** the `angular_dist` evaluated AT `t0_tick` (physics-bounded inspection column, B-5 post-mortem rule). NULL when t0 is None.

**Derived RT:** `rt_visible_to_land_ms = (t1_tick - t0_tick) * MS_PER_TICK` (None if either None); `rt_visible_to_hit_ms = (first_event_tick - t0_tick) * MS_PER_TICK` (None if t0 None).

**Return** the dict with all 7 snake_case keys. **Never raise** — wrap the body in try/except (model on outcome_first.py:333-337); on failure return all-NULL with `t0_source="error"`, `t1_source="error"` so the row is still written (label-not-drop). Use strict typing hints (Tuple/Dict/Optional).
  </action>
  <verify>
    <automated>py -m pytest tests/test_reaction_timing.py tests/test_distribution_shape.py -m "not requires_db" --override-ini="addopts=--strict-markers" -q</automated>
  </verify>
  <acceptance_criteria>
    - `py -m pytest tests/test_reaction_timing.py --override-ini="addopts=--strict-markers" -q` → all >=7 tests PASS (GREEN)
    - `grep -n "def compute_timing" reaction_timing.py` returns a match with typed signature
    - `grep -n "get_desired_angles\|angular_diff" reaction_timing.py` shows geometry is REUSED (imported from ddm_analyzer), not redefined: `grep -c "def get_desired_angles\|def angular_diff" reaction_timing.py` == 0
    - `grep -n "_detect_t1\|T0_MIN_OFFSET_TICKS\|T0_TO_T2_MAX_TICKS" reaction_timing.py` returns NOTHING (deprecated framing not imported, D-04/D-16)
    - `grep -n "long_visible\|never_visible\|never_landed\|no_t0" reaction_timing.py` shows all 4 labels present
    - The second backward-continuity pass exists (not just a single find_t0 call): the test_t0_backward_run_start_not_first_visible test PASSES
  </acceptance_criteria>
  <done>reaction_timing.py implements compute_timing; all reaction_timing + synthetic distribution-shape tests GREEN; geometry reused; deprecated constants untouched.</done>
</task>

<task type="auto">
  <name>Task 2: Wire timing pass into reconstruct_all_players + size parse_ticks window</name>
  <files>outcome_first.py</files>
  <read_first>
    - outcome_first.py (lines 240-339: _parse_demo_events + reconstruct_all_players — the integration point; note current parse_events call has NO parse_ticks yet)
    - t0_detector.py (T0Detector constructor — what reconstruct_all_players must instantiate to pass to compute_timing)
    - config.py (_T0_SEARCH_PARSE_WINDOW_TICKS)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (reconstruct_all_players integration analog, lines 341-367; Pitfall 2)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md (Pitfall 2: parse window must cover backward cap)
  </read_first>
  <action>
1. In `_parse_demo_events` (or a new sibling parse step in `reconstruct_all_players`), add a selective `parse_ticks` call that returns a tick frame covering, for each episode, `[first_event_tick - _T0_SEARCH_PARSE_WINDOW_TICKS, last_event_tick]`. Since episodes span the whole demo, the simplest correct approach: parse ticks for the union window `[min(first_event_tick) - _T0_SEARCH_PARSE_WINDOW_TICKS, max(last_event_tick)]` once per demo (selective-parse pattern, Phase 9.1). Required tick columns for `get_desired_angles` + visibility: `tick, X, Y, Z, pitch, yaw` per steamid (use the existing demoparser2 prop names this codebase already parses — grep `parse_ticks` usage in ddm_analyzer.py for the exact prop list and reuse it). Coerce sid columns with `_coerce_sid`, never `pd.to_numeric`.
2. Build `ticks_by_sid` (the per-sid cache `find_t0` accepts) the same way the existing pipeline does (grep for `ticks_by_sid` construction in ddm_analyzer.py / t0_detector usage; reuse the idiom).
3. Instantiate a `T0Detector` once per demo (it loads BVH/.tri meshes — do it ONCE outside the per-player loop for cost, D-07 correctness-first but no needless re-instantiation).
4. In the per-player loop, AFTER `group_episodes` builds `df` and BEFORE `save_to_db`, run the timing pass for EVERY episode row (incl. unresolved — D-08):

```python
        timing_cols = ["t0_tick","t0_source","t1_tick","t1_source",
                       "crosshair_angle_at_t0_deg","rt_visible_to_land_ms","rt_visible_to_hit_ms"]
        timings = []
        for _, row in df.iterrows():
            t = reaction_timing.compute_timing(row.to_dict(), ticks_df, t0_detector, ticks_by_sid=ticks_by_sid)
            timings.append(t)
        timing_df = pd.DataFrame(timings, index=df.index, columns=timing_cols)
        df = pd.concat([df, timing_df], axis=1)
        save_to_db(df, db_path, "duel_episodes", match_ids_by_sid[sid])
```
   Add `import reaction_timing` at module top. Keep the existing per-player try/except (label-not-drop). Do NOT change `group_episodes` or the existing column-rename logic.
5. Confirm `find_t0`'s search window is FULLY covered by the parsed ticks: assert/log when `search_start < ticks_df.tick.min()` so a too-small window surfaces as a warning (Pitfall 2 warning sign).
  </action>
  <verify>
    <automated>py -m pytest tests/test_outcome_first.py --override-ini="addopts=--strict-markers" -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "import reaction_timing" outcome_first.py` returns a match
    - `grep -n "compute_timing(" outcome_first.py` shows the per-episode call inside reconstruct_all_players
    - `grep -n "parse_ticks" outcome_first.py` shows the new selective tick parse
    - `grep -n "_T0_SEARCH_PARSE_WINDOW_TICKS" outcome_first.py` confirms the window constant is used (Pitfall 2)
    - `grep -n "pd.to_numeric\|pd.read_sql" outcome_first.py` shows NO new sid coercion via these (only the pre-existing tick numeric coercion at line ~261 remains)
    - Full suite: `py -m pytest --override-ini="addopts=--strict-markers" -q` → all prior tests still GREEN (no regression to OF-2's 365)
  </acceptance_criteria>
  <done>reconstruct_all_players runs the timing pass per episode and writes the 7 columns to duel_episodes; parse window covers the backward cap; suite GREEN.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: D-02 threshold A/B on 1 demo + lock TARGET_REACHED_THRESHOLD</name>
  <what-built>
    A one-demo A/B comparison of the T1 LANDS threshold: fixed 3.0deg (current config default) vs distance-scaled (`max(degrees(atan2(16, distance_to_enemy)), 0.5)`), per D-02. Run the OF-3 timing pass on `for_analysis/spirit/spirit-vs-the-mongolz-m2-ancient.dem` (the Phase 10 SC-4 reference demo with known floor-pinning history; substitute any donk demo with high episode count if absent) under BOTH variants, into a scratch/throwaway DB (NOT analytics.db). Produce a comparison table with, per variant: (a) %@tick-quantum pinning, (b) min/p10 rt_visible_to_land_ms, (c) never_landed%, (d) count of b5-class impossible rows (t1_tick==t0_tick+1 AND crosshair_angle_at_t0_deg > 2*threshold).
  </what-built>
  <how-to-verify>
    1. Open the A/B comparison table the executor produced (printed to console and saved to `of3_threshold_ab.md` in repo root).
    2. Confirm the chosen variant (default: fixed 3.0) has: 0 (or near-0) b5-class impossible rows, <10% tick-quantum pinning, and a plausible never_landed% (NOT >50% = too tight, NOT <2% = too loose / B-5 redux).
    3. Decision rule (locked, no moving goalposts): KEEP fixed 3.0 UNLESS fixed produces >10% pinning OR >10 impossible rows that distance-scaling resolves. If distance-scaling wins, the executor switches `TARGET_REACHED_THRESHOLD` to the formula form in config.py and re-runs to confirm.
    4. Approve the locked threshold value/mode, which OF-3-03 will use for the staged N=1->5->81 re-batch.
  </how-to-verify>
  <resume-signal>Type "approved: fixed 3.0" (or "approved: distance-scaled") to lock the threshold, or describe the distribution-shape concern to address.</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|-|-|
| demo file → parser | Untrusted .dem; unchanged (demoparser2-validated) |
| tick data → geometry/visibility | In-memory pandas; no external surface |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-|-|-|-|-|
| T-OF3-03 | Information disclosure | SteamID handling in timing pass | mitigate | reaction_timing/outcome_first use `_coerce_sid` string-path for any sid; no `pd.to_numeric`/`pd.read_sql` on sid columns |
| T-OF3-04 | Denial of service | unbounded backward BVH raycast cost | accept | Bounded by T0_BACKWARD_SEARCH_CAP_TICKS; D-07 defers optimization, profiles on N=1 staged run (OF-3-03) |

No network, auth, or crypto surface. ASVS L1 V2/V3/V4/V6 N/A.
</threat_model>

<verification>
- `py -m pytest tests/test_reaction_timing.py tests/test_distribution_shape.py -m "not requires_db" --override-ini="addopts=--strict-markers" -q` → GREEN
- `py -m pytest --override-ini="addopts=--strict-markers" -q` → full suite GREEN (no OF-2 regression)
- D-02 A/B table reviewed; b5-class impossible rows ~0 under the locked threshold (acceptance smell-test)
</verification>

<success_criteria>
- compute_timing turns all OF-3-01 RED tests GREEN (D-01/D-03/D-05/D-06)
- T0 second backward-continuity pass implemented (run-start, not first-ever-visible)
- geometry reused (get_desired_angles/angular_diff imported, not duplicated)
- timing pass wired into reconstruct_all_players for ALL episodes (D-08); parse window covers backward cap (Pitfall 2)
- _detect_t1 and deprecated T0 constants untouched (D-04/D-16)
- TARGET_REACHED_THRESHOLD locked via user checkpoint (D-02)
</success_criteria>

<output>
After completion, create `.planning/phases/OF-3-revalidation-measurability-gate/OF-3-02-SUMMARY.md`
</output>
