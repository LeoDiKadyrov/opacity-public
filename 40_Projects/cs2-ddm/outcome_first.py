"""outcome_first.py -- Production outcome-first duel reconstruction (OF-2).

Opponent identity for every reconstructed duel comes from a real
player_hurt / player_death event. The other steamid on that event IS the
opponent -- NEVER from BVH geometry guessing. Supersedes the
geometry-first DuelAttemptFinder opponent-selector path.

Outcome (won / lost / unresolved) and initiator come from event ordering,
not survival proxies. Episodes are gun-only anchored: utility/world damage
rows (HE, molotov, inferno tick-damage, flash, smoke) never start an
episode. Unresolved episodes are written to duel_episodes with an explicit
label -- they are filtered at the metric layer, never silently dropped.

Multi-player from day one: one parse per demo, per-player reconstruction
loop, per-player DB write.

CLI usage:
    py outcome_first.py --demos <root> [--player <sid>] [--db <path>]
    py outcome_first.py --demos <root> --compare-baseline <spike.json>
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from typing import Dict, List, Optional, Tuple, Union

import pandas as pd

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import (
    _INITIATOR_LOOKBACK_TICKS,
    _KILL_CONFIRM_WINDOW_TICKS,
    _T0_SEARCH_PARSE_WINDOW_TICKS,
    DB_PATH,
    UTILITY_WEAPON_NAMES,
)
from db_utils import init_db, save_to_db
import reaction_timing
from t0_detector import T0Detector

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SteamID coercion
# ---------------------------------------------------------------------------

def _coerce_sid(series: pd.Series) -> pd.Series:
    """SteamID64 -> int64 WITHOUT a float64 intermediate.

    pd.to_numeric on an object column containing None produces float64 and
    silently corrupts 17-digit SteamIDs (the classic precision bug -- see
    CLAUDE.md gotchas). Route through strings: None -> "0", digits -> int64.
    """
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")


# ---------------------------------------------------------------------------
# Event normalization
# ---------------------------------------------------------------------------

def _normalize_events(df: Optional[pd.DataFrame], kind: str) -> pd.DataFrame:
    """Normalize a player_hurt/player_death frame to tick/attacker/victim/kind/weapon."""
    cols = ["tick", "attacker", "victim", "kind", "weapon"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    weapon_col: pd.Series
    if kind == "hurt" and "weapon" in df.columns:
        weapon_col = df["weapon"].astype(str).str.lower()
    else:
        weapon_col = pd.Series([""] * len(df), dtype=str)
    out = pd.DataFrame(
        {
            "tick": pd.to_numeric(df["tick"], errors="coerce"),
            "attacker": _coerce_sid(df["attacker_steamid"]),
            "victim": _coerce_sid(df["user_steamid"]),
            "weapon": weapon_col,
        }
    ).dropna(subset=["tick"])
    out["tick"] = out["tick"].astype("int64")
    out["kind"] = kind
    return out[cols]


# ---------------------------------------------------------------------------
# Exchange collection (gun-only)
# ---------------------------------------------------------------------------

def collect_exchanges(
    hurt_df: Optional[pd.DataFrame],
    death_df: Optional[pd.DataFrame],
    player_steamid: int,
) -> pd.DataFrame:
    """All ground-truth exchanges involving P, with the REAL opponent attached.

    The opponent is the other steamid on the event -- read from the event,
    never selected by geometry. World/suicide rows (opponent 0 or == P) drop.

    Gun-only anchor (OF-2 decision): utility damage never starts/joins an
    episode's event stream. Defensive: if weapon column absent, treat all
    hurts as gunfire (conservative -- no silent episode drops).
    """
    # Gun-only anchor: filter utility rows from hurt_df before normalizing
    filtered_hurt = hurt_df
    if hurt_df is not None and not hurt_df.empty and "weapon" in hurt_df.columns:
        filtered_hurt = hurt_df[
            ~hurt_df["weapon"].astype(str).str.lower().isin(UTILITY_WEAPON_NAMES)
        ]

    events = pd.concat(
        [
            _normalize_events(filtered_hurt, "hurt"),
            _normalize_events(death_df, "death"),
        ],
        ignore_index=True,
    )
    if events.empty:
        return pd.DataFrame(columns=list(events.columns) + ["opponent"])
    mask = (events["attacker"] == player_steamid) | (events["victim"] == player_steamid)
    events = events[mask].copy()
    events["opponent"] = events["attacker"].where(
        events["victim"] == player_steamid, events["victim"]
    )
    events = events[
        (events["opponent"] != 0) & (events["opponent"] != player_steamid)
    ]
    return events.sort_values("tick").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Episode helpers
# ---------------------------------------------------------------------------

def _episode_outcome(
    ep: pd.DataFrame, player_steamid: int, opponent: int
) -> str:
    deaths = ep[ep["kind"] == "death"]
    e_death = deaths[deaths["victim"] == opponent]["tick"]
    p_death = deaths[deaths["victim"] == player_steamid]["tick"]
    e_tick = int(e_death.min()) if not e_death.empty else None
    p_tick = int(p_death.min()) if not p_death.empty else None
    if e_tick is not None and (p_tick is None or e_tick <= p_tick):
        return "won"
    if p_tick is not None:
        return "lost"
    return "unresolved"


def _episode_initiator(
    ep: pd.DataFrame,
    fires: pd.DataFrame,
    player_steamid: int,
    opponent: int,
) -> str:
    first_tick = int(ep["tick"].iloc[0])
    lo = first_tick - _INITIATOR_LOOKBACK_TICKS
    if not fires.empty:
        win = fires[
            (fires["tick"] >= lo)
            & (fires["tick"] <= first_tick)
            & (fires["shooter"].isin([player_steamid, opponent]))
        ]
        if not win.empty:
            first_shooter = int(win.sort_values("tick")["shooter"].iloc[0])
            return "player" if first_shooter == player_steamid else "opponent"
    # Fallback: who landed the first hit in the episode.
    first_attacker = int(ep["attacker"].iloc[0])
    if first_attacker == player_steamid:
        return "player"
    if first_attacker == opponent:
        return "opponent"
    return "unknown"


# ---------------------------------------------------------------------------
# Episode grouping
# ---------------------------------------------------------------------------

def group_episodes(
    events: pd.DataFrame,
    fires: Optional[pd.DataFrame],
    player_steamid: int,
    demo: str,
    match_id: Union[int, str] = "",
    # _KILL_CONFIRM_WINDOW_TICKS=320 ~= 5s @ 64-tick, reused as episode gap
    # (same semantic: fight over after 5s silence)
    gap_ticks: int = _KILL_CONFIRM_WINDOW_TICKS,
) -> List[dict]:
    """Group consecutive same-opponent P-vs-E events into duel episodes."""
    if fires is None:
        fires = pd.DataFrame(columns=["tick", "shooter"])
    episodes: List[dict] = []
    if events.empty:
        return episodes

    # New episode when opponent changes or gap to prior event > gap_ticks.
    prev_opp = events["opponent"].shift(1)
    prev_tick = events["tick"].shift(1)
    new_ep = (events["opponent"] != prev_opp) | (
        (events["tick"] - prev_tick) > gap_ticks
    )
    ep_id = new_ep.cumsum()

    for _, ep in events.groupby(ep_id):
        opponent = int(ep["opponent"].iloc[0])
        hurts = ep[ep["kind"] == "hurt"]
        first_attacker = int(ep["attacker"].iloc[0])
        # anchor_weapon: weapon string from the first hurt event in this episode
        first_hurt = hurts.sort_values("tick") if not hurts.empty else None
        anchor_weapon = (
            str(first_hurt.iloc[0]["weapon"])
            if first_hurt is not None and not first_hurt.empty and "weapon" in first_hurt.columns
            else ""
        )
        episodes.append(
            {
                "demo_name": demo,
                "match_id": str(match_id),
                "opponent_steamid": opponent,
                "opponent": opponent,  # kept for backward-compat with tests
                "first_event_tick": int(ep["tick"].iloc[0]),
                "last_event_tick": int(ep["tick"].iloc[-1]),
                "outcome": _episode_outcome(ep, player_steamid, opponent),
                "p_was_attacker_first": int(first_attacker == player_steamid),
                "initiator": _episode_initiator(ep, fires, player_steamid, opponent),
                "n_hits_P_on_E": int((hurts["attacker"] == player_steamid).sum()),
                "n_hits_E_on_P": int((hurts["attacker"] == opponent).sum()),
                "anchor_weapon": anchor_weapon,
            }
        )
    return episodes


# ---------------------------------------------------------------------------
# Demo parsing
# ---------------------------------------------------------------------------

# Tick props required by reaction_timing.compute_timing: position + aim
# (X, Y, Z, pitch, yaw) plus steamid for per-sid lookup. Mirrors
# DDMAnalyzer._TICKS_REQUIRED (ddm_analyzer.py line 51).
_TIMING_TICK_PROPS: List[str] = ["X", "Y", "Z", "pitch", "yaw", "steamid"]


def _parse_demo_header_map(demo_path: str) -> str:
    """Return the map_name from the demo header, or 'unknown' on failure."""
    from demoparser2 import DemoParser

    try:
        parser = DemoParser(demo_path)
        header = parser.parse_header()
        return header.get("map_name", "unknown")
    except Exception:
        logger.exception("Could not parse demo header for %s", demo_path)
        return "unknown"


def _parse_timing_ticks(
    demo_path: str,
    episodes_by_sid: Dict[int, List[dict]],
) -> Tuple[pd.DataFrame, Dict[int, pd.DataFrame]]:
    """Selective parse_ticks covering [first_event_tick - WINDOW, last_event_tick]
    for every episode across all players (D-08, Pitfall 2).

    Returns (ticks_df, ticks_by_sid). Empty DataFrame + {} if no episodes.
    """
    from demoparser2 import DemoParser

    all_ticks: List[int] = []
    for eps in episodes_by_sid.values():
        for ep in eps:
            first_tick = int(ep["first_event_tick"])
            last_tick = int(ep["last_event_tick"])
            all_ticks.append(first_tick - _T0_SEARCH_PARSE_WINDOW_TICKS)
            all_ticks.append(last_tick)

    if not all_ticks:
        return pd.DataFrame(columns=_TIMING_TICK_PROPS + ["tick"]), {}

    import numpy as np

    window_min = max(0, min(all_ticks))
    window_max = max(all_ticks)
    window = np.arange(window_min, window_max + 1, dtype=np.int64)

    parser = DemoParser(demo_path)
    ticks_df = pd.DataFrame(parser.parse_ticks(_TIMING_TICK_PROPS, ticks=window.tolist()))
    if ticks_df.empty:
        return ticks_df, {}

    ticks_df["steamid"] = _coerce_sid(ticks_df["steamid"])
    ticks_df["tick"] = pd.to_numeric(ticks_df["tick"], errors="coerce")
    ticks_df.dropna(subset=["tick"], inplace=True)
    ticks_df["tick"] = ticks_df["tick"].astype("int64")

    # Pitfall 2: warn if the parsed window does not fully cover the backward
    # search start for any episode (find_t0 would falsely return never_visible).
    parsed_min = int(ticks_df["tick"].min())
    for eps in episodes_by_sid.values():
        for ep in eps:
            search_start = int(ep["first_event_tick"]) - _T0_SEARCH_PARSE_WINDOW_TICKS
            if search_start < parsed_min:
                logger.warning(
                    "Timing tick window does not cover backward search start "
                    "(search_start=%d < parsed_min=%d) for episode first_event_tick=%d",
                    search_start, parsed_min, ep["first_event_tick"],
                )

    ticks_by_sid: Dict[int, pd.DataFrame] = {
        int(sid): g.sort_values("tick")
        for sid, g in ticks_df.groupby("steamid", sort=False)
    }
    return ticks_df, ticks_by_sid


def _parse_demo_events(
    demo_path: str,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Return (hurt_df, death_df, fires_df) for one demo."""
    from demoparser2 import DemoParser  # local import: unit tests need no parser

    parser = DemoParser(demo_path)
    parsed = dict(
        parser.parse_events(["player_hurt", "player_death", "weapon_fire"])
    )
    hurt = parsed.get("player_hurt")
    death = parsed.get("player_death")
    fire = parsed.get("weapon_fire")
    fires = None
    if fire is not None and not fire.empty and "user_steamid" in fire.columns:
        fires = pd.DataFrame(
            {
                "tick": pd.to_numeric(fire["tick"], errors="coerce"),
                "shooter": _coerce_sid(fire["user_steamid"]),
            }
        ).dropna(subset=["tick"])
        fires["tick"] = fires["tick"].astype("int64")
    return hurt, death, fires


