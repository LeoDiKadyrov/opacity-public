# Phase 8: Interpretation Layer — Pattern Map

**Mapped:** 2026-05-06
**Files analyzed:** 4 (2 new, 2 modified)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `interpretation.py` | service | CRUD (read-only SQLite + transform) | `db_utils.py` + `kill_rate_analysis.py` | role-match |
| `config.py` | config | — | `config.py` itself (edit) | exact |
| `app.py` | component (Streamlit section) | request-response | `app.py` Batch Analysis section (lines 437–617) | exact |
| `tests/test_interpretation.py` | test | — | `tests/test_db_utils.py` + `tests/test_kill_rate_analysis.py` | exact |

---

## Pattern Assignments

### `interpretation.py` (service, read-only CRUD + transform)

**Primary analog:** `db_utils.py`
**Secondary analog:** `kill_rate_analysis.py` (PLAYERS dict pattern → METRIC_CONFIG dict)

**Imports pattern** (`db_utils.py` lines 1–10):
```python
import sqlite3
from contextlib import closing
from typing import Union

import pandas as pd
```
For `interpretation.py`, extend to:
```python
import sqlite3
from contextlib import closing
from typing import Optional

import numpy as np
import pandas as pd

from config import DB_PATH, PLAYER_NAMES
```

**SQLite read pattern** (`db_utils.py` lines 35–44):
```python
with closing(sqlite3.connect(db_path)) as conn:
    with conn:
        ...
        df.to_sql(table, conn, if_exists="append", index=False)
```
For read-only queries in `interpretation.py`, use the same `closing()` wrapper but with `pd.read_sql()`:
```python
with closing(sqlite3.connect(db_path)) as conn:
    eng_df = pd.read_sql(
        "SELECT ... FROM engagements WHERE player_steamid = ? AND engagement_type = ?",
        conn, params=(int(player_steamid), engagement_type)
    )
```

**Security pattern — parameterized queries** (`db_utils.py` lines 14–16, 42–44):
```python
# CR-01: whitelist allowed table names to prevent SQL injection via f-string interpolation
_ALLOWED_TABLES = {"engagements", "duel_attempts"}
...
conn.execute(
    f"DELETE FROM {table} WHERE match_id = ?",
    (str(match_id),),
)
```
In `interpretation.py`, all SQL uses `?` placeholders only. No f-string SQL. SteamID is always cast to `int()` before passing as param (Pitfall 1 from RESEARCH.md).

**Error handling pattern** (`db_utils.py` lines 46–47):
```python
except (sqlite3.DatabaseError, OSError, ValueError) as e:
    print(f"Warning: could not write to '{db_path}' table '{table}': {e}")
```
`interpretation.py` functions return empty DataFrame / empty list on DB error rather than raising — callers check `.empty` before rendering.

**Dict-keyed configuration pattern** (`kill_rate_analysis.py` lines 43–60):
```python
PLAYERS: dict[str, tuple[int, list[str]]] = {
    "donk": (76561198386265483, [...]),
    # Add other players here when demo files and steamids are available:
    # "shoke": (76561198XXXXXXXXX, [rf"..."]),
}
```
`interpretation.py` follows the same "single source of truth dict" pattern for:
- `METRIC_CONFIG: dict[str, tuple]` — `(db_column, lower_is_better, display_name, source_table)`
- `DRILLS: dict[tuple, str]` — keyed by `(metric_name, tier, engagement_type)`
- `RT_BOTTLENECK_DRILLS: dict[tuple, str]` — keyed by `(metric, tier, engagement_type, component)`
- `TIER_ORDER: dict[str, int]` — `{"Elite": 0, "Good": 1, "Average": 2, "Work needed": 3}`

**NaN guard pattern** (established project-wide, referenced in RESEARCH.md Pitfall 3):
```python
# Always dropna() before quantile() call
series = df["rt_visible_to_aim_ms"].dropna()
if series.empty:
    return fallback_value
p25, p50, p75 = series.quantile([0.25, 0.50, 0.75])
```

**Module docstring pattern** (`db_utils.py` lines 1–6):
```python
"""
SQLite persistence helpers for the DDM reaction analysis pipeline.

Strategy: replace-or-append per match_id (idempotent re-runs), mirroring
the csv_utils.save_results() pattern.
"""
```
`interpretation.py` follows same: module-level docstring explaining role + caller.

---

### `config.py` (config, edit only)

**Analog:** `config.py` itself — existing constant block pattern.

**Named constant pattern** (`config.py` lines 13–50):
```python
DB_PATH: str = "analytics.db"

VELOCITY_PEEK_THRESHOLD_UPS: float = 50.0
ENEMY_VELOCITY_HOLD_THRESHOLD_UPS: float = 120.0

KNIFE_WEAPON_NAMES: frozenset = frozenset([...])
```
Add `PLAYER_NAMES` in the same style — typed dict, inline comment explaining role:
```python
# Mapping from SteamID64 → display name for the Interpretation tab benchmark dropdown.
# Add entries here when new benchmark players are added to analytics.db.
PLAYER_NAMES: dict[int, str] = {
    76561197989430253: "karrigan",
    76561198386265483: "donk",
}
```
Place after `DB_PATH` (line 13) in the "Persistence paths" section — it is a display-layer config close to DB_PATH in purpose.

