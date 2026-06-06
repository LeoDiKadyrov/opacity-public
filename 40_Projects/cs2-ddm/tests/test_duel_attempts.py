from dataclasses import asdict
from unittest.mock import MagicMock, patch

import pandas as pd

from duel_attempts import DuelAttempt
from t0_detector import T0Detector


def _make_ticks_df(rows):
    return pd.DataFrame(rows)


def test_duel_attempt_fields():
    a = DuelAttempt(
        match_id="abc123",
        map_name="de_dust2",
        t0_tick=1000,
        enemy_steamid=76561198000000001,
        was_killed=True,
        bullets_fired=5,
        bullets_hit=3,
        engagement_type="peek",
        player_velocity_ups=250.0,
        crosshair_angle_deg=3.5,
    )
    d = asdict(a)
    assert d["was_killed"] is True
    assert d["bullets_fired"] == 5
    assert d["bullets_hit"] == 3
    assert d["engagement_type"] == "peek"


def test_duel_attempt_zero_hits_survivor():
    a = DuelAttempt(
        match_id="abc123",
        map_name="de_dust2",
        t0_tick=2000,
        enemy_steamid=76561198000000002,
        was_killed=False,
        bullets_fired=8,
        bullets_hit=0,
        engagement_type="peek",
        player_velocity_ups=180.0,
        crosshair_angle_deg=12.0,
    )
    assert a.was_killed is False
    assert a.bullets_hit == 0


def test_find_visible_enemies_empty_when_no_enemies():
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector.__new__(T0Detector)
        detector.checker = MagicMock()
        detector.map_name = "de_test"

    player_row = {"steamid": 1, "tick": 100, "X": 0.0, "Y": 0.0, "Z": 0.0,
                  "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True}
    all_ticks = _make_ticks_df([player_row])
    result = detector.find_visible_enemies_at_tick(all_ticks, player_steamid=1, tick=100)
    assert result == []


def test_find_visible_enemies_returns_visible_enemy():
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector.__new__(T0Detector)
        detector.checker = MagicMock()
        detector.checker.is_visible.return_value = True
        detector.map_name = "de_test"

    player_row = {"steamid": 1, "tick": 100, "X": 0.0, "Y": 0.0, "Z": 0.0,
                  "pitch": 0.0, "yaw": 90.0, "team_num": 2, "is_alive": True}
    enemy_row  = {"steamid": 2, "tick": 100, "X": 100.0, "Y": 0.0, "Z": 0.0,
                  "pitch": 0.0, "yaw": 0.0, "team_num": 3, "is_alive": True}
    all_ticks = _make_ticks_df([player_row, enemy_row])
    result = detector.find_visible_enemies_at_tick(all_ticks, player_steamid=1, tick=100)
    assert len(result) == 1
    enemy_sid, angle = result[0]
    assert enemy_sid == 2
    assert isinstance(angle, float)


def test_find_visible_enemies_skips_same_team():
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector.__new__(T0Detector)
        detector.checker = MagicMock()
        detector.checker.is_visible.return_value = True
        detector.map_name = "de_test"

    player_row   = {"steamid": 1, "tick": 100, "X": 0.0, "Y": 0.0, "Z": 0.0,
                    "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True}
    teammate_row = {"steamid": 3, "tick": 100, "X": 50.0, "Y": 0.0, "Z": 0.0,
                    "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True}
    all_ticks = _make_ticks_df([player_row, teammate_row])
    result = detector.find_visible_enemies_at_tick(all_ticks, player_steamid=1, tick=100)
    assert result == []


def test_find_visible_enemies_skips_dead():
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector.__new__(T0Detector)
        detector.checker = MagicMock()
        detector.checker.is_visible.return_value = True
        detector.map_name = "de_test"

    player_row = {"steamid": 1, "tick": 100, "X": 0.0, "Y": 0.0, "Z": 0.0,
                  "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True}
    dead_enemy = {"steamid": 4, "tick": 100, "X": 100.0, "Y": 0.0, "Z": 0.0,
                  "pitch": 0.0, "yaw": 0.0, "team_num": 3, "is_alive": False}
    all_ticks = _make_ticks_df([player_row, dead_enemy])
    result = detector.find_visible_enemies_at_tick(all_ticks, player_steamid=1, tick=100)
    assert result == []


# ── Task 1 (06-02): player_steamid in DuelAttempt (D-05) ──────────────────────

import dataclasses


class TestDuelAttemptPlayerSteamid:
    """TDD tests for DuelAttempt.player_steamid field (D-05)."""

    def _make_attempt(self, **kwargs):
        defaults = dict(
            match_id="m1", map_name="de_dust2", t0_tick=100,
            enemy_steamid=123, was_killed=True, bullets_fired=5,
            bullets_hit=3, engagement_type="peek",
            player_velocity_ups=100.0, crosshair_angle_deg=5.0,
        )
        defaults.update(kwargs)
        return DuelAttempt(**defaults)

    def test_player_steamid_defaults_to_none(self):
        """DuelAttempt without player_steamid -- default None."""
        a = self._make_attempt()
        assert a.player_steamid is None

    def test_player_steamid_explicit_value_stored(self):
        """DuelAttempt with explicit player_steamid stores value."""
        steamid = 76561198386265483
        a = self._make_attempt(player_steamid=steamid)
        assert a.player_steamid == steamid

    def test_player_steamid_in_asdict(self):
        """dataclasses.asdict(attempt) contains key 'player_steamid'."""
        a = self._make_attempt(player_steamid=76561198386265483)
        d = dataclasses.asdict(a)
        assert "player_steamid" in d
        assert d["player_steamid"] == 76561198386265483
