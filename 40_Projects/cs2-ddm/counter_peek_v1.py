"""
counter_peek_v1.py — bounded exploratory probe (NOT production).

A v1 "hold-success" / counter-peek metric built ONLY from the duel_attempts
table. The player is HOLDING an angle (engagement_type='hold'); the enemy is
the one peeking. We ask: when this player holds, how often do they win?

DELIBERATELY ignores the entire reaction-time / DDM layer (T0/T1/T2,
analyze_engagement_episode, _detect_t1, coaching). Reads duel_attempts only.

WIN definition (see STEP 2 / module docstring):
    win = NOT was_killed
duel_attempts has no clean "enemy died" flag (was_killed is about the PLAYER;
bullets_hit counts the player's registered hits but not a confirmed kill of the
peeker). So "win" here is strictly "player survived the duel". This OVER-counts
wins (a trade where both die, or the player surviving but losing the round, both
read as wins). Stated as a limitation, not papered over.

Usage:
    py counter_peek_v1.py --db ../cs2-ddm-phase-10a/analytics.db \
        --player-steamid 76561198386265483
"""
from __future__ import annotations

import argparse
import sqlite3
import sys

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

# Slice thresholds (chosen from observed donk hold distribution, see probe).
NEAR_ANGLE_DEG = 5.0      # crosshair already on/near the angle at t0 = "pre-aimed"
STATIC_VEL_UPS = 10.0     # <= this ~= standing still while holding


def load_holds(db_path: str, player_steamid: int) -> pd.DataFrame:
    con = sqlite3.connect(db_path)
    try:
        df = pd.read_sql_query(
            """
            SELECT was_killed, bullets_fired, bullets_hit,
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


def win_rate(df: pd.DataFrame) -> tuple[int, float]:
    n = len(df)
    if n == 0:
        return 0, float("nan")
    wins = int((df["was_killed"] == 0).sum())  # win = survived = NOT killed
    return n, 100.0 * wins / n


def fmt(label: str, df: pd.DataFrame) -> str:
    n, wr = win_rate(df)
    if n == 0:
        return f"  {label:<34} N={n:>5}   (no data)"
    return f"  {label:<34} N={n:>5}   win% = {wr:5.1f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", required=True)
    ap.add_argument("--player-steamid", required=True, type=int)
    args = ap.parse_args()

    df = load_holds(args.db, args.player_steamid)

    print("=" * 64)
    print("counter_peek_v1 — HOLD-success probe (player holds, enemy peeks)")
    print(f"  db     = {args.db}")
    print(f"  player = {args.player_steamid}")
    print(f'  win    = NOT was_killed (survival proxy; OVER-counts, see header)')
    print("=" * 64)

    n_total, wr_total = win_rate(df)
    if n_total == 0:
        print("No hold duels for this player in this DB. Nothing to report.")
        return

    print(fmt("OVERALL hold duels", df))
    print()

    # Slice (a): pre-aim readiness on crosshair_angle_deg at t0
    print("Slice (a) — pre-aim readiness (crosshair angle at t0):")
    near = df[df["crosshair_angle_deg"] <= NEAR_ANGLE_DEG]
    wide = df[df["crosshair_angle_deg"] > NEAR_ANGLE_DEG]
    print(fmt(f"near angle (<= {NEAR_ANGLE_DEG:g} deg)", near))
    print(fmt(f"wide angle (> {NEAR_ANGLE_DEG:g} deg)", wide))
    print()

    # Slice (b): static vs moving on player_velocity_ups
    print("Slice (b) — static vs moving while holding:")
    static = df[df["player_velocity_ups"] <= STATIC_VEL_UPS]
    moving = df[df["player_velocity_ups"] > STATIC_VEL_UPS]
    print(fmt(f"static (vel <= {STATIC_VEL_UPS:g} ups)", static))
    print(fmt(f"moving (vel > {STATIC_VEL_UPS:g} ups)", moving))
    print("=" * 64)


if __name__ == "__main__":
    main()
