# Phase 6: Quality Gates + Schema Migration — Pattern Map

**Mapped:** 2026-04-30
**Files analyzed:** 5 (4 modified + 1 new)
**Analogs found:** 5 / 5

## File Classification

| Файл | Role | Data Flow | Closest Analog | Match Quality |
|-|-|-|-|-|
| `csv_utils.py` | utility | CRUD | самосылка (расширяется) | exact |
| `ddm_analyzer.py` | service | request-response | самосылка (расширяется) | exact |
| `duel_attempts.py` | model + service | CRUD | `config.py` (dataclass) + `ddm_analyzer.py` (state) | role-match |
| `kill_rate_analysis.py` | utility | CRUD | `csv_utils.save_results()` | exact |
| `db_utils.py` (новый) | utility | CRUD | `csv_utils.py` | role-match |

## Pattern Assignments

### `db_utils.py` (новый файл — utility, CRUD)

**Analog:** `csv_utils.py` — повторяет ту же идиому replace-or-append, но через SQLite.

**Imports pattern** (копировать из `csv_utils.py` lines 1–8):
```python
import sqlite3
import pandas as pd
from typing import List
```

**Idempotency pattern** — replace-or-append by match_id (аналог `csv_utils.save_results()` lines 38–53):
```python
def save_to_db(df: pd.DataFrame, db_path: str, table: str, match_id: int | str) -> None:
    """Replace-or-append: удаляет старые строки match_id, вставляет новые."""
    with sqlite3.connect(db_path) as conn:
        existing = pd.read_sql(f"SELECT * FROM {table}", conn) if _table_exists(conn, table) else pd.DataFrame()
        if not existing.empty and "match_id" in existing.columns:
            conn.execute(f"DELETE FROM {table} WHERE match_id = ?", (str(match_id),))
        df.to_sql(table, conn, if_exists="append", index=False)

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
    return cur.fetchone() is not None
```

**Error handling pattern** (копировать из `csv_utils.load_existing_results()` lines 33–35):
```python
except (sqlite3.DatabaseError, OSError, ValueError) as e:
    print(f"Warning: could not access '{db_path}': {e}")
    return
```

---

### `csv_utils.py` — расширение `save_results()` (utility, CRUD)

**Файл:** `csv_utils.py`, lines 38–53 — существующий паттерн без изменений.

Никаких изменений в `save_results()` не требуется — Path 1 уже работает.

**Новая колонка `player_steamid`** добавляется только в DataFrame, который передаётся в `save_results()` — в самом `csv_utils.py` код менять не нужно (функция не фильтрует по колонкам, пишет всё что в DataFrame).

---

### `kill_rate_analysis.py` — `save_attempts()` получает dedup (utility, CRUD)

**Analog:** `csv_utils.save_results()` lines 38–53.

**Текущая реализация** (lines 83–89) — НЕТ dedup, перезаписывает весь файл:
```python
def save_attempts(name: str, attempts: List[DuelAttempt]) -> None:
    if not attempts:
        return
    rows = [dataclasses.asdict(a) for a in attempts]
    path = f"{name}_attempts.csv"
    pd.DataFrame(rows).to_csv(path, index=False)
    print(f"  Saved {len(rows)} rows → {path}")
```

**Целевой паттерн** (скопировать идиому из `csv_utils.save_results()` lines 44–53):
```python
def save_attempts(name: str, attempts: List[DuelAttempt], match_id: str) -> None:
    if not attempts:
        return
    rows = pd.DataFrame([dataclasses.asdict(a) for a in attempts])
    path = f"{name}_attempts.csv"
    # --- dedup by match_id (аналог csv_utils.save_results) ---
    if os.path.exists(path) and os.path.getsize(path) > 0:
        existing = pd.read_csv(path, dtype=str)
        existing = existing[existing["match_id"].astype(str) != str(match_id)]
        combined = pd.concat([existing, rows.astype(str)], ignore_index=True)
    else:
        combined = rows
    combined.to_csv(path, index=False)
    print(f"  → Saved {len(rows)} rows for match_id={match_id} (CSV total: {len(combined)} rows).")
```

**Вызов нужно обновить** в `run_player()` (line 78): `save_attempts(name, attempts)` → `save_attempts(name, attempts, match_id=f"{name}_{basename}")`.

---

### `ddm_analyzer.py` — три изменения (service, request-response)

#### Изменение 1: `self.last_accepted_t2_tick` state (D-07)

**Analog:** существующий state в `__init__` (lines 65–72):
```python
self.player_steamid = player_steamid
self.analysis_moments: List[AnalysisMoment] = []
self.enemy_velocity_threshold = enemy_velocity_threshold
```

**Целевой паттерн** — добавить рядом:
```python
self.last_accepted_t2_tick: Optional[int] = None  # overlapping window gate (D-07)
```

**Gate в `analyze_demo()`** — добавить перед `results.append(result)` (lines 778–779), после проверки `if result:`:
```python
if result:
    first_hit = result["t2_first_hit_tick"]
    if (
        self.last_accepted_t2_tick is not None
        and isinstance(first_hit, (int, float))
        and not math.isnan(float(first_hit))
        and int(first_hit) < self.last_accepted_t2_tick + 300
    ):
        self.logger.warning(
            f"Overlapping window rejected: first_hit={first_hit} < "
            f"last_accepted_t2={self.last_accepted_t2_tick} + 300"
        )
        continue
    results.append(result)
    if isinstance(first_hit, (int, float)) and not math.isnan(float(first_hit)):
        self.last_accepted_t2_tick = int(first_hit)
```