**Section header pattern** (`config.py` lines 5–7):
```python
# ─────────────────────────────────────────────────────────────────────────────
# Persistence paths
# ─────────────────────────────────────────────────────────────────────────────
```
No new section needed — `PLAYER_NAMES` belongs under the existing "Persistence paths" header.

---

### `app.py` — Interpretation section (component, request-response)

**Analog:** `app.py` Batch Analysis section (lines 437–617) — closest structural match: a new `st.header()` section with sidebar SteamID reuse, selectbox, and conditional rendering.

**Section header + caption pattern** (`app.py` lines 437–441):
```python
st.header("Batch Analysis")
st.caption(
    "Process all .dem files in a `for_analysis/` subfolder in parallel. "
    "Uses the Player SteamID64 from Configuration above."
)
```
Interpretation section:
```python
st.header("Interpretation")
st.caption(
    "Compares your metrics against a benchmark player's distribution. "
    "Run analysis first to populate your data."
)
```

**SteamID reuse + int-cast + ValueError guard pattern** (`app.py` lines 479–488):
```python
_batch_sid_str = st.session_state.get("steamid_input", "").strip()
batch_steamid_valid = False
batch_player_steamid = 0
if _batch_sid_str:
    try:
        batch_player_steamid = int(_batch_sid_str)
        batch_steamid_valid = True
        st.info(f"Using SteamID64 from Configuration: `{batch_player_steamid}`")
    except ValueError:
        st.error("SteamID64 in Configuration is invalid — enter a plain 17-digit number there.")
else:
    st.warning("Enter Player SteamID64 in the Configuration panel (sidebar) first.")
```
Interpretation section follows the same pattern verbatim for `_interp_player_sid`.

**selectbox pattern** (`app.py` lines 452–457):
```python
selected_folder = st.selectbox(
    "Demo folder",
    options=_folder_options,
    index=0,
    help="Select a subfolder to process.",
)
```
Benchmark dropdown follows same signature — `options=_benchmark_labels`, `index=_default_idx`.

**Conditional section render pattern** (`app.py` lines 470–476):
```python
if dem_files:
    st.success(f"{len(dem_files)} demo(s) in `{_scan_dir.name}/`")
    ...
else:
    st.info(f"No .dem files in `{_scan_dir}` — drop files there and refresh.")
```
Interpretation section uses same guard: `if player_rows_empty: st.info("No data...") else: render table`.

**st.tabs() within a section** — no existing analog in app.py (app uses flat `st.header()` only). The Interpretation section introduces `st.tabs(["Peek", "Hold"])` for engagement-type split per D-06. This is a new pattern — no analog to copy from. Use standard Streamlit `st.tabs()` API.

**Imports to add** (follow `app.py` lines 18–22 import block style):
```python
from interpretation import get_benchmark_options, compute_interpretation
from config import PLAYER_NAMES  # already imported via config line 21 — extend existing import
```
Add `PLAYER_NAMES` to the existing `from config import ...` line (line 21).

**st.dataframe with Styler pattern** (`app.py` lines 255–268 — Results section, inferred from grep):
Use `st.dataframe(df.style.map(_color_tier, subset=["Tier"]))` for tier color coding — consistent with existing Results table styling in app.py.

---

### `tests/test_interpretation.py` (test)

**Primary analog:** `tests/test_db_utils.py` — closest match: SQLite-layer unit tests with `tmp_path`, `monkeypatch`, and direct DB setup.

**File header pattern** (`tests/test_db_utils.py` lines 1–9):
```python
"""
Tests for db_utils.py — SQLite persistence layer (Plan 06-03).
"""
import sqlite3
from contextlib import closing
import pandas as pd
import pytest

import db_utils
```
`test_interpretation.py` follows same:
```python
"""
Tests for interpretation.py — percentile tier computation + drill lookup (Plan 08-XX).
"""
import sqlite3
from contextlib import closing
import pandas as pd
import pytest

import interpretation
from config import PLAYER_NAMES
```

**tmp_path fixture + DB setup pattern** (`tests/test_db_utils.py` lines 25–28):
```python
def test_table_exists_returns_false_for_missing_table(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        assert db_utils._table_exists(conn, "engagements") is False
```
`test_interpretation.py` uses `tmp_path` to create an isolated analytics.db with injected fixture data per test:
```python
def _make_db(tmp_path, rows_engagements=None, rows_attempts=None) -> str:
    db = str(tmp_path / "test.db")
    import db_utils
    db_utils.init_db(db)
    # insert fixture rows via pd.DataFrame.to_sql(...)
    return db
```

