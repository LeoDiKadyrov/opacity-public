"""Wave-0 RED tests for reaction_timing.py (OF-3 reaction timing, D-01/D-03/D-05/D-06).

Written BEFORE the module exists (TDD). Public API under test:
    reaction_timing.compute_timing(episode, ticks_df, t0_detector, ticks_by_sid=None) -> Dict

This file MUST fail at collection (ModuleNotFoundError: reaction_timing) until
OF-3-02 implements reaction_timing.py. That is the expected Wave-0 RED state —
do NOT implement reaction_timing.py in this plan.

Contract pinned here:
  - D-01: T1 = first tick the crosshair LANDS (angular_dist <= TARGET_REACHED_THRESHOLD)
    and stays landed for T1_SUSTAINED_AIM_TICKS+1 ticks. NOT "motion towards" (B-5 class).
  - D-03: t1_source in {"lands", "never_landed", "no_t0"}.
  - D-05: T0 backward search — when the enemy is visible in multiple disjoint runs,
    T0 is the START of the run CONTAINING first_event_tick (T2), not the first-ever
    visible tick. Visibility runs extending to the search cap are labeled
    "long_visible" (no clamp). Never-visible -> t0_tick=None, t0_source="never_visible".
  - D-06: rt_visible_to_land_ms / rt_visible_to_hit_ms derived as
    (t1_tick - t0_tick) * MS_PER_TICK and (first_event_tick - t0_tick) * MS_PER_TICK.
"""

from __future__ import annotations

import pandas as pd
import pytest

from reaction_timing import compute_timing  # NOT YET IMPLEMENTED -> RED
from config import TARGET_REACHED_THRESHOLD, T0_BACKWARD_SEARCH_CAP_TICKS
from ddm_analyzer import DDMAnalyzer

MS_PER_TICK = 1000.0 / 64.0

P = 76561198386265483  # player (donk)
E = 76561198113666193  # enemy / opponent

# Fixed world positions for player and enemy. Player stands still; enemy stands
# still at a position offset on the X axis so desired (pitch, yaw) is constant
# and easy to reason about.
P_POS = (0.0, 0.0, 0.0)
E_POS = (500.0, 0.0, 0.0)

_DESIRED_PITCH, _DESIRED_YAW = DDMAnalyzer.get_desired_angles(
    P_POS[0], P_POS[1], P_POS[2], E_POS[0], E_POS[1], E_POS[2]
)


class _StubT0Detector:
    """Synthetic T0Detector double — no BVH, no demo files.

    `visible_ticks` is the set of ticks where the enemy is BVH-visible to the
    player. `find_t0` mimics the real T0Detector contract: scans
    [search_start_tick, search_end_tick] and returns the first tick in that
    range where the enemy is visible, or (None, "not_found").
    """

    def __init__(self, visible_ticks: set[int]):
        self.visible_ticks = visible_ticks

    def is_visible(self, tick: int) -> bool:
        return tick in self.visible_ticks

    def find_t0(
        self,
        all_ticks_df,
        player_steamid,
        enemy_steamid,
        search_start_tick,
        search_end_tick,
        active_smokes=None,
        flash_intervals=None,
        ticks_by_sid=None,
    ):
        for tick in range(search_start_tick, search_end_tick + 1):
            if tick in self.visible_ticks:
                return tick, "BVH+AABB"
        return None, "not_found"


def _make_ticks_df(
    start_tick: int,
    end_tick: int,
    yaw_by_tick: dict[int, float],
    pitch_by_tick: dict[int, float] | None = None,
) -> pd.DataFrame:
    """Build a synthetic tick frame with player + enemy rows.

    Player rows carry crosshair (pitch, yaw) per `yaw_by_tick`/`pitch_by_tick`
    (defaulting to the desired angle, i.e. perfectly on-target, when absent).
    Enemy rows are stationary at E_POS.
    """
    rows = []
    for tick in range(start_tick, end_tick + 1):
        yaw = yaw_by_tick.get(tick, _DESIRED_YAW)
        pitch = (pitch_by_tick or {}).get(tick, _DESIRED_PITCH)
        rows.append(
            {
                "tick": tick,
                "steamid": P,
                "X": P_POS[0],
                "Y": P_POS[1],
                "Z": P_POS[2],
                "pitch": pitch,
                "yaw": yaw,
            }
        )
        rows.append(
            {
                "tick": tick,
                "steamid": E,
                "X": E_POS[0],
                "Y": E_POS[1],
                "Z": E_POS[2],
                "pitch": 0.0,
                "yaw": 0.0,
            }
        )
    return pd.DataFrame(rows)


def _episode(first_event_tick: int, last_event_tick: int) -> dict:
    return {
        "player_steamid": P,
        "opponent_steamid": E,
        "first_event_tick": first_event_tick,
        "last_event_tick": last_event_tick,
    }


