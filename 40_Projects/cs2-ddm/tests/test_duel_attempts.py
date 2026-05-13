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


# --- Task 3 tests ---

def _fire_df(*ticks, weapon="weapon_ak47"):
    import pandas as pd
    return pd.DataFrame({"tick": list(ticks), "weapon": [weapon] * len(ticks)})

def _hurt_df(attacker, victim, tick):
    import pandas as pd
    return pd.DataFrame({
        "tick": [tick],
        "attacker_steamid": [str(attacker)],
        "user_steamid": [str(victim)],
    })

def _ticks_df(player_sid, enemy_sid, tick, p_vel=300.0):
    import pandas as pd
    return pd.DataFrame([
        {"steamid": player_sid, "tick": tick, "X": 0.0, "Y": 0.0, "Z": 0.0,
         "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True,
         "vel_x": p_vel, "vel_y": 0.0},
        {"steamid": enemy_sid, "tick": tick, "X": 200.0, "Y": 0.0, "Z": 0.0,
         "pitch": 0.0, "yaw": 0.0, "team_num": 3, "is_alive": True,
         "vel_x": 0.0, "vel_y": 0.0},
    ])

import pandas as pd
from unittest.mock import MagicMock
from duel_attempts import DuelAttemptFinder


def _fire_df(*ticks, weapon="weapon_ak47"):
    return pd.DataFrame({"tick": list(ticks), "weapon": [weapon] * len(ticks)})


def _hurt_df(rows):
    return pd.DataFrame(
        rows,
        columns=["tick", "attacker_steamid", "user_steamid"],
    )


def _death_df(rows):
    return pd.DataFrame(
        rows,
        columns=["tick", "attacker_steamid", "user_steamid"],
    )


def _ticks_df_at(ticks, player_sid=1, enemy_sid=99, p_vel=300.0, tickrate=64):
    # Player velocity is derived from X/Y delta across consecutive ticks in
    # DuelAttemptFinder._player_velocity, so X must advance by p_vel / tickrate
    # per tick to produce the intended speed.
    dx_per_tick = p_vel / tickrate
    rows = []
    for t in sorted(ticks):
        rows.append({"steamid": player_sid, "tick": t, "X": t * dx_per_tick,
                     "Y": 0.0, "Z": 0.0,
                     "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True})
        rows.append({"steamid": enemy_sid, "tick": t, "X": 200.0, "Y": 0.0, "Z": 0.0,
                     "pitch": 0.0, "yaw": 0.0, "team_num": 3, "is_alive": True})
    return pd.DataFrame(rows)


def _mock_detector_with_t0(t0_tick, enemy_sid=99, angle=2.0):
    det = MagicMock()
    det.find_first_visible_enemy_in_window.return_value = (t0_tick, enemy_sid, angle)
    return det


def test_finder_drops_cluster_when_no_enemy_visible():
    det = MagicMock()
    det.find_first_visible_enemy_in_window.return_value = None
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000), _ticks_df_at([1000]),
        _hurt_df([]), _death_df([]),
    )
    assert attempts == []


def test_finder_accepts_cluster_with_t0_and_records_kill():
    det = _mock_detector_with_t0(t0_tick=1005, enemy_sid=99, angle=3.0)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000, 1008, 1016),
        _ticks_df_at([1000, 1005, 1008, 1016], p_vel=300.0),
        _hurt_df([
            {"tick": 1010, "attacker_steamid": "1", "user_steamid": "99"},
            {"tick": 1020, "attacker_steamid": "1", "user_steamid": "99"},
        ]),
        _death_df([
            {"tick": 1050, "attacker_steamid": "1", "user_steamid": "99"},
        ]),
    )
    assert len(attempts) == 1
    a = attempts[0]
    assert a.t0_tick == 1005
    assert a.enemy_steamid == 99
    assert a.was_killed is True
    assert a.engagement_type == "peek"
    assert a.bullets_fired >= 1
    assert a.bullets_hit >= 1


