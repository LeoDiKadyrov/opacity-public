"""
TDD tests for kill_rate_analysis.save_attempts() append+dedup by match_id (D-06).

Tests: create-new, idempotency (same match_id no duplicate), accumulation (different
match_id additive), empty list no-op, run_player passes match_id explicitly,
multi-demo batch two match_ids stay independent.
"""
from __future__ import annotations

import dataclasses
import os
import tempfile
from typing import List
from unittest.mock import MagicMock, patch, call

import pandas as pd
import pytest

from duel_attempts import DuelAttempt
import kill_rate_analysis


# ── Helpers ───────────────────────────────────────────────────────────────────

def _attempt(match_id: str, enemy_steamid: int = 999) -> DuelAttempt:
    return DuelAttempt(
        match_id=match_id,
        map_name="de_dust2",
        t0_tick=1000,
        enemy_steamid=enemy_steamid,
        was_killed=True,
        bullets_fired=5,
        bullets_hit=3,
        engagement_type="peek",
        player_velocity_ups=250.0,
        crosshair_angle_deg=3.5,
        player_steamid=76561198386265483,
    )


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestSaveAttempts:
    """Tests for save_attempts() idempotency and accumulation (D-06)."""

    @pytest.fixture(autouse=True)
    def tmp_dir(self, tmp_path, monkeypatch):
        """Run each test with a fresh temp directory as CWD so CSV paths are isolated."""
        monkeypatch.chdir(tmp_path)
        self.tmp_path = tmp_path

    def test_creates_new_csv_when_absent(self):
        """save_attempts() creates CSV when file does not exist."""
        attempts = [_attempt("demo_a"), _attempt("demo_a", enemy_steamid=888)]
        kill_rate_analysis.save_attempts("player1", attempts, match_id="demo_a")
        csv_path = self.tmp_path / "player1_attempts.csv"
        assert csv_path.exists()
        df = pd.read_csv(csv_path)
        assert len(df) == 2

    def test_idempotent_same_match_id_no_duplicate(self):
        """Повторный вызов save_attempts() с тем же match_id — N строк, не 2N."""
        attempts = [_attempt("demo_a")]
        kill_rate_analysis.save_attempts("player1", attempts, match_id="demo_a")
        kill_rate_analysis.save_attempts("player1", attempts, match_id="demo_a")
        csv_path = self.tmp_path / "player1_attempts.csv"
        df = pd.read_csv(csv_path)
        assert len(df) == 1, f"Expected 1 row after 2 calls with same match_id, got {len(df)}"

    def test_accumulates_different_match_ids(self):
        """Разные match_id аккумулируются: N1 + N2 строки."""
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_a")], match_id="demo_a")
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_b")], match_id="demo_b")
        csv_path = self.tmp_path / "player1_attempts.csv"
        df = pd.read_csv(csv_path)
        assert len(df) == 2, f"Expected 2 rows (1 per match_id), got {len(df)}"

    def test_empty_list_does_not_create_file(self):
        """save_attempts() с пустым списком — файл не создаётся."""
        kill_rate_analysis.save_attempts("player1", [], match_id="demo_a")
        csv_path = self.tmp_path / "player1_attempts.csv"
        assert not csv_path.exists()

    def test_empty_list_does_not_modify_existing_file(self):
        """save_attempts() с пустым списком — существующий файл не изменяется."""
        attempts = [_attempt("demo_a")]
        kill_rate_analysis.save_attempts("player1", attempts, match_id="demo_a")
        csv_path = self.tmp_path / "player1_attempts.csv"
        mtime_before = csv_path.stat().st_mtime
        kill_rate_analysis.save_attempts("player1", [], match_id="demo_a")
        mtime_after = csv_path.stat().st_mtime
        assert mtime_before == mtime_after

    def test_run_player_passes_match_id_to_save_attempts(self):
        """run_player() передаёт match_id явно в save_attempts()."""
        demo_name = "donk1"
        player_name = "donk"
        steamid = 76561198386265483
        expected_match_id = f"{player_name}_{demo_name}"

        fake_attempt = _attempt(expected_match_id)

        with patch("kill_rate_analysis.os.path.exists", return_value=True), \
             patch("kill_rate_analysis.DDMAnalyzer") as MockAnalyzer, \
             patch("kill_rate_analysis.save_attempts") as mock_save:

            mock_analyzer_instance = MagicMock()
            mock_analyzer_instance.analyze_demo.return_value = ([], [fake_attempt])
            MockAnalyzer.return_value = mock_analyzer_instance

            kill_rate_analysis.run_player(player_name, steamid, [f"/fake/{demo_name}.dem"])

        assert mock_save.called, "save_attempts() was not called"
        # Check that match_id keyword arg was passed
        call_kwargs = mock_save.call_args
        # match_id should be passed as keyword or 3rd positional
        passed_match_id = None
        if call_kwargs.kwargs.get("match_id") is not None:
            passed_match_id = call_kwargs.kwargs["match_id"]
        elif len(call_kwargs.args) >= 3:
            passed_match_id = call_kwargs.args[2]
        assert passed_match_id == expected_match_id, (
            f"Expected match_id={expected_match_id!r}, got {passed_match_id!r}"
        )

    def test_multi_demo_two_match_ids_stay_independent(self):
        """Два разных match_id — итого 2 строки (по одной на match_id), не 4."""
        # Call twice for demo_a, twice for demo_b (simulating rerun)
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_a")], match_id="demo_a")
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_b")], match_id="demo_b")
        # Rerun — should not duplicate
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_a")], match_id="demo_a")
        kill_rate_analysis.save_attempts("player1", [_attempt("demo_b")], match_id="demo_b")
        csv_path = self.tmp_path / "player1_attempts.csv"
        df = pd.read_csv(csv_path)
        assert len(df) == 2, (
            f"Expected 2 rows (demo_a + demo_b, deduplicated), got {len(df)}"
        )
        match_ids_in_csv = set(df["match_id"].astype(str))
        assert "demo_a" in match_ids_in_csv
        assert "demo_b" in match_ids_in_csv
