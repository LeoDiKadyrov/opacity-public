---
phase: OF-2
plan: 01
type: execute
wave: 1
depends_on: [OF-2-00]
milestone: outcome-first
autonomous: true
files_modified:
  - config.py            # +UTILITY_WEAPON_NAMES, +_INITIATOR_LOOKBACK_TICKS
  - db_utils.py          # quad-touch: _ALLOWED_TABLES, _migrate_schema, get_next_match_id, force_reprocess_demo
  - outcome_first.py     # NEW — production module (spike port + gun-only + multi-player + DB write + CLI)
requirements: [R-1, R-2, R-3, R-4, R-5, R-6]
branch: outcome-first

must_haves:
  truths:
    - "outcome_first.py exists; opponent identity derives ONLY from player_hurt/player_death events, never BVH"
    - "Gun-only anchor: utility/world rows never start an episode; unresolved episodes are written with explicit label"
    - "Multi-player: one parse per demo, per-player reconstruction loop, per-player DB write"
    - "All 9 Wave-0 tests GREEN; full suite GREEN"
  artifacts:
    - path: "outcome_first.py"
      provides: "Production outcome-first duel reconstructor"
      contains: "reconstruct_all_players"
    - path: "db_utils.py"
      provides: "duel_episodes table support"
      contains: "duel_episodes"
---

<objective>
GREEN: productionize the spike. Port validated logic from outcome_first_spike.py into outcome_first.py, add gun-only anchor filter, multi-player API, and duel_episodes persistence following db_utils conventions. All Wave-0 tests pass.
</objective>

<threat_model>
- T-OF2-01 (medium): SQL injection via table-name interpolation in save_to_db — MITIGATED by extending the existing `_ALLOWED_TABLES` whitelist (CR-01 pattern); table names never come from user input.
- T-OF2-02 (low): match_id collision between concurrent pipelines if get_next_match_id doesn't scan duel_episodes — MITIGATED in Task 2 (add scan).
No network, no untrusted input — local analysis tool.
</threat_model>

<context>
@.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md
@.planning/phases/OF-2-core-rebuild/OF-2-RESEARCH.md  (§2 db conventions, §3 spike gap, §6 constants)
@.planning/phases/OF-2-core-rebuild/OF-2-PATTERNS.md  (полные code excerpts для каждого файла)
@outcome_first_spike.py
</context>

<tasks>

<task type="auto">
  <name>Task 1: config.py — new constants</name>
  <files>config.py</files>
  <read_first>
    - config.py L30-80 (frozenset style KNIFE_WEAPON_NAMES/AWP_WEAPON_NAMES; _KILL_CONFIRM_WINDOW_TICKS at L78)
  </read_first>
  <action>
    Add after the AWP_WEAPON_NAMES block:

    ```python
    # OF-2: weapon categories excluded from gun-only episode anchoring.
    # Utility damage (HE/molotov/inferno tick-damage/flash/smoke) does NOT start
    # a duel episode. "inferno" = demoparser2 weapon string for molotov burn ticks.
    UTILITY_WEAPON_NAMES: frozenset = frozenset([
        "hegrenade", "weapon_hegrenade",
        "molotov", "weapon_molotov",
        "incgrenade", "weapon_incgrenade",
        "inferno",
        "flashbang", "weapon_flashbang",
        "smokegrenade", "weapon_smokegrenade",
    ])

    # OF-2: lookback window (ticks) for weapon_fire initiator attribution
    # in outcome_first.py. 128 ticks = 2s @ 64 Hz. Matches OF-1 spike semantics.
    _INITIATOR_LOOKBACK_TICKS: int = 128
    ```

    Do NOT alias _KILL_CONFIRM_WINDOW_TICKS — reuse it directly as the episode gap with a comment at the use site in outcome_first.py.
  </action>
  <verify>
    <automated>py -c "from config import UTILITY_WEAPON_NAMES, _INITIATOR_LOOKBACK_TICKS; assert 'inferno' in UTILITY_WEAPON_NAMES and _INITIATOR_LOOKBACK_TICKS == 128"</automated>
  </verify>
  <acceptance_criteria>
    - config.py contains `UTILITY_WEAPON_NAMES: frozenset` with all 10 strings above
    - config.py contains `_INITIATOR_LOOKBACK_TICKS: int = 128`
  </acceptance_criteria>
  <commit>feat(OF-2): config constants for gun-only anchor + initiator lookback</commit>
</task>

