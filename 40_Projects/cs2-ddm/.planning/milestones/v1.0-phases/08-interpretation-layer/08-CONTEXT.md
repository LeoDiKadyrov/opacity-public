# Phase 8: Interpretation Layer — Context

**Gathered:** 2026-05-06
**Status:** Ready for planning

<domain>
## Phase Boundary

Build an Interpretation tab in app.py that converts raw pipeline metrics (crosshair angle, RT components, kill rate, hit rate) into actionable coaching output: tier rating vs a selectable benchmark player, plain-English meaning, gap, and one specific drill recommendation. Tier thresholds computed as percentiles from the benchmark player's distribution in analytics.db. Supports any player in analytics.db as benchmark (currently donk + karrigan). Works with any data volume; warns when sample is too small.

</domain>

<decisions>
## Implementation Decisions

### Report Location
- **D-01:** New **"Interpretation" tab** in `app.py` — 4th tab added alongside existing sections. Reads from `analytics.db` directly (not CSV). Clean separation from raw results.
- **D-02:** Tab layout: **summary card first** — "Your worst metric is X — do drill Y" at the very top (SC2), then the full 5-metric comparison table below. Punchline before data.
- **D-03:** Tab reads **sidebar SteamID64** as the player being analyzed. No separate player-selection input inside the tab.
- **D-04:** Tab renders with **any data volume**. If benchmark player has <20 demos, shows warning and falls back to hard-coded threshold estimates.

### Tier Thresholds
- **D-05:** Tiers computed as **percentiles from selected benchmark player's distribution** in `analytics.db`. Top 25% = Elite, 25–50% = Good, 50–75% = Average, bottom 25% = Work needed. Auto-updates as more demos are added.
- **D-06:** Tiers computed **separately per engagement_type** (peek vs hold). Donk peek distribution for peek tiers, hold distribution for hold tiers. Never conflates engagement types (SC3).
- **D-07:** Minimum **20 demos** for reliable percentiles. Below threshold → warning banner + fall back to hard-coded estimates.

### Drill Content
- **D-08:** Drills are **hard-coded text per metric × tier** in a new `interpretation.py` module — Python dict keyed by `(metric_name, tier, engagement_type)`. Single primary drill per cell.
- **D-09:** **5 metrics** have drills: `crosshair_angle_at_t0_deg`, `rt_visible_to_aim_ms`, `rt_aim_to_hit_ms`, `kill_rate`, `hit_rate` (bullets_hit/bullets_fired from Path 2). When `rt_visible_to_hit_ms` is the bottleneck, drill down to T0→T1 vs T1→T2 components (SC5).

### Benchmark Player
- **D-10:** **Benchmark dropdown** in the Interpretation tab header. Populated from `DISTINCT player_steamid` in `analytics.db`. Default = donk.
- **D-11:** Player display uses **`PLAYER_NAMES` dict in `config.py`** (`{steamid: 'donk', ...}`). Falls back to raw SteamID if not mapped. Easy to extend as new players are added.
- **D-12:** Players with <20 demos shown with **"(small sample)"** suffix in dropdown. Still selectable but triggers D-04 warning + fallback.

### Claude's Discretion
- Exact percentile breakpoints (e.g., 25/50/75 or 20/40/60/80) — standard quartile split unless distribution suggests otherwise.
- `interpretation.py` internal structure (class vs module-level dicts).
- Specific drill text per metric+tier — author based on CS2 coaching best practices.
- Hard-coded fallback threshold values per metric (to use when sample < 20 demos).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap and success criteria
- `.planning/ROADMAP.md` — Phase 8 success criteria (SC1–SC5, all 5 must be TRUE)

### Schema and storage
- `db_utils.py` — SQLite read/write; `analytics.db` schema (`engagements`, `duel_attempts`, `processed_matches` tables)
- `config.py` — DB_PATH, existing constants; PLAYER_NAMES dict added here
- `.planning/phases/07-parallel-batch-runner-data-accumulation/07-CONTEXT.md` — D-06/D-07/D-13 (demo_name, demo-level idempotency, all results in single analytics.db)

