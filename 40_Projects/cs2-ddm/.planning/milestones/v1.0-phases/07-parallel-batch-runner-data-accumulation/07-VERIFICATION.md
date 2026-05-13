---
phase: 07-parallel-batch-runner-data-accumulation
verified: 2026-05-06T00:00:00Z
status: human_needed
score: 11/12 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: human_needed
  previous_score: 11/12
  gaps_closed:
    - "H-01 path traversal guard added (app.py:469-472)"
    - "H-02 _BATCH_LOCK threading safety for _BATCH_SHARED (app.py:65,558,564,583)"
    - "H-03 demo_name UPDATE failure now logged as WARNING instead of swallowed (batch_runner.py:118)"
    - "L-02 dead variable existing_tables removed from db_utils.py"
    - "L-03 str(old_match_id) cast added in force_reprocess_demo (db_utils.py:185-186)"
  gaps_remaining: []
  regressions: []
human_verification:
  - test: "streamlit run app.py → Section 5 → place 1 .dem in for_analysis/ → enter SteamID 76561198386265483 → Run Batch"
    expected: "Progress bar updates live (~0.5s interval), UI not frozen, after completion shows summary OK/Failed count"
    why_human: "st.rerun() polling and threading.Thread behavior cannot be verified without a live Streamlit server"
---

# Phase 7: Parallel Batch Runner Verification Report

**Phase Goal:** Parallel batch runner that processes 80+ demos, writes to analytics.db with WAL mode, idempotent re-runs, Streamlit UI for batch execution.
**Verified:** 2026-05-06
**Status:** human_needed
**Re-verification:** Yes — after review fixes from commit 8088704

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|-|-|-|-|
| 1 | analytics.db uses WAL after init_db() | VERIFIED | Live query: `PRAGMA journal_mode` → `wal` |
| 2 | processed_matches exists with PK (demo_filename, player_steamid) | VERIFIED | db_utils.py lines 121-128; 83 rows in prod DB |
| 3 | duel_attempts table exists | VERIFIED | Live query: table present, 6432 rows |
| 4 | demo_name and player_steamid columns in engagements | VERIFIED | `PRAGMA table_info(engagements)` confirms both |
| 5 | is_processed / mark_processed work correctly | VERIFIED | 22 tests in test_db_utils.py, all green |
| 6 | get_next_match_id takes MAX across both tables | VERIFIED | db_utils.py lines 162-170; test_get_next_match_id_uses_both_tables |
| 7 | DEFAULT_BATCH_WORKERS = 8 in config.py | VERIFIED | Import confirmed: 8 |
| 8 | analyze_demo_worker is top-level and picklable | VERIFIED | pickle.dumps(analyze_demo_worker) OK |
| 9 | Worker returns dict with status/traceback on error | VERIFIED | Error path returns status=error with traceback |
| 10 | BatchRunner.run() pre-assigns match_ids, uses ProcessPoolExecutor | VERIFIED | batch_runner.py lines 240-256 |
| 11 | Streamlit Batch Analysis section exists with correct patterns | VERIFIED | _BATCH_LOCK, threading.Thread, st.progress, force_reprocess all present |
| 12 | UI does not freeze (st.rerun() polling) | UNCERTAIN | Requires live Streamlit server |

**Score:** 11/12

### Deferred Items

SC4 (≥80 demos): PASS — 83 distinct demos in processed_matches (donk 26 + karrigan 57).

### Required Artifacts

| Artifact | Status | Details |
|-|-|-|
| `db_utils.py` | VERIFIED | init_db, _migrate_schema, is_processed, mark_processed, get_next_match_id, force_reprocess_demo — all 6 functions present |
| `config.py` | VERIFIED | DEFAULT_BATCH_WORKERS=8, BATCH_INPUT_DIR, BATCH_ERRORS_LOG |
| `batch_runner.py` | VERIFIED | analyze_demo_worker (top-level), BatchRunner class with all methods |
| `app.py` | VERIFIED | Section 5 Batch Analysis, _BATCH_LOCK threading safety, all patterns present |
| `ddm_analyzer.py` | VERIFIED | `demo_name: str = ""` param, self.demo_name attribute |
| `tests/test_db_utils.py` | VERIFIED | test_wal_concurrent_writes, test_processed_matches_idempotency and others |
| `tests/test_batch_runner.py` | VERIFIED | test_worker_is_picklable, test_filter_unprocessed_skips_processed, test_pre_assign_sequential |

