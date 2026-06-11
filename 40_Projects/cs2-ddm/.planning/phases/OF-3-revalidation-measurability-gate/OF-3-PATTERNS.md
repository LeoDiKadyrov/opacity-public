# Phase OF-3: Re-validation + Metric + Measurability Gate - Pattern Map

**Mapped:** 2026-06-10
**Files analyzed:** 8 (new) + 3 (modified)
**Analogs found:** 8 / 8

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-|-|-|-|-|
| `reaction_timing.py` | service/utility (per-episode transform) | transform | `outcome_first.py` (`group_episodes`/`reconstruct_all_players`) + `t0_detector.find_t0` + `ddm_analyzer.get_desired_angles`/`angular_diff` | role-match (new module, reuses primitives) |
| `tests/test_distribution_shape.py` (Tier 1 synthetic) | test | transform | `tests/test_outcome_first.py` (synthetic DataFrame fixtures, episode assertions) | role-match |
| `tests/test_distribution_shape.py` (Tier 2 `@requires_db`) | test | batch / DB-read | `tests/test_outcome_first.py::test_db_write_duel_episodes` (sqlite round-trip) | role-match |
| `tests/test_db_utils.py` (new migration test) | test | CRUD (schema) | existing `tests/test_db_utils.py` (idempotent ALTER TABLE pattern, t1_source precedent) | exact |
| `db_utils.py` `_migrate_schema` | migration | CRUD (schema) | `db_utils.py` lines 129-146 (`duel_episodes` CREATE TABLE) + lines 84-107 (`_eng_migrations` ALTER pattern) | exact |
| `config.py` new constants | config | — | `config.py` lines 95-161 (named constants w/ rationale comments, T1 detection block) | exact |
| `of3_rebatch.py` | utility (driver) | batch | `monesy_rebatch.py` (2-phase staged driver, skip-existing, roster extraction) | exact |
| `generate_of3_inspection.py` | utility (report generator) | file-I/O / batch | `generate_top10_inspection.py` (sqlite read, markdown sections, pct/fmt helpers) | exact |
| `of3_gate.py` | utility (statistical script) | batch / transform | `monesy_rebatch.py` (CLI `--gate=` arg pattern) + new Fisher-z formula (no analog, see RESEARCH Code Examples) | role-match (no direct analog for stats) |
| `pytest.ini` | config | — | existing `markers =` section (add `requires_db`) | exact |
| `outcome_first.py` `reconstruct_all_players` | service (modified) | transform | itself, lines 292-338 (per-episode loop, save_to_db call site) | exact |

## Pattern Assignments

### `reaction_timing.py` (new module — service/transform)

**Analog 1:** `t0_detector.py` lines 88-115 (`find_t0` signature/contract)

**find_t0 signature to call** (verified, do not modify `t0_detector.py`):
```python
# Source: t0_detector.py:88-98
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
Call with `search_start_tick = first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS`, `search_end_tick = first_event_tick`. Then do the SECOND backward-continuity pass per Pattern 1 (D-05) — no existing analog for this second pass, must be new code; do not skip it (Pitfall 3).

**Analog 2:** `ddm_analyzer.py` lines 105-122 (`get_desired_angles`, `angular_diff` — static methods, import and call, do NOT duplicate)

```python
# Source: ddm_analyzer.py:105-122
@staticmethod
def get_desired_angles(
    px: float, py: float, pz: float,
    ex: float, ey: float, ez: float,
) -> Tuple[float, float]:
    dx, dy, dz = ex - px, ey - py, ez - pz
    yaw = math.degrees(math.atan2(dy, dx))
    h_dist = math.sqrt(dx * dx + dy * dy)
    if h_dist == 0:
        pitch = -90.0 if dz > 0 else (90.0 if dz < 0 else 0.0)
    else:
        pitch = math.degrees(math.atan2(-dz, h_dist))
    return pitch, yaw

@staticmethod
def angular_diff(a1: float, a2: float) -> float:
    """Signed angular difference in [-180, 180]."""
    return (a2 - a1 + 180) % 360 - 180