**Helper fixture function pattern** (`tests/test_kill_rate_analysis.py` lines 25–38):
```python
def _attempt(match_id: str, enemy_steamid: int = 999) -> DuelAttempt:
    return DuelAttempt(
        match_id=match_id,
        map_name="de_dust2",
        t0_tick=1000,
        ...
        player_steamid=76561198386265483,
    )
```
`test_interpretation.py` uses an analogous `_engagement_row()` and `_attempt_row()` helper that returns a minimal dict for DataFrame construction — keeps test data concise.

**Test class grouping pattern** (`tests/test_kill_rate_analysis.py` lines 43–44):
```python
class TestSaveAttempts:
    """Tests for save_attempts() idempotency and accumulation (D-06)."""
```
`test_interpretation.py` groups by function under test:
- `class TestAssignTier` — pure unit, no DB
- `class TestComputeInterpretation` — DB-backed, uses tmp_path
- `class TestGetBenchmarkOptions` — DB-backed
- `class TestRtBottleneckComponent` — pure unit

**monkeypatch + mock pattern** (`tests/test_kill_rate_analysis.py` lines 46–50):
```python
@pytest.fixture(autouse=True)
def tmp_dir(self, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    self.tmp_path = tmp_path
```
`test_interpretation.py` does NOT use `monkeypatch.chdir` (no CWD dependency) — passes `db_path` explicitly to all functions under test.

**assert pattern** (`tests/test_db_utils.py` lines 46–47):
```python
assert len(result) == 2
assert set(result.columns) >= {"match_id", "player_steamid", "rt_visible_to_hit_ms"}
```
Same style for schema validation tests in `test_interpretation.py`:
```python
assert len(rows) == 5
assert all(k in rows[0] for k in ["metric", "player_value", "tier", "benchmark_p50", "gap", "drill"])
```

---

## Shared Patterns

### SQLite connection — `closing()` wrapper
**Source:** `db_utils.py` lines 35–36
**Apply to:** All DB-reading functions in `interpretation.py`
```python
with closing(sqlite3.connect(db_path)) as conn:
    df = pd.read_sql(query, conn, params=(int(steamid), etype))
```

### SteamID int-cast guard
**Source:** `app.py` lines 482–488
**Apply to:** `app.py` Interpretation section + `interpretation.py` all public functions
```python
try:
    sid = int(sid_str)
except ValueError:
    st.error("Invalid SteamID64.")
    sid = None
```
In `interpretation.py` function signatures: always accept `player_steamid: int` (already cast by caller) and document this contract.

### Empty-guard before computation
**Source:** `db_utils.py` line 29: `if df.empty: return`
**Apply to:** All `interpretation.py` functions that call `quantile()` or access `.iloc[0]`
```python
series = df["column"].dropna()
if series.empty:
    return fallback_value
```

### Named constants for thresholds
**Source:** `config.py` lines 23–50 (VELOCITY_PEEK_THRESHOLD_UPS, T0_MIN_OFFSET_TICKS, etc.)
**Apply to:** Hard-coded fallback tier thresholds in `interpretation.py`
```python
# In interpretation.py — fallback thresholds for <20 demo benchmark (D-04/D-07)
# Values from analytics.db verified queries 2026-05-06 (karrigan, 57 demos)
_FALLBACK_THRESHOLDS: dict[str, dict[str, tuple[float, float, float]]] = {
    "peek": {
        "crosshair_angle_at_t0_deg": (3.0, 6.0, 11.0),   # p25, p50, p75
        "rt_visible_to_aim_ms":      (125.0, 203.0, 328.0),
        "rt_aim_to_hit_ms":          (203.0, 422.0, 1000.0),
        "rt_visible_to_hit_ms":      (375.0, 578.0, 1156.0),
        "kill_rate":                 (31.5, 24.5, 17.2),   # reversed: p75, p50, p25
        "hit_rate":                  (15.2, 10.9, 8.8),
    },
    "hold": {
        "crosshair_angle_at_t0_deg": (3.0, 5.0, 10.0),
        "rt_visible_to_hit_ms":      (375.0, 516.0, 812.0),
        "kill_rate":                 (7.3, 4.3, 1.8),
        "hit_rate":                  (3.3, 1.7, 0.7),
    },
}
```

### Section-level `st.caption()` for caveats
**Source:** `app.py` lines 438–441
**Apply to:** RT metric rows in Interpretation table — inline survivorship bias caveat (REQ-INT-04)
```python
st.caption(
    "RT metrics reflect only won duels (survivorship bias). "
    "Comparisons across players should account for opponent difficulty."
)
```

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| `interpretation.py` — `assign_tier()` pure logic | utility | transform | No tier/percentile ranking logic exists in codebase. Pattern designed from scratch per RESEARCH.md Pattern 2. |
| `app.py` — `st.tabs()` within section | component | — | App currently has no `st.tabs()` usage anywhere. Pattern is standard Streamlit API, no codebase analog. |

---

## Metadata

**Analog search scope:** `db_utils.py`, `app.py`, `config.py`, `kill_rate_analysis.py`, `duel_attempts.py`, `tests/test_db_utils.py`, `tests/test_kill_rate_analysis.py`
**Files read:** 9
**Pattern extraction date:** 2026-05-06
