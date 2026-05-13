"""
Tests for config module: constants, data models, and logging factory.
"""

import logging
import tempfile
import os
import pytest
from dataclasses import dataclass

from config import (
    AnalysisMoment,
    get_logger,
    VELOCITY_PEEK_THRESHOLD_UPS,
    ENEMY_VELOCITY_HOLD_THRESHOLD_UPS,
    KNIFE_WEAPON_NAMES,
    AWP_WEAPON_NAMES,
    T0_MIN_OFFSET_TICKS,
)


class TestAnalysisMomentDataclass:
    """Tests for AnalysisMoment data model."""

    def test_analysis_moment_with_manual_t0(self):
        """AnalysisMoment with manual T0 tick."""
        moment = AnalysisMoment(
            timestamp="2:30",
            manual_t0_tick_enemy_first_visible=1000,
            description="test moment",
        )
        assert moment.timestamp == "2:30"
        assert moment.manual_t0_tick_enemy_first_visible == 1000
        assert moment.description == "test moment"
        assert moment.use_auto_t0 is False
        assert moment.analysis_window_seconds_after_t0 == 5

    def test_analysis_moment_with_auto_t0(self):
        """AnalysisMoment with automatic T0 detection."""
        moment = AnalysisMoment(
            timestamp="3:00",
            manual_t0_tick_enemy_first_visible=None,
            use_auto_t0=True,
            auto_t0_search_start_tick=800,
        )
        assert moment.timestamp == "3:00"
        assert moment.manual_t0_tick_enemy_first_visible is None
        assert moment.use_auto_t0 is True
        assert moment.auto_t0_search_start_tick == 800

    def test_analysis_moment_defaults(self):
        """AnalysisMoment respects default values."""
        moment = AnalysisMoment(
            timestamp="2:30",
            manual_t0_tick_enemy_first_visible=1000,
        )
        assert moment.description == ""
        assert moment.analysis_window_seconds_after_t0 == 5
        assert moment.target_enemy_steamid_if_known is None
        assert moment.use_auto_t0 is False
        assert moment.auto_t0_search_start_tick is None

    def test_analysis_moment_with_custom_window(self):
        """AnalysisMoment supports custom analysis window."""
        moment = AnalysisMoment(
            timestamp="2:30",
            manual_t0_tick_enemy_first_visible=1000,
            analysis_window_seconds_after_t0=8,
        )
        assert moment.analysis_window_seconds_after_t0 == 8


class TestConfigConstants:
    """Tests for configuration constants — validates contracts & relationships."""

    # ─ Velocity thresholds ─────────────────────────────────────────────────────

    def test_velocity_peek_threshold_positive(self):
        """Peek velocity threshold must be positive (no negative speeds)."""
        assert VELOCITY_PEEK_THRESHOLD_UPS > 0

    def test_enemy_velocity_hold_threshold_positive(self):
        """Enemy hold velocity threshold must be positive."""
        assert ENEMY_VELOCITY_HOLD_THRESHOLD_UPS > 0

    # ─ T0 offset threshold ─────────────────────────────────────────────────────

    def test_t0_min_offset_ticks_positive(self):
        """T0 min offset must be positive (need lookback window)."""
        assert T0_MIN_OFFSET_TICKS > 0

    def test_t0_min_offset_in_reaction_range(self):
        """T0 offset should be long enough to contain a real reaction (>100ms)
        but short enough to stay in the same engagement (<800ms).

        At 64 Hz: 1 tick = 15.625ms
        """
        ms_per_tick = 1000 / 64
        offset_ms = T0_MIN_OFFSET_TICKS * ms_per_tick
        assert 100 < offset_ms < 800

    # ─ Weapon exclusion sets ───────────────────────────────────────────────────
    # These constants define what gets EXCLUDED from rifle-duel analysis.
    # The critical contract: rifles must never appear in exclusion sets.

    def test_rifles_are_not_excluded(self):
        """Primary rifles must not appear in exclusion sets.

        This is the most important test: if a rifle ends up in an exclusion set
        by mistake, entire engagements will be silently dropped from analysis.
        """
        excluded = KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES
        rifles = ["ak47", "m4a4", "m4a1_silencer", "famas", "galil",
                  "sg553", "aug", "weapon_ak47", "weapon_m4a4"]
        for rifle in rifles:
            assert rifle not in excluded, (
                f"Rifle '{rifle}' is in exclusion set — "
                f"duel analysis will silently discard these engagements"
            )

    def test_exclusion_sets_do_not_overlap(self):
        """Knife and AWP sets must be mutually exclusive to avoid counting twice."""
        overlap = KNIFE_WEAPON_NAMES & AWP_WEAPON_NAMES
        assert len(overlap) == 0, f"Overlapping exclusions: {overlap}"

    def test_exclusion_sets_are_immutable(self):
        """Exclusion sets must be frozensets so they can't be accidentally mutated."""
        assert isinstance(KNIFE_WEAPON_NAMES, frozenset)
        assert isinstance(AWP_WEAPON_NAMES, frozenset)

    def test_exclusion_set_names_lowercase_for_matching(self):
        """Names must be lowercase — demoparser2 reports weapon names in lowercase.

        If any name is uppercase, the .isin() filter in auto_build_moments()
        will silently fail to exclude it.
        """
        all_excluded = KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES
        for weapon in all_excluded:
            assert weapon == weapon.lower(), (
                f"'{weapon}' is not lowercase — exclusion filter will miss it"
            )


