"""
Tests for db_utils.py — SQLite persistence layer (Plan 06-03).
"""
import sqlite3
from contextlib import closing
import pandas as pd
import pytest

import db_utils


# ── helpers ──────────────────────────────────────────────────────────────────

def _sample_df(match_id: str = "match1", n: int = 2) -> pd.DataFrame:
    return pd.DataFrame({
        "match_id": [match_id] * n,
        "player_steamid": [76561198386265483] * n,
        "map_name": ["de_ancient"] * n,
        "rt_visible_to_hit_ms": [250.0 + i * 10 for i in range(n)],
    })


# ── Tests for _table_exists ───────────────────────────────────────────────────

def test_table_exists_returns_false_for_missing_table(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        assert db_utils._table_exists(conn, "engagements") is False


def test_table_exists_returns_true_after_table_created(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE engagements (id INTEGER PRIMARY KEY)")
        assert db_utils._table_exists(conn, "engagements") is True


# ── Tests for save_to_db ─────────────────────────────────────────────────────

def test_save_to_db_creates_table_and_inserts_rows(tmp_path):
    db = str(tmp_path / "test.db")
    df = _sample_df()
    db_utils.save_to_db(df, db, "engagements", "match1")
    with closing(sqlite3.connect(db)) as conn:
        result = pd.read_sql("SELECT * FROM engagements", conn)
    assert len(result) == 2
    assert set(result.columns) >= {"match_id", "player_steamid", "rt_visible_to_hit_ms"}


def test_save_to_db_same_match_id_replaces_old_rows(tmp_path):
    """Idempotency: re-saving same match_id keeps N rows, not 2N."""
    db = str(tmp_path / "test.db")
    df = _sample_df(n=2)
    db_utils.save_to_db(df, db, "engagements", "match1")
    db_utils.save_to_db(df, db, "engagements", "match1")
    with closing(sqlite3.connect(db)) as conn:
        result = pd.read_sql("SELECT * FROM engagements", conn)
    assert len(result) == 2


def test_save_to_db_different_match_id_appends(tmp_path):
    """Different match_ids accumulate — rows from match1 survive after match2 write."""
    db = str(tmp_path / "test.db")
    db_utils.save_to_db(_sample_df("match1", 2), db, "engagements", "match1")
    db_utils.save_to_db(_sample_df("match2", 3), db, "engagements", "match2")
    with closing(sqlite3.connect(db)) as conn:
        result = pd.read_sql("SELECT * FROM engagements", conn)
    assert len(result) == 5


def test_save_to_db_corrupted_db_prints_warning_and_does_not_crash(tmp_path, capsys):
    """Corrupted DB path should print a warning and return cleanly."""
    corrupted = str(tmp_path / "corrupted.db")
    with open(corrupted, "w") as f:
        f.write("this is not a sqlite database\x00\x01\x02")
    df = _sample_df()
    db_utils.save_to_db(df, corrupted, "engagements", "match1")
    captured = capsys.readouterr()
    assert "Warning" in captured.out


def test_save_to_db_query_by_player_steamid(tmp_path):
    """After save, SQL query by player_steamid returns correct rows."""
    db = str(tmp_path / "test.db")
    df = pd.DataFrame({
        "match_id": ["match1", "match1"],
        "player_steamid": [76561198386265483, 99999999999],
        "rt_visible_to_hit_ms": [250.0, 310.0],
    })
    db_utils.save_to_db(df, db, "engagements", "match1")
    with closing(sqlite3.connect(db)) as conn:
        result = pd.read_sql(
            "SELECT * FROM engagements WHERE player_steamid = ?",
            conn,
            params=(76561198386265483,),
        )
    assert len(result) == 1
    assert result.iloc[0]["player_steamid"] == 76561198386265483


def test_csv_sqlite_row_parity(tmp_path):
    """SC4: CSV and SQLite must have the same column sets and row counts."""
    db = str(tmp_path / "test.db")
    csv_path = str(tmp_path / "test.csv")
    df = pd.DataFrame({
        "match_id": ["match1", "match1"],
        "player_steamid": [76561198386265483, 76561198386265483],
        "map_name": ["de_ancient", "de_ancient"],
        "rt_visible_to_hit_ms": [250.0, 310.0],
    })
    df.to_csv(csv_path, index=False)
    db_utils.save_to_db(df, db, "engagements", "match1")
    csv_result = pd.read_csv(csv_path)
    with closing(sqlite3.connect(db)) as conn:
        db_result = pd.read_sql("SELECT * FROM engagements", conn)
    assert set(csv_result.columns) == set(db_result.columns)
    assert len(csv_result) == len(db_result)


# ── Integration: save_attempts wires save_to_db ───────────────────────────────

def test_save_attempts_calls_save_to_db(tmp_path, monkeypatch):
    """save_attempts() must call db_utils.save_to_db with table='duel_attempts'."""
    from duel_attempts import DuelAttempt
    import kill_rate_analysis
    from unittest.mock import MagicMock

    mock_db = MagicMock()
    monkeypatch.setattr(kill_rate_analysis, "db_utils", mock_db)
    # Also redirect CSV write so we don't need a real path
    monkeypatch.chdir(tmp_path)

    attempt = DuelAttempt(
        match_id="match1",
        map_name="de_dust2",
        t0_tick=100,
        enemy_steamid=123,
        was_killed=True,
        bullets_fired=5,
        bullets_hit=3,
        engagement_type="peek",
        player_velocity_ups=100.0,
        crosshair_angle_deg=5.0,
        player_steamid=76561198386265483,
    )
    kill_rate_analysis.save_attempts("test", [attempt], match_id="match1")
    mock_db.save_to_db.assert_called_once()
    call_args = mock_db.save_to_db.call_args
    assert call_args[0][2] == "duel_attempts"


# ── Tests for init_db (Task 07-01) ───────────────────────────────────────────

def test_init_db_wal_mode(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode == "wal"


def test_init_db_idempotent(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    db_utils.init_db(db)  # should not raise


def test_init_db_creates_processed_matches(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(processed_matches)").fetchall()}
    assert {"demo_filename", "player_steamid", "match_id", "processed_at"} <= cols


def test_init_db_creates_duel_attempts(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        exists = db_utils._table_exists(conn, "duel_attempts")
    assert exists is True


def test_migrate_schema_adds_demo_name(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE engagements (match_id TEXT, rt REAL)")
        conn.commit()
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
    assert "demo_name" in cols


def test_migrate_schema_adds_player_steamid(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE engagements (match_id TEXT, rt REAL)")
        conn.commit()
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
    assert "player_steamid" in cols


def test_migrate_schema_idempotent(tmp_path):
    db = str(tmp_path / "test.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            "CREATE TABLE engagements (match_id TEXT, demo_name TEXT, player_steamid INTEGER)"
        )
        conn.commit()
    db_utils.init_db(db)
    db_utils.init_db(db)  # should not raise


def test_is_processed_returns_false_when_missing(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    assert db_utils.is_processed(db, "demo.dem", 123) is False


def test_is_processed_returns_true_after_mark(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    db_utils.mark_processed(db, "demo.dem", 123, 1)
    assert db_utils.is_processed(db, "demo.dem", 123) is True


def test_mark_processed_idempotent(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    db_utils.mark_processed(db, "demo.dem", 123, 1)
    db_utils.mark_processed(db, "demo.dem", 123, 2)  # INSERT OR REPLACE — no IntegrityError


def test_get_next_match_id_empty_db(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    assert db_utils.get_next_match_id(db) == 1


def test_get_next_match_id_from_engagements(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("INSERT INTO engagements (match_id) VALUES (5)")
        conn.commit()
    assert db_utils.get_next_match_id(db) == 6


def test_get_next_match_id_takes_max_across_both_tables(tmp_path):
    db = str(tmp_path / "test.db")
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("INSERT INTO engagements (match_id) VALUES (3)")
        conn.execute("INSERT INTO duel_attempts (match_id) VALUES (7)")
        conn.commit()
    assert db_utils.get_next_match_id(db) == 8


# ── Phase 7 additions ──────────────────────────────────────────────────────────

import threading


def test_wal_concurrent_writes(tmp_path):
    """4 threads simultaneously call mark_processed — WAL must handle all without error."""
    db = str(tmp_path / "concurrent.db")
    db_utils.init_db(db)

    errors = []

    def _write(i):
        try:
            db_utils.mark_processed(db, f"demo_{i}.dem", 100 + i, i)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=_write, args=(i,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"WAL concurrent write errors: {errors}"
    with closing(sqlite3.connect(db)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM processed_matches").fetchone()[0]
    assert count == 4, f"Expected 4 rows, got {count}"


def test_processed_matches_idempotency(tmp_path):
    """Double-marking same (demo, steamid) must result in 1 row, not IntegrityError."""
    db = str(tmp_path / "idem.db")
    db_utils.init_db(db)
    db_utils.mark_processed(db, "demo.dem", 12345, 1)
    db_utils.mark_processed(db, "demo.dem", 12345, 1)  # INSERT OR REPLACE — must not raise
    with closing(sqlite3.connect(db)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM processed_matches").fetchone()[0]
    assert count == 1, f"Expected 1 row after double-insert, got {count}"


def _mp_write_row(args):
    """Top-level worker for test_wal_concurrent_multiprocess (must be picklable on Windows)."""
    db_path, i = args
    import sqlite3
    from contextlib import closing
    with closing(sqlite3.connect(db_path, timeout=10)) as conn:
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO processed_matches "
                "(demo_filename, player_steamid, match_id, processed_at) VALUES (?,?,?,?)",
                (f"demo_{i}.dem", 1000 + i, i, "2026-01-01T00:00:00+00:00"),
            )


def test_wal_concurrent_multiprocess(tmp_path):
    """4 OS processes simultaneously write to analytics.db — WAL must handle all without error."""
    import multiprocessing

    db = str(tmp_path / "multiproc.db")
    db_utils.init_db(db)

    ctx = multiprocessing.get_context("spawn")
    with ctx.Pool(processes=4) as pool:
        pool.map(_mp_write_row, [(db, i) for i in range(1, 5)])

    with closing(sqlite3.connect(db)) as conn:
        count = conn.execute("SELECT COUNT(*) FROM processed_matches").fetchone()[0]
    assert count == 4, f"Expected 4 rows from 4 processes, got {count}"


# ── round_number column migration (kept post-v2 discard for future v1 use) ──


def test_round_number_migration_idempotent(tmp_path):
    """v2-00-02 — round_number column added on fresh + re-runs are no-op."""
    db = str(tmp_path / "round.db")
    db_utils.init_db(db)
    db_utils.init_db(db)  # idempotent re-run must not raise
    with closing(sqlite3.connect(db)) as conn:
        cols = {c[1] for c in conn.execute(
            "PRAGMA table_info(engagements)"
        ).fetchall()}
    assert "round_number" in cols


def test_round_number_migration_on_legacy_engagements(tmp_path):
    """v2-00-02 — adding round_number to a pre-existing engagements table works."""
    db = str(tmp_path / "legacy.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE engagements (match_id TEXT, rt REAL)")
        conn.commit()
    db_utils.init_db(db)
    with closing(sqlite3.connect(db)) as conn:
        cols = {c[1] for c in conn.execute(
            "PRAGMA table_info(engagements)"
        ).fetchall()}
    assert "round_number" in cols


def test_allowed_tables_set():
    """_ALLOWED_TABLES = exactly {engagements, duel_attempts, duel_episodes} (OF-2 updated)."""
    assert db_utils._ALLOWED_TABLES == {
        "engagements", "duel_attempts", "duel_episodes"
    }, f"Unexpected _ALLOWED_TABLES={db_utils._ALLOWED_TABLES}"


def test_save_to_db_rejects_unknown_table_still(tmp_path):
    """CR-01 invariant — unknown tables are rejected."""
    db = str(tmp_path / "reject.db")
    df = _sample_df()
    with pytest.raises(ValueError, match="Unknown table"):
        db_utils.save_to_db(df, db, "ddm_fits", "match1")
