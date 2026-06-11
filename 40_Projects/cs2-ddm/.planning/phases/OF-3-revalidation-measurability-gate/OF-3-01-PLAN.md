---
phase: OF-3
plan: "01"
type: tdd
wave: 1
depends_on: []
files_modified:
  - config.py
  - db_utils.py
  - pytest.ini
  - tests/test_reaction_timing.py
  - tests/test_distribution_shape.py
  - tests/test_db_utils.py
autonomous: true
requirements: [SC-3]
must_haves:
  truths:
    - "New duel_episodes timing columns exist after init_db (D-13)"
    - "requires_db pytest marker registered (D-15 tier-2 enablement)"
    - "RED tests pin the T1 LANDS predicate and T0 backward-search contract before any implementation (TDD convention)"
  artifacts:
    - path: "config.py"
      provides: "TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS, _T0_SEARCH_PARSE_WINDOW_TICKS constants (D-02, D-05)"
      contains: "TARGET_REACHED_THRESHOLD"
    - path: "db_utils.py"
      provides: "duel_episodes timing column migration (D-13)"
      contains: "_episode_timing_migrations"
    - path: "tests/test_reaction_timing.py"
      provides: "RED stubs for T0/T1 detection (D-01,D-03,D-05,D-06)"
    - path: "tests/test_distribution_shape.py"
      provides: "two-tier distribution-shape suite scaffold (D-15)"
    - path: "pytest.ini"
      provides: "requires_db marker registration (D-15)"
      contains: "requires_db"
  key_links:
    - from: "tests/test_db_utils.py"
      to: "db_utils._migrate_schema"
      via: "init_db twice on same tmp_path, assert duel_episodes timing columns present + idempotent"
      pattern: "duel_episodes.*t0_tick"
---

<objective>
Lay the TDD + schema + config foundation for OF-3 reaction timing. Write RED tests that pin the NEW T1 "crosshair LANDS" predicate (D-01) and the T0 backward-search contract (D-05) BEFORE any implementation exists. Add the `duel_episodes` timing columns (D-13), the new config constants (D-02/D-05), and register the `requires_db` pytest marker (D-15).

Purpose: Establish the contract the implementation in OF-3-02 must satisfy, and the live-DB regression infrastructure OF-3-03 will run after re-batch. TDD-first is the project convention (OF-2 precedent: 9 RED tests → GREEN) and the explicit guard against re-introducing the B-5 class of bug.
Output: config constants, idempotent schema migration, two new test files (RED), an updated `tests/test_db_utils.py`, and a registered `requires_db` marker.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-CONTEXT.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md
@b5_smoking_gun.md

<interfaces>
Contracts the implementation (OF-3-02) MUST satisfy. RED tests in this plan import a NOT-YET-EXISTING module `reaction_timing.py`. Define the expected public surface here so the tests are deterministic:

