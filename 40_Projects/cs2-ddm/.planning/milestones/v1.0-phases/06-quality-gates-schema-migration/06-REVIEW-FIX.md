---
phase: 06-quality-gates-schema-migration
fixed_at: 2026-05-01T00:00:00Z
review_path: .planning/phases/06-quality-gates-schema-migration/06-REVIEW.md
iteration: 1
findings_in_scope: 9
fixed: 9
skipped: 0
status: all_fixed
---

# Phase 06: Code Review Fix Report

**Fixed at:** 2026-05-01
**Source review:** .planning/phases/06-quality-gates-schema-migration/06-REVIEW.md
**Iteration:** 1

**Summary:**
- Findings in scope: 9
- Fixed: 9
- Skipped: 0

## Fixed Issues

### CR-01: SQL injection via f-string table name in `db_utils.save_to_db`

**Files modified:** `db_utils.py`
**Commit:** 8e79699
**Applied fix:** Added `_ALLOWED_TABLES = {"engagements", "duel_attempts"}` constant and a guard at the top of `save_to_db` that raises `ValueError` for any table name not in the whitelist.

---

### CR-02: DELETE not committed before `to_sql` append — data loss on crash

**Files modified:** `db_utils.py`
**Commit:** 8e79699 (same commit as CR-01)
**Applied fix:** Wrapped the `conn.execute(DELETE)` and `df.to_sql(...)` calls in a `with conn:` inner context manager so both operations share one transaction. Removed the now-redundant explicit `conn.commit()`.

---

### CR-03: Silent dedup bypass on CSV read error in `save_attempts`

**Files modified:** `kill_rate_analysis.py`
**Commit:** 56191e7
**Applied fix:** Changed bare `except Exception: combined = rows` to log a warning and `return` immediately, preventing any write when the existing CSV cannot be read.

---

### WR-01: NaN velocity always evaluates to `False` — wrong engagement classification

**Files modified:** `duel_attempts.py`
**Commit:** 7517069
**Applied fix:** `_player_velocity` now returns `float("nan")` instead of `0.0` when tick data is missing. The `_process_cluster` engagement assignment now uses `not math.isnan(player_velocity) and player_velocity >= self.velocity_peek_threshold` so missing data defaults to "hold" rather than silently faking a 0 u/s hold.

---

### WR-02: `rt_t1_t2` fallback uses T0 instead of T1 — inflated metric

**Files modified:** `ddm_analyzer.py`
**Commit:** f34c2bd
**Applied fix:** Removed the `elif t2_tick >= t0_tick: rt_t1_t2 = (t2_tick - t0_tick) * ms` branch entirely. When T1 is unknown `rt_aim_to_hit_ms` is now `np.nan` as intended.
**Note:** requires human verification (logic change to metric computation).

---

### WR-03: Unguarded `int(target_enemy_id)` cast crashes on non-numeric steamids

**Files modified:** `ddm_analyzer.py`
**Commit:** f34c2bd (same commit as WR-02)
**Applied fix:** Wrapped `int(target_enemy_id)` in `try/except (ValueError, TypeError)` producing `enemy_sid_int = None` on failure. `_compute_crosshair_angle_at_t0` is only called when `enemy_sid_int is not None`, returning `None` for the angle otherwise.

---

### WR-04: `_check_kill` does not guard missing `user_steamid` column

**Files modified:** `duel_attempts.py`
**Commit:** 954bbb7
**Applied fix:** Expanded the existing `attacker_steamid` column guard to also check `user_steamid`, returning `False` if either column is absent.

---

### WR-05: `parse_smoke_events` uses tickrate 64 hardcoded

**Files modified:** `t0_detector.py`, `ddm_analyzer.py`
**Commit:** 4c90fbe
**Applied fix:** Added `tickrate: int = 64` parameter to `T0Detector.parse_smoke_events` (and the module-level alias). The fallback duration calculation now uses `_SMOKE_FALLBACK_DURATION_S * tickrate`. The call site in `ddm_analyzer.py` now passes `tickrate=self.tickrate`.

---

### WR-06: `run_analysis.py` calls `db_utils.save_to_db` twice for the same data

**Files modified:** `run_analysis.py`
**Commit:** 027b849
**Applied fix:** Removed the `db_utils.save_to_db(results_df, DB_PATH, "engagements", match_id)` call from `run_analysis.py` and the now-unused `import db_utils` / `from config import DB_PATH` imports. The call inside `analyze_demo()` handles persistence.

---

## Test Results

`python -m pytest --override-ini="addopts=--strict-markers" -x -q`

**256 passed in 1.50s** — all tests green after fixes.

---

_Fixed: 2026-05-01_
_Fixer: Claude (gsd-code-fixer)_
_Iteration: 1_
