# Phase OF-3: Re-validation + Metric + Measurability Gate - Research

**Researched:** 2026-06-10
**Domain:** measurement-layer redesign (T0/T1 reaction-time detection on KNOWN opponent) + statistical gate design (split-half reliability, distribution-shape regression)
**Confidence:** HIGH (codebase/algorithm), MEDIUM (gate threshold derivation — no external benchmark exists, derived from first principles + project history)

## Summary

OF-3 adds a timing pass on top of the OF-2 `duel_episodes` table. For each episode the opponent is already known (ground truth), so T0 becomes a **backward BVH visibility search** (`t0_detector.find_t0`, already correct for known-enemy lookups) and T1 becomes a **new "crosshair LANDS" detector** that fixes B-5 (the bug where `_detect_t1`'s old "motion toward target" semantics produced 1-tick T1 at 86° crosshair angles). Both T0 and T1 use label-not-drop semantics (`t0_source`/`t1_source` ∈ `{"...", "never_visible"/"never_landed"}`), columns land on `duel_episodes` via the existing idempotent `_migrate_schema` ALTER-TABLE pattern, and a two-tier `tests/test_distribution_shape.py` suite (synthetic pytest always-on + `@requires_db` live-DB checks) catches recurrence of tick-quantum pinning.

The hardest part of this phase is **D-10**: designing concrete, written-down PASS/FAIL thresholds for Gate-A (win-rate slices — already proven at 5σ in OF-1/OF-2, expected PASS) and Gate-B (RT split-half reliability — the actual risk, given the prior DDM stability gate closed RED 1/30). This research derives Gate-B numbers from split-half reliability statistics (Spearman-Brown corrected r, with explicit N floors via the standard error of a correlation), grounded in the donk 81-demo / ~3352-episode corpus size already in `analytics.db`. These numbers are **proposals for the user checkpoint**, not silently-locked decisions — PLAN.md must present them for approval before the gate run, per D-10.

**Primary recommendation:** Implement T1 as a **single-pass per-tick scan from T0 forward** using the existing `get_desired_angles`/`angular_diff` helpers, with `on_target = angular_dist <= TARGET_REACHED_THRESHOLD` sustained for `T1_SUSTAINED_AIM_TICKS+1` ticks (mirrors Phase 10's pre-aim branch but as the PRIMARY definition, not a special case). Run the **3°-fixed vs distance-scaled threshold A/B comparison on ONE demo** (`spirit-vs-the-mongolz-m2-ancient.dem` — already the Phase 10 SC-4 reference, has known floor-pinning history) using the distribution-shape criteria in this document, before committing to a constant value for the staged 81-demo re-batch.

## Architectural Responsibility Map

Single-tier Python pipeline (no client/server split). Mapping is by module/data-flow stage.

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| T0 backward visibility search | `t0_detector.py` (`find_t0`, BVH+AABB) | `outcome_first.py` (caller, per-episode loop) | BVH is the only correct visibility primitive (project-wide rule); reuse, don't reimplement |
| T1 "crosshair lands" detection | New function in `outcome_first.py` (or new module `t1_detector.py`) | `ddm_analyzer.get_desired_angles`/`angular_diff` (geometry helpers, reused not duplicated) | New algorithm per D-04 (deprecate old `_detect_t1`, don't edit); geometry math is shared/proven |
| Tick-data fetch for timing pass | `outcome_first.py` (selective `parse_ticks` per episode window) | `ddm_analyzer.py` (Phase 9.1 selective-window pattern as reference) | Per-episode windowed parse keeps cost bounded (D-07: correctness first, profile later) |
| Schema (timing columns) | `db_utils.py` (`_migrate_schema`, idempotent ALTER TABLE) | — | Established pattern (t1_source precedent from Phase 10) |
| Distribution-shape regression | `tests/test_distribution_shape.py` (two-tier: synthetic + `@requires_db`) | `pytest.ini` (register `requires_db` marker) | New test infra; marker not yet registered — must add |
| Re-batch driver | New/reused staged-rebatch script (`monesy_rebatch.py`-style or new `of3_rebatch.py`) | `outcome_first.reconstruct_all_players` (per-demo entry point) | D-14: staged N=1→5→81, manual checkpoints, inspection artifact |
| Gate-A (win-rate slices) | SQL queries against `duel_episodes` | `outcome_first_spike.py` (slice logic precedent from OF-1) | Re-derive on clean re-batched data; same slice definitions as OF-1/OF-2 |
| Gate-B (RT stability) | New analysis script (split-half reliability) | `analytics.db` `duel_episodes` post-rebatch | Statistical computation only — no production code |

## Standard Stack

### Core (no new external dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| pandas | already in requirements.txt | tick-frame ops for T0/T1 detection | unchanged, project standard |
| numpy / scipy.stats | numpy already present; scipy NOT confirmed | split-half reliability (Pearson r), Spearman-Brown correction | scipy.stats.pearsonr is the standard; verify scipy is installed |
| sqlite3 | stdlib | `_migrate_schema` ALTER TABLE for new columns | unchanged |
| pytest | already configured | `tests/test_distribution_shape.py` two-tier suite | unchanged |
| demoparser2 | already in requirements.txt | selective `parse_ticks` per episode window | unchanged |

**Version verification:**
```bash
py -c "import scipy; print(scipy.__version__)"
```
`[VERIFIED needed at plan time]` — if scipy is absent, split-half reliability (Pearson r) can be computed with `numpy.corrcoef` (no scipy dependency needed) or `pandas.Series.corr()`. **Recommendation: use `pandas.Series.corr(method='pearson')` — already a transitive dependency, zero new installs, sufficient for Gate-B.**

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| matplotlib/seaborn | already present | distribution-shape histograms in inspection artifact | reuse `visualize_results.py` patterns |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `pandas.Series.corr()` for split-half r | `scipy.stats.pearsonr` | scipy gives p-value too, but adds a dependency check; pandas.corr is sufficient since CI95 is computed via Fisher z-transform manually either way |
| New `t1_detector.py` module | Inline function in `outcome_first.py` | Module split keeps `outcome_first.py` focused on episode reconstruction; T1 detection is a distinct algorithm with its own test file — **recommend new module** `reaction_timing.py` housing both T0-wrapper and T1 detector, imported by `outcome_first.py` |

**Installation:** none — verify scipy presence only as a discretionary check, no action needed if absent (pandas.corr suffices).

## Architecture Patterns

### System Architecture Diagram

```
[duel_episodes row: player_steamid, opponent_steamid, first_event_tick, last_event_tick]
        |
        v
[reaction_timing.compute_timing(episode, demo_path)]
        |
        |-- selective parse_ticks window:
        |     [first_event_tick - LOOKBACK, last_event_tick]
        |     (LOOKBACK = cost-capped backward search bound, see D-05)
        |
        v
   [T0 backward search] -- t0_detector.find_t0(player, opponent,
        |                       search_start = first_event_tick - LOOKBACK,
        |                       search_end   = first_event_tick)
        |
        |-- found within run --> t0_tick, t0_source = "BVH+AABB" | "long_visible"
        |-- never visible      --> t0_tick = NULL, t0_source = "never_visible"
        |
        v
   [T1 "lands" search] -- forward scan [t0_tick, first_event_tick]
        |   per-tick: angular_dist = angular_diff(crosshair, desired_angle_to_enemy)
        |   on_target = angular_dist <= TARGET_REACHED_THRESHOLD
        |   sustained for T1_SUSTAINED_AIM_TICKS+1 ticks --> T1 = first on-target tick
        |
        |-- lands            --> t1_tick, t1_source = "lands"
        |-- never lands       --> t1_tick = NULL, t1_source = "never_landed"
        |
        v
   [derived columns] -- rt_visible_to_land_ms = (t1_tick - t0_tick) * MS_PER_TICK
        |                rt_visible_to_hit_ms  = (t2_tick - t0_tick) * MS_PER_TICK
        |                (t2_tick = first_event_tick, already known)
        |
        v
   [_migrate_schema ALTER TABLE duel_episodes ADD COLUMN ...]
        |
        v
   [staged re-batch driver: N=1 -> 5 -> 81]
        |
        |-- after N=5: distribution-shape SQL + inspection artifact --> user checkpoint
        |
        v
   [tests/test_distribution_shape.py @requires_db against duel_episodes]
        |
        v
   [Gate-A: win-rate slices (SQL)] --+
                                       |--> measurability/stability VERDICT.md
   [Gate-B: split-half RT reliability]+
```

### Recommended Project Structure
```
cs2-ddm/
├── reaction_timing.py        # NEW: compute_timing(episode_dict, ticks_df, t0_detector) -> dict
│                              #   wraps find_t0 backward search + new T1 "lands" detector
├── config.py                 # NEW constants: TARGET_REACHED_THRESHOLD,
│                              #   T0_BACKWARD_SEARCH_CAP_TICKS, LONG_VISIBLE_THRESHOLD_TICKS
├── db_utils.py                # _migrate_schema: ADD t0_tick, t0_source, t1_tick, t1_source,
│                              #   rt_visible_to_land_ms, rt_visible_to_hit_ms to duel_episodes
├── outcome_first.py           # reconstruct_all_players: call reaction_timing.compute_timing
│                              #   per episode after group_episodes, before save_to_db
├── tests/
│   └── test_distribution_shape.py  # NEW: two-tier (synthetic always-on + @requires_db)
├── of3_rebatch.py              # NEW (or reuse monesy_rebatch.py pattern): staged N=1->5->81
├── generate_of3_inspection.py  # NEW: 7-section inspection artifact (of2_parity_inspection.md pattern)
└── of3_gate.py                  # NEW: Gate-A + Gate-B computation -> VERDICT.md
```

### Pattern 1: T0 backward search per episode (D-05)

**What:** For each `duel_episodes` row, call `find_t0(all_ticks_df, player_steamid, opponent_steamid, search_start_tick, search_end_tick=first_event_tick, ...)`. The KEY decision is `search_start_tick`.

**D-05 algorithm (backward scan to start of continuous visibility run, cost-capped, no fixed-window clamp):**

1. Set a generous **cost-cap window** `T0_BACKWARD_SEARCH_CAP_TICKS` (proposal: 640 ticks ≈ 10s — double Phase 9.1's `_SELECTIVE_WINDOW_BEFORE_TICKS=384`, since T0 search now needs to look further back than the old engagement-window approach which only looked back from a `player_hurt` anchor by ~6s).
2. Call `find_t0` with `search_start_tick = first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS`, `search_end_tick = first_event_tick`. `find_t0` scans **forward** from `search_start_tick` and returns the **first** visible tick — this is NOT yet "start of the continuous run containing the first event."
3. **The continuous-run extension** (the actual D-05 requirement): after `find_t0` returns `t0_candidate`, do a SECOND backward scan from `t0_candidate` toward `search_start_tick`, checking `is_visible` tick-by-tick (or in larger strides) to find where the visibility run ACTUALLY begins. If the run extends all the way to `search_start_tick` (the cap), label `t0_source = "long_visible"` and use `t0_candidate = search_start_tick` (i.e., do NOT report a T0 earlier than the cap, but DO mark it as `long_visible` rather than treating the cap as a true T0 — this is the distinction D-05 requires vs. a "fixed-window clamp").
4. If `find_t0` returns `(None, ...)` across the entire cap window, label `t0_source = "never_visible"`, `t0_tick = NULL` (D-06).

**Why this avoids the B-1 floor-artifact class:** B-1 was a hard ADDITIVE floor on top of T0 (T1_GRACE_MS added 8 ticks to T0 unconditionally). D-05's cap is a **search boundary**, not a value transformation — when the boundary is hit, the row is LABELED (`long_visible`) rather than silently assigned a clamped T0 value that masquerades as a real measurement. The label is the safety valve; `long_visible` rows can be excluded from RT distributions at the metric layer (same pattern as `unresolved`/`never_landed`/`never_visible`) without corrupting the T0 column itself.

**Cost feasibility:** `find_t0` with `ticks_by_sid` cache (Phase 9.1 SC4) does a per-tick BVH raycast (8 AABB corners). At 640 ticks × 2 entities (player+opponent visibility check is single-directional, so 640 ticks × up to 8 rays = ~5120 raycasts worst case per episode). With ~3352 episodes for donk alone, worst case ~17M raycasts. **This needs profiling on N=1 before committing to N=81** (D-07 explicitly defers optimization but mandates profiling on the staged run). If N=5 staged run shows excessive wall-time, the FIRST lever is reducing `T0_BACKWARD_SEARCH_CAP_TICKS` (a label-safe parameter — rows that hit the new lower cap simply get `long_visible` more often), NOT adding a fixed-window clamp.

**When to use:** Every `duel_episodes` row, including unresolved (D-08).

```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\t0_detector.py:88-98 (verified 2026-06-10)
# find_t0 signature — reuse directly, scanning forward from a backward-shifted search_start
t0_tick, method = self.t0_detector.find_t0(
    all_ticks_df=ticks_df,
    player_steamid=player_sid,
    enemy_steamid=opponent_sid,
    search_start_tick=first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS,
    search_end_tick=first_event_tick,
    active_smokes=active_smokes,
    flash_intervals=flash_intervals,
    ticks_by_sid=ticks_by_sid,
)
```

### Pattern 2: T1 "crosshair lands" detection (D-01, D-02, D-03)

**What:** New function, NOT a variant of `_detect_t1`. Forward scan `[t0_tick, first_event_tick]` (the T2 anchor — `first_event_tick` is the first hurt/death event in the episode, i.e. the existing T2). For each tick, compute `angular_dist = hypot(angular_diff(yaw, desired_yaw), angular_diff(pitch, desired_pitch))` using the EXISTING `get_desired_angles`/`angular_diff` static methods (already proven across 367+ tests — reuse, don't reimplement per "Don't Hand-Roll").

```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py:106-122 (verified 2026-06-10)
# get_desired_angles(px,py,pz, ex,ey,ez) -> (pitch, yaw)
# angular_diff(a1, a2) -> signed diff in [-180,180]
```

**T1 predicate (D-01 default, validate via distribution shape):**
```
on_target(tick) = angular_dist(tick) <= TARGET_REACHED_THRESHOLD
T1 = first tick t in [t0_tick, first_event_tick] such that
     on_target(t), on_target(t+1), ..., on_target(t + T1_SUSTAINED_AIM_TICKS)
     are ALL true (T1_SUSTAINED_AIM_TICKS=2, existing constant — sustained-aim
     window is T1_SUSTAINED_AIM_TICKS+1 = 3 ticks total, per the off-by-one
     lesson from Phase 10)
```
- If found: `t1_tick = T1`, `t1_source = "lands"`.
- If `angular_dist(t0_tick) <= TARGET_REACHED_THRESHOLD` already (pre-aimed at T0): `t1_tick = t0_tick`, `t1_source = "lands"` (same predicate naturally covers this — no separate branch needed, UNLIKE Phase 10's `pre_aimed` special case, because here "on target at T0" simply satisfies the same `on_target` check at the first tick of the scan).
- If never satisfied within `[t0_tick, first_event_tick]`: `t1_tick = NULL`, `t1_source = "never_landed"` (D-03).

**Why this kills B-5:** B-5's bug was that `_detect_t1` used a "moving toward target AND significant angular change" predicate — which can fire on tick 1 of a flick that's 86° away from target, because the FIRST tick of any flick shows "moving toward + significant change". The new predicate requires the crosshair to ACTUALLY ARRIVE within `TARGET_REACHED_THRESHOLD` and STAY there — physically impossible to satisfy in 1 tick from 86° away (would require ~5400°/s rotation, impossible even for the fastest pro flicks which top out around 1000-1500°/s = ~16-23°/tick at 64Hz).

**Acceptance smell-test (from CONTEXT.md `<specifics>`):** re-run the `b5_smoking_gun.md` query class on fresh `duel_episodes` data → 0 rows where `crosshair_angle_at_t0_deg > TARGET_REACHED_THRESHOLD * 2` (say >6° for a 3° threshold) AND `t1_tick == t0_tick + 1`. No >10% cluster at any tick-quantum value (15.625/31.25/46.875ms) in the `rt_visible_to_land_ms` distribution.

### Pattern 3: D-02 threshold A/B comparison procedure

**What:** D-02 mandates comparing **fixed `TARGET_REACHED_THRESHOLD = 3.0`** vs **distance-scaled by hitbox angular size**, picking by distribution shape, on ONE demo.

**Distance-scaled formula (CS2 player hitbox ~32 units wide at typical 500-1500 unit engagement distances):**
```python
# angular size of a ~32-unit-wide target at distance D (in CS2 units):
# angular_radius_deg = degrees(atan2(16, D))  # half-width / distance
# At D=500: ~1.83°. At D=1000: ~0.92°. At D=1500: ~0.61°.
hitbox_angular_radius_deg = math.degrees(math.atan2(16.0, distance_to_enemy))
threshold_scaled = max(hitbox_angular_radius_deg, MIN_THRESHOLD_FLOOR)
```

**Quantization-floor check (project rule: threshold ≥ 3× quantization step, demoparser2 ~0.022°):**
- 3.0° fixed: 3.0 / 0.022 ≈ 136× — clears comfortably.
- Distance-scaled at D=1500 (long-range, e.g. dust2 long A): ~0.61° / 0.022 ≈ 28× — still clears, but the LONGER the engagement distance, the closer to the floor. At D=3000 (extreme long sightlines): ~0.31° / 0.022 ≈ 14× — still clears but margin shrinks. **Set `MIN_THRESHOLD_FLOOR = 0.5°` (≈23× quantization) as a hard floor for the distance-scaled variant** to guarantee the ≥3× rule holds at any realistic CS2 engagement distance.

**Comparison procedure (1 demo):**
1. Run the OF-3 timing pass on `spirit-vs-the-mongolz-m2-ancient.dem` (donk's demo, Phase 10 SC-4 reference — has documented floor-pinning history, good stress test) with `TARGET_REACHED_THRESHOLD = 3.0` (fixed).
2. Re-run the SAME demo with the distance-scaled formula above.
3. For each variant, compute: (a) `%@tick-quantum` pinning (>10% at any 15.625ms multiple = FAIL signal), (b) `min(rt_visible_to_land_ms)`, `p10`, (c) `never_landed %`, (d) re-run the b5_smoking_gun query class — count of impossible rows (T1=T0+1tick AND crosshair_angle_at_t0 > 2×threshold).
4. **Pick the variant with**: fewer impossible rows, lower tick-quantum pinning %, and a `never_landed %` that is plausible (not >50% — would suggest threshold too tight; not <2% — would suggest threshold too loose, recreating B-5's "always lands instantly" failure mode).
5. Document the chosen value + comparison table in the staged-rebatch N=1 inspection output (per D-14, every inspection table needs a physics-bounded column — `crosshair_angle_at_t0_deg` already exists as a precedent column name on `engagements`; for `duel_episodes` this becomes a NEW derived column computed at T0, same name).

**Recommendation (pre-data, to be confirmed by the A/B run):** Fixed 3.0° is simpler, has a much larger quantization margin, and matches the existing `T1_NOT_AIMED_THRESHOLD` lineage (Phase 10 used 1.0° for "already aimed" — 3.0° as "landed" is a reasonable widening for a LANDING criterion vs. a PRE-AIM criterion, since landing tolerates slightly more crosshair wobble than "already perfectly aimed before the engagement started"). Distance-scaling adds complexity (requires `distance_to_enemy` at every tick) for a benefit that's only material at very long sightlines, which are a minority of CS2 duels. **Default to fixed 3.0° unless the A/B run shows fixed produces >10% pinning or >10 impossible rows that distance-scaling resolves.**

### Pattern 4: Distribution-shape regression suite (D-15)

**Two-tier structure:**

**Tier 1 — synthetic, always-on (`tests/test_distribution_shape.py::TestSyntheticDistributionShape`):**
- Build synthetic tick-frames (reuse `_make_ticks`-style helpers from `tests/test_ddm_analyzer_t1.py`) that exercise: (a) a flick scenario where crosshair is 30° off at T0 — assert T1 is NOT T0+1 (B-5 regression guard), (b) a pre-aimed scenario where crosshair is already within threshold at T0 — assert T1=T0, (c) a never-lands scenario (crosshair never gets within threshold) — assert `t1_source == "never_landed"`, T1=NULL, (d) a never-visible scenario for T0 (BVH always returns None) — assert `t0_source == "never_visible"`, T0=NULL, (e) a long-visible scenario (visibility run extends to the search cap) — assert `t0_source == "long_visible"`.
- These run in the standard pytest suite (no DB, no demo files) — fast, always green.

**Tier 2 — `@requires_db` live-DB checks (`tests/test_distribution_shape.py::TestLiveDistributionShape`):**
- Register `requires_db` marker in `pytest.ini` (currently only `slow` and `integration` exist — **gap, must add**).
- Checks against `analytics.db` `duel_episodes` POST-rebatch:
  1. `%@tick-quantum` pinning: `SUM(CASE WHEN rt_visible_to_land_ms IN (15.625, 31.25, 46.875, 62.5) THEN 1 ELSE 0 END) / COUNT(*) < 0.10` (mirrors Phase 10 SC-4's `n_at_125ms / n_total < 0.10`, generalized to all small-tick multiples).
  2. `MIN(rt_visible_to_land_ms) >= 0` (no negative RTs — sanity).
  3. `never_landed_pct` and `never_visible_pct` reported (no hard threshold — diagnostic signal per D-03/D-06, but flag if either >50%).
  4. Physics-bounded check (B-5 post-mortem rule): for rows where `t1_tick == t0_tick + 1` (1-tick land), `crosshair_angle_at_t0_deg <= TARGET_REACHED_THRESHOLD * 2` for ALL such rows — direct b5_smoking_gun regression guard.
  5. Per-player median `rt_visible_to_land_ms < 100ms` flagged as "investigate" (not hard FAIL — per CONTEXT.md `<specifics>` "pro-physiology sanity floor... investigate before accepting", this is a soft warning surfaced in the inspection artifact, not a pytest failure).
- Run AFTER every re-batch stage (N=1, N=5, N=81) per D-15.

```python
# Source: pytest marker registration pattern — pytest.ini currently has:
#   markers =
#       slow: marks tests as slow (deselect with '-m "not slow"')
#       integration: marks tests as integration tests (cwd-sensitive, skip in CI)
# ADD:
#       requires_db: marks tests requiring analytics.db with post-rebatch data (skip if absent)
```

### Anti-Patterns to Avoid

- **Don't add a fixed-window clamp for T0** (D-05 hard constraint) — recreates B-1 floor-artifact class. Use cost-cap + `long_visible` label instead.
- **Don't reuse/edit `_detect_t1`** (D-04) — old function stays untouched in `ddm_analyzer.py`, deprecated. New T1 logic lives in `reaction_timing.py` (or new module), called from `outcome_first.py`.
- **Don't drop `never_landed`/`never_visible`/`long_visible` rows from the DB** (D-03, D-06, D-08) — label-not-drop is the established project semantic (unresolved episodes already follow this pattern).
- **Don't compute timing only for resolved (won/lost) episodes** (D-08) — unresolved episodes need timing too for distribution-shape checks to see the full picture.
- **Don't lock Gate-B numbers without a user checkpoint** (D-10) — this research PROPOSES numbers; PLAN.md must present them for approval before the gate run.
- **Don't backfill `t0_tick`/`t1_tick`/etc. on existing `duel_episodes` rows via UPDATE** — re-batch (re-run `reconstruct_all_players`) regenerates rows; existing rows get NULL via DEFAULT (idempotent ALTER TABLE pattern, Phase 10 precedent).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Visibility/raycast for T0 | New BVH wrapper or FOV-only check | `t0_detector.find_t0` (BVH+AABB, smoke/flash suppression already correct) | Project-wide rule: BVH+AABB is the ONLY correct T0 approach; FOV-only always fails for peeks |
| Angular geometry math | New trig functions for crosshair-vs-target angle | `ddm_analyzer.get_desired_angles` + `angular_diff` (static methods, 367+ tests) | Already battle-tested; B-4/Phase-10 pre-aim branch reused these directly |
| Schema migration | New table or DROP/CREATE duel_episodes | `db_utils._migrate_schema` idempotent ADD COLUMN pattern | Established, idempotent, preserves existing rows (t1_source precedent) |
| Split-half reliability stats | Custom correlation/CI code | `pandas.Series.corr()` + manual Fisher z-transform for CI95 (standard formula, ~5 lines) | Avoids new scipy dependency; Fisher z-transform is a well-known closed-form, no library needed |
| Staged rebatch driver with pause/resume | New from-scratch driver | Adapt `monesy_rebatch.py` 2-phase pattern (`--phase` flag, skip-existing via DB state) | Verified working pattern from 2026-05-19, PowerShell pause/resume wrappers exist |
| Inspection artifact | New ad-hoc markdown format | `of2_parity_inspection.md` 7-section format (aggregate / per-unit / per-actor / full-list / anomaly buckets / random sample / pre-vs-post + acceptance checklist) | Verified working at top-10 scale (53KB/785 engagements), user-approved pattern |

**Key insight:** Every primitive OF-3 needs (visibility raycast, angular geometry, schema migration, staged-rebatch driver, inspection format) already exists and is proven in this codebase. OF-3's actual NEW work is: (1) the T1 "lands" predicate (a different combination of existing primitives), (2) the T0 backward-search wrapper around `find_t0` (new search-direction logic, but `find_t0` itself is reused), (3) the distribution-shape test suite (new test file, but reuses fixture patterns from `test_ddm_analyzer_t1.py`), (4) the Gate-A/Gate-B statistical scripts (new, but standard formulas).

## Common Pitfalls

### Pitfall 1: T1 scan window must extend to T2 (first_event_tick), not a fixed offset

**What goes wrong:** If the T1 forward-scan window is capped at `t0_tick + N` for a small fixed N (like Phase 10's old `T0_TO_T2_MAX_TICKS` reasoning), engagements where the crosshair takes longer to land than N ticks will incorrectly get `never_landed` even though they DID land before the hit.

**Why it happens:** Old pipeline conflated "scan window for T1 candidates" with "gradeable window" via `T0_TO_T2_MAX_TICKS=96`. In OF-3, T2 (`first_event_tick`) is ALREADY KNOWN per episode (it's the anchor). The T1 scan window is naturally `[t0_tick, first_event_tick]` — bounded by real data, not a heuristic constant.

**How to avoid:** Scan window = `[t0_tick, first_event_tick]` always. If `t0_tick is None` (never_visible), T1 cannot be computed — also NULL, `t1_source` should reflect the upstream `never_visible` (e.g. `t1_source = "no_t0"` or simply NULL with `t0_source` already explaining why).

**Warning signs:** `never_landed %` unexpectedly high (>50%) on episodes with long T0→T2 gaps — check whether the scan window was truncated.

### Pitfall 2: Selective parse_ticks window must cover the BACKWARD search cap, not just the old engagement window

**What goes wrong:** Phase 9.1's `_SELECTIVE_WINDOW_BEFORE_TICKS=384` was sized for the OLD pipeline's lookback from a `player_hurt` anchor. OF-3's T0 backward search may need `T0_BACKWARD_SEARCH_CAP_TICKS` ticks BEFORE `first_event_tick` — if this cap exceeds 384, the existing selective-parse window will silently miss tick data, and `find_t0` will return `not_found` (interpreted as `never_visible`) for episodes that actually had earlier visibility.

**Why it happens:** Two independent windowing concerns (old: episode analysis window; new: T0 backward search) get conflated if the same `_SELECTIVE_WINDOW_BEFORE_TICKS` constant is reused without checking the new requirement.

**How to avoid:** Either (a) introduce a NEW constant `_T0_SEARCH_PARSE_WINDOW_TICKS >= T0_BACKWARD_SEARCH_CAP_TICKS` for the OF-3 timing pass's `parse_ticks` call, or (b) verify `T0_BACKWARD_SEARCH_CAP_TICKS <= _SELECTIVE_WINDOW_BEFORE_TICKS` and reuse. Given the proposed cap (640) > existing window (384), a NEW constant is needed. Plan must size this explicitly and grep for all `parse_ticks(... ticks=...)` call sites in the OF-3 timing path.

**Warning signs:** `never_visible %` much higher than expected, especially correlating with episodes that have large `(first_event_tick - <previous episode's last_event_tick>)` gaps (long pre-engagement quiet periods).

### Pitfall 3: `find_t0` returns the FIRST visible tick scanning FORWARD — D-05's "continuous run start" requires a SECOND pass

**What goes wrong:** Calling `find_t0(search_start, search_end)` once and using its return value directly gives "first visible tick within the cap window" — NOT "start of the continuous visibility run containing the first event" as D-05 specifies. These can differ: e.g. enemy becomes briefly visible at tick 100, goes behind cover, becomes visible again at tick 150 and STAYS visible until `first_event_tick=200`. `find_t0(100, 200)` returns tick 100 (the FIRST visible tick overall), but the "continuous run containing the first event" starts at tick 150.

**Why it happens:** `find_t0`'s docstring says "first tick where ... visibility ... clears" — it's a forward scan for ANY visibility, not specifically the run adjacent to `search_end`.

**How to avoid:** Per Pattern 1 step 3 — after getting `t0_candidate` from `find_t0`, do a backward continuity check: scan backward from `first_event_tick` (or from `t0_candidate`, whichever framing is cleaner) checking `is_visible` per-tick until visibility breaks, OR until the cap is hit. The actual T0 = the earliest tick in that continuous backward run. **This is the single most important algorithmic detail in D-05** — getting it wrong either reproduces "first ever visible" (too early, inflates RT) or "only checks search_end tick" (too late, undercounts RT).

**Warning signs:** RT distribution has an implausibly long right tail (multi-second RTs) — symptom of using the wrong (too-early) visibility tick as T0.

### Pitfall 4: Gate-B sample size — donk's 81-demo corpus may not split cleanly

**What goes wrong:** Split-half reliability requires dividing the corpus into two halves (e.g., odd/even demo index, or odd/even episode index) and correlating per-player (or per-slice) mean RT between halves. With donk alone (~3352 episodes across 81 demos, but only ~1428 "won" episodes where T1/T2 are most meaningful), the per-DEMO split gives only 40/41 demos per half — if the metric is aggregated per-demo, N=40 is the correlation sample size, which has wide confidence intervals.

**Why it happens:** The DDM gate that closed RED 1/30 (2026-05-12) was per-PLAYER (30 players, 1 RT estimate each) — fundamentally different N than per-DEMO splits within ONE player's corpus.

**How to avoid:** D-12 adds 2-4 pros from the same corpus — this gives a per-PLAYER cross-check (small N, like the prior gate) AND a per-player WITHIN-corpus split-half (larger N, ~40 demo-halves or ~600+ episode-halves for donk). **Recommend BOTH**: (a) per-player split-half on donk's own corpus (high N, answers "is the metric internally consistent for one player") as the PRIMARY Gate-B test, and (b) cross-player comparison (low N, 3-5 players, answers "does the metric differentiate players sensibly") as a secondary/diagnostic slice, NOT the primary PASS/FAIL.

**Warning signs:** If Gate-B is framed ONLY as cross-player (N=3-5), it inherits the SAME small-N problem that closed the DDM gate RED — re-deriving the same failure with a different label.

### Pitfall 5: `crosshair_angle_at_t0_deg` column name collision

**What goes wrong:** `engagements` table already has a `crosshair_angle_at_t0_deg REAL DEFAULT NULL` column (CSV schema, "must stay stable" per CLAUDE.md). If the OF-3 timing pass writes to `duel_episodes` with the SAME column name but DIFFERENT semantics (computed at the NEW T0, via the NEW backward-search algorithm), this is fine (different table) — but inspection-artifact generators or shared utility functions that assume "crosshair_angle_at_t0_deg always means the OLD `engagements` semantics" could get confused if they query across both tables.

**Why it happens:** Reusing a familiar column name for clarity (good) vs. cross-table semantic drift (risk) when both tables coexist (D-16: `engagements` stays as-is, deprecated but present).

**How to avoid:** Use the SAME column name `crosshair_angle_at_t0_deg` on `duel_episodes` (consistency, physics-bounded-column convention from B-5 post-mortem) but ensure all new SQL/Python explicitly qualifies the table (`duel_episodes.crosshair_angle_at_t0_deg`), and the inspection-artifact generator for OF-3 is a NEW script (`generate_of3_inspection.py`), not a modification of the old `generate_top10_inspection.py` that might implicitly assume `engagements`.

**Warning signs:** Inspection artifact shows numbers that don't match direct SQL against `duel_episodes` — likely querying the wrong table.

### Pitfall 6: pytest marker registration with `--strict-markers`

**What goes wrong:** `pytest.ini` has `--strict-markers` (via `--override-ini` in the CLAUDE.md invocation, but ALSO present in the base `addopts`). If `tests/test_distribution_shape.py` uses `@pytest.mark.requires_db` without registering it in `pytest.ini`'s `markers =` list, pytest will ERROR (not just warn) on collection.

**Why it happens:** `--strict-markers` is strict by design — unregistered markers fail the run, even with `--override-ini="addopts=--strict-markers"` (which REPLACES addopts but keeps `--strict-markers`, and the `markers=` registration list is a SEPARATE ini key, unaffected by `--override-ini`).

**How to avoid:** Plan must include an explicit edit to `pytest.ini`'s `markers =` section adding `requires_db: marks tests requiring analytics.db with post-rebatch duel_episodes data`.

**Warning signs:** `pytest.PytestUnknownMarkWarning` escalated to error, or collection failure: "'requires_db' not found in `markers` configuration option".

## Code Examples

### Verified `find_t0` signature and return contract
```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\t0_detector.py:88-98 (verified 2026-06-10)
def find_t0(
    self,
    all_ticks_df: pd.DataFrame,
    player_steamid: int,
    enemy_steamid: int,
    search_start_tick: int,
    search_end_tick: int,
    active_smokes: Optional[pd.DataFrame] = None,
    flash_intervals: Optional[List[Tuple[int, int]]] = None,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Tuple[Optional[int], str]:
    """Returns (t0_tick, method_string) or (None, "not_found")."""
```

### Verified geometry helpers (T1 reuse target)
```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py:106-122 (verified 2026-06-10)
@staticmethod
def get_desired_angles(px, py, pz, ex, ey, ez) -> Tuple[float, float]:
    """Returns (pitch, yaw) the player would need to aim at (ex,ey,ez) from (px,py,pz)."""

@staticmethod
def angular_diff(a1: float, a2: float) -> float:
    """Signed angular difference in [-180, 180]."""
```

### Verified ALTER TABLE pattern for new duel_episodes columns
```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\db_utils.py:74-107 (verified 2026-06-10)
# Add to _migrate_schema, after the existing duel_episodes CREATE TABLE block:
cols = {c[1] for c in conn.execute("PRAGMA table_info(duel_episodes)").fetchall()}
_episode_timing_migrations = [
    ("t0_tick", "INTEGER DEFAULT NULL"),
    ("t0_source", "TEXT DEFAULT NULL"),       # 'BVH+AABB' | 'long_visible' | 'never_visible'
    ("t1_tick", "INTEGER DEFAULT NULL"),
    ("t1_source", "TEXT DEFAULT NULL"),       # 'lands' | 'never_landed'
    ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
    ("rt_visible_to_land_ms", "REAL DEFAULT NULL"),
    ("rt_visible_to_hit_ms", "REAL DEFAULT NULL"),
]
for col, col_def in _episode_timing_migrations:
    if col not in cols:
        conn.execute(f"ALTER TABLE duel_episodes ADD COLUMN {col} {col_def}")
```

### Split-half reliability with Fisher z-transform CI95 (Gate-B, no scipy needed)
```python
# Standard formula — Fisher z-transform for CI on Pearson r
import math
def split_half_reliability(half_a: pd.Series, half_b: pd.Series) -> dict:
    n = len(half_a)
    r = half_a.corr(half_b, method="pearson")
    # Spearman-Brown correction (split-half underestimates full-test reliability)
    r_full = (2 * r) / (1 + r)
    # Fisher z CI95
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    ci_lo = math.tanh(z - 1.96 * se)
    ci_hi = math.tanh(z + 1.96 * se)
    r_full_ci = ((2*ci_lo)/(1+ci_lo), (2*ci_hi)/(1+ci_hi))
    return {"n": n, "r_half": r, "r_full_spearman_brown": r_full,
            "ci95_full": r_full_ci}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|---------------|--------|
| `_detect_t1`: T1 = "moving toward target with significant angular change, sustained" | New: T1 = "crosshair angular distance to target <= threshold, sustained" (LANDS, not motion) | OF-3 (this phase) | Kills B-5 (1-tick T1 at 86° impossible-physics rows); new predicate cannot fire before crosshair physically arrives |
| Fixed-window T0 (engagement-window-relative lookback) | Backward continuous-visibility-run search with cost cap + `long_visible` label | OF-3 (D-05) | No fixed-window clamp = no B-1-class floor artifact on T0 |
| `engagements` table, geometry-guessed opponent | `duel_episodes` table, ground-truth opponent (OF-2, already shipped) | OF-2 (2026-06-05) | OF-3 builds timing ON TOP of this — opponent identity is no longer a variable |
| No distribution-shape regression suite | Two-tier `tests/test_distribution_shape.py` (synthetic + `@requires_db`) | OF-3 (D-15) | Catches B-1/B-4/B-5-CLASS bugs (tick-quantum pinning, impossible physics) automatically going forward |

**Deprecated/outdated:**
- `_detect_t1` (`ddm_analyzer.py` L477+): DEPRECATED per D-04, untouched, B-5 remains live there (acceptable — engagements path is deprecated wholesale per D-16).
- `T0_MIN_OFFSET_TICKS` / `T0_TO_T2_MAX_TICKS` (config.py): these constants belonged to the OLD engagement-window-relative T0/T2 framing. OF-3's T0/T2 are episode-relative (T2 = `first_event_tick`, already known). These constants are NOT directly reusable for OF-3's gradeability logic — `long_visible`/`never_visible`/`never_landed` LABELS replace the old "ungradeable, drop from RT stats" numeric-threshold approach. Do not import these constants into `reaction_timing.py`.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `T0_BACKWARD_SEARCH_CAP_TICKS = 640` (≈10s) is a reasonable starting cap for the backward visibility search. | Pattern 1 | If too small, `never_visible`/`long_visible` rates inflate artificially (label noise, not a correctness bug, but reduces usable N for Gate-B). If too large, cost balloons (BVH raycasts scale linearly with window). Cheap to tune — adjust constant, no algorithm change. Validate on N=1 staged run. |
| A2 | `TARGET_REACHED_THRESHOLD = 3.0°` (fixed) is the better default vs. distance-scaled, pending the D-02 A/B run. | Pattern 3 | If distance-scaled wins the A/B comparison, the constant becomes a function of `distance_to_enemy` — larger code change (T1 detector needs distance at every tick, which it computes anyway via `get_desired_angles` inputs, so cost is low; but the constant becomes a formula not a literal). |
| A3 | `_T0_SEARCH_PARSE_WINDOW_TICKS` (new constant, >= `T0_BACKWARD_SEARCH_CAP_TICKS`) is needed because Phase 9.1's `_SELECTIVE_WINDOW_BEFORE_TICKS=384` is too small for the proposed 640-tick cap. | Pitfall 2 | If the planner instead reduces `T0_BACKWARD_SEARCH_CAP_TICKS` to <= 384, the existing constant could be reused — simpler. This is a tradeoff to make explicitly in PLAN.md, not a hidden assumption. |
| A4 | Gate-B should be primarily a per-player split-half reliability test on donk's own ~3352-episode corpus (high N), with cross-player (D-12, 2-4 pros) as a secondary diagnostic, NOT the primary PASS/FAIL axis. | Pitfall 4 | If the user/planner intends Gate-B to mirror the EXACT prior DDM gate framing (per-player, cross-player N=30), this research's recommendation diverges. This is the SINGLE MOST IMPORTANT open question for D-10 — flagged below as Open Question 1. |
| A5 | `pandas.Series.corr()` + manual Fisher z-transform is sufficient for Gate-B; scipy is not required. | Standard Stack | If scipy IS already installed (likely, given numpy/pandas/awpy stack), `scipy.stats.pearsonr` could be used for convenience (also returns p-value) — purely a style choice, no functional risk either way. |
| A6 | `spirit-vs-the-mongolz-m2-ancient.dem` is still on disk at `for_analysis/spirit/` (it was the Phase 10 SC-4 reference demo). | Pattern 3 | If the demo is missing, substitute any donk demo with a high engagement count — the A/B comparison procedure doesn't depend on this SPECIFIC demo, just one with enough episodes to see distribution shape. |

**Risk flag on A4:** This is the highest-stakes assumption in this document because D-10 explicitly delegates gate-design to the researcher with a user checkpoint. See Open Question 1.

## Open Questions

1. **Gate-B framing: per-player split-half (high N) vs. cross-player comparison (low N, mirrors prior DDM gate)?**
   - What we know: The prior DDM stability gate (2026-05-12) was cross-player, N=30, closed RED 1/30 PASS — this is the "real risk" D-09 references. donk's own corpus (81 demos, ~3352 episodes, ~1428 won) supports a much higher-N per-player split-half.
   - What's unclear: Whether "measurability/stability" for THIS metric (counter-peek/hold-success RT) should be judged primarily on (a) "is the RT measurement internally consistent/reliable for one well-sampled player" (high N, answers a narrower question) or (b) "does the RT metric meaningfully differentiate players" (low N, answers the marketing-relevant question — "donk reacts faster than X").
   - Recommendation: Run BOTH, report both, but make **(a) per-player split-half on donk's corpus the PRIMARY Gate-B PASS/FAIL** (it's the question OF-3 can actually answer with statistical power) and **(b) cross-player (D-12, 2-4 pros) the SECONDARY/diagnostic slice** feeding into the VERDICT narrative but not gating ship/no-ship alone. Concrete proposed thresholds (PRESENT FOR USER APPROVAL per D-10, not locked):
     - **Gate-B PRIMARY (per-player split-half on donk):** Split donk's resolved (`won`+`lost`) episodes into two halves by ODD/EVEN `match_id` (= odd/even demo index, since match_id increments per-demo-per-player in this pipeline — verify this assumption at plan time). Compute mean `rt_visible_to_land_ms` per half across some grouping (e.g., per-demo means, giving N≈40 per half, OR per-round means for higher N). Spearman-Brown corrected r with CI95. **Proposed PASS threshold: r_full >= 0.5 (CI95 lower bound > 0)** — a moderate-reliability bar; r=0.5 with N=40 has CI95 width manageable (SE ≈ 1/sqrt(37) ≈ 0.164, so CI95 ≈ ±0.27 in z-space, translating to roughly r ∈ [0.25, 0.70] if point estimate is 0.5 — wide but the LOWER BOUND > 0 is the meaningful gate, i.e. "reliably non-zero, not noise").
     - **Gate-B SECONDARY (cross-player, D-12):** report median `rt_visible_to_land_ms` per player (donk + 2-4 pros), with CI95 via bootstrap (episodes per player likely 50-300 — bootstrap is appropriate for non-normal RT distributions). No hard PASS/FAIL — feeds the VERDICT narrative ("donk's median RT is X [CI], player B's is Y [CI] — overlapping/non-overlapping").
   - **THIS ENTIRE FRAMING MUST BE PRESENTED TO THE USER FOR APPROVAL PER D-10 BEFORE THE GATE RUN.** The numbers above (r>=0.5, odd/even split, per-demo grouping) are PROPOSALS with stated rationale, not locked decisions.

2. **What grouping unit for split-half (per-demo, per-round, per-episode)?**
   - What we know: Per-episode N is largest (~1428 won episodes for donk) but episodes within the same demo/round are NOT independent (correlated by map, opponent, round-context) — naive per-episode split-half could overstate reliability via pseudo-replication.
   - What's unclear: Whether per-DEMO aggregation (N≈81, independent units) or per-ROUND aggregation (N≈ rounds played, intermediate, partially independent) is the right level.
   - Recommendation: Default to per-DEMO means (N≈81→ ~40/41 per half) as the conservative/independent choice. If N=40 proves too noisy (CI95 too wide to be informative either direction), per-ROUND is the fallback — flag this as a decision point in PLAN.md, resolved during the N=5 staged checkpoint (compute split-half at N=5 demos as a feasibility smoke test before committing to N=81).

3. **Does `match_id` actually increment cleanly per-demo for a single player to support odd/even demo splitting?**
   - What we know: `db_utils.get_next_match_id` does `MAX(match_id)+1` across tables; `reconstruct_all_players` calls `save_to_db(df, db_path, "duel_episodes", match_ids_by_sid[sid])` — one match_id per (demo, player) pair, assigned by the caller (`monesy_rebatch.py` or batch driver).
   - What's unclear: Whether match_ids for donk's 81 demos are CONTIGUOUS/orderable in a way that supports a clean odd/even split, or whether re-batches (Phase 10, monesy rebatch, etc.) have left gaps/duplicates.
   - Recommendation: At plan time, run `SELECT match_id, demo_name FROM duel_episodes WHERE player_steamid=<donk> GROUP BY match_id` to verify 1:1 match_id↔demo_name mapping for donk post-OF-3-rebatch (the rebatch will assign FRESH match_ids since OF-2's `duel_episodes` already has 3352 rows pre-timing — re-running `reconstruct_all_players` likely needs `force_reprocess_demo` per D-14's staged re-batch, which deletes-and-re-inserts with a NEW match_id). Use `demo_name` (stable, not match_id) for the odd/even split key — alphabetical or hash-based parity on `demo_name` is more robust than match_id ordering.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| pandas | T0/T1 detection, split-half stats | Yes (existing) | per requirements.txt | — |
| scipy | optional convenience for Gate-B stats | Not verified | — | `pandas.Series.corr()` + manual Fisher z (no new dep needed) |
| demoparser2 | selective parse_ticks for timing pass | Yes (existing) | per requirements.txt | — |
| sqlite3 | schema migration | Yes (stdlib) | — | — |
| analytics.db | re-batch target, Gate-A/B source | Yes (3352 donk episodes already present from OF-2) | — | — |
| for_analysis/spirit/ demo corpus | re-batch source, D-02 A/B comparison | Yes (81 demos verified per OF-1/OF-2) | — | — |

No blocking missing dependencies. scipy check is discretionary (pandas.corr sufficient).

## Validation Architecture

### Test Framework
| Property | Value |
|-----------|-------|
| Framework | pytest 7.x (configured in pytest.ini) |
| Config file | `pytest.ini` (root) — needs `requires_db` marker added |
| Quick run command | `py -m pytest tests/test_distribution_shape.py --override-ini="addopts=--strict-markers" -x` |
| Full suite command | `py -m pytest --override-ini="addopts=--strict-markers" -q` |

### Phase Requirements -> Test Map

No formal REQ-IDs (milestone-phase, success criteria = SC-3 + CONTEXT.md decisions). Mapping by CONTEXT.md decision IDs:

| Decision | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|---------------------|-------------|
| D-01/D-03 | T1 "lands" predicate: flick (30°@T0) does NOT yield T1=T0+1 | unit (synthetic) | `py -m pytest tests/test_distribution_shape.py::TestSyntheticDistributionShape::test_t1_flick_not_one_tick --override-ini="addopts=--strict-markers" -x` | Wave 0 |
| D-01 | Pre-aimed-at-T0 -> T1=T0, t1_source="lands" | unit (synthetic) | `...::test_t1_pre_aimed_at_t0_lands_immediately` | Wave 0 |
| D-03 | Never-lands -> t1_tick=NULL, t1_source="never_landed" | unit (synthetic) | `...::test_t1_never_lands_labeled` | Wave 0 |
| D-05 | Backward search: continuous-run start, not first-ever-visible | unit (synthetic) | `...::test_t0_backward_run_start_not_first_visible` | Wave 0 |
| D-05 | Cap hit -> t0_source="long_visible", not clamped value treated as real T0 | unit (synthetic) | `...::test_t0_long_visible_labeled_at_cap` | Wave 0 |
| D-06 | Never visible -> t0_tick=NULL, t0_source="never_visible" | unit (synthetic) | `...::test_t0_never_visible_labeled` | Wave 0 |
| D-13 | New columns present on duel_episodes after migration | unit (db_utils) | `py -m pytest tests/test_db_utils.py -k duel_episodes_timing --override-ini="addopts=--strict-markers" -x` | Wave 0 |
| D-15 (tier 2) | Tick-quantum pinning < 10% post-rebatch | `@requires_db` | `py -m pytest tests/test_distribution_shape.py::TestLiveDistributionShape -m requires_db --override-ini="addopts=--strict-markers" -x` | Wave 0 (after N=1 rebatch) |
| D-15 (tier 2) | b5_smoking_gun regression (1-tick land at >2x threshold angle = 0 rows) | `@requires_db` | same file, `::test_no_impossible_one_tick_lands` | Wave 0 |
| SC-3 / D-09/D-10 | Gate-A win-rate slices reproduce OF-1/OF-2 separation on clean data | manual + SQL | `py of3_gate.py --gate=A` (new script) | Wave 0 |
| SC-3 / D-09/D-10/D-11 | Gate-B split-half reliability computed, VERDICT.md written | manual + script | `py of3_gate.py --gate=B` (new script) | Wave 0 |

### Sampling Rate
- **Per task commit:** `py -m pytest tests/test_distribution_shape.py --override-ini="addopts=--strict-markers" -x` (synthetic tier, fast)
- **Per wave merge:** `py -m pytest --override-ini="addopts=--strict-markers" -q` (full suite, ~30-60s)
- **Per re-batch stage (N=1, 5, 81):** `py -m pytest tests/test_distribution_shape.py -m requires_db --override-ini="addopts=--strict-markers" -x` (live-DB tier) + manual inspection artifact review
- **Phase gate:** Full suite green + live-DB tier green at N=81 + Gate-A/Gate-B VERDICT.md written before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_distribution_shape.py` — does not exist, full new file (both tiers)
- [ ] `pytest.ini` `markers =` — add `requires_db: marks tests requiring analytics.db with post-rebatch duel_episodes data`
- [ ] `tests/test_db_utils.py` — add migration test for new `duel_episodes` timing columns (idempotent ALTER TABLE)
- [ ] `reaction_timing.py` (or chosen module name) — does not exist, new module for T0 wrapper + T1 detector
- [ ] `of3_rebatch.py` (or adapted from `monesy_rebatch.py`) — staged N=1->5->81 driver
- [ ] `generate_of3_inspection.py` — 7-section inspection artifact generator (of2_parity_inspection.md pattern)
- [ ] `of3_gate.py` — Gate-A + Gate-B computation script

## Security Domain

Skip — phase has no auth, no input validation beyond existing demo-file parsing (unchanged), no crypto, no network surface. Pure internal-pipeline algorithm + schema + statistics. ASVS categories not applicable (V2/V3/V4/V6 N/A; V5 unchanged from prior phases — demoparser2-validated input).

## Project Constraints (from CLAUDE.md)

| # | Constraint | Source | OF-3 Compliance Note |
|---|-----------|--------|----------------------|
| C1 | `pip install -r requirements.txt` — no new deps preferred | CLAUDE.md Quick Start | Plan should avoid scipy; use pandas.corr() (Standard Stack section) |
| C2 | Test invocation: `py -m pytest --override-ini="addopts=--strict-markers"` (also `--override-ini="addopts=--strict-markers" -q` per memory) | CLAUDE.md Quick Start | All Validation Architecture commands use this form |
| C3 | Edit/Write `*.py` -> autoformat black+ruff+pytest hook | CLAUDE.md Automations | New files (`reaction_timing.py`, `tests/test_distribution_shape.py`, etc.) trigger hook automatically |
| C4 | `/check-phase6` skill required before commits to `t0_detector.py`/`ddm_analyzer.py` | CLAUDE.md Skills | OF-3 reuses `find_t0` (no edit to `t0_detector.py` expected) and `get_desired_angles`/`angular_diff` (no edit to `ddm_analyzer.py` expected — these are read-only reuses). If ANY edit to these files becomes necessary, `/check-phase6` is mandatory. |
| C5 | `cs2_engagement_analysis_results.csv` and `.env` write-blocked | CLAUDE.md Automations | OF-3 writes only to `analytics.db` (`duel_episodes`), new `.py` files, `tests/` — none blocked |
| C6 | Named constants in config.py, no magic numbers | CLAUDE.md Code Style | `TARGET_REACHED_THRESHOLD`, `T0_BACKWARD_SEARCH_CAP_TICKS`, `_T0_SEARCH_PARSE_WINDOW_TICKS` (or equivalent) all go in `config.py` with rationale comments |
| C7 | Strict typing hints (Tuple, List, Dict, Optional) | CLAUDE.md Code Style | `reaction_timing.compute_timing` signature must use these |
| C8 | `@dataclass` for state management | CLAUDE.md Code Style | Consider a `TimingResult` dataclass (t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms) returned by `compute_timing` — cleaner than a raw dict, though `outcome_first.py`'s episode dicts are currently plain dicts (precedent for either) |
| C9 | Tickrate=64, ms_per_tick=15.625, formula `ticks * (1000/tickrate)` | CLAUDE.md Tech Stack | All RT derived columns use this formula; tick-quantum multiples for distribution-shape checks are 15.625, 31.25, 46.875, 62.5 ms |
| C10 | Isolation Rule: never combine unrelated data categories | CLAUDE.md Tech Stack | `duel_episodes` timing columns stay separate from `engagements` table (D-16); Gate-A/B scripts query `duel_episodes` only |
| Ops | SteamID coercion via `_coerce_sid` string-path; never `pd.to_numeric`/`pd.read_sql` on sid columns | OF-2-CONTEXT, OF-1 found-bug | `reaction_timing.py` and `of3_gate.py` must use `_coerce_sid` (import from `outcome_first.py`) for any sid handling |
| Ops | Subprocess env: `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` | memory (recurring gotcha) | `of3_rebatch.py` driver must set this env for any subprocess.run/Popen calls |
| Ops | Python launcher `py`, not `python` | OF-2-CONTEXT | All commands in this research and PLAN.md use `py` |

## Sources

### Primary (HIGH confidence — direct codebase reads, verified 2026-06-10)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\t0_detector.py` (lines 75-260) — `find_t0` signature, BVH+AABB algorithm, `find_visible_enemies_at_tick`
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\config.py` (lines 100-200) — T1 constants, selective-parse window constants, T0/T2 gradeability constants
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\outcome_first.py` (full 447 lines, read 1-339) — `collect_exchanges`, `group_episodes`, `reconstruct_all_players`, `_coerce_sid`
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\db_utils.py` (lines 60-220) — `_migrate_schema`, `duel_episodes` CREATE TABLE, idempotent ALTER TABLE pattern
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py` (lines 95-122) — `get_desired_angles`, `angular_diff` static methods
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\pytest.ini` — marker registration, `--strict-markers`, addopts
- `analytics.db` (live query, 2026-06-10) — `duel_episodes` schema (12 columns, no timing columns yet), 3352 donk episodes (1428 won / 1090 lost / 834 unresolved), 81 distinct demos
- `.planning/phases/OF-3-revalidation-measurability-gate/OF-3-CONTEXT.md` — locked decisions D-01 through D-16
- `.planning/milestones/outcome-first-ROADMAP.md` — SC-3, CAVEAT-1/2
- `.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md` — gate numbers (56.7% win-rate, 9.7pp separation)
- `.planning/phases/OF-2-core-rebuild/OF-2-PARITY.md` — band-miscalibration lesson
- `.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md` — inherited locked decisions (gun-only, find_t0 kept)
- `b5_smoking_gun.md` (repo root) — 15 impossible rows, crosshair-angle distribution at 1-tick T1
- `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/10-RESEARCH.md` — prior T1 fix patterns, `t1_source` precedent, pytest invocation, ALTER TABLE pattern

### Secondary (MEDIUM confidence)
- CS2 player hitbox dimensions (~32 units wide) and pro flick speeds (1000-1500°/s) — `[ASSUMED]` from training knowledge, used only to justify the `MIN_THRESHOLD_FLOOR=0.5°` and the "1-tick flick from 86° is impossible" framing in Pattern 2. Not load-bearing for any PASS/FAIL threshold — illustrative only.

### Tertiary (LOW confidence — flagged for validation)
- Split-half reliability r>=0.5 threshold (Open Question 1) — derived from first principles (CI95 lower bound > 0 at N≈40), NOT benchmarked against any external CS2-analytics or sports-science reliability standard. **This number MUST go through the D-10 user checkpoint before being locked.**

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — zero new dependencies, all primitives verified in codebase
- Architecture (T0/T1 algorithm design): HIGH — directly grounded in verified `find_t0`/`get_desired_angles` signatures and the B-5 bug mechanism
- Pitfalls: HIGH — each grounded in verified file content or documented project history (Phase 9.1 windowing, pytest strict-markers, B-1 floor mechanism)
- Gate-B threshold derivation (D-10): MEDIUM — statistically sound formulas (Fisher z, Spearman-Brown) but the SPECIFIC threshold (r>=0.5) and grouping unit (per-demo) are proposals requiring user approval, not verified against an external benchmark
- D-02 threshold A/B procedure: MEDIUM-HIGH — comparison procedure is sound and grounded in the quantization-floor rule; the specific hitbox/distance-scaling formula is `[ASSUMED]` (illustrative, not load-bearing)

**Research date:** 2026-06-10
**Valid until:** 30 days (project-internal scope, no fast-moving external dependencies)

## Phase Requirements

None — milestone-phase (no REQ-IDs in REQUIREMENTS.md, file does not exist for this project). Scope defined by `.planning/milestones/outcome-first-ROADMAP.md` SC-3 + `OF-3-CONTEXT.md` decisions D-01 through D-16.

| ID | Description | Research Support |
|----|--------------|-------------------|
| D-01/D-02/D-03 | New T1 "lands" detector, threshold A/B, never_landed label | Pattern 2, Pattern 3, Wave 0 Gaps |
| D-04 | Old `_detect_t1` deprecated/untouched | State of the Art, Architectural Responsibility Map |
| D-05/D-06/D-07/D-08 | T0 backward search, never_visible label, correctness-first, all episodes timed | Pattern 1, Pitfall 2, Pitfall 3 |
| D-09/D-10/D-11/D-12 | Two-layer gate, thresholds + rationale, STOP on Gate-B FAIL, donk+2-4 pros | Open Questions 1-3, Code Examples (split-half formula) |
| D-13 | Timing columns on duel_episodes via idempotent migration | Code Examples (ALTER TABLE) |
| D-14 | Staged N=1->5->81 rebatch with inspection artifacts | Don't Hand-Roll (monesy_rebatch.py / of2_parity_inspection.md reuse) |
| D-15 | Two-tier distribution-shape suite | Pattern 4, Pitfall 6, Wave 0 Gaps |
| D-16 | Old engagements table untouched, duel_episodes sole source | Pitfall 5, Architectural Responsibility Map |
