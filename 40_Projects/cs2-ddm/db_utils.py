"""
SQLite persistence helpers for the DDM reaction analysis pipeline.

Strategy: replace-or-append per match_id (idempotent re-runs), mirroring
the csv_utils.save_results() pattern.
"""

import sqlite3
from contextlib import closing
from typing import Union

import pandas as pd

# CR-01: whitelist allowed table names to prevent SQL injection via f-string interpolation
# Phase v2-interpretation-narrative D-09 / R-11: explicitly DOES NOT include `ddm_fits`
# (Phase 10a worktree leak guard — DDM dropped per project_ddm_validation_final_2026_05_12).
_ALLOWED_TABLES = {"engagements", "duel_attempts"}


def save_to_db(
    df: pd.DataFrame,
    db_path: str,
    table: str,
    match_id: Union[int, str],
) -> None:
    """Write DataFrame to SQLite table, replacing any existing rows for match_id.

    Idempotent: re-running with the same match_id keeps N rows, not 2N.
    Silently warns and returns on any database or I/O error.
    """
    if df.empty:
        return
    # CR-01: reject unknown table names before any SQL is executed
    if table not in _ALLOWED_TABLES:
        raise ValueError(f"Unknown table '{table}'. Allowed: {_ALLOWED_TABLES}")
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            # CR-02: wrap DELETE + to_sql in a single explicit transaction so that
            # a crash between the two operations cannot leave the table empty.
            with conn:
                if _table_exists(conn, table):
                    conn.execute(
                        f"DELETE FROM {table} WHERE match_id = ?",
                        (str(match_id),),
                    )
                df.to_sql(table, conn, if_exists="append", index=False)
                # conn.__exit__ commits; explicit conn.commit() not needed here
    except (sqlite3.DatabaseError, OSError, ValueError) as e:
        print(f"Warning: could not write to '{db_path}' table '{table}': {e}")


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Return True if the named table exists in the connected SQLite database."""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,),
    )
    return cur.fetchone() is not None


def init_db(db_path: str) -> None:
    """Initialize analytics.db: WAL mode + idempotent schema migration.

    Safe to call multiple times. WAL mode persists to DB file — subsequent
    connections inherit it automatically.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        with conn:
            _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migration. Adds columns/tables if missing."""
    # engagements: create if missing, then add new columns if absent
    conn.execute("""
        CREATE TABLE IF NOT EXISTS engagements (
            match_id TEXT,
            demo_name TEXT DEFAULT NULL,
            player_steamid INTEGER DEFAULT NULL
        )
    """)
    cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
    _eng_migrations = [
        ("demo_name", "TEXT DEFAULT NULL"),
        ("player_steamid", "INTEGER DEFAULT NULL"),
        ("map_name", "TEXT DEFAULT NULL"),
        ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
        ("round_time_s", "REAL DEFAULT NULL"),
        ("round_phase", "TEXT DEFAULT NULL"),
        # Phase v2-interpretation-narrative D-01: per-engagement attribution.
        # Backfilled for existing rows via scripts/backfill_round_number.py
        # (operator-run gate, NOT CI). 1-indexed; NULL for warmup engagements.
        ("round_number", "INTEGER DEFAULT NULL"),
    ]
    for col, col_def in _eng_migrations:
        if col not in cols:
            conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")

    # duel_attempts: create if missing (was absent from analytics.db after Phase 6)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS duel_attempts (
            match_id TEXT,
            map_name TEXT,
            demo_name TEXT,
            player_steamid INTEGER,
            t0_tick INTEGER,
            enemy_steamid INTEGER,
            was_killed INTEGER,
            bullets_fired INTEGER,
            bullets_hit INTEGER,
            engagement_type TEXT,
            player_velocity_ups REAL,
            crosshair_angle_deg REAL,
            hurt_victims_in_window TEXT,
            fires_in_cluster INTEGER
        )
    """)

    # processed_matches: idempotency tracker for batch runner
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_matches (
            demo_filename TEXT NOT NULL,
            player_steamid INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (demo_filename, player_steamid)
        )
    """)


def is_processed(db_path: str, demo_filename: str, player_steamid: int) -> bool:
    """Return True if (demo_filename, player_steamid) exists in processed_matches."""
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_matches WHERE demo_filename=? AND player_steamid=?",
            (demo_filename, player_steamid),
        ).fetchone()
        return row is not None


def mark_processed(
    db_path: str, demo_filename: str, player_steamid: int, match_id: int
) -> None:
    """Record that (demo_filename, player_steamid) has been processed."""
    from datetime import datetime, timezone
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO processed_matches
                   (demo_filename, player_steamid, match_id, processed_at)
                   VALUES (?, ?, ?, ?)""",
                (demo_filename, player_steamid, match_id,
                 datetime.now(timezone.utc).isoformat()),
            )


def get_next_match_id(db_path: str) -> int:
    """Return MAX(match_id) + 1 across engagements and duel_attempts tables.

    Returns 1 if both tables are empty or absent.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        r1 = conn.execute(
            "SELECT MAX(CAST(match_id AS INTEGER)) FROM engagements"
        ).fetchone()[0] if _table_exists(conn, "engagements") else None
        r2 = conn.execute(
            "SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_attempts"
        ).fetchone()[0] if _table_exists(conn, "duel_attempts") else None
        current_max = max(r1 or 0, r2 or 0)
        return current_max + 1


def force_reprocess_demo(db_path: str, demo_filename: str, player_steamid: int) -> int:
    """Delete all rows for a previously processed demo so it can be re-run.

    D-12: force mode deletes processed_matches record and all rows for that match_id.
    Returns the old match_id (0 if demo was not processed).
    """
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            row = conn.execute(
                "SELECT match_id FROM processed_matches WHERE demo_filename=? AND player_steamid=?",
                (demo_filename, player_steamid),
            ).fetchone()
            if row is None:
                return 0
            old_match_id = row[0]
            # L-03: cast to str — engagements/duel_attempts store match_id as TEXT
            conn.execute("DELETE FROM engagements WHERE match_id=?", (str(old_match_id),))
            conn.execute("DELETE FROM duel_attempts WHERE match_id=?", (str(old_match_id),))
            conn.execute(
                "DELETE FROM processed_matches WHERE demo_filename=? AND player_steamid=?",
                (demo_filename, player_steamid),
            )
            return old_match_id
