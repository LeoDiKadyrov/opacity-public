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


def test_coerce_sid_none_preserves_17digit():
    """R-4: _coerce_sid must not corrupt 17-digit SteamIDs via float64 intermediate."""
    result = _coerce_sid(pd.Series([str(P), None, str(E1)]))
    assert result.iloc[0] == P
    assert result.iloc[1] == 0
    assert result.iloc[2] == E1
    assert result.dtype == "int64"


def test_collect_exchanges_opponent_from_event():
    """R-2: opponent is always read from the event, never BVH-guessed."""
    hurt = pd.DataFrame({
        "tick": [1000, 1050],
        "attacker_steamid": [str(P), str(E1)],
        "user_steamid": [str(E1), str(P)],
        "weapon": ["ak47", "ak47"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    events = collect_exchanges(hurt, death, P)
    assert len(events) == 2
    assert (events["opponent"].unique() == [E1]).all()


def test_collect_exchanges_gun_only():
    """R-1: only gunfire player_hurt rows anchor episodes; utility drops."""
    # HE grenade row -- must drop
    hurt_he = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": [str(E1)],
        "user_steamid": [str(P)],
        "weapon": ["hegrenade"],
    })
    events = collect_exchanges(hurt_he, pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"]), P)
    assert events.empty

    # Mixed: inferno (drop) + ak47 (keep)
    hurt_mixed = pd.DataFrame({
        "tick": [1000, 1050, 1100],
        "attacker_steamid": [str(E1), str(E1), str(E1)],
        "user_steamid": [str(P), str(P), str(P)],
        "weapon": ["inferno", "ak47", "inferno"],
    })
    events2 = collect_exchanges(hurt_mixed, pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"]), P)
    assert len(events2) == 1


def test_collect_exchanges_world_damage_dropped():
    """R-4: attacker_steamid=None (world/suicide) drops; sibling 17-digit stays exact."""
    hurt = pd.DataFrame({
        "tick": [1000, 1050],
        "attacker_steamid": [None, str(P)],
        "user_steamid": [str(P), str(E1)],
        "weapon": ["world", "ak47"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    events = collect_exchanges(hurt, death, P)
    # None-attacker world row dropped; P->E1 ak47 row kept with exact int value
    assert len(events) == 1
    assert int(events.iloc[0]["opponent"]) == E1


def test_group_episodes_outcome_won_lost_unresolved():
    """R-3: port of spike self_check verbatim -- 3 episodes with correct outcomes."""
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
    eps = group_episodes(events, fires, P, demo="synthetic")

    assert len(eps) == 3
    outcomes = [e["outcome"] for e in eps]
    assert outcomes == ["won", "lost", "unresolved"]

    e1 = eps[0]
    assert e1["n_hits_P_on_E"] == 1 and e1["n_hits_E_on_P"] == 1
    assert e1["initiator"] == "player"

    e2 = eps[1]
    assert e2["initiator"] == "opponent"


def test_group_episodes_gap_split():
    """R-3: gap > 320 ticks between same-opponent events splits into 2 episodes."""
    hurt = pd.DataFrame({
        "tick": [1000, 1500],
        "attacker_steamid": [str(P), str(P)],
        "user_steamid": [str(E1), str(E1)],
        "weapon": ["ak47", "ak47"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    fires = pd.DataFrame(columns=["tick", "shooter"])

    events = collect_exchanges(hurt, death, P)
    eps = group_episodes(events, fires, P, demo="synthetic")

    assert len(eps) == 2


def test_group_episodes_opponent_change():
    """R-3: opponent change splits episodes even within gap threshold."""
    hurt = pd.DataFrame({
        "tick": [1000, 1100, 1200],
        "attacker_steamid": [str(P), str(P), str(P)],
        "user_steamid": [str(E1), str(E2), str(E1)],
        "weapon": ["ak47", "ak47", "ak47"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    fires = pd.DataFrame(columns=["tick", "shooter"])

    events = collect_exchanges(hurt, death, P)
    eps = group_episodes(events, fires, P, demo="synthetic")

    assert len(eps) == 3


def test_multi_player_per_demo():
    """R-5: same hurt/death dfs processed for P and E1 as focal player independently."""
    hurt = pd.DataFrame({
        "tick": [1000, 1050],
        "attacker_steamid": [str(P), str(E1)],
        "user_steamid": [str(E1), str(P)],
        "weapon": ["ak47", "ak47"],
    })
    death = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])

    events_p = collect_exchanges(hurt, death, P)
    events_e1 = collect_exchanges(hurt, death, E1)

    assert (events_p["opponent"].unique() == [E1]).all()
    assert (events_e1["opponent"].unique() == [P]).all()


def test_db_write_duel_episodes(tmp_path):
    """R-6: duel_episodes rows survive round-trip through SQLite."""
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
