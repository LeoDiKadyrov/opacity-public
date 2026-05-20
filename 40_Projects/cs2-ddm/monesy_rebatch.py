"""Monesy rebatch driver — 21 demos, 2 phases.

Phase A (--phase a): monesy-only (~36min). Deletes legacy/stale monesy rows
per demo, runs multi_player_analyze with --players=MONESY_SID.

Phase B (--phase b): full roster (~6h). Runs multi_player_analyze with
--skip-existing so monesy (done in Phase A) is skipped; other 9 players run.

Both phases append to rebatch_monesy.log + monesy_report.md (markdown table,
appended per-demo for live tail).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.resolve()
DB = REPO / "analytics.db"
LIST_FILE = REPO / "monesy_demo_list.txt"
LOG = REPO / "rebatch_monesy.log"
REPORT = REPO / "monesy_report.md"
REPORT_B = REPO / "monesy_report_phase_b.md"
LOG_B = REPO / "rebatch_monesy_phase_b.log"

MONESY_SID = 76561198074762801

UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def extract_roster(demo_path: str) -> list[int]:
    """Return SteamID64 roster (first 6400 ticks) — copy of multi_player_analyze.extract_steamids."""
    from demoparser2 import DemoParser
    parser = DemoParser(demo_path)
    df = parser.parse_ticks(["steamid"], ticks=list(range(0, 6400)))
    if df is None or df.empty:
        return []
    sids = df["steamid"].dropna().astype("int64").unique().tolist()
    return [int(s) for s in sids if s and int(s) > 1_000_000_000_000_000]


_LOG_PATH = LOG
_REPORT_PATH = REPORT


def log(msg: str) -> None:
    with open(_LOG_PATH, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def report_append(line: str) -> None:
    with open(_REPORT_PATH, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def delete_monesy_rows(demo_name: str) -> int:
    conn = sqlite3.connect(str(DB))
    n = conn.execute(
        "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=?",
        (demo_name, MONESY_SID),
    ).fetchone()[0]
    conn.execute(
        "DELETE FROM engagements WHERE demo_name=? AND player_steamid=?",
        (demo_name, MONESY_SID),
    )
    conn.execute(
        "DELETE FROM duel_attempts WHERE demo_name=? AND player_steamid=?",
        (demo_name, MONESY_SID),
    )
    conn.commit()
    conn.close()
    return n


def monesy_done(demo_name: str) -> tuple[bool, int, int]:
    """Return (done_post_fix, n_rows, n_pre_aimed)."""
    conn = sqlite3.connect(str(DB))
    n_total = conn.execute(
        "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=?",
        (demo_name, MONESY_SID),
    ).fetchone()[0]
    n_post = conn.execute(
        "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=? "
        "AND t1_source IS NOT NULL",
        (demo_name, MONESY_SID),
    ).fetchone()[0]
    n_pre = conn.execute(
        "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=? "
        "AND t1_source='pre_aimed'",
        (demo_name, MONESY_SID),
    ).fetchone()[0]
    conn.close()
    return (n_total > 0 and n_post == n_total), n_post, n_pre


def all_done(demo_name: str, min_players: int = 8) -> bool:
    conn = sqlite3.connect(str(DB))
    n = conn.execute(
        "SELECT COUNT(DISTINCT player_steamid) FROM engagements "
        "WHERE demo_name=? AND t1_source IS NOT NULL "
        "AND player_steamid IS NOT NULL",
        (demo_name,),
    ).fetchone()[0]
    conn.close()
    return n >= min_players


def run_phase_a(demos: list[tuple[str, str]]) -> int:
    log(f"\n{'=' * 60}\nPHASE A — monesy-only ({MONESY_SID})\n{'=' * 60}\n")
    report_append(f"\n## Phase A — monesy-only ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
    report_append("| # | demo | rows | pre_aimed | min_ms | secs |")
    report_append("|-|-|-|-|-|-|")

    t_start = time.time()
    for i, (name, path) in enumerate(demos, 1):
        log(f"\n--- A {i}/{len(demos)}: {name} ---")
        done, n_post, n_pre = monesy_done(name)
        if done:
            log(f"SKIP: monesy already post-fix rows={n_post}")
            report_append(f"| {i} | {name} | {n_post} (skip) | {n_pre} | - | - |")
            continue

        deleted = delete_monesy_rows(name)
        log(f"deleted {deleted} stale/legacy monesy rows")

        if not Path(path).exists():
            log(f"FAIL: demo missing: {path}")
            return 1

        t0 = time.time()
        with open(_LOG_PATH, "a", encoding="utf-8") as out_fh:
            result = subprocess.run(
                [sys.executable, "multi_player_analyze.py", path,
                 "--players", str(MONESY_SID), "--skip-existing"],
                cwd=str(REPO), env=UTF8_ENV,
                stdout=out_fh, stderr=subprocess.STDOUT,
            )
        dt = time.time() - t0
        if result.returncode != 0:
            log(f"FAILED on {name} exit={result.returncode}")
            return result.returncode

        conn = sqlite3.connect(str(DB))
        n_rows = conn.execute(
            "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=?",
            (name, MONESY_SID)).fetchone()[0]
        n_pre = conn.execute(
            "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND player_steamid=? "
            "AND t1_source='pre_aimed'",
            (name, MONESY_SID)).fetchone()[0]
        min_ms = conn.execute(
            "SELECT MIN(rt_visible_to_aim_ms) FROM engagements WHERE demo_name=? "
            "AND player_steamid=? AND rt_visible_to_aim_ms IS NOT NULL",
            (name, MONESY_SID)).fetchone()[0]
        conn.close()
        log(f"done {dt:.1f}s rows={n_rows} pre_aimed={n_pre} min={min_ms}ms")
        report_append(
            f"| {i} | {name} | {n_rows} | {n_pre} | "
            f"{min_ms if min_ms is not None else '-'} | {dt:.0f} |"
        )

    total_min = (time.time() - t_start) / 60
    log(f"\nPHASE A done in {total_min:.1f}min")
    report_append(f"\n**Phase A finished:** {time.strftime('%Y-%m-%d %H:%M:%S')} (elapsed {total_min:.1f}min)\n")

    # aggregate monesy stats
    conn = sqlite3.connect(str(DB))
    agg = conn.execute(
        "SELECT COUNT(*), AVG(rt_visible_to_aim_ms), "
        "       MIN(rt_visible_to_aim_ms), "
        "       SUM(CASE WHEN t1_source='pre_aimed' THEN 1 ELSE 0 END), "
        "       SUM(CASE WHEN rt_visible_to_aim_ms <= 125 THEN 1 ELSE 0 END) "
        "FROM engagements WHERE player_steamid=? AND t1_source IS NOT NULL",
        (MONESY_SID,),
    ).fetchone()
    conn.close()
    n, mean, mn, npre, n_floor = agg
    report_append("### Aggregate (m0NESY post-fix across all monesy demos in DB)\n")
    report_append(f"- total engagements: **{n}**")
    report_append(f"- mean T0→T1: **{mean:.1f}ms**" if mean else "- mean: n/a")
    report_append(f"- min T0→T1: **{mn:.1f}ms**" if mn is not None else "- min: n/a")
    report_append(f"- pre_aimed rows: **{npre}** ({npre/n*100:.1f}%)" if n else "")
    report_append(f"- @ ≤125ms (legacy floor): **{n_floor}** ({n_floor/n*100:.1f}%)" if n else "")
    return 0


def run_phase_b(demos: list[tuple[str, str]]) -> int:
    log(f"\n{'=' * 60}\nPHASE B — full roster\n{'=' * 60}\n")
    report_append(f"\n## Phase B — full roster ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
    report_append("| # | demo | post_fix_sids | rows_total | secs |")
    report_append("|-|-|-|-|-|")

    t_start = time.time()
    for i, (name, path) in enumerate(demos, 1):
        log(f"\n--- B {i}/{len(demos)}: {name} ---")
        if all_done(name):
            log("SKIP: >=8 post-fix players already present")
            conn = sqlite3.connect(str(DB))
            sids = conn.execute(
                "SELECT COUNT(DISTINCT player_steamid) FROM engagements "
                "WHERE demo_name=? AND t1_source IS NOT NULL", (name,)).fetchone()[0]
            rows = conn.execute(
                "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND t1_source IS NOT NULL",
                (name,)).fetchone()[0]
            conn.close()
            report_append(f"| {i} | {name} | {sids} (skip) | {rows} | - |")
            continue

        if not Path(path).exists():
            log(f"FAIL: demo missing: {path}")
            return 1

        roster = extract_roster(path)
        non_monesy = [s for s in roster if s != MONESY_SID]
        if not non_monesy:
            log(f"WARN: no non-monesy SIDs extracted from {name}; skipping")
            report_append(f"| {i} | {name} | 0 (no-roster) | 0 | - |")
            continue
        log(f"roster {len(roster)} sids, passing {len(non_monesy)} non-monesy to subprocess")

        t0 = time.time()
        with open(_LOG_PATH, "a", encoding="utf-8") as out_fh:
            result = subprocess.run(
                [sys.executable, "multi_player_analyze.py", path,
                 "--players", ",".join(str(s) for s in non_monesy),
                 "--skip-existing"],
                cwd=str(REPO), env=UTF8_ENV,
                stdout=out_fh, stderr=subprocess.STDOUT,
            )
        dt = time.time() - t0
        if result.returncode != 0:
            log(f"FAILED on {name} exit={result.returncode}")
            return result.returncode

        conn = sqlite3.connect(str(DB))
        sids = conn.execute(
            "SELECT COUNT(DISTINCT player_steamid) FROM engagements "
            "WHERE demo_name=? AND t1_source IS NOT NULL", (name,)).fetchone()[0]
        rows = conn.execute(
            "SELECT COUNT(*) FROM engagements WHERE demo_name=? AND t1_source IS NOT NULL",
            (name,)).fetchone()[0]
        conn.close()
        log(f"done {dt:.1f}s sids={sids} rows={rows}")
        report_append(f"| {i} | {name} | {sids} | {rows} | {dt:.0f} |")

    total_min = (time.time() - t_start) / 60
    log(f"\nPHASE B done in {total_min:.1f}min")
    report_append(f"\n**Phase B finished:** {time.strftime('%Y-%m-%d %H:%M:%S')} (elapsed {total_min:.1f}min)\n")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", choices=["a", "b"], required=True)
    args = ap.parse_args()

    global _LOG_PATH, _REPORT_PATH
    if args.phase == "b":
        _LOG_PATH = LOG_B
        _REPORT_PATH = REPORT_B

    if not LIST_FILE.exists():
        log(f"FAIL: {LIST_FILE.name} missing")
        return 1

    demos: list[tuple[str, str]] = []
    for line in LIST_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        demos.append((parts[0], parts[1]))

    log(f"\n{'#' * 60}")
    log(f"MONESY REBATCH — phase {args.phase.upper()} — {len(demos)} demos")
    log(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'#' * 60}")

    if args.phase == "a":
        return run_phase_a(demos)
    else:
        return run_phase_b(demos)


if __name__ == "__main__":
    sys.exit(main())