```
Import via `from ddm_analyzer import DDMAnalyzer` (or refactor to module-level functions if planner prefers — check existing import style first). Combine into `angular_dist = hypot(angular_diff(yaw_actual, yaw_desired), angular_diff(pitch_actual, pitch_desired))`.

**Analog 3:** `outcome_first.py` lines 52-61 (`_coerce_sid` — import, do not redefine)

```python
# Source: outcome_first.py:52-61
def _coerce_sid(series: pd.Series) -> pd.Series:
    """SteamID64 -> int64 WITHOUT a float64 intermediate.
    ...
    """
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")
```
`reaction_timing.py` and `of3_gate.py` must `from outcome_first import _coerce_sid` for any sid handling (Ops constraint, OF-2-CONTEXT).

**Imports pattern** (model on `outcome_first.py` lines 1-43):
```python
from __future__ import annotations

import logging
import math
from typing import Dict, List, Optional, Tuple

import pandas as pd

from config import (
    TARGET_REACHED_THRESHOLD,
    T0_BACKWARD_SEARCH_CAP_TICKS,
    T1_SUSTAINED_AIM_TICKS,
)

logger = logging.getLogger(__name__)
```

**Core transform pattern** — model the per-episode dict-return shape on `outcome_first.group_episodes` (lines 185+, returns list of dicts with mixed-case keys later renamed before DB write — see `reconstruct_all_players` lines 324-330). `reaction_timing.compute_timing(episode_dict, ticks_df, t0_detector, ticks_by_sid=...) -> dict` should return a dict with keys matching the NEW `duel_episodes` columns directly (`t0_tick`, `t0_source`, `t1_tick`, `t1_source`, `crosshair_angle_at_t0_deg`, `rt_visible_to_land_ms`, `rt_visible_to_hit_ms`) — no rename step needed if keys are already snake_case lower (unlike `n_hits_P_on_E`).

**Error handling pattern** — model on `reconstruct_all_players` lines 333-337:
```python
# Source: outcome_first.py:333-337
except Exception:
    logger.exception(
        "Failed to reconstruct episodes for %s in %s", sid, demo_name
    )
    results[sid] = 0
```
`compute_timing` should never raise from the per-episode loop — wrap in try/except, log + return all-NULL timing dict with appropriate `*_source` (e.g. `"error"` — define if needed) so the row still gets written (label-not-drop, D-03/D-06/D-08).

---

### `tests/test_distribution_shape.py` (new — two-tier test file)

**Analog (Tier 1 synthetic):** `tests/test_outcome_first.py` lines 86-148

**Imports + fixture-construction pattern**:
```python
# Source: tests/test_outcome_first.py:1-25 (imports) + 88-99 (synthetic DataFrame fixtures)
import sqlite3

import pandas as pd
import pytest

from outcome_first import (
    collect_exchanges,
    group_episodes,
    # ... add reaction_timing imports
)

P, E1, E2 = <steamids as in test_outcome_first.py top constants>

def test_group_episodes_outcome_won_lost_unresolved():
    hurt = pd.DataFrame({
        "tick": [1000, 1050, 2000, 5000, 6000],
        "attacker_steamid": [str(P), str(E1), str(E2), str(P), None],
        "user_steamid": [str(E1), str(P), str(P), str(E1), str(P)],
        "weapon": ["ak47", "ak47", "ak47", "ak47", "world"],
    })
    ...
    assert outcomes == ["won", "lost", "unresolved"]
```
For T1 synthetic fixtures, build minimal tick-DataFrames with `tick`, `X`, `Y`, `Z`, `pitch`, `yaw` columns for player + enemy, covering: flick-30deg-at-T0 (assert T1 != T0+1), pre-aimed-at-T0 (assert T1==T0), never-lands (assert `t1_source=="never_landed"`, T1 NULL), never-visible (assert `t0_source=="never_visible"`), long-visible (assert `t0_source=="long_visible"`).

**Analog (Tier 2 `@requires_db`):** `tests/test_outcome_first.py` lines 167-185 (`test_db_write_duel_episodes`)

```python
# Source: tests/test_outcome_first.py:167-185
def test_db_write_duel_episodes(tmp_path):
    """R-6: duel_episodes rows survive round-trip through SQLite."""
    from db_utils import init_db, save_to_db

    db = str(tmp_path / "test.db")
    init_db(db)
    df = pd.DataFrame([{...}])
    save_to_db(df, db, "duel_episodes", 1)
    rows = sqlite3.connect(db).execute(
        "SELECT player_steamid, opponent_steamid, outcome FROM duel_episodes"
    ).fetchall()
