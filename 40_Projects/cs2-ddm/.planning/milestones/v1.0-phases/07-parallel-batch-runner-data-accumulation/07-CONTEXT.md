# Phase 7: Parallel Batch Runner + Data Accumulation — Context

**Gathered:** 2026-05-04
**Status:** Ready for planning

<domain>
## Phase Boundary

Scale the analysis pipeline from 7 manually-curated demos to 100+ demos with automated parallel processing, idempotent SQLite storage, and a Streamlit Batch Analysis section. Delivers a queryable dataset in `analytics.db` where all moments are keyed by `player_steamid` and `demo_name`, enabling cross-player comparisons in Phase 8. One player processed per batch run. FACEIT API not needed — demos downloaded manually.

</domain>

<decisions>
## Implementation Decisions

### Demo Source and Discovery
- **D-01:** Demos sourced manually — no FACEIT API. User drops `.dem` files into `for_analysis/` directory (already exists).
- **D-02:** Batch runner scans `for_analysis/` for `.dem` files at run time. No file upload widget for batch (too slow for 600MB+ files).

### Streamlit Integration
- **D-03:** Batch processing is triggered from a new **Batch Analysis section in `app.py`** — not a separate CLI script. User enters SteamID64, sees files in `for_analysis/`, clicks Run Batch.
- **D-04:** Batch UI shows per-demo progress: `st.progress()` bar + live status text ("Processing demo 12/100: team-spirit-vs-mongolz-dust2..."). Workers run via ProcessPoolExecutor; Streamlit polls a shared status structure.
- **D-05:** Worker count is configurable via a Streamlit slider. Default = **8 workers** (matches i7-11800H 8 physical cores; 32GB RAM, ~300MB per demo process = safe headroom).

### Match ID and Demo Name
- **D-06:** `match_id` stays as integer (auto-increment from `MAX(match_id) + 1` in `analytics.db`). If DB is empty, start at 1.
- **D-07:** New column **`demo_name`** added to both `engagements` and `duel_attempts` tables — derived from demo filename without extension (e.g., `"team-spirit-vs-the-mongolz-de_dust2"`). Used as human-readable label in Streamlit dropdowns and result tables.

### Parallelization
- **D-08:** Use `ProcessPoolExecutor` (multiprocessing, not threading) — each demo analysis is CPU-bound (BVH raycasting). Each worker gets one `.dem` file.
- **D-09:** Error handling: log-and-continue. Failed demos logged to `batch_errors.log` with traceback. Batch completes even if individual demos fail. User sees error summary at end of run.

### Idempotency — Processed Matches Tracking
- **D-10:** New **`processed_matches`** table in `analytics.db` with columns: `demo_filename TEXT`, `player_steamid INTEGER`, `match_id INTEGER`, `processed_at TEXT`. Primary key on `(demo_filename, player_steamid)`.
- **D-11:** Before processing a demo, check if `(demo_filename, player_steamid)` exists in `processed_matches`. If found → skip. This prevents duplicate rows on re-runs.
- **D-12:** Re-process flag: a "Force reprocess" checkbox in Streamlit (or `--force` if CLI fallback is ever added). Force mode deletes the `processed_matches` record and all rows for that `match_id` before re-running.

### Dataset Strategy
- **D-13:** All batch results go into the **same `analytics.db`** as single-demo analysis. Queryable by `player_steamid`, `demo_name`, `match_id`. Enables Phase 8 cross-player benchmarks without joins across DBs.
- **D-14:** One player per batch run — multi-player batch is deferred to future (not roadmap).

### Claude's Discretion
- Implementation of the Streamlit polling mechanism (st.session_state with threading, or queue-based status updates) — standard Streamlit background task pattern.
- Exact `demo_name` parsing logic (strip `.dem` extension, normalize separators) — straightforward string manipulation.
- `batch_errors.log` format and location — follow existing `ddm_analysis.log` pattern in project root.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing pipeline entry points
- `run_analysis.py` — current sequential pipeline; batch runner replaces/extends this pattern
- `kill_rate_analysis.py` — PLAYERS dict + sequential loop; batch runner supersedes for multi-demo runs

### Schema and storage
- `db_utils.py` — existing SQLite dual-write; `processed_matches` table added here or in new `batch_utils.py`
- `config.py` — DB_PATH, constants; worker count default added here
- `.planning/phases/06-quality-gates-schema-migration/06-CONTEXT.md` — D-01 through D-10 locked decisions (SQLite dual-write, match_id idempotency pattern, player_steamid schema)

### Analysis core
- `ddm_analyzer.py` — DDMAnalyzer class called per demo in each worker process
- `duel_attempts.py` — DuelAttemptFinder called per demo

### Dashboard integration
- `app.py` — Streamlit app where Batch Analysis section is added

### Roadmap reference
- `.planning/ROADMAP.md` — Phase 7 success criteria (4 SCs)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `csv_utils.save_results()` — match_id replace-by-id dedup pattern; `processed_matches` check (D-10) mirrors this at the demo level.
- `db_utils.save_to_db()` — existing SQLite write; extend to also write to `processed_matches` on success.
- `run_analysis.py` sequential loop — direct template for the per-demo worker function body.

### Established Patterns
- `for_analysis/` directory already used as drop location for single-demo analysis in Streamlit.
- `DDMAnalyzer(demo_path, player_steamid, match_id=N, tickrate=64)` — existing constructor signature; batch worker calls this exactly.
- `logger.warning(...)` and `ddm_analysis.log` — existing logging pattern; `batch_errors.log` follows same setup.

### Integration Points
- `app.py` Streamlit: new "Batch Analysis" tab/section. Reads `for_analysis/`, shows file list, steamid input, worker slider, Run Batch button, progress display.
- `db_utils.py`: add `processed_matches` table creation to `init_db()` and a `mark_processed()` / `is_processed()` helper.
- `ProcessPoolExecutor` workers cannot share the SQLite connection — each worker writes to `analytics.db` independently (SQLite WAL mode handles concurrent writes).

</code_context>

<specifics>
## Specific Ideas

- Demo filename format from FACEIT: `"team-spirit-vs-the-mongolz-de_dust2"` — use as `demo_name` directly (strip `.dem`). No need to parse team names.
- Machine: i7-11800H (8 cores / 16 logical), 32GB RAM, RTX 3070 laptop, Windows 11. SQLite WAL mode required for parallel writer safety.
- User confirmed: demos downloaded manually — hundreds available. FACEIT API not needed for Phase 7.

</specifics>

<deferred>
## Deferred Ideas

- **Multi-player batch in one run** — process multiple players' demos in a single batch session. Deferred beyond Phase 9 (potential future if product has users). Not in roadmap.
- **FACEIT API integration** — auto-download demos via API. 30-day approval time; manual download sufficient for now.
- **CLI run_batch.py** — separate command-line batch script. Deferred; Streamlit UI covers the use case.

</deferred>

---

*Phase: 7 — Parallel Batch Runner + Data Accumulation*
*Context gathered: 2026-05-04*
