# Architecture Research
_Generated: 2026-04-30_

## Summary

The current architecture (single-threaded Python CLI, two CSVs, Streamlit) is appropriate for 6 demos. At 100+ demos it breaks on three dimensions: runtime (BVH scan is CPU-bound and linear), storage (CSV lacks query capability), and ergonomics (no per-player identity in schema). Multi-player comparison requires adding a `player_id` foreign key to every output row — this is the one schema migration that must precede everything else. The recommended build order is: schema migration → parallel batch runner → interpretation layer → B2C delivery. Do not invert.

---

## Scale Patterns

### The bottleneck

BVH tree construction via awpy is the dominant cost per demo. The awpy docs confirm: "most of the time is spent creating the BVH tree." The `.tri` files are ~20 MB total across all maps. Key insight: **one `T0Detector` instance per map, reused across all demos on that map, eliminates repeated tree construction.** This is already partially exploited — `T0Detector` is constructed once per `DDMAnalyzer` instance. At scale, a map-keyed singleton cache of `T0Detector` instances across demos avoids rebuilding the same BVH N times.

### Parallelism strategy

For 100+ demos: `concurrent.futures.ProcessPoolExecutor` with one process per demo file. Each worker:
1. Receives a `(demo_path, player_steamid, match_id)` tuple
2. Constructs its own `DDMAnalyzer` and `T0Detector` (BVH per-process, can't share across processes without shared memory)
3. Returns a list of result dicts (serializable)

Pickling constraint: `demoparser2` and awpy `VisibilityChecker` objects are likely not picklable. **Do not pass them across process boundaries.** Instead, pass only primitive arguments to the worker function and construct all objects inside the worker. Top-level module functions only (no lambdas, no closures).

Recommended concurrency: `max_workers = os.cpu_count() - 1`. Each demo parse + BVH scan is memory-heavy (~500 MB per process for large maps). On a 16 GB machine, 4–6 workers is a safe ceiling.

### Incremental processing

Maintain a `processed_matches.txt` (or a `matches` table in SQLite) tracking which `match_id` values have been analyzed. Batch runner skips already-processed demos. This makes re-runs after crashes safe and free.

### Runtime estimate

Single-threaded: if one demo takes ~2 min to process (parse + BVH scan per moment), 100 demos = ~3.3 hours. With 4-way parallelism: ~50 minutes. With 6-way: ~33 minutes. Acceptable for overnight runs.

---

## Multi-Player Comparison Architecture

### The core problem with the current schema

Both CSVs have no `player_id` column. `match_id` identifies a game, not a player. Adding a second player's data to `cs2_engagement_analysis_results.csv` today would be ambiguous — you can't filter by player without knowing which match belongs to whom.

### Recommended schema addition (one migration, do it first)

Add `player_steamid` (int64) to every row in both output files. This is the only breaking schema change required before multi-player work begins. Update `csv_utils.save_results()` to accept and write `player_steamid`. Update `DDMAnalyzer.__init__` to take `player_steamid` as a parameter (already known — it's the target player being analyzed).

After this migration, multi-player comparison is a pandas groupby on `player_steamid`.

### Data model

**Single table, player-keyed** — not per-player files. The current per-player file approach (`donk_attempts.csv`, `friend_attempts.csv`) does not scale beyond 2 players and makes cross-player queries require manual DataFrame merging. Move to:

```
engagements table:
  player_steamid, match_id, map_name, engagement_type, 
  rt_visible_to_aim_ms, rt_aim_to_hit_ms, rt_visible_to_hit_ms,
  crosshair_angle_at_t0_deg, player_velocity_at_t0_ups, ...

duel_attempts table:
  player_steamid, match_id, map_name, was_killed, bullets_fired,
  bullets_hit, engagement_type, crosshair_angle_deg, ...
```

Players are identified by SteamID64 (already used as `enemy_steamid` internally). No new ID system needed.

### Comparison query pattern

```python
# Per-player median RT, grouped
df.groupby('player_steamid')['rt_visible_to_hit_ms'].median()

# Distribution comparison
for sid, group in df.groupby('player_steamid'):
    sns.kdeplot(group['rt_visible_to_hit_ms'], label=names[sid])
```

This is straightforward once `player_steamid` is in the schema. The current Streamlit dashboard needs a player-selector dropdown added.

### Survivorship bias caveat (already documented)

Cross-player RT comparisons must always note that donk's moments are high-difficulty engagements (pro play, fast enemies). This context belongs in the interpretation layer, not the data schema.

---

## Storage Layer Options

At 100 games, the dataset is small:
- ~30 moments per game × 100 games = ~3,000 RT rows
- ~50 duel attempts per game × 100 games = ~5,000 attempt rows

This is **not a big data problem**. The storage decision is about query ergonomics and multi-player correctness, not performance.

| Option | Fit for this project | Reason |
|-|-|-|
| CSV (current) | Poor at scale | No player_id FK, no query capability, append/dedup logic is fragile, human-merge required for multi-player |
| SQLite | Best fit | Single file, zero infra, native SQL for groupby/filter/join, pandas reads it natively (`pd.read_sql`), survives concurrent writes with WAL mode |
| Parquet | Overkill | Columnar compression only matters above ~100 MB; 5k rows is ~500 KB. Adds pyarrow dependency, no interactive query without DuckDB |
| PostgreSQL | Overkill | Requires server, migrations, connection pooling — for a solo Python CLI tool this is unnecessary |

**Recommendation: migrate to SQLite.** One `analytics.db` file replaces both CSVs. Schema:
- `engagements` table (Path 1 results)
- `duel_attempts` table (Path 2 results)
- `processed_matches` table (idempotency tracking)

Migration path: `csv_utils.save_results()` → `db_utils.save_results()` using `df.to_sql('engagements', conn, if_exists='append')`. The `match_id` + `player_steamid` composite unique constraint replaces the current CSV dedup logic.

Keep CSV export as an optional output for paper authoring (`pd.read_sql(...).to_csv(...)`).

---

## Build Order Recommendation

**Scale first, then interpret. Never the reverse.**

Rationale: interpretation rules (what counts as "good" crosshair angle, what RT delta is meaningful) require statistical distributions from N>30 players or N>100 games. Building interpretation with 6 games produces rules that will be invalidated when the dataset grows. Scaling first gives you the data to make interpretation defensible.

### Recommended sequence

**Step 1 — Schema migration (1 session)**
Add `player_steamid` to both output schemas. Migrate to SQLite. Update `csv_utils` → `db_utils`. This is the prerequisite for everything else.

**Step 2 — Phase 6 quality gate (already planned)**
T0 offset rejection and overlapping window fix. Do this before accumulating 100 games — otherwise bad data propagates into the full dataset and requires reprocessing everything.

**Step 3 — Parallel batch runner (1 session)**
`run_batch.py`: scans `for_analysis/`, skips processed match_ids, spawns `ProcessPoolExecutor` workers. Output: progress bar (tqdm), per-demo error log, final summary table.

**Step 4 — Accumulate donk dataset (ongoing)**
Download 100 FACEIT demos programmatically (see B2C section). Run batch. Validate distributions.

**Step 5 — Interpretation layer**
Only after Step 4 data exists. Percentile benchmarks ("your crosshair angle is 73rd percentile among donk's hold engagements"). Statistical comparisons (Mann-Whitney U for RT distributions, not t-test — RT is not normally distributed).

**Step 6 — Djok B2C delivery**
Only after interpretation layer is validated on real users.

Do not start Step 5 before Step 4 is complete. Do not start Step 6 before Step 5 is validated.

---

## B2C Delivery Architecture

### Demo acquisition: FACEIT API vs manual upload

**FACEIT Downloads API** provides signed URLs for demo files from match responses. Requires application approval (30-day response time). Once approved: given a player's SteamID or FACEIT nickname, you can enumerate their match history and fetch demo URLs programmatically. Python wrappers exist (`faceit` on PyPI). This is the correct long-term path for B2C — users connect their FACEIT account (OAuth or nickname), Djok fetches and processes their last N matches automatically.

**Manual upload** (current) is appropriate for early access validation only. Friction is too high for B2C at scale — CS2 demos are 1–3 GB each, users won't upload them manually.

**Recommendation for Djok early access:** Hybrid. Phase 1 B2C = user provides FACEIT match URLs or match IDs (copy-paste from FACEIT match room). Djok fetches demo via Downloads API (after approval). No file upload required. Phase 2 = full FACEIT OAuth, auto-pull last 20 matches.

### Processing architecture for B2C

The current Python CLI is not suitable for multi-user concurrent requests. At B2C scale (even 10 users/day), processing must be async and queued.

**Minimal viable B2C backend:**
- Job queue: Redis + RQ (Redis Queue) or Celery. One worker process per CPU core.
- Storage: SQLite is sufficient for hundreds of users. Switch to PostgreSQL only if concurrent writes become a bottleneck (unlikely until 1,000+ users/day).
- Results delivery: async email ("your analysis is ready") or polling endpoint. Processing one demo takes 2–10 minutes — users cannot wait synchronously.
- API layer: FastAPI (async, lightweight) — serves job submission and result retrieval endpoints. Streamlit dashboard becomes a client of this API.

**Deployment path:**
1. Wrap `run_analysis.py` logic into a callable function (remove `if __name__ == '__main__'` dependency)
2. Add FastAPI `/analyze` endpoint that enqueues a job
3. Add RQ worker that processes the queue
4. Deploy on a single VPS (4 vCPU, 16 GB RAM handles ~6 concurrent demo analyses)

**Do not build this until B2C early access proves demand.** The Djok landing + early access flow exists; validate payment and retention before investing in backend infra.

### Insight delivery format

Raw metrics (RT in ms, crosshair angle in degrees) are not the deliverable. The deliverable is a ranked list of actionable findings:

1. "Your crosshair angle at first visibility (avg 18°) is 3× higher than donk's in equivalent hold scenarios (avg 6°) → focus on pre-aim placement."
2. "Your T0→T1 delay (avg 210ms) matches donk's, but your T1→T2 (avg 180ms) is 2× longer → your aim execution, not reaction speed, is the gap."

This framing requires the interpretation layer (Step 5 above). Do not deliver raw CSVs to B2C users.

---

## Sources

- awpy visibility docs: https://awpy.readthedocs.io/en/latest/examples/visibility.html
- FACEIT Downloads API: https://docs.faceit.com/getting-started/Guides/download-api/
- FACEIT Data API: https://docs.faceit.com/docs/data-api/data/
- faceit Python library: https://pypi.org/project/faceit/
- Python ProcessPoolExecutor docs: https://docs.python.org/3/library/concurrent.futures.html
- SQLite vs Parquet comparison (DuckDB blog): https://duckdb.org/2024/12/05/csv-files-dethroning-parquet-or-not
