"""
TDD tests for T1 detection algorithm in DDMAnalyzer.analyze_engagement_episode() (Phase 5).

T1 = first tick of sustained reactive aim movement toward the target enemy.

Algorithm: after a grace period (120ms), scan consecutive tick-pairs for:
  - significant angular movement (d_yaw or d_pitch > T1_MIN_ANGLE_CHANGE)
  - movement TOWARD enemy (nxt_dist < curr_dist - 0.01)
  - player not already aimed (curr_dist > T1_NOT_AIMED_THRESHOLD)
  - T1_SUSTAINED_AIM_TICKS=2 consecutive qualifying pairs required

All tests use manual T0 mode to bypass BVH, with controlled DataFrames
that isolate the T1 algorithm from other episode gates.
"""

import math
import pandas as pd
import pytest
from unittest.mock import patch

from ddm_analyzer import DDMAnalyzer
from config import AnalysisMoment, T1_GRACE_MS, T1_SUSTAINED_AIM_TICKS, T1_MIN_ANGLE_CHANGE

PLAYER_ID = 76561198386265483
ENEMY_ID  = 76561198315710555
TICKRATE  = 64

# At tickrate=64: 1 tick = 15.625ms. Grace period = int(120/15.625) = 7 ticks.
GRACE_TICKS = int(T1_GRACE_MS / (1000 / TICKRATE))

T0 = 1000
T2 = 1080  # 80 ticks after T0 = 1250ms (within T0_TO_T2_MAX_TICKS=96 cluster-bleed gate)

# Enemy is directly ahead at X=100, Y=0, Z=0 from player at (0,0,0).
# get_desired_angles(0,0,0, 100,0,0) → des_yaw=0°, des_pitch=0°
ENEMY_X = 100.0


@pytest.fixture
def analyzer():
    with patch("ddm_analyzer.DemoParser"):
        a = DDMAnalyzer(
            demo_path="fake.dem",
            player_steamid=PLAYER_ID,
            match_id="t1_test",
            debug_prints=False,
        )
    a.t0_detector = None
    return a


def _manual_moment(t0=T0, window_sec=5):
    return AnalysisMoment(
        timestamp="0:15",
        manual_t0_tick_enemy_first_visible=t0,
        description="t1_test",
        analysis_window_seconds_after_t0=window_sec,
        use_auto_t0=False,
    )


def _hurt(t2=T2):
    """One clean hit by player on enemy at T2."""
    return pd.DataFrame({
        "tick":             [t2],
        "attacker_steamid": [str(PLAYER_ID)],
        "user_steamid":     [str(ENEMY_ID)],
        "weapon":           ["ak47"],
    })