class TestGetLoggerFactory:
    """Tests for logging factory function."""

    def test_get_logger_returns_logger(self):
        """get_logger() should return a logging.Logger instance."""
        logger = get_logger("test_match")
        assert isinstance(logger, logging.Logger)

    def test_get_logger_with_different_match_ids(self):
        """Different match_ids should get different logger names."""
        logger1 = get_logger("match_1")
        logger2 = get_logger("match_2")
        assert logger1.name == "DDM.match_1"
        assert logger2.name == "DDM.match_2"

    def test_get_logger_has_file_handler(self):
        """Logger should have a FileHandler for logging to file."""
        logger = get_logger("test_file_logging")
        assert len(logger.handlers) > 0
        has_file_handler = any(
            isinstance(h, logging.FileHandler) for h in logger.handlers
        )
        assert has_file_handler

    def test_get_logger_debug_mode(self):
        """Logger should respect debug flag."""
        # Use unique names to avoid sharing cached logger state between tests
        logger_info = get_logger("test_logger_info_mode", debug=False)
        assert logger_info.level in (logging.INFO, logging.NOTSET)

        logger_debug = get_logger("test_logger_debug_mode", debug=True)
        assert logger_debug.level == logging.DEBUG

    def test_get_logger_idempotent(self):
        """Getting same logger twice should return same instance."""
        logger1 = get_logger("test_logger_idempotent_check")
        logger2 = get_logger("test_logger_idempotent_check")
        assert logger1 is logger2

    @pytest.mark.integration
    def test_get_logger_writes_to_file(self):
        """Logger should write to ddm_analysis.log (requires cwd = project root)."""
        logger = get_logger("test_logger_file_write")
        logger.info("Test log message integration")

        assert os.path.exists("ddm_analysis.log")
        with open("ddm_analysis.log", "r") as f:
            assert "Test log message integration" in f.read()


def test_attempt_window_constants_defined():
    from config import (
        _ATTEMPT_WINDOW_BEFORE_TICKS,
        _ATTEMPT_WINDOW_AFTER_TICKS,
        _KILL_CONFIRM_WINDOW_TICKS,
        _BULLETS_FOR_HIT_RATE,
    )
    assert _ATTEMPT_WINDOW_BEFORE_TICKS > 0
    assert _ATTEMPT_WINDOW_AFTER_TICKS > 0
    assert _KILL_CONFIRM_WINDOW_TICKS >= 64
    assert _BULLETS_FOR_HIT_RATE >= 1


# ─────────────────────────────────────────────────────────────────────────────
# Phase v2 — LLM narrative coaching layer constants
# ─────────────────────────────────────────────────────────────────────────────


