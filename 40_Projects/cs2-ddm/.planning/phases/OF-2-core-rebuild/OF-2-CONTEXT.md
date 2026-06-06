# Phase OF-2: Core Rebuild - Context

**Gathered:** 2026-06-05
**Status:** Ready for planning
**Source:** OF-1 gate GO (3/3 PASS) + user decisions (AskUserQuestion 2026-06-05) + milestone roadmap

<domain>
## Phase Boundary

OF-2 makes **outcome-first duel reconstruction the production duel path**. Episodes anchored on ground-truth `player_hurt`/`player_death` events (gunfire-anchored); opponent, outcome, and initiator come from events, never from BVH geometry guessing. Multi-player from day one. New `duel_episodes` table in analytics.db. Geometry-first opponent selector deleted.

**IN scope:**
- Productionize spike logic (`collect_exchanges` + `group_episodes` from `outcome_first_spike.py`, commit 17ec39a)
- Gun-only episode anchoring + unresolved-as-label semantics
- Multi-player API (all players in demo per run)
- New `duel_episodes` SQLite table (dual-write conventions per `db_utils.py`)
- Delete geometry opponent-selector path + its tests
- TDD: Wave-0 RED tests first (project convention)

**OUT of scope (deferred to OF-3):**
- Reaction timing (T0 backward search + redefined T1 «crosshair LANDS ≤3°», B-5 fix) — USER DECISION 2026-06-05
- Measurability/stability gate (CAVEAT-1 — mandatory before any marketing claim)
- Distribution-shape regression suite (`tests/test_distribution_shape.py`)
- Full corpus re-batch (OF-3 re-validation)

</domain>

<decisions>
## Implementation Decisions

### Episode anchoring (USER DECISION)
- **Gun-only anchor:** episode starts ONLY from gunfire `player_hurt` (HE/molotov/inferno/world damage does NOT anchor a new episode)
- **Unresolved stays as label:** unresolved episodes written to DB with explicit outcome label; filtered at metric level, never silently dropped
- Episode grouping: same-opponent events, gap > 320 ticks (`_KILL_CONFIRM_WINDOW_TICKS`) or opponent change → new episode (spike semantics)
- Outcome from death ordering: won (E died first) / lost (P died first) / unresolved
- Initiator: fire-based 128-tick lookback, fallback first-hit attacker (spike v1 semantics; refinement allowed, not required)

### Old path fate (USER DECISION)
- **Delete** geometry opponent-selector path (`DuelAttemptFinder._process_cluster` → `find_first_visible_enemy_in_window` as opponent selector) **+ tests pinning that behavior**
- **Keep** `t0_detector.find_t0(known_enemy)` and BVH — correct when enemy is KNOWN; OF-3 will use it for backward reaction search
- Audit EVERY consumer of deleted/changed methods (memory lesson: same-class bugs cross pipelines)

### Schema (USER DECISION)
- **New table `duel_episodes`** in analytics.db: ground-truth opponent steamid, outcome, initiator, anchor weapon class, episode tick bounds, match_id, player steamid
- Old `engagements` table untouched (history preserved, no migration)
- CSV schema (`cs2_engagement_analysis_results.csv`) untouched — stability rule holds

### Multi-player (USER DECISION 2026-06-05, pre-session)
- Multi-player **сразу**: pipeline processes all players in a demo per run, not single-player + loop

### Engineering constraints (LOCKED)
- TDD Wave-0 RED tests first, per project convention
- SteamID coercion: `_coerce_sid` string-path EVERYWHERE; never `pd.to_numeric` on sid columns with None (float64 precision loss — OF-1 found-bug); never `pd.read_sql` for sid columns
- Branch discipline: all work in `outcome-first` branch; merge to main only when «всё прям будет работать»
- Subprocess env: `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8` (cp1252 gotcha)
- Python launcher: `py`, not `python`

### Claude's Discretion
- Module layout (new module vs rework of `duel_attempts.py`)
- Exact `duel_episodes` column list beyond the locked ground-truth set
- Weapon-classification mechanism for gun-only anchor (weapon string from `player_hurt`)
- Whether utility damage WITHIN an established episode counts toward episode events (anchoring is what's locked, not in-episode accounting)
- Batch runner integration details

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone & gate
- `.planning/milestones/outcome-first-ROADMAP.md` — milestone goal, SC-2, caveats
- `.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md` — gate numbers, «What OF-2 must do», found-bug
- `.planning/phases/OF-1-outcome-first-validation-spike/OF-1-CONTEXT.md` — death diagnosis with exact code refs, outcome-first design, reuse map
- `.planning/phases/OF-1-outcome-first-validation-spike/OF-1-00-SUMMARY.md` — spike deviations

### Reference implementation
- `outcome_first_spike.py` (repo root, commit 17ec39a) — validated logic to productionize

### Production code touched
- `duel_attempts.py` — geometry selector to delete (`_process_cluster` L167, `find_attempts` L87)
- `t0_detector.py` — `find_first_visible_enemy_in_window` (L291) selector usage removed; `find_t0` KEPT
- `db_utils.py` — dual-write conventions for new table
- `config.py` — constants home (`_KILL_CONFIRM_WINDOW_TICKS` etc.)
- `batch_runner.py` — multi-player batch integration

</canonical_refs>

<specifics>
## Specific Ideas

- Spike cross-check pattern worth keeping in tests: per-demo won/lost must ≈ player kill/death volume (physics-bounded sanity column — memory lesson: every inspection table needs ≥1 physics-bounded column)
- Spike `--self-check` synthetic case (real 17-digit sids + None row) → port as pytest
- Demo corpus external: `D:\Obsidian\opacity\40_Projects\for_analysis\` (donk: spirit/, 81 demos verified)

</specifics>

<deferred>
## Deferred Ideas

- Reaction timing on KNOWN enemy (redefined T1 = crosshair lands ≤3°, B-5 fix) → OF-3
- Measurability/stability gate (CAVEAT-1) → OF-3
- `tests/test_distribution_shape.py` regression suite → OF-3
- Initiator refinement via visibility/positioning → OF-3 candidate

</deferred>

---

*Phase: OF-2-core-rebuild*
*Context gathered: 2026-06-05*
