"""
TDD tests for T0Detector smoke/flash parsing (Phase 3a).

Tests: parse_smoke_events() — extract smoke intervals from demoparser2 events
       parse_flash_intervals() — extract flash blindness windows
"""

from unittest.mock import Mock
import pandas as pd
from t0_detector import parse_smoke_events, parse_flash_intervals


class TestParseSmokeEvents:
    """Extract smoke detonation intervals from demoparser2 events."""

    def test_parse_smoke_no_events(self):
        """Parser returns no smoke events."""
        parser = Mock()
        parser.parse_event.return_value = pd.DataFrame()

        result = parse_smoke_events(parser)

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert list(result.columns) == ["X", "Y", "Z", "start_tick", "end_tick"]

    def test_parse_smoke_single_detonate_no_expiry(self):
        """Single smoke detonates, no expiry event (uses 18s fallback)."""
        parser = Mock()
        det_df = pd.DataFrame([
            {"tick": 100, "x": 500.0, "y": 600.0, "z": 0.0}
        ])
        parser.parse_event.side_effect = lambda event: (
            det_df if event == "smokegrenade_detonate" else pd.DataFrame()
        )

        result = parse_smoke_events(parser)

        assert len(result) == 1
        assert result.iloc[0]["start_tick"] == 100
        assert result.iloc[0]["end_tick"] == 100 + 18 * 64  # ~18s fallback
        assert result.iloc[0]["X"] == 500.0
        assert result.iloc[0]["Y"] == 600.0

    def test_parse_smoke_detonate_and_expiry(self):
        """Smoke detonates and expires (uses expiry event tick)."""
        parser = Mock()
        det_df = pd.DataFrame([
            {"tick": 100, "x": 500.0, "y": 600.0, "z": 0.0}
        ])
        exp_df = pd.DataFrame([
            {"tick": 150, "x": 505.0, "y": 605.0}  # Close position
        ])

        def mock_parse_event(event):
            if event == "smokegrenade_detonate":
                return det_df
            elif event == "smokegrenade_expired":
                return exp_df
            return pd.DataFrame()

        parser.parse_event.side_effect = mock_parse_event

        result = parse_smoke_events(parser)

        assert len(result) == 1
        assert result.iloc[0]["start_tick"] == 100
        assert result.iloc[0]["end_tick"] == 150  # From expiry

    def test_parse_smoke_multiple_detonates(self):
        """Multiple smokes detonating with no expiry — both use 18s fallback."""
        parser = Mock()
        det_df = pd.DataFrame([
            {"tick": 100, "x": 500.0, "y": 600.0, "z": 0.0},
            {"tick": 200, "x": 1000.0, "y": 1200.0, "z": 0.0},
        ])
        parser.parse_event.side_effect = lambda event: (
            det_df if event == "smokegrenade_detonate" else pd.DataFrame()
        )

        result = parse_smoke_events(parser)

        assert len(result) == 2
        assert result.iloc[0]["start_tick"] == 100
        assert result.iloc[0]["end_tick"] == 100 + 18 * 64
        assert result.iloc[1]["start_tick"] == 200
        assert result.iloc[1]["end_tick"] == 200 + 18 * 64

    def test_parse_smoke_handles_parser_exception(self):
        """Parser raises exception (graceful fallback)."""
        parser = Mock()
        parser.parse_event.side_effect = Exception("Parser error")

        result = parse_smoke_events(parser)

        assert isinstance(result, pd.DataFrame)
        assert result.empty
        assert list(result.columns) == ["X", "Y", "Z", "start_tick", "end_tick"]

    def test_parse_smoke_column_name_variance(self):
        """Handle both 'x'/'X' and 'y'/'Y' column names (demoparser2 variance)."""
        parser = Mock()
        # Some demos use lowercase 'x', 'y', 'z'
        det_df = pd.DataFrame([
            {"tick": 100, "x": 500.0, "y": 600.0, "z": 0.0}
        ])
        parser.parse_event.return_value = det_df

        result = parse_smoke_events(parser)

        # Result should normalize to uppercase
        assert result.iloc[0]["X"] == 500.0
        assert result.iloc[0]["Y"] == 600.0


