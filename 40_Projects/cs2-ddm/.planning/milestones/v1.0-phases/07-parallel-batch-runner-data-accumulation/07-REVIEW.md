---
phase: 07-parallel-batch-runner-data-accumulation
reviewed: 2026-05-05T00:00:00Z
depth: standard
files_reviewed: 5
files_reviewed_list:
  - batch_runner.py
  - db_utils.py
  - ddm_analyzer.py
  - config.py
  - app.py
findings:
  critical: 3
  warning: 5
  info: 3
  total: 11
status: issues_found
---

# Phase 7: Code Review Report

**Reviewed:** 2026-05-05
**Depth:** standard
**Files Reviewed:** 5
**Status:** issues_found

## Summary

Phase 7 adds a ProcessPoolExecutor-based batch runner, SQLite WAL migration, idempotency tracking, and a Streamlit batch UI. The architecture is sound: match_ids are pre-assigned in the main thread before any worker starts (correctly avoiding concurrent MAX+1 races), the `_ALLOWED_TABLES` whitelist prevents SQL injection through f-string interpolation, and the Windows spawn guard (top-level worker function) is correctly placed.

However there are three blockers: a path traversal vulnerability via demo subfolder selection in the UI, a race condition in `_BATCH_SHARED` dict access (dict operations are not GIL-atomic for compound read-modify-write), and a silent data corruption path where `demo_name` UPDATE failure in `analyze_demo_worker` can leave rows with NULL `demo_name` yet still get marked as processed.

---

## HIGH Issues

### H-01: Path traversal in Streamlit subfolder selection

**File:** `app.py:466`
**Issue:** `_scan_dir = _FOR_ANALYSIS_DIR / selected_folder` is constructed from a value that comes from `_FOR_ANALYSIS_DIR.iterdir()`, which appears safe at first glance. But `_subfolders` contains bare directory names from the filesystem — if an attacker can place a directory with a crafted name (e.g. via symlink or external tool), `Path.__truediv__` will follow it. More critically, the resolved path is never validated to confirm it sits under `_FOR_ANALYSIS_DIR`. A symlinked subdirectory pointing outside the project root would cause the batch runner to scan and submit arbitrary `.dem` files from anywhere on the filesystem to `ProcessPoolExecutor` workers.

**Fix:**
```python
_scan_dir = (_FOR_ANALYSIS_DIR / selected_folder).resolve()
assert _scan_dir.is_relative_to(_FOR_ANALYSIS_DIR.resolve()), "Path traversal attempt"
```
Or equivalently:
```python
_scan_dir = _FOR_ANALYSIS_DIR.resolve() / selected_folder
if not str(_scan_dir).startswith(str(_FOR_ANALYSIS_DIR.resolve())):
    st.error("Invalid folder selection.")
    st.stop()
```

---

### H-02: `_BATCH_SHARED` compound read-modify-write is not thread-safe

**File:** `app.py:532–558`, `app.py:574–577`
**Issue:** `_BATCH_SHARED` is a plain `dict` shared between the main Streamlit thread and the background `_run_batch_thread`. Individual `dict.__setitem__` calls are GIL-protected in CPython, but compound operations are not. The pattern:
```python
_BATCH_SHARED["errors"].append(...)   # line 549
_BATCH_SHARED["results"] = results   # line 552
```
and the main thread polling `_BATCH_SHARED.get("done")` / `_BATCH_SHARED.get("running")` simultaneously can produce torn reads. Specifically: the main thread can read `running=False` and `results=[]` simultaneously (in the window between lines 552 and 559 `finally: running=False`) and display a "0 demos" success banner before results are written.

Additionally, `_BATCH_SHARED["errors"].append(...)` is called from the background thread while the main thread reads `_BATCH_SHARED.get("errors", [])` — list `append` is GIL-safe but only because CPython happens to make it so; this is an implementation detail, not a guarantee.

**Fix:** Use `threading.Lock` for the shared dict, or replace with `queue.Queue` for fire-and-forget updates:
```python
_BATCH_LOCK = threading.Lock()

# In writer:
with _BATCH_LOCK:
    _BATCH_SHARED["results"] = results
    _BATCH_SHARED["running"] = False  # always last

# In reader:
with _BATCH_LOCK:
    still_running = _BATCH_SHARED["running"]
    results = list(_BATCH_SHARED["results"])
```

