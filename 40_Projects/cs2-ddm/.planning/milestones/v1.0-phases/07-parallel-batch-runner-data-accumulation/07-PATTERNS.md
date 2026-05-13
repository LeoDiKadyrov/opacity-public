# Phase 7: Parallel Batch Runner + Data Accumulation — Pattern Map

**Mapped:** 2026-05-05
**Files analyzed:** 4 (1 new, 3 modified)
**Analogs found:** 4 / 4

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `batch_runner.py` | service / worker module | batch, request-response | `run_analysis.py` | role-match (sequential→parallel) |
| `db_utils.py` | utility extension | CRUD | `db_utils.py` itself (extend) | exact — add functions to existing file |
| `config.py` | config | — | `config.py` itself (extend) | exact — add constant |
| `app.py` | UI layer | event-driven, request-response | `app.py` Section 2 `_run_analysis()` | exact — add sibling section |

---

## Pattern Assignments

### `batch_runner.py` (new service module, batch)

**Analog:** `run_analysis.py`

**Imports pattern** (`run_analysis.py` lines 1–21):
```python
import pandas as pd
from typing import List

from ddm_analyzer import DDMAnalyzer
from csv_utils import save_results

try:
    from obsidian_writer import write_analysis_note
    _OBSIDIAN_WRITER_AVAILABLE = True
except ImportError:
    _OBSIDIAN_WRITER_AVAILABLE = False
```
For `batch_runner.py`: omit `csv_utils`, `obsidian_writer`. Add `concurrent.futures`, `logging`, `pathlib.Path`, `db_utils`.

**Core per-demo loop pattern** (`run_analysis.py` lines 39–76):
```python
for match_id, filename in DEMOS:
    demo_path = rf"{BASE}\{filename}"
    try:
        analyzer = DDMAnalyzer(
            demo_path, PLAYER_STEAMID,
            match_id=match_id, tickrate=64, debug_prints=DEBUG_PRINTS,
        )
    except Exception as e:
        print(f"  ERROR initialising analyzer: {e}")
        continue

    try:
        results_df, _ = analyzer.analyze_demo(bulk_mode=True)
    except Exception as e:
        print(f"  ERROR during analysis: {e}")
        continue
    # db_utils.save_to_db is already called inside analyze_demo(); no duplicate write needed
```
Worker function body mirrors this loop body for a single demo. Key differences:
1. `match_id` is pre-assigned (passed as arg), not from a DEMOS list
2. Errors are returned as `dict` with `"status": "error"`, not `print + continue`
3. `obsidian_writer` is NOT called in batch mode
4. `demo_name = Path(demo_path).stem` injected into DataFrame before save

**DDMAnalyzer constructor** (`ddm_analyzer.py` lines 50–58):
```python
def __init__(
    self,
    demo_path: str,
    player_steamid: int,
    match_id=None,
    tickrate: int = 64,
    debug_prints: bool = False,
    enemy_velocity_threshold: float = ENEMY_VELOCITY_HOLD_THRESHOLD_UPS,
    player_velocity_threshold: float = VELOCITY_PEEK_THRESHOLD_UPS,
```
Worker passes: `demo_path`, `player_steamid`, `match_id` (pre-assigned int), `tickrate=64`, `debug_prints=False`. Threshold params use defaults.

**Error handling pattern** (`run_analysis.py` lines 46–59):
```python
try:
    analyzer = DDMAnalyzer(...)
except Exception as e:
    print(f"  ERROR initialising analyzer: {e}")
    continue

try:
    results_df, _ = analyzer.analyze_demo(bulk_mode=True)
except Exception as e:
    print(f"  ERROR during analysis: {e}")
    continue
```
Worker wraps the whole body in a single `try/except Exception as exc` and returns `{"status": "error", "traceback": traceback.format_exc()}`. Log to `batch_errors.log` using `logging.FileHandler`.

