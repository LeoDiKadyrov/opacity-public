"""
TDD tests for T0Detector.find_t0() BVH ray-casting (Phase 3b).

Tests: find_t0() — BVH+AABB visibility detection with smoke/flash overlay.
Mocks: awpy.visibility.VisibilityChecker
"""

from unittest.mock import Mock, patch
import pandas as pd
import pytest
from t0_detector import T0Detector, _AABB_OFFSETS


class TestFindT0:
    """BVH ray-casting T0 detection with smoke/flash suppression."""

    @pytest.fixture
    def detector(self):
        """Create T0Detector with mocked BVH."""
        # Patch VisibilityChecker during init
        with patch("t0_detector.VisibilityChecker"):
            detector = T0Detector(map_name="de_ancient")
            detector.checker = Mock()  # Replace with controllable mock
            return detector

    def test_find_t0_empty_player_data(self, detector):
        """No player ticks in search window — early exit returns bare 'not_found' (no counter parens)."""
        all_ticks = pd.DataFrame({
            "steamid": [999],
            "tick": [100],
            "X": [0.0], "Y": [0.0], "Z": [0.0]
        })

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick is None
        assert result_method == "not_found"  # bare string, no counter parens

    def test_find_t0_empty_enemy_data(self, detector):
        """No enemy ticks in search window — early exit returns bare 'not_found' (no counter parens)."""
        all_ticks = pd.DataFrame({
            "steamid": [123],
            "tick": [100],
            "X": [0.0], "Y": [0.0], "Z": [0.0]
        })

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick is None
        assert result_method == "not_found"  # bare string, no counter parens

    def test_find_t0_visible_immediately(self, detector):
        """T0 found at first tick (ray is visible immediately)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 100],
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 0.0]
        })

        detector.checker.is_visible.return_value = True  # Mock: ray is visible

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick == 100
        assert result_method == "BVH+AABB"

    def test_find_t0_found_after_failed_ticks(self, detector):
        """T0 not found at tick 100, found at tick 110 (visibility succeeds)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 123, 456, 456],
            "tick": [100, 110, 100, 110],
            "X": [0.0, 0.0, 100.0, 100.0],
            "Y": [0.0, 0.0, 0.0, 0.0],
            "Z": [60.0, 60.0, 60.0, 60.0],
            "duck_amount": [0.0, 0.0, 0.0, 0.0]
        })

        # Tick 100: all 9 AABB targets invisible; tick 110: first target visible
        # 9 = 4 lower corners + 4 upper corners + 1 center mass (see _AABB_OFFSETS)
        detector.checker.is_visible.side_effect = [False]*9 + [True]

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick == 110
        assert result_method == "BVH+AABB"

    def test_find_t0_never_found(self, detector):
        """No visible rays across all ticks."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 123, 456, 456],
            "tick": [100, 110, 100, 110],
            "X": [0.0, 0.0, 100.0, 100.0],
            "Y": [0.0, 0.0, 0.0, 0.0],
            "Z": [60.0, 60.0, 60.0, 60.0],
            "duck_amount": [0.0, 0.0, 0.0, 0.0]
        })

        detector.checker.is_visible.return_value = False  # All rays blocked by walls

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick is None
        assert "not_found" in result_method
        assert "vis_failed=2" in result_method  # 2 ticks, visibility failed

    def test_find_t0_flash_suppression(self, detector):
        """All ticks within flash window (T0 suppressed by blindness)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 100],
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 0.0]
        })

        detector.checker.is_visible.return_value = True  # Would be visible, but...
        flash_intervals = [(100, 200)]  # Player is blind during search window

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200,
            flash_intervals=flash_intervals
        )

        assert result_tick is None
        assert "flash_skip=1" in result_method  # 1 tick skipped due to flash

    def test_find_t0_smoke_suppression(self, detector):
        """All rays obscured by smoke (T0 suppressed by smoke)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 100],
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 0.0]
        })

        active_smokes = pd.DataFrame({
            "X": [50.0],
            "Y": [0.0],
            "Z": [60.0],
            "start_tick": [100],
            "end_tick": [200]
        })

        detector.checker.is_visible.return_value = True  # Would be visible, but...

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200,
            active_smokes=active_smokes
        )

        assert result_tick is None
        assert "smoke_blocked=1" in result_method  # 1 tick blocked by smoke

    def test_find_t0_enemy_crouching(self, detector):
        """Enemy is crouching: AABB uses _HULL_HEIGHT_CROUCHING (54) not standing (72)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 100],
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 1.0]  # Enemy crouching
        })

        detector.checker.is_visible.return_value = True

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick == 100
        # Verify ray targets use crouching hull height (54): upper corners at Z = 60 + 0.8*54 = 103.2
        # (not 60 + 0.8*72 = 117.6 which would be standing)
        call_args = [call[0] for call in detector.checker.is_visible.call_args_list]
        target_z_values = [target[2] for _, target in call_args]
        assert max(target_z_values) < 110, (
            f"Max target Z {max(target_z_values):.1f} suggests standing hull (72) was used, "
            f"expected crouching hull (54): max Z should be ~{60 + 0.8*54:.1f}"
        )

    def test_find_t0_multiple_enemy_ticks(self, detector):
        """Multiple enemy ticks in window (matches are found per tick)."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 123, 123, 456, 456, 456],
            "tick": [100, 110, 120, 100, 110, 120],
            "X": [0.0, 0.0, 0.0, 100.0, 110.0, 120.0],
            "Y": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "Z": [60.0, 60.0, 60.0, 60.0, 60.0, 60.0],
            "duck_amount": [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        })

        # Tick 100: 9 targets invisible; Tick 110: 9 targets invisible; Tick 120: first visible
        # 9 = 4 lower corners + 4 upper corners + 1 center mass (see _AABB_OFFSETS)
        detector.checker.is_visible.side_effect = [False]*9 + [False]*9 + [True]

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick == 120
        assert result_method == "BVH+AABB"

    def test_find_t0_partial_flash_window(self, detector):
        """Flash window covers some ticks, but T0 found after flash ends."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 123, 456, 456],
            "tick": [100, 110, 100, 110],
            "X": [0.0, 0.0, 100.0, 100.0],
            "Y": [0.0, 0.0, 0.0, 0.0],
            "Z": [60.0, 60.0, 60.0, 60.0],
            "duck_amount": [0.0, 0.0, 0.0, 0.0]
        })

        detector.checker.is_visible.return_value = True
        flash_intervals = [(100, 105)]  # Flash covers tick 100 only

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200,
            flash_intervals=flash_intervals
        )

        assert result_tick == 110  # Found after flash window
        assert result_method == "BVH+AABB"  # T0 is found, not suppressed

    def test_find_t0_no_matching_enemy_tick(self, detector):
        """Player tick exists but no enemy tick at that moment."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 110],  # Player at 100, enemy at 110 (no match at 100)
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 0.0]
        })

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick is None
        assert "no_match=1" in result_method

    def test_find_t0_diagnostics_format(self, detector):
        """Diagnostic string includes all failure reasons when T0 not found."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456],
            "tick": [100, 100],
            "X": [0.0, 100.0],
            "Y": [0.0, 0.0],
            "Z": [60.0, 60.0],
            "duck_amount": [0.0, 0.0]
        })

        detector.checker.is_visible.return_value = False

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        assert result_tick is None
        assert "not_found(" in result_method
        assert "p=1" in result_method  # 1 player tick
        assert "e=1" in result_method  # 1 enemy tick
        assert "no_match=0" in result_method
        assert "flash_skip=0" in result_method
        assert "smoke_blocked=0" in result_method
        assert "vis_failed=1" in result_method  # 1 tick failed visibility

    def test_find_t0_duplicate_enemy_tick(self, detector):
        """Duplicate enemy rows at same tick (e.g. overlapping search windows) — takes first row."""
        all_ticks = pd.DataFrame({
            "steamid": [123, 456, 456],
            "tick": [100, 100, 100],  # Two enemy rows at tick 100
            "X": [0.0, 100.0, 200.0],  # Different X positions
            "Y": [0.0, 0.0, 0.0],
            "Z": [60.0, 60.0, 60.0],
            "duck_amount": [0.0, 0.0, 0.0]
        })

        detector.checker.is_visible.return_value = True

        result_tick, result_method = detector.find_t0(
            all_ticks, player_steamid=123, enemy_steamid=456,
            search_start_tick=100, search_end_tick=200
        )

        # Duplicate tick guard takes first row (X=100.0), not second (X=200.0)
        assert result_tick == 100
        assert result_method == "BVH+AABB"
        first_call_target = detector.checker.is_visible.call_args_list[0][0][1]
        assert abs(first_call_target[0] - 100.0) <= 16 + 0.01, (
            "Should use first enemy row (X=100), not second (X=200)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Phase 9.1 Wave 0 — RED tests for SC1 (center-first AABB) and SC4 (sid cache)
#
# These tests are intentionally failing on current code:
#   - _AABB_OFFSETS[0] is currently a lower corner, not the center mass.
#   - find_t0() does NOT yet accept a ``ticks_by_sid`` kwarg.
# Plans 09.1-01 (SC1) and 09.1-04 (SC4) turn them GREEN.
# ─────────────────────────────────────────────────────────────────────────────


def test_aabb_offsets_center_first():
    """SC1: center mass offset (0, 0, 0.5) must be first in _AABB_OFFSETS.

    Most-likely-visible target should be checked first so find_t0 can short
    circuit before iterating the 8 corners. Reordering does NOT change
    semantics — find_t0 returns the first tick with ANY visible ray.
    """
    assert _AABB_OFFSETS[0] == (0.0, 0.0, 0.5), (
        f"Expected center mass (0.0, 0.0, 0.5) at index 0, got {_AABB_OFFSETS[0]}. "
        "SC1: center-first ordering not yet applied (will be fixed in plan 09.1-01)."
    )


def test_find_t0_uses_ticks_by_sid_when_provided():
    """SC4: when ticks_by_sid is supplied, find_t0 short-circuits the bool-filter.

    Passes a sentinel empty all_ticks_df that would yield no rows under the
    legacy bool-filter path, plus a populated cache. If find_t0 honors the
    cache it must still locate T0 at tick=100.
    """
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector(map_name="de_ancient")
        detector.checker = Mock()
        detector.checker.is_visible.return_value = True

    cached = {
        123: pd.DataFrame({
            "tick": [100],
            "X": [0.0], "Y": [0.0], "Z": [60.0],
            "duck_amount": [0.0],
        }),
        456: pd.DataFrame({
            "tick": [100],
            "X": [100.0], "Y": [0.0], "Z": [60.0],
            "duck_amount": [0.0],
        }),
    }
    sentinel = pd.DataFrame(columns=["tick", "steamid", "X", "Y", "Z", "duck_amount"])

    result_tick, result_method = detector.find_t0(
        sentinel,
        player_steamid=123,
        enemy_steamid=456,
        search_start_tick=100,
        search_end_tick=200,
        ticks_by_sid=cached,
    )

    assert result_tick == 100, (
        "find_t0 should consume cached per-sid frames via ticks_by_sid kwarg "
        "(SC4 — kwarg not yet implemented)."
    )
    assert result_method == "BVH+AABB"


def test_find_t0_fallback_when_ticks_by_sid_none():
    """SC4 backward-compat: ticks_by_sid=None preserves the bool-filter path.

    Existing 322 tests must keep passing without change after #4 ships.
    Validates the explicit-None branch still resolves T0 from all_ticks_df.
    """
    with patch("t0_detector.VisibilityChecker"):
        detector = T0Detector(map_name="de_ancient")
        detector.checker = Mock()
        detector.checker.is_visible.return_value = True

    all_ticks = pd.DataFrame({
        "steamid": [123, 456],
        "tick": [100, 100],
        "X": [0.0, 100.0],
        "Y": [0.0, 0.0],
        "Z": [60.0, 60.0],
        "duck_amount": [0.0, 0.0],
    })

    result_tick, result_method = detector.find_t0(
        all_ticks,
        player_steamid=123,
        enemy_steamid=456,
        search_start_tick=100,
        search_end_tick=200,
        ticks_by_sid=None,
    )

    assert result_tick == 100
    assert result_method == "BVH+AABB"
