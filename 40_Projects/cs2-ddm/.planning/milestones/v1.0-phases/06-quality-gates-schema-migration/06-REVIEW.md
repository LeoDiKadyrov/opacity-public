---
phase: 06-quality-gates-schema-migration
reviewed: 2026-05-01T00:00:00Z
depth: standard
files_reviewed: 10
files_reviewed_list:
  - ddm_analyzer.py
  - t0_detector.py
  - config.py
  - csv_utils.py
  - db_utils.py
  - duel_attempts.py
  - kill_rate_analysis.py
  - visualize_results.py
  - app.py
  - run_analysis.py
findings:
  critical: 3
  warning: 6
  info: 4
  total: 13
status: issues_found
---

# Phase 06: Code Review Report

**Reviewed:** 2026-05-01
**Depth:** standard
**Files Reviewed:** 10
**Status:** issues_found

## Summary

Ten files reviewed covering the full Phase 6 deliverables: SQLite dual-write (`db_utils.py`), teammate/overlap quality gates, `player_steamid` schema addition, `DuelAttemptFinder`, and kill-rate analysis. The core pipeline logic is structurally sound. Three blockers found: a SQL injection vector in `db_utils.py`, a data-loss race in `save_to_db` where the DELETE is not committed before the `to_sql` append, and a silent data-corruption path in `save_attempts` where a CSV read exception causes dedup to be skipped entirely, silently duplicating rows. Six warnings cover correctness gaps including a `float('nan') >= threshold` comparison that always returns False for NaN velocity, a missing `user_steamid` column guard in `_check_kill`, an incorrect `rt_t1_t2` fallback computation, and an unguarded `int()` cast on `target_enemy_id` that will crash on non-numeric values.

---

## Critical Issues

### CR-01: SQL Injection via f-string table name in `db_utils.save_to_db`

**File:** `db_utils.py:34`
**Issue:** The `table` parameter is interpolated directly into the DELETE statement with an f-string. If any caller passes a user-controlled or externally-sourced table name, arbitrary SQL can be executed. The `to_sql` call on line 35 uses `table` as well but pandas quotes it internally — the DELETE does not.
**Fix:**
```python
# Whitelist allowed table names
_ALLOWED_TABLES = {"engagements", "duel_attempts"}

def save_to_db(df, db_path, table, match_id):
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table '{table}'. Allowed: {_ALLOWED_TABLES}")
    ...
    conn.execute(
        f"DELETE FROM {table} WHERE match_id = ?",  # safe: table is now whitelisted
        (str(match_id),),
    )
```

---

### CR-02: DELETE not committed before `to_sql` append — data loss on crash

**File:** `db_utils.py:32-36`
**Issue:** `conn.execute("DELETE …")` runs in autocommit-off mode (sqlite3 default). The `df.to_sql(…, if_exists="append")` then appends. If the process crashes between the DELETE and `conn.commit()` on line 37, the transaction is rolled back and both the DELETE and the inserts are lost — but on a *successful* path this is fine. The real bug is subtler: `pandas.to_sql` opens its own internal cursor and calls `commit()` on some pandas versions, which commits the preceding DELETE without the new rows being present if `to_sql` itself then fails midway. The result is the existing rows are gone and the new partial insert is not committed. Wrap both operations in an explicit transaction.
**Fix:**
```python
with closing(sqlite3.connect(db_path)) as conn:
    with conn:  # explicit transaction — rolls back both DELETE and inserts on error
        if _table_exists(conn, table):
            conn.execute(
                f"DELETE FROM {table} WHERE match_id = ?",
                (str(match_id),),
            )
        df.to_sql(table, conn, if_exists="append", index=False)
        # conn.__exit__ commits; no explicit conn.commit() needed
```

---

### CR-03: Silent dedup bypass on CSV read error in `save_attempts`