---

### H-03: Silent data corruption — failed `demo_name` UPDATE still marks demo as processed

**File:** `batch_runner.py:108–117`, `batch_runner.py:127–130`
**Issue:** The `UPDATE engagements SET demo_name=? WHERE match_id=?` block (lines 109–117) silently swallows all exceptions (`except Exception: pass`). If that UPDATE fails (e.g. WAL lock contention, schema mismatch), `mark_processed()` is still called on line 128, permanently recording the demo as done. Re-running will skip it. The database now has engagement rows with `demo_name=NULL` for that match_id that can never be corrected without manual `force_reprocess`.

The same silent-pass pattern at line 95–96 (WAL pragma in worker) is acceptable since WAL mode is best-effort — but the `demo_name` UPDATE failure is a data integrity issue because the rows are permanently committed by `analyze_demo()` before this code runs.

**Fix:** Either log the failure at WARNING level (do not swallow), or restructure so `demo_name` is injected before `save_to_db` rather than via a post-hoc UPDATE:
```python
except Exception as e:
    # log but do not block — demo_name is cosmetic, but record the gap
    import logging as _log
    _log.getLogger("BatchRunner").warning(
        f"demo_name UPDATE failed for match_id={match_id}: {e}"
    )
```
Better long-term: inject `demo_name` into `results_df` inside `DDMAnalyzer` before `save_to_db`, which Phase 7 already does for the inline-analysis path (line 888 of `ddm_analyzer.py`). The worker's post-hoc UPDATE would then be a no-op.

---

## MEDIUM Issues

### M-01: `BATCH_INPUT_DIR = "../for_analysis"` is a relative path — breaks on CWD change

**File:** `config.py:151`
**Issue:** `"../for_analysis"` is relative to wherever the process is launched from. When called from `batch_runner.py` directly (e.g. `python batch_runner.py` from the project root), it resolves to the parent directory. When called from `app.py` via Streamlit (launched from any directory), it may resolve differently again. `for_analysis/` (no `../`) is used everywhere else in the codebase by convention. The `../` prefix is almost certainly a bug.

**Fix:**
```python
BATCH_INPUT_DIR: str = "for_analysis"
```

---

### M-02: `get_next_match_id` executes two separate connections to check two tables — TOCTOU window

**File:** `db_utils.py:157–170`
**Issue:** `get_next_match_id` opens one connection, queries `MAX(match_id)` from `engagements` and `duel_attempts` separately, then returns `max+1`. Between the time this function returns and the time the first worker actually writes rows, another concurrent call (e.g. a second Streamlit session) could call `get_next_match_id` and receive the same value. The pre-assignment mitigation in `BatchRunner.pre_assign_match_ids` only helps if there is exactly one active `BatchRunner` at a time — there is no DB-level lock or transaction preventing two concurrent sessions from colliding.

**Fix:** Wrap the two SELECT statements in a single `BEGIN IMMEDIATE` transaction or use an autoincrement surrogate key in `processed_matches` as the canonical match_id source:
```python
with closing(sqlite3.connect(db_path)) as conn:
    conn.execute("BEGIN IMMEDIATE")
    r1 = ...
    r2 = ...
    # do not commit — read-only, just ensures serialization
    return current_max + 1
```

---

### M-03: `ALTER TABLE engagements ADD COLUMN` is not safe inside a transaction on older SQLite

**File:** `db_utils.py:97`
**Issue:** `ALTER TABLE ... ADD COLUMN` executed inside `with conn:` (which is an implicit transaction) works in SQLite ≥ 3.37 but can raise `OperationalError: cannot commit - no transaction is active` on some 3.x versions because DDL implicitly commits. Python's `sqlite3` module on Windows ships with bundled SQLite — the version depends on CPython build. If a `ADD COLUMN` for column N fails mid-migration (e.g. permissions, disk full), columns 1..N-1 are committed but the migration state is inconsistent.

**Fix:** Execute each `ADD COLUMN` in its own try/except with explicit commit, or check the SQLite version at startup:
```python
for col, col_def in _eng_migrations:
    if col not in cols:
        try:
            conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
        except sqlite3.OperationalError:
            pass  # column already added by concurrent call
```

---

### M-04: `_run_batch_thread` receives `dem_files` as `list[Path]` but `BatchRunner.run` expects `List[Path]` — type mismatch on `str(p)` conversion silently discards Path info on error

