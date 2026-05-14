"""One-shot, idempotent backfill of engagements.round_number from re-parsed
round_start events.

Phase v2-interpretation-narrative D-02. Operator-run, NOT CI:
~5 min/demo × N demos. Re-runnable: only updates rows WHERE round_number IS NULL.

Usage:

    python scripts/backfill_round_number.py \
        --db analytics.db \
        --demo-dir for_analysis/spirit for_analysis/faze \
        [--dry-run]

The script:
1. Selects DISTINCT demo_name FROM engagements WHERE round_number IS NULL.
2. For each demo, locates the .dem file in any of --demo-dir directories.
3. Re-parses round_start events; bisect_right(round_start_ticks, t0) gives the
   1-indexed round_number.
4. UPDATEs engagements.round_number for matching rows in a per-demo transaction.

In --dry-run mode, prints the work plan without writing to the DB.
"""
from __future__ import annotations

import argparse
import bisect
import sqlite3
from contextlib import closing
from pathlib import Path


def backfill(db_path: str, demo_dirs: list[str], dry_run: bool = False) -> dict:
    """Run the round_number backfill.

    Returns
    -------
    dict
        Stats: ``{demos_processed: int, rows_updated: int,
        demos_missing: list[str]}``.

    Notes
    -----
    Idempotent: only ``WHERE round_number IS NULL`` rows are touched. Re-running
    after a partial completion resumes cleanly. ``dry_run=True`` still walks the
    DB and reports the plan but does NOT call ``demoparser2`` or UPDATE rows.
    """
    stats: dict = {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}
    with closing(sqlite3.connect(db_path)) as conn:
        # Guard against legacy DBs that haven't run db_utils.init_db() yet.
        # Acceptance criterion: dry-run on any DB must not crash.
        eng_exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='engagements'"
        ).fetchone()
        if eng_exists is None:
            return stats
        cols = {c[1] for c in conn.execute(
            "PRAGMA table_info(engagements)"
        ).fetchall()}
        if "round_number" not in cols or "demo_name" not in cols:
            print(
                "Warning: engagements table missing round_number or demo_name column. "
                "Run db_utils.init_db(db_path) first to apply Wave 0 migration."
            )
            return stats
        cur = conn.execute(
            """
            SELECT DISTINCT demo_name FROM engagements
            WHERE round_number IS NULL AND demo_name IS NOT NULL
            """
        )
        demos = [r[0] for r in cur.fetchall()]
        for demo_name in demos:
            demo_path = None
            # Some legacy rows store demo_name WITHOUT .dem extension while newer
            # rows (Phase 10a multi-player path) store WITH .dem. Try both.
            name_variants = [demo_name]
            if not demo_name.endswith(".dem"):
                name_variants.append(demo_name + ".dem")
            for d in demo_dirs:
                for name in name_variants:
                    candidate = Path(d) / name
                    if candidate.exists():
                        demo_path = candidate
                        break
                if demo_path is not None:
                    break
            if demo_path is None:
                stats["demos_missing"].append(demo_name)
                continue
            if dry_run:
                n_rows = conn.execute(
                    "SELECT COUNT(*) FROM engagements "
                    "WHERE demo_name = ? AND round_number IS NULL",
                    (demo_name,),
                ).fetchone()[0]
                print(
                    f"[dry-run] would re-parse {demo_name} and update {n_rows} rows"
                )
                stats["rows_updated"] += n_rows
                stats["demos_processed"] += 1
                continue

            # Real run — import demoparser2 lazily so dry-run / unit tests
            # don't pay the import cost.
            from demoparser2 import DemoParser  # type: ignore[import-not-found]

            parser = DemoParser(str(demo_path))
            events = parser.parse_events(["round_start"])
            rs_df = next((df for name, df in events if name == "round_start"), None)
            if rs_df is None or rs_df.empty:
                continue
            round_start_ticks = sorted(rs_df["tick"].astype(int).tolist())
            with conn:
                rows = conn.execute(
                    "SELECT rowid, t0_manual_tick FROM engagements "
                    "WHERE demo_name = ? AND round_number IS NULL",
                    (demo_name,),
                ).fetchall()
                for rid, t0 in rows:
                    if t0 is None:
                        continue
                    rn = bisect.bisect_right(round_start_ticks, int(t0))
                    conn.execute(
                        "UPDATE engagements SET round_number = ? WHERE rowid = ?",
                        (rn, rid),
                    )
                    stats["rows_updated"] += 1
            stats["demos_processed"] += 1
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(prog="backfill_round_number")
    parser.add_argument("--db", default="analytics.db")
    parser.add_argument(
        "--demo-dir",
        nargs="+",
        required=True,
        help="One or more directories containing .dem files",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Enumerate work without writing",
    )
    args = parser.parse_args()
    stats = backfill(args.db, args.demo_dir, dry_run=args.dry_run)
    print(
        f"Demos processed: {stats['demos_processed']}, "
        f"rows updated: {stats['rows_updated']}"
    )
    if stats["demos_missing"]:
        print(f"Demos missing on disk: {len(stats['demos_missing'])}")
        for n in stats["demos_missing"][:10]:
            print(f"  - {n}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
