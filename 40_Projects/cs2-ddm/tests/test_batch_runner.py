"""
Tests for batch_runner.py — analyze_demo_worker + BatchRunner.

Tests do NOT spawn real ProcessPoolExecutor with actual .dem files.
All DB operations use :memory: or tmp_path.
"""
from __future__ import annotations

import pickle
import sqlite3
from pathlib import Path

import pytest

from batch_runner import BatchRunner, analyze_demo_worker
from db_utils import init_db, get_next_match_id, mark_processed


# ── Picklability ──────────────────────────────────────────────────────────────

def test_worker_is_picklable():
    """analyze_demo_worker must be a top-level function — pickle.dumps must succeed."""
    data = pickle.dumps(analyze_demo_worker)
    assert data is not None
    assert len(data) > 0


# ── Worker error return ───────────────────────────────────────────────────────

def test_worker_returns_error_dict_for_bad_path():
    """Worker must catch exceptions and return dict{status='error'} — never raise."""
    result = analyze_demo_worker(("/nonexistent/demo.dem", 12345, 99, ":memory:", 64))
    assert result["status"] == "error"
    assert "traceback" in result
    assert result["match_id"] == 99


def test_worker_error_dict_has_required_keys():
    """Error result must include all required keys."""
    result = analyze_demo_worker(("/nonexistent/demo.dem", 12345, 1, ":memory:", 64))
    for key in ("status", "match_id", "demo", "engagements", "attempts"):
        assert key in result, f"Missing key: {key}"


def test_worker_error_engagements_and_attempts_are_zero():
    result = analyze_demo_worker(("/nonexistent/demo.dem", 12345, 1, ":memory:", 64))
    assert result["engagements"] == 0
    assert result["attempts"] == 0


# ── BatchRunner.scan_demos ────────────────────────────────────────────────────

def test_scan_demos_returns_dem_files(tmp_path):
    (tmp_path / "a.dem").touch()
    (tmp_path / "b.dem").touch()
    (tmp_path / "notes.txt").touch()
    runner = BatchRunner(db_path=":memory:")
    result = runner.scan_demos(str(tmp_path))
    assert len(result) == 2
    assert all(p.suffix == ".dem" for p in result)


def test_scan_demos_returns_sorted(tmp_path):
    (tmp_path / "z.dem").touch()
    (tmp_path / "a.dem").touch()
    (tmp_path / "m.dem").touch()
    runner = BatchRunner(db_path=":memory:")
    result = runner.scan_demos(str(tmp_path))
    names = [p.name for p in result]
    assert names == sorted(names)


def test_scan_demos_empty_dir(tmp_path):
    runner = BatchRunner(db_path=":memory:")
    result = runner.scan_demos(str(tmp_path))
    assert result == []


def test_scan_demos_creates_dir_if_missing(tmp_path):
    new_dir = tmp_path / "nonexistent_subdir"
    assert not new_dir.exists()
    runner = BatchRunner(db_path=":memory:")
    result = runner.scan_demos(str(new_dir))
    assert new_dir.exists()
    assert result == []


# ── BatchRunner.filter_unprocessed ───────────────────────────────────────────

def test_filter_unprocessed_includes_new_demos(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / "a.dem", tmp_path / "b.dem"]
    runner = BatchRunner(db_path=db)
    result = runner.filter_unprocessed(demos, player_steamid=123)
    assert len(result) == 2


def test_filter_unprocessed_skips_processed(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / "a.dem", tmp_path / "b.dem"]
    mark_processed(db, "a.dem", 123, match_id=1)
    runner = BatchRunner(db_path=db)
    result = runner.filter_unprocessed(demos, player_steamid=123)
    assert len(result) == 1
    assert result[0].name == "b.dem"


def test_filter_unprocessed_all_processed_returns_empty(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / "a.dem", tmp_path / "b.dem"]
    mark_processed(db, "a.dem", 123, match_id=1)
    mark_processed(db, "b.dem", 123, match_id=2)
    runner = BatchRunner(db_path=db)
    result = runner.filter_unprocessed(demos, player_steamid=123)
    assert result == []


# ── BatchRunner.pre_assign_match_ids ─────────────────────────────────────────

def test_pre_assign_match_ids_length(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / "a.dem", tmp_path / "b.dem", tmp_path / "c.dem"]
    runner = BatchRunner(db_path=db)
    result = runner.pre_assign_match_ids(demos)
    assert len(result) == 3


def test_pre_assign_match_ids_starts_at_1_on_empty_db(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / "a.dem"]
    runner = BatchRunner(db_path=db)
    result = runner.pre_assign_match_ids(demos)
    assert result[0][0] == 1


def test_pre_assign_match_ids_continues_from_max(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    # Simulate existing data: MAX(match_id) = 5
    with sqlite3.connect(db) as conn:
        conn.execute(
            "INSERT INTO engagements (match_id) VALUES ('5')"
        )
    demos = [tmp_path / "a.dem", tmp_path / "b.dem"]
    runner = BatchRunner(db_path=db)
    result = runner.pre_assign_match_ids(demos)
    assert result[0][0] == 6
    assert result[1][0] == 7


def test_pre_assign_match_ids_sequential(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    demos = [tmp_path / f"{i}.dem" for i in range(5)]
    runner = BatchRunner(db_path=db)
    result = runner.pre_assign_match_ids(demos)
    ids = [mid for mid, _ in result]
    assert ids == list(range(1, 6))


def test_pre_assign_match_ids_empty_list(tmp_path):
    db = str(tmp_path / "test.db")
    init_db(db)
    runner = BatchRunner(db_path=db)
    result = runner.pre_assign_match_ids([])
    assert result == []


# ── Phase 7 filter / assign additions ────────────────────────────────────────

def test_filter_unprocessed_force(tmp_path):
    """force=True returns all demos regardless of processed_matches."""
    import db_utils
    db = str(tmp_path / "force.db")
    db_utils.init_db(db)
    (tmp_path / "a.dem").touch()
    db_utils.mark_processed(db, "a.dem", 99999, 1)

    runner = BatchRunner(db_path=db)
    paths = [tmp_path / "a.dem"]
    result = runner.filter_unprocessed(paths, player_steamid=99999, force=True)
    assert len(result) == 1
