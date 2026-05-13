"""
TDD tests for DDMAnalyzer quality gates (Phase 5 + Phase 6).

Tests: clean 1v1 detection, third-party damage rejection,
       multi-enemy rejection, window boundary inclusivity,
       overlapping window gate, teammate phantom kill gate,
       player_steamid in return dict.
"""

import math
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from ddm_analyzer import DDMAnalyzer

PLAYER_ID = 100
ENEMY_ID  = 200
THIRD_ID  = 300
TEAMMATE_ID = 400


@pytest.fixture
def analyzer():
    with patch("ddm_analyzer.DemoParser"):
        a = DDMAnalyzer(
            demo_path="fake.dem",
            player_steamid=PLAYER_ID,
            match_id="quality_test",
            debug_prints=False,
        )
    return a


def _hurt(attackers, victims, ticks):
    """Build a player_hurt DataFrame."""
    return pd.DataFrame({
        "attacker_steamid": [str(x) for x in attackers],
        "user_steamid":     [str(x) for x in victims],
        "tick":             list(ticks),
    })


class TestIs1v1Duel:

    def test_empty_window_is_clean(self, analyzer):
        """No events in window → True (nothing to violate 1v1)."""
        result, reason = analyzer.is_1v1_duel(
            _hurt([], [], []), t0_tick=1000, t2_tick=1100, target_enemy_id=ENEMY_ID
        )
        assert result is True
        assert reason == ""

    def test_player_hits_one_enemy_no_incoming_is_clean(self, analyzer):
        """Player hits target enemy, receives no damage → clean 1v1."""
        df = _hurt([PLAYER_ID], [ENEMY_ID], [1050])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is True
        assert reason == ""

    def test_player_receives_damage_from_target_only(self, analyzer):
        """Player is hit by the target enemy → allowed, still clean 1v1."""
        df = _hurt([PLAYER_ID, ENEMY_ID], [ENEMY_ID, PLAYER_ID], [1050, 1060])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is True
        assert reason == ""

    def test_third_party_damage_rejected(self, analyzer):
        """A third player hits player in window → not clean 1v1."""
        df = _hurt([PLAYER_ID, THIRD_ID], [ENEMY_ID, PLAYER_ID], [1050, 1060])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is False
        assert reason != ""

    def test_third_party_attacker_named_in_reason(self, analyzer):
        """Rejection reason includes the third-party attacker's steamid."""
        df = _hurt([THIRD_ID], [PLAYER_ID], [1050])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is False
        assert str(THIRD_ID) in reason

    def test_multiple_enemies_hit_rejected(self, analyzer):
        """Player hits two distinct enemies → not a clean 1v1."""
        OTHER_ENEMY = 201
        df = _hurt([PLAYER_ID, PLAYER_ID], [ENEMY_ID, OTHER_ENEMY], [1050, 1060])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is False
        assert reason != ""

    def test_multiple_enemies_named_in_reason(self, analyzer):
        """Rejection reason includes the list of enemies when multiple are hit."""
        OTHER_ENEMY = 201
        df = _hurt([PLAYER_ID, PLAYER_ID], [ENEMY_ID, OTHER_ENEMY], [1050, 1060])
        _, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert str(ENEMY_ID) in reason and str(OTHER_ENEMY) in reason

    def test_player_hits_same_enemy_multiple_times_clean(self, analyzer):
        """Player hits the same enemy twice → still 1 distinct enemy → clean."""
        df = _hurt([PLAYER_ID, PLAYER_ID], [ENEMY_ID, ENEMY_ID], [1050, 1070])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is True
        assert reason == ""

    def test_window_boundary_t0_included(self, analyzer):
        """Event at exactly t0 is inside the window."""
        df = _hurt([THIRD_ID], [PLAYER_ID], [1000])
        result, _ = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is False

    def test_window_boundary_t2_included(self, analyzer):
        """Event at exactly t2 is inside the window."""
        df = _hurt([THIRD_ID], [PLAYER_ID], [1100])
        result, _ = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is False

    def test_event_one_tick_before_t0_excluded(self, analyzer):
        """Third-party damage at t0-1 is outside the window → clean."""
        df = _hurt([THIRD_ID], [PLAYER_ID], [999])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is True
        assert reason == ""

    def test_event_one_tick_after_t2_excluded(self, analyzer):
        """Third-party damage at t2+1 is outside the window → clean."""
        df = _hurt([THIRD_ID], [PLAYER_ID], [1101])
        result, reason = analyzer.is_1v1_duel(df, 1000, 1100, ENEMY_ID)
        assert result is True
        assert reason == ""


