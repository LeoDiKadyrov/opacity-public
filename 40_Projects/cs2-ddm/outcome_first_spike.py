"""outcome_first_spike.py — OF-1 outcome-first validation spike (NOT production).

Standalone duel reconstructor that INVERTS djok's geometry-first architecture:

    Opponent identity for every reconstructed duel comes from a real
    player_hurt / player_death event (attacker==P OR victim==P) — the other
    steamid on that event IS the opponent. NEVER from BVH selection.

    Outcome (won / lost / unresolved) comes from player_death ordering
    within the duel episode — ground truth, not a survival proxy.

This script does NOT import duel_attempts, DuelAttemptFinder, ddm_analyzer or
_detect_t1. No production module is touched (OF-1 tripwire).

Episodes: consecutive P-vs-E events (same opponent E) are grouped into one
duel episode; a new episode starts when the opponent changes or the gap to
the prior P-vs-E event exceeds KILL_CONFIRM_WINDOW_TICKS (320 ≈ 5s @ 64-tick).

Initiator: whoever of {P, E} fired first (weapon_fire) in the window
[first_event_tick - INITIATOR_LOOKBACK_TICKS, first_event_tick]; falls back
to who landed the first hit in the episode. weapon_fire has no target, so a
fire by E at someone else inside the lookback is attributed to the duel —
accepted spike-level noise, documented here.

Usage:
    py -X utf8 outcome_first_spike.py --self-check
    py -X utf8 outcome_first_spike.py --player 76561198386265483 \
        --demos "D:/Obsidian/opacity/40_Projects/for_analysis" \
        --out outcome_first_spike_results.json
    py -X utf8 outcome_first_spike.py --gate --out outcome_first_spike_results.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from typing import List, Optional, Tuple

import pandas as pd

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

# Mirrored from config._KILL_CONFIRM_WINDOW_TICKS (320 = 5s @ 64-tick).
# Reused here as the duel-episode grouping gap. Do NOT import config (tripwire).
KILL_CONFIRM_WINDOW_TICKS = 320

# How far before the first landed hit we look for weapon_fire to decide initiator.
INITIATOR_LOOKBACK_TICKS = 128  # 2s @ 64-tick

DONK_STEAMID = 76561198386265483

# Old geometry-first baseline (see outcome-first-ROADMAP.md / OF-1-CONTEXT.md):
OLD_OPPONENT_TRUTH_RATE = 5.9  # % of hold rows with any hit on BVH-nominal enemy
OLD_SURVIVAL_WIN_RATE = 92.7   # % survival-proxy "win" — implausible

EPISODE_COLUMNS = [
    "demo",
    "opponent",
    "first_event_tick",
    "last_event_tick",
    "outcome",            # won | lost | unresolved
    "p_was_attacker_first",
    "initiator",          # player | opponent | unknown
    "n_hits_P_on_E",
    "n_hits_E_on_P",
]


def _coerce_sid(series: pd.Series) -> pd.Series:
    """SteamID64 -> int64 WITHOUT a float64 intermediate.

    pd.to_numeric on an object column containing None produces float64 and
    silently corrupts 17-digit SteamIDs (the classic precision bug — see
    CLAUDE.md gotchas). Route through strings: None -> "0", digits -> int64.
    """
    s = series.astype("string").fillna("0")
    s = s.str.extract(r"(\d+)", expand=False).fillna("0")
    return s.astype("int64")


def _normalize_events(df: Optional[pd.DataFrame], kind: str) -> pd.DataFrame:
    """Normalize a player_hurt/player_death frame to tick/attacker/victim/kind."""
    cols = ["tick", "attacker", "victim", "kind"]
    if df is None or df.empty:
        return pd.DataFrame(columns=cols)
    out = pd.DataFrame(
        {
            "tick": pd.to_numeric(df["tick"], errors="coerce"),
            "attacker": _coerce_sid(df["attacker_steamid"]),
            "victim": _coerce_sid(df["user_steamid"]),
        }
    ).dropna(subset=["tick"])
    out["tick"] = out["tick"].astype("int64")
    out["kind"] = kind
    return out[cols]


def collect_exchanges(
    hurt_df: Optional[pd.DataFrame],
    death_df: Optional[pd.DataFrame],
    player_steamid: int,
) -> pd.DataFrame:
    """All ground-truth exchanges involving P, with the REAL opponent attached.

    The opponent is the other steamid on the event — read from the event,
    never selected by geometry. World/suicide rows (opponent 0 or == P) drop.
    """
    events = pd.concat(
        [_normalize_events(hurt_df, "hurt"), _normalize_events(death_df, "death")],
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
    lo = first_tick - INITIATOR_LOOKBACK_TICKS
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


def group_episodes(
    events: pd.DataFrame,
    fires: Optional[pd.DataFrame],
    player_steamid: int,
    demo: str,
    gap_ticks: int = KILL_CONFIRM_WINDOW_TICKS,
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
        episodes.append(
            {
                "demo": demo,
                "opponent": opponent,
                "first_event_tick": int(ep["tick"].iloc[0]),
                "last_event_tick": int(ep["tick"].iloc[-1]),
                "outcome": _episode_outcome(ep, player_steamid, opponent),
                "p_was_attacker_first": first_attacker == player_steamid,
                "initiator": _episode_initiator(ep, fires, player_steamid, opponent),
                "n_hits_P_on_E": int((hurts["attacker"] == player_steamid).sum()),
                "n_hits_E_on_P": int((hurts["attacker"] == opponent).sum()),
            }
        )
    return episodes


def _parse_demo_events(
    demo_path: str,
) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """Return (hurt_df, death_df, fires_df) for one demo."""
    from demoparser2 import DemoParser  # local import: --self-check needs no parser

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


def reconstruct_duels(
    player_steamid: int, demo_paths: List[str]
) -> Tuple[pd.DataFrame, dict]:
    """Outcome-first duel episodes for one player across demos.

    Opponent and outcome derive ONLY from player_hurt / player_death events.
    """
    all_eps: List[dict] = []
    n_failed = 0
    n_no_player = 0
    for i, path in enumerate(demo_paths, 1):
        demo = os.path.splitext(os.path.basename(path))[0]
        try:
            hurt, death, fires = _parse_demo_events(path)
        except Exception as exc:  # noqa: BLE001 — skip + log, never fabricate
            n_failed += 1
            print(f"  [{i:>3}/{len(demo_paths)}] {demo:<50} PARSE FAIL: {exc}")
            continue
        events = collect_exchanges(hurt, death, player_steamid)
        if events.empty:
            n_no_player += 1
            print(f"  [{i:>3}/{len(demo_paths)}] {demo:<50} no player events, skip")
            continue
        eps = group_episodes(events, fires, player_steamid, demo)
        all_eps.extend(eps)
        print(f"  [{i:>3}/{len(demo_paths)}] {demo:<50} episodes={len(eps):>4}")

    df = pd.DataFrame(all_eps, columns=EPISODE_COLUMNS)
    stats = {
        "n_demos_given": len(demo_paths),
        "n_demos_failed": n_failed,
        "n_demos_no_player_events": n_no_player,
        "n_demos_with_episodes": len(demo_paths) - n_failed - n_no_player,
    }
    return df, stats


def summarize(df: pd.DataFrame) -> dict:
    n = len(df)
    won = int((df["outcome"] == "won").sum())
    lost = int((df["outcome"] == "lost").sum())
    unresolved = int((df["outcome"] == "unresolved").sum())
    resolved = won + lost
    return {
        "n_episodes": n,
        "won": won,
        "lost": lost,
        "unresolved": unresolved,
        "resolved": resolved,
        "win_rate_resolved_pct": round(100.0 * won / resolved, 1) if resolved else None,
        "median_hits_P_on_E": float(df["n_hits_P_on_E"].median()) if n else None,
        "median_hits_E_on_P": float(df["n_hits_E_on_P"].median()) if n else None,
    }


def _bucket_win_rate(df: pd.DataFrame) -> Tuple[int, Optional[float]]:
    res = df[df["outcome"].isin(["won", "lost"])]
    n = len(res)
    if n == 0:
        return 0, None
    return n, round(100.0 * (res["outcome"] == "won").sum() / n, 1)


def print_gates(df: pd.DataFrame, summary: dict) -> dict:
    """GATE-1/2/3 vs old geometry-first baseline. Returns gate dict for json."""
    n = len(df)
    print()
    print("=" * 72)
    print("OF-1 GATE METRICS  (new outcome-first  vs  old geometry-first baseline)")
    print("=" * 72)

    # GATE-1 — opponent-truth rate. By construction every episode is anchored
    # on a real player_hurt/player_death involving the player; report explicitly.
    truth_rate = 100.0 if n else 0.0
    print(f"GATE-1 opponent-truth rate : {truth_rate:5.1f}%   "
          f"(old nominal-hit rate: {OLD_OPPONENT_TRUTH_RATE}%)")
    print("        every episode anchored on real player_hurt/player_death; "
          "opponent read from event, never BVH-guessed")

    # GATE-2 — win-rate plausibility (resolved duels), PASS band ~40-70%.
    wr = summary["win_rate_resolved_pct"]
    print(f"GATE-2 resolved win-rate   : {wr}%  on N={summary['resolved']} resolved "
          f"({summary['won']} won / {summary['lost']} lost; "
          f"{summary['unresolved']} unresolved)   "
          f"(old survival-proxy win: {OLD_SURVIVAL_WIN_RATE}%)")

    # GATE-3 — interpretable slice: holder/counter (opponent initiated) vs
    # player-initiated. Old slices: zero separation.
    holder = df[df["initiator"] == "opponent"]
    init = df[df["initiator"] == "player"]
    n_h, wr_h = _bucket_win_rate(holder)
    n_i, wr_i = _bucket_win_rate(init)
    print("GATE-3 initiator slice (win-rate among resolved):")
    print(f"        opponent initiated (P holds/counters): win% = {wr_h} on N={n_h}")
    print(f"        player initiated   (P peeks first)   : win% = {wr_i} on N={n_i}")
    sep = round(abs((wr_h or 0) - (wr_i or 0)), 1) if (wr_h is not None and wr_i is not None) else None
    print(f"        separation = {sep} pp   (old slices: no separation)")

    # Secondary slice: who landed the first hit (purely event-derived).
    fh_p = df[df["p_was_attacker_first"]]
    fh_e = df[~df["p_was_attacker_first"]]
    n_fp, wr_fp = _bucket_win_rate(fh_p)
    n_fe, wr_fe = _bucket_win_rate(fh_e)
    print("        [aux] first-hit slice: P landed first hit "
          f"win% = {wr_fp} (N={n_fp}); opponent landed first win% = {wr_fe} (N={n_fe})")
    print("=" * 72)

    return {
        "gate1_opponent_truth_rate_pct": truth_rate,
        "gate1_old_baseline_pct": OLD_OPPONENT_TRUTH_RATE,
        "gate2_win_rate_resolved_pct": wr,
        "gate2_old_baseline_pct": OLD_SURVIVAL_WIN_RATE,
        "gate3_holder_win_pct": wr_h,
        "gate3_holder_n_resolved": n_h,
        "gate3_initiator_win_pct": wr_i,
        "gate3_initiator_n_resolved": n_i,
        "gate3_separation_pp": sep,
        "aux_first_hit_player_win_pct": wr_fp,
        "aux_first_hit_player_n": n_fp,
        "aux_first_hit_opponent_win_pct": wr_fe,
        "aux_first_hit_opponent_n": n_fe,
    }


def self_check() -> None:
    """Synthetic 3-episode sanity check — no real demos needed."""
    # Real 17-digit IDs as STRINGS + a None row — regression guard for the
    # float64 precision bug (None in column -> to_numeric -> float -> sid corrupt).
    P, E1, E2 = 76561198386265483, 76561198113666193, 76561198081484775
    hurt = pd.DataFrame(
        {
            "tick": [1000, 1050, 2000, 5000, 6000],
            "attacker_steamid": [str(P), str(E1), str(E2), str(P), None],
            "user_steamid": [str(E1), str(P), str(P), str(E1), str(P)],
        }
    )
    death = pd.DataFrame(
        {
            "tick": [1100, 2100],
            "attacker_steamid": [str(P), str(E2)],
            "user_steamid": [str(E1), str(P)],
        }
    )
    fires = pd.DataFrame({"tick": [990, 1990], "shooter": [P, E2]})

    events = collect_exchanges(hurt, death, P)
    # 6 valid P-events; the None-attacker row (world damage on P) must DROP,
    # and its presence must NOT corrupt the other 17-digit sids via float64.
    assert len(events) == 6, f"expected 6 P-events, got {len(events)}"
    assert (events["opponent"].isin([E1, E2])).all(), events["opponent"].tolist()
    eps = group_episodes(events, fires, P, demo="synthetic")
    assert len(eps) == 3, f"expected 3 episodes, got {len(eps)}"

    e1, e2, e3 = eps
    assert e1["opponent"] == E1 and e1["outcome"] == "won", e1
    assert e1["n_hits_P_on_E"] == 1 and e1["n_hits_E_on_P"] == 1, e1
    assert e1["p_was_attacker_first"] is True and e1["initiator"] == "player", e1

    assert e2["opponent"] == E2 and e2["outcome"] == "lost", e2
    assert e2["p_was_attacker_first"] is False and e2["initiator"] == "opponent", e2

    # Third: same opponent E1 but gap 5000-1100 > 320 ticks -> new episode.
    assert e3["opponent"] == E1 and e3["outcome"] == "unresolved", e3

    df = pd.DataFrame(eps, columns=EPISODE_COLUMNS)
    s = summarize(df)
    assert s["n_episodes"] == 3 and s["won"] == 1 and s["lost"] == 1, s
    assert s["unresolved"] == 1 and s["win_rate_resolved_pct"] == 50.0, s
    print("self-check PASS: 3 synthetic episodes, opponent+outcome+initiator "
          "all derived from events only")


def find_demos(root: str) -> List[str]:
    out: List[str] = []
    for dp, _, files in os.walk(root):
        for f in files:
            if f.lower().endswith(".dem"):
                out.append(os.path.join(dp, f))
    return sorted(out)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="OF-1 outcome-first duel reconstruction spike"
    )
    ap.add_argument("--self-check", action="store_true")
    ap.add_argument("--player", type=int, default=DONK_STEAMID)
    ap.add_argument("--demos", type=str, help="demo root dir (recursed)")
    ap.add_argument("--out", type=str, default="outcome_first_spike_results.json")
    ap.add_argument("--gate", action="store_true",
                    help="print GATE-1/2/3 from --out json (no re-parse)")
    args = ap.parse_args()

    if args.self_check:
        self_check()
        return

    if args.gate and not args.demos:
        with open(args.out, encoding="utf-8") as fh:
            payload = json.load(fh)
        df = pd.DataFrame(payload["episodes"], columns=EPISODE_COLUMNS)
        summary = payload["summary"]
        gates = print_gates(df, summary)
        payload["gates"] = gates
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2)
        return

    if not args.demos:
        ap.error("--demos required (or use --self-check / --gate)")

    demos = find_demos(args.demos)
    print(f"player={args.player}  demos found={len(demos)}  root={args.demos}")
    df, parse_stats = reconstruct_duels(args.player, demos)
    summary = summarize(df)
    summary.update(parse_stats)

    print()
    print("-" * 72)
    print("SUMMARY")
    print(f"  total episodes      : {summary['n_episodes']}")
    print(f"  won / lost / unres. : {summary['won']} / {summary['lost']} / "
          f"{summary['unresolved']}")
    print(f"  resolved win-rate   : {summary['win_rate_resolved_pct']}%")
    print(f"  median hits P-on-E  : {summary['median_hits_P_on_E']}")
    print(f"  demos: given={summary['n_demos_given']} "
          f"failed={summary['n_demos_failed']} "
          f"no-player={summary['n_demos_no_player_events']} "
          f"used={summary['n_demos_with_episodes']}")
    print("-" * 72)

    gates = print_gates(df, summary)

    payload = {
        "player_steamid": str(args.player),  # str: json readers must not float it
        "summary": summary,
        "gates": gates,
        "episodes": df.assign(opponent=df["opponent"].astype(str)).to_dict(
            orient="records"
        ),
    }
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    print(f"results written -> {args.out}")


if __name__ == "__main__":
    main()
