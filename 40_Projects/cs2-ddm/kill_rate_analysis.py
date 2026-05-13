#!/usr/bin/env python3
"""
Kill rate normalization analysis.

Re-runs demos via attempts_mode to track both hits and misses, then
prints a per-player kill rate comparison table.

Usage:
    python kill_rate_analysis.py                # process demos + save *_attempts.csv
    python kill_rate_analysis.py --load-only    # load existing *_attempts.csv, skip demo processing

Output per player (when demo processing):
    {player}_attempts.csv  — all duel attempts with was_killed + bullets columns

Comparison table printed to stdout in both modes.
"""
from __future__ import annotations

import argparse
import dataclasses
import itertools
import os
import sys
from typing import List

import pandas as pd

from ddm_analyzer import DDMAnalyzer
from duel_attempts import DuelAttempt
import db_utils
from config import DB_PATH

# ── Player registry ───────────────────────────────────────────────────────────
# Format: player_name → (steamid, [demo_paths])
# Demo paths must be absolute or relative to the working directory.
# To add a player: copy the donk example and fill in steamid + demo list.
#
# Example for another player:
# "shoke": (76561198XXXXXXXXX, [r"path\to\shoke1.dem", r"path\to\shoke2.dem"]),

_DEMO_BASE = r"D:\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo"

PLAYERS: dict[str, tuple[int, list[str]]] = {
    "donk": (
        76561198386265483,
        [
            rf"{_DEMO_BASE}\donk1.dem",
            rf"{_DEMO_BASE}\ancient1.dem",
            rf"{_DEMO_BASE}\ancient2.dem",
            rf"{_DEMO_BASE}\ancient3.dem",
            rf"{_DEMO_BASE}\mirage1.dem",
            rf"{_DEMO_BASE}\mirage2.dem",
            rf"{_DEMO_BASE}\mirage3.dem",
        ],
    ),
    # Add other players here when demo files and steamids are available:
    # "shoke": (76561198XXXXXXXXX, [rf"{_DEMO_BASE}\shoke1.dem"]),
    # "karrigan": (76561197XXXXXXXXX, [rf"{_DEMO_BASE}\karrigan1.dem"]),
    # "strogo": (76561198XXXXXXXXX, [rf"{_DEMO_BASE}\strogo1.dem"]),
    # "abdra": (76561198XXXXXXXXX, [rf"{_DEMO_BASE}\abdra1.dem"]),
}


def run_player(name: str, steamid: int, demo_paths: List[str]) -> List[DuelAttempt]:
    all_attempts: List[DuelAttempt] = []
    for demo_path in demo_paths:
        if not os.path.exists(demo_path):
            print(f"  [SKIP] {os.path.basename(demo_path)} not found", file=sys.stderr)
            continue
        print(f"  Processing {os.path.basename(demo_path)} ...")
        match_id = f"{name}_{os.path.splitext(os.path.basename(demo_path))[0]}"
        try:
            analyzer = DDMAnalyzer(
                demo_path=demo_path,
                player_steamid=steamid,
                match_id=match_id,
            )
            _, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)
            kills = sum(a.was_killed for a in attempts)
            print(f"    → {len(attempts)} attempts ({kills} kills, {len(attempts) - kills} misses)")
            all_attempts.extend(attempts)
            save_attempts(name, attempts, match_id=match_id)
        except Exception as e:
            print(f"  [ERROR] {os.path.basename(demo_path)}: {e}", file=sys.stderr)
    return all_attempts


def save_attempts(name: str, attempts: List[DuelAttempt], match_id: str) -> None:
    """Append+dedup by match_id — аналог csv_utils.save_results() (D-06).

    match_id обязателен — без него невозможно гарантировать корректный dedup.
    """
    if not attempts:
        return
    rows = pd.DataFrame([dataclasses.asdict(a) for a in attempts])
    path = f"{name}_attempts.csv"
    if os.path.exists(path) and os.path.getsize(path) > 0:
        try:
            existing = pd.read_csv(path, dtype=str)
            if "match_id" in existing.columns:
                existing = existing[existing["match_id"].astype(str) != str(match_id)]
            combined = pd.concat([existing, rows.astype(str)], ignore_index=True)
        except Exception as e:
            print(f"  [WARNING] Could not read existing {path}: {e}. Aborting save to prevent data loss.")
            return  # do not overwrite a file we cannot read
    else:
        combined = rows
    combined.to_csv(path, index=False)
    db_utils.save_to_db(combined, DB_PATH, "duel_attempts", match_id)
    print(f"  -> Saved {len(rows)} rows for match_id={match_id} (CSV total: {len(combined)} rows).")


def load_attempts(name: str) -> pd.DataFrame:
    path = f"{name}_attempts.csv"
    if not os.path.exists(path):
        return pd.DataFrame()
    return pd.read_csv(path)


def print_comparison_table(dfs: dict[str, pd.DataFrame]) -> None:
    print()
    print("=" * 72)
    print("  Kill Rate + First-Burst Hit Rate by Engagement Type")
    print("=" * 72)

    for eng_type in ("peek", "hold"):
        rows = []
        for name, df in dfs.items():
            sub = df[df["engagement_type"] == eng_type]
            total = len(sub)
            if total == 0:
                continue
            kills = int(sub["was_killed"].sum())
            kill_pct = 100.0 * kills / total
            fired = int(sub["bullets_fired"].sum())
            hit = int(sub["bullets_hit"].sum())
            hit_pct = (100.0 * hit / fired) if fired else 0.0
            rows.append((name, total, kills, kill_pct, fired, hit, hit_pct))

        if not rows:
            continue

        print(f"\n  {eng_type.upper()} engagements")
        print(f"  {'Player':<12} {'Att':>5} {'Kills':>6} {'Kill%':>7} "
              f"{'Fired':>6} {'Hit':>5} {'Hit%':>6}")
        print(f"  {'-'*12} {'-'*5} {'-'*6} {'-'*7} {'-'*6} {'-'*5} {'-'*6}")
        for name, total, kills, kpct, fired, hit, hpct in sorted(rows, key=lambda x: -x[3]):
            print(f"  {name:<12} {total:>5} {kills:>6} {kpct:>6.1f}% "
                  f"{fired:>6} {hit:>5} {hpct:>5.1f}%")

    print()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--load-only", action="store_true",
                        help="Skip demo processing; load existing *_attempts.csv files")
    args = parser.parse_args()

    dfs: dict[str, pd.DataFrame] = {}

    for name, (steamid, demo_paths) in PLAYERS.items():
        print(f"\n[{name}]")
        if args.load_only:
            df = load_attempts(name)
            if df.empty:
                print(f"  No {name}_attempts.csv found — skipping.")
                continue
            print(f"  Loaded {len(df)} rows from {name}_attempts.csv")
        else:
            attempts = run_player(name, steamid, demo_paths)
            df = pd.DataFrame([dataclasses.asdict(a) for a in attempts]) if attempts else pd.DataFrame()

        if not df.empty:
            dfs[name] = df

    if dfs:
        print_comparison_table(dfs)
    else:
        print("\nNo data loaded. Run without --load-only to process demos,")
        print("or add {player}_attempts.csv files first.")


if __name__ == "__main__":
    main()
