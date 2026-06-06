"""
DuelAttempt dataclass for T0-anchored duel attempt typing.

NOTE: DuelAttemptFinder (geometry-first opponent selection) was removed in OF-2
-- opponent identity now comes from ground-truth events via outcome_first.py.
The DuelAttempt dataclass remains for legacy CSV/db row typing (kill_rate_analysis).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class DuelAttempt:
    """A single T0-anchored duel attempt.

    T0 = first tick the target enemy became BVH-visible inside the
    [cluster_first_fire - W_before, cluster_last_fire + W_after] window.
    """

    match_id: str
    map_name: str
    t0_tick: int
    enemy_steamid: int
    was_killed: bool
    bullets_fired: int
    bullets_hit: int
    engagement_type: str
    player_velocity_ups: float
    crosshair_angle_deg: float
    # Diagnostic: all enemy steamids player actually damaged during the cluster
    # window (cluster_first_fire - W_before .. cluster_last_fire + W_after + hit tolerance).
    # Comma-separated. Empty string if none. Used to detect target misidentification
    # where BVH-selected enemy_steamid differs from who player was really shooting at.
    hurt_victims_in_window: str = ""
    fires_in_cluster: int = 0
    player_steamid: Optional[int] = None  # D-05: player identity for cross-player queries