def _make_ticks(t0=T0, player_aim_rows=None, enemy_x=ENEMY_X, player_velocity_dx=1.0):
    """
    Build all_ticks_df containing:
    - Player rows at t0 and t0+1 for velocity classification.
    - Enemy rows at t0 and t0+1 (stationary) for velocity gate.
    - Player aim rows passed in as [(tick, yaw, pitch), ...].
    - Enemy rows at each aim tick for get_desired_angles.
    """
    rows = []

    # Player velocity rows (t0 and t0+1)
    rows.append({"steamid": PLAYER_ID, "tick": t0,   "X": 0.0,              "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    rows.append({"steamid": PLAYER_ID, "tick": t0+1, "X": player_velocity_dx, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})

    # Enemy velocity rows (stationary → 0 u/s, passes gate)
    rows.append({"steamid": ENEMY_ID, "tick": t0,   "X": enemy_x, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    rows.append({"steamid": ENEMY_ID, "tick": t0+1, "X": enemy_x, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})

    if player_aim_rows:
        for tick, yaw, pitch in player_aim_rows:
            rows.append({"steamid": PLAYER_ID, "tick": tick, "X": 0.0, "Y": 0.0, "Z": 0.0, "yaw": yaw, "pitch": pitch})
        # Enemy present at every player aim tick
        for tick, _, _ in player_aim_rows:
            rows.append({"steamid": ENEMY_ID, "tick": tick, "X": enemy_x, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})

    return pd.DataFrame(rows)


# ── Helpers for readable aim data ─────────────────────────────────────────────

# Player at (0,0,0), enemy at (100,0,0): des_yaw=0°, des_pitch=0°.
# "Aiming toward" means both yaw and pitch approach 0°.
# Starting far from enemy aim direction so curr_dist >> T1_NOT_AIMED_THRESHOLD=1.0°

def _aim_rows_t1_found():
    """
    3 ticks after grace that produce exactly T1_SUSTAINED_AIM_TICKS=2 consecutive pairs.
    Tick T0+10: yaw=30, pitch=5  → dist≈30.4°  (far from des=0)
    Tick T0+11: yaw=20, pitch=3  → dist≈20.2°  (d_yaw=10, moving towards, curr_dist>1.0)
    Tick T0+12: yaw=12, pitch=1.5 → dist≈12.1° (d_yaw=8, moving towards, curr_dist>1.0)
    Pair (T0+10→T0+11): consecutive=1, potential_t1=T0+11
    Pair (T0+11→T0+12): consecutive=2 ≥ 2  → T1 = T0+11 = 1011
    """
    base = T0 + 10
    return [(base,   30.0, 5.0),
            (base+1, 20.0, 3.0),
            (base+2, 12.0, 1.5)]


def _aim_rows_already_aimed():
    """
    Player already looking at enemy (dist < T1_NOT_AIMED_THRESHOLD=1.0°).
    Even with movement, the 'curr_dist > threshold' check fails → T1 not found.
    """
    base = T0 + 10
    return [(base,   0.5, 0.3),   # dist = hypot(0.5,0.3) ≈ 0.58 < 1.0
            (base+1, 0.3, 0.2),
            (base+2, 0.1, 0.1)]


def _aim_rows_moving_away():
    """
    Player moving away from enemy (nxt_dist > curr_dist) → moving_towards=False → T1 not found.
    """
    base = T0 + 10
    return [(base,   5.0,  1.0),   # dist ≈ 5.1° (close)
            (base+1, 15.0, 2.0),   # dist ≈ 15.1° (moving away)
            (base+2, 25.0, 3.0)]   # further away


def _aim_rows_angle_too_small():
    """
    Angular change per tick < T1_MIN_ANGLE_CHANGE=0.08° → sig_change=False → T1 not found.
    """
    base = T0 + 10
    return [(base,   30.0, 5.0),
            (base+1, 29.97, 4.97),  # d_yaw=0.03, d_pitch=0.03, both < 0.08
            (base+2, 29.94, 4.94)]


# ── Test class ────────────────────────────────────────────────────────────────

class TestT1Detection:

    # ── T1 found ──────────────────────────────────────────────────────────────

    def test_t1_found_returns_tick(self, analyzer):
        """Sustained aim toward enemy → T1 tick is detected and returned."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert not math.isnan(result["t1_aim_start_tick"])
        assert int(result["t1_aim_start_tick"]) == T0 + 11  # nxt tick of first qualifying pair

    def test_t1_found_rt_visible_to_aim_ms(self, analyzer):
        """RT(T0→T1) = (T1 - T0) × ms_per_tick."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        expected_ms = (T0 + 11 - T0) * (1000.0 / TICKRATE)
        assert abs(result["rt_visible_to_aim_ms"] - expected_ms) < 0.1

    def test_t1_found_rt_aim_to_hit_ms(self, analyzer):
        """RT(T1→T2) = (T2 - T1) × ms_per_tick."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        t1 = T0 + 11
        expected_ms = (T2 - t1) * (1000.0 / TICKRATE)
        assert abs(result["rt_aim_to_hit_ms"] - expected_ms) < 0.1

    def test_t1_found_rt_visible_to_hit_ms(self, analyzer):
        """RT(T0→T2) is correct regardless of T1."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        expected_ms = (T2 - T0) * (1000.0 / TICKRATE)
        assert abs(result["rt_visible_to_hit_ms"] - expected_ms) < 0.1

    def test_t1_exactly_sustained_ticks_boundary(self, analyzer):
        """Exactly T1_SUSTAINED_AIM_TICKS=2 consecutive pairs → T1 found (boundary condition)."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert not math.isnan(result["t1_aim_start_tick"])

    # ── T1 not found ─────────────────────────────────────────────────────────

    def test_t1_not_found_single_tick_in_window(self, analyzer):
        """Only 1 player tick in the aim window (< 2 rows needed) → T1=NaN."""
        base = T0 + 10
        ticks = _make_ticks(player_aim_rows=[(base, 30.0, 5.0)])
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_t1_not_found_only_one_consecutive_pair(self, analyzer):
        """Only 2 aim ticks (1 pair) → max consecutive=1 < T1_SUSTAINED_AIM_TICKS=2 → T1=NaN."""
        base = T0 + 10
        # One pair that qualifies but consecutive never reaches 2
        aim_rows = [(base, 30.0, 5.0), (base+1, 20.0, 3.0)]
        ticks = _make_ticks(player_aim_rows=aim_rows)
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_t1_not_found_aim_moving_away(self, analyzer):
        """Aim movement is away from enemy (nxt_dist > curr_dist) → T1=NaN."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_moving_away())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_t1_not_found_already_aimed_at_enemy(self, analyzer):
        """Player is already aimed at enemy (curr_dist ≤ threshold) → T1=NaN."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_already_aimed())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_t1_not_found_angle_change_below_minimum(self, analyzer):
        """Angular change per tick < T1_MIN_ANGLE_CHANGE=0.08° → sig_change=False → T1=NaN."""
        ticks = _make_ticks(player_aim_rows=_aim_rows_angle_too_small())
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_t1_not_found_enemy_data_missing_resets_consecutive(self, analyzer):
        """Enemy tick missing mid-sequence resets consecutive counter → T1=NaN."""
        # 4 player aim ticks but enemy missing at T0+11, so pair (T0+11→T0+12)
        # can't qualify → consecutive resets and never reaches 2 with only 4 ticks.
        base = T0 + 10
        player_rows = [
            (base,   30.0, 5.0),
            (base+1, 20.0, 3.0),   # enemy will be missing here
            (base+2, 12.0, 1.5),
            (base+3, 6.0,  0.8),
        ]
        # Build ticks manually: include enemy at base and base+2, NOT base+1
        rows = []
        rows.append({"steamid": PLAYER_ID, "tick": T0,   "X": 0.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
        rows.append({"steamid": PLAYER_ID, "tick": T0+1, "X": 1.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
        rows.append({"steamid": ENEMY_ID,  "tick": T0,   "X": ENEMY_X, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
        rows.append({"steamid": ENEMY_ID,  "tick": T0+1, "X": ENEMY_X, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
        for tick, yaw, pitch in player_rows:
            rows.append({"steamid": PLAYER_ID, "tick": tick, "X": 0.0, "Y": 0.0, "Z": 0.0, "yaw": yaw, "pitch": pitch})
        # Enemy present at base and base+2/base+3 only (NOT base+1)
        for tick in [base, base+2, base+3]:
            rows.append({"steamid": ENEMY_ID, "tick": tick, "X": ENEMY_X, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
        ticks = pd.DataFrame(rows)

        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    # ── Grace period ──────────────────────────────────────────────────────────

    def test_t1_grace_period_excludes_early_ticks(self, analyzer):
        """Aim ticks before T0+grace_ticks are excluded from T1 search → T1=NaN."""
        # Provide qualifying aim data ONLY at ticks T0+1 through T0+6 (< aim_search_start=T0+7)
        before_grace = T0 + GRACE_TICKS - 2  # still before grace
        aim_rows = [
            (before_grace,   30.0, 5.0),
            (before_grace+1, 20.0, 3.0),
            (before_grace+2, 12.0, 1.5),
        ]
        ticks = _make_ticks(player_aim_rows=aim_rows)
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    # ── Result integrity ─────────────────────────────────────────────────────

    def test_result_returned_when_t1_not_found(self, analyzer):
        """T1 not found does NOT reject the episode — a result dict is still returned."""
        ticks = _make_ticks()  # no aim rows → T1 not found
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert isinstance(result, dict)

    def test_rt_visible_to_aim_ms_is_nan_when_t1_not_found(self, analyzer):
        """rt_visible_to_aim_ms is NaN when T1 detection fails."""
        ticks = _make_ticks()
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        assert math.isnan(result["rt_visible_to_aim_ms"])

    def test_rt_visible_to_hit_ms_correct_regardless_of_t1(self, analyzer):
        """rt_visible_to_hit_ms = (T2 - T0) × ms even when T1 is NaN."""
        ticks = _make_ticks()
        result = analyzer.analyze_engagement_episode(
            _manual_moment(), ticks, pd.DataFrame(), _hurt()
        )
        assert result is not None
        expected_ms = (T2 - T0) * (1000.0 / TICKRATE)
        assert abs(result["rt_visible_to_hit_ms"] - expected_ms) < 0.1