### Dashboard integration
- `app.py` — existing Streamlit app; Interpretation is a new tab here
- `visualize_results.py` — existing chart generation; interpretation tab may reuse some chart patterns

### Data paths
- `.planning/codebase/ARCHITECTURE.md` — two-path pipeline, CSV schemas for Path 1 + Path 2, key class methods
- `duel_attempts.py` — DuelAttempt dataclass; `hit_rate = bullets_hit / bullets_fired`

### Prior phase context
- `.planning/phases/06-quality-gates-schema-migration/06-CONTEXT.md` — D-09 (teammate gate, weapon_type split deferred to here), round_phase column exists in schema
- `.planning/STATE.md` — "Interpretation thresholds for crosshair angle tiers are estimates — validate against actual donk distribution"

### Memory
- `C:\Users\Leo\.claude\projects\D--Obsidian-opacity-40-Projects-cs2-ddm\memory\feedback_survivorship_bias_context.md` — survivorship bias caveat on RT metrics (SC4 requirement)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `analytics.db` — 83+ demos (donk 26 + karrigan 57) already queryable by `player_steamid`, `engagement_type`, `demo_name`.
- `db_utils.py:init_db()` — DB connection pattern; new read-only queries for interpretation follow same pattern.
- `app.py` existing tab structure — add 4th tab via `st.tabs(["Upload", "Results", "Batch", "Interpretation"])`.
- `config.py` — add `PLAYER_NAMES: dict[int, str]` dict here; no new file needed.

### Established Patterns
- `engagement_type` column already separates peek/hold in both `engagements` and `duel_attempts` tables.
- `player_steamid` is in both tables — WHERE clause for user's data is already the pattern.
- `visualize_results.py` box plots use peek/hold split — reuse the same grouping logic for tier computation.
- Hard-coded threshold constants already in `config.py` (T0_MIN_OFFSET_TICKS, ENEMY_VELOCITY_HOLD_THRESHOLD_UPS) — follow same convention for fallback tier thresholds.

### Integration Points
- New `interpretation.py` module — owns tier computation from analytics.db + drill lookup dict. Called by app.py Interpretation tab.
- `app.py` Interpretation tab → reads `analytics.db` via `db_utils` or direct sqlite3, calls `interpretation.py` to compute tiers, renders summary card + metrics table.
- `config.py` → add `PLAYER_NAMES` dict (used by Interpretation tab dropdown).
- Path 2 hit_rate: computed from `duel_attempts` table (`bullets_hit / bullets_fired`), grouped by `player_steamid` + `engagement_type`.

</code_context>

<specifics>
## Specific Ideas

- User wants benchmark player to be **selectable by name** (donk, flamez, karrigan, etc.) — not just by SteamID. PLAYER_NAMES dict in config.py handles this.
- User explicitly wants **multi-player comparison** (not hardcoded donk only). Phase 8 delivers this via dropdown from analytics.db.
- FACEIT-level cohort comparison ("average at your FACEIT level") — deferred to Phase 9+ (requires FACEIT API, out of scope here).
- Tab should work during Phase 8 development with the 83-demo dataset already in analytics.db.

</specifics>

<deferred>
## Deferred Ideas

- **Downloadable reports (PDF/HTML)** — Phase 9 scope (SC3: shareable via URL or exportable). Not in Phase 8.
- **Metric ↔ engagement outcome correlation** — show that crosshair_angle correlates with kill_rate, etc. New analytical capability; belongs in a future phase or backlog.
- **FACEIT-level cohort comparison** — "compare against average at your FACEIT level". Requires FACEIT API (30-day approval). Future phase.
- **Weapon type split in interpretation** (rifle vs pistol vs AWP) — mentioned in Phase 6 CONTEXT as deferred to Phase 8, but scope is already full. Consider Phase 9 if needed.
- **round_phase breakdown** — `round_phase` column exists in schema; interpretation by early/mid/late round. Deferred — insufficient data signal at current scale.

</deferred>

---

*Phase: 8 — Interpretation Layer*
*Context gathered: 2026-05-06*
