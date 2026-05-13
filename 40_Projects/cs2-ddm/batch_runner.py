"""
Parallel batch runner for DDM demo analysis.

Worker function is top-level (module-level) — required for Windows spawn
multiprocessing where child processes import this module directly.

Usage:
    from batch_runner import BatchRunner
    runner = BatchRunner(db_path="analytics.db", n_workers=8)
    results = runner.run(demo_paths, player_steamid=76561198386265483)
"""

from __future__ import annotations

import logging
import os
import sys
import traceback as _traceback
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from config import (
    DB_PATH,
    DEFAULT_BATCH_WORKERS,
    BATCH_INPUT_DIR,
    BATCH_ERRORS_LOG,
)
import db_utils


# ── Module-level logger ───────────────────────────────────────────────────────

def _get_batch_logger() -> logging.Logger:
    logger = logging.getLogger("BatchRunner")
    if not logger.handlers:
        fh = logging.FileHandler(BATCH_ERRORS_LOG, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        logger.addHandler(sh)
    logger.setLevel(logging.INFO)
    logger.propagate = False
    return logger


logger = _get_batch_logger()


# ── Top-level worker function (MUST stay module-level for Windows spawn) ──────

def analyze_demo_worker(args: Tuple[str, int, int, str, int]) -> Dict:
    """
    Worker callable for ProcessPoolExecutor.

    All arguments are plain picklable types (no DDMAnalyzer, no connection).
    DDMAnalyzer is instantiated INSIDE the worker process.

    Args:
        args: (demo_path, player_steamid, match_id, db_path, tickrate)

    Returns:
        dict with keys:
            status: "ok" | "error"
            match_id: int
            demo: str (demo stem name)
            engagements: int (0 on error)
            attempts: int (0 on error)
            error: str (only on error)
            traceback: str (only on error)
    """
    demo_path, player_steamid, match_id, db_path, tickrate = args

    demo_name = Path(demo_path).stem

    try:
        # Imports inside worker — clean namespace after Windows spawn
        import dataclasses

        import pandas as pd

        from ddm_analyzer import DDMAnalyzer
        import db_utils as _db

        # Ensure WAL mode on first worker DB touch (idempotent if already WAL)
        if db_path != ":memory:":
            try:
                import sqlite3 as _sq
                conn = _sq.connect(db_path, timeout=30)
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("PRAGMA busy_timeout=10000")
                conn.close()
            except Exception:
                pass  # If DB not accessible, DDMAnalyzer will fail with a clear error

        analyzer = DDMAnalyzer(
            demo_path=demo_path,
            player_steamid=player_steamid,
            match_id=match_id,
            tickrate=tickrate,
            debug_prints=False,
        )
        results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)

        # Inject demo_name into engagement rows already saved by analyze_demo()
        if not results_df.empty and match_id is not None and db_path != ":memory:":
            try:
                import sqlite3 as _sq2
                with _sq2.connect(db_path, timeout=30) as _c:
                    _c.execute(
                        "UPDATE engagements SET demo_name=? WHERE match_id=?",
                        (demo_name, str(match_id)),
                    )
            except Exception as _upd_err:
                # H-03: log instead of swallow — silent failure leaves demo_name=NULL permanently
                logger.warning(f"demo_name UPDATE failed for match_id={match_id}: {_upd_err}")

        # Save duel_attempts to DB (analyze_demo does NOT save these)
        n_attempts = 0
        if attempts:
            n_attempts = len(attempts)
            att_df = pd.DataFrame([dataclasses.asdict(a) for a in attempts])
            att_df["demo_name"] = demo_name
            _db.save_to_db(att_df, db_path, "duel_attempts", match_id)

        # Mark as processed AFTER all writes succeed
        _db.mark_processed(
            db_path, os.path.basename(demo_path), player_steamid, match_id
        )

        return {
            "status": "ok",
            "match_id": match_id,
            "demo": demo_name,
            "engagements": len(results_df),
            "attempts": n_attempts,
        }

    except Exception as exc:
        tb = _traceback.format_exc()
        return {
            "status": "error",
            "match_id": match_id,
            "demo": demo_name,
            "engagements": 0,
            "attempts": 0,
            "error": str(exc),
            "traceback": tb,
        }


# ── BatchRunner class ─────────────────────────────────────────────────────────

