"""
DDM Phase 10b Unlock Progress Tracker

Reads analytics.db and prints how close the corpus is to the Phase 10b unlock
criteria established by `/gsd-explore` 2026-05-08:

- >=30 distinct players with >=50 peek trials each
- >=600 total peek trials (population-level fit feasibility)
- Spike re-run feasibility checkpoint (~3000 peek trials = stricter target)

Run:  python bench/ddm_unlock_tracker.py
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "analytics.db"

# Phase 10b unlock criteria (from .planning/spikes/ez-pc-validation/SPEC.md routing)
TARGETS = {
    "players_50_peek": 30,        # distinct players with >=50 peek trials
    "players_100_peek": 30,       # distinct players with >=100 peek trials (Phase 10b ideal)
    "total_peek_trials": 600,     # population-level fit minimum
    "stricter_total_peek": 3000,  # per-player stability checkpoint
    "distinct_demos": 630,        # at ~5 peek/demo, 30 players * 21 demos
}

RT_CAP_MS = 1500.0  # Phase 6+ ungradeable gate


def progress_bar(current: int, target: int, width: int = 12) -> str:
    pct = current / target if target else 0.0
    filled = min(width, int(pct * width))
    bar = "=" * filled + ">" + "." * max(0, width - filled - 1)
    return f"[{bar[:width]}] {pct*100:5.1f}%"


def fmt_row(label: str, current: int, target: int) -> str:
    return f"  {label:<38} {current:>6} / {target:<6}  {progress_bar(current, target)}"


def main() -> None:
    if not DB_PATH.exists():
        print(f"ERROR: {DB_PATH} not found")
        return

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Players with >=50 peek trials (engagements table, with rt cap)
    n_players_50_peek = cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT player_steamid, COUNT(*) AS n
            FROM engagements
            WHERE engagement_type = 'peek'
              AND rt_visible_to_hit_ms IS NOT NULL
              AND rt_visible_to_hit_ms <= ?
            GROUP BY player_steamid
            HAVING n >= 50
        )
        """,
        (RT_CAP_MS,),
    ).fetchone()[0]

    n_players_100_peek = cur.execute(
        """
        SELECT COUNT(*) FROM (
            SELECT player_steamid, COUNT(*) AS n
            FROM engagements
            WHERE engagement_type = 'peek'
              AND rt_visible_to_hit_ms IS NOT NULL
              AND rt_visible_to_hit_ms <= ?
            GROUP BY player_steamid
            HAVING n >= 100
        )
        """,
        (RT_CAP_MS,),
    ).fetchone()[0]

    total_peek_trials = cur.execute(
        """
        SELECT COUNT(*) FROM engagements
        WHERE engagement_type = 'peek'
          AND rt_visible_to_hit_ms IS NOT NULL
          AND rt_visible_to_hit_ms <= ?
        """,
        (RT_CAP_MS,),
    ).fetchone()[0]

    distinct_demos = cur.execute(
        "SELECT COUNT(DISTINCT demo_name) FROM engagements"
    ).fetchone()[0]

    distinct_players = cur.execute(
        "SELECT COUNT(DISTINCT player_steamid) FROM engagements"
    ).fetchone()[0]

    # Hold engagement_type structural check
    n_hold_with_rt = cur.execute(
        """
        SELECT COUNT(*) FROM engagements
        WHERE engagement_type = 'hold'
          AND rt_visible_to_hit_ms IS NOT NULL
        """
    ).fetchone()[0]

    # Per-player breakdown
    per_player = cur.execute(
        """
        SELECT
            player_steamid,
            COUNT(CASE WHEN engagement_type = 'peek' AND rt_visible_to_hit_ms <= ? THEN 1 END) AS peek_n,
            COUNT(CASE WHEN engagement_type = 'hold' AND rt_visible_to_hit_ms IS NOT NULL THEN 1 END) AS hold_n,
            COUNT(DISTINCT demo_name) AS demos
        FROM engagements
        GROUP BY player_steamid
        ORDER BY peek_n DESC
        """,
        (RT_CAP_MS,),
    ).fetchall()

    conn.close()

    print()
    print("=" * 60)
    print("Phase 10b unlock progress  (target: >=30 players, ~600 trials)")
    print("=" * 60)
    print()
    print(fmt_row("Players >=50 peek trials:",  n_players_50_peek,  TARGETS["players_50_peek"]))
    print(fmt_row("Players >=100 peek trials:", n_players_100_peek, TARGETS["players_100_peek"]))
    print(fmt_row("Total peek trials:",         total_peek_trials,  TARGETS["total_peek_trials"]))
    print(fmt_row("Distinct demos analyzed:",   distinct_demos,     TARGETS["distinct_demos"]))
    print()
    print(f"  Distinct players in DB:                {distinct_players}")
    print(f"  Hold engagements with valid RT:        {n_hold_with_rt}  (structural gap if 0)")
    print()
    print("=" * 60)
    print("Stretch (per-player stability)")
    print("=" * 60)
    print(fmt_row("Total peek trials:", total_peek_trials, TARGETS["stricter_total_peek"]))
    print()

    if per_player:
        print("=" * 60)
        print("Per-player breakdown")
        print("=" * 60)
        print(f"  {'SteamID64':<20} {'peek_n':>8} {'hold_n':>8} {'demos':>8}")
        for sid, peek_n, hold_n, demos in per_player:
            mark = "*" if peek_n >= 50 else " "
            sid_str = str(sid) if sid is not None else "<NULL>"
            print(f"  {mark}{sid_str:<19} {peek_n:>8} {hold_n:>8} {demos:>8}")
        print(f"  (* = qualifies for Phase 10b player roster, peek_n >= 50)")
        print()

    # Verdict
    unlock_ready = (
        n_players_50_peek >= TARGETS["players_50_peek"]
        and total_peek_trials >= TARGETS["total_peek_trials"]
    )
    if unlock_ready:
        print("STATUS: Phase 10b unlock criteria MET — re-run spike "
              "(`python bench/ez_pc_validation.py`)")
    else:
        gap_players = max(0, TARGETS["players_50_peek"] - n_players_50_peek)
        gap_trials = max(0, TARGETS["total_peek_trials"] - total_peek_trials)
        print(f"STATUS: NOT yet — need {gap_players} more players (>=50 peek) "
              f"and {gap_trials} more peek trials")
    print()


if __name__ == "__main__":
    main()