**File:** `kill_rate_analysis.py:103-104`
**Issue:** If `pd.read_csv` raises any exception, the bare `except Exception` falls through to `combined = rows` — discarding the existing CSV content entirely and writing only the new rows. This means a corrupted or locked CSV silently drops all previously saved attempts instead of raising an error. The old data is then permanently overwritten.
**Fix:**
```python
except Exception as e:
    print(f"  [WARNING] Could not read existing {path}: {e}. Aborting save to prevent data loss.")
    return  # do not overwrite a file we can't read
```

---

## Warnings

### WR-01: NaN velocity always evaluates to `False` in `_classify_engagement` — wrong classification

**File:** `ddm_analyzer.py:577`
**Issue:** `_classify_engagement` checks `not math.isnan(velocity_ups) and velocity_ups >= threshold`. This is correct. However `_compute_velocity` returns `np.nan` (not `float('nan')`), and `math.isnan(np.nan)` works fine — so the classification is correct. **But** `DuelAttemptFinder._player_velocity` (duel_attempts.py:288) returns `0.0` when data is missing instead of `np.nan`. Zero velocity is then classified as "hold" rather than "unknown/missing". An engagement with no velocity data is silently labeled "hold", inflating hold counts.
**Fix:**
```python
# duel_attempts.py:288 — return nan instead of 0.0 for missing data
if at_t.empty or after_t.empty:
    return float("nan")
```
And in `_process_cluster` line 192:
```python
import math
engagement = "peek" if not math.isnan(player_velocity) and player_velocity >= self.velocity_peek_threshold else "hold"
```

---

### WR-02: `rt_t1_t2` fallback uses T0 instead of T1 — inflated metric

**File:** `ddm_analyzer.py:671-673`
**Issue:** When `t1_tick == -1` (no T1 found), the `elif` branch computes `rt_t1_t2 = (t2_tick - t0_tick) * ms`. This assigns the full T0→T2 window to `rt_aim_to_hit_ms` — a value that is physically meaningless and will inflate the "Aim→Hit" metric. Downstream aggregations in `print_comparison_table` and visualize charts will include this inflated value.
```python
rt_t1_t2 = np.nan
if t1_tick != -1 and t2_tick >= t1_tick:
    rt_t1_t2 = (t2_tick - t1_tick) * ms
elif t2_tick >= t0_tick:          # ← this sets rt_t1_t2 = full T0→T2, wrong
    rt_t1_t2 = (t2_tick - t0_tick) * ms
```
**Fix:** Remove the `elif` branch entirely. When T1 is unknown, `rt_aim_to_hit_ms` should be `np.nan` — there is no T1 reference point.
```python
rt_t1_t2 = np.nan
if t1_tick != -1 and t2_tick >= t1_tick:
    rt_t1_t2 = (t2_tick - t1_tick) * ms
```

---

### WR-03: Unguarded `int(target_enemy_id)` cast crashes on non-numeric steamids

**File:** `ddm_analyzer.py:630`
**Issue:** `_compute_crosshair_angle_at_t0(t0_tick, int(target_enemy_id), all_ticks_df)` — `target_enemy_id` comes from `first_hit["user_steamid"]` which may be `"nan"`, `""`, or `"None"` if demoparser2 returns a null. The `int()` cast will raise `ValueError` and crash the entire episode analysis rather than just returning `None` for the angle.
**Fix:**
```python
try:
    enemy_sid_int = int(target_enemy_id)
except (ValueError, TypeError):
    enemy_sid_int = None
crosshair_angle = (
    self._compute_crosshair_angle_at_t0(t0_tick, enemy_sid_int, all_ticks_df)
    if enemy_sid_int is not None else None
)
```

---

### WR-04: `_check_kill` does not guard missing `user_steamid` column

**File:** `duel_attempts.py:222-228`
**Issue:** `_check_kill` guards `attacker_steamid` but not `user_steamid`. If `all_death_df` lacks `user_steamid` (e.g., demoparser2 returns deaths without victim info), line 227 will raise `KeyError`. The method has no `try/except` and the exception propagates through `_process_cluster` uncaught, silently dropping the entire cluster via the `except`-less call stack.
**Fix:**
```python
if "attacker_steamid" not in all_death_df.columns or "user_steamid" not in all_death_df.columns:
    return False
```