### Key Link Verification

| From | To | Via | Status |
|-|-|-|-|
| db_utils.init_db() | analytics.db | PRAGMA journal_mode=WAL | WIRED |
| db_utils.mark_processed() | processed_matches | INSERT OR REPLACE | WIRED |
| BatchRunner.run() | analyze_demo_worker | ProcessPoolExecutor.submit() | WIRED |
| analyze_demo_worker | db_utils.mark_processed() | after analyze_demo() | WIRED |
| Run Batch button | threading.Thread(_run_batch_thread) | batch_running session state | WIRED |
| _BATCH_SHARED compound ops | _BATCH_LOCK | with _BATCH_LOCK context manager | WIRED (H-02 fixed) |
| DDMAnalyzer.__init__ | self.demo_name | Path(demo_path).stem fallback | WIRED |

### Behavioral Spot-Checks

| Behavior | Result | Status |
|-|-|-|
| analytics.db WAL mode | journal_mode = wal | PASS |
| processed_matches count | 83 distinct demos | PASS |
| 289 tests | 0 failures, 4.19s | PASS |
| analyze_demo_worker picklable | pickle.dumps OK | PASS |
| DEFAULT_BATCH_WORKERS import | 8 | PASS |

### Requirements Coverage

| Requirement | Status |
|-|-|
| SC1: batch without manual intervention | SATISFIED — BatchRunner.run() automates full pipeline |
| SC2: idempotency (no duplicates) | SATISFIED — test_processed_matches_idempotency |
| SC3: WAL concurrent writes | SATISFIED — test_wal_concurrent_writes + multiprocess |
| SC4: ≥80 demos | SATISFIED — 83 distinct demos in prod DB |

### Anti-Patterns Resolved (from 07-REVIEW.md)

| Issue | Severity | Fix Status |
|-|-|-|
| H-01: path traversal via subfolder selection | HIGH | FIXED — is_relative_to guard in app.py:469-472 |
| H-02: _BATCH_SHARED compound read-modify-write not thread-safe | HIGH | FIXED — _BATCH_LOCK added, all access under lock |
| H-03: silent demo_name UPDATE failure marks demo processed anyway | HIGH | FIXED — WARNING log instead of swallow |
| M-01: BATCH_INPUT_DIR relative path "../for_analysis" | MEDIUM | NOT FIXED — still "../for_analysis" in config.py |
| M-02: get_next_match_id TOCTOU window | MEDIUM | NOT FIXED — no BEGIN IMMEDIATE |
| M-03: ALTER TABLE inside transaction on older SQLite | MEDIUM | NOT FIXED |
| M-04: orphaned match_id in error dict | MEDIUM | NOT FIXED |
| M-05: time.sleep(0.5) blocks event loop | MEDIUM | NOT FIXED |
| L-01: FileHandler relative path in workers | LOW | NOT FIXED |
| L-02: dead variable existing_tables | LOW | FIXED — removed |
| L-03: int vs str match_id in force_reprocess DELETE | LOW | FIXED — str() cast added |

Note: M-01 through M-05 and L-01 are not blockers for the phase goal. They are quality issues for a future cleanup pass.

### Human Verification Required

**1. Streamlit Batch UI live test**

**Test:** `streamlit run app.py` → Section 5 → place 1 .dem in for_analysis/ → enter SteamID 76561198386265483 → Run Batch
**Expected:** Progress bar updates every ~0.5s without UI freeze, after completion shows "Batch complete: N/N demos OK" summary
**Why human:** st.rerun() polling and threading.Thread live behavior cannot be verified programmatically without a running Streamlit server

---

_Verified: 2026-05-06T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
