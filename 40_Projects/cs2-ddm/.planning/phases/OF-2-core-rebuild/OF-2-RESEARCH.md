# Phase OF-2: Core Rebuild - Research

**Researched:** 2026-06-05
**Domain:** Python codebase — outcome-first duel reconstruction, SQLite schema, test conventions
**Confidence:** HIGH (all findings verified against source files in this session)

---

<user_constraints>
## User Constraints (from OF-2-CONTEXT.md)

### Locked Decisions
- Gun-only anchor: episode starts ONLY from gunfire `player_hurt`; HE/molotov/inferno/world damage does NOT anchor a new episode
- Unresolved stays as label: written to DB, filtered at metric level, never dropped
- Episode grouping: same-opponent events, gap > 320 ticks or opponent change → new episode
- Outcome from death ordering: won / lost / unresolved
- Initiator: fire-based 128-tick lookback, fallback first-hit attacker (spike v1 semantics)
- Delete geometry opponent-selector path (`_process_cluster` → `find_first_visible_enemy_in_window` as selector) + tests pinning that behavior
- Keep `t0_detector.find_t0(known_enemy)` and BVH — for OF-3 backward reaction search
- New table `duel_episodes` in analytics.db; old `engagements` table untouched; CSV schema untouched
- Multi-player from day one (all players in demo per run)
- TDD Wave-0 RED tests first
- `_coerce_sid` string-path EVERYWHERE; never `pd.to_numeric` on sid columns with None
- Branch: `outcome-first`; merge to main only when everything works
- Subprocess env: `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`
- Python launcher: `py`

### Claude's Discretion
- Module layout (new module vs rework of `duel_attempts.py`)
- Exact `duel_episodes` column list beyond the locked ground-truth set
- Weapon-classification mechanism for gun-only anchor
- Whether utility damage WITHIN an established episode counts toward episode events
- Batch runner integration details

### Deferred Ideas (OUT OF SCOPE)
- Reaction timing (T0 backward search + redefined T1 "crosshair LANDS ≤3°", B-5 fix) — OF-3
- Measurability/stability gate (CAVEAT-1) — OF-3
- Distribution-shape regression suite (`tests/test_distribution_shape.py`) — OF-3
- Full corpus re-batch — OF-3
</user_constraints>

---

## Summary

OF-2 productionizes `collect_exchanges` + `group_episodes` from `outcome_first_spike.py` (commit 17ec39a). The spike is self-contained and nearly production-ready; the main gaps are: (1) multi-player loop (spike takes a single `player_steamid`), (2) gun-only anchor filter (spike includes HE/molotov row in exchanges), (3) SQLite write via `db_utils.py` conventions (new `duel_episodes` table), (4) batch runner integration. The geometry-first path (`DuelAttemptFinder._process_cluster` → `find_first_visible_enemy_in_window`) lives entirely in `duel_attempts.py` with one caller in `ddm_analyzer.py`. Deleting it only breaks `ddm_analyzer.py:241-250` and the entire `tests/test_duel_attempts.py` + `tests/test_t0_detector_first_visible_window.py` (which pin the geometry selector). `kill_rate_analysis.py` imports `DuelAttempt` dataclass but not `DuelAttemptFinder` — must be audited for whether it can survive without the old path.

**Primary recommendation:** New module `outcome_first.py` (keep `duel_attempts.py` intact for `DuelAttempt` dataclass used by `kill_rate_analysis.py` and `test_kill_rate_analysis.py` and `test_db_utils.py`; gut only the geometry-selector methods). Add `duel_episodes` to `_ALLOWED_TABLES` whitelist in `db_utils.py` and `_migrate_schema`. Integrate multi-player via `group_by steamid` on a shared `parse_events` parse.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Duel episode reconstruction | `outcome_first.py` (new) | `ddm_analyzer.py` parse pipeline | Event grouping logic lives in new module; `ddm_analyzer` owns the parse pass |
| Multi-player iteration | `ddm_analyzer.py` / new `outcome_first.py` | `batch_runner.py` | parse once, iterate players |
| DB write for episodes | `db_utils.py` `save_to_db` + `init_db` | new `duel_episodes` table schema | follow existing dual-write conventions |
| Weapon classification | `outcome_first.py` helper / `config.py` | — | frozensets already exist in config |
| Old geometry-selector deletion | `duel_attempts.py` | `t0_detector.py` (keep find_t0) | only `_process_cluster` and its callers die |
| Test coverage | `tests/test_outcome_first.py` (new) | delete `test_duel_attempts.py` tests that pin selector | |

