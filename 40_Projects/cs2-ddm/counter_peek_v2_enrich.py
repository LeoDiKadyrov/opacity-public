"""
counter_peek_v2_enrich.py — bounded enrichment probe (NOT production).

Adds a REAL win signal to the hold-success / counter-peek metric. The v1 probe
(counter_peek_v1.py) used win = NOT was_killed (player survival), which OVER-counts
wins and inflated donk's hold win% to an implausible ~92.7%.

This script re-parses ONLY the `player_death` event stream from each demo
(cheap — one event, no tick stream, no BVH, no reaction-time layer) and computes,
for each of the chosen player's HOLD duel_attempts rows:

    enemy_died = the row's enemy_steamid appears as VICTIM (user_steamid) in a
                 player_death event within the SAME kill-confirm window the
                 detection pipeline uses:
                     t0_tick <= death_tick <= t0_tick + _KILL_CONFIRM_WINDOW_TICKS
                 (constant mirrored from config._KILL_CONFIRM_WINDOW_TICKS = 320,
                  i.e. 5s @ 64 tick)

    win = enemy_died

TRADE / both-die handling (stated precisely):
  - We require the enemy's death to occur AT OR AFTER the player's own death does
    NOT disqualify it AS LONG AS the enemy died first or simultaneously. Concretely:
    if the player also died inside the window, the duel counts as a WIN only if the
    enemy's death_tick <= the player's own death_tick (player got the kill before /
    at the same tick they fell). If the player died strictly BEFORE the enemy, it is
    NOT a win (the player lost the duel; the enemy was killed by a teammate/trade).
  - A clean kill with the player surviving the window = win.
  - Enemy not dying in window = loss (player held but did not down the peeker:
    enemy backed off, or downed the player, or was killed elsewhere later).

This DELIBERATELY ignores T0/T1/T2, _detect_t1, analyze_engagement_episode, DDM.
It reads duel_attempts (for t0_tick/enemy_steamid/slices) + player_death only.

Usage:
    py counter_peek_v2_enrich.py \
        --db ../cs2-ddm-phase-10a/analytics.db \
        --player-steamid 76561198386265483 \
        --demo-root D:/Obsidian/opacity/40_Projects/for_analysis
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

import pandas as pd
from demoparser2 import DemoParser

sys.stdout.reconfigure(encoding="utf-8")

# Mirrored from config._KILL_CONFIRM_WINDOW_TICKS (320 = 5s @ 64 tick).
KILL_CONFIRM_WINDOW_TICKS = 320

# Slice thresholds — identical to counter_peek_v1.py for apples-to-apples.
NEAR_ANGLE_DEG = 5.0
STATIC_VEL_UPS = 10.0


def index_demos(demo_root: str) -> dict[str, str]:
    idx: dict[str, str] = {}
    for dp, _, files in os.walk(demo_root):
        for f in files:
            if f.lower().endswith(".dem"):
                idx.setdefault(f[:-4], os.path.join(dp, f))
    return idx


def load_holds(db_path: str, player_steamid: int) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT demo_name, t0_tick, enemy_steamid, was_killed,
                   player_velocity_ups, crosshair_angle_deg
            FROM duel_attempts
            WHERE engagement_type = 'hold'
              AND CAST(player_steamid AS TEXT) = ?
            """,
            con,
            params=(str(player_steamid),),
        )
    finally:
        con.close()
    return df


def parse_deaths(demo_path: str) -> pd.DataFrame:
    """Return player_death events as DataFrame with str steamids + int tick."""
    p = DemoParser(demo_path)
    df = p.parse_event("player_death")
    if df is None or df.empty:
        return pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    df = df[["tick", "attacker_steamid", "user_steamid"]].copy()
    df["tick"] = pd.to_numeric(df["tick"], errors="coerce")
    df = df.dropna(subset=["tick"])
    df["tick"] = df["tick"].astype(int)
    df["attacker_steamid"] = df["attacker_steamid"].astype(str)
    df["user_steamid"] = df["user_steamid"].astype(str)
    return df


