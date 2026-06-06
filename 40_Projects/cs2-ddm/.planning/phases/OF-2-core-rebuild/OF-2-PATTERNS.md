# Phase OF-2: Core Rebuild - Pattern Map

**Mapped:** 2026-06-05
**Files analyzed:** 6
**Analogs found:** 6 / 6

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `outcome_first.py` | service | event-driven, CRUD | `outcome_first_spike.py` (logic) + `duel_attempts.py` (module structure) | exact |
| `db_utils.py` | utility | CRUD | `db_utils.py` itself (additive edit) | exact |
| `config.py` | config | — | `config.py` itself (additive edit) | exact |
| `tests/test_outcome_first.py` | test | — | `tests/test_duel_attempts.py` | role-match |
| `duel_attempts.py` | service | CRUD | `duel_attempts.py` itself (surgical delete) | exact |
| `batch_runner.py` | service | batch | `batch_runner.py` itself (additive edit) | exact |

---

## Pattern Assignments

### `outcome_first.py` (new service module, event-driven)

**Primary analog:** `outcome_first_spike.py` (copy-port, nearly production-ready)
**Structure analog:** `duel_attempts.py` (module header, import style, logging setup)

**Imports pattern** — copy from `duel_attempts.py` lines 1-21:
```python
from __future__ import annotations

import logging
from typing import List, Optional, Tuple

import pandas as pd

from config import (
    _KILL_CONFIRM_WINDOW_TICKS,
    KNIFE_WEAPON_NAMES,
    AWP_WEAPON_NAMES,
    UTILITY_WEAPON_NAMES,       # new — add to config.py first
    _INITIATOR_LOOKBACK_TICKS,  # new — add to config.py first
    DB_PATH,
)
from db_utils import save_to_db, init_db

logger = logging.getLogger(__name__)
```

**UTF-8 env guard** — copy from `outcome_first_spike.py` lines 42-45:
```python
import os, sys
os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
```

**`_coerce_sid`** — port verbatim from `outcome_first_spike.py` lines 73-82:
```python
def _coerce_sid(series: pd.Series) -> pd.Series:
    """SteamID64 -> int64 WITHOUT a float64 intermediate."""
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")
```

**`_normalize_events`** — port verbatim from spike lines 85-99.

**`collect_exchanges`** — port from spike lines 102-126, ADD gun-only filter before `pd.concat`:
```python
# Gun-only anchor: filter hurt_df before processing
if hurt_df is not None and not hurt_df.empty and "weapon" in hurt_df.columns:
    hurt_df = hurt_df[
        ~hurt_df["weapon"].astype(str).str.lower().isin(UTILITY_WEAPON_NAMES)
    ]
# then proceed with spike's pd.concat logic
```

**`_episode_outcome`** — port verbatim from spike lines 129-141.

**`_episode_initiator`** — port verbatim from spike lines 144-167. Replace hardcoded `INITIATOR_LOOKBACK_TICKS` with constant from config.

**`group_episodes`** — port verbatim from spike lines 170-209. Add `match_id: str` and `demo_name: str` params; include them in the episode dict.

**`_parse_demo_events`** — port from spike lines 212-. Keep as private helper.

**Multi-player public API** (new, not in spike):
```python
def reconstruct_all_players(
    demo_path: str,
    player_sids: List[int],
    match_ids_by_sid: dict,
    db_path: str = DB_PATH,
) -> None:
    """Parse demo once, reconstruct episodes for all players, write to DB."""
    hurt_df, death_df, fires_df = _parse_demo_events(demo_path)
    demo_name = os.path.basename(demo_path)
    for player_sid in player_sids:
        try:
            events = collect_exchanges(hurt_df, death_df, player_sid)
            eps = group_episodes(events, fires_df, player_sid,
                                 demo=demo_name,
                                 match_id=str(match_ids_by_sid[player_sid]))
            if eps:
                df = pd.DataFrame(eps)
                df["player_steamid"] = player_sid
                save_to_db(df, db_path, "duel_episodes",
                           match_ids_by_sid[player_sid])
        except Exception:
            logger.exception("Failed to reconstruct episodes for %s in %s",
                             player_sid, demo_name)
```

**Error handling pattern** — use `logger.exception(...)` (not print) inside try/except, per `duel_attempts.py` logging style. Never raise to caller from the per-player loop.

---

### `db_utils.py` (additive edits only)