---

## 1. Consumer Map (CRITICAL)

### Who calls `DuelAttemptFinder` / geometry-selector methods

**`duel_attempts.py`** — defines everything. Methods being deleted:
- `DuelAttemptFinder._process_cluster` (L167) — calls `t0_detector.find_first_visible_enemy_in_window`
- `DuelAttemptFinder.find_attempts` (L87) — calls `_process_cluster` in a loop

**`ddm_analyzer.py`** (the ONLY production caller):
- L18: `from duel_attempts import DuelAttempt, DuelAttemptFinder`
- L241-250: instantiates `DuelAttemptFinder` and calls `finder.find_attempts(...)` [VERIFIED: ddm_analyzer.py:241]
- Breaking: this instantiation + call block must be replaced with the new `outcome_first` path

**`kill_rate_analysis.py`**:
- L19: `from duel_attempts import DuelAttempt` [VERIFIED: kill_rate_analysis.py:19]
- Does NOT import `DuelAttemptFinder`
- Does NOT call `find_attempts` or `_process_cluster`
- Uses `DuelAttempt` dataclass only for CSV → dataclass conversion
- Impact: `DuelAttempt` dataclass must be KEPT (or `kill_rate_analysis.py` updated)

**`batch_runner.py`**:
- No direct import of `DuelAttemptFinder` or `find_attempts` [VERIFIED: grep found none]
- Calls `analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)` at L105
- Reads `attempts` list returned by `analyze_demo` and saves via `_db.save_to_db(att_df, db_path, "duel_attempts", match_id)` [VERIFIED: batch_runner.py:126]
- Impact: batch_runner's `analyze_demo_worker` must also write `duel_episodes` via the new path; `"duel_attempts"` write may need to remain or be replaced