# ---------------------------------------------------------------------------
# Discover player sids
# ---------------------------------------------------------------------------

def discover_player_sids(hurt_df: Optional[pd.DataFrame]) -> List[int]:
    """Return all distinct non-zero sids from attacker+victim columns via _coerce_sid.

    Enables "all players in demo" mode when the roster is unknown.
    Defensive: returns empty list if hurt_df is None or empty.
    """
    if hurt_df is None or hurt_df.empty:
        return []
    sids: List[int] = []
    for col in ("attacker_steamid", "user_steamid"):
        if col in hurt_df.columns:
            sids.extend(_coerce_sid(hurt_df[col]).tolist())
    return sorted({int(s) for s in sids if int(s) != 0})


# ---------------------------------------------------------------------------
# Multi-player public API
# ---------------------------------------------------------------------------

def reconstruct_all_players(
    demo_path: str,
    player_sids: List[int],
    match_ids_by_sid: Dict[int, Union[int, str]],
    db_path: str = DB_PATH,
) -> Dict[int, int]:
    """Parse demo ONCE, reconstruct episodes per player, write each player's
    episodes to duel_episodes. Returns {sid: n_episodes}.
    Never raises from the per-player loop (logger.exception + continue).
    """
    demo_name = os.path.splitext(os.path.basename(demo_path))[0]
    try:
        hurt_df, death_df, fires_df = _parse_demo_events(demo_path)
    except Exception:
        logger.exception("Failed to parse demo events from %s", demo_path)
        return {sid: 0 for sid in player_sids}

    # Build episodes for ALL players first so the selective timing-tick parse
    # (D-08) can cover the union window across every player's episodes.
    episodes_by_sid: Dict[int, List[dict]] = {}
    for sid in player_sids:
        try:
            events = collect_exchanges(hurt_df, death_df, sid)
            episodes_by_sid[sid] = group_episodes(
                events,
                fires_df,
                sid,
                demo=demo_name,
                match_id=str(match_ids_by_sid[sid]),
            )
        except Exception:
            logger.exception(
                "Failed to group episodes for %s in %s", sid, demo_name
            )
            episodes_by_sid[sid] = []

    # OF-3: per-episode timing pass (D-01/D-03/D-05/D-06/D-08). Parse the
    # union tick window once per demo and instantiate T0Detector once
    # (D-07: no needless re-instantiation; BVH/.tri load is the costly step).
    timing_cols = [
        "t0_tick", "t0_source", "t1_tick", "t1_source",
        "crosshair_angle_at_t0_deg", "rt_visible_to_land_ms", "rt_visible_to_hit_ms",
    ]
    t0_detector = None
    ticks_df = pd.DataFrame()
    ticks_by_sid: Dict[int, pd.DataFrame] = {}
    try:
        ticks_df, ticks_by_sid = _parse_timing_ticks(demo_path, episodes_by_sid)
        if any(episodes_by_sid.values()):
            map_name = _parse_demo_header_map(demo_path)
            t0_detector = T0Detector(map_name)
    except Exception:
        logger.exception(
            "Failed to prepare OF-3 timing pass for %s; episodes will be "
            "written without timing columns",
            demo_name,
        )

    results: Dict[int, int] = {}
    for sid in player_sids:
        eps = episodes_by_sid.get(sid, [])
        try:
            if eps:
                df = pd.DataFrame(eps)
                df["player_steamid"] = sid
                # Rename from group_episodes mixed-case keys to DB DDL column names
                df = df.rename(columns={
                    "n_hits_P_on_E": "n_hits_p_on_e",
                    "n_hits_E_on_P": "n_hits_e_on_p",
                })
                # Drop the backward-compat 'opponent' alias before DB write
                if "opponent" in df.columns:
                    df = df.drop(columns=["opponent"])

                if t0_detector is not None:
                    timings = []
                    for _, row in df.iterrows():
                        t = reaction_timing.compute_timing(
                            row.to_dict(), ticks_df, t0_detector, ticks_by_sid=ticks_by_sid
                        )
                        timings.append(t)
                    timing_df = pd.DataFrame(timings, index=df.index, columns=timing_cols)
                    df = pd.concat([df, timing_df], axis=1)

                save_to_db(df, db_path, "duel_episodes", match_ids_by_sid[sid])
            results[sid] = len(eps)
        except Exception:
            logger.exception(
                "Failed to reconstruct episodes for %s in %s", sid, demo_name
            )
            results[sid] = 0
    return results


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def find_demos(root: str) -> List[str]:
    """Recursively find all .dem files under root."""
    out: List[str] = []
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".dem"):
                out.append(os.path.join(dp, f))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="OF-2 outcome-first duel reconstruction (production)"
    )
    ap.add_argument("--demos", type=str, help="Demo root directory (recursed)")
    ap.add_argument(
        "--player", type=int, default=None,
        help="Single player SteamID64 (default: all players per demo)"
    )
    ap.add_argument("--db", type=str, default=DB_PATH, help="SQLite DB path")
    ap.add_argument(
        "--compare-baseline", type=str, default=None,
        metavar="JSON",
        help="Spike JSON output: print n_episodes/won/lost/unresolved deltas vs production run"
    )
    args = ap.parse_args()

    if not args.demos:
        ap.error("--demos required")

    demo_paths = find_demos(args.demos)
    print(f"demos found={len(demos)} root={args.demos}" if False else
          f"demos found={len(demo_paths)}  root={args.demos}")

    init_db(args.db)

    from db_utils import get_next_match_id
    match_id_counter = get_next_match_id(args.db)

    baseline: Optional[dict] = None
    if args.compare_baseline:
        with open(args.compare_baseline, encoding="utf-8") as fh:
            baseline = json.load(fh)

    total_eps: Dict[int, int] = {}
    for demo_path in demo_paths:
        demo_name = os.path.splitext(os.path.basename(demo_path))[0]
        try:
            hurt_df, death_df, fires_df = _parse_demo_events(demo_path)
        except Exception as exc:
            print(f"  PARSE FAIL: {demo_name}: {exc}")
            continue

        if args.player:
            sids = [args.player]
        else:
            sids = discover_player_sids(hurt_df)

        if not sids:
            print(f"  no players found in {demo_name}, skip")
            continue

        match_ids_by_sid = {sid: match_id_counter + i for i, sid in enumerate(sids)}
        match_id_counter += len(sids)

        for sid in sids:
            events = collect_exchanges(hurt_df, death_df, sid)
            eps = group_episodes(
                events, fires_df, sid, demo=demo_name,
                match_id=str(match_ids_by_sid[sid]),
            )
            if eps:
                df = pd.DataFrame(eps)
                df["player_steamid"] = sid
                df = df.rename(columns={
                    "n_hits_P_on_E": "n_hits_p_on_e",
                    "n_hits_E_on_P": "n_hits_e_on_p",
                })
                if "opponent" in df.columns:
                    df = df.drop(columns=["opponent"])
                save_to_db(df, args.db, "duel_episodes", match_ids_by_sid[sid])
            total_eps[sid] = total_eps.get(sid, 0) + len(eps)
        print(f"  {demo_name}: {sum(len(group_episodes(collect_exchanges(hurt_df, death_df, s), fires_df, s, demo=demo_name)) for s in sids)} episodes across {len(sids)} players")

    print(f"Done. Episodes per player: {total_eps}")

    if baseline is not None and args.player:
        b_eps = baseline.get("summary", {})
        prod_eps = total_eps.get(args.player, 0)
        b_n = b_eps.get("n_episodes", 0)
        b_won = b_eps.get("won", 0)
        b_lost = b_eps.get("lost", 0)
        b_unres = b_eps.get("unresolved", 0)
        print(f"\n-- compare-baseline --")
        print(f"  baseline n_episodes : {b_n}")
        print(f"  production n_episodes: {prod_eps}")
        if b_n:
            print(f"  delta n_episodes    : {prod_eps - b_n:+d} ({100.0*(prod_eps-b_n)/b_n:+.1f}%)")
        print(f"  baseline  won/lost/unres: {b_won}/{b_lost}/{b_unres}")


if __name__ == "__main__":
    main()