class BatchRunner:
    """Orchestrates parallel batch processing of .dem files.

    Usage:
        runner = BatchRunner(db_path=DB_PATH, n_workers=DEFAULT_BATCH_WORKERS)
        results = runner.run(
            demo_paths=[Path("for_analysis/demo1.dem"), ...],
            player_steamid=76561198386265483,
            tickrate=64,
            force_reprocess=False,
            progress_callback=None,  # callable(done: int, total: int, current: str)
        )
    """

    def __init__(
        self,
        db_path: str = DB_PATH,
        n_workers: int = DEFAULT_BATCH_WORKERS,
    ) -> None:
        self.db_path = db_path
        self.n_workers = n_workers

    def scan_demos(self, input_dir: Optional[str] = None) -> List[Path]:
        """Return sorted list of .dem files in input_dir (default: BATCH_INPUT_DIR)."""
        d = Path(input_dir or BATCH_INPUT_DIR)
        d.mkdir(parents=True, exist_ok=True)
        return sorted(d.glob("*.dem"))

    def filter_unprocessed(
        self,
        demo_paths: List[Path],
        player_steamid: int,
        force: bool = False,
    ) -> List[Path]:
        """Return demos not yet in processed_matches for this player.

        If force=True (D-12): deletes existing rows for already-processed demos
        via force_reprocess_demo() before returning the full list, so workers
        write fresh rows without duplicates.
        """
        if force:
            for p in demo_paths:
                db_utils.force_reprocess_demo(self.db_path, p.name, player_steamid)
            return list(demo_paths)
        return [
            p for p in demo_paths
            if not db_utils.is_processed(self.db_path, p.name, player_steamid)
        ]

    def pre_assign_match_ids(
        self, demos_to_process: List[Path]
    ) -> List[Tuple[int, Path]]:
        """Assign sequential match_ids in main thread BEFORE spawning workers.

        Prevents race conditions from 8 concurrent SELECT MAX(match_id)+1 calls.
        Returns list of (match_id, demo_path) pairs.
        """
        if not demos_to_process:
            return []
        next_id = db_utils.get_next_match_id(self.db_path)
        return [(next_id + i, p) for i, p in enumerate(demos_to_process)]

    def run(
        self,
        demo_paths: List[Path],
        player_steamid: int,
        tickrate: int = 64,
        force_reprocess: bool = False,
        progress_callback: Optional[object] = None,
    ) -> List[Dict]:
        """Process demos in parallel. Returns list of result dicts.

        progress_callback(done: int, total: int, current: str) — called after
        each completed future (from main thread or background thread).
        """
        import concurrent.futures

        # Ensure DB is initialized (WAL + schema) before dispatching workers
        db_utils.init_db(self.db_path)

        to_process = self.filter_unprocessed(demo_paths, player_steamid, force=force_reprocess)
        if not to_process:
            logger.info("All demos already processed — nothing to do.")
            return []

        assigned = self.pre_assign_match_ids(to_process)
        total = len(assigned)
        results: List[Dict] = []

        worker_args = [
            (str(p), player_steamid, mid, self.db_path, tickrate)
            for mid, p in assigned
        ]

        logger.info(f"Starting batch: {total} demos, {self.n_workers} workers")

        # Always resolve the worker function from the current sys.modules entry.
        # Streamlit hot-reload replaces sys.modules['batch_runner'] with a new
        # module object; if we hold a stale reference from the old module's
        # __globals__, pickle's identity check fails with PicklingError.
        _worker = sys.modules[__name__].analyze_demo_worker

        with concurrent.futures.ProcessPoolExecutor(
            max_workers=self.n_workers
        ) as pool:
            futures = {
                pool.submit(_worker, arg): arg[0]
                for arg in worker_args
            }
            done_count = 0
            for future in concurrent.futures.as_completed(futures):
                demo_path_str = futures[future]
                try:
                    result = future.result()
                except Exception as exc:
                    result = {
                        "status": "error",
                        "demo": Path(demo_path_str).stem,
                        "match_id": None,
                        "engagements": 0,
                        "attempts": 0,
                        "error": str(exc),
                        "traceback": _traceback.format_exc(),
                    }

                results.append(result)
                done_count += 1

                if result["status"] == "error":
                    err_msg = (
                        f"FAILED: {result.get('demo', demo_path_str)} — "
                        f"{result.get('error', 'unknown')}\n"
                        f"{result.get('traceback', '')}"
                    )
                    logger.error(err_msg)
                else:
                    logger.info(
                        f"[{done_count}/{total}] OK: {result['demo']} — "
                        f"{result['engagements']} engagements, "
                        f"{result['attempts']} attempts"
                    )

                if progress_callback is not None:
                    try:
                        progress_callback(
                            done_count, total, result.get("demo", "")
                        )
                    except Exception:
                        pass  # Never let UI callback crash the runner

        failed = [r for r in results if r["status"] == "error"]
        if failed:
            logger.warning(
                f"Batch complete: {len(failed)}/{total} demos failed. See {BATCH_ERRORS_LOG}."
            )
        else:
            logger.info(
                f"Batch complete: {total}/{total} demos processed successfully."
            )

        return results