**`t0_detector.py`**:
- `find_first_visible_enemy_in_window` (L291) — called ONLY by `_process_cluster`; KEEP the method (it's also tested separately) but it becomes dead code after `_process_cluster` deletion. Safe to leave in place for OF-3 reuse; just not called from production path.
- `find_t0` — KEEP; OF-3 needs it

**No other production callers found** (`app.py`, `run_analysis.py`, `multi_player_analyze.py` do not import these symbols directly). [VERIFIED: grep across all .py]

### Mocks that break when signatures change

Pinning `find_first_visible_enemy_in_window` (must DELETE the tests, not just update):
- `tests/test_duel_attempts.py:180` — `det.find_first_visible_enemy_in_window.return_value = (t0_tick, enemy_sid, angle)` [VERIFIED]
- `tests/test_duel_attempts.py:186` — `det.find_first_visible_enemy_in_window.return_value = None` [VERIFIED]
- `tests/test_duel_attempts.py:282` — `det.find_first_visible_enemy_in_window.side_effect = [...]` [VERIFIED]
- `tests/test_t0_detector_first_visible_window.py:35,55,71` — calls `det.find_first_visible_enemy_in_window(...)` directly [VERIFIED]

Pinning `DuelAttemptFinder` (geometry-selector behavior tests — DELETE):
- `tests/test_duel_attempts.py:142-359` — entire `DuelAttemptFinder` test section [VERIFIED]

Pinning `DuelAttempt` dataclass (KEEP — used outside geometry path):
- `tests/test_db_utils.py:124` — `from duel_attempts import DuelAttempt` [VERIFIED]
- `tests/test_kill_rate_analysis.py:19,25,26` — `DuelAttempt` helper [VERIFIED]

`patch.object` mocks in other files — NOT affected by OF-2 changes:
- `tests/test_ddm_analyzer_core.py` — patches `_resolve_t0`, `_find_t2`, `_detect_t1`, `_classify_engagement`, etc. None patch `DuelAttemptFinder` [VERIFIED]
- `tests/test_ddm_analyzer_quality.py` — same pattern; no `DuelAttemptFinder` patches [VERIFIED]

---

## 2. db_utils.py Conventions

### Pattern for new `duel_episodes` table

**`_ALLOWED_TABLES` whitelist** (`db_utils.py:17`): currently `{"engagements", "duel_attempts"}`. Must add `"duel_episodes"`. [VERIFIED: db_utils.py:17]

**`save_to_db` contract** (`db_utils.py:20`):
- Takes `df: pd.DataFrame, db_path: str, table: str, match_id: Union[int, str]`
- DELETE-then-INSERT in explicit transaction (idempotent re-runs): `DELETE FROM {table} WHERE match_id = ?` then `df.to_sql(table, conn, if_exists="append", index=False)`
- Error: silently warns and returns (never raises to caller)

**`init_db` / `_migrate_schema`** (`db_utils.py:62-138`):
- WAL + `busy_timeout=10000` on init
- `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE ADD COLUMN IF NOT EXISTS` via PRAGMA check
- New `duel_episodes` table goes into `_migrate_schema` as a `CREATE TABLE IF NOT EXISTS` block

**`get_next_match_id`** (`db_utils.py:167`):
- `MAX(CAST(match_id AS INTEGER))` across `engagements` and `duel_attempts`
- Non-atomic (MAX+1 in main thread, workers get pre-assigned IDs from `batch_runner.pre_assign_match_ids`)
- Must include `duel_episodes` in the MAX scan (or it stays separate and we use a different ID allocation — planner decision)

**SteamID safe read** — `cursor.fetchall()` pattern:
```python
# CORRECT: never pd.read_sql for sid columns
rows = conn.execute("SELECT player_steamid, ... FROM duel_episodes WHERE ...").fetchall()
df = pd.DataFrame(rows, columns=["player_steamid", ...])
# CORRECT: store as INTEGER in schema; str-coerce on insert
```

**`match_id` storage**: stored as `TEXT` in engagements/duel_attempts (L199 `str(old_match_id)`). Follow same convention for `duel_episodes`.

### Proposed `duel_episodes` schema (minimal ground-truth columns + audit columns)

```sql
CREATE TABLE IF NOT EXISTS duel_episodes (
    match_id TEXT,
    demo_name TEXT DEFAULT NULL,
    player_steamid INTEGER,          -- int64 from _coerce_sid
    opponent_steamid INTEGER,        -- ground-truth from event, never BVH
    first_event_tick INTEGER,
    last_event_tick INTEGER,
    outcome TEXT,                    -- 'won' | 'lost' | 'unresolved'
    initiator TEXT,                  -- 'player' | 'opponent' | 'unknown'
    p_was_attacker_first INTEGER,    -- 0/1 boolean
    n_hits_p_on_e INTEGER DEFAULT 0,
    n_hits_e_on_p INTEGER DEFAULT 0,
    anchor_weapon TEXT DEFAULT NULL  -- weapon string of anchoring hit (gun-only)
)
```

Additional discretionary columns the planner may add: `map_name TEXT`, `round_number INTEGER`.

---

## 3. Spike → Production Gap

### Reusable as-is (copy-port directly)

| Spike function | Status | Notes |
|----------------|--------|-------|
| `_coerce_sid` | REUSE | Exactly what production needs; port to `outcome_first.py` |
| `_normalize_events` | REUSE | Handles None attacker rows (world damage drop) correctly |
| `collect_exchanges` | REUSE with gun-filter addition | Currently includes ALL hurt events; add weapon filter |
| `_episode_outcome` | REUSE | Ground-truth death-ordering logic |
| `_episode_initiator` | REUSE | Spike v1 semantics; fire-based lookback with fallback |
| `group_episodes` | REUSE | Gap-split logic correct; add demo_name + match_id params |
| `self_check` | PORT as pytest | Synthetic 3-episode test + None-corruption regression guard |

### Needs hardening

**Gun-only anchor filter** — `collect_exchanges` currently pulls ALL `player_hurt` events. Need to filter before grouping. The spike's `_normalize_events` is called on the full hurt_df. Add weapon filter at `collect_exchanges` call site or inside `_normalize_events`:

```python
# In collect_exchanges, before pd.concat:
if hurt_df is not None and "weapon" in hurt_df.columns:
    gun_weapons_excluded = KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES
    # Gun-only: KEEP rows that are NOT in the utility/world set
    UTILITY_WEAPON_NAMES = frozenset([
        "hegrenade", "weapon_hegrenade",
        "molotov", "weapon_molotov",
        "incgrenade", "weapon_incgrenade",
        "inferno",           # demoparser2 sometimes reports "inferno" for molotov damage
        "flashbang", "weapon_flashbang",
        "smokegrenade", "weapon_smokegrenade",
    ])
    hurt_df = hurt_df[
        ~hurt_df["weapon"].astype(str).str.lower().isin(UTILITY_WEAPON_NAMES)
    ]
# World damage is already dropped by _normalize_events (opponent==0 filter)
```

**Weapon column presence** — `player_hurt` from demoparser2 DOES carry a `weapon` column [VERIFIED: `ddm_analyzer.py:142` checks `if "weapon" in all_hurt_df.columns`]. The existing `auto_build_moments` already filters by `KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES`. For gun-only anchor, the new set must additionally exclude utility. "world" damage rows have `attacker_steamid` as None/0 and are already dropped by the `(events["opponent"] != 0)` filter in `collect_exchanges`.

**Multi-player loop** — spike takes a single `player_steamid`. Production path must process all players per demo in ONE `parse_events` call:

```python
# parse once per demo
hurt, death, fires = _parse_demo_events(demo_path)

# group all hurt events by player (both attacker and victim)
all_sids = set(hurt["attacker"].unique()) | set(hurt["victim"].unique())

for player_steamid in all_sids:
    events = collect_exchanges(hurt, death, player_steamid)
    eps = group_episodes(events, fires, player_steamid, demo)
    # write to db: save_to_db(...)
```

This means `_parse_demo_events` must be called once and the result passed to `collect_exchanges` per player — not re-parsed. The spike already does this cleanly (it returns DataFrames, not parsed per-player).

**Error handling** — spike has `except Exception` with skip+print. Production needs logging per project convention + `narrative_failures.log`-style failure tracking. Use `logging.getLogger`.

**match_id assignment** — spike has no match_id. Production must get `match_id` from `db_utils.get_next_match_id` (or from pre-assigned batch list) and pass it into the episode write.

---

## 4. Multi-Player Path

### Current iteration pattern

`batch_runner.analyze_demo_worker` (L74-151) takes `(demo_path, player_steamid, match_id, db_path, tickrate)` — **one player per worker call**. For multi-player, the batch driver calls the worker once per (demo, player) pair. [VERIFIED: batch_runner.py:245]

`BatchRunner.run` dispatches one future per (demo, player) pair. `pre_assign_match_ids` assigns match_ids in main thread. [VERIFIED: batch_runner.py:205-216]

### Cheapest multi-player-per-demo approach

**Option A (parse-once-per-demo driver)**: New `outcome_first.py` module exports `reconstruct_all_players(demo_path, player_sids, match_ids_by_sid, db_path)` — parses events ONCE, calls `collect_exchanges` per player, writes all. Batch runner calls this once per demo (not once per player).

**Implication for batch_runner.py**: `analyze_demo_worker` currently takes one `player_steamid`. For OF-2 episodes, the worker (or a new sibling worker) passes a list of sids + pre-assigned match_ids. The `processed_matches` skip-check would need to check per `(demo, player)` pairs.

**Option B (keep current one-player-per-worker)**: Each worker processes one player, re-parses the demo independently. Simpler to implement (no batch_runner changes), but ~10x parse overhead per demo for a 10-player roster. Acceptable for OF-2 since full corpus re-batch is OF-3 scope.

**Planner decision**: CONTEXT.md says "multi-player сразу" — this means the API must accept multiple players, but doesn't mandate parse-once optimization. Option B is correct for OF-2 (defers parse optimization to OF-3/9.x). The new `reconstruct_duels` function should accept `List[int]` of player steamids.

---

## 5. Test Conventions

### Existing test structure

- `tests/conftest.py` — `fake_parser` autouse fixture; supports `parse_events(list) → list[(name, df)]` shape [VERIFIED: conftest.py:55]
- All tests use synthetic DataFrames, no real demos
- `patch.object` for collaborator mocking; `MagicMock` for detector stubs
- Tests named by class `TestXxx` + method `test_xxx`; plain module-level functions also used

### Wave-0 RED TDD convention (from Phase 10 execution)

1. Write failing tests first (`pytest` must show RED)
2. Commit RED tests as Wave 0 plan
3. Implement until GREEN
4. The plan MUST include pytest acceptance criterion per edit

### Test files to DELETE (pin geometry-selector behavior)

| File | Why delete |
|------|-----------|
| `tests/test_duel_attempts.py` (L142-359) | `DuelAttemptFinder` + `find_attempts` + geometry-selector tests |
| `tests/test_t0_detector_first_visible_window.py` | Directly tests `find_first_visible_enemy_in_window` as selector |

**Preserve** from `test_duel_attempts.py`:
- L1-141: `DuelAttempt` dataclass field tests (L14-49) and `find_visible_enemies_*` tests at L51-80 (these test `T0Detector.find_visible_enemies_at_tick` which is NOT the geometry selector)

**Preserve entirely** (no delete):
- `tests/test_db_utils.py` — uses `DuelAttempt` but not `DuelAttemptFinder`
- `tests/test_kill_rate_analysis.py` — uses `DuelAttempt` only

### New test file: `tests/test_outcome_first.py`

Minimal required Wave-0 RED tests:
1. `test_collect_exchanges_gun_only` — HE/molotov rows do NOT anchor an episode
2. `test_collect_exchanges_world_damage_dropped` — None-attacker rows (world) dropped without corrupting 17-digit sids
3. `test_group_episodes_outcome_won_lost_unresolved` — port spike's `self_check` as pytest
4. `test_group_episodes_gap_split` — gap > 320 ticks → new episode
5. `test_group_episodes_opponent_change` → new episode
6. `test_multi_player_per_demo` — two players in same hurt_df → separate episode lists
7. `test_db_write_duel_episodes` — `save_to_db` with `"duel_episodes"` table (requires `_ALLOWED_TABLES` update)
8. `test_coerce_sid_none_preserves_17digit` — regression for float64 precision bug

---

## 6. Config Constants

### Existing constants that apply directly

| Constant | Value | Location | Use in OF-2 |
|----------|-------|----------|-------------|
| `_KILL_CONFIRM_WINDOW_TICKS` | 320 | config.py:78 | Episode gap threshold (same semantic) |
| `KNIFE_WEAPON_NAMES` | frozenset | config.py:35 | Exclude from gun-only anchor |
| `AWP_WEAPON_NAMES` | frozenset | config.py:45 | Exclude from gun-only anchor |
| `DB_PATH` | `"analytics.db"` | config.py:14 | DB path for new table |

### New constants needed for OF-2

| Constant | Suggested Value | Purpose |
|----------|----------------|---------|
| `_EPISODE_GAP_TICKS` | 320 | Alias/rename of `_KILL_CONFIRM_WINDOW_TICKS` for episode grouping semantics (or reuse the same constant with a comment) |
| `_INITIATOR_LOOKBACK_TICKS` | 128 | Lookback window for weapon_fire initiator attribution |
| `UTILITY_WEAPON_NAMES` | frozenset (HE/molotov/inferno/incgrenade/flashbang/smoke) | Gun-only anchor filter |

Note: `_KILL_CONFIRM_WINDOW_TICKS` can be reused as the episode gap (same 320-tick value, same conceptual "fight is over if 5s gap"); adding a separate `_EPISODE_GAP_TICKS = _KILL_CONFIRM_WINDOW_TICKS` alias with a comment is cleaner for readability but not required.

---

## Architecture Patterns

### Recommended Module Layout

```
outcome_first.py          # new — productionized spike logic + multi-player API
duel_attempts.py          # keep DuelAttempt dataclass + _cluster_fires util
                          # gut: DuelAttemptFinder._process_cluster, find_attempts
                          # (or move DuelAttempt to config.py and delete file later)
db_utils.py               # add duel_episodes to _ALLOWED_TABLES + _migrate_schema
config.py                 # add UTILITY_WEAPON_NAMES, _INITIATOR_LOOKBACK_TICKS
tests/test_outcome_first.py   # new Wave-0 RED tests
```

### Data flow (multi-player per demo)

```
demo_path
    |
    v
parse_events(["player_hurt","player_death","weapon_fire"])
    |
    +-- hurt_df (all players, gun-only after filter)
    +-- death_df (all players)
    +-- fires_df (all players)
    |
    for player_sid in roster_sids:
        collect_exchanges(hurt_df, death_df, player_sid)
            |
            v
        events_df  [opponent from event — ground truth]
            |
        group_episodes(events_df, fires_df, player_sid, demo, gap=320)
            |
            v
        List[dict]  episodes
            |
        pd.DataFrame + save_to_db("duel_episodes", match_id)
```

### Anti-Patterns to Avoid

- **Re-parsing per player**: call `_parse_demo_events` once per demo, loop players over result DataFrames
- **`pd.to_numeric` on sid columns**: use `_coerce_sid` exclusively
- **`pd.read_sql` for sid columns**: use `cursor.fetchall()` + manual dict construction
- **Stacking safety-margin filters on semantic filters**: don't add a grace-tick floor on top of the gap threshold (B-1 lesson)

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SteamID coercion | Custom int parse | `_coerce_sid` from spike | Float64 precision bug already solved |
| DB transaction safety | Manual commit/rollback | `db_utils.save_to_db` | DELETE+INSERT in `with conn:` block |
| Table existence | `CREATE TABLE IF NOT EXISTS` + `ALTER TABLE` | `_migrate_schema` pattern | Idempotent migration proven in prod |
| Weapon classification | Custom string matching | `KNIFE_WEAPON_NAMES`, `AWP_WEAPON_NAMES` frozensets | Already in config.py |
| Demo parsing | Direct `demoparser2` calls | Wrap as in spike's `_parse_demo_events` | Column name assumptions are fragile |

---

## Common Pitfalls

### Pitfall 1: Deleting `DuelAttemptFinder` breaks `DuelAttempt` consumers
**What goes wrong:** `kill_rate_analysis.py` and `test_db_utils.py` import `DuelAttempt` from `duel_attempts`. Deleting the module breaks them.
**Prevention:** Keep `DuelAttempt` dataclass in `duel_attempts.py` (or migrate it explicitly with import update). Do NOT delete the whole file.

### Pitfall 2: `_ALLOWED_TABLES` whitelist blocks new table write
**What goes wrong:** `save_to_db("duel_episodes", ...)` raises `ValueError: Unknown table 'duel_episodes'` — silent in prod (caught by except block) but data never written.
**Prevention:** Add `"duel_episodes"` to `_ALLOWED_TABLES` frozenset at `db_utils.py:17` BEFORE any write call. Include this as Wave-0 acceptance criterion.

### Pitfall 3: `get_next_match_id` doesn't scan `duel_episodes`
**What goes wrong:** Two concurrent writes (engagements pipeline vs episodes pipeline) can get the same match_id from `MAX+1` if only `engagements` and `duel_attempts` are scanned.
**Prevention:** Add `duel_episodes` to `get_next_match_id` scan [db_utils.py:172-180]. Or use pre-assigned match_ids from batch runner (already the pattern).

### Pitfall 4: HE/molotov damage produces fake episode anchors
**What goes wrong:** Utility chip damage from `player_hurt` where attacker is enemy creates an episode anchored on utility. Win-rate polluted by non-duel exchanges.
**Prevention:** Filter `hurt_df` to gunfire weapons BEFORE `collect_exchanges`. The `weapon` column is present on `player_hurt` in demoparser2 [VERIFIED: ddm_analyzer.py:142]. Specific strings: `hegrenade`, `weapon_hegrenade`, `molotov`, `weapon_molotov`, `incgrenade`, `weapon_incgrenade`, `inferno` (molotov damage ticks), `flashbang`, `weapon_flashbang`.

### Pitfall 5: `force_reprocess_demo` doesn't clear `duel_episodes`
**What goes wrong:** Re-running a demo with `force=True` deletes rows from `engagements` and `duel_attempts` but leaves stale `duel_episodes` rows (double-counts on re-batch).
**Prevention:** Add `DELETE FROM duel_episodes WHERE match_id=?` to `force_reprocess_demo` [db_utils.py:199-204].

### Pitfall 6: Signature change to `_normalize_events` misses downstream mocks
**What goes wrong:** If `_normalize_events` or `collect_exchanges` signature changes (e.g., add `weapon_filter` param), any test that mocks them by patching the module-level function breaks silently.
**Prevention:** After any signature change, grep `patch.*collect_exchanges` and `patch.*_normalize_events` across ALL test files.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest (no coverage by default) |
| Config file | none — `pytest.ini` or inline via `conftest.py` |
| Quick run command | `py -m pytest tests/test_outcome_first.py -p no:cov -x` |
| Full suite command | `py -m pytest -p no:cov` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Automated Command | File Exists? |
|-----|----------|-----------|-------------------|--------------|
| R-1 | Episodes anchored on gunfire only (no HE/molotov) | unit | `pytest tests/test_outcome_first.py::test_collect_exchanges_gun_only -x` | Wave 0 |
| R-2 | Opponent = steamid from event, never BVH | unit | `pytest tests/test_outcome_first.py::test_collect_exchanges_opponent_from_event -x` | Wave 0 |
| R-3 | Won/lost/unresolved outcomes correct | unit | `pytest tests/test_outcome_first.py::test_group_episodes_outcome_*` | Wave 0 |
| R-4 | None-attacker rows (world damage) dropped without float64 corruption | unit | `pytest tests/test_outcome_first.py::test_coerce_sid_none_preserves_17digit -x` | Wave 0 |
| R-5 | Multi-player: two players on same hurt_df → separate episode lists | unit | `pytest tests/test_outcome_first.py::test_multi_player_per_demo -x` | Wave 0 |
| R-6 | `duel_episodes` DB write via `save_to_db` | unit | `pytest tests/test_outcome_first.py::test_db_write_duel_episodes -x` | Wave 0 |
| R-7 | Old geometry-selector path removed | integration | `pytest tests/ -p no:cov -k "not duel_attempt_finder"` + `grep -r DuelAttemptFinder src/` | Wave 0 |
| R-8 | Parity with spike baseline (4168 donk episodes ± tolerance) | integration/manual | `py outcome_first_spike.py --gate --out outcome_first_spike_results.json` then `py -m outcome_first --player donk --compare-baseline` | post-implementation |

### Physics-Bounded Sanity Checks (per memory lesson: every inspection table needs ≥1 physics-bounded column)

Per-demo after implementation:
```sql
-- won ≈ player's kills on demo, lost ≈ player's deaths
SELECT
  demo_name,
  SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) AS won,
  SUM(CASE WHEN outcome='lost' THEN 1 ELSE 0 END) AS lost,
  COUNT(*) AS total_episodes,
  ROUND(100.0 * SUM(CASE WHEN outcome='won' THEN 1 ELSE 0 END) /
    NULLIF(SUM(CASE WHEN outcome IN ('won','lost') THEN 1 ELSE 0 END), 0), 1) AS win_pct
FROM duel_episodes
WHERE player_steamid = 76561198386265483
GROUP BY demo_name
ORDER BY demo_name;
```

Acceptance: `win_pct` between 40–70% (OF-1 gate band); `won` ≈ player kill count for spot-check demo (spirit-vs-vitality-m3-dust2: won=17, lost=16).

### Baseline Parity Check vs Spike

`outcome_first_spike_results.json` has 4168 donk episodes as baseline. After OF-2 ships:
- Run new production path on same 81 demos
- Compare totals: `n_episodes`, `won`, `lost`, `unresolved`
- Acceptable delta: ±5% due to gun-only filter (spike includes utility damage rows; production filters them → fewer episodes expected)
- Gate: `win_rate_resolved_pct` still in 40–70% band; holder/initiator separation still ≥5pp

### Wave 0 Gaps

- [ ] `tests/test_outcome_first.py` — all R-1 through R-7 tests (8 test functions minimum)
- [ ] Update `db_utils._ALLOWED_TABLES` to include `"duel_episodes"` (no test file gap — but prerequisite for R-6)
- [ ] Update `db_utils._migrate_schema` with `duel_episodes` DDL (prerequisite for R-6)
- [ ] `config.py` new constants: `UTILITY_WEAPON_NAMES`, `_INITIATOR_LOOKBACK_TICKS`

---

## Code Examples

### `_coerce_sid` (port directly from spike)

```python
# Source: outcome_first_spike.py:73-82
def _coerce_sid(series: pd.Series) -> pd.Series:
    """SteamID64 -> int64 WITHOUT a float64 intermediate."""
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")
```

### Gun-only filter (new, add to `collect_exchanges`)

```python
# Add to config.py:
UTILITY_WEAPON_NAMES: frozenset = frozenset([
    "hegrenade", "weapon_hegrenade",
    "molotov", "weapon_molotov",
    "incgrenade", "weapon_incgrenade",
    "inferno",
    "flashbang", "weapon_flashbang",
    "smokegrenade", "weapon_smokegrenade",
])

# In collect_exchanges, before _normalize_events:
if hurt_df is not None and not hurt_df.empty and "weapon" in hurt_df.columns:
    from config import UTILITY_WEAPON_NAMES
    hurt_df = hurt_df[
        ~hurt_df["weapon"].astype(str).str.lower().isin(UTILITY_WEAPON_NAMES)
    ]
```

### `save_to_db` for new table

```python
# db_utils.py — add to _ALLOWED_TABLES
_ALLOWED_TABLES = {"engagements", "duel_attempts", "duel_episodes"}

# db_utils._migrate_schema — add after duel_attempts block:
conn.execute("""
    CREATE TABLE IF NOT EXISTS duel_episodes (
        match_id TEXT,
        demo_name TEXT DEFAULT NULL,
        player_steamid INTEGER,
        opponent_steamid INTEGER,
        first_event_tick INTEGER,
        last_event_tick INTEGER,
        outcome TEXT,
        initiator TEXT,
        p_was_attacker_first INTEGER,
        n_hits_p_on_e INTEGER DEFAULT 0,
        n_hits_e_on_p INTEGER DEFAULT 0,
        anchor_weapon TEXT DEFAULT NULL
    )
""")
```

### Self-check ported as pytest (Wave-0 RED test skeleton)

```python
# tests/test_outcome_first.py
import pandas as pd
import pytest
from outcome_first import collect_exchanges, group_episodes, _coerce_sid

P, E1, E2 = 76561198386265483, 76561198113666193, 76561198081484775

def test_self_check_3_episodes():
    hurt = pd.DataFrame({
        "tick": [1000, 1050, 2000, 5000, 6000],
        "attacker_steamid": [str(P), str(E1), str(E2), str(P), None],
        "user_steamid": [str(E1), str(P), str(P), str(E1), str(P)],
        "weapon": ["ak47", "ak47", "ak47", "ak47", "world"],
    })
    death = pd.DataFrame({
        "tick": [1100, 2100],
        "attacker_steamid": [str(P), str(E2)],
        "user_steamid": [str(E1), str(P)],
    })
    fires = pd.DataFrame({"tick": [990, 1990], "shooter": [P, E2]})
    events = collect_exchanges(hurt, death, P)
    assert len(events) == 6
    eps = group_episodes(events, fires, P, demo="synthetic")
    assert len(eps) == 3
    assert eps[0]["outcome"] == "won"
    assert eps[1]["outcome"] == "lost"
    assert eps[2]["outcome"] == "unresolved"

def test_collect_exchanges_gun_only():
    """HE grenade row does NOT anchor an episode."""
    hurt = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": [str(E1)],
        "user_steamid": [str(P)],
        "weapon": ["hegrenade"],
    })
    death = pd.DataFrame(columns=["tick","attacker_steamid","user_steamid"])
    events = collect_exchanges(hurt, death, P)
    assert events.empty
```

---

## Open Questions (RESOLVED)

1. **`DuelAttempt` dataclass fate — RESOLVED (OF-2-02 Task 1)**
   - What we know: `kill_rate_analysis.py` and `test_db_utils.py` use it; `DuelAttemptFinder` is being deleted
   - Resolution: `DuelAttempt` dataclass KEPT in `duel_attempts.py` verbatim; only the `DuelAttemptFinder` class is deleted; file survives with deprecation note in module docstring

2. **`batch_runner` `attempts_mode` param after OF-2 — RESOLVED (OF-2-02 Task 2)**
   - What we know: `analyze_demo(bulk_mode=True, attempts_mode=True)` returns attempts (old path); batch_runner saves to `duel_attempts` table
   - Resolution: REPLACE, not augment — `attempts_mode` param deleted from `analyze_demo`; `duel_attempts` write blocks in batch_runner/multi_player_analyze replaced by `reconstruct_all_players` episode writes; `kill_rate_analysis.py` marked DEPRECATED (its data source was the removed geometry path); old `duel_attempts` table rows preserved as history, no new writes

3. **`weapon` column guaranteed on `player_hurt`? — RESOLVED (OF-2-01 Task 3)**
   - What we know: `ddm_analyzer.py:142` does a conditional check `if "weapon" in all_hurt_df.columns` (implies it may be absent)
   - Resolution: defensive check adopted (`if "weapon" in hurt_df.columns`) before gun-only filtering; if absent, all hurts treated as gunfire (conservative — more episodes, no silent drops); comment in collect_exchanges documents this

---

## Sources

### Primary (HIGH confidence — verified against source files this session)
- `duel_attempts.py` — DuelAttemptFinder full implementation, callers, consumer list
- `ddm_analyzer.py:18,241-250,142` — DuelAttemptFinder instantiation; weapon column check
- `db_utils.py:17,20-50,61-205` — full db conventions, _ALLOWED_TABLES, schema migration
- `outcome_first_spike.py:1-485` — complete spike implementation
- `batch_runner.py:54-260` — worker signature, multi-player pattern, analyze_demo call
- `config.py:1-158` — all relevant constants
- `tests/conftest.py` — fixture conventions
- `tests/test_duel_attempts.py:1-370` — mock patterns, DuelAttemptFinder tests to delete
- `tests/test_t0_detector_first_visible_window.py:35,55,71` — geometry-selector tests to delete
- `kill_rate_analysis.py:19,29` — DuelAttempt consumer (not DuelAttemptFinder)
- `tests/test_db_utils.py:124`, `tests/test_kill_rate_analysis.py:19,25` — DuelAttempt consumers

---

## Metadata

**Confidence breakdown:**
- Consumer map: HIGH — grep verified across all .py files
- db_utils conventions: HIGH — read full db_utils.py
- Spike gap analysis: HIGH — read full spike + compared against production patterns
- Weapon classification: MEDIUM — `player_hurt` weapon column conditional implies possible absence; exact utility weapon strings cross-checked against existing code patterns
- Multi-player path: HIGH — batch_runner worker signature verified

**Research date:** 2026-06-05
**Valid until:** 2026-07-05 (stable codebase; no external dependencies)