<task type="auto">
  <name>Task 2: db_utils.py — quad-touch for duel_episodes</name>
  <files>db_utils.py</files>
  <read_first>
    - db_utils.py (полностью — 206 строк; все 4 точки касания)
  </read_first>
  <action>
    Four additive edits, each follows the existing duel_attempts pattern:

    EDIT 2.1 — whitelist (db_utils.py:17):
    REPLACE:
    ```python
    _ALLOWED_TABLES = {"engagements", "duel_attempts"}
    ```
    WITH:
    ```python
    _ALLOWED_TABLES = {"engagements", "duel_attempts", "duel_episodes"}
    ```

    EDIT 2.2 — `_migrate_schema`: add AFTER the duel_attempts CREATE block (after L127), BEFORE processed_matches:
    ```python
    # duel_episodes: OF-2 outcome-first ground-truth duels (opponent/outcome
    # from player_hurt/player_death events, never BVH-guessed)
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

    EDIT 2.3 — `get_next_match_id` (L167-180):
    REPLACE:
    ```python
        r2 = conn.execute(
            "SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_attempts"
        ).fetchone()[0] if _table_exists(conn, "duel_attempts") else None
        current_max = max(r1 or 0, r2 or 0)
    ```
    WITH:
    ```python
        r2 = conn.execute(
            "SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_attempts"
        ).fetchone()[0] if _table_exists(conn, "duel_attempts") else None
        r3 = conn.execute(
            "SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_episodes"
        ).fetchone()[0] if _table_exists(conn, "duel_episodes") else None
        current_max = max(r1 or 0, r2 or 0, r3 or 0)
    ```
    Also update the docstring line "across engagements and duel_attempts tables" → "across engagements, duel_attempts, and duel_episodes tables".

    EDIT 2.4 — `force_reprocess_demo` (after L200):
    REPLACE:
    ```python
            conn.execute("DELETE FROM duel_attempts WHERE match_id=?", (str(old_match_id),))
    ```
    WITH:
    ```python
            conn.execute("DELETE FROM duel_attempts WHERE match_id=?", (str(old_match_id),))
            if _table_exists(conn, "duel_episodes"):
                conn.execute("DELETE FROM duel_episodes WHERE match_id=?", (str(old_match_id),))
    ```
    (The `_table_exists` guard protects DBs created before this migration runs.)
  </action>
  <verify>
    <automated>py -m pytest tests/test_outcome_first.py::test_db_write_duel_episodes -p no:cov exits 0</automated>
    <automated>py -m pytest tests/test_db_utils.py -p no:cov exits 0</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c duel_episodes db_utils.py` >= 5
    - test_db_write_duel_episodes GREEN
    - existing test_db_utils.py suite GREEN
  </acceptance_criteria>
  <commit>feat(OF-2): duel_episodes table — whitelist, DDL, match_id scan, force-reprocess cleanup</commit>
</task>