reaction_timing.compute_timing(
    episode: Dict,          # one duel_episodes row as dict; keys include
                            #   "player_steamid", "opponent_steamid",
                            #   "first_event_tick" (== T2 anchor), "last_event_tick"
    ticks_df: pd.DataFrame, # parsed tick frame covering the search window
    t0_detector,            # a t0_detector.T0Detector instance
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Dict           # snake_case keys matching the NEW duel_episodes columns:
                    #   t0_tick, t0_source, t1_tick, t1_source,
                    #   crosshair_angle_at_t0_deg,
                    #   rt_visible_to_land_ms, rt_visible_to_hit_ms

t0_source ∈ {"BVH+AABB", "long_visible", "never_visible"}
t1_source ∈ {"lands", "never_landed", "no_t0"}  ("no_t0" when t0_tick is None)

find_t0 signature being wrapped (DO NOT modify t0_detector.py):
    find_t0(all_ticks_df, player_steamid, enemy_steamid,
            search_start_tick, search_end_tick,
            active_smokes=None, flash_intervals=None, ticks_by_sid=None)
        -> Tuple[Optional[int], str]   # (t0_tick, method) or (None, "not_found")

duel_episodes existing columns (db_utils.py CREATE TABLE, do not change):
    match_id, demo_name, player_steamid, opponent_steamid,
    first_event_tick, last_event_tick, outcome, initiator,
    p_was_attacker_first, n_hits_p_on_e, n_hits_e_on_p, anchor_weapon
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add OF-3 config constants + duel_episodes timing migration + requires_db marker</name>
  <files>config.py, db_utils.py, pytest.ini</files>
  <read_first>
    - config.py (read lines 100-165: the existing T0/T1 constant block + rationale-comment style to replicate)
    - db_utils.py (read lines 60-150: _migrate_schema, the _eng_migrations ALTER loop at ~84-107, and the duel_episodes CREATE TABLE at 131-146)
    - pytest.ini (read full: current `markers =` section has `slow` and `integration` only)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (config.py and db_utils.py analog sections)
  </read_first>
  <behavior>
    - init_db on a fresh tmp_path DB creates duel_episodes with columns t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms present
    - Calling init_db twice on the SAME db is idempotent (no error, columns present both times)
    - config exposes TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS, _T0_SEARCH_PARSE_WINDOW_TICKS
  </behavior>
  <action>
1. **config.py** — append after the existing T1 constant block (after line ~161, same named-constant + multi-line-rationale-comment style as `T0_MIN_OFFSET_TICKS` at line ~108):

```python
# OF-3 (2026-06-10): reaction timing on KNOWN opponent (duel_episodes path).
# TARGET_REACHED_THRESHOLD: crosshair "LANDS" tolerance for the new T1 predicate
#   (D-01/D-02). T1 = first tick angular_dist(crosshair, enemy) <= this, sustained
#   T1_SUSTAINED_AIM_TICKS+1 ticks. This is a LANDING criterion (wider than the
#   deprecated pre-aim T1_NOT_AIMED_THRESHOLD=1.0). Quantization rule: demoparser2
#   angular step ~0.022 deg; 3.0/0.022 ~= 136x, clears the >=3x-step rule comfortably.
#   D-02 A/B (fixed 3.0 vs distance-scaled) is resolved on 1 demo in OF-3-02; this is
#   the locked default unless that A/B run shows >10% tick-quantum pinning or >10
#   impossible b5-class rows that distance-scaling resolves.
TARGET_REACHED_THRESHOLD: float = 3.0

# T0_BACKWARD_SEARCH_CAP_TICKS: cost-cap for the D-05 backward visibility search.
#   This is a SEARCH BOUNDARY, NOT a value clamp -- when the cap is hit the row is
#   LABELED t0_source="long_visible" (NOT assigned a clamped T0 that masquerades as a
#   real measurement). This is the explicit D-05 distinction vs the B-1 floor-artifact
#   class. 640 ticks ~= 10s @ 64Hz; double the deprecated _SELECTIVE_WINDOW_BEFORE_TICKS
#   (384) because backward T0 search looks further back than the old hurt-anchored window.
#   Tunable on the N=1 staged run (lowering it is label-safe: more long_visible, no clamp).
T0_BACKWARD_SEARCH_CAP_TICKS: int = 640

# _T0_SEARCH_PARSE_WINDOW_TICKS: ticks BEFORE first_event_tick that the OF-3 timing
#   pass must parse_ticks so find_t0 can scan the full backward cap. Must be
#   >= T0_BACKWARD_SEARCH_CAP_TICKS (Pitfall 2: the deprecated _SELECTIVE_WINDOW_BEFORE_TICKS
#   =384 is too small for the 640-tick cap -> find_t0 would falsely return never_visible).
_T0_SEARCH_PARSE_WINDOW_TICKS: int = 640
```

2. **db_utils.py** — in `_migrate_schema`, insert the duel_episodes timing migration AFTER the `duel_episodes` CREATE TABLE block (line 146) and BEFORE the `processed_matches` block (line 148). Use the exact `_eng_migrations` ALTER-loop pattern (lines 84-107):

```python
        # OF-3 (2026-06-10): reaction timing columns on duel_episodes (D-13).
        # Idempotent ADD COLUMN (mirrors the engagements t1_source precedent).
        # NULL on legacy (pre-OF-3) rows; populated by reaction_timing.compute_timing.
        ep_cols = {c[1] for c in conn.execute("PRAGMA table_info(duel_episodes)").fetchall()}
        _episode_timing_migrations = [
            ("t0_tick", "INTEGER DEFAULT NULL"),
            ("t0_source", "TEXT DEFAULT NULL"),       # 'BVH+AABB' | 'long_visible' | 'never_visible'
            ("t1_tick", "INTEGER DEFAULT NULL"),
            ("t1_source", "TEXT DEFAULT NULL"),       # 'lands' | 'never_landed' | 'no_t0'
            ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
            ("rt_visible_to_land_ms", "REAL DEFAULT NULL"),
            ("rt_visible_to_hit_ms", "REAL DEFAULT NULL"),
        ]
        for col, col_def in _episode_timing_migrations:
            if col not in ep_cols:
                conn.execute(f"ALTER TABLE duel_episodes ADD COLUMN {col} {col_def}")
```
   (Match the surrounding indentation level of the existing CREATE TABLE / ALTER blocks in `_migrate_schema`.)

3. **pytest.ini** — in the `markers =` block (currently `slow` and `integration`), add a third line, preserving existing indentation:

```ini
    requires_db: marks tests requiring analytics.db with post-rebatch duel_episodes data (skip if absent)
```
  </action>
  <verify>
    <automated>py -m pytest tests/test_db_utils.py --override-ini="addopts=--strict-markers" -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "TARGET_REACHED_THRESHOLD" config.py` returns a line with `= 3.0`
    - `grep -n "T0_BACKWARD_SEARCH_CAP_TICKS" config.py` returns `= 640`
    - `grep -n "_T0_SEARCH_PARSE_WINDOW_TICKS" config.py` returns `= 640`
    - `grep -n "_episode_timing_migrations" db_utils.py` returns a match inside `_migrate_schema`
    - `grep -n "requires_db" pytest.ini` returns a registered marker line
    - Running `init_db` on a fresh DB then `PRAGMA table_info(duel_episodes)` lists all 7 new columns (assert in the test from Task 3)
  </acceptance_criteria>
  <done>config constants present with rationale comments; duel_episodes gains 7 timing columns idempotently; requires_db marker registered.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: RED tests for T0 backward search + T1 LANDS predicate (tests/test_reaction_timing.py)</name>
  <files>tests/test_reaction_timing.py</files>
  <read_first>
    - tests/test_outcome_first.py (read lines 1-185: synthetic DataFrame fixture style + duel_episodes round-trip test; reuse fixture-construction idiom)
    - t0_detector.py (read lines 75-130: find_t0 signature/return contract + is_visible — the primitives compute_timing wraps)
    - ddm_analyzer.py (read lines 105-122: get_desired_angles + angular_diff — the geometry compute_timing reuses)
    - b5_smoking_gun.md (the bug class the flick test must guard against)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (test_distribution_shape.py + reaction_timing.py analog sections)
  </read_first>
  <behavior>
    These tests import `reaction_timing.compute_timing` which does NOT exist yet — they MUST fail at import/collection (RED). The contract they pin:
    - test_t1_flick_not_one_tick: crosshair 30deg off target at T0 (the b5 class) → resulting t1_tick is NOT t0_tick+1. Physically a 30deg flick cannot land+sustain in 1 tick.
    - test_t1_pre_aimed_at_t0_lands_immediately: crosshair already within TARGET_REACHED_THRESHOLD at T0 and stays → t1_tick == t0_tick, t1_source == "lands" (no separate pre_aimed branch, unlike Phase 10).
    - test_t1_never_lands_labeled: crosshair never gets within threshold in [t0, first_event_tick] → t1_tick is None, t1_source == "never_landed".
    - test_t0_backward_run_start_not_first_visible: enemy visible at tick A, occluded, visible again at run B..T2 → T0 == start of the run CONTAINING the first event (B), NOT the first-ever-visible tick (A). (Pitfall 3 — the most important algorithmic detail.)
    - test_t0_long_visible_labeled_at_cap: visibility run extends to the search cap → t0_source == "long_visible", t0_tick == search_start (cap), NOT a value treated as a real measured T0. No clamp.
    - test_t0_never_visible_labeled: BVH never sees the enemy in the window → t0_tick is None, t0_source == "never_visible".
    - test_rt_columns_derived: when t0 and t1 both resolve, rt_visible_to_land_ms == (t1_tick - t0_tick) * 15.625 and rt_visible_to_hit_ms == (first_event_tick - t0_tick) * 15.625.
  </behavior>
  <action>
Create `tests/test_reaction_timing.py`. Import the not-yet-existing module at top so collection fails RED until OF-3-02 lands:

```python
from __future__ import annotations
import math
import pandas as pd
import pytest
from reaction_timing import compute_timing  # NOT YET IMPLEMENTED -> RED
from config import TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS
```

Build synthetic tick frames with columns `tick, steamid, X, Y, Z, pitch, yaw` for player + enemy. Place the enemy at a fixed world position; compute the player's desired (pitch, yaw) toward the enemy with the same math as `ddm_analyzer.get_desired_angles` (you may import and call it to generate fixture angles so the test stays consistent with production geometry). Steer `yaw`/`pitch` per tick to construct each scenario:

- **flick**: at and just after T0, set crosshair 30deg off desired yaw; only reach within threshold ~5 ticks later. Assert `result["t1_tick"] != result["t0_tick"] + 1`.
- **pre-aimed**: crosshair within `TARGET_REACHED_THRESHOLD` of desired from T0 onward. Assert `result["t1_tick"] == result["t0_tick"]` and `result["t1_source"] == "lands"`.
- **never-lands**: crosshair stays >= 2*TARGET_REACHED_THRESHOLD the whole window. Assert `result["t1_tick"] is None` and `result["t1_source"] == "never_landed"`.
- **backward-run-start**: make `is_visible` true at an early tick A, false for a gap, true again from B through first_event_tick. Use a fake/stub T0Detector whose `is_visible`/`find_t0` is driven by a per-tick visibility map you control (do NOT call real BVH — synthetic). Assert `result["t0_tick"] == B`, not A.
- **long-visible**: visibility true for the entire cap window. Assert `result["t0_source"] == "long_visible"` and `result["t0_tick"] == first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS`.
- **never-visible**: stub returns not-visible for all ticks. Assert `result["t0_tick"] is None`, `result["t0_source"] == "never_visible"`, and `result["t1_source"] == "no_t0"`.
- **rt-derived**: a resolvable case; assert both rt columns via the `MS_PER_TICK = 1000/64 = 15.625` formula (use `pytest.approx`).

Use a lightweight stub T0Detector (a small class with `find_t0` and `is_visible` reading a dict you build) so these tests need NO demo files and NO real BVH — they pin the WRAPPER logic (backward continuity + labels), which is the genuinely-new code. Keep each scenario in its own `def test_...` with a docstring naming the decision (D-01/D-03/D-05/D-06).
  </action>
  <verify>
    <automated>py -m pytest tests/test_reaction_timing.py --override-ini="addopts=--strict-markers" -q</automated>
  </verify>
  <acceptance_criteria>
    - Test run fails RED with a collection/import error referencing `reaction_timing` (module not found) OR all tests fail — this is the expected RED state for a TDD Wave-0 plan; the executor commits the RED tests and does NOT implement reaction_timing.py in this plan
    - `grep -c "def test_" tests/test_reaction_timing.py` (filter header: `grep -v '^#' tests/test_reaction_timing.py | grep -c "def test_"`) returns >= 7
    - Each of these test names is present: `grep -n "test_t1_flick_not_one_tick\|test_t1_pre_aimed_at_t0_lands_immediately\|test_t1_never_lands_labeled\|test_t0_backward_run_start_not_first_visible\|test_t0_long_visible_labeled_at_cap\|test_t0_never_visible_labeled\|test_rt_columns_derived" tests/test_reaction_timing.py` shows all 7
    - No production module `reaction_timing.py` is created in this plan (it lands in OF-3-02): `test ! -f reaction_timing.py` (or note its absence)
  </acceptance_criteria>
  <done>tests/test_reaction_timing.py exists with >=7 RED tests pinning the T0/T1 contract; suite is RED on these tests only (expected); reaction_timing.py NOT yet created.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: Distribution-shape synthetic tier + db_utils migration test</name>
  <files>tests/test_distribution_shape.py, tests/test_db_utils.py</files>
  <read_first>
    - tests/test_db_utils.py (read full or grep for the existing engagements/t1_source migration-idempotency test to copy its structure)
    - tests/test_outcome_first.py (lines 167-185: test_db_write_duel_episodes round-trip pattern for the @requires_db tier scaffold)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md (Pattern 4: two-tier suite spec — synthetic always-on + @requires_db checks 1-5)
    - b5_smoking_gun.md (the physics-bounded regression the tier-2 test guards)
  </read_first>
  <behavior>
    - Tier 1 (synthetic, always-on): reuse the reaction_timing scenarios so they ALSO assert distribution-shape invariants on small synthetic batches: a flick batch produces 0 rows with (t1_tick == t0_tick+1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD). These import reaction_timing → RED until OF-3-02 (acceptable; same Wave-0 RED state).
    - Tier 2 (@requires_db): functions marked `@pytest.mark.requires_db` that query the real analytics.db duel_episodes and assert: (1) tick-quantum pinning < 10%, (2) MIN(rt_visible_to_land_ms) >= 0, (3) report never_landed%/never_visible% (flag >50%), (4) physics-bounded: 0 rows where t1_tick==t0_tick+1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD, (5) per-player median rt < 100ms flagged (soft warn, not fail). These must SKIP gracefully when analytics.db is absent or duel_episodes has 0 rows with non-NULL t1_tick (so they don't fail before re-batch in OF-3-03).
    - tests/test_db_utils.py gains a test asserting the 7 new duel_episodes timing columns exist after init_db and that a second init_db is idempotent.
  </behavior>
  <action>
1. **tests/test_db_utils.py** — add `test_duel_episodes_timing_migration_idempotent(tmp_path)`: call `init_db(str(tmp_path/"t.db"))` twice; after each, `PRAGMA table_info(duel_episodes)` must include all 7 columns: `t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms`. Assert no exception on the second call. Model on the existing engagements/t1_source idempotency test in this file.

2. **tests/test_distribution_shape.py** — create with two classes:

```python
from __future__ import annotations
import math
import sqlite3
import pandas as pd
import pytest
from config import TARGET_REACHED_THRESHOLD

MS_PER_TICK = 1000.0 / 64.0
TICK_QUANTA_MS = [15.625, 31.25, 46.875, 62.5]

class TestSyntheticDistributionShape:
    """Tier 1 -- always-on, no DB, no demos (D-15). Imports reaction_timing -> RED until OF-3-02."""
    def test_flick_batch_no_impossible_one_tick_lands(self):
        from reaction_timing import compute_timing  # RED until OF-3-02
        # build N synthetic flick episodes (30deg off at T0); run compute_timing on each;
        # assert 0 rows with (t1_tick == t0_tick+1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD)
        ...

class TestLiveDistributionShape:
    """Tier 2 -- @requires_db, runs after each re-batch stage (D-15)."""
    @pytest.mark.requires_db
    def test_tick_quantum_pinning_below_10pct(self):
        rows = _load_resolved_rt()  # helper: open analytics.db, SELECT rt_visible_to_land_ms WHERE t1_source='lands'
        if not rows:
            pytest.skip("duel_episodes has no resolved timing rows yet (pre-rebatch)")
        pinned = sum(1 for v in rows if any(abs(v - q) < 0.01 for q in TICK_QUANTA_MS))
        assert pinned / len(rows) < 0.10

    @pytest.mark.requires_db
    def test_min_rt_non_negative(self): ...
    @pytest.mark.requires_db
    def test_no_impossible_one_tick_lands(self):
        # 0 rows where t1_tick == t0_tick + 1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD
        ...
    @pytest.mark.requires_db
    def test_never_landed_never_visible_pct_reported(self): ...  # assert each <= 0.50 (diagnostic)
```
   Write a module-level helper `_load_resolved_rt()` that opens `analytics.db` via `sqlite3` (use `DB_PATH` from `config`/`db_utils`), runs the SELECT with `cursor.fetchall()` (NEVER `pd.read_sql` — SteamID precision rule; though these queries select RT/angle floats, keep the fetchall convention), and returns a plain list. SKIP (not fail) when the DB file is absent or the query returns 0 rows — so this tier is green-or-skipped before OF-3-03's re-batch populates data.
  </action>
  <verify>
    <automated>py -m pytest tests/test_db_utils.py tests/test_distribution_shape.py -m "not requires_db" --override-ini="addopts=--strict-markers" -q</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "test_duel_episodes_timing_migration_idempotent" tests/test_db_utils.py` returns a match; that test PASSES (migration is implemented in Task 1)
    - `grep -n "requires_db" tests/test_distribution_shape.py` shows >=3 marked methods
    - `grep -n "TICK_QUANTA_MS" tests/test_distribution_shape.py` shows the quantum list [15.625, 31.25, 46.875, 62.5]
    - Running with `-m "not requires_db"`: the Tier-1 synthetic test is RED (imports reaction_timing — expected Wave-0 state); the db_utils migration test is GREEN
    - Running `py -m pytest -m requires_db tests/test_distribution_shape.py --override-ini="addopts=--strict-markers"` reports the requires_db tests as SKIPPED (analytics.db duel_episodes has no timing rows yet), NOT failed
    - `grep -n "pd.read_sql" tests/test_distribution_shape.py` returns nothing (fetchall convention honored)
  </acceptance_criteria>
  <done>db_utils migration test GREEN; distribution-shape file has Tier-1 synthetic (RED, awaiting OF-3-02) + Tier-2 @requires_db (skips cleanly pre-rebatch).</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|-|-|
| demo file → parser | Untrusted .dem input; unchanged from prior phases (demoparser2-validated) |
| analytics.db ← pipeline | Local SQLite write; no external network surface |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-|-|-|-|-|
| T-OF3-01 | Tampering | dynamic SQL in db_utils ALTER TABLE | accept | Column names are hard-coded literals in `_episode_timing_migrations` (no user input interpolated); f-string only formats trusted constants |
| T-OF3-02 | Information disclosure | SteamID precision in test SQL | mitigate | Tier-2 tests use `cursor.fetchall()`, never `pd.read_sql`/`pd.to_numeric` on sid columns (project rule) |

No network, auth, crypto, or user-input surface in this phase. ASVS L1 categories V2/V3/V4/V6 N/A.
</threat_model>

<verification>
- `py -m pytest tests/test_db_utils.py --override-ini="addopts=--strict-markers" -q` → migration test GREEN
- `py -m pytest tests/test_reaction_timing.py tests/test_distribution_shape.py -m "not requires_db" --override-ini="addopts=--strict-markers" -q` → RED on reaction_timing imports (expected Wave-0 TDD state), GREEN on db_utils migration
- `py -m pytest -m requires_db --override-ini="addopts=--strict-markers"` → requires_db tests SKIP cleanly (no analytics.db timing rows yet)
</verification>

<success_criteria>
- config.py has TARGET_REACHED_THRESHOLD=3.0, T0_BACKWARD_SEARCH_CAP_TICKS=640, _T0_SEARCH_PARSE_WINDOW_TICKS=640 with rationale comments
- duel_episodes gains 7 timing columns idempotently (D-13)
- requires_db marker registered (D-15)
- tests/test_reaction_timing.py has >=7 RED tests pinning the T0/T1 contract (D-01/D-03/D-05/D-06)
- tests/test_distribution_shape.py has Tier-1 synthetic + Tier-2 @requires_db scaffold (D-15)
- reaction_timing.py NOT created (deferred to OF-3-02)
</success_criteria>

<output>
After completion, create `.planning/phases/OF-3-revalidation-measurability-gate/OF-3-01-SUMMARY.md`
</output>