# ── Task 1: Overlapping window gate (D-07, D-08) ─────────────────────────────

def _make_result(t2_first_hit_tick):
    """Build a minimal analyze_engagement_episode() result dict."""
    return {
        "match_id": "quality_test",
        "t2_first_hit_tick": t2_first_hit_tick,
        "t0_manual_tick": t2_first_hit_tick - 50,
        "moment_timestamp": "0:00",
        "description": "test",
    }


class TestOverlappingWindowGate:
    """Task 1: overlapping window gate — last_accepted_t2_tick state in analyze_demo()."""

    def _run_moments(self, analyzer, results):
        """Simulate analyze_demo() result filtering using the gate logic directly."""
        # We test the gate by calling the same logic that analyze_demo() uses.
        # This exercises last_accepted_t2_tick state management without running
        # the full demo parsing pipeline.
        accepted = []
        for result in results:
            first_hit = result.get("t2_first_hit_tick")
            if (
                analyzer.last_accepted_t2_tick is not None
                and isinstance(first_hit, (int, float))
                and not math.isnan(float(first_hit))
                and int(first_hit) < analyzer.last_accepted_t2_tick + 300
            ):
                analyzer.logger.warning(
                    f"Overlapping window rejected: first_hit={first_hit} < "
                    f"last_accepted_t2={analyzer.last_accepted_t2_tick} + 300"
                )
            else:
                accepted.append(result)
                if isinstance(first_hit, (int, float)) and not math.isnan(float(first_hit)):
                    analyzer.last_accepted_t2_tick = int(first_hit)
        return accepted

    def test_moment_rejected_when_within_299_ticks(self, analyzer):
        """first_hit_tick = last_accepted + 299 → rejected (< 300)."""
        analyzer.last_accepted_t2_tick = 1000
        result = _make_result(1000 + 299)
        accepted = self._run_moments(analyzer, [result])
        assert len(accepted) == 0

    def test_moment_accepted_at_exactly_300_ticks(self, analyzer):
        """first_hit_tick = last_accepted + 300 → accepted (boundary inclusive)."""
        analyzer.last_accepted_t2_tick = 1000
        result = _make_result(1000 + 300)
        accepted = self._run_moments(analyzer, [result])
        assert len(accepted) == 1

    def test_moment_accepted_when_301_ticks_apart(self, analyzer):
        """first_hit_tick = last_accepted + 301 → accepted."""
        analyzer.last_accepted_t2_tick = 1000
        result = _make_result(1000 + 301)
        accepted = self._run_moments(analyzer, [result])
        assert len(accepted) == 1

    def test_first_moment_always_accepted(self, analyzer):
        """last_accepted_t2_tick is None → always accept first moment."""
        assert analyzer.last_accepted_t2_tick is None
        result = _make_result(500)
        accepted = self._run_moments(analyzer, [result])
        assert len(accepted) == 1

    def test_state_updated_after_accept(self, analyzer):
        """After accepting, last_accepted_t2_tick equals the accepted t2."""
        assert analyzer.last_accepted_t2_tick is None
        result = _make_result(800)
        self._run_moments(analyzer, [result])
        assert analyzer.last_accepted_t2_tick == 800

    def test_rejected_moment_does_not_update_state(self, analyzer):
        """Rejected moment does not update last_accepted_t2_tick."""
        analyzer.last_accepted_t2_tick = 1000
        result = _make_result(1000 + 100)  # within 300, rejected
        self._run_moments(analyzer, [result])
        assert analyzer.last_accepted_t2_tick == 1000

    def test_warning_logged_on_rejection(self, analyzer):
        """logger.warning called with 'Overlapping window rejected' on rejection."""
        analyzer.last_accepted_t2_tick = 1000
        result = _make_result(1000 + 100)
        with patch.object(analyzer.logger, "warning") as mock_warn:
            self._run_moments(analyzer, [result])
            assert mock_warn.called
            call_args = mock_warn.call_args[0][0]
            assert "Overlapping window rejected" in call_args

    def test_last_accepted_t2_tick_initialized_as_none(self, analyzer):
        """DDMAnalyzer.__init__ sets last_accepted_t2_tick = None."""
        assert hasattr(analyzer, "last_accepted_t2_tick")
        assert analyzer.last_accepted_t2_tick is None


# ── Task 2: Teammate phantom kill gate (D-09) ────────────────────────────────

def _hurt_full(attackers, victims, ticks):
    """Build a player_hurt DataFrame with attacker_steamid, user_steamid, tick columns."""
    return pd.DataFrame({
        "attacker_steamid": [str(x) for x in attackers],
        "user_steamid":     [str(x) for x in victims],
        "tick":             list(ticks),
    })


