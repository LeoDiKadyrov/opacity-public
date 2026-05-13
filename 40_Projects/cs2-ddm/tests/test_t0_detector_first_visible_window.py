from unittest.mock import MagicMock, patch
import pandas as pd
from t0_detector import T0Detector


def _ticks_rows(player_sid, enemy_sid, ticks, enemy_visible_from_tick=None):
    rows = []
    for t in ticks:
        rows.append({
            "steamid": player_sid, "tick": t, "X": 0.0, "Y": 0.0, "Z": 0.0,
            "pitch": 0.0, "yaw": 0.0, "team_num": 2, "is_alive": True,
        })
        rows.append({
            "steamid": enemy_sid, "tick": t, "X": 200.0, "Y": 0.0, "Z": 0.0,
            "pitch": 0.0, "yaw": 0.0, "team_num": 3, "is_alive": True,
        })
    return pd.DataFrame(rows)


def _make_detector(visible_from_tick=None):
    with patch("t0_detector.VisibilityChecker"):
        det = T0Detector.__new__(T0Detector)
        det.checker = MagicMock()
        det.map_name = "de_test"
    if visible_from_tick is None:
        det.checker.is_visible.return_value = False
    else:
        raise NotImplementedError
    return det


def test_find_first_visible_returns_none_when_never_visible():
    det = _make_detector()
    ticks = _ticks_rows(1, 99, [100, 101, 102, 103])
    result = det.find_first_visible_enemy_in_window(
        ticks, player_steamid=1, start_tick=100, end_tick=103,
    )
    assert result is None


def test_find_first_visible_returns_earliest_tick():
    with patch("t0_detector.VisibilityChecker"):
        det = T0Detector.__new__(T0Detector)
        det.checker = MagicMock()
        det.map_name = "de_test"

    det.find_visible_enemies_at_tick = MagicMock(side_effect=[
        [],                       # tick 100
        [],                       # tick 101
        [(99, 3.0)],              # tick 102 — first visible
        [(99, 2.0)],              # tick 103
    ])

    ticks = _ticks_rows(1, 99, [100, 101, 102, 103])
    result = det.find_first_visible_enemy_in_window(
        ticks, player_steamid=1, start_tick=100, end_tick=103,
    )
    assert result == (102, 99, 3.0)


def test_find_first_visible_picks_closest_crosshair_on_tie():
    with patch("t0_detector.VisibilityChecker"):
        det = T0Detector.__new__(T0Detector)
        det.checker = MagicMock()
        det.map_name = "de_test"

    det.find_visible_enemies_at_tick = MagicMock(side_effect=[
        [(99, 8.0), (77, 2.5)],
    ])
    ticks = _ticks_rows(1, 99, [500])
    result = det.find_first_visible_enemy_in_window(
        ticks, player_steamid=1, start_tick=500, end_tick=500,
    )
    assert result == (500, 77, 2.5)
