"""Full corpus rebatch driver — 132 remaining demos after top-10.

Reads demo list from full_corpus_demo_list.txt (tab-separated:
demo_name<TAB>full_path<TAB>pre_fix_row_count).

Sequential per-demo invocation of multi_player_analyze.py with UTF-8 env.
Each demo: roster extraction + 10-player sequential analysis. Per-demo
pre-fix rows are DELETED before re-batch (idempotent — safe to restart
after a crash mid-list, but currently does NOT skip already-rebatched
demos; that logic could be added if needed).

Log: rebatch_full.log (live tail).
Stop on first failure (exit 1) so we don't bury crashes in long batches.

ETA: ~17 min/demo × 132 demos ≈ 37 hours.
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.resolve()
DB = REPO / "analytics.db"
LIST_FILE = REPO / "full_corpus_demo_list.txt"
LOG = REPO / "rebatch_full.log"

UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def delete_demo_rows(demo_name: str) -> int:
    conn = sqlite3.connect(str(DB))
    n = conn.execute(
        "SELECT COUNT(*) FROM engagements WHERE demo_name=?", (demo_name,)
    ).fetchone()[0]
    conn.execute("DELETE FROM engagements WHERE demo_name=?", (demo_name,))
    conn.execute("DELETE FROM duel_attempts WHERE demo_name=?", (demo_name,))
    conn.commit()
    conn.close()
    return n


def already_done(demo_name: str, min_players: int = 8) -> bool:
    """Return True if demo already has post-fix rows for at least min_players
    distinct steamids. Allows clean pause+resume: kill driver anytime, restart
    same script — already-done demos skipped, partial demos (<8 players)
    re-run from clean state. min_players=8 tolerates 2 missing roster slots
    (spectators/coaches/AFK joiners that DDMAnalyzer may not analyze)."""
    conn = sqlite3.connect(str(DB))
    n = conn.execute(
        "SELECT COUNT(DISTINCT player_steamid) FROM engagements "
        "WHERE demo_name=? AND t1_source IS NOT NULL "
        "AND player_steamid IS NOT NULL",
        (demo_name,),
    ).fetchone()[0]
    conn.close()
    return n >= min_players


def main() -> int:
    if not LIST_FILE.exists():
        log(f"FAIL: {LIST_FILE.name} not found")
        return 1

    demos: list[tuple[str, str, int]] = []
    for line in LIST_FILE.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        demos.append((parts[0], parts[1], int(parts[2])))

    total = len(demos)
    log(f"\n{'=' * 60}")
    log(f"FULL CORPUS REBATCH — {total} demos, expected ~17min/demo")
    log(f"Started: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'=' * 60}\n")

    t_start = time.time()
    for i, (name, path, prefix_rows) in enumerate(demos, 1):
        elapsed_min = (time.time() - t_start) / 60
        log(f"\n{'=' * 60}")
        log(f"DEMO {i}/{total}: {name}  (pre-fix rows: {prefix_rows})")
        log(f"Elapsed so far: {elapsed_min:.1f} min")
        log(f"{'=' * 60}")

        if already_done(name):
            log(f"SKIP {i}/{total}: {name} — already has post-fix rows for >=8 players (resume safe)")
            continue

        if not Path(path).exists():
            log(f"FAIL: demo file not found: {path}")
            return 1

        deleted = delete_demo_rows(name)
        log(f"Deleted {deleted} pre-fix rows for {name}")

        t0 = time.time()
        with open(LOG, "a", encoding="utf-8") as out_fh:
            result = subprocess.run(
                [sys.executable, "multi_player_analyze.py", path],
                cwd=str(REPO),
                env=UTF8_ENV,
                stdout=out_fh,
                stderr=subprocess.STDOUT,
            )
        dt = time.time() - t0
        log(f"\nDemo {i}/{total} done in {dt:.1f}s (exit {result.returncode})")
        if result.returncode != 0:
            log(f"FAILED on {path}")
            return result.returncode

    total_min = (time.time() - t_start) / 60
    log(f"\n{'=' * 60}")
    log(f"ALL {total} DEMOS COMPLETE in {total_min:.1f} min")
    log(f"Finished: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log(f"{'=' * 60}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