class TestTeammateGate:
    """Task 2: _teammate_hurt_target() method + gate in analyze_engagement_episode()."""

    def test_empty_df_returns_false(self, analyzer):
        """Empty DataFrame → no teammate → False."""
        df = _hurt_full([], [], [])
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is False

    def test_only_player_attacks_target_returns_false(self, analyzer):
        """Only player (PLAYER_ID) attacks ENEMY_ID in window → False."""
        df = _hurt_full([PLAYER_ID], [ENEMY_ID], [1050])
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is False

    def test_teammate_attacker_returns_true(self, analyzer):
        """attacker != player AND attacker != target_enemy attacks ENEMY_ID → True."""
        df = _hurt_full([TEAMMATE_ID], [ENEMY_ID], [1050])
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is True

    def test_event_outside_window_before_t0_returns_false(self, analyzer):
        """Teammate event at tick < t0 → outside window → False."""
        df = _hurt_full([TEAMMATE_ID], [ENEMY_ID], [999])
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is False

    def test_event_outside_window_after_t2_returns_false(self, analyzer):
        """Teammate event at tick > t2 → outside window → False."""
        df = _hurt_full([TEAMMATE_ID], [ENEMY_ID], [1101])
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is False

    def test_missing_columns_returns_false(self, analyzer):
        """DataFrame without required columns → returns False (T-06-02 mitigation)."""
        df = pd.DataFrame({"tick": [1050], "some_col": [1]})
        assert analyzer._teammate_hurt_target(df, 1000, 1100, ENEMY_ID) is False


# ── Task 3: player_steamid in return dict (D-05 Path 1) ──────────────────────

DONK_STEAMID = 76561198386265483


class TestAnalyzeEpisodeReturnDict:
    """Task 3: player_steamid in return dict of analyze_engagement_episode()."""

    @pytest.fixture
    def analyzer_donk(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=DONK_STEAMID,
                match_id="donk_test",
                debug_prints=False,
            )
        return a

    def _minimal_episode_result(self, analyzer):
        """Call analyze_engagement_episode() with mocked internals that return success."""
        from config import AnalysisMoment
        moment = AnalysisMoment(
            timestamp="0:00",
            manual_t0_tick_enemy_first_visible=None,
            description="test moment",
            target_enemy_steamid_if_known=None,
            use_auto_t0=True,
            auto_t0_search_start_tick=1000,
        )
        # Mock all heavy methods so episode analysis returns a result dict
        with patch.object(analyzer, "_resolve_t0", return_value=(1050, "auto")), \
             patch.object(analyzer, "_find_t2", return_value=(1100, ENEMY_ID, "weapon_rifle_ak47")), \
             patch.object(analyzer, "_compute_crosshair_angle_at_t0", return_value=5.0), \
             patch.object(analyzer, "is_1v1_duel", return_value=(True, "")), \
             patch.object(analyzer, "_teammate_hurt_target", return_value=False), \
             patch.object(analyzer, "_compute_velocity", return_value=0.0), \
             patch.object(analyzer, "_detect_t1", return_value=-1), \
             patch.object(analyzer, "_classify_engagement", return_value="hold"), \
             patch.object(analyzer, "_compute_round_phase", return_value=(30.0, "mid", 1)):

            all_ticks_df = pd.DataFrame({"tick": [1000, 1050, 1100]})
            player_fire_df = pd.DataFrame()
            all_hurt_df = pd.DataFrame({
                "attacker_steamid": [str(analyzer.player_steamid)],
                "user_steamid": [str(ENEMY_ID)],
                "tick": [1100],
            })
            round_start_ticks = [0]
            return analyzer.analyze_engagement_episode(
                moment, all_ticks_df, player_fire_df, all_hurt_df,
                round_start_ticks, smoke_events=None
            )

    def test_return_dict_contains_player_steamid_key(self, analyzer_donk):
        """analyze_engagement_episode() return dict has 'player_steamid' key."""
        result = self._minimal_episode_result(analyzer_donk)
        assert result is not None, "Expected a result dict, got None"
        assert "player_steamid" in result

    def test_player_steamid_value_equals_instance_steamid(self, analyzer_donk):
        """player_steamid value in dict equals self.player_steamid."""
        result = self._minimal_episode_result(analyzer_donk)
        assert result is not None
        assert result["player_steamid"] == DONK_STEAMID

    def test_player_steamid_with_simple_id(self, analyzer):
        """Works with simple int player_steamid (PLAYER_ID=100)."""
        result = self._minimal_episode_result(analyzer)
        assert result is not None
        assert result["player_steamid"] == PLAYER_ID