def test_finder_records_miss_when_no_death():
    det = _mock_detector_with_t0(t0_tick=1005)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000, 1008),
        _ticks_df_at([1000, 1005, 1008]),
        _hurt_df([]),
        _death_df([]),
    )
    assert len(attempts) == 1
    assert attempts[0].was_killed is False
    assert attempts[0].bullets_hit == 0


def test_finder_peek_fire_before_t0_accepted():
    det = _mock_detector_with_t0(t0_tick=1010)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000, 1004, 1012, 1018),
        _ticks_df_at([1000, 1004, 1010, 1012, 1018]),
        _hurt_df([{"tick": 1020, "attacker_steamid": "1", "user_steamid": "99"}]),
        _death_df([{"tick": 1025, "attacker_steamid": "1", "user_steamid": "99"}]),
    )
    assert len(attempts) == 1
    assert attempts[0].t0_tick == 1010
    assert attempts[0].was_killed is True
    assert attempts[0].bullets_fired == 2  # ticks 1012, 1018
    assert attempts[0].bullets_hit == 1


def test_finder_hold_engagement_classified():
    det = _mock_detector_with_t0(t0_tick=1000)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000),
        _ticks_df_at([1000], p_vel=10.0),
        _hurt_df([]),
        _death_df([]),
    )
    assert len(attempts) == 1
    assert attempts[0].engagement_type == "hold"


def test_finder_knife_excluded():
    det = _mock_detector_with_t0(t0_tick=1000)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000, weapon="weapon_knife"),
        _ticks_df_at([1000]),
        _hurt_df([]),
        _death_df([]),
    )
    assert attempts == []


def test_finder_two_clusters():
    det = MagicMock()
    det.find_first_visible_enemy_in_window.side_effect = [
        (1000, 99, 2.0),
        (2000, 99, 4.0),
    ]
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000, 1010, 2000),
        _ticks_df_at([1000, 1010, 2000]),
        _hurt_df([]),
        _death_df([]),
    )
    assert len(attempts) == 2
    assert attempts[0].t0_tick == 1000
    assert attempts[1].t0_tick == 2000


def test_finder_death_outside_window_not_counted():
    det = _mock_detector_with_t0(t0_tick=1000)
    finder = DuelAttemptFinder(t0_detector=det, player_steamid=1,
                               match_id="m", map_name="de_t", tickrate=64)
    attempts = finder.find_attempts(
        _fire_df(1000),
        _ticks_df_at([1000]),
        _hurt_df([]),
        _death_df([{"tick": 5000, "attacker_steamid": "1", "user_steamid": "99"}]),
    )
    assert attempts[0].was_killed is False


# ── Task 1 (06-02): player_steamid в DuelAttempt (D-05) ──────────────────────

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
        """DuelAttempt без player_steamid — дефолт None."""
        a = self._make_attempt()
        assert a.player_steamid is None

    def test_player_steamid_explicit_value_stored(self):
        """DuelAttempt с явным player_steamid сохраняет значение."""
        steamid = 76561198386265483
        a = self._make_attempt(player_steamid=steamid)
        assert a.player_steamid == steamid

    def test_player_steamid_in_asdict(self):
        """dataclasses.asdict(attempt) содержит ключ 'player_steamid'."""
        a = self._make_attempt(player_steamid=76561198386265483)
        d = dataclasses.asdict(a)
        assert "player_steamid" in d
        assert d["player_steamid"] == 76561198386265483

    def test_finder_propagates_player_steamid_to_attempt(self):
        """DuelAttemptFinder с player_steamid=X генерирует DuelAttempt.player_steamid=X."""
        player_sid = 76561198386265483
        det = _mock_detector_with_t0(t0_tick=1005, enemy_sid=99, angle=3.0)
        finder = DuelAttemptFinder(
            t0_detector=det,
            player_steamid=player_sid,
            match_id="m",
            map_name="de_t",
            tickrate=64,
        )
        attempts = finder.find_attempts(
            _fire_df(1000),
            _ticks_df_at([1000, 1005]),
            _hurt_df([]),
            _death_df([]),
        )
        assert len(attempts) == 1
        assert attempts[0].player_steamid == player_sid