**Analog:** `db_utils.py` itself — all edits follow existing patterns in the file.

**`_ALLOWED_TABLES` — line 17:**
```python
# BEFORE:
_ALLOWED_TABLES = {"engagements", "duel_attempts"}
# AFTER:
_ALLOWED_TABLES = {"engagements", "duel_attempts", "duel_episodes"}
```

**`_migrate_schema` — add after `duel_attempts` block (after line 127), copy DDL structure from lines 110-127:**
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS duel_episodes (
        match_id TEXT,
        demo_name TEXT DEFAULT NULL,
        player_steamid INTEGER,
        opponent_steamid INTEGER,
        first_event_tick INTEGER,
        last_event_tick INTEGER,
        outcome TEXT,
        initiator TEXT,
        p_was_attacker_first INTEGER,
        n_hits_p_on_e INTEGER DEFAULT 0,
        n_hits_e_on_p INTEGER DEFAULT 0,
        anchor_weapon TEXT DEFAULT NULL
    )
""")
```

**`get_next_match_id` — add `duel_episodes` scan (lines 172-180 pattern):**
```python
r3 = conn.execute(
    "SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_episodes"
).fetchone()[0] if _table_exists(conn, "duel_episodes") else None
current_max = max(r1 or 0, r2 or 0, r3 or 0)
```

**`force_reprocess_demo` — add episode cleanup (after line 200, copy lines 199-200 pattern):**
```python
conn.execute("DELETE FROM duel_episodes WHERE match_id=?", (str(old_match_id),))
```

**Safe SteamID read pattern** (lines 141-148 style — use for any new read functions):
```python
rows = conn.execute(
    "SELECT player_steamid, ... FROM duel_episodes WHERE ..."
).fetchall()
df = pd.DataFrame(rows, columns=["player_steamid", ...])
# NEVER: pd.read_sql for sid columns
```

---

### `config.py` (additive edits only)

**Analog:** `config.py` itself — copy frozenset style from lines 35-50.

**New constants — add after `AWP_WEAPON_NAMES` block:**
```python
# Weapon categories excluded from gun-only episode anchoring.
# HE/molotov/utility damage does NOT start a new duel episode (OF-2 decision).
# "inferno" = demoparser2 tick-damage from molotov (distinct from "molotov" trigger).
UTILITY_WEAPON_NAMES: frozenset = frozenset([
    "hegrenade", "weapon_hegrenade",
    "molotov", "weapon_molotov",
    "incgrenade", "weapon_incgrenade",
    "inferno",
    "flashbang", "weapon_flashbang",
    "smokegrenade", "weapon_smokegrenade",
])

# Lookback window for weapon_fire initiator attribution in outcome_first.py.
# 128 ticks = 2s @ 64 Hz. Matches spike v1 semantics.
_INITIATOR_LOOKBACK_TICKS: int = 128
```

**Reuse existing** `_KILL_CONFIRM_WINDOW_TICKS = 320` (line 78) as episode gap threshold — no alias needed, add comment at use site.

---

### `tests/test_outcome_first.py` (new test file)

**Analog:** `tests/test_duel_attempts.py` lines 1-80 (import style, DataFrame fixture style, `patch` usage)

**Imports pattern** (copy from `test_duel_attempts.py` lines 1-8):
```python
import pandas as pd
import pytest
from outcome_first import (
    _coerce_sid, collect_exchanges, group_episodes,
    reconstruct_all_players,
)
```

**Synthetic DataFrame fixture style** (copy from `test_duel_attempts.py` lines 10-11):
```python
def _hurt_df(rows):
    return pd.DataFrame(rows)
```

**Wave-0 RED test skeleton** (port from spike `self_check`, lines 380-450 area):
```python
P  = 76561198386265483
E1 = 76561198113666193
E2 = 76561198081484775

def test_collect_exchanges_gun_only():
    """HE grenade row does NOT anchor an episode."""
    hurt = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": [str(E1)],
        "user_steamid":     [str(P)],
        "weapon":           ["hegrenade"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    events = collect_exchanges(hurt, death, P)
    assert events.empty

def test_coerce_sid_none_preserves_17digit():
    """None row must not corrupt a 17-digit SteamID via float64."""
    import pandas as pd
    s = pd.Series([str(P), None, str(E1)])
    result = _coerce_sid(s)
    assert int(result.iloc[0]) == P
    assert int(result.iloc[1]) == 0
    assert int(result.iloc[2]) == E1
```

**DB write test pattern** — use `tmp_path` pytest fixture (standard in project, no conftest needed):
```python
def test_db_write_duel_episodes(tmp_path):
    from db_utils import init_db, save_to_db
    db = str(tmp_path / "test.db")
    init_db(db)
    df = pd.DataFrame([{
        "match_id": "1", "demo_name": "test.dem",
        "player_steamid": P, "opponent_steamid": E1,
        "first_event_tick": 1000, "last_event_tick": 1100,
        "outcome": "won", "initiator": "player",
        "p_was_attacker_first": 1,
        "n_hits_p_on_e": 2, "n_hits_e_on_p": 1,
        "anchor_weapon": "ak47",
    }])
    save_to_db(df, db, "duel_episodes", 1)
    import sqlite3
    rows = sqlite3.connect(db).execute("SELECT * FROM duel_episodes").fetchall()
    assert len(rows) == 1
```

---

### `duel_attempts.py` (surgical delete of geometry-selector methods)

**Analog:** `duel_attempts.py` itself.

**Delete:** `DuelAttemptFinder._process_cluster` (L167) and `DuelAttemptFinder.find_attempts` (L87) — the two methods that call `find_first_visible_enemy_in_window` as opponent selector.

**Keep:** `DuelAttempt` dataclass (lines 26-51) — imported by `kill_rate_analysis.py` (line 19) and `tests/test_db_utils.py` (line 124).

**Keep:** `DuelAttemptFinder` class shell and any utility methods not part of the geometry-selector path.

**Acceptance criterion:** `grep -r "DuelAttemptFinder" . --include="*.py"` returns 0 hits in production files (`duel_attempts.py` class def excluded); `grep -r "from duel_attempts import DuelAttempt"` still returns 2 hits.

---

### `batch_runner.py` (additive: wire new episode write)

**Analog:** `batch_runner.py` lines 105-126 (the `analyze_demo_worker` write block).

**Existing pattern** (lines 124-126) — `duel_attempts` write:
```python
att_df = pd.DataFrame([asdict(a) for a in attempts])
_db.save_to_db(att_df, db_path, "duel_attempts", match_id)
```

**New parallel write** — add after the above, calling `reconstruct_all_players`:
```python
from outcome_first import reconstruct_all_players
reconstruct_all_players(
    demo_path,
    player_sids=[player_steamid],
    match_ids_by_sid={player_steamid: match_id},
    db_path=db_path,
)
```

Note: OF-2 keeps one-player-per-worker (Option B) — no batch_runner API change needed, just add the episode write call inside the existing worker. parse-once optimization deferred to OF-3.

---

## Shared Patterns

### SteamID coercion
**Source:** `outcome_first_spike.py` lines 73-82 → port to `outcome_first.py`
**Apply to:** every DataFrame column containing steamids in `outcome_first.py`
```python
def _coerce_sid(series: pd.Series) -> pd.Series:
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")
```
NEVER use `pd.to_numeric` or `pd.read_sql` on sid columns.

### DB write + table whitelist
**Source:** `db_utils.py` lines 17, 20-49
**Apply to:** all new table writes — add `"duel_episodes"` to `_ALLOWED_TABLES` FIRST, then call `save_to_db`. The write silently swallows errors; test writes via `init_db` + `tmp_path` pattern.

### Idempotent schema migration
**Source:** `db_utils.py` lines 74-127
**Apply to:** `duel_episodes` DDL — use `CREATE TABLE IF NOT EXISTS` inside `_migrate_schema`, called from `init_db`. Never create tables outside this function.

### Error handling in per-player loops
**Source:** `duel_attempts.py` logging style + spike's `except Exception: print(...)` upgraded
**Apply to:** `reconstruct_all_players` player loop — `logger.exception(...)`, never raise, never silent swallow without log.

### Frozenset constant style
**Source:** `config.py` lines 35-50
**Apply to:** `UTILITY_WEAPON_NAMES` — same style, same file section, with doc comment explaining each category.

---

## No Analog Found

None. All files have direct analogs in the codebase.

---

## Metadata

**Analog search scope:** repo root + `tests/` + `config.py` + `db_utils.py`
**Files scanned:** `outcome_first_spike.py`, `duel_attempts.py`, `db_utils.py`, `config.py`, `batch_runner.py`, `tests/test_duel_attempts.py`, `tests/conftest.py`
**Pattern extraction date:** 2026-06-05