def enemy_died_for_rows(
    rows: pd.DataFrame, deaths: pd.DataFrame, player_steamid: int
) -> list[bool]:
    """For each hold row, decide win=enemy_died with trade handling."""
    pid = str(player_steamid)
    out: list[bool] = []
    for _, r in rows.iterrows():
        t0 = int(r["t0_tick"])
        enemy = str(int(r["enemy_steamid"]))
        lo, hi = t0, t0 + KILL_CONFIRM_WINDOW_TICKS

        enemy_deaths = deaths[
            (deaths["user_steamid"] == enemy)
            & (deaths["tick"] >= lo)
            & (deaths["tick"] <= hi)
        ]
        if enemy_deaths.empty:
            out.append(False)
            continue
        enemy_death_tick = int(enemy_deaths["tick"].min())

        # Did the player also die in the window? Trade handling:
        player_deaths = deaths[
            (deaths["user_steamid"] == pid)
            & (deaths["tick"] >= lo)
            & (deaths["tick"] <= hi)
        ]
        if player_deaths.empty:
            out.append(True)  # enemy down, player survived window -> clean win
            continue
        player_death_tick = int(player_deaths["tick"].min())
        # Win only if enemy fell at or before the player did.
        out.append(enemy_death_tick <= player_death_tick)
    return out


def win_stats(df: pd.DataFrame, col: str) -> tuple[int, float]:
    n = len(df)
    if n == 0:
        return 0, float("nan")
    return n, 100.0 * float(df[col].sum()) / n


def fmt(label: str, df: pd.DataFrame, col: str) -> str:
    n, wr = win_stats(df, col)
    if n == 0:
        return f"  {label:<34} N={n:>5}   (no data)"
    return f"  {label:<34} N={n:>5}   win% = {wr:5.1f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--player-steamid", required=True, type=int)
    ap.add_argument("--demo-root", required=True)
    args = ap.parse_args()

    holds = load_holds(args.db, args.player_steamid)
    if holds.empty:
        print("No hold duels for this player. Nothing to report.")
        return

    disk = index_demos(args.demo_root)
    demo_names = sorted(holds["demo_name"].unique())
    missing = [d for d in demo_names if d not in disk]
    usable = [d for d in demo_names if d in disk]

    print("=" * 70)
    print("counter_peek_v2 — HOLD-success with REAL win signal (enemy_died)")
    print(f"  db          = {args.db}")
    print(f"  player      = {args.player_steamid}")
    print(f"  win         = enemy_steamid downed in [t0, t0+{KILL_CONFIRM_WINDOW_TICKS}]")
    print(f"  demos: {len(usable)} usable / {len(missing)} missing on disk")
    print("=" * 70)

    holds = holds[holds["demo_name"].isin(usable)].copy()
    holds["enemy_died"] = False

    for i, dn in enumerate(usable, 1):
        sub_idx = holds.index[holds["demo_name"] == dn]
        deaths = parse_deaths(disk[dn])
        flags = enemy_died_for_rows(holds.loc[sub_idx], deaths, args.player_steamid)
        holds.loc[sub_idx, "enemy_died"] = flags
        print(f"  [{i:>2}/{len(usable)}] {dn:<42} rows={len(sub_idx):>3} "
              f"wins={sum(flags):>3}")

    holds["survived"] = (holds["was_killed"] == 0).astype(int)
    holds["enemy_died_i"] = holds["enemy_died"].astype(int)

    print()
    print("-" * 70)
    print("RESULTS  (old survival-proxy  vs  new enemy_died)")
    print("-" * 70)

    def block(title: str, d: pd.DataFrame) -> None:
        n_old, wr_old = win_stats(d, "survived")
        n_new, wr_new = win_stats(d, "enemy_died_i")
        print(f"{title}")
        print(f"    N={n_new:>5}   old(survival)={wr_old:5.1f}%   "
              f"new(enemy_died)={wr_new:5.1f}%")

    block("OVERALL hold duels", holds)
    print()
    near = holds[holds["crosshair_angle_deg"] <= NEAR_ANGLE_DEG]
    wide = holds[holds["crosshair_angle_deg"] > NEAR_ANGLE_DEG]
    print("Slice (a) — pre-aim readiness (crosshair angle at t0):")
    block(f"  near angle (<= {NEAR_ANGLE_DEG:g} deg)", near)
    block(f"  wide angle (> {NEAR_ANGLE_DEG:g} deg)", wide)
    print()
    static = holds[holds["player_velocity_ups"] <= STATIC_VEL_UPS]
    moving = holds[holds["player_velocity_ups"] > STATIC_VEL_UPS]
    print("Slice (b) — static vs moving while holding:")
    block(f"  static (vel <= {STATIC_VEL_UPS:g} ups)", static)
    block(f"  moving (vel > {STATIC_VEL_UPS:g} ups)", moving)
    print("=" * 70)


if __name__ == "__main__":
    main()