**Logging pattern** (`config.py` lines 141–156):
```python
def get_logger(match_id: int | str, debug: bool = False) -> logging.Logger:
    name = f"DDM.{match_id}"
    logger = logging.getLogger(name)
    if not logger.handlers:
        fh = logging.FileHandler("ddm_analysis.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        logger.addHandler(sh)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    return logger
```
`batch_runner.py` creates its own logger the same way — name `"BatchRunner"`, file `"batch_errors.log"`.

---

### `db_utils.py` (utility extension, CRUD)

**Existing file to extend:** `db_utils.py` (57 lines total — read in full above)

**Existing structure to preserve:**
```python
import sqlite3
from contextlib import closing
from typing import Union
import pandas as pd

_ALLOWED_TABLES = {"engagements", "duel_attempts"}

def save_to_db(df, db_path, table, match_id) -> None: ...
def _table_exists(conn, table) -> bool: ...
```

**Table whitelist pattern** (`db_utils.py` line 15):
```python
_ALLOWED_TABLES = {"engagements", "duel_attempts"}
```
`processed_matches` is NOT added to `_ALLOWED_TABLES` — it is written only by `mark_processed()` directly, not via `save_to_db()`.

**Existing write pattern** (`db_utils.py` lines 18–47) — preserve exactly:
```python
def save_to_db(df, db_path, table, match_id) -> None:
    if df.empty:
        return
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table '{table}'. Allowed: {_ALLOWED_TABLES}")
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            with conn:  # implicit transaction: DELETE + to_sql atomic
                if _table_exists(conn, table):
                    conn.execute(
                        f"DELETE FROM {table} WHERE match_id = ?",
                        (str(match_id),),
                    )
                df.to_sql(table, conn, if_exists="append", index=False)
    except (sqlite3.DatabaseError, OSError, ValueError) as e:
        print(f"Warning: could not write to '{db_path}' table '{table}': {e}")
```
New functions follow the same `with closing(sqlite3.connect(db_path)) as conn:` pattern.

**New functions to add** (following existing `closing` pattern):

`init_db(db_path: str) -> None` — sets WAL + runs `_migrate_schema()`. Called once at app start and in each worker.

`_migrate_schema(conn: sqlite3.Connection) -> None` — idempotent: `ALTER TABLE ADD COLUMN` if missing, `CREATE TABLE IF NOT EXISTS` for new tables. Uses `PRAGMA table_info()` and `sqlite_master` checks (same as existing `_table_exists` helper).

`is_processed(db_path: str, demo_filename: str, player_steamid: int) -> bool` — `SELECT 1 FROM processed_matches WHERE demo_filename=? AND player_steamid=?`

`mark_processed(db_path: str, demo_filename: str, player_steamid: int, match_id: int) -> None` — `INSERT OR REPLACE INTO processed_matches ...` with `with conn:` implicit transaction.

`get_next_match_id(db_path: str) -> int` — `MAX(CAST(match_id AS INTEGER))` across both `engagements` and `duel_attempts`, returns `current_max + 1`.

**Schema for new tables** (from RESEARCH.md Focus Area 5):
```sql
-- processed_matches: idempotency tracker
CREATE TABLE IF NOT EXISTS processed_matches (
    demo_filename TEXT NOT NULL,
    player_steamid INTEGER NOT NULL,
    match_id INTEGER NOT NULL,
    processed_at TEXT NOT NULL,
    PRIMARY KEY (demo_filename, player_steamid)
);

-- duel_attempts: Phase 7 creates this (was missing from analytics.db)
CREATE TABLE IF NOT EXISTS duel_attempts (
    match_id TEXT,
    map_name TEXT,
    demo_name TEXT,
    player_steamid INTEGER,
    t0_tick INTEGER,
    enemy_steamid INTEGER,
    was_killed INTEGER,
    bullets_fired INTEGER,
    bullets_hit INTEGER,
    engagement_type TEXT,
    player_velocity_ups REAL,
    crosshair_angle_deg REAL,
    hurt_victims_in_window TEXT
);
```

**ALTER TABLE migrations** (idempotent, for existing engagements table):
```sql
ALTER TABLE engagements ADD COLUMN demo_name TEXT DEFAULT NULL;
ALTER TABLE engagements ADD COLUMN player_steamid INTEGER DEFAULT NULL;
```