```
Tier 2 tests connect to `analytics.db` (real `DB_PATH`, not `tmp_path`) and run aggregate SQL (pinning %, MIN, physics-bounded check). Mark with `@pytest.mark.requires_db`; skip gracefully if DB missing or `duel_episodes` has 0 rows with non-NULL `t1_tick`.

**pytest.ini edit** (exact location):
```ini
# Source: pytest.ini (current, full file read)
markers =
    slow: marks tests as slow (deselect with '-m "not slow"')
    integration: marks tests as integration tests (cwd-sensitive, skip in CI)
    requires_db: marks tests requiring analytics.db with post-rebatch duel_episodes data
```

---

### `db_utils.py` `_migrate_schema` (modified — schema migration)

**Analog:** `db_utils.py` lines 84-107 (`_eng_migrations` list + ALTER loop) — exact precedent including the `t1_source` Phase 10 comment style.

```python
# Source: db_utils.py:84-107 (pattern to replicate for duel_episodes)
cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
_eng_migrations = [
    ("demo_name", "TEXT DEFAULT NULL"),
    ...
    # Phase 10 (2026-05-16, REVIEW-2026-05-16.md B-4): T1 detection branch.
    # Values in {"sustained_aim", "pre_aimed", "none"} for new rows.
    # NULL on legacy (pre-Phase-10) rows...
    ("t1_source", "TEXT DEFAULT NULL"),
]
for col, col_def in _eng_migrations:
    if col not in cols:
        conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
```

**Apply identically to `duel_episodes`** (CREATE TABLE at lines 131-146). Insert AFTER the existing CREATE TABLE block, BEFORE the `processed_matches` block (line 148):

```python
# NEW — Source: db_utils.py:131-146 (duel_episodes CREATE TABLE, for column-set baseline)
# and OF-3-RESEARCH.md Code Examples section (verified ALTER pattern)
ep_cols = {c[1] for c in conn.execute("PRAGMA table_info(duel_episodes)").fetchall()}
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
    if col not in ep_cols:
        conn.execute(f"ALTER TABLE duel_episodes ADD COLUMN {col} {col_def}")