def test_t1_flick_not_one_tick():
    """D-01/D-03 (B-5 guard): a 30deg flick at T0 cannot land+sustain in 1 tick.

    Crosshair is 30deg off desired yaw at T0 and for several ticks after;
    only converges to within TARGET_REACHED_THRESHOLD 5 ticks later. T1 must
    NOT be T0+1 (the B-5 motion-not-landing artifact).
    """
    t0 = 1000
    t2 = 1020
    off_yaw = _DESIRED_YAW + 30.0

    yaw_by_tick = {}
    for tick in range(t0, t0 + 5):
        yaw_by_tick[tick] = off_yaw
    for tick in range(t0 + 5, t2 + 1):
        yaw_by_tick[tick] = _DESIRED_YAW  # converges and stays landed

    ticks_df = _make_ticks_df(t0 - 5, t2 + 5, yaw_by_tick)
    detector = _StubT0Detector(visible_ticks=set(range(t0, t2 + 1)))
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] == t0
    assert result["t1_tick"] is not None
    assert result["t1_tick"] != result["t0_tick"] + 1


def test_t1_pre_aimed_at_t0_lands_immediately():
    """D-01/D-03: crosshair already within TARGET_REACHED_THRESHOLD at T0 and
    stays landed -> t1_tick == t0_tick, t1_source == "lands" (no separate
    pre_aimed branch, unlike Phase 10).
    """
    t0 = 2000
    t2 = 2010

    # On-target for the entire window (default yaw == _DESIRED_YAW).
    ticks_df = _make_ticks_df(t0 - 5, t2 + 5, yaw_by_tick={})
    detector = _StubT0Detector(visible_ticks=set(range(t0, t2 + 1)))
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] == t0
    assert result["t1_tick"] == result["t0_tick"]
    assert result["t1_source"] == "lands"


def test_t1_never_lands_labeled():
    """D-01/D-03: crosshair stays >= 2*TARGET_REACHED_THRESHOLD off-target the
    whole window -> t1_tick is None, t1_source == "never_landed".
    """
    t0 = 3000
    t2 = 3020
    off_yaw = _DESIRED_YAW + 2 * TARGET_REACHED_THRESHOLD + 5.0

    yaw_by_tick = {tick: off_yaw for tick in range(t0 - 5, t2 + 6)}
    ticks_df = _make_ticks_df(t0 - 5, t2 + 5, yaw_by_tick)
    detector = _StubT0Detector(visible_ticks=set(range(t0, t2 + 1)))
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] == t0
    assert result["t1_tick"] is None
    assert result["t1_source"] == "never_landed"


def test_t0_backward_run_start_not_first_visible():
    """D-05 (Pitfall 3): enemy visible at tick A, occluded, visible again from
    B through T2. T0 must be the START of the run CONTAINING T2 (B), NOT the
    first-ever-visible tick (A).
    """
    a = 1000  # first-ever-visible (isolated tick)
    # gap: ticks 1001-1099 occluded
    b = 1100  # start of the run containing T2
    t2 = 1120

    visible_ticks = {a} | set(range(b, t2 + 1))
    ticks_df = _make_ticks_df(a - 5, t2 + 5, yaw_by_tick={})
    detector = _StubT0Detector(visible_ticks=visible_ticks)
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] == b
    assert result["t0_tick"] != a


def test_t0_long_visible_labeled_at_cap():
    """D-05: visibility run extends all the way to the backward search cap ->
    t0_source == "long_visible", t0_tick == search_start (the cap boundary),
    NOT a clamped "real measurement".
    """
    t2 = 5000
    search_start = t2 - T0_BACKWARD_SEARCH_CAP_TICKS

    # Visible for the entire window from search_start through T2 (no gaps).
    visible_ticks = set(range(search_start, t2 + 1))
    ticks_df = _make_ticks_df(search_start, t2, yaw_by_tick={})
    detector = _StubT0Detector(visible_ticks=visible_ticks)
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_source"] == "long_visible"
    assert result["t0_tick"] == search_start


def test_t0_never_visible_labeled():
    """D-05: BVH never sees the enemy in the window -> t0_tick is None,
    t0_source == "never_visible", and downstream t1_source == "no_t0".
    """
    t2 = 6000
    ticks_df = _make_ticks_df(t2 - 50, t2 + 5, yaw_by_tick={})
    detector = _StubT0Detector(visible_ticks=set())  # never visible
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] is None
    assert result["t0_source"] == "never_visible"
    assert result["t1_source"] == "no_t0"


def test_rt_columns_derived():
    """D-06: when t0 and t1 both resolve, rt_visible_to_land_ms ==
    (t1_tick - t0_tick) * MS_PER_TICK and rt_visible_to_hit_ms ==
    (first_event_tick - t0_tick) * MS_PER_TICK.
    """
    t0 = 7000
    t2 = 7010

    # On-target for the entire window -> t1_tick == t0_tick (lands immediately).
    ticks_df = _make_ticks_df(t0 - 5, t2 + 5, yaw_by_tick={})
    detector = _StubT0Detector(visible_ticks=set(range(t0, t2 + 1)))
    episode = _episode(first_event_tick=t2, last_event_tick=t2)

    result = compute_timing(episode, ticks_df, detector)

    assert result["t0_tick"] is not None
    assert result["t1_tick"] is not None
    expected_land_ms = (result["t1_tick"] - result["t0_tick"]) * MS_PER_TICK
    expected_hit_ms = (t2 - result["t0_tick"]) * MS_PER_TICK
    assert result["rt_visible_to_land_ms"] == pytest.approx(expected_land_ms)
    assert result["rt_visible_to_hit_ms"] == pytest.approx(expected_hit_ms)