---

### `config.py` (config extension)

**Existing constant format** (`config.py` lines 1–156):

Grouping pattern — constants are grouped under comment banners:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Group name
# ─────────────────────────────────────────────────────────────────────────────
CONSTANT_NAME: type = value
```

Naming convention: `SCREAMING_SNAKE_CASE` for public constants, `_LEADING_UNDERSCORE_SCREAMING_SNAKE` for internal-use constants.

Type-annotated: `DB_PATH: str = "analytics.db"`, `VELOCITY_PEEK_THRESHOLD_UPS: float = 50.0`, `T0_MIN_OFFSET_TICKS: int = 20`.

**New constant to add:**
```python
# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

# Default number of parallel worker processes for batch demo analysis.
# Matches i7-11800H physical core count (8 cores / 16 logical).
# Each worker loads awpy + demoparser2 + numpy (~300 MB RAM each).
DEFAULT_BATCH_WORKERS: int = 8
```

---

### `app.py` (UI extension, event-driven)

**Existing section structure** (`app.py` lines 85–419) — follow exactly:
```python
# ── Section N: Title ──────────────────────────────────────────────────────────
st.header("N. Title")
```

**Session state initialization pattern** (`app.py` lines 32–43):
```python
if "results_df" not in st.session_state:
    st.session_state.results_df = pd.DataFrame()
if "demo_paths" not in st.session_state:
    st.session_state.demo_paths = {}
```
New batch keys follow same guard pattern:
```python
if "batch_running" not in st.session_state:
    st.session_state.batch_running = False
if "batch_status" not in st.session_state:
    st.session_state.batch_status = {}
if "batch_results" not in st.session_state:
    st.session_state.batch_results = []
```

**SteamID validation pattern** (`app.py` lines 217–220):
```python
sid_str = st.session_state.get("steamid_input", "").strip()
try:
    player_steamid = int(sid_str)
except ValueError:
    st.error("Invalid SteamID64 — must be a plain 17-digit number.")
    st.stop()
```
Batch section reuses same `int()` cast + `ValueError` catch pattern.

**Progress bar pattern** (`app.py` lines 160–163, `_run_analysis`):
```python
progress_bar = st.progress(0, text="Starting…")
for i, (filename, demo_path) in enumerate(demos):
    progress_bar.progress(i / len(demos), text=f"Analyzing {filename}…")
progress_bar.progress(1.0, text="Done!")
```
Batch section uses the polling variant:
```python
# In polling loop (main thread, after st.rerun()):
status = st.session_state.get("batch_status", {})
done = status.get("done", 0)
total = status.get("total", 1)
st.progress(done / total, text=f"Processing demo {done}/{total}: {status.get('current', '')}")
```

**Error display pattern** (`app.py` lines 189–191):
```python
except Exception as e:
    import traceback
    st.error(f"✗ `{filename}` — {e}")
    st.code(traceback.format_exc())
```
Batch section: display error summary at end from `status["errors"]` list using `st.warning()` for each entry.

**`analyze_demo()` call signature** (`app.py` lines 173):
```python
results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)
```
Worker uses exact same call. Note: `analyze_demo()` already calls `db_utils.save_to_db(engagements)` internally — worker must NOT call it again for engagements.

**Button + disabled guard pattern** (`app.py` lines 136–141):
```python
analyze_clicked = st.button(
    "▶ Run Analysis",
    use_container_width=True,
    type="primary",
    disabled=no_demos or no_steamid,
)
```
Batch section:
```python
batch_clicked = st.button(
    "▶ Run Batch",
    use_container_width=True,
    type="primary",
    disabled=not dem_files or not batch_steamid_valid or st.session_state.get("batch_running"),
)
```

**for_analysis/ scan pattern** (implied by existing `TEMP_DIR` usage, `app.py` line 101):
```python
TEMP_DIR.mkdir(exist_ok=True)
```
Batch section uses `FOR_ANALYSIS_DIR = Path("for_analysis")` with same `mkdir(exist_ok=True)` guard. File list: `sorted(FOR_ANALYSIS_DIR.glob("*.dem"))`.

---

## Shared Patterns

### `with closing(sqlite3.connect(...)) as conn:` + `with conn:` transaction
**Source:** `db_utils.py` lines 35–44
**Apply to:** All new `db_utils.py` functions (`init_db`, `is_processed`, `mark_processed`, `get_next_match_id`)
```python
with closing(sqlite3.connect(db_path)) as conn:
    with conn:  # implicit transaction, commits on __exit__
        conn.execute("...", (params,))
