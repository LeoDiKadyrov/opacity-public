"""reaction_timing.py -- OF-3 reaction timing on KNOWN opponent (duel_episodes path).

Implements the new T0 backward-search wrapper (D-05) and the T1 "crosshair
LANDS" detector (D-01/D-02/D-03) that replaces the deprecated
`ddm_analyzer._detect_t1` motion-towards predicate (D-04, kills B-5).

Public API:
    compute_timing(episode, ticks_df, t0_detector, ticks_by_sid=None) -> Dict

Returns the 7 new duel_episodes columns:
    t0_tick, t0_source, t1_tick, t1_source,
    crosshair_angle_at_t0_deg, rt_visible_to_land_ms, rt_visible_to_hit_ms

t0_source in {"BVH+AABB", "long_visible", "never_visible", "error"}
t1_source in {"lands", "never_landed", "no_t0", "error"}

REUSE -- do NOT reimplement:
    t0_detector.find_t0 (backward search + second backward-continuity pass)
    ddm_analyzer.DDMAnalyzer.get_desired_angles / angular_diff (geometry)

DEPRECATED -- do NOT import: ddm_analyzer._detect_t1, config.T0_MIN_OFFSET_TICKS,
config.T0_TO_T2_MAX_TICKS (old engagement-window framing, D-04/D-16).
"""

from __future__ import annotations

import logging
import math
from typing import Dict, Optional, Tuple

import pandas as pd

from config import (
    TARGET_REACHED_THRESHOLD,
    T0_BACKWARD_SEARCH_CAP_TICKS,
    T1_SUSTAINED_AIM_TICKS,
)
from ddm_analyzer import DDMAnalyzer

logger = logging.getLogger(__name__)

