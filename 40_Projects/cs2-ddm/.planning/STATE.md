---
gsd_state_version: 1.0
milestone: outcome-first
milestone_name: Outcome-First Duel Reconstruction
status: executing
stopped_at: "Phase OF-3 context gathered — 4 gray areas resolved (T1 LANDS-semantics delegated with mandate, T0 backward no-clamp, two-layer gate with pre-run number approval, duel_episodes timing columns + staged rebatch). Next: /gsd-plan-phase OF-3. Branch `outcome-first` holds all OF work — merge to main only when «всё прям будет работать». B-5 still live in deprecated `ddm_analyzer._detect_t1`; new detector lands in outcome-first path per OF-3-CONTEXT D-04."
last_updated: "2026-06-11T04:04:37.000Z"
last_activity: 2026-06-11 -- OF-3-01 (TDD + schema + config foundation) executed
progress:
  total_phases: 7
  completed_phases: 1
  total_plans: 3
  completed_plans: 3
  percent: 100
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-30)

**Core value:** Not just metrics — specific insight: what exactly to change in training to be closer to donk
**Current focus:** Phase OF-3 — Re-validation + Metric + Measurability Gate

Prior: Phase 10 SHIPPED 2026-05-16 (B-1 floor + B-4 pre-aim fixes). Milestone v1.0 ARCHIVED. v2-interpretation-narrative DISCARDED 2026-05-14.

## Current Position

Phase: OF-3 (Re-validation + Metric + Measurability Gate) — EXECUTING
Plan: 2 of 4 (OF-3-01 complete)
Status: Executing Phase OF-3
Last activity: 2026-06-11 -- OF-3-01 (TDD + schema + config foundation) executed

Progress: [████████████████████] 96% (v0.x engine + v1.0 + Phase 10 complete; pending Phase A items not yet planned)

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

- Phase 10 inserted URGENT 2026-05-16 — T1 detection fix batch (B-1 grace floor + B-4 pre-aim censorship); 3 plans Waves 0/1/2; SHIPPED 2026-05-16 same day
- Phase v2-interpretation-narrative DISCARDED 2026-05-14 — pipeline lacks data scope (util/position/opponent intent) for class-level narrative coaching; survived: round_number column + CR-01 cluster-bleed fix
- Phase 9.1 inserted after Phase 9 (URGENT) — 2026-05-07 — perf optimizations (4 SC: AABB ordering, parse_events batching, selective parse_ticks, per-steamid cache); subsumes backlog 999.1

### Decisions

- [OF-3-01] TARGET_REACHED_THRESHOLD=3.0, T0_BACKWARD_SEARCH_CAP_TICKS=640, _T0_SEARCH_PARSE_WINDOW_TICKS=640 locked in config.py per D-02/D-05 rationale; A/B re-evaluation deferred to OF-3-02's N=1 staged run
- [OF-3-01] duel_episodes gains 7 timing columns (t0_tick, t0_source, t1_tick, t1_source, crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms) via idempotent `_episode_timing_migrations`; requires_db pytest marker registered (D-15)
- [OF-3-01] reaction_timing.py deliberately NOT created — tests/test_reaction_timing.py (7 tests) and the Tier-1 synthetic test in tests/test_distribution_shape.py are RED by design (Wave-0 TDD); GREEN implementation lands in OF-3-02
- [10-00] Wave 0 TDD-first: 5 RED tests staged BEFORE production code edit; frozen `grace_experiment_pre_fix.txt` baseline captured pre-edit for SC-5 parity diff
- [10-01] `T1_GRACE_MS = 0` keeps constant (not removed) — future re-experimentation = one-line config flip, not algorithm edit (defensive plumbing pattern)
- [10-01] `_detect_t1` returns `Tuple[int, str]` not `int`; `t1_source ∈ {"sustained_aim", "pre_aimed", "none"}` distinguishes branch labels for downstream consumers
- [10-01] Pre-aim gate `len(window) >= T1_SUSTAINED_AIM_TICKS + 1` (3 rows) — plan-as-written had off-by-one (used 2); inclusive range `[T0, T0+N]` covers N+1 ticks
- [10-01] DB column `t1_source TEXT DEFAULT NULL` added via idempotent `db_utils._eng_migrations`; legacy NULL = "sustained_aim under old grace=120" interpretively
- [10-02] SC-4 ran 5-pro subset of dust2 demo (RESEARCH Open Q6 permits); SC-5 ran full 13 pros for statistical robustness
- [10-02] Multi-pipeline init_db gap surfaced — `multi_player_analyze.py` did NOT call init_db; fixed in commit 32ce270 (+W-6 bound roster parse to 6400 ticks)
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

- Phase A item 6: full corpus re-batch (~20h via batch_runner.py) — BLOCKED on demo availability (only 1/83 demos on disk; rest were deleted post-analysis). Requires re-download from HLTV or FACEIT API ingest.
- Phase A item 7: re-derive `_FALLBACK_THRESHOLDS` + `_ABSOLUTE_ELITE_CEILING` in interpretation.py after clean re-batched data lands
- Phase A item 5: build `tests/test_distribution_shape.py` regression suite (gated via @requires_db)
- Phase A item 3: B-2 fix — DuelAttemptFinder missing is_alive gate
- Phase A item 4: B-3 fix — find_first_visible_enemy_in_window missing flash gate
- W-7 in `multi_player_analyze.py`: numeric coercion before int64 cast (small bundle)
- Landing banner: black-out warning on `djok-landing` while data refresh in progress (separate repo)
- B-2 (peek/hold strafe-hold mis-classification): deferred from 2026-05-14 data-layer fix batch
- `round_time_s` off-by-20s: round_freeze_end-based fix landed 2026-05-14 (commit 47cb085); spot-check after Phase A re-batch

### Blockers/Concerns

- **Phase A item 6 BLOCKED**: 82/83 corpus demos NOT on disk (deleted post-analysis). Engagement DB rows reference demo files that no longer exist locally. Cannot re-batch without re-downloading. Marketing claim refresh (donk 172ms, m0NESY 203ms) blocked downstream.
- **STATE.md gap-bridge**: Phase 10 inserted urgent outside milestone structure (v1.0 ARCHIVED, v1.1 not declared). `/gsd-new-milestone v1.1` needed to formalize Phase A items as planned phases.
- [Phase 7] FACEIT Downloads API has ~30-day approval response time — access granted 2026-05-15, grant email pending. Could unlock DEMO_READY webhook → automated demo ingest → solve Phase A demo-availability blocker
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

Last session: 2026-06-11 (OF-3-01 executed)
Stopped at: OF-3-01 complete — config constants (TARGET_REACHED_THRESHOLD/T0_BACKWARD_SEARCH_CAP_TICKS/_T0_SEARCH_PARSE_WINDOW_TICKS), duel_episodes 7-column timing migration, requires_db marker, and RED tests (tests/test_reaction_timing.py 7 tests + tests/test_distribution_shape.py Tier-1/Tier-2) all committed (9f8b174, ea2abd1, ca5a4b8). 366/366 pre-existing tests still GREEN; 2 new files RED-by-design (Wave-0 TDD). Next: OF-3-02 implements reaction_timing.compute_timing to turn RED -> GREEN.
Resume file: .planning/phases/OF-3-revalidation-measurability-gate/OF-3-02-PLAN.md
Note: donk corpus = for_analysis/spirit/, 86 demos on disk, 81 with donk events, 0 parse failures. pytest: `py -m pytest --override-ini="addopts=--strict-markers" -q` (`-p no:cov` broken on this machine).
