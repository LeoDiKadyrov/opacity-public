"""
TDD tests for T0Detector._is_smoke_obscured() (Phase 5).

Tests: geometric line-segment vs sphere intersection for smoke suppression.
       Smoke is modelled as a sphere of radius _SMOKE_RADIUS_UNITS (144 units).
"""

import numpy as np
import pandas as pd
import pytest

from t0_detector import T0Detector, _SMOKE_RADIUS_UNITS

R = _SMOKE_RADIUS_UNITS  # 144.0


@pytest.fixture
def detector():
    """T0Detector instance without loading a real .tri file."""
    return object.__new__(T0Detector)


def _smoke(x, y, z, start=0, end=1000):
    """Build a single-row active_smokes DataFrame."""
    return pd.DataFrame({
        "X": [float(x)],
        "Y": [float(y)],
        "Z": [float(z)],
        "start_tick": [start],
        "end_tick":   [end],
    })


def _smokes(*rows):
    """Build a multi-row active_smokes DataFrame. Each row: (x, y, z, start, end)."""
    return pd.DataFrame(
        [{"X": float(x), "Y": float(y), "Z": float(z), "start_tick": s, "end_tick": e}
         for x, y, z, s, e in rows]
    )


class TestIsSmokeObscured:

    def test_none_smokes_returns_false(self, detector):
        """active_smokes=None → not obscured."""
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, None) is False

    def test_empty_smokes_df_returns_false(self, detector):
        """Empty DataFrame → not obscured."""
        empty = pd.DataFrame(columns=["X", "Y", "Z", "start_tick", "end_tick"])
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, empty) is False

    def test_smoke_not_yet_active_at_tick(self, detector):
        """Smoke start_tick=100 but tick=50 → smoke not yet active → False."""
        smokes = _smoke(100, 0, 0, start=100, end=500)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is False

    def test_smoke_already_expired_at_tick(self, detector):
        """Smoke end_tick=30 but tick=50 → smoke expired → False."""
        smokes = _smoke(100, 0, 0, start=0, end=30)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is False

    def test_ray_through_smoke_center(self, detector):
        """Ray passes exactly through smoke center → True."""
        # Ray: (0,0,0)→(200,0,0). Smoke center at (100,0,0). Closest point = center → dist=0.
        smokes = _smoke(100, 0, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is True

    def test_ray_touches_smoke_boundary_exactly(self, detector):
        """Closest point on ray is exactly R units from smoke center → True (≤ comparison)."""
        # Ray: (0,0,0)→(200,0,0). Smoke center at (100, R, 0). Closest = (100,0,0). dist=R.
        smokes = _smoke(100, R, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is True

    def test_ray_just_misses_smoke(self, detector):
        """Closest point on ray is R+0.1 units from smoke center → False."""
        smokes = _smoke(100, R + 0.1, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is False

    def test_ray_far_from_smoke(self, detector):
        """Smoke is far from the ray → False."""
        smokes = _smoke(1000, 1000, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is False

    def test_zero_length_ray_returns_false(self, detector):
        """start == end → seg_len_sq < 1e-9 → False."""
        smokes = _smoke(0, 0, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (0, 0, 0), 50, smokes) is False

    def test_smoke_near_ray_start_within_radius(self, detector):
        """Smoke center perpendicular to ray at start, within radius → t clamps to 0 → True."""
        # Ray: (100,0,0)→(200,0,0). Smoke at (100, 50, 0). t=0 → closest=(100,0,0). dist=50<R.
        smokes = _smoke(100, 50, 0)
        assert detector._is_smoke_obscured((100, 0, 0), (200, 0, 0), 50, smokes) is True

    def test_smoke_beyond_segment_end_outside_radius(self, detector):
        """Smoke beyond end, distance from end > R → False."""
        # Ray: (0,0,0)→(100,0,0). Smoke at (400,0,0). t>1 → clamp to 1 → closest=(100,0,0).
        # dist from (100,0,0) to (400,0,0) = 300 > R=144 → False.
        smokes = _smoke(400, 0, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (100, 0, 0), 50, smokes) is False

    def test_smoke_beyond_segment_end_within_radius(self, detector):
        """Smoke beyond end but distance from end < R → True (endpoint is inside smoke)."""
        # Ray: (0,0,0)→(100,0,0). Smoke at (200,0,0). t>1 → clamp → closest=(100,0,0).
        # dist from (100,0,0) to (200,0,0) = 100 < R=144 → True.
        smokes = _smoke(200, 0, 0)
        assert detector._is_smoke_obscured((0, 0, 0), (100, 0, 0), 50, smokes) is True

    def test_tick_exactly_at_smoke_start_tick(self, detector):
        """Tick == smoke start_tick → smoke is active (inclusive) → True if blocking."""
        smokes = _smoke(100, 0, 0, start=50, end=200)
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is True

    def test_multiple_smokes_one_blocking(self, detector):
        """Two smokes: one misses, one blocks → True."""
        smokes = _smokes(
            (100, 500, 0, 0, 1000),   # far away, misses
            (100, 0, 0, 0, 1000),     # on ray, blocks
        )
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is True

    def test_multiple_smokes_none_blocking(self, detector):
        """Two smokes: both miss → False."""
        smokes = _smokes(
            (100, 500, 0, 0, 1000),    # far away
            (300, 400, 0, 0, 1000),    # also far away
        )
        assert detector._is_smoke_obscured((0, 0, 0), (200, 0, 0), 50, smokes) is False