---

### WR-05: `parse_smoke_events` uses tickrate 64 hardcoded instead of instance tickrate

**File:** `t0_detector.py:362`
**Issue:** `end_tick = int(d_row.tick) + _SMOKE_FALLBACK_DURATION_S * 64` — the `64` is a hardcoded tickrate. The rest of the codebase passes `tickrate` as a parameter. If a 128-tick demo is ever processed, smoke durations will be halved (smokes expire at tick 18s/128 = wrong duration), causing T0 to be found through smokes that should be blocking it.
**Fix:**
```python
# parse_smoke_events cannot receive tickrate as a static method without signature change.
# Either add tickrate parameter or use a module-level constant that respects config.
@staticmethod
def parse_smoke_events(parser, tickrate: int = 64) -> pd.DataFrame:
    ...
    end_tick = int(d_row.tick) + _SMOKE_FALLBACK_DURATION_S * tickrate
```
All callers must pass `tickrate`.

---

### WR-06: `run_analysis.py` calls `db_utils.save_to_db` twice for the same data

**File:** `run_analysis.py:64` and `ddm_analyzer.py:879`
**Issue:** `analyze_demo()` already calls `db_utils.save_to_db(results_df, DB_PATH, "engagements", self.match_id)` internally (ddm_analyzer.py:879). `run_analysis.py:64` then calls `db_utils.save_to_db(results_df, DB_PATH, "engagements", match_id)` again. On each run, the second call DELETEs what the first call just wrote and re-inserts the same rows — wasting a write cycle and risking data loss if the process is killed between the two calls.
**Fix:** Remove the `db_utils.save_to_db` call from `run_analysis.py:64` since `analyze_demo` already handles it.

---

## Info

### IN-01: `config.py` — import order: module-level code before imports

**File:** `config.py:9`
**Issue:** `DB_PATH: str = "analytics.db"` appears at line 9, before the `import` statements at line 11. This is non-standard and violates PEP 8 import ordering (imports at top). While Python allows it, it's a maintenance hazard — any reader expects all names at module scope to be defined after imports.
**Fix:** Move `DB_PATH` to after the import block.

---

### IN-02: `kill_rate_analysis.py` — hardcoded absolute demo path as module-level constant

**File:** `kill_rate_analysis.py:41`
**Issue:** `_DEMO_BASE = r"D:\Steam\steamapps\..."` is a hardcoded machine-specific path at module scope. Any other developer or CI system will silently skip all demos (the `os.path.exists` guard prevents a crash but hides the misconfiguration). Same pattern in `run_analysis.py:20`.
**Fix:** Read from an environment variable with a clear fallback error, or accept demos as CLI arguments.

---

### IN-03: `app.py` — SteamID validation allows any integer, including negative or zero

**File:** `app.py:217`
**Issue:** `int(sid_str)` will succeed for `"0"`, `"-1"`, or any non-SteamID integer. A valid SteamID64 is always ≥ 76561193990340609. No minimum-value check means a typo will pass validation and produce an empty analysis without a clear error.
**Fix:**
```python
player_steamid = int(sid_str)
if player_steamid < 76_561_193_990_340_609:
    st.error("SteamID64 too small — must be a valid 17-digit Steam ID.")
    st.stop()
```

---

### IN-04: `visualize_results.py` — deprecated `get_xticklabels` pattern causes Matplotlib warning

**File:** `visualize_results.py:178, 185`
**Issue:** `ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right")` on axes that haven't been rendered yet returns empty tick label objects in recent Matplotlib versions (3.7+), causing a `UserWarning: FixedLocator` and potentially blank x-axis labels. Project uses matplotlib 3.10.8.
**Fix:**
```python
ax.tick_params(axis="x", rotation=45)
# or use plt.setp(ax.get_xticklabels(), rotation=45, ha="right") after fig.draw()
```

---

_Reviewed: 2026-05-01_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
