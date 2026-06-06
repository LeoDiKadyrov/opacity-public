---
phase: OF-2
plan: 00
type: tdd-red
wave: 0
depends_on: []
milestone: outcome-first
autonomous: true
files_modified:
  - tests/test_outcome_first.py   # NEW — Wave-0 RED tests
requirements: [R-1, R-2, R-3, R-4, R-5, R-6]
branch: outcome-first

must_haves:
  truths:
    - "tests/test_outcome_first.py exists with >=9 test functions covering R-1..R-6"
    - "All new tests are RED (module outcome_first does not exist yet; duel_episodes table not whitelisted yet)"
    - "The rest of the suite stays GREEN — no existing test touched"
  artifacts:
    - path: "tests/test_outcome_first.py"
      provides: "Wave-0 RED contract for the outcome-first production module"
      contains: "test_collect_exchanges_gun_only"
---

<objective>
Wave-0 RED: write the full test contract for `outcome_first.py` BEFORE the module exists. Tests define the public API (collect_exchanges, group_episodes, _coerce_sid, reconstruct_all_players) and the duel_episodes DB write. They MUST fail now (ImportError on outcome_first; ValueError on unknown table) and go GREEN only when OF-2-01 ships.
</objective>

<threat_model>
No new attack surface in this plan — test file only, synthetic data, tmp_path DB. (DB whitelist threat handled in OF-2-01.)
</threat_model>