class TestPhaseV2NarrativeConstants:
    """Tests for v2 LLM narrative + validator constants (REQ-3, REQ-5, D-06)."""

    def test_narrative_common_nouns_whitelist_present(self):
        """NARRATIVE_COMMON_NOUNS_WHITELIST must be a frozenset with locked
        D-06 vocabulary. The validator allows these tokens without attribution.
        """
        from config import NARRATIVE_COMMON_NOUNS_WHITELIST

        assert isinstance(NARRATIVE_COMMON_NOUNS_WHITELIST, frozenset)
        # Locked D-06 vocabulary — every token below MUST be present.
        required = {
            "peek", "hold", "aim", "crosshair", "pre-aim",
            "deathmatch", "DM", "VOD",
        }
        assert required <= NARRATIVE_COMMON_NOUNS_WHITELIST, (
            f"Missing tokens: {required - NARRATIVE_COMMON_NOUNS_WHITELIST}"
        )

    def test_narrative_common_nouns_whitelist_immutable(self):
        """frozenset prevents accidental mutation downstream."""
        from config import NARRATIVE_COMMON_NOUNS_WHITELIST

        with pytest.raises(AttributeError):
            NARRATIVE_COMMON_NOUNS_WHITELIST.add("foo")  # type: ignore[attr-defined]

    def test_llm_provider_default_anthropic(self):
        """LLM_PROVIDER must default to 'anthropic' (REQ-3 L-2)."""
        from config import LLM_PROVIDER

        assert isinstance(LLM_PROVIDER, str)
        # Default — env override allowed but no env var set in test env.
        assert LLM_PROVIDER == "anthropic" or os.environ.get("LLM_PROVIDER")

    def test_llm_model_default_sonnet(self):
        """LLM_MODEL must default to claude-sonnet-4-6 (L-2 cost/quality balance)."""
        from config import LLM_MODEL

        assert isinstance(LLM_MODEL, str)
        # Default — env override allowed.
        assert LLM_MODEL == "claude-sonnet-4-6" or os.environ.get("LLM_MODEL")


class TestPlayerNamesD15Roster:
    """Plan v2-03 task 2 — PLAYER_NAMES MUST cover the D-15 eval roster.

    Per CONTEXT.md D-15 + B-1 + B-4 hard block: real nicknames only, no
    placeholder strings like `player_<last4>`. SteamIDs sourced from
    `reference_player_steam_ids.md` memory file (verified 2026-05-12 via
    profilerr.net for Spirit + FaZe).
    """

    def test_player_names_has_at_least_ten_entries(self):
        from config import PLAYER_NAMES

        assert len(PLAYER_NAMES) >= 10, (
            f"PLAYER_NAMES has {len(PLAYER_NAMES)} entries; D-15 roster needs ≥10"
        )

    def test_player_names_includes_donk_and_karrigan(self):
        """Preserve W1 baseline — donk + karrigan were the first two seeded."""
        from config import PLAYER_NAMES

        assert PLAYER_NAMES[76561198386265483] == "donk"
        assert PLAYER_NAMES[76561197989430253] == "karrigan"

    def test_player_names_includes_d15_top_tier(self):
        """D-15 top-3: donk, karrigan, frozen (memory: 76561198068422762)."""
        from config import PLAYER_NAMES

        assert 76561198386265483 in PLAYER_NAMES  # donk
        assert 76561197989430253 in PLAYER_NAMES  # karrigan
        assert 76561198081484775 in PLAYER_NAMES  # sh1ro
        assert 76561198068422762 in PLAYER_NAMES  # frozen

    def test_player_names_keys_are_int_not_str(self):
        """Guard against accidental string SteamIDs — DB queries pass int(sid)."""
        from config import PLAYER_NAMES

        assert all(isinstance(k, int) for k in PLAYER_NAMES.keys()), (
            "All PLAYER_NAMES keys must be int (SteamID64) — string keys "
            "silently break int(sid) lookup paths"
        )

    def test_player_names_has_no_placeholder_values(self):
        """B-1 + B-4 hard block: no `player_<last4>` placeholders allowed."""
        from config import PLAYER_NAMES

        for sid, name in PLAYER_NAMES.items():
            assert not name.startswith("player_"), (
                f"PLAYER_NAMES[{sid}] = {name!r} looks like a placeholder; "
                f"D-10 + D-15 require real nicknames only"
            )
            assert name.strip() == name and len(name) > 0, (
                f"PLAYER_NAMES[{sid}] = {name!r} is empty or has whitespace"
            )

    def test_player_names_values_are_str(self):
        from config import PLAYER_NAMES

        assert all(isinstance(v, str) for v in PLAYER_NAMES.values())

