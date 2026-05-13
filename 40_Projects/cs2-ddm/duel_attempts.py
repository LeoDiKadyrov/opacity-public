from __future__ import annotations

import logging
import math
import time
from dataclasses import dataclass
from typing import List, Optional, Tuple

import pandas as pd

from config import (
    VELOCITY_PEEK_THRESHOLD_UPS,
    KNIFE_WEAPON_NAMES,
    AWP_WEAPON_NAMES,
    _FIRE_CLUSTER_GAP_TICKS,
    _FIRE_CLUSTER_MAX_SPAN_TICKS,
    _ATTEMPT_WINDOW_BEFORE_TICKS,
    _ATTEMPT_WINDOW_AFTER_TICKS,
    _KILL_CONFIRM_WINDOW_TICKS,
    _BULLETS_FOR_HIT_RATE,
)

_HIT_LATENCY_TICKS = 4  # tolerance between fire and registered hurt (~60ms)


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


class DuelAttemptFinder:
    """
    T0-anchored duel attempt detection.

    For each cluster of player weapon_fire events, scan a window around the
    cluster via BVH to find T0 — the first tick any enemy becomes visible.
    If no T0 found, the cluster is dropped.

    Each accepted attempt reports:
      - was_killed: a player_death (attacker=self, victim=target) within
        _KILL_CONFIRM_WINDOW_TICKS of T0.
      - bullets_fired / bullets_hit: count of the first _BULLETS_FOR_HIT_RATE
        fire ticks at or after T0, and how many produced a registered
        player_hurt on the target within _HIT_LATENCY_TICKS.
    """

    def __init__(
        self,
        t0_detector,
        player_steamid: int,
        match_id: str,
        map_name: str,
        tickrate: int = 64,
        velocity_peek_threshold: float = VELOCITY_PEEK_THRESHOLD_UPS,
        logger: Optional[logging.Logger] = None,
    ):
        self.t0_detector = t0_detector
        self.player_steamid = player_steamid
        self.match_id = match_id
        self.map_name = map_name
        self.tickrate = tickrate
        self.velocity_peek_threshold = velocity_peek_threshold
        self.logger = logger or logging.getLogger(__name__)

    def find_attempts(
        self,
        player_fire_df: pd.DataFrame,
        all_ticks_df: pd.DataFrame,
        all_hurt_df: pd.DataFrame,
        all_death_df: pd.DataFrame,
        active_smokes: Optional[pd.DataFrame] = None,
        excluded_weapons: Optional[set] = None,
    ) -> List[DuelAttempt]:
        if excluded_weapons is None:
            excluded_weapons = KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES

        fire_df = player_fire_df.copy()
        if "weapon" in fire_df.columns:
            fire_df = fire_df[
                ~fire_df["weapon"].astype(str).str.lower().isin(excluded_weapons)
            ]
        if fire_df.empty:
            return []

        fire_ticks = sorted(int(t) for t in fire_df["tick"].dropna().tolist())
        clusters = self._cluster_fires(fire_ticks)

        n_clusters = len(clusters)
        self.logger.info(
            f"[attempts] match={self.match_id} map={self.map_name} "
            f"fires={len(fire_ticks)} clusters={n_clusters} "
            f"all_ticks_rows={len(all_ticks_df)}"
        )
        t_start = time.perf_counter()
        log_every = max(1, n_clusters // 20)  # ~20 progress pings

        attempts: List[DuelAttempt] = []
        for i, cluster_ticks in enumerate(clusters):
            c_start = time.perf_counter()
            attempt = self._process_cluster(
                cluster_ticks, all_ticks_df, all_hurt_df, all_death_df, active_smokes
            )
            c_elapsed = time.perf_counter() - c_start

            if attempt is not None:
                attempts.append(attempt)

            # Per-cluster progress log
            if (i + 1) % log_every == 0 or c_elapsed > 2.0:
                total = time.perf_counter() - t_start
                rate = (i + 1) / total if total > 0 else 0
                eta = (n_clusters - (i + 1)) / rate if rate > 0 else 0
                self.logger.info(
                    f"[attempts] {i+1}/{n_clusters} clusters "
                    f"({len(attempts)} accepted) elapsed={total:.1f}s "
                    f"rate={rate:.1f}/s eta={eta:.0f}s "
                    f"last_cluster={c_elapsed*1000:.0f}ms "
                    f"window=[{cluster_ticks[0]-_ATTEMPT_WINDOW_BEFORE_TICKS},"
                    f"{cluster_ticks[-1]+_ATTEMPT_WINDOW_AFTER_TICKS}] "
                    f"fires_in_cluster={len(cluster_ticks)}"
                )

        total = time.perf_counter() - t_start
        self.logger.info(
            f"[attempts] DONE {len(attempts)}/{n_clusters} accepted in {total:.1f}s"
        )
        return attempts

    @staticmethod
    def _cluster_fires(fire_ticks: List[int]) -> List[List[int]]:
        if not fire_ticks:
            return []
        clusters: List[List[int]] = [[fire_ticks[0]]]
        for t in fire_ticks[1:]:
            current = clusters[-1]
            if (
                t - current[-1] > _FIRE_CLUSTER_GAP_TICKS
                or t - current[0] > _FIRE_CLUSTER_MAX_SPAN_TICKS
            ):
                clusters.append([t])
            else:
                current.append(t)
        return clusters

    def _process_cluster(
        self,
        cluster_ticks: List[int],
        all_ticks_df: pd.DataFrame,
        all_hurt_df: pd.DataFrame,
        all_death_df: pd.DataFrame,
        active_smokes: Optional[pd.DataFrame],
    ) -> Optional[DuelAttempt]:
        first_fire = cluster_ticks[0]
        last_fire = cluster_ticks[-1]
        window_start = first_fire - _ATTEMPT_WINDOW_BEFORE_TICKS
        window_end = last_fire + _ATTEMPT_WINDOW_AFTER_TICKS

        found = self.t0_detector.find_first_visible_enemy_in_window(
            all_ticks_df, self.player_steamid, window_start, window_end, active_smokes
        )
        if found is None:
            return None
        t0_tick, enemy_sid, crosshair_angle = found

        was_killed = self._check_kill(t0_tick, enemy_sid, all_death_df)
        bullets_fired, bullets_hit = self._count_bullets(
            cluster_ticks, t0_tick, enemy_sid, all_hurt_df
        )
        player_velocity = self._player_velocity(all_ticks_df, t0_tick)
        engagement = (
            "peek"
            if not math.isnan(player_velocity) and player_velocity >= self.velocity_peek_threshold
            else "hold"
        )
        hurt_victims = self._hurt_victims_in_window(
            cluster_ticks[0] - _ATTEMPT_WINDOW_BEFORE_TICKS,
            cluster_ticks[-1] + _ATTEMPT_WINDOW_AFTER_TICKS + _HIT_LATENCY_TICKS,
            all_hurt_df,
        )

        return DuelAttempt(
            match_id=self.match_id,
            map_name=self.map_name,
            t0_tick=t0_tick,
            enemy_steamid=enemy_sid,
            was_killed=was_killed,
            bullets_fired=bullets_fired,
            bullets_hit=bullets_hit,
            engagement_type=engagement,
            player_velocity_ups=player_velocity,
            crosshair_angle_deg=crosshair_angle,
            hurt_victims_in_window=hurt_victims,
            fires_in_cluster=len(cluster_ticks),
            player_steamid=self.player_steamid,
        )

    def _check_kill(
        self, t0_tick: int, enemy_sid: int, all_death_df: pd.DataFrame
    ) -> bool:
        if all_death_df is None or all_death_df.empty:
            return False
        if "attacker_steamid" not in all_death_df.columns or "user_steamid" not in all_death_df.columns:
            return False
        deaths = all_death_df[
            (all_death_df["tick"] >= t0_tick)
            & (all_death_df["tick"] <= t0_tick + _KILL_CONFIRM_WINDOW_TICKS)
            & (all_death_df["attacker_steamid"].astype(str) == str(self.player_steamid))
            & (all_death_df["user_steamid"].astype(str) == str(enemy_sid))
        ]
        return not deaths.empty

    def _count_bullets(
        self,
        cluster_ticks: List[int],
        t0_tick: int,
        enemy_sid: int,
        all_hurt_df: pd.DataFrame,
    ) -> Tuple[int, int]:
        fires_after_t0 = [t for t in cluster_ticks if t >= t0_tick][:_BULLETS_FOR_HIT_RATE]
        bullets_fired = len(fires_after_t0)
        if bullets_fired == 0 or all_hurt_df is None or all_hurt_df.empty:
            return bullets_fired, 0
        if "attacker_steamid" not in all_hurt_df.columns:
            return bullets_fired, 0

        on_target = all_hurt_df[
            (all_hurt_df["attacker_steamid"].astype(str) == str(self.player_steamid))
            & (all_hurt_df["user_steamid"].astype(str) == str(enemy_sid))
        ]
        if on_target.empty:
            return bullets_fired, 0

        hurt_ticks = sorted(int(t) for t in on_target["tick"].dropna().tolist())
        bullets_hit = 0
        for f in fires_after_t0:
            if any(f <= h <= f + _HIT_LATENCY_TICKS for h in hurt_ticks):
                bullets_hit += 1
        return bullets_fired, bullets_hit

    def _hurt_victims_in_window(
        self, window_start: int, window_end: int, all_hurt_df: pd.DataFrame
    ) -> str:
        if all_hurt_df is None or all_hurt_df.empty:
            return ""
        if "attacker_steamid" not in all_hurt_df.columns:
            return ""
        rows = all_hurt_df[
            (all_hurt_df["attacker_steamid"].astype(str) == str(self.player_steamid))
            & (all_hurt_df["tick"] >= window_start)
            & (all_hurt_df["tick"] <= window_end)
        ]
        if rows.empty:
            return ""
        victims = rows["user_steamid"].astype(str).unique().tolist()
        return ",".join(sorted(victims))

    def _player_velocity(self, all_ticks_df: pd.DataFrame, tick: int) -> float:
        """XY speed at `tick` via position delta to next-tick row × tickrate.

        Demos don't expose vel_x/vel_y columns — velocity must be derived from
        consecutive X/Y positions, matching DDMAnalyzer._compute_velocity.
        """
        player_ticks = all_ticks_df[
            all_ticks_df["steamid"] == self.player_steamid
        ].sort_values("tick")
        at_t = player_ticks[player_ticks["tick"] == tick]
        after_t = player_ticks[player_ticks["tick"] > tick]
        if at_t.empty or after_t.empty:
            return float("nan")
        p0 = at_t.iloc[0]
        p1 = after_t.iloc[0]
        dx = float(p1["X"]) - float(p0["X"])
        dy = float(p1["Y"]) - float(p0["Y"])
        return math.sqrt(dx * dx + dy * dy) * self.tickrate