<task type="auto">
  <name>Task 3: outcome_first.py — production module</name>
  <files>outcome_first.py</files>
  <read_first>
    - outcome_first_spike.py (полностью — source of truth для портируемой логики)
    - OF-2-PATTERNS.md §outcome_first.py (готовые excerpts: imports, reconstruct_all_players)
    - db_utils.py L20-49 (save_to_db contract)
  </read_first>
  <action>
    Create outcome_first.py. Structure:

    1. Module docstring: production outcome-first duel reconstruction; opponent/outcome from events only; gun-only anchoring; supersedes the geometry-first DuelAttemptFinder path (OF-2).

    2. UTF-8 env guard (port from spike L42-45 verbatim).

    3. Imports per PATTERNS.md: `from config import _KILL_CONFIRM_WINDOW_TICKS, _INITIATOR_LOOKBACK_TICKS, UTILITY_WEAPON_NAMES, DB_PATH`; `from db_utils import save_to_db, init_db`; `logger = logging.getLogger(__name__)`.

    4. PORT VERBATIM from spike (keep docstrings, keep float64-bug comment):
       - `_coerce_sid` (spike L73-82)
       - `_normalize_events` (L85-99) — ADD `weapon` passthrough: include column `"weapon": df["weapon"].astype(str).str.lower() if "weapon" in df.columns else ""` in the output frame for hurt events (death events get empty string). Needed for anchor_weapon.
       - `_episode_outcome` (L129-141)
       - `_episode_initiator` (L144-167) — replace module constant with `_INITIATOR_LOOKBACK_TICKS` from config
       - `_parse_demo_events` (L212-234)

    5. `collect_exchanges(hurt_df, death_df, player_steamid)` — port spike L102-126, ADD gun-only filter BEFORE `pd.concat`:
       ```python
       # Gun-only anchor (OF-2 decision): utility damage never starts/joins
       # an episode's event stream. Defensive: if weapon column absent,
       # treat all hurts as gunfire (conservative — no silent episode drops).
       if hurt_df is not None and not hurt_df.empty and "weapon" in hurt_df.columns:
           hurt_df = hurt_df[
               ~hurt_df["weapon"].astype(str).str.lower().isin(UTILITY_WEAPON_NAMES)
           ]
       ```

    6. `group_episodes(events, fires, player_steamid, demo, match_id="", gap_ticks=_KILL_CONFIRM_WINDOW_TICKS)` — port spike L170-209 with these changes:
       - episode dict keys renamed to DB schema: `demo_name` (not `demo`), `n_hits_p_on_e` / `n_hits_e_on_p` (lowercase, match DDL), add `match_id: str(match_id)`, add `opponent_steamid` (rename from `opponent`), add `anchor_weapon`: weapon string of the FIRST hurt event in the episode (empty string if episode anchored by a death event).
       - keep `p_was_attacker_first` as int(bool) for SQLite.
       - comment at gap param: `# _KILL_CONFIRM_WINDOW_TICKS=320 ≈ 5s @ 64-tick, reused as episode gap (same semantic: fight over after 5s silence)`.

    7. NEW public API:
       ```python
       def reconstruct_all_players(
           demo_path: str,
           player_sids: List[int],
           match_ids_by_sid: Dict[int, Union[int, str]],
           db_path: str = DB_PATH,
       ) -> Dict[int, int]:
           """Parse demo ONCE, reconstruct episodes per player, write each
           player's episodes to duel_episodes. Returns {sid: n_episodes}.
           Never raises from the per-player loop (logger.exception + continue).
           """
       ```
       Implementation per PATTERNS.md excerpt: one `_parse_demo_events` call; loop players; `collect_exchanges` → `group_episodes` → `pd.DataFrame(eps)` → add `player_steamid` column → `save_to_db(df, db_path, "duel_episodes", match_ids_by_sid[sid])`. demo_name = `os.path.splitext(os.path.basename(demo_path))[0]`.

    8. `discover_player_sids(hurt_df) -> List[int]` helper: all distinct non-zero sids from attacker+victim columns via `_coerce_sid` (enables "all players in demo" mode when roster unknown).

    9. CLI `main()`: args `--demos <root>`, `--player <sid>` (optional; default = all players per demo), `--db <path>` (default DB_PATH), `--compare-baseline <json>` (optional: load spike json, print n_episodes/won/lost/unresolved deltas in % vs production run for the given player). Use `find_demos` port from spike L409-415. Call `init_db(db_path)` once before processing. Allocate match_ids via `db_utils.get_next_match_id` + increment per (demo, player).

    Type hints strict (List, Dict, Optional, Tuple, Union). No magic numbers — constants from config only.
  </action>
  <verify>
    <automated>py -m pytest tests/test_outcome_first.py -p no:cov exits 0 (all 9 GREEN)</automated>
    <automated>py -m pytest -p no:cov exits 0 (full suite GREEN)</automated>
    <automated>py -c "from outcome_first import reconstruct_all_players, discover_player_sids, collect_exchanges, group_episodes, _coerce_sid"</automated>
  </verify>
  <acceptance_criteria>
    - outcome_first.py contains `def reconstruct_all_players(` and `def discover_player_sids(`
    - `grep -c "pd.to_numeric" outcome_first.py` == 1 (только tick coercion в _normalize_events/_parse_demo_events; НЕ на sid колонках — verify by reading those lines)
    - `grep "DuelAttemptFinder\|find_first_visible_enemy" outcome_first.py` returns 0 hits
    - All 9 Wave-0 tests GREEN; full suite GREEN
  </acceptance_criteria>
  <commit>feat(OF-2): outcome_first.py — production outcome-first duel reconstruction</commit>
</task>

</tasks>

<verification>
- `py -m pytest -p no:cov` exits 0 — full suite GREEN including все 9 Wave-0 тестов
- `py -c "import outcome_first"` works
- duel_episodes DDL idempotent: `py -c "from db_utils import init_db; init_db('analytics.db'); init_db('analytics.db')"` exits 0 (run twice, no error; main analytics.db gains empty table — safe, additive)
</verification>