class TestParseFlashIntervals:
    """Extract flash blindness windows for a player."""

    def test_parse_flash_no_events(self):
        """No flash events for player."""
        parser = Mock()
        parser.parse_event.return_value = pd.DataFrame()

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_flash_single_event_in_window(self):
        """Single flash event within search window."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 12345, "blind_duration": 2.0}  # 2 seconds
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 1
        assert result[0] == (100, 100 + int(2.0 * 64))  # 100 to 228

    def test_parse_flash_outside_window_before(self):
        """Flash event ends before search window starts (excluded)."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 10, "userid_steamid": 12345, "blind_duration": 0.5}  # Ends at 10+32=42, before 100
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=100, search_end=1000)

        assert len(result) == 0

    def test_parse_flash_outside_window_after(self):
        """Flash event after search window (excluded)."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 1100, "userid_steamid": 12345, "blind_duration": 2.0}
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=100, search_end=1000)

        assert len(result) == 0

    def test_parse_flash_overlapping_window(self):
        """Flash event overlaps with search window (included)."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 900, "userid_steamid": 12345, "blind_duration": 2.0}  # Ends at tick 1028
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=100, search_end=1000)

        assert len(result) == 1  # Flash overlaps (900 < 1000)

    def test_parse_flash_multiple_events(self):
        """Multiple flash events for same player."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 12345, "blind_duration": 1.0},
            {"tick": 300, "userid_steamid": 12345, "blind_duration": 1.5},
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 2
        assert result[0] == (100, 100 + int(1.0 * 64))
        assert result[1] == (300, 300 + int(1.5 * 64))

    def test_parse_flash_different_player(self):
        """Flash event for different player (excluded)."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 99999, "blind_duration": 2.0}
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 0

    def test_parse_flash_column_name_variance(self):
        """Handle both 'userid_steamid' and 'user_steamid' column names."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "user_steamid": 12345, "blind_duration": 2.0}
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 1

    def test_parse_flash_duration_field_variance(self):
        """Handle both 'blind_duration' and 'duration' field names."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 12345, "duration": 2.5}  # Use 'duration' instead
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 1
        assert result[0] == (100, 100 + int(2.5 * 64))

    def test_parse_flash_parser_exception(self):
        """Parser raises exception (graceful fallback)."""
        parser = Mock()
        parser.parse_event.side_effect = Exception("Parser error")

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert isinstance(result, list)
        assert len(result) == 0

    def test_parse_flash_missing_tick_column(self):
        """DataFrame missing 'tick' column — itertuples raises AttributeError, caught by exception handler."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"userid_steamid": 12345, "blind_duration": 2.0}  # No 'tick'
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 0

    def test_parse_flash_zero_duration(self):
        """Flash with zero duration — still recorded (0.0 is not None, does not fall through to 'duration').
        Verifies the blind_duration=0.0 fix: bd=0.0 → duration_s=0.0, f_end=f_start."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 12345, "blind_duration": 0.0}
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert len(result) == 1
        assert result[0] == (100, 100)

    def test_parse_flash_no_steamid_column_returns_empty(self):
        """blind_df has neither userid_steamid nor user_steamid column → []."""
        parser = Mock()
        parser.parse_event.return_value = pd.DataFrame({
            "tick": [100, 200],
            "blind_duration": [1.0, 0.5],
        })

        result = parse_flash_intervals(parser, player_steamid=12345, search_start=0, search_end=1000)

        assert result == []

    def test_parse_flash_custom_tickrate(self):
        """Non-default tickrate (128) affects flash end_tick calculation."""
        parser = Mock()
        blind_df = pd.DataFrame([
            {"tick": 100, "userid_steamid": 12345, "blind_duration": 2.0}
        ])
        parser.parse_event.return_value = blind_df

        result = parse_flash_intervals(
            parser, player_steamid=12345, search_start=0, search_end=1000,
            tickrate=128,
        )

        assert len(result) == 1
        # 2.0s * 128 ticks/s = 256 ticks
        assert result[0] == (100, 100 + int(2.0 * 128))