**logger.warning паттерн** (аналог lines 373–377 в `_resolve_t0()`):
```python
self.logger.warning(f"{tag} REJECTED — ...")
return None
```

#### Изменение 2: teammate gate в `analyze_engagement_episode()` (D-09)

**Analog:** `is_1v1_duel()` lines 251–288 — тот же подход: фильтр player_hurt в окне.

**Место вставки:** сразу после вызова `is_1v1_duel()` (line 606), до velocity gate (line 611):
```python
# Teammate gate (D-09): reject if teammate hurt target_enemy in [T0..T2]
teammate_hurt = self._teammate_hurt_target(
    all_player_hurt_events_df, t0_tick, t2_tick, target_enemy_id
)
if teammate_hurt:
    self.logger.warning(f"{tag} REJECTED — teammate phantom kill detected in [T0..T2]")
    return None
```

**Новый приватный метод** (по образцу `is_1v1_duel()` lines 251–288):
```python
def _teammate_hurt_target(
    self,
    all_player_hurt_events_df: pd.DataFrame,
    t0_tick: int,
    t2_tick: int,
    target_enemy_id,
) -> bool:
    """True если в окне [t0..t2] кто-то из тиммейтов нанёс урон target_enemy_id."""
    window = all_player_hurt_events_df[
        (all_player_hurt_events_df["tick"] >= t0_tick)
        & (all_player_hurt_events_df["tick"] <= t2_tick)
        & (all_player_hurt_events_df["user_steamid"].astype(str) == str(target_enemy_id))
        & (all_player_hurt_events_df["attacker_steamid"].astype(str) != str(self.player_steamid))
    ]
    # Фильтруем только тиммейтов (та же команда что player) —
    # требует team_num в all_player_hurt_events_df или отдельный all_ticks_df lookup.
    # Простой вариант Phase 6: любой другой attacker, не являющийся target_enemy, считается тиммейтом.
    # (Точная team_num фильтрация — Phase 8 refinement если нужна.)
    return not window.empty
```

#### Изменение 3: `player_steamid` в результирующий dict (D-05)

**Место:** в return dict `analyze_engagement_episode()` (lines 651–670):
```python
return {
    "match_id": self.match_id,
    "player_steamid": self.player_steamid,  # D-05 — добавить эту строку
    "map_name": self.map_name,
    ...
}
```

---

### `duel_attempts.py` — `DuelAttempt` получает `player_steamid` (model, CRUD)

**Analog:** `AnalysisMoment` dataclass в `config.py` lines 117–129 — Optional field с дефолтом None.

**Текущий `DuelAttempt`** (lines 27–50):
```python
@dataclass
class DuelAttempt:
    match_id: str
    map_name: str
    t0_tick: int
    enemy_steamid: int
    was_killed: bool
    bullets_fired: int
    bullets_hit: int
    engagement_type: str
    player_velocity_ups: float
    crosshair_angle_deg: float
    hurt_victims_in_window: str = ""
    fires_in_cluster: int = 0
```

**Целевой паттерн** — добавить поле с дефолтом (аналог Optional fields в AnalysisMoment):
```python
@dataclass
class DuelAttempt:
    match_id: str
    map_name: str
    t0_tick: int
    enemy_steamid: int
    was_killed: bool
    bullets_fired: int
    bullets_hit: int
    engagement_type: str
    player_velocity_ups: float
    crosshair_angle_deg: float
    hurt_victims_in_window: str = ""
    fires_in_cluster: int = 0
    player_steamid: Optional[int] = None  # D-05
```

**Заполнение в `DuelAttemptFinder._process_cluster()`** (line 198):
```python
return DuelAttempt(
    ...
    player_steamid=self.player_steamid,  # добавить
)
```

---

### `config.py` — без изменений в Phase 6

`T0_MIN_OFFSET_TICKS = 20` (line 89) уже реализован (D-10 DONE). Phase 6 не трогает `config.py`.

---

## Shared Patterns

### Replace-or-append by match_id
**Source:** `csv_utils.save_results()` lines 38–53
**Apply to:** `kill_rate_analysis.save_attempts()` (D-06), `db_utils.save_to_db()` (D-01/D-03)
```python
existing = load_existing_results(filename)
if not existing.empty and "match_id" in existing.columns:
    existing = existing[existing["match_id"].astype(str) != str(match_id)]
    combined = pd.concat([existing, results_df], ignore_index=True)
else:
    combined = results_df
combined.to_csv(filename, index=False)
```

### logger.warning rejection pattern
**Source:** `ddm_analyzer.py` lines 373–377, 608, 614–618
**Apply to:** D-07 overlapping window gate, D-09 teammate gate
```python
self.logger.warning(f"{tag} REJECTED — <reason>")
return None  # в методах; continue — в цикле analyze_demo()
```

### State в `__init__` (Optional[int] с None дефолтом)
**Source:** `ddm_analyzer.py` lines 65–72
**Apply to:** `self.last_accepted_t2_tick: Optional[int] = None` (D-07)

### player_hurt window filter
**Source:** `is_1v1_duel()` lines 266–287
**Apply to:** `_teammate_hurt_target()` (D-09) — тот же паттерн DataFrame boolean indexing

### dataclass Optional field
**Source:** `config.py` AnalysisMoment lines 117–129
**Apply to:** `DuelAttempt.player_steamid: Optional[int] = None` (D-05)

---

## No Analog Found

Нет файлов без аналога — все паттерны покрыты существующим кодом.

---

## Metadata

**Analog search scope:** `csv_utils.py`, `ddm_analyzer.py`, `duel_attempts.py`, `kill_rate_analysis.py`, `config.py`
**Files scanned:** 5
**Pattern extraction date:** 2026-04-30
