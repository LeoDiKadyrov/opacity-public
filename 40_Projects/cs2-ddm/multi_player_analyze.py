"""
Multi-player demo analyzer wrapper.

Each CS2 demo contains 10 players. The standard pipeline (`run_analysis.py`)
analyzes ONE player per run (hardcoded `PLAYER_STEAMID`). This wrapper extracts
all 10 SteamID64s from the demo and runs the pipeline for each, producing
per-player engagement rows in `analytics.db`.

Usage:
    python multi_player_analyze.py path/to/demo.dem
    python multi_player_analyze.py path/to/demo.dem --players 76561198386265483,76561197989430253
    python multi_player_analyze.py path/to/demo.dem --skip-existing

Idempotency: each (demo, player) combo gets a unique `match_id` so re-runs do
not overwrite earlier players' rows. With `--skip-existing`, players already
present in `engagements` for this demo are skipped.

Requires: same env as `run_analysis.py` (demoparser2, awpy, .tri files).
"""

from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from pathlib import Path
from typing import List

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

from ddm_analyzer import DDMAnalyzer
from csv_utils import save_results
from db_utils import get_next_match_id

DB_PATH = REPO_ROOT / "analytics.db"
CSV_PATH = REPO_ROOT / "cs2_engagement_analysis_results.csv"

# Spectator / coach SteamIDs sometimes show up as casters or referees — skip them.
# Add known non-player SIDs here as encountered.
EXCLUDE_SIDS: set[int] = set()


def extract_steamids(demo_path: str) -> List[int]:
    """Parse a demo and return distinct numeric SteamID64s seen on tick stream.

    Uses a minimal `parse_ticks(["steamid"])` call over an early tick window
    (~first 6400 ticks = first ~100 seconds at 64 tickrate) to capture the
    player roster without parsing the full demo.
    """
    from demoparser2 import DemoParser  # local import — keep startup cost low

    parser = DemoParser(demo_path)
    # parse_ticks defaults to all ticks; we keep it that way but only read steamid.
    # Demos with weird first-round joins may need a wider window.
    df = parser.parse_ticks(["steamid"])
    if df is None or df.empty:
        return []
    sids = (
        df["steamid"]
        .dropna()
        .astype("int64")
        .unique()
        .tolist()
    )
    sids = [int(s) for s in sids if s and int(s) > 1_000_000_000_000_000]  # SteamID64s are 17 digits
    return [s for s in sids if s not in EXCLUDE_SIDS]


def already_processed(demo_name: str, player_sid: int) -> bool:
    """Return True if this (demo, player) combo already has rows in engagements."""
    if not DB_PATH.exists():
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        n = cur.execute(
            """
            SELECT COUNT(*) FROM engagements
            WHERE demo_name = ? AND player_steamid = ?
            """,
            (demo_name, player_sid),
        ).fetchone()[0]
        return n > 0
    finally:
        conn.close()


def analyze_one(demo_path: str, player_sid: int, demo_name: str) -> int:
    """Run the standard pipeline for one (demo, player). Returns rows written."""
    match_id = get_next_match_id(str(DB_PATH))
    print(f"  [match_id={match_id}] running for player {player_sid}...")
    try:
        analyzer = DDMAnalyzer(
            demo_path,
            player_sid,
            match_id=match_id,
            tickrate=64,
            debug_prints=False,
            demo_name=demo_name,
        )
    except Exception as e:
        print(f"    ERROR initialising analyzer: {e}")
        return 0
    try:
        results_df, _ = analyzer.analyze_demo(bulk_mode=True)
    except Exception as e:
        print(f"    ERROR during analysis: {e}")
        return 0
    if results_df is None or results_df.empty:
        print(f"    no engagements found for {player_sid}")
        return 0
    save_results(results_df, str(CSV_PATH), match_id)
    return len(results_df)


def main() -> None:
    ap = argparse.ArgumentParser(description="Run analyzer pipeline for every player in a demo.")
    ap.add_argument("demo", help="Path to .dem file")
    ap.add_argument(
        "--players",
        help="Comma-separated SteamID64s. If omitted, all players in the demo are analyzed.",
    )
    ap.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip (demo, player) combos already present in engagements table.",
    )
    args = ap.parse_args()

    demo_path = str(Path(args.demo).expanduser().resolve())
    if not Path(demo_path).exists():
        print(f"ERROR: demo not found: {demo_path}")
        sys.exit(1)
    demo_name = Path(demo_path).name

    print(f"\n=== multi_player_analyze :: {demo_name} ===\n")

    if args.players:
        sids = [int(s.strip()) for s in args.players.split(",") if s.strip()]
        print(f"Using {len(sids)} player SIDs from --players flag")
    else:
        print("Extracting player roster from demo...")
        t0 = time.time()
        sids = extract_steamids(demo_path)
        print(f"Found {len(sids)} player SIDs in {time.time()-t0:.1f}s: {sids}")

    if not sids:
        print("No players to analyze. Exit.")
        return

    total_rows = 0
    summary: list[tuple[int, int, str]] = []
    for sid in sids:
        if args.skip_existing and already_processed(demo_name, sid):
            print(f"\n[skip] {sid} already in engagements for this demo")
            summary.append((sid, 0, "skipped"))
            continue
        print(f"\n--- Player {sid} ---")
        n = analyze_one(demo_path, sid, demo_name)
        total_rows += n
        summary.append((sid, n, "ok" if n > 0 else "empty"))

    print(f"\n=== {demo_name} done ===")
    print(f"Total engagement rows written: {total_rows}")
    print()
    print(f"  {'SteamID64':<20} {'rows':>8}  status")
    for sid, n, status in summary:
        print(f"  {sid:<20} {n:>8}  {status}")


if __name__ == "__main__":
    main()
