"""Phase v2-interpretation-narrative Wave 0 — backfill script idempotency
+ dry-run + missing-demo handling.

Real-demo integration is deferred to Wave 4 manual operator gate (R-2):
re-parsing 5557 rows × ~5min/demo = ~6.5h. Wave 0 only proves wiring +
dry-run + idempotency on no-NULL-rows.
"""
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
from backfill_round_number import backfill  # noqa: E402


@pytest.fixture
def empty_db_with_missing_demo(tmp_path):
    """Single engagement row pointing at a demo file that doesn't exist on disk."""
    db = str(tmp_path / "missing.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            """CREATE TABLE engagements (
                demo_name TEXT,
                t0_manual_tick INTEGER,
                round_number INTEGER
            )"""
        )
        conn.execute(
            "INSERT INTO engagements VALUES ('missing.dem', 100, NULL)"
        )
        conn.commit()
    return db


def test_backfill_dry_run_no_writes(empty_db_with_missing_demo):
    """Demo missing on disk → counted as missing, no DB writes occur."""
    stats = backfill(
        empty_db_with_missing_demo, demo_dirs=["/nonexistent"], dry_run=True
    )
    assert stats["rows_updated"] == 0
    assert "missing.dem" in stats["demos_missing"]


def test_backfill_idempotent_on_no_null_rows(tmp_path):
    """All rows already have round_number → backfill is a no-op (0 demos to process)."""
    db = str(tmp_path / "filled.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            """CREATE TABLE engagements (
                demo_name TEXT,
                t0_manual_tick INTEGER,
                round_number INTEGER
            )"""
        )
        conn.execute("INSERT INTO engagements VALUES ('any.dem', 100, 5)")
        conn.commit()
    stats = backfill(db, demo_dirs=["/nonexistent"], dry_run=False)
    assert stats["rows_updated"] == 0
    assert stats["demos_processed"] == 0
    assert stats["demos_missing"] == []


def test_backfill_empty_db_returns_zeros(tmp_path):
    """Empty engagements table → all-zero stats, no exceptions."""
    db = str(tmp_path / "empty.db")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            """CREATE TABLE engagements (
                demo_name TEXT,
                t0_manual_tick INTEGER,
                round_number INTEGER
            )"""
        )
        conn.commit()
    stats = backfill(db, demo_dirs=["/nonexistent"], dry_run=True)
    assert stats == {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}


def test_backfill_legacy_db_without_round_number_does_not_crash(tmp_path, capsys):
    """Pre-Wave-0 DB lacking round_number column → graceful warning, exit clean."""
    db = str(tmp_path / "legacy.db")
    with closing(sqlite3.connect(db)) as conn:
        # Legacy schema: NO round_number column.
        conn.execute(
            "CREATE TABLE engagements (demo_name TEXT, t0_manual_tick INTEGER)"
        )
        conn.commit()
    stats = backfill(db, demo_dirs=["/nonexistent"], dry_run=True)
    out = capsys.readouterr().out
    assert "missing round_number" in out
    assert stats == {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}


def test_backfill_missing_engagements_table_does_not_crash(tmp_path):
    """Brand-new DB with no engagements table → return zero stats, no crash."""
    db = str(tmp_path / "fresh.db")
    # Touch the DB but do not create the engagements table.
    with closing(sqlite3.connect(db)) as conn:
        conn.execute("CREATE TABLE other (id INTEGER)")
        conn.commit()
    stats = backfill(db, demo_dirs=["/nonexistent"], dry_run=True)
    assert stats == {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}


def test_backfill_dry_run_reports_row_count(tmp_path, capsys, monkeypatch):
    """Dry-run prints '[dry-run] would re-parse ... update N rows' for each found demo."""
    db = str(tmp_path / "dryrun.db")
    demo_dir = tmp_path / "demos"
    demo_dir.mkdir()
    fake_demo = demo_dir / "real.dem"
    fake_demo.write_bytes(b"\x00fake-demo-not-parsed-in-dry-run")
    with closing(sqlite3.connect(db)) as conn:
        conn.execute(
            """CREATE TABLE engagements (
                demo_name TEXT,
                t0_manual_tick INTEGER,
                round_number INTEGER
            )"""
        )
        conn.executemany(
            "INSERT INTO engagements VALUES (?, ?, ?)",
            [
                ("real.dem", 100, None),
                ("real.dem", 200, None),
                ("real.dem", 300, None),
            ],
        )
        conn.commit()
    stats = backfill(db, demo_dirs=[str(demo_dir)], dry_run=True)
    out = capsys.readouterr().out
    assert "[dry-run]" in out
    assert "real.dem" in out
    assert stats["demos_processed"] == 1
    assert stats["rows_updated"] == 3
    # Verify DB was NOT modified (round_number still NULL).
    with closing(sqlite3.connect(db)) as conn:
        nulls = conn.execute(
            "SELECT COUNT(*) FROM engagements WHERE round_number IS NULL"
        ).fetchone()[0]
    assert nulls == 3