**File:** `app.py:567`, `batch_runner.py:245`
**Issue:** When `future.result()` raises, the error dict at line 264–271 captures `demo_path_str = futures[future]` (which is `str(p)` from line 255). But `match_id` in the fallback error dict is `None` (line 267) while `pre_assign_match_ids` already allocated a real ID for this demo. The allocated match_id is therefore orphaned — it exists in no DB table and is never freed. After N failed demos, `get_next_match_id` still returns the correct next value (since `MAX` on empty rows is 0), but it does skip the gaps, leading to non-contiguous IDs with no explanation.

This is cosmetic today but becomes confusing when querying analytics.db expecting contiguous match_ids.

**Fix:** Pass `match_id` into the fallback error dict from `worker_args`:
```python
# futures dict should map future → (demo_path_str, match_id)
futures = {
    pool.submit(analyze_demo_worker, arg): (arg[0], arg[2])
    for arg in worker_args
}
# ...
demo_path_str, alloc_match_id = futures[future]
result = {
    "match_id": alloc_match_id,
    ...
}
```

---

### M-05: `time.sleep(0.5)` in main Streamlit render loop blocks the entire event loop

**File:** `app.py:583`
**Issue:** `time.sleep(0.5)` is called unconditionally in the Streamlit script execution path whenever a batch is running. Streamlit's execution model reruns the entire script on each interaction. This means every user interaction (slider move, button click, page scroll) while a batch is running will block for 500ms before re-rendering. On a 100-demo batch this is acceptable but degrades perceived responsiveness noticeably.

**Fix:** Use `st.empty()` + `st.rerun()` with a shorter sleep, or rely on Streamlit's `experimental_fragment` / `st.fragment` (Streamlit 1.33+) for isolated polling. Minimum viable fix:
```python
time.sleep(0.3)  # reduce from 500ms
```
Or prefer `st.spinner` + a manual refresh button instead of auto-polling.

---

## LOW Issues

### L-01: `_get_batch_logger()` sets up FileHandler at module import time — fails silently in worker processes if CWD differs

**File:** `batch_runner.py:36–46`
**Issue:** `logging.FileHandler(BATCH_ERRORS_LOG)` is called at module level (line 49: `logger = _get_batch_logger()`). In Windows spawn workers, this module is re-imported fresh, triggering the FileHandler setup in the worker's CWD, which may differ from the parent. The log file ends up in the worker's CWD (typically the process CWD inherited from Python) rather than alongside the main log. If that directory is read-only, the FileHandler silently fails — errors are lost.

**Fix:** Pass the log file as an absolute path:
```python
import os
_LOG_PATH = os.path.join(os.path.dirname(__file__), BATCH_ERRORS_LOG)
fh = logging.FileHandler(_LOG_PATH, encoding="utf-8")
```

---

### L-02: `existing_tables` is computed but never used in `_migrate_schema`

**File:** `db_utils.py:74–75`
**Issue:** `existing_tables` is populated on line 74 and then never referenced. All table existence checks use `CREATE TABLE IF NOT EXISTS` which makes the variable redundant. Dead code.

**Fix:** Remove lines 74–75:
```python
# delete:
existing_tables = {r[0] for r in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table'"
).fetchall()}
```

---

### L-03: `force_reprocess_demo` deletes engagement rows but does not handle `match_id` type mismatch

**File:** `db_utils.py:188–189`
**Issue:** `old_match_id` is retrieved from `processed_matches.match_id` which is `INTEGER`. The `engagements.match_id` and `duel_attempts.match_id` columns are `TEXT`. The DELETE uses `WHERE match_id=?` with `(old_match_id,)` — Python will pass an `int`. SQLite will coerce it to TEXT for comparison only if type affinity allows it, but since the column is TEXT, `match_id='7'` and `match_id=7` are different under `=` depending on the stored representation. If `save_to_db` stored `str(match_id)` and `force_reprocess_demo` deletes with `int(match_id)`, the DELETE silently matches zero rows.

**Fix:** Ensure consistent string casting in the DELETE:
```python
conn.execute("DELETE FROM engagements WHERE match_id=?", (str(old_match_id),))
conn.execute("DELETE FROM duel_attempts WHERE match_id=?", (str(old_match_id),))
```

---

_Reviewed: 2026-05-05_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
