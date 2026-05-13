"""
TDD tests for DDMAnalyzer geometry helpers (Phase 2).

Tests: get_desired_angles() — pitch/yaw from player to enemy
       angular_diff() — signed angle wrapping to [-180, 180]
"""

import math
import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from ddm_analyzer import DDMAnalyzer


class TestGetDesiredAngles:
    """Pitch/yaw calculation from player position to enemy position."""

    def test_enemy_directly_ahead_on_ground(self):
        """Enemy at same height, directly ahead (angle 0°)."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,  # player at origin, eye height 64
            ex=100, ey=0, ez=64,  # enemy 100 units ahead at same height
        )
        assert abs(pitch - 0.0) < 0.01, "Pitch should be ~0° for same height"
        assert abs(yaw - 0.0) < 0.01, "Yaw should be ~0° for ahead"

    def test_enemy_90_degrees_right(self):
        """Enemy 90° to the right."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=0, ey=100, ez=64,
        )
        assert abs(pitch - 0.0) < 0.01, "Pitch should be ~0° for same height"
        assert abs(yaw - 90.0) < 0.01, "Yaw should be ~90° for right"

    def test_enemy_90_degrees_left(self):
        """Enemy 90° to the left."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=0, ey=-100, ez=64,
        )
        assert abs(pitch - 0.0) < 0.01, "Pitch should be ~0° for same height"
        assert abs(yaw - (-90.0)) < 0.01, "Yaw should be ~-90° for left"

    def test_enemy_180_degrees_behind(self):
        """Enemy directly behind."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=-100, ey=0, ez=64,
        )
        assert abs(pitch - 0.0) < 0.01, "Pitch should be ~0° for same height"
        # Yaw should be ±180°; atan2 returns -180 to 180
        assert abs(abs(yaw) - 180.0) < 0.01, "Yaw should be ~±180° for behind"

    def test_enemy_above(self):
        """Enemy directly above (dz > 0)."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=0, ey=0, ez=164,  # 100 units above
        )
        # When h_dist == 0 and dz > 0, pitch = -90°
        assert abs(pitch - (-90.0)) < 0.01, "Pitch should be -90° for directly above"

    def test_enemy_below(self):
        """Enemy directly below (dz < 0)."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=0, ey=0, ez=-36,  # 100 units below
        )
        # When h_dist == 0 and dz < 0, pitch = 90°
        assert abs(pitch - 90.0) < 0.01, "Pitch should be 90° for directly below"

    def test_enemy_at_same_position(self):
        """Enemy at exact same position (edge case)."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=0, ey=0, ez=64,  # Same position
        )
        # h_dist == 0, dz == 0 → pitch = 0°
        assert abs(pitch - 0.0) < 0.01, "Pitch should be 0° when at same position"
        assert abs(yaw - 0.0) < 0.01, "Yaw should be 0° when at same position (atan2(0,0)=0)"

    def test_enemy_above_and_45_degrees_right(self):
        """Enemy above and to the right (pitch down, yaw right)."""
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=64,
            ex=100, ey=100, ez=164,  # 100 up, 100√2 horizontal
        )
        # yaw = atan2(100, 100) = 45°
        assert abs(yaw - 45.0) < 0.01, "Yaw should be ~45°"
        # pitch = atan2(-100, 100√2) ≈ -35.26°
        assert abs(pitch - (-35.26)) < 0.5, f"Pitch should be ~-35.26°, got {pitch}"

    def test_consistent_with_cs2_coordinates(self):
        """Verify calculation matches Source engine coordinate system."""
        # Source: +X ahead, +Y right, +Z up
        # Player at origin looking ahead
        pitch, yaw = DDMAnalyzer.get_desired_angles(
            px=0, py=0, pz=0,
            ex=100, ey=0, ez=-50,  # Ahead and down
        )
        assert yaw > -1 and yaw < 1, "Yaw should be ~0° for ahead"
        assert pitch > 0, "Pitch should be positive (down) when enemy is below"


class TestAngularDiff:
    """Signed angle difference normalized to [-180, 180]."""

    def test_zero_difference(self):
        """No angular difference."""
        result = DDMAnalyzer.angular_diff(0, 0)
        assert abs(result - 0.0) < 0.01

    def test_positive_difference(self):
        """Simple positive rotation."""
        result = DDMAnalyzer.angular_diff(10, 30)
        assert abs(result - 20.0) < 0.01, "Should be 30 - 10 = 20"

    def test_negative_difference(self):
        """Simple negative rotation."""
        result = DDMAnalyzer.angular_diff(30, 10)
        assert abs(result - (-20.0)) < 0.01, "Should be 10 - 30 = -20"

    def test_wrapping_at_180_boundary(self):
        """Angle wrapping across 180°."""
        result = DDMAnalyzer.angular_diff(170, -170)
        # Difference is -170 - 170 = -340, normalized to -340 + 360 = 20
        assert abs(result - 20.0) < 0.01, "Should wrap to +20°"

    def test_wrapping_at_minus_180_boundary(self):
        """Angle wrapping across -180°."""
        result = DDMAnalyzer.angular_diff(-170, 170)
        # Difference is 170 - (-170) = 340, normalized to 340 - 360 = -20
        assert abs(result - (-20.0)) < 0.01, "Should wrap to -20°"

    def test_exactly_180_degrees_apart(self):
        """Angles exactly 180° apart — formula returns -180 (not +180)."""
        result = DDMAnalyzer.angular_diff(0, 180)
        assert result == -180.0, "Formula (a2-a1+180)%360-180 returns -180 for this case"

    def test_exactly_180_degrees_apart_reversed(self):
        """Angles exactly 180° apart (reversed)."""
        result = DDMAnalyzer.angular_diff(180, 0)
        assert abs(result - (-180.0)) < 0.01, "Should be -180 (from 180 to 0)"

    def test_small_clockwise_rotation(self):
        """Small rotation clockwise (positive yaw)."""
        result = DDMAnalyzer.angular_diff(0, 5)
        assert abs(result - 5.0) < 0.01

    def test_small_counterclockwise_rotation(self):
        """Small rotation counterclockwise (negative yaw)."""
        result = DDMAnalyzer.angular_diff(5, 0)
        assert abs(result - (-5.0)) < 0.01

    def test_360_degree_full_rotation(self):
        """Full 360° rotation normalizes to 0."""
        result = DDMAnalyzer.angular_diff(0, 360)
        assert abs(result - 0.0) < 0.01, "360° wraps to 0°"

    def test_negative_angles(self):
        """Negative angle inputs."""
        result = DDMAnalyzer.angular_diff(-45, -25)
        assert abs(result - 20.0) < 0.01, "-25 - (-45) = 20"

    def test_across_zero_positive_to_negative(self):
        """Crossing zero going negative."""
        result = DDMAnalyzer.angular_diff(10, -10)
        assert abs(result - (-20.0)) < 0.01, "-10 - 10 = -20"

    def test_across_zero_negative_to_positive(self):
        """Crossing zero going positive."""
        result = DDMAnalyzer.angular_diff(-10, 10)
        assert abs(result - 20.0) < 0.01, "10 - (-10) = 20"

    def test_always_returns_in_normalized_range(self):
        """Result is always in [-180, 180]."""
        test_cases = [
            (0, 270),  # Should be -90 (270 → -90)
            (90, 450),  # Should be 0 (450 → 90, diff = 0)
            (-180, 180),  # Should be 0 (540%360-180 = 0)
            (359, 1),  # Should be +2
        ]
        for a1, a2 in test_cases:
            result = DDMAnalyzer.angular_diff(a1, a2)
            assert -180 <= result <= 180, f"Result {result} out of range for angular_diff({a1}, {a2})"


class TestComputeCrosshairAngleAtT0:
    PLAYER_ID = 111111111
    ENEMY_ID = 222222222
    TICK = 500

    def _make_df(self, p_pitch, p_yaw, ex, ey, ez=64.0):
        """Build minimal all_ticks_df with one player row and one enemy row at TICK."""
        return pd.DataFrame([
            {
                "steamid": self.PLAYER_ID,
                "tick": self.TICK,
                "X": 0.0, "Y": 0.0, "Z": 0.0,
                "pitch": p_pitch, "yaw": p_yaw,
            },
            {
                "steamid": self.ENEMY_ID,
                "tick": self.TICK,
                "X": float(ex), "Y": float(ey), "Z": float(ez) - 36.0,
                "pitch": 0.0, "yaw": 0.0,
            },
        ])

    def _analyzer(self):
        with patch("ddm_analyzer.DemoParser") as MockParser, \
             patch("ddm_analyzer.T0Detector"):
            MockParser.return_value.parse_header.return_value = {"map_name": "de_dust2"}
            a = DDMAnalyzer.__new__(DDMAnalyzer)
            a.player_steamid = self.PLAYER_ID
            a.tickrate = 64
            a.debug_prints = False
            a.logger = MagicMock()
            return a

    def test_looking_directly_at_enemy_returns_zero(self):
        # Enemy 200u ahead at eye height, player looking yaw=0 pitch=0 → angle ≈ 0°
        df = self._make_df(p_pitch=0.0, p_yaw=0.0, ex=200, ey=0, ez=64.0)
        a = self._analyzer()
        angle = a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df)
        assert angle is not None
        assert abs(angle) < 1.0, f"Expected ~0°, got {angle}"

    def test_looking_90_degrees_off_horizontally(self):
        # Enemy at (0, 200, eye_height) → desired yaw=90°, player looking yaw=0 → angle ≈ 90°
        df = self._make_df(p_pitch=0.0, p_yaw=0.0, ex=0, ey=200, ez=64.0)
        a = self._analyzer()
        angle = a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df)
        assert angle is not None
        assert abs(angle - 90.0) < 1.0, f"Expected ~90°, got {angle}"

    def test_small_offset_returns_expected_angle(self):
        # Enemy 200u ahead, 10u right → yaw offset = atan2(10,200) ≈ 2.86°
        df = self._make_df(p_pitch=0.0, p_yaw=0.0, ex=200, ey=10, ez=64.0)
        a = self._analyzer()
        angle = a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df)
        expected = math.degrees(math.atan2(10, 200))
        assert angle is not None
        assert abs(angle - expected) < 1.0, f"Expected ~{expected:.1f}°, got {angle}"

    def test_missing_player_row_returns_none(self):
        df = pd.DataFrame([
            {"steamid": self.ENEMY_ID, "tick": self.TICK,
             "X": 200.0, "Y": 0.0, "Z": 28.0, "pitch": 0.0, "yaw": 0.0},
        ])
        a = self._analyzer()
        assert a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df) is None

    def test_missing_enemy_row_returns_none(self):
        df = pd.DataFrame([
            {"steamid": self.PLAYER_ID, "tick": self.TICK,
             "X": 0.0, "Y": 0.0, "Z": 0.0, "pitch": 0.0, "yaw": 0.0},
        ])
        a = self._analyzer()
        assert a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df) is None

    def test_result_is_non_negative(self):
        df = self._make_df(p_pitch=10.0, p_yaw=-45.0, ex=100, ey=-100, ez=80.0)
        a = self._analyzer()
        angle = a._compute_crosshair_angle_at_t0(self.TICK, self.ENEMY_ID, df)
        assert angle is not None
        assert angle >= 0.0