```

**Test analog:** existing `tests/test_db_utils.py` already has migration-idempotency tests for `engagements`/`t1_source` — find that test, copy structure for `duel_episodes` timing columns (call `init_db` twice on same `tmp_path` db, assert no error + columns present both times).

---

### `config.py` new constants (modified — config)

**Analog:** `config.py` lines 104-162 (T0/T1 constant block — exact style: named constant + multi-line rationale comment referencing phase/bug history)

```python
# Source: config.py:108-121 (rationale-comment style to replicate)
# Minimum ticks between BVH-found T0 and search_start.
# If T0 == search_start the enemy was already visible before the lookback window
# started -- the true T0 is unknown and T0->T2 will be inflated.
# 20 ticks ~= 312ms. Engagements failing this gate are not gradeable.
T0_MIN_OFFSET_TICKS: int = 20
```

```python
# Source: config.py:148-158 (T1 constant block style)
T1_GRACE_MS: int = 0
T1_SUSTAINED_AIM_TICKS: int = 2
T1_MIN_ANGLE_CHANGE: float = 0.08
T1_NOT_AIMED_THRESHOLD: float = 1.0
T1_MOVING_TOWARDS_TOLERANCE: float = 0.01
```

**New constants to add (same block style, append after line ~161)**:
- `TARGET_REACHED_THRESHOLD: float = 3.0` — with rationale comment citing quantization rule (3.0/0.022 ~= 136x, project rule >=3x) and D-02 A/B procedure result.
- `T0_BACKWARD_SEARCH_CAP_TICKS: int = 640` — rationale: cost-cap for D-05 backward search, NOT a clamp (label `long_visible` on cap-hit, per anti-pattern note).
- `_T0_SEARCH_PARSE_WINDOW_TICKS` (or equivalent, must be >= `T0_BACKWARD_SEARCH_CAP_TICKS`) — rationale: Pitfall 2, existing `_SELECTIVE_WINDOW_BEFORE_TICKS=384` (line 131) is too small.

Do NOT import `T0_MIN_OFFSET_TICKS` / `T0_TO_T2_MAX_TICKS` into `reaction_timing.py` (State of the Art section — these belong to the deprecated engagement-window framing).

---

### `of3_rebatch.py` (new — staged rebatch driver)

**Analog:** `monesy_rebatch.py` (full file, 2-phase pattern)

```python
# Source: monesy_rebatch.py:13-21 (imports)
from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
```

**Roster/skip-existing pattern** (lines 36-114):
```python
# Source: monesy_rebatch.py:36-114 (function names — read full bodies at plan time)
def extract_roster(demo_path: str) -> list[int]: ...
def log(msg: str) -> None: ...
def report_append(line: str) -> None: ...
def delete_monesy_rows(demo_name: str) -> int: ...   # analog for "force_reprocess_demo" delete-then-reinsert
def monesy_done(demo_name: str, ...) -> tuple[bool, int, int]: ...  # skip-existing check
def all_done(demo_name: str, min_players: int = 8) -> bool: ...
```
For OF-3, adapt `monesy_done`/`all_done` to check `duel_episodes.t0_tick IS NOT NULL OR t0_source IS NOT NULL` (timing already computed) per demo, for skip-existing across N=1/5/81 stages. Use `--stage={1|5|81}` CLI flag analogous to `--phase={a|b}`.

**Subprocess UTF-8 env** (memory-verified pattern, apply at driver top):
```python
_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
# pass env=_UTF8_ENV to every subprocess.run/Popen call
```

---

### `generate_of3_inspection.py` (new — inspection artifact generator)

**Analog:** `generate_top10_inspection.py` (full file)

```python
# Source: generate_top10_inspection.py:13-17 (imports)
from __future__ import annotations

import sqlite3
import statistics
from pathlib import Path
```

**Helper functions to replicate** (lines 38-52):
```python
# Source: generate_top10_inspection.py:38-52
def pct(p: float, vals: list[float]) -> float: ...
def fmt_num(v) -> str: ...
def main(): ...
```
Follow the `of2_parity_inspection.md` 7-section format (aggregate / per-unit / per-actor / full-list-of-changed-rows / anomaly buckets / random sample / pre-vs-post + acceptance checklist), per Don't-Hand-Roll table. **Critical addition per D-14/B-5 post-mortem**: every table MUST include `crosshair_angle_at_t0_deg` (or another physics-bounded column) — this is the lesson from `feedback_inspection_without_physics_sanity_columns_misses_bugs_2026_05_19`. Query `duel_episodes` exclusively (Pitfall 5 — new script, do not extend `generate_top10_inspection.py` which implicitly assumes `engagements`).

---

### `of3_gate.py` (new — Gate-A/Gate-B statistical script)

**No direct analog** for the statistics; CLI scaffolding analog is `monesy_rebatch.py` (`argparse` with `--gate={A|B}` mirroring `--phase={a|b}`).

**Split-half reliability formula** (from RESEARCH.md Code Examples — no codebase analog, standard formula):
```python
# Source: OF-3-RESEARCH.md "Split-half reliability with Fisher z-transform CI95"
import math

def split_half_reliability(half_a: pd.Series, half_b: pd.Series) -> dict:
    n = len(half_a)
    r = half_a.corr(half_b, method="pearson")
    r_full = (2 * r) / (1 + r)
    z = 0.5 * math.log((1 + r) / (1 - r))
    se = 1 / math.sqrt(n - 3)
    ci_lo = math.tanh(z - 1.96 * se)
    ci_hi = math.tanh(z + 1.96 * se)
    r_full_ci = ((2 * ci_lo) / (1 + ci_lo), (2 * ci_hi) / (1 + ci_hi))
    return {"n": n, "r_half": r, "r_full_spearman_brown": r_full, "ci95_full": r_full_ci}
