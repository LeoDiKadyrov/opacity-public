"""
Shared fixtures and configuration for the DDM test suite.

Phase 9.1 (Wave 0) extension: ``fake_parser`` fixture exposes a mock that
supports BOTH the legacy singular ``parse_event(name)`` shape used by the
existing 322 tests AND the batched ``parse_events(list[name])`` shape that
production code migrates to in plan 09.1-02 (Pitfall #3 mitigation).

Usage in tests:

    def test_something(fake_parser):
        # legacy singular (returns DataFrame directly):
        fake_parser.parse_event.return_value = pd.DataFrame(...)

        # new batched (returns list[(name, DataFrame)]):
        fake_parser.parse_events.return_value = [
            ("player_hurt",  hurt_df),
            ("player_death", death_df),
            ("weapon_fire",  fire_df),
            ("round_start",  rs_df),
        ]

        # or override with a spy callable:
        fake_parser.parse_events = lambda events: [(n, pd.DataFrame()) for n in events]

Production code uses ``parse_events([list])`` per RESEARCH.md §Pattern 2 — the
return shape is a list-of-tuples, NOT a dict, and order is non-deterministic
(Pitfall #2). Tests should mirror the list-of-tuples shape and let the code
under test build its own ``dict(by_name)``.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def fake_parser():
    """A demoparser2.DemoParser stand-in supporting both event-API shapes.

    The default ``parse_events`` behavior returns ``[(name, empty_df)]`` for
    every requested event name so that tests not focused on event content
    don't have to hand-stub the full 4-event tuple list. Tests that DO care
    about event content override via ``return_value`` or by reassigning the
    attribute to a spy callable.
    """
    parser = MagicMock(name="fake_parser")

    # Legacy singular API — kept for backward compat with existing 322 tests.
    parser.parse_event.return_value = pd.DataFrame()

    # Batched API (demoparser2 0.41.2). Default = empty DataFrame per event,
    # preserving the list-of-tuples shape from RESEARCH.md §Pattern 2.
    def _default_parse_events(event_names, *args, **kwargs):
        return [(name, pd.DataFrame()) for name in event_names]

    parser.parse_events.side_effect = _default_parse_events

    # Common ancillary calls used by ddm_analyzer / t0_detector.
    parser.parse_ticks.return_value = pd.DataFrame()
    parser.parse_header.return_value = {"map_name": "de_test"}

    return parser