```

### Logger setup (FileHandler + StreamHandler, `propagate=False`)
**Source:** `config.py` lines 141–156
**Apply to:** `batch_runner.py` module-level logger
```python
logger = logging.getLogger("BatchRunner")
if not logger.handlers:
    fh = logging.FileHandler("batch_errors.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter(
        "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
    ))
    logger.addHandler(fh)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
    logger.addHandler(sh)
logger.setLevel(logging.INFO)
logger.propagate = False
```

### `try / except Exception → continue` error isolation
**Source:** `run_analysis.py` lines 45–59
**Apply to:** `batch_runner.py` worker function outer try/except; batch thread's `as_completed` loop
Return dict `{"status": "error", ...}` from worker; log errors at end of batch run.

### Type annotations: `typing.Tuple`, `typing.List`, `typing.Dict`, `typing.Optional`
**Source:** `config.py` line 9, `db_utils.py` line 10 (`from typing import Union`)
**Apply to:** All new function signatures in `batch_runner.py` and `db_utils.py`

---

## No Analog Found

| File | Role | Data Flow | Reason |
|------|------|-----------|--------|
| (none) | — | — | All patterns have direct analogs in the codebase |

The `ProcessPoolExecutor` + `threading.Thread` polling combination is new to this project but its Streamlit integration pattern is fully specified in RESEARCH.md Focus Area 2 with verified code examples.

---

## Critical Implementation Notes for Planner

1. **Worker function location:** `analyze_demo_worker` MUST be a top-level function in `batch_runner.py`, NOT inside `app.py` or inside a class. Windows spawn requires this. (RESEARCH.md Pitfall 1)

2. **WAL mode:** `init_db()` must set `PRAGMA journal_mode=WAL` — analytics.db currently uses `journal_mode=delete`. (RESEARCH.md Pitfall 2, Focus Area 1)

3. **match_id pre-assignment:** All match_ids assigned in main thread via `get_next_match_id()` BEFORE spawning workers. Never assign inside workers. (RESEARCH.md Focus Area 4)

4. **`analyze_demo()` already saves engagements to DB** (confirmed in `run_analysis.py` line 62 comment). Worker must NOT call `save_to_db` for engagements again. Only call `save_to_db` for `duel_attempts` (currently not saved by analyzer).

5. **`for_analysis/` does not exist on disk** — create with `mkdir(exist_ok=True)` in Wave 0 task or in Batch Analysis section startup. (RESEARCH.md Pitfall 6)

6. **`duel_attempts` table missing from analytics.db** — `init_db()` must `CREATE TABLE IF NOT EXISTS duel_attempts`. (RESEARCH.md Pitfall 7)

7. **Open question on `demo_name` injection:** `analyze_demo()` calls `save_to_db` internally before worker can inject `demo_name`. Resolution needed in planning: either (a) add `self.demo_name = Path(demo_path).stem` to `DDMAnalyzer.__init__` and inject into results dict there, or (b) worker does `UPDATE engagements SET demo_name=? WHERE match_id=?` after `analyze_demo()` returns. Option (a) is cleaner. (RESEARCH.md Open Question 1)

---

## Metadata

**Analog search scope:** `db_utils.py`, `config.py`, `run_analysis.py`, `app.py`, `ddm_analyzer.py` (init signature only)
**Files read:** 5
**Pattern extraction date:** 2026-05-05