MS_PER_TICK = 1000.0 / 64.0  # 15.625


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _row_at_tick(
    ticks_df: pd.DataFrame,
    steamid: int,
    tick: int,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Optional[pd.Series]:
    """Return the tick-row for `steamid` at `tick`, or None if missing."""
    if ticks_by_sid is not None and steamid in ticks_by_sid:
        frame = ticks_by_sid[steamid]
        match = frame[frame["tick"] == tick]
    else:
        match = ticks_df[(ticks_df["steamid"] == steamid) & (ticks_df["tick"] == tick)]
    if match.empty:
        return None
    return match.iloc[0]


def _angular_dist_at_tick(
    ticks_df: pd.DataFrame,
    player_steamid: int,
    enemy_steamid: int,
    tick: int,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Optional[float]:
    """Angular distance (deg) between player crosshair and the desired aim
    direction toward the enemy at `tick`. None if either row is missing.
    """
    p_row = _row_at_tick(ticks_df, player_steamid, tick, ticks_by_sid)
    e_row = _row_at_tick(ticks_df, enemy_steamid, tick, ticks_by_sid)
    if p_row is None or e_row is None:
        return None

    desired_pitch, desired_yaw = DDMAnalyzer.get_desired_angles(
        float(p_row["X"]), float(p_row["Y"]), float(p_row["Z"]),
        float(e_row["X"]), float(e_row["Y"]), float(e_row["Z"]),
    )
    actual_pitch = float(p_row["pitch"])
    actual_yaw = float(p_row["yaw"])

    yaw_diff = DDMAnalyzer.angular_diff(actual_yaw, desired_yaw)
    pitch_diff = DDMAnalyzer.angular_diff(actual_pitch, desired_pitch)
    return math.hypot(yaw_diff, pitch_diff)


def _is_visible_at_tick(
    ticks_df: pd.DataFrame,
    player_steamid: int,
    enemy_steamid: int,
    tick: int,
    t0_detector,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> bool:
    """Single-tick visibility check, detector-agnostic.

    Both the production T0Detector and the synthetic _StubT0Detector
    implement `find_t0(all_ticks_df, player_sid, enemy_sid, search_start_tick,
    search_end_tick, ...)`. Calling it with search_start==search_end==tick
    reuses that single contract for the second backward-continuity pass
    (Pitfall 3) without depending on a detector-specific `is_visible` method.
    """
    found_tick, _method = t0_detector.find_t0(
        ticks_df,
        player_steamid,
        enemy_steamid,
        tick,
        tick,
        ticks_by_sid=ticks_by_sid,
    )
    return found_tick is not None


# ---------------------------------------------------------------------------
# T0 backward search (D-05)
# ---------------------------------------------------------------------------

def _find_t0(
    ticks_df: pd.DataFrame,
    player_steamid: int,
    enemy_steamid: int,
    first_event_tick: int,
    t0_detector,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Tuple[Optional[int], str]:
    """T0 backward search wrapper around find_t0 + second backward-continuity
    pass (D-05, Pitfall 3).

    1. Bounded backward search in [first_event_tick - CAP, first_event_tick]
       via find_t0. (None, _) -> never_visible.
    2. Second pass: walk backward tick-by-tick from first_event_tick while the
       opponent stays continuously visible, until visibility breaks or the
       cap (search_start) is reached. The earliest still-visible tick in that
       unbroken run containing first_event_tick is the real T0 -- NOT the
       first-ever-visible tick find_t0's forward scan would return.
    """
    search_start = first_event_tick - T0_BACKWARD_SEARCH_CAP_TICKS
    search_end = first_event_tick

    t0_candidate, _method = t0_detector.find_t0(
        ticks_df,
        player_steamid,
        enemy_steamid,
        search_start,
        search_end,
        ticks_by_sid=ticks_by_sid,
    )
    if t0_candidate is None:
        return None, "never_visible"

    # Second backward-continuity pass: find the start of the unbroken
    # visibility run CONTAINING first_event_tick.
    run_start = first_event_tick
    tick = first_event_tick - 1
    while tick >= search_start:
        if _is_visible_at_tick(
            ticks_df, player_steamid, enemy_steamid, tick, t0_detector, ticks_by_sid
        ):
            run_start = tick
            tick -= 1
        else:
            break

    if run_start <= search_start:
        return search_start, "long_visible"
    return run_start, "BVH+AABB"


# ---------------------------------------------------------------------------
# T1 LANDS detector (D-01/D-02/D-03)
# ---------------------------------------------------------------------------

def _find_t1(
    ticks_df: pd.DataFrame,
    player_steamid: int,
    enemy_steamid: int,
    t0_tick: int,
    first_event_tick: int,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Tuple[Optional[int], str]:
    """T1 = first tick t in [t0_tick, first_event_tick] such that the crosshair
    is on-target (angular_dist <= TARGET_REACHED_THRESHOLD) at t and stays
    on-target for T1_SUSTAINED_AIM_TICKS+1 ticks total (inclusive window).

    The inclusive [t0, first_event_tick] upper bound naturally covers the
    pre-aimed@T0 case (t1_tick == t0_tick) with no separate branch.
    """
    window_size = T1_SUSTAINED_AIM_TICKS + 1  # 3 ticks total

    # Precompute angular_dist for every tick in [t0_tick, first_event_tick].
    dists: Dict[int, Optional[float]] = {}
    for t in range(t0_tick, first_event_tick + 1):
        dists[t] = _angular_dist_at_tick(
            ticks_df, player_steamid, enemy_steamid, t, ticks_by_sid
        )

    for t in range(t0_tick, first_event_tick + 1):
        # Need the full sustained window [t, t+window_size-1] to be on-target.
        window_ticks = range(t, t + window_size)
        on_target_all = True
        for wt in window_ticks:
            d = dists.get(wt)
            if wt > first_event_tick:
                # Outside the precomputed range -- fetch directly.
                d = _angular_dist_at_tick(
                    ticks_df, player_steamid, enemy_steamid, wt, ticks_by_sid
                )
            if d is None or d > TARGET_REACHED_THRESHOLD:
                on_target_all = False
                break
        if on_target_all:
            return t, "lands"

    return None, "never_landed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_NULL_RESULT_KEYS = (
    "t0_tick",
    "t0_source",
    "t1_tick",
    "t1_source",
    "crosshair_angle_at_t0_deg",
    "rt_visible_to_land_ms",
    "rt_visible_to_hit_ms",
)


def compute_timing(
    episode: Dict,
    ticks_df: pd.DataFrame,
    t0_detector,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Dict:
    """Compute T0/T1 timing for one duel episode (D-01/D-03/D-05/D-06/D-08).

    episode keys used: player_steamid, opponent_steamid, first_event_tick,
    last_event_tick.

    Never raises -- on failure returns all-NULL with t0_source="error" and
    t1_source="error" so the row is still written (label-not-drop, model on
    outcome_first.py per-player try/except).
    """
    try:
        player_steamid = int(episode["player_steamid"])
        opponent_steamid = int(episode["opponent_steamid"])
        first_event_tick = int(episode["first_event_tick"])

        t0_tick, t0_source = _find_t0(
            ticks_df,
            player_steamid,
            opponent_steamid,
            first_event_tick,
            t0_detector,
            ticks_by_sid=ticks_by_sid,
        )

        if t0_tick is None:
            return {
                "t0_tick": None,
                "t0_source": t0_source,
                "t1_tick": None,
                "t1_source": "no_t0",
                "crosshair_angle_at_t0_deg": None,
                "rt_visible_to_land_ms": None,
                "rt_visible_to_hit_ms": None,
            }

        crosshair_angle_at_t0_deg = _angular_dist_at_tick(
            ticks_df, player_steamid, opponent_steamid, t0_tick, ticks_by_sid
        )

        t1_tick, t1_source = _find_t1(
            ticks_df,
            player_steamid,
            opponent_steamid,
            t0_tick,
            first_event_tick,
            ticks_by_sid=ticks_by_sid,
        )

        if t1_tick is not None:
            rt_visible_to_land_ms = (t1_tick - t0_tick) * MS_PER_TICK
        else:
            rt_visible_to_land_ms = None
        rt_visible_to_hit_ms = (first_event_tick - t0_tick) * MS_PER_TICK

        return {
            "t0_tick": t0_tick,
            "t0_source": t0_source,
            "t1_tick": t1_tick,
            "t1_source": t1_source,
            "crosshair_angle_at_t0_deg": crosshair_angle_at_t0_deg,
            "rt_visible_to_land_ms": rt_visible_to_land_ms,
            "rt_visible_to_hit_ms": rt_visible_to_hit_ms,
        }
    except Exception:
        logger.exception("compute_timing failed for episode %r", episode)
        return {
            "t0_tick": None,
            "t0_source": "error",
            "t1_tick": None,
            "t1_source": "error",
            "crosshair_angle_at_t0_deg": None,
            "rt_visible_to_land_ms": None,
            "rt_visible_to_hit_ms": None,
        }