```
Gate-A SQL slices model on `outcome_first_spike.py` slice logic (OF-1 precedent — locate at plan time via Glob if not already read). Output: `VERDICT.md` (model markdown structure on `OF-2-PARITY.md` / `OF-1-VERDICT.md`).

---

### `outcome_first.py` `reconstruct_all_players` (modified — integration point)

**Analog:** itself, lines 292-338 (per-player loop, `save_to_db` call)

```python
# Source: outcome_first.py:310-332 (insertion point: after group_episodes, before save_to_db)
for sid in player_sids:
    try:
        events = collect_exchanges(hurt_df, death_df, sid)
        eps = group_episodes(events, fires_df, sid, demo=demo_name, match_id=str(match_ids_by_sid[sid]))
        if eps:
            df = pd.DataFrame(eps)
            df["player_steamid"] = sid
            df = df.rename(columns={...})
            if "opponent" in df.columns:
                df = df.drop(columns=["opponent"])
            # NEW: timing pass slots HERE, per-row, before save_to_db
            # for i, row in df.iterrows():
            #     timing = reaction_timing.compute_timing(row.to_dict(), ticks_df, t0_detector, ticks_by_sid=...)
            #     df.loc[i, timing.keys()] = timing.values()
            save_to_db(df, db_path, "duel_episodes", match_ids_by_sid[sid])
        results[sid] = len(eps)
    except Exception:
        logger.exception("Failed to reconstruct episodes for %s in %s", sid, demo_name)
        results[sid] = 0
```
Selective `parse_ticks` window must be sized to `_T0_SEARCH_PARSE_WINDOW_TICKS` (Pitfall 2) — check current `_parse_demo_events` (lines 244-262) for the existing `parse_ticks(ticks=...)` call site and extend the window union.

## Shared Patterns

### SteamID coercion
**Source:** `outcome_first.py:52-61` (`_coerce_sid`)
**Apply to:** `reaction_timing.py`, `of3_gate.py` — any sid column handling. Never `pd.to_numeric`/`pd.read_sql` on sid columns.

### Idempotent schema migration
**Source:** `db_utils.py:84-107` (`_eng_migrations` ALTER TABLE loop)
**Apply to:** `db_utils._migrate_schema` for new `duel_episodes` timing columns — same `PRAGMA table_info` + conditional `ALTER TABLE ADD COLUMN` loop, same Phase-10-style rationale comments.

### Named constants with rationale comments
**Source:** `config.py:104-162`
**Apply to:** `TARGET_REACHED_THRESHOLD`, `T0_BACKWARD_SEARCH_CAP_TICKS`, `_T0_SEARCH_PARSE_WINDOW_TICKS` — multi-line comment citing the quantization rule / D-05 anti-clamp rationale / Pitfall 2.

### Label-not-drop / never-raise per-row error handling
**Source:** `outcome_first.py:333-337` (`reconstruct_all_players` per-sid try/except + `logger.exception`)
**Apply to:** `reaction_timing.compute_timing` per-episode — never raise; on failure return all-NULL timing dict with diagnostic source label, row stays in DB.

### Subprocess UTF-8 env
**Source:** memory `feedback_subprocess_utf8_env_for_windows_cp1252_2026_05_16` (no single file analog — pattern convention)
**Apply to:** `of3_rebatch.py` — define `_UTF8_ENV` dict at driver top, pass to all subprocess calls.

## No Analog Found

| File | Role | Data Flow | Reason |
|-|-|-|-|
| `of3_gate.py` (statistics core) | utility | batch | No prior split-half/Fisher-z reliability code in repo; formula sourced from RESEARCH.md Code Examples (standard closed-form, not project-specific) |
| Second-pass backward-continuity scan (D-05 step 3) inside `reaction_timing.py` | transform (sub-routine) | transform | `find_t0` only does forward-scan-for-first-visible; the "extend backward to run start" logic is genuinely new — no codebase precedent, must be written fresh per Pattern 1/Pitfall 3 |

## Metadata

**Analog search scope:** repo root (`*.py`), `tests/`, `.planning/phases/OF-2-core-rebuild/`, `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/`
**Files scanned:** `outcome_first.py`, `t0_detector.py`, `ddm_analyzer.py`, `db_utils.py`, `config.py`, `monesy_rebatch.py`, `generate_top10_inspection.py`, `tests/test_outcome_first.py`, `pytest.ini`
**Pattern extraction date:** 2026-06-10