<context>
@.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md
@.planning/phases/OF-2-core-rebuild/OF-2-RESEARCH.md  (§5 Test Conventions, §Code Examples)
@.planning/phases/OF-2-core-rebuild/OF-2-PATTERNS.md  (§tests/test_outcome_first.py)
@outcome_first_spike.py  (self_check L361-406 — порт как pytest)
@tests/test_duel_attempts.py  (L1-80 — fixture style)
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write tests/test_outcome_first.py — 9 RED tests</name>
  <files>tests/test_outcome_first.py</files>
  <read_first>
    - outcome_first_spike.py (self_check L361-406 — exact synthetic case to port; collect_exchanges L102-126 semantics; group_episodes L170-209 dict keys)
    - tests/test_duel_attempts.py L1-80 (import style, synthetic DataFrame style)
    - tests/conftest.py (autouse fixtures — make sure none interfere)
    - db_utils.py L20-58 (save_to_db contract: raises ValueError on non-whitelisted table)
  </read_first>
  <action>
    Create tests/test_outcome_first.py with EXACTLY this structure (concrete values, no placeholders):

    ```python
    """Wave-0 RED tests for outcome_first.py (OF-2 core rebuild).

    Written BEFORE the module exists (TDD). Public API under test:
        _coerce_sid(series) -> pd.Series[int64]
        collect_exchanges(hurt_df, death_df, player_steamid) -> pd.DataFrame
        group_episodes(events, fires, player_steamid, demo, match_id=...) -> List[dict]
        reconstruct_all_players(demo_path, player_sids, match_ids_by_sid, db_path)
    """
    import sqlite3

    import pandas as pd
    import pytest

    from outcome_first import (
        _coerce_sid,
        collect_exchanges,
        group_episodes,
    )

    P  = 76561198386265483   # donk
    E1 = 76561198113666193
    E2 = 76561198081484775
    ```

    Test functions (all 9, exact names — VALIDATION.md R-map references them):

    1. `test_coerce_sid_none_preserves_17digit` (R-4) — `_coerce_sid(pd.Series([str(P), None, str(E1)]))` → iloc[0]==P, iloc[1]==0, iloc[2]==E1, dtype int64. Regression for the float64 precision bug (OF-1 found-bug).

    2. `test_collect_exchanges_opponent_from_event` (R-2) — hurt rows: (tick=1000, attacker=str(P), victim=str(E1), weapon="ak47"), (tick=1050, attacker=str(E1), victim=str(P), weapon="ak47"); empty death df with columns ["tick","attacker_steamid","user_steamid"]. Assert: len(events)==2, events["opponent"].unique()==[E1].

    3. `test_collect_exchanges_gun_only` (R-1) — single hurt row weapon="hegrenade", attacker=str(E1), victim=str(P). Assert `events.empty`. Add second case in same test: weapon="inferno" row also dropped, weapon="ak47" row kept (3-row df → len(events)==1).

    4. `test_collect_exchanges_world_damage_dropped` (R-4) — hurt row with attacker_steamid=None, victim=str(P), weapon="world" → dropped; AND a sibling 17-digit row in the same df keeps exact integer value (no float corruption).

    5. `test_group_episodes_outcome_won_lost_unresolved` (R-3) — port spike self_check verbatim (hurt 5 rows / death 2 rows / fires from L366-380, plus weapon column "ak47" on hurt rows and "world" on the None row): 3 episodes, outcomes ["won","lost","unresolved"], e1 n_hits_P_on_E==1 n_hits_E_on_P==1, e1 initiator=="player", e2 initiator=="opponent".

    6. `test_group_episodes_gap_split` (R-3) — same opponent E1, two hurt events at tick 1000 and tick 1500 (gap 500 > 320) → 2 episodes.

    7. `test_group_episodes_opponent_change` (R-3) — events E1@1000, E2@1100, E1@1200 → 3 episodes (opponent change splits even within gap).

    8. `test_multi_player_per_demo` (R-5) — call collect_exchanges twice on the SAME hurt/death dfs for P and for E1 as the focal player; assert P's events have opponent==E1 and E1's events have opponent==P (multi-player = same parse, per-player grouping; no re-parse needed).

    9. `test_db_write_duel_episodes` (R-6) — tmp_path SQLite:
       ```python
       def test_db_write_duel_episodes(tmp_path):
           from db_utils import init_db, save_to_db
           db = str(tmp_path / "test.db")
           init_db(db)
           df = pd.DataFrame([{
               "match_id": "1", "demo_name": "test.dem",
               "player_steamid": P, "opponent_steamid": E1,
               "first_event_tick": 1000, "last_event_tick": 1100,
               "outcome": "won", "initiator": "player",
               "p_was_attacker_first": 1,
               "n_hits_p_on_e": 2, "n_hits_e_on_p": 1,
               "anchor_weapon": "ak47",
           }])
           save_to_db(df, db, "duel_episodes", 1)
           rows = sqlite3.connect(db).execute(
               "SELECT player_steamid, opponent_steamid, outcome FROM duel_episodes"
           ).fetchall()
           assert len(rows) == 1
           assert rows[0][0] == P and rows[0][1] == E1 and rows[0][2] == "won"
       ```

    All synthetic hurt DataFrames use columns: tick, attacker_steamid, user_steamid, weapon (strings for sids — matching demoparser2 object dtype + the None row pattern).
  </action>
  <verify>
    <automated>py -m pytest tests/test_outcome_first.py -p no:cov 2>&1 | grep -E "error|failed" (expect collection error: ModuleNotFoundError outcome_first — this IS the RED state)</automated>
    <automated>py -m pytest -p no:cov --ignore=tests/test_outcome_first.py exits 0 (rest of suite untouched, GREEN)</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_outcome_first.py contains all 9 exact test names listed above
    - `grep -c "def test_" tests/test_outcome_first.py` >= 9
    - `grep "pd.to_numeric" tests/test_outcome_first.py` returns 0 hits
    - New file RED, rest of suite GREEN
  </acceptance_criteria>
  <commit>test(OF-2): Wave-0 RED contract for outcome_first module</commit>
</task>

</tasks>

<verification>
- `py -m pytest tests/test_outcome_first.py -p no:cov` fails with ModuleNotFoundError (RED confirmed)
- `py -m pytest -p no:cov --ignore=tests/test_outcome_first.py` exits 0
- Commit on branch outcome-first
</verification>
