"""
TDD tests for DDMAnalyzer core logic (Phase 4).

Tests: auto_build_moments() — clustering, enemy discovery, analysis window setup
       analyze_engagement_episode() — T0 source, gates, schema, timing
       analyze_demo() — T0 deduplication (Phase 6)
       analyze_demo() — orchestration: parsing fallbacks, DIAG branches, bulk mode
"""

from unittest.mock import Mock, patch
import math
import numpy as np
import pandas as pd
import pytest
from ddm_analyzer import DDMAnalyzer
from config import AnalysisMoment


class TestAutoBuildMoments:
    """Engagement clustering, enemy discovery, and analysis window setup."""

    @pytest.fixture
    def analyzer(self):
        """Create DDMAnalyzer with mocked DemoParser."""
        with patch("ddm_analyzer.DemoParser"):
            analyzer = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=76561198386265483,
                match_id="test_match",
                debug_prints=False
            )
            analyzer.t0_detector = None  # Not needed for auto_build_moments tests
            return analyzer

    def test_auto_build_moments_empty_input(self, analyzer):
        """Empty player_hurt DataFrame (0 rows, correct columns) → returns 0, no moments created."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": [],
            "user_steamid": [],
            "tick": [],
        })

        result = analyzer.auto_build_moments(all_hurt_df)

        assert result == 0
        assert len(analyzer.analysis_moments) == 0

    def test_auto_build_moments_missing_columns_returns_zero(self, analyzer):
        """DataFrame missing attacker_steamid (e.g. bare pd.DataFrame()) → returns 0, no crash."""
        result = analyzer.auto_build_moments(pd.DataFrame())

        assert result == 0
        assert len(analyzer.analysis_moments) == 0

    def test_auto_build_moments_single_hit(self, analyzer):
        """Single hit by player → creates 1 moment."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],  # enemy steamid
            "tick": [1000],
        })

        result = analyzer.auto_build_moments(all_hurt_df)

        assert result == 1
        assert len(analyzer.analysis_moments) == 1
        assert analyzer.analysis_moments[0].target_enemy_steamid_if_known == 76561198315710555

    def test_auto_build_moments_multiple_hits_within_gap(self, analyzer):
        """Multiple hits with gaps < cluster_gap_ticks → 1 cluster."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710555", "76561198315710555"],
            "tick": [1000, 1100, 1150],
        })
        result = analyzer.auto_build_moments(all_hurt_df, cluster_gap_ticks=320)
        assert result == 1
        assert analyzer.analysis_moments[0].description == "bulk_auto first_hit=1000"

    def test_auto_build_moments_multiple_clusters(self, analyzer):
        """Multiple hits separated by gap > cluster_gap_ticks → multiple clusters."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710556", "76561198315710556"],
            "tick": [1000, 1500, 1600],
        })
        result = analyzer.auto_build_moments(all_hurt_df, cluster_gap_ticks=320)
        assert result == 2
        assert analyzer.analysis_moments[1].description == "bulk_auto first_hit=1500"

    def test_auto_build_moments_knife_filtering(self, analyzer):
        """Knife hits excluded from clustering."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710555"],
            "weapon": ["knife_t", "ak47"],
            "tick": [1000, 1050],
        })
        result = analyzer.auto_build_moments(all_hurt_df)
        assert result == 1
        assert analyzer.analysis_moments[0].description == "bulk_auto first_hit=1050"

    def test_auto_build_moments_awp_filtering(self, analyzer):
        """AWP hits excluded from clustering."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710555"],
            "weapon": ["awp", "ak47"],
            "tick": [1000, 1050],
        })
        result = analyzer.auto_build_moments(all_hurt_df)
        assert result == 1
        assert analyzer.analysis_moments[0].description == "bulk_auto first_hit=1050"

    def test_auto_build_moments_search_window_clamped(self, analyzer):
        """search_start clamps to 0 when negative."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],
            "tick": [100],
        })
        analyzer.auto_build_moments(all_hurt_df, lookback_ticks=200)
        assert analyzer.analysis_moments[0].auto_t0_search_start_tick == 0

    def test_auto_build_moments_search_window_positive(self, analyzer):
        """search_start = first_hit_tick - lookback_ticks."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],
            "tick": [1000],
        })
        analyzer.auto_build_moments(all_hurt_df, lookback_ticks=300)
        assert analyzer.analysis_moments[0].auto_t0_search_start_tick == 700

    def test_auto_build_moments_timestamp(self, analyzer):
        """Timestamp calculated as MM:SS. (tickrate is 64 by default in fixture)"""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],
            "tick": [3840],  # 60 sec
        })
        analyzer.auto_build_moments(all_hurt_df)
        assert analyzer.analysis_moments[0].timestamp == "1:00"

    def test_auto_build_moments_enemy_steamid_valid(self, analyzer):
        """Valid enemy steamid stored as integer."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],
            "tick": [1000],
        })
        analyzer.auto_build_moments(all_hurt_df)
        moment = analyzer.analysis_moments[0]
        assert moment.target_enemy_steamid_if_known == 76561198315710555
        assert isinstance(moment.target_enemy_steamid_if_known, int)

    def test_auto_build_moments_enemy_steamid_invalid(self, analyzer):
        """Invalid enemy steamid stored as None."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["invalid"],
            "tick": [1000],
        })
        analyzer.auto_build_moments(all_hurt_df)
        assert analyzer.analysis_moments[0].target_enemy_steamid_if_known is None

    def test_auto_build_moments_uses_first_victim(self, analyzer):
        """Multiple enemies in cluster → uses first hit victim."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710556"],
            "tick": [1000, 1050],
        })
        analyzer.auto_build_moments(all_hurt_df, cluster_gap_ticks=320)
        assert analyzer.analysis_moments[0].target_enemy_steamid_if_known == 76561198315710555

    def test_auto_build_moments_use_auto_t0_flag(self, analyzer):
        """All moments have use_auto_t0=True."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "76561198386265483"],
            "user_steamid": ["76561198315710555", "76561198315710556"],
            "tick": [1000, 2000],
        })
        analyzer.auto_build_moments(all_hurt_df)
        for moment in analyzer.analysis_moments:
            assert moment.use_auto_t0 is True
            assert moment.manual_t0_tick_enemy_first_visible is None

    def test_auto_build_moments_excludes_other_players_hits(self, analyzer):
        """Hits by other players are excluded — only attacker_steamid == player_steamid counts."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483", "99999999999999999"],
            "user_steamid": ["76561198315710555", "76561198315710555"],
            "tick": [1000, 1050],
        })
        result = analyzer.auto_build_moments(all_hurt_df)
        assert result == 1  # Only our player's hit
        assert analyzer.analysis_moments[0].description == "bulk_auto first_hit=1000"

    def test_auto_build_moments_analysis_window_stored(self, analyzer):
        """Custom analysis_window_seconds is stored on the moment."""
        all_hurt_df = pd.DataFrame({
            "attacker_steamid": ["76561198386265483"],
            "user_steamid": ["76561198315710555"],
            "tick": [1000],
        })
        analyzer.auto_build_moments(all_hurt_df, analysis_window_seconds=12)
        assert analyzer.analysis_moments[0].analysis_window_seconds_after_t0 == 12


class TestAnalyzeEngagementEpisode:

    PLAYER_SID = 76561198386265483
    ENEMY_SID  = 76561198315710555

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="test_ep",
            )
        # _smoke_events removed; smoke_events is now passed explicitly
        a.t0_detector = Mock()
        a.t0_detector.find_t0 = Mock(return_value=(None, "not_found"))
        return a

    @staticmethod
    def _empty_fire():
        return pd.DataFrame({"tick": []})

    def _make_ticks(self, t0, player_dx=0.0, enemy_dx=0.1):
        return pd.DataFrame({
            "steamid": [self.PLAYER_SID, self.PLAYER_SID, self.ENEMY_SID, self.ENEMY_SID],
            "tick":    [t0,              t0+1,             t0,             t0+1],
            "X":       [0.0,             player_dx,        100.0,          100.0+enemy_dx],
            "Y":       [0.0,             0.0,              0.0,            0.0],
            "Z":       [0.0,             0.0,              0.0,            0.0],
            "pitch":   [0.0,             0.0,              0.0,            0.0],
            "yaw":     [0.0,             0.0,              0.0,            0.0],
        })

    def _make_hurt(self, t2, weapon='ak47'):
        return pd.DataFrame({
            "tick":             [t2],
            "attacker_steamid": [str(self.PLAYER_SID)],
            "user_steamid":     [str(self.ENEMY_SID)],
            "weapon":           [weapon],
        })

    def _manual_moment(self, t0=1000, window_sec=8):
        return AnalysisMoment(
            timestamp="0:15",
            manual_t0_tick_enemy_first_visible=t0,
            description="test",
            analysis_window_seconds_after_t0=window_sec,
            use_auto_t0=False,
        )

    def _auto_moment(self, search_start=700, window_sec=8):
        return AnalysisMoment(
            timestamp="0:15",
            manual_t0_tick_enemy_first_visible=None,
            description="test",
            analysis_window_seconds_after_t0=window_sec,
            use_auto_t0=True,
            auto_t0_search_start_tick=search_start,
            target_enemy_steamid_if_known=self.ENEMY_SID,
        )

    # Rejection paths

    def test_returns_none_no_t0_available(self, analyzer):
        """use_auto_t0=False and manual_t0_tick=None -> None."""
        moment = AnalysisMoment(
            timestamp="0:15", manual_t0_tick_enemy_first_visible=None,
            description="test", use_auto_t0=False,
        )
        result = analyzer.analyze_engagement_episode(
            moment, pd.DataFrame(), self._empty_fire(), pd.DataFrame()
        )
        assert result is None

    def test_returns_none_auto_t0_detector_unavailable(self, analyzer):
        """use_auto_t0=True but t0_detector is None -> None."""
        analyzer.t0_detector = None
        result = analyzer.analyze_engagement_episode(
            self._auto_moment(), pd.DataFrame(), self._empty_fire(), pd.DataFrame()
        )
        assert result is None

    def test_returns_none_auto_t0_not_found(self, analyzer):
        """BVH find_t0 returns (None, ...) -> None."""
        analyzer.t0_detector.find_t0.return_value = (None, "not_found")
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                self._auto_moment(search_start=700),
                self._make_ticks(900),
                self._empty_fire(),
                self._make_hurt(1000),
            )
        assert result is None

    def test_returns_none_auto_t0_offset_too_small(self, analyzer):
        """Auto T0 within T0_MIN_OFFSET_TICKS of search_start -> rejected."""
        search_start = 700
        t0_too_close = search_start + 5  # 5 < T0_MIN_OFFSET_TICKS=20
        analyzer.t0_detector.find_t0.return_value = (t0_too_close, "BVH+AABB")
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                self._auto_moment(search_start=search_start),
                self._make_ticks(t0_too_close),
                self._empty_fire(),
                self._make_hurt(t0_too_close + 50),
            )
        assert result is None

    def test_returns_none_no_hit_in_window(self, analyzer):
        """No player_hurt events in window -> None."""
        t0 = 1000
        empty_hurt = pd.DataFrame(
            {"tick": [], "attacker_steamid": [], "user_steamid": [], "weapon": []}
        )
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), empty_hurt
        )
        assert result is None

    def test_returns_none_awp_hit(self, analyzer):
        """First hit with AWP weapon -> None."""
        t0 = 1000
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0),
            self._make_ticks(t0),
            self._empty_fire(),
            self._make_hurt(t0 + 50, weapon='awp'),
        )
        assert result is None

    def test_returns_none_enemy_velocity_too_high(self, analyzer):
        """Enemy moving >= ENEMY_VELOCITY_HOLD_THRESHOLD_UPS -> None."""
        t0 = 1000
        # 2.0 units/tick * 64 ticks/sec = 128 u/s (>= threshold 80, set in Phase 6)
        ticks = self._make_ticks(t0, enemy_dx=2.0)
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), ticks, self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result is None

    # Success paths

    def test_manual_t0_returns_result_dict(self, analyzer):
        """Manual T0 with hit in window -> returns non-None dict."""
        t0 = 1000
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0),
            self._make_ticks(t0),
            self._empty_fire(),
            self._make_hurt(t0 + 50),
        )
        assert result is not None
        assert isinstance(result, dict)

    def test_result_dict_required_schema(self, analyzer):
        """Result contains all CSV schema keys."""
        t0 = 1000
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), self._make_hurt(t0 + 50)
        )
        required = {
            "match_id", "moment_timestamp", "description", "t0_source",
            "t0_manual_tick", "t1_aim_start_tick", "t2_first_hit_tick",
            "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
            "target_enemy_id", "player_velocity_at_t0_ups",
            "enemy_velocity_at_t0_ups", "engagement_type",
        }
        assert required.issubset(result.keys())

    def test_t0_source_manual(self, analyzer):
        """Manual T0 -> t0_source = 'manual'."""
        t0 = 1000
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result["t0_source"] == "manual"

    def test_t0_source_from_bvh(self, analyzer):
        """Auto T0 -> t0_source matches method string from find_t0."""
        search_start, t0 = 700, 750  # offset=50 > T0_MIN_OFFSET_TICKS=20
        analyzer.t0_detector.find_t0.return_value = (t0, "BVH+AABB")
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                self._auto_moment(search_start=search_start),
                self._make_ticks(t0),
                self._empty_fire(),
                self._make_hurt(t0 + 50),
            )
        assert result is not None
        assert result["t0_source"] == "BVH+AABB"

    # Classification

    def test_engagement_type_peek(self, analyzer):
        """Player velocity >= 50 u/s at T0 -> engagement_type = 'peek'."""
        t0 = 1000
        # 1.0 unit/tick * 64 ticks/sec = 64 u/s (>= peek threshold 50)
        ticks = self._make_ticks(t0, player_dx=1.0)
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), ticks, self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result is not None
        assert result["engagement_type"] == "peek"

    def test_engagement_type_hold(self, analyzer):
        """Player stationary at T0 -> engagement_type = 'hold'."""
        t0 = 1000
        ticks = self._make_ticks(t0, player_dx=0.0)
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), ticks, self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result is not None
        assert result["engagement_type"] == "hold"

    # T1 and timing

    def test_t1_not_found_gives_nan(self, analyzer):
        """No sustained aim movement -> t1_aim_start_tick is NaN."""
        import math
        t0 = 1000
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result is not None
        assert math.isnan(result["t1_aim_start_tick"])

    def test_rt_visible_to_hit_ms(self, analyzer):
        """rt_visible_to_hit_ms = (t2 - t0) * ms_per_tick."""
        t0, t2 = 1000, 1064  # 64 ticks * 15.625ms = 1000ms
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), self._make_hurt(t2)
        )
        assert result is not None
        expected_ms = (t2 - t0) * (1000 / 64)
        assert abs(result["rt_visible_to_hit_ms"] - expected_ms) < 0.1

    # Coverage gap fixes

    def test_returns_none_not_clean_1v1(self, analyzer):
        """Third-party damage during engagement window → is_1v1_duel rejects → None."""
        t0 = 1000
        # Third-party event at t0+40 (before t2=t0+50) so it falls inside the [t0, t2] window.
        hurt = pd.DataFrame({
            "tick":             [t0 + 40,          t0 + 50],
            "attacker_steamid": ["999999999999",    str(self.PLAYER_SID)],
            "user_steamid":     [str(self.PLAYER_SID), str(self.ENEMY_SID)],
            "weapon":           ["ak47",               "ak47"],
        })
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), self._make_ticks(t0), self._empty_fire(), hurt
        )
        assert result is None

    def test_returns_none_auto_t0_no_hits_unknown_enemy(self, analyzer):
        """target_enemy_steamid_if_known=None with no player hits in search window → None."""
        moment = AnalysisMoment(
            timestamp="0:15",
            manual_t0_tick_enemy_first_visible=None,
            description="test",
            use_auto_t0=True,
            auto_t0_search_start_tick=700,
            target_enemy_steamid_if_known=None,
        )
        empty_hurt = pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid", "weapon"])
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                moment, self._make_ticks(900), self._empty_fire(), empty_hurt
            )
        assert result is None

    def test_auto_t0_discovers_enemy_from_hits_when_not_provided(self, analyzer):
        """target_enemy_steamid_if_known=None with valid hits → enemy auto-discovered, BVH proceeds."""
        t0, search_start = 730, 700  # offset=30 ≥ T0_MIN_OFFSET_TICKS=20
        moment = AnalysisMoment(
            timestamp="0:15",
            manual_t0_tick_enemy_first_visible=None,
            description="test",
            use_auto_t0=True,
            auto_t0_search_start_tick=search_start,
            target_enemy_steamid_if_known=None,
        )
        hurt = pd.DataFrame({
            "tick":             [800],
            "attacker_steamid": [str(self.PLAYER_SID)],
            "user_steamid":     [str(self.ENEMY_SID)],   # valid 17-digit steamid
            "weapon":           ["ak47"],
        })
        analyzer.t0_detector.find_t0.return_value = (t0, "BVH+AABB")
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                moment, self._make_ticks(t0), self._empty_fire(), hurt
            )
        assert result is not None
        assert result["t0_source"] == "BVH+AABB"

    def test_returns_none_auto_t0_all_hits_invalid_steamid(self, analyzer):
        """target_enemy_steamid_if_known=None with hits whose user_steamid fails the 10-digit filter → None.

        find_t0 is set to succeed so that None can only come from the steamid filter
        rejecting all candidates before BVH is ever called with a valid enemy.
        """
        search_start = 700
        t0_would_succeed = search_start + 30  # offset=30 ≥ T0_MIN_OFFSET_TICKS=20
        analyzer.t0_detector.find_t0.return_value = (t0_would_succeed, "BVH+AABB")
        moment = AnalysisMoment(
            timestamp="0:15",
            manual_t0_tick_enemy_first_visible=None,
            description="test",
            use_auto_t0=True,
            auto_t0_search_start_tick=search_start,
            target_enemy_steamid_if_known=None,
        )
        hurt = pd.DataFrame({
            "tick":             [800],
            "attacker_steamid": [str(self.PLAYER_SID)],
            "user_steamid":     ["bot"],   # fails ^\d{10,}$ filter → no valid enemy found
            "weapon":           ["ak47"],
        })
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                moment, self._make_ticks(t0_would_succeed), self._empty_fire(), hurt
            )
        assert result is None

    def test_non_empty_flash_intervals_are_logged(self, analyzer):
        """Flash intervals in auto-T0 window are passed to find_t0 (non-empty flash_intervals path)."""
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[(800, 900)]):
            result = analyzer.analyze_engagement_episode(
                self._auto_moment(search_start=700),
                self._make_ticks(900),
                self._empty_fire(),
                self._make_hurt(1000),
            )
        # BVH mock returns (None, "not_found") → rejected, but the flash-interval logging branch was reached
        assert result is None

    @pytest.mark.parametrize("offset,should_pass", [
        (0,  False),   # t0 == search_start → rejected
        (19, False),   # offset=19 < T0_MIN_OFFSET_TICKS=20 → rejected
        (20, True),    # offset=20 == T0_MIN_OFFSET_TICKS → accepted
        (21, True),    # offset=21 > T0_MIN_OFFSET_TICKS → accepted
    ])
    def test_t0_min_offset_ticks_gate(self, analyzer, offset, should_pass):
        """T0 offset from search_start boundary: < 20 ticks → rejected, >= 20 → accepted."""
        search_start = 700
        t0 = search_start + offset
        t2 = t0 + 50  # always far enough ahead for a valid hit
        analyzer.t0_detector.find_t0.return_value = (t0, "BVH+AABB")
        with patch("t0_detector.T0Detector.parse_flash_intervals", return_value=[]):
            result = analyzer.analyze_engagement_episode(
                self._auto_moment(search_start=search_start),
                self._make_ticks(t0),
                self._empty_fire(),
                self._make_hurt(t2),
            )
        if should_pass:
            assert result is not None, f"offset={offset} should be accepted"
        else:
            assert result is None, f"offset={offset} should be rejected"

    def test_debug_prints_enabled_exercises_t1_loop(self, analyzer):
        """debug_prints=True exercises per-tick debug logging inside the T1 aim search loop."""
        analyzer.debug_prints = True
        t0 = 1000
        base = t0 + 10  # after grace period (T0+7 ticks)
        rows = self._make_ticks(t0).to_dict("records")
        rows += [
            {"steamid": self.PLAYER_SID, "tick": base,   "X": 0.0,   "Y": 0.0, "Z": 0.0, "yaw": 30.0, "pitch": 5.0},
            {"steamid": self.PLAYER_SID, "tick": base+1, "X": 0.0,   "Y": 0.0, "Z": 0.0, "yaw": 20.0, "pitch": 3.0},
            {"steamid": self.ENEMY_SID,  "tick": base,   "X": 100.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0,  "pitch": 0.0},
            {"steamid": self.ENEMY_SID,  "tick": base+1, "X": 100.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0,  "pitch": 0.0},
        ]
        result = analyzer.analyze_engagement_episode(
            self._manual_moment(t0=t0), pd.DataFrame(rows), self._empty_fire(), self._make_hurt(t0 + 50)
        )
        assert result is not None


class TestDDMAnalyzerInit:
    """Tests for DDMAnalyzer.__init__ error paths and fallback behaviour."""

    def test_demoparser_failure_propagates_exception(self):
        """If DemoParser raises, the exception propagates to the caller."""
        with patch("ddm_analyzer.DemoParser") as MockParser:
            MockParser.side_effect = RuntimeError("demo file not found")
            with pytest.raises(RuntimeError):
                DDMAnalyzer(demo_path="fake.dem", player_steamid=100, match_id="test")

    def test_parse_header_failure_defaults_map_name_to_unknown(self):
        """If parse_header() raises, map_name falls back to 'unknown'."""
        with patch("ddm_analyzer.DemoParser") as MockParser, \
             patch("ddm_analyzer.T0Detector"):
            MockParser.return_value.parse_header.side_effect = RuntimeError("header broken")
            a = DDMAnalyzer(demo_path="fake.dem", player_steamid=100, match_id="test")
        assert a.map_name == "unknown"

    def test_t0detector_success_sets_detector(self):
        """If T0Detector initialises without error, t0_detector is set to the instance."""
        with patch("ddm_analyzer.DemoParser"), \
             patch("ddm_analyzer.T0Detector") as MockT0:
            a = DDMAnalyzer(demo_path="fake.dem", player_steamid=100, match_id="test")
        assert a.t0_detector is MockT0.return_value

    def test_no_match_id_uses_demo_filename_hash(self):
        """When match_id is omitted, a 10-character hex hash of the demo filename is used."""
        with patch("ddm_analyzer.DemoParser"), \
             patch("ddm_analyzer.T0Detector"):
            a = DDMAnalyzer(demo_path="my_match.dem", player_steamid=100)
        assert len(a.match_id) == 10
        assert all(c in "0123456789abcdef" for c in a.match_id)


class TestAnalyzeDemoDeduplication:
    """Tests for T0 deduplication logic in analyze_demo() (Phase 6).

    Two moments that resolve to the same t0_manual_tick are the same engagement
    (overlapping 300-tick search windows). analyze_demo() keeps only the first.
    """

    PLAYER_SID = 76561198386265483
    ENEMY_SID  = 76561198315710555

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="dedup_test",
            )
        # a.parser is the Mock instance created during __init__
        a.parser.parse_ticks.return_value = [
            {"steamid": self.PLAYER_SID, "tick": 1000,
             "X": 0.0, "Y": 0.0, "Z": 0.0, "pitch": 0.0, "yaw": 0.0, "duck_amount": 0.0}
        ]
        a.parser.parse_event.return_value = pd.DataFrame()
        return a

    def _result(self, t0: int, timestamp: str, description: str = "") -> dict:
        return {
            "match_id": "dedup_test",
            "moment_timestamp": timestamp,
            "description": description,
            "t0_source": "manual",
            "t0_manual_tick": t0,
            "t1_aim_start_tick": float("nan"),
            "t2_first_hit_tick": t0 + 50,
            "rt_visible_to_aim_ms": float("nan"),
            "rt_aim_to_hit_ms": float("nan"),
            "rt_visible_to_hit_ms": 781.25,
            "target_enemy_id": self.ENEMY_SID,
            "player_velocity_at_t0_ups": 0.0,
            "enemy_velocity_at_t0_ups": 0.0,
            "engagement_type": "hold",
        }

    def test_duplicate_t0_keeps_only_first(self, analyzer):
        """Two moments resolving to the same T0 tick → only first result kept."""
        shared_t0 = 1000
        analyzer.analysis_moments = [
            AnalysisMoment(timestamp="0:15", manual_t0_tick_enemy_first_visible=shared_t0,
                           description="first"),
            AnalysisMoment(timestamp="0:20", manual_t0_tick_enemy_first_visible=shared_t0,
                           description="duplicate"),
        ]
        side_effects = [
            self._result(shared_t0, "0:15", "first"),
            self._result(shared_t0, "0:20", "duplicate"),
        ]
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            with patch.object(analyzer, "analyze_engagement_episode", side_effect=side_effects):
                df, _ = analyzer.analyze_demo(bulk_mode=False)

        assert len(df) == 1
        assert df.iloc[0]["moment_timestamp"] == "0:15"
        assert df.iloc[0]["description"] == "first"

    def test_distinct_t0_keeps_all(self, analyzer):
        """Two moments with different T0 ticks → both results kept."""
        analyzer.analysis_moments = [
            AnalysisMoment(timestamp="0:15", manual_t0_tick_enemy_first_visible=1000),
            AnalysisMoment(timestamp="0:30", manual_t0_tick_enemy_first_visible=2000),
        ]
        side_effects = [
            self._result(1000, "0:15"),
            self._result(2000, "0:30"),
        ]
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            with patch.object(analyzer, "analyze_engagement_episode", side_effect=side_effects):
                df, _ = analyzer.analyze_demo(bulk_mode=False)

        assert len(df) == 2

    def test_three_moments_two_share_t0(self, analyzer):
        """Three moments: first two share T0, third is distinct → 2 results kept."""
        shared_t0 = 1000
        unique_t0 = 5000
        analyzer.analysis_moments = [
            AnalysisMoment(timestamp="0:15", manual_t0_tick_enemy_first_visible=shared_t0),
            AnalysisMoment(timestamp="0:20", manual_t0_tick_enemy_first_visible=shared_t0),
            AnalysisMoment(timestamp="1:18", manual_t0_tick_enemy_first_visible=unique_t0),
        ]
        side_effects = [
            self._result(shared_t0, "0:15"),
            self._result(shared_t0, "0:20"),
            self._result(unique_t0, "1:18"),
        ]
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            with patch.object(analyzer, "analyze_engagement_episode", side_effect=side_effects):
                df, _ = analyzer.analyze_demo(bulk_mode=False)

        assert len(df) == 2
        assert set(df["moment_timestamp"].tolist()) == {"0:15", "1:18"}


class TestAnalyzeDemoOrchestration:
    """Tests for analyze_demo() parsing, fallbacks, DIAG branches, and bulk-mode."""

    PLAYER_SID = 76561198386265483
    ENEMY_SID  = 76561198315710555

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="orch_test",
            )
        a.parser.parse_ticks.return_value = [
            {"steamid": self.PLAYER_SID, "tick": 1000,
             "X": 0.0, "Y": 0.0, "Z": 0.0, "pitch": 0.0, "yaw": 0.0}
        ]
        # Schema-correct empty DataFrame (matches demoparser2 real output shape)
        a.parser.parse_event.return_value = pd.DataFrame(
            columns=["tick", "attacker_steamid", "user_steamid"]
        )
        a.analysis_moments = []
        return a

    def test_parse_ticks_exception_falls_back_to_required_props(self, analyzer):
        """parse_ticks raises on first call (all props) → retries with required-only → returns DataFrame."""
        required_row = [
            {"steamid": self.PLAYER_SID, "tick": 1000,
             "X": 0.0, "Y": 0.0, "Z": 0.0, "pitch": 0.0, "yaw": 0.0}
        ]
        analyzer.parser.parse_ticks.side_effect = [
            Exception("Optional props unavailable"),
            required_row,
        ]
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=False)
        assert isinstance(result, pd.DataFrame)

    def test_weapon_fire_event_exception_gives_empty_fire_df(self, analyzer):
        """parse_event raises for weapon_fire → graceful fallback to empty fire_df, no crash."""
        def parse_event_side(event, **kwargs):
            if event == "weapon_fire":
                raise Exception("Parse error")
            return pd.DataFrame()
        analyzer.parser.parse_event.side_effect = parse_event_side
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=False)
        assert isinstance(result, pd.DataFrame)

    def test_player_hurt_event_exception_gives_empty_hurt_df(self, analyzer):
        """parse_event raises for player_hurt → graceful fallback to empty hurt_df, no crash."""
        def parse_event_side(event, **kwargs):
            if event == "player_hurt":
                raise Exception("Parse error")
            return pd.DataFrame()
        analyzer.parser.parse_event.side_effect = parse_event_side
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=False)
        assert isinstance(result, pd.DataFrame)

    def test_player_found_in_hurt_events_logs_tick_range(self, analyzer):
        """Player is attacker in hurt events → DIAG tick-range logging branch reached, no crash."""
        hurt_df = pd.DataFrame({
            "attacker_steamid": [str(self.PLAYER_SID)],
            "user_steamid":     [str(self.ENEMY_SID)],
            "tick":             [1000],
        })
        def parse_event_side(event, **kwargs):
            if event == "player_hurt":
                return hurt_df
            return pd.DataFrame()
        analyzer.parser.parse_event.side_effect = parse_event_side
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=False)
        assert isinstance(result, pd.DataFrame)

    def test_player_not_in_hurt_events_logs_warning(self, analyzer):
        """Player is not attacker in any hurt event → DIAG warning branch reached, no crash."""
        hurt_df = pd.DataFrame({
            "attacker_steamid": ["99999"],
            "user_steamid":     [str(self.PLAYER_SID)],
            "tick":             [1000],
        })
        def parse_event_side(event, **kwargs):
            if event == "player_hurt":
                return hurt_df
            return pd.DataFrame()
        analyzer.parser.parse_event.side_effect = parse_event_side
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=False)
        assert isinstance(result, pd.DataFrame)

    def test_bulk_mode_no_hits_returns_empty_dataframe(self, analyzer):
        """bulk_mode=True, no player hits → auto_build_moments returns 0 → early empty return."""
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            result, _ = analyzer.analyze_demo(bulk_mode=True)
        assert isinstance(result, pd.DataFrame)
        assert result.empty

    def test_bulk_mode_with_hits_generates_moments_and_returns_results(self, analyzer):
        """bulk_mode=True, player hits enemy → moment built and analyze_engagement_episode called."""
        hurt_df = pd.DataFrame({
            "attacker_steamid": [str(self.PLAYER_SID)],
            "user_steamid":     [str(self.ENEMY_SID)],
            "tick":             [1000],
        })
        # Phase 9.1 SC2: production now batches events via parse_events([...]).
        analyzer.parser.parse_events.side_effect = lambda events, *a, **kw: [
            ("player_hurt",  hurt_df),
            ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
            ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
            ("round_start",  pd.DataFrame(columns=["tick"])),
        ]
        episode_result = {
            "match_id": "orch_test", "moment_timestamp": "0:15",
            "description": "bulk_auto first_hit=1000", "t0_source": "BVH+AABB",
            "t0_manual_tick": 900, "t1_aim_start_tick": float("nan"),
            "t2_first_hit_tick": 1000, "rt_visible_to_aim_ms": float("nan"),
            "rt_aim_to_hit_ms": float("nan"), "rt_visible_to_hit_ms": 1562.5,
            "target_enemy_id": self.ENEMY_SID, "player_velocity_at_t0_ups": 0.0,
            "enemy_velocity_at_t0_ups": 0.0, "engagement_type": "hold",
        }
        with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
            with patch.object(analyzer, "analyze_engagement_episode", return_value=episode_result):
                result, _ = analyzer.analyze_demo(bulk_mode=True)
        assert len(result) == 1
        assert result.iloc[0]["t0_source"] == "BVH+AABB"

    def test_find_all_duel_attempts_returns_list(self):
        """find_all_duel_attempts() returns a list (empty when no T0Detector)."""
        analyzer = DDMAnalyzer.__new__(DDMAnalyzer)
        analyzer.player_steamid = 1
        analyzer.match_id = "test"
        analyzer.map_name = "de_test"
        analyzer.tickrate = 64
        analyzer.t0_detector = None  # no BVH available
        import logging
        analyzer.logger = logging.getLogger("test")
        analyzer.player_velocity_threshold = 50.0

        result = analyzer.find_all_duel_attempts(
            player_fire_df=pd.DataFrame(columns=["tick", "weapon"]),
            all_ticks_df=pd.DataFrame(),
            all_hurt_df=pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"]),
            all_death_df=pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"]),
        )
        assert isinstance(result, list)
        assert result == []


class TestComputeRoundPhase:
    """Tests for _compute_round_phase — round time and phase classification."""

    PLAYER_SID = 76561198386265483

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="test_phase",
            )
        return a

    def test_no_round_start_ticks_returns_none(self, analyzer):
        """No round_start_ticks → (None, None, None)."""
        rt, rp, rn = analyzer._compute_round_phase(5000, None, "[test]")
        assert rt is None
        assert rp is None
        assert rn is None

    def test_empty_round_start_ticks_returns_none(self, analyzer):
        """Empty list → (None, None, None)."""
        rt, rp, rn = analyzer._compute_round_phase(5000, [], "[test]")
        assert rt is None
        assert rp is None
        assert rn is None

    def test_early_phase(self, analyzer):
        """T0 within 40s of round start → 'early'."""
        # 1000 ticks after round start = 1000/64 * 1000/1000 = 15.625s
        rt, rp, _ = analyzer._compute_round_phase(2000, [1000], "[test]")
        assert rp == "early"
        assert rt == round((2000 - 1000) * (1000 / 64) / 1000, 2)

    def test_mid_phase(self, analyzer):
        """T0 between 40s–70s of round start → 'mid'."""
        # Need 40s * 64 = 2560 ticks after round start
        round_start = 1000
        t0 = round_start + 3200  # 50s at 64Hz
        _, rp, _ = analyzer._compute_round_phase(t0, [round_start], "[test]")
        assert rp == "mid"

    def test_late_phase(self, analyzer):
        """T0 after 70s of round start → 'late'."""
        round_start = 1000
        t0 = round_start + 5000  # 78.1s at 64Hz
        _, rp, _ = analyzer._compute_round_phase(t0, [round_start], "[test]")
        assert rp == "late"

    def test_t0_before_first_round_start(self, analyzer):
        """T0 before any round_start → (None, 'unknown', None)."""
        rt, rp, rn = analyzer._compute_round_phase(500, [1000, 5000], "[test]")
        assert rt is None
        assert rp == "unknown"
        assert rn is None

    def test_picks_correct_round(self, analyzer):
        """With multiple rounds, picks the most recent round_start before T0."""
        rt, rp, _ = analyzer._compute_round_phase(6000, [1000, 5000, 10000], "[test]")
        expected_s = round((6000 - 5000) * (1000 / 64) / 1000, 2)
        assert rt == expected_s
        assert rp == "early"  # ~15.6s into round

    # ── Phase v2 Wave 0 — round_number emission (D-01) ──────────────────────

    def test_compute_round_phase_returns_round_number(self, analyzer):
        """v2-00-05 — _compute_round_phase returns 3-tuple with 1-indexed round_number.

        bisect_right of t0=1500 in [100, 1000, 2500] → idx=2 (insertion point),
        idx-1=1 → round_number = (idx-1)+1 = 2.
        """
        result = analyzer._compute_round_phase(1500, [100, 1000, 2500], "[test]")
        assert len(result) == 3, (
            f"Expected 3-tuple (round_time_s, round_phase, round_number), got len={len(result)}"
        )
        rt, rp, rn = result
        assert rn == 2, f"Expected round_number=2 for t0=1500 in [100,1000,2500], got {rn}"

    def test_compute_round_phase_warmup_returns_none_round_number(self, analyzer):
        """v2-00-06 — warmup branch (t0 before first round_start) → (None, 'unknown', None)."""
        result = analyzer._compute_round_phase(50, [100, 1000], "[test]")
        assert len(result) == 3
        rt, rp, rn = result
        assert rt is None
        assert rp == "unknown", "Warmup must surface 'unknown' phase per ddm_analyzer.py:608-612"
        assert rn is None

    def test_compute_round_phase_no_round_start_ticks_triple(self, analyzer):
        """v2-00-06b — empty/None round_start_ticks → (None, None, None)."""
        for empty in (None, []):
            result = analyzer._compute_round_phase(5000, empty, "[test]")
            assert len(result) == 3
            assert result == (None, None, None), f"For input {empty!r} got {result}"

    def test_compute_round_phase_first_round_round_number_is_one(self, analyzer):
        """v2-00-05b — t0 just after first round_start → round_number=1 (1-indexed)."""
        rt, rp, rn = analyzer._compute_round_phase(2000, [1000], "[test]")
        assert rn == 1


class TestAnalyzeEpisodeRoundNumberEmission:
    """v2-00-07 — analyze_engagement_episode result dict gains 'round_number' key (D-01)."""

    PLAYER_SID = 76561198386265483
    ENEMY_ID = 999

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            return DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="test_round_number",
                debug_prints=False,
            )

    def test_result_dict_includes_round_number(self, analyzer):
        """Mock heavy methods; assert returned dict has 'round_number' key with computed value."""
        moment = AnalysisMoment(
            timestamp="00:00",
            manual_t0_tick_enemy_first_visible=None,
            description="round_number test",
            target_enemy_steamid_if_known=None,
            use_auto_t0=True,
            auto_t0_search_start_tick=1000,
        )
        with patch.object(analyzer, "_resolve_t0", return_value=(2500, "auto")), \
             patch.object(analyzer, "_find_t2", return_value=(2550, self.ENEMY_ID, "weapon_ak47")), \
             patch.object(analyzer, "_compute_crosshair_angle_at_t0", return_value=3.0), \
             patch.object(analyzer, "is_1v1_duel", return_value=(True, "")), \
             patch.object(analyzer, "_teammate_hurt_target", return_value=False), \
             patch.object(analyzer, "_compute_velocity", return_value=0.0), \
             patch.object(analyzer, "_detect_t1", return_value=(2520, "sustained_aim")), \
             patch.object(analyzer, "_classify_engagement", return_value="hold"):
            ticks_df = pd.DataFrame({"tick": [2500, 2520, 2550]})
            fire_df = pd.DataFrame()
            hurt_df = pd.DataFrame({
                "attacker_steamid": [str(self.PLAYER_SID)],
                "user_steamid": [str(self.ENEMY_ID)],
                "tick": [2550],
            })
            # 2500 sits in round #2 of [100, 1000, 5000]: bisect_right→2, -1=1 → rn=2
            round_start_ticks = [100, 1000, 5000]
            result = analyzer.analyze_engagement_episode(
                moment, ticks_df, fire_df, hurt_df, round_start_ticks
            )
        assert result is not None
        assert "round_number" in result, "result dict missing 'round_number' key (D-01)"
        assert result["round_number"] == 2


class TestComputeVelocity:
    """Tests for _compute_velocity — XY speed at a given tick."""

    PLAYER_SID = 76561198386265483

    @pytest.fixture
    def analyzer(self):
        with patch("ddm_analyzer.DemoParser"):
            a = DDMAnalyzer(
                demo_path="fake.dem",
                player_steamid=self.PLAYER_SID,
                match_id="test_vel",
            )
        return a

    def test_normal_velocity(self, analyzer):
        """Standard case: two consecutive ticks with position delta."""
        ticks_df = pd.DataFrame({
            "steamid": [self.PLAYER_SID, self.PLAYER_SID],
            "tick": [100, 101],
            "X": [0.0, 1.0],
            "Y": [0.0, 0.0],
            "Z": [0.0, 0.0],
        })
        vel = analyzer._compute_velocity(self.PLAYER_SID, 100, ticks_df, "player")
        assert vel == pytest.approx(1.0 * 64)  # 1u per tick * 64 tickrate

    def test_no_tick_at_t0_returns_nan(self, analyzer):
        """No data at T0 tick → np.nan."""
        ticks_df = pd.DataFrame({
            "steamid": [self.PLAYER_SID],
            "tick": [200],
            "X": [0.0],
            "Y": [0.0],
            "Z": [0.0],
        })
        vel = analyzer._compute_velocity(self.PLAYER_SID, 100, ticks_df, "player")
        assert math.isnan(vel)

    def test_no_tick_after_t0_returns_nan(self, analyzer):
        """Only one tick at T0, none after → np.nan."""
        ticks_df = pd.DataFrame({
            "steamid": [self.PLAYER_SID],
            "tick": [100],
            "X": [0.0],
            "Y": [0.0],
            "Z": [0.0],
        })
        vel = analyzer._compute_velocity(self.PLAYER_SID, 100, ticks_df, "player")
        assert math.isnan(vel)


def test_analyze_demo_parses_player_death(monkeypatch):
    """analyze_demo must parse player_death events and pass them downstream."""
    import pandas as pd
    from unittest.mock import MagicMock
    from ddm_analyzer import DDMAnalyzer

    analyzer = DDMAnalyzer.__new__(DDMAnalyzer)
    analyzer.demo_path = "/fake.dem"
    analyzer.player_steamid = 1
    analyzer.match_id = "m1"
    analyzer.map_name = "de_test"
    analyzer.tickrate = 64
    analyzer.debug_prints = False
    analyzer.analysis_moments = []
    analyzer.enemy_velocity_threshold = 120
    analyzer.player_velocity_threshold = 50
    analyzer.t0_detector = None
    analyzer.logger = MagicMock()

    parser = MagicMock()
    parser.parse_ticks.return_value = pd.DataFrame(columns=["X", "Y", "Z", "pitch", "yaw", "steamid", "name"])

    # Phase 9.1 SC2: production batches events via parse_events([...]).
    death_df = pd.DataFrame([{"tick": 500, "attacker_steamid": "1", "user_steamid": "99"}])
    parser.parse_events.side_effect = lambda events, *a, **kw: [
        ("player_hurt",  pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("player_death", death_df),
        ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
        ("round_start",  pd.DataFrame(columns=["tick"])),
    ]
    analyzer.parser = parser

    captured = {}

    def fake_find_all(**kw):
        captured["death_df"] = kw.get("all_death_df")
        return []
    analyzer.find_all_duel_attempts = fake_find_all

    df, attempts = analyzer.analyze_demo(bulk_mode=False, attempts_mode=True)
    assert "death_df" in captured
    assert not captured["death_df"].empty
    assert int(captured["death_df"].iloc[0]["tick"]) == 500


# ─────────────────────────────────────────────────────────────────────────────
# Phase 9.1 Wave 0 — RED tests for SC2 (parse_events batch),
# SC3 (selective parse_ticks + empty-anchor guard + flag-off path),
# and SC4 (analyze_engagement_episode receives ticks_by_sid kwarg).
#
# These tests are intentionally failing on current code:
#   - SC2: production currently calls parse_event(...) per event, not parse_events([...]).
#   - SC3: config.PARSE_TICKS_SELECTIVE does not exist yet; production never passes
#     ticks= kwarg; empty-anchor guard isn't implemented.
#   - SC4: analyze_engagement_episode is not yet receiving a ticks_by_sid kwarg.
# Plans 09.1-02, 09.1-03, 09.1-04 turn them GREEN.
# ─────────────────────────────────────────────────────────────────────────────


def _new_perf_analyzer(parser_mock):
    """Construct a DDMAnalyzer skipping __init__ — same pattern as
    test_analyze_demo_parses_player_death above. Wires the supplied parser_mock
    and minimal attribute surface required by analyze_demo()."""
    from unittest.mock import MagicMock
    from ddm_analyzer import DDMAnalyzer

    analyzer = DDMAnalyzer.__new__(DDMAnalyzer)
    analyzer.demo_path = "/fake.dem"
    analyzer.player_steamid = 76561198386265483
    analyzer.match_id = "perf_test"
    analyzer.map_name = "de_test"
    analyzer.tickrate = 64
    analyzer.debug_prints = False
    analyzer.analysis_moments = []
    analyzer.enemy_velocity_threshold = 120
    analyzer.player_velocity_threshold = 50
    analyzer.t0_detector = None
    analyzer.logger = MagicMock()
    analyzer.parser = parser_mock
    return analyzer


def _empty_tick_props_df():
    return pd.DataFrame(columns=["X", "Y", "Z", "pitch", "yaw", "steamid", "name"])


def test_analyze_demo_uses_parse_events_batch():
    """SC2: analyze_demo calls parse_events ONCE with the 4-event list.

    Spies parse_events to capture arguments; pytest.fail's if legacy
    parse_event(name) is invoked. Currently FAILS: production code still
    calls parse_event() per event.
    """
    from unittest.mock import MagicMock
    parser = MagicMock()
    parser.parse_ticks.return_value = _empty_tick_props_df()
    parser.parse_header.return_value = {"map_name": "de_test"}

    calls = []

    def _events_spy(events, *args, **kwargs):
        calls.append(list(events))
        return [
            ("player_hurt",  pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
            ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
            ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
            ("round_start",  pd.DataFrame(columns=["tick"])),
        ]
    parser.parse_events.side_effect = _events_spy
    parser.parse_event.side_effect = lambda *a, **kw: pytest.fail(
        "parse_event(singular) must NOT be called after #2 — "
        "all event extraction goes through parse_events([...])."
    )

    analyzer = _new_perf_analyzer(parser)

    with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
        analyzer.analyze_demo(bulk_mode=False)

    assert len(calls) == 1, (
        f"parse_events should be called exactly once, got {len(calls)} calls. "
        "SC2: parse_events batching not yet implemented."
    )
    assert set(calls[0]) >= {"player_hurt", "player_death", "weapon_fire", "round_start"}, (
        f"parse_events first call missing required events: {calls[0]}"
    )


def test_parse_ticks_selective_uses_ticks_kwarg(monkeypatch):
    """SC3: when PARSE_TICKS_SELECTIVE=True and hurt anchors exist,
    parse_ticks is called with a ticks= kwarg covering anchor ± window."""
    monkeypatch.setattr("config.PARSE_TICKS_SELECTIVE", True, raising=False)

    from unittest.mock import MagicMock
    parser = MagicMock()
    parser.parse_header.return_value = {"map_name": "de_test"}

    captured = {}

    def _ticks_spy(props, *args, **kwargs):
        captured.setdefault("calls", []).append(kwargs)
        return _empty_tick_props_df()
    parser.parse_ticks.side_effect = _ticks_spy

    # Seed a single player_hurt anchor at tick=1000 attributed to the player.
    hurt_df = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": ["76561198386265483"],
        "user_steamid": ["76561198315710555"],
    })
    parser.parse_events.side_effect = lambda events, *a, **kw: [
        ("player_hurt",  hurt_df),
        ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
        ("round_start",  pd.DataFrame(columns=["tick"])),
    ]

    analyzer = _new_perf_analyzer(parser)

    with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
        analyzer.analyze_demo(bulk_mode=False)

    ticks_kwargs = [c for c in captured.get("calls", []) if "ticks" in c]
    assert ticks_kwargs, (
        "parse_ticks was never called with a ticks= kwarg. "
        "SC3: selective parse_ticks not yet implemented."
    )
    union = list(ticks_kwargs[0]["ticks"])
    assert 1000 in union, "anchor tick must be inside the selective window"


def test_parse_ticks_selective_disabled_full_parse(monkeypatch):
    """SC3 D-02 fallback: PARSE_TICKS_SELECTIVE=False → no ticks= kwarg.

    Asserts the feature flag actually exists in config so the fallback
    branch is wired (currently RED — flag not yet defined).
    """
    import config
    assert hasattr(config, "PARSE_TICKS_SELECTIVE"), (
        "config.PARSE_TICKS_SELECTIVE flag missing — D-02 fallback not yet "
        "wired (will be added in plan 09.1-03)."
    )
    monkeypatch.setattr("config.PARSE_TICKS_SELECTIVE", False, raising=True)

    from unittest.mock import MagicMock
    parser = MagicMock()
    parser.parse_header.return_value = {"map_name": "de_test"}

    captured = {}

    def _ticks_spy(props, *args, **kwargs):
        captured.setdefault("calls", []).append(kwargs)
        return _empty_tick_props_df()
    parser.parse_ticks.side_effect = _ticks_spy

    hurt_df = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": ["76561198386265483"],
        "user_steamid": ["76561198315710555"],
    })
    parser.parse_events.side_effect = lambda events, *a, **kw: [
        ("player_hurt",  hurt_df),
        ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
        ("round_start",  pd.DataFrame(columns=["tick"])),
    ]

    analyzer = _new_perf_analyzer(parser)

    with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
        analyzer.analyze_demo(bulk_mode=False)

    for kw in captured.get("calls", []):
        assert "ticks" not in kw, (
            f"PARSE_TICKS_SELECTIVE=False but parse_ticks received ticks= kwarg: {kw}. "
            "SC3 fallback not yet implemented."
        )


def test_parse_ticks_empty_anchors_falls_back_full(monkeypatch):
    """SC3 Pitfall #1: empty hurt list does NOT pass ticks=[] (silent full parse).

    Empty union must take the explicit fallback branch — never call
    parse_ticks(props, ticks=[]). Also asserts the flag exists so this
    test stays RED until plan 09.1-03 wires the guard.
    """
    import config
    assert hasattr(config, "PARSE_TICKS_SELECTIVE"), (
        "config.PARSE_TICKS_SELECTIVE flag missing — Pitfall #1 guard not yet "
        "wired (will be added in plan 09.1-03)."
    )
    monkeypatch.setattr("config.PARSE_TICKS_SELECTIVE", True, raising=True)

    from unittest.mock import MagicMock
    parser = MagicMock()
    parser.parse_header.return_value = {"map_name": "de_test"}

    captured = {}

    def _ticks_spy(props, *args, **kwargs):
        captured.setdefault("calls", []).append(kwargs)
        return _empty_tick_props_df()
    parser.parse_ticks.side_effect = _ticks_spy

    # Empty hurt → empty anchor union.
    parser.parse_events.side_effect = lambda events, *a, **kw: [
        ("player_hurt",  pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
        ("round_start",  pd.DataFrame(columns=["tick"])),
    ]

    analyzer = _new_perf_analyzer(parser)

    with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
        analyzer.analyze_demo(bulk_mode=False)

    for kw in captured.get("calls", []):
        assert "ticks" not in kw or len(list(kw["ticks"])) > 0, (
            "Empty anchors must NOT pass ticks=[] (silent full-parse trap). "
            "SC3 Pitfall #1 guard not yet implemented."
        )


def test_analyze_engagement_passes_ticks_by_sid():
    """SC4: analyze_engagement_episode receives ticks_by_sid kwarg from analyze_demo.

    Monkeypatches the method, captures kwargs, asserts a non-None
    ticks_by_sid dict was forwarded.
    """
    from unittest.mock import MagicMock
    parser = MagicMock()
    parser.parse_header.return_value = {"map_name": "de_test"}
    parser.parse_ticks.return_value = pd.DataFrame({
        "steamid": [76561198386265483, 76561198315710555],
        "tick": [1000, 1000],
        "X": [0.0, 100.0], "Y": [0.0, 0.0], "Z": [0.0, 0.0],
        "pitch": [0.0, 0.0], "yaw": [0.0, 0.0],
    })
    hurt_df = pd.DataFrame({
        "tick": [1000],
        "attacker_steamid": ["76561198386265483"],
        "user_steamid": ["76561198315710555"],
    })
    # Support both legacy and batched event APIs so the test can fail purely
    # on the missing ticks_by_sid forwarding rather than an upstream parse path.
    parser.parse_event.side_effect = lambda name, **kw: (
        hurt_df if name == "player_hurt"
        else pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
    )
    parser.parse_events.side_effect = lambda events, *a, **kw: [
        ("player_hurt",  hurt_df),
        ("player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])),
        ("weapon_fire",  pd.DataFrame(columns=["tick", "user_steamid"])),
        ("round_start",  pd.DataFrame(columns=["tick"])),
    ]

    analyzer = _new_perf_analyzer(parser)

    captured = {}

    def _episode_spy(*args, **kwargs):
        captured["kwargs"] = kwargs
        return None  # filtered out by analyze_demo

    analyzer.analyze_engagement_episode = _episode_spy

    with patch("t0_detector.T0Detector.parse_smoke_events", return_value=pd.DataFrame()):
        analyzer.analyze_demo(bulk_mode=True)

    assert "kwargs" in captured, (
        "analyze_engagement_episode was never invoked — test setup issue."
    )
    assert "ticks_by_sid" in captured["kwargs"], (
        "analyze_engagement_episode did not receive a ticks_by_sid kwarg. "
        "SC4: per-sid cache forwarding not yet implemented."
    )
    assert captured["kwargs"]["ticks_by_sid"] is not None, (
        "ticks_by_sid kwarg must be a populated dict, not None."
    )
