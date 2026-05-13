---
gsd_state_version: 1.0
milestone: v1.0
milestone_name: Djok MVP
status: executing
stopped_at: Phase v2-interpretation-narrative context gathered
last_updated: "2026-05-12T12:41:50.114Z"
last_activity: 2026-05-12 -- Phase v2-interpretation-narrative execution started
progress:
  total_phases: 6
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 95
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-30)

**Core value:** Not just metrics — specific insight: what exactly to change in training to be closer to donk
**Current focus:** Phase v2-interpretation-narrative — narrative

## Current Position

Phase: v2-interpretation-narrative (narrative) — EXECUTING
Plan: 1 of 7
Status: Executing Phase v2-interpretation-narrative
Last activity: 2026-05-12 -- Phase v2-interpretation-narrative execution started

Progress: [████████████████████] 95% (v0.x engine + Phases 6–8 + 09-01, 09-02, 09-03 complete)

## Performance Metrics

**Velocity:**

- Total plans completed: 0 (pre-GSD phases shipped outside GSD tracking)
- Average duration: unknown
- Total execution time: unknown

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 6–9 | TBD | - | - |

*Updated after each plan completion*

## Accumulated Context

### Roadmap Evolution

- Phase 9.1 inserted after Phase 9 (URGENT) — 2026-05-07 — perf optimizations (4 SC: AABB ordering, parse_events batching, selective parse_ticks, per-steamid cache); subsumes backlog 999.1

### Decisions

- [09-03] No st.cache_data on generate_html_report() call — deferred; MVP is fast enough, caching requires function-scope refactor out of phase scope
- [09-03] except Exception (broad catch) in download button block — operator-only local app; st.error() surfaces problem without traceback in UI
- [09-02] matplotlib.use("Agg") at module level — no GUI display, safe for Streamlit threads
- [09-02] _KNOWN_COLS frozenset whitelist for dynamic SQL column names (T-09-05 mitigation)
- [09-02] interp_rows_by_type passed to _generate_charts_html() — reuses computed data, avoids redundant DB query
- [09-01] Pure f-string templating in report_generator.py — no Jinja2 dependency needed for static HTML structure
- [09-01] cursor.fetchall() enforced in raw data query — pd.read_sql loses SteamID64 precision
- [v0.x] BVH+AABB only for T0 — m_bSpotted not populated in GOTV; FOV always fails for peeks
- [v0.x] T0-anchored kill rate (DuelAttemptFinder) — hit rate on player_hurt ignores misses
- [Phase 6] Schema migration BEFORE batch runner — retroactive migration across 100 games is painful
- [Phase 8] Build interpretation UI structure now with donk-reference framing; populate tier thresholds after 100-game dataset
- [06-01] Overlapping window gate via last_accepted_t2_tick state in analyze_demo() (D-07/D-08)
- [06-01] Teammate gate uses attacker != player_steamid heuristic; team_num refinement deferred to Phase 8 (D-09)
- [06-01] player_steamid added to analyze_engagement_episode() return dict as Path 1 schema column (D-05)
- [06-02] player_steamid added to DuelAttempt dataclass as Optional[int] = None (D-05 Path 2)
- [06-02] save_attempts() match_id required parameter, append+dedup by match_id; per-demo save inside run_player() loop (D-06)
- [07-01] engagements table created by _migrate_schema (CREATE TABLE IF NOT EXISTS) — enables test isolation with fresh DBs
- [07-01] busy_timeout=10000ms on all connections to handle parallel WAL lock contention
- [07-03] demo_name injected by DDMAnalyzer itself (not batch_runner UPDATE) — cleaner ownership; batch_runner UPDATE in 07-02 remains as fallback
- [07-05] SC4 counted player-agnostic (COUNT DISTINCT demo_filename across all players, not only donk) — 83 demos total (donk 26 + karrigan 57)

### Pending Todos

None yet.

### Blockers/Concerns

- [Phase 7] FACEIT Downloads API has ~30-day approval response time — research this before starting Phase 7; prepare manual bulk-download fallback
- [Phase 7] awpy installed with `--ignore-requires-python` (Python 3.14 not official) — monitor on any awpy or numpy update
- [Phase 8] Interpretation thresholds for crosshair angle tiers (< 10° / 10–25° / > 25°) are estimates — validate against actual donk distribution before publishing

## Deferred Items

| Category | Item | Status | Deferred At |
|---------|------|--------|------------|
| Scope | Per-map/position breakdown | Out of scope | PROJECT.md — needs more data first |
| Scope | Team analytics | Out of scope | PROJECT.md — separate product/tier |
| Scope | Real-time overlay | Out of scope | PROJECT.md — different architecture |
| Scope | Biometric correlation | Out of scope | PROJECT.md — distant horizon |
| v2 | Percentile rankings | Deferred | SUMMARY.md — meaningless without 500+ players |
| v2 | FACEIT OAuth auto-pull | Deferred | SUMMARY.md — manual input fine for early access |

## Session Continuity

Last session: 2026-05-12T11:11:56.502Z
Stopped at: Phase v2-interpretation-narrative context gathered
Resume file: .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
