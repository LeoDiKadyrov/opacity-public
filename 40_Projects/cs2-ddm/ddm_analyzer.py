import math
import os
import hashlib
import time
import tracemalloc
import pandas as pd
import numpy as np

try:
    import psutil as _psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False
from demoparser2 import DemoParser
from typing import Tuple, List, Dict, Optional

from t0_detector import T0Detector
from duel_attempts import DuelAttempt, DuelAttemptFinder
import bisect

import config
from config import (
    AnalysisMoment,
    get_logger,
    VELOCITY_PEEK_THRESHOLD_UPS,
    ENEMY_VELOCITY_HOLD_THRESHOLD_UPS,
    KNIFE_WEAPON_NAMES,
    AWP_WEAPON_NAMES,
    T0_MIN_OFFSET_TICKS,
    T0_TO_T2_MAX_TICKS,
    T1_GRACE_MS,
    T1_SUSTAINED_AIM_TICKS,
    T1_MIN_ANGLE_CHANGE,
    T1_NOT_AIMED_THRESHOLD,
    T1_MOVING_TOWARDS_TOLERANCE,
    _SUB_CLUSTER_GAP_TICKS,
    _ROUND_EARLY_MAX_S,
    _ROUND_MID_MAX_S,
    _SELECTIVE_WINDOW_BEFORE_TICKS,
    _SELECTIVE_WINDOW_AFTER_TICKS,
    DB_PATH,
)
import db_utils

_ENEMY_DISCOVERY_DIAG_RADIUS = 10_000  # ticks ±window for diagnostic nearby-hit search
_STEAMID_PATTERN = r"^\d{10,}$"        # valid numeric SteamID64 regex


class DDMAnalyzer:

    _TICKS_REQUIRED = ["X", "Y", "Z", "pitch", "yaw", "steamid", "name"]
    _TICKS_OPTIONAL = ["is_alive", "team_num", "is_spotted"]

    def __init__(
        self,
        demo_path: str,
        player_steamid: int,
        match_id=None,
        tickrate: int = 64,
        debug_prints: bool = False,
        enemy_velocity_threshold: float = ENEMY_VELOCITY_HOLD_THRESHOLD_UPS,
        player_velocity_threshold: float = VELOCITY_PEEK_THRESHOLD_UPS,
        demo_name: str = "",
    ):
        try:
            self.parser = DemoParser(demo_path)
        except Exception as e:
            print(f"Error initializing DemoParser: {e}")
            raise

        self.demo_path = demo_path
        self.player_steamid = player_steamid
        self.tickrate = tickrate
        self.debug_prints = debug_prints
        self.match_id = match_id if match_id is not None else self._hash_demo(demo_path)
        self.logger = get_logger(self.match_id, debug_prints)
        self.analysis_moments: List[AnalysisMoment] = []
        self.enemy_velocity_threshold = enemy_velocity_threshold
        self.player_velocity_threshold = player_velocity_threshold
        # demo_name: human-readable label for DB queries and Streamlit dropdowns.
        # Defaults to demo filename stem if not provided.
        self.demo_name: str = demo_name if demo_name else os.path.splitext(os.path.basename(self.demo_path))[0]
        self.last_accepted_t2_tick: Optional[int] = None  # overlapping window gate (D-07)

        try:
            header = self.parser.parse_header()
            self.map_name = header.get("map_name", "unknown")
        except Exception as e:
            self.logger.warning(f"Could not parse demo header, defaulting map_name to 'unknown': {e}")
            self.map_name = "unknown"

        try:
            self.t0_detector = T0Detector(self.map_name)
            self.logger.info(f"T0Detector ready for map '{self.map_name}'")
        except FileNotFoundError as e:
            self.t0_detector = None
            self.logger.warning(f"T0Detector unavailable: {e}")

    @staticmethod
    def _hash_demo(demo_path: str) -> str:
        return hashlib.md5(os.path.basename(demo_path).encode()).hexdigest()[:10]

    # ── Geometry helpers (used by T1 detection) ───────────────────────────────

    @staticmethod
    def get_desired_angles(
        px: float, py: float, pz: float,
        ex: float, ey: float, ez: float,
    ) -> Tuple[float, float]:
        dx, dy, dz = ex - px, ey - py, ez - pz
        yaw = math.degrees(math.atan2(dy, dx))
        h_dist = math.sqrt(dx * dx + dy * dy)
        if h_dist == 0:
            pitch = -90.0 if dz > 0 else (90.0 if dz < 0 else 0.0)
        else:
            pitch = math.degrees(math.atan2(-dz, h_dist))
        return pitch, yaw

    @staticmethod
    def angular_diff(a1: float, a2: float) -> float:
        """Signed angular difference in [-180, 180]."""
        return (a2 - a1 + 180) % 360 - 180

    # ── Phase 4: Bulk engagement builder ─────────────────────────────────────

    def auto_build_moments(
        self,
        all_hurt_df: pd.DataFrame,
        lookback_ticks: int = 300,
        cluster_gap_ticks: int = 320,
        analysis_window_seconds: int = 8,
    ) -> int:
        """
        Scan all player_hurt events by this player, group consecutive hits into
        engagement clusters, and populate self.analysis_moments automatically.

        Clustering: a new engagement starts when the gap between consecutive
        hit ticks exceeds cluster_gap_ticks (default 320 = 5 seconds at 64 Hz).

        Returns number of clusters found.
        """
        if "weapon" in all_hurt_df.columns:
            excluded = KNIFE_WEAPON_NAMES | AWP_WEAPON_NAMES
            gun_hurt_df = all_hurt_df[
                ~all_hurt_df["weapon"].astype(str).str.lower().isin(excluded)
            ]
            excluded_count = len(all_hurt_df) - len(gun_hurt_df)
            if excluded_count:
                self.logger.info(f"auto_build_moments: filtered out {excluded_count} knife/AWP hits.")
        else:
            gun_hurt_df = all_hurt_df

        if "attacker_steamid" not in gun_hurt_df.columns:
            self.logger.warning("auto_build_moments: hurt DataFrame missing required columns.")
            return 0

        donk_hits = gun_hurt_df[
            gun_hurt_df["attacker_steamid"].astype(str) == str(self.player_steamid)
        ].sort_values("tick")

        if donk_hits.empty:
            self.logger.warning("auto_build_moments: no hits by player found in demo.")
            return 0

        ticks = donk_hits["tick"].astype(int).tolist()
        victims = donk_hits["user_steamid"].astype(str).tolist()

        # Step 1: split into coarse 320-tick clusters
        coarse_clusters: List[List[Tuple[int, str]]] = []
        current_cluster: List[Tuple[int, str]] = [(ticks[0], victims[0])]
        for i in range(1, len(ticks)):
            if ticks[i] - ticks[i - 1] > cluster_gap_ticks:
                coarse_clusters.append(current_cluster)
                current_cluster = [(ticks[i], victims[i])]
            else:
                current_cluster.append((ticks[i], victims[i]))
        coarse_clusters.append(current_cluster)

        # Step 2: within each coarse cluster, split into sub-clusters when
        # victim changes AND gap > _SUB_CLUSTER_GAP_TICKS (~1 s at 64 Hz)
        cluster_starts: List[Tuple[int, str]] = []
        for coarse in coarse_clusters:
            sub: List[Tuple[int, str]] = [coarse[0]]
            for i in range(1, len(coarse)):
                tick_i, victim_i = coarse[i]
                gap = tick_i - sub[-1][0]
                victim_changed = victim_i != sub[0][1]
                if victim_changed and gap > _SUB_CLUSTER_GAP_TICKS:
                    cluster_starts.append((sub[0][0], sub[0][1]))
                    sub = [(tick_i, victim_i)]
                else:
                    sub.append((tick_i, victim_i))
            cluster_starts.append((sub[0][0], sub[0][1]))

        self.logger.info(
            f"auto_build_moments: {len(ticks)} total hits → "
            f"{len(coarse_clusters)} coarse clusters → "
            f"{len(cluster_starts)} sub-clusters (gap>{cluster_gap_ticks}/{_SUB_CLUSTER_GAP_TICKS} ticks)"
        )

        moments: List[AnalysisMoment] = []
        for first_hit_tick, victim_steamid_str in cluster_starts:
            search_start = max(0, first_hit_tick - lookback_ticks)
            demo_sec = first_hit_tick // self.tickrate
            label = f"{demo_sec // 60}:{demo_sec % 60:02d}"

            try:
                enemy_sid: Optional[int] = int(victim_steamid_str)
            except (ValueError, TypeError):
                enemy_sid = None

            moments.append(AnalysisMoment(
                timestamp=label,
                manual_t0_tick_enemy_first_visible=None,
                description=f"bulk_auto first_hit={first_hit_tick}",
                analysis_window_seconds_after_t0=analysis_window_seconds,
                target_enemy_steamid_if_known=enemy_sid,
                use_auto_t0=True,
                auto_t0_search_start_tick=search_start,
            ))

        self.analysis_moments = moments
        return len(moments)

    def find_all_duel_attempts(
        self,
        player_fire_df: pd.DataFrame,
        all_ticks_df: pd.DataFrame,
        all_hurt_df: pd.DataFrame,
        all_death_df: pd.DataFrame,
        active_smokes: Optional[pd.DataFrame] = None,
    ) -> List[DuelAttempt]:
        """
        Find all duel attempts (hit + miss) from weapon_fire clusters.
        Returns empty list if T0Detector is unavailable.
        """
        if self.t0_detector is None:
            self.logger.warning("find_all_duel_attempts: T0Detector unavailable, skipping.")
            return []

        finder = DuelAttemptFinder(
            t0_detector=self.t0_detector,
            player_steamid=self.player_steamid,
            match_id=self.match_id,
            map_name=self.map_name,
            tickrate=self.tickrate,
            velocity_peek_threshold=self.player_velocity_threshold,
            logger=self.logger,
        )
        attempts = finder.find_attempts(
            player_fire_df, all_ticks_df, all_hurt_df, all_death_df, active_smokes
        )
        self.logger.info(
            f"find_all_duel_attempts: {len(attempts)} attempts "
            f"({sum(getattr(a, 'was_killed', False) for a in attempts)} kills; "
            f"death_events_parsed={len(all_death_df)})"
        )
        return attempts

    # ── Quality filter ────────────────────────────────────────────────────────

    def is_1v1_duel(
        self,
        all_player_hurt_events_df: pd.DataFrame,
        t0_tick: int,
        t2_tick: int,
        target_enemy_id,
    ) -> Tuple[bool, str]:
        """
        Returns (True, "") if the engagement is a clean 1v1.
        Returns (False, reason_string) for any quality violation.

        Checks:
        1. Player received NO damage from third parties during [t0, t2].
        2. Player hit exactly ONE distinct enemy during [t0, t2].
        """
        window = all_player_hurt_events_df[
            (all_player_hurt_events_df["tick"] >= t0_tick)
            & (all_player_hurt_events_df["tick"] <= t2_tick)
        ]

        incoming = window[
            window["user_steamid"].astype(str) == str(self.player_steamid)
        ]
        third_party = incoming[
            incoming["attacker_steamid"].astype(str) != str(target_enemy_id)
        ]
        if not third_party.empty:
            attackers = third_party["attacker_steamid"].unique().tolist()
            return False, f"Third-party damage from {attackers}"

        outgoing = window[
            window["attacker_steamid"].astype(str) == str(self.player_steamid)
        ]
        targets_hit = outgoing["user_steamid"].unique()
        if len(targets_hit) > 1:
            return False, f"Player engaged multiple enemies: {targets_hit.tolist()}"

        return True, ""

    def _teammate_hurt_target(
        self,
        all_player_hurt_events_df: pd.DataFrame,
        t0_tick: int,
        t2_tick: int,
        target_enemy_id,
    ) -> bool:
        """True если в окне [t0..t2] кто-то кроме player нанёс урон target_enemy_id.

        Phase 6 simplified: любой attacker != player_steamid считается тиммейтом.
        Точная team_num фильтрация — Phase 8 refinement если нужна.
        """
        if all_player_hurt_events_df.empty:
            return False
        required_cols = {"tick", "user_steamid", "attacker_steamid"}
        if not required_cols.issubset(all_player_hurt_events_df.columns):
            return False
        window = all_player_hurt_events_df[
            (all_player_hurt_events_df["tick"] >= t0_tick)
            & (all_player_hurt_events_df["tick"] <= t2_tick)
            & (all_player_hurt_events_df["user_steamid"].astype(str) == str(target_enemy_id))
            & (all_player_hurt_events_df["attacker_steamid"].astype(str) != str(self.player_steamid))
        ]
        return not window.empty

    # ── Episode analysis (extracted sub-methods) ─────────────────────────────

    def _resolve_t0(
        self, moment_info: AnalysisMoment, all_ticks_df: pd.DataFrame,
        all_player_hurt_events_df: pd.DataFrame,
        smoke_events: Optional[pd.DataFrame], tag: str,
        ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
    ) -> Optional[Tuple[int, str]]:
        """Resolve T0 from manual tick or BVH auto-detection. Returns (t0_tick, source) or None."""
        t0_tick: Optional[int] = moment_info.manual_t0_tick_enemy_first_visible
        t0_source = "manual"

        if moment_info.use_auto_t0:
            if self.t0_detector is None:
                self.logger.warning(f"{tag} REJECTED — BVH T0Detector unavailable (missing .tri file).")
                return None

            search_start = moment_info.auto_t0_search_start_tick or 0
            search_end = search_start + moment_info.analysis_window_seconds_after_t0 * self.tickrate

            enemy_steamid_for_bvh = moment_info.target_enemy_steamid_if_known
            if enemy_steamid_for_bvh is None:
                candidate_hits = all_player_hurt_events_df[
                    (all_player_hurt_events_df["tick"] >= search_start)
                    & (all_player_hurt_events_df["tick"] <= search_end)
                    & (all_player_hurt_events_df["attacker_steamid"].astype(str) == str(self.player_steamid))
                ].sort_values("tick")
                if candidate_hits.empty:
                    nearby = all_player_hurt_events_df[
                        (all_player_hurt_events_df["tick"] >= search_start - _ENEMY_DISCOVERY_DIAG_RADIUS)
                        & (all_player_hurt_events_df["tick"] <= search_end + _ENEMY_DISCOVERY_DIAG_RADIUS)
                        & (all_player_hurt_events_df["attacker_steamid"].astype(str) == str(self.player_steamid))
                    ].sort_values("tick")["tick"].astype(int).tolist()
                    self.logger.warning(
                        f"{tag} REJECTED — no hits by player in [{search_start}–{search_end}]. "
                        f"Nearest in ±{_ENEMY_DISCOVERY_DIAG_RADIUS} ticks: {nearby[:6] if nearby else 'none'}"
                    )
                    return None
                candidate_hits = candidate_hits[
                    candidate_hits["user_steamid"].astype(str).str.match(_STEAMID_PATTERN)
                ]
                if candidate_hits.empty:
                    self.logger.warning(f"{tag} REJECTED — all hits in window have null user_steamid.")
                    return None
                enemy_steamid_for_bvh = int(candidate_hits.iloc[0]["user_steamid"])
                self.logger.info(f"{tag} Auto-discovered enemy steamid={enemy_steamid_for_bvh} from first hit.")

            p_count = len(all_ticks_df[
                (all_ticks_df["steamid"] == self.player_steamid)
                & (all_ticks_df["tick"] >= search_start)
                & (all_ticks_df["tick"] <= search_end)
            ])
            e_count = len(all_ticks_df[
                (all_ticks_df["steamid"] == enemy_steamid_for_bvh)
                & (all_ticks_df["tick"] >= search_start)
                & (all_ticks_df["tick"] <= search_end)
            ])
            self.logger.info(
                f"{tag} DIAG BVH window [{search_start}–{search_end}]: "
                f"player_ticks={p_count}, enemy_ticks={e_count} (enemy={enemy_steamid_for_bvh})"
            )

            flash_ivs = T0Detector.parse_flash_intervals(
                self.parser, self.player_steamid, search_start, search_end,
                tickrate=self.tickrate,
            )
            if flash_ivs:
                self.logger.info(f"{tag} Flash intervals in window: {flash_ivs}")

            auto_t0, method = self.t0_detector.find_t0(
                all_ticks_df,
                player_steamid=self.player_steamid,
                enemy_steamid=enemy_steamid_for_bvh,
                search_start_tick=search_start,
                search_end_tick=search_end,
                active_smokes=smoke_events,
                flash_intervals=flash_ivs,
                ticks_by_sid=ticks_by_sid,
            )
            if auto_t0 is not None:
                t0_tick = auto_t0
                t0_source = method
                self.logger.info(f"{tag} Auto T0={t0_tick}, source={t0_source}")
                offset = t0_tick - search_start
                if offset < T0_MIN_OFFSET_TICKS:
                    self.logger.warning(
                        f"{tag} REJECTED — T0 at search_start boundary "
                        f"(offset={offset} ticks < {T0_MIN_OFFSET_TICKS})"
                    )
                    return None
            else:
                self.logger.warning(f"{tag} REJECTED — BVH: {method}")
                return None

        if t0_tick is None:
            self.logger.warning(f"{tag} REJECTED — no T0 available (manual not set, auto disabled).")
            return None

        return (t0_tick, t0_source)

    def _find_t2(
        self, t0_tick: int, window_end_tick: int,
        all_player_hurt_events_df: pd.DataFrame, tag: str,
    ) -> Optional[Tuple[int, str, str]]:
        """Find first hit after T0. Returns (t2_tick, target_enemy_id, hit_weapon) or None."""
        hits_by_player = all_player_hurt_events_df[
            (all_player_hurt_events_df["tick"] >= t0_tick)
            & (all_player_hurt_events_df["tick"] <= window_end_tick)
            & (all_player_hurt_events_df["attacker_steamid"].astype(str) == str(self.player_steamid))
        ].copy()

        if hits_by_player.empty:
            self.logger.warning(
                f"{tag} REJECTED — no hit by player in window [{t0_tick}–{window_end_tick}]."
            )
            return None

        first_hit = hits_by_player.sort_values("tick").iloc[0]
        t2_tick = int(first_hit["tick"])
        target_enemy_id = first_hit["user_steamid"]
        hit_weapon = str(first_hit.get("weapon", "")).lower()
        self.logger.info(f"{tag} T2={t2_tick}, target={target_enemy_id}, weapon={hit_weapon}")

        if hit_weapon in AWP_WEAPON_NAMES:
            self.logger.warning(f"{tag} REJECTED — AWP engagement (weapon={hit_weapon}).")
            return None

        return (t2_tick, str(target_enemy_id), hit_weapon)

    def _compute_velocity(
        self, steamid: int, t0_tick: int, all_ticks_df: pd.DataFrame,
        label: str = "",
    ) -> float:
        """Compute XY velocity at t0_tick for the given steamid. Returns u/s or np.nan."""
        ticks_sorted = all_ticks_df[
            all_ticks_df["steamid"] == steamid
        ].sort_values("tick")
        at_t0 = ticks_sorted[ticks_sorted["tick"] == t0_tick]
        after_t0 = ticks_sorted[ticks_sorted["tick"] > t0_tick]

        if at_t0.empty or after_t0.empty:
            return np.nan

        p0 = at_t0.iloc[0]
        p1 = after_t0.iloc[0]
        dx = float(p1["X"]) - float(p0["X"])
        dy = float(p1["Y"]) - float(p0["Y"])
        return math.sqrt(dx * dx + dy * dy) * self.tickrate

    def _compute_crosshair_angle_at_t0(
        self,
        t0_tick: int,
        enemy_steamid: int,
        all_ticks_df: pd.DataFrame,
    ) -> Optional[float]:
        """
        Angular distance (degrees) between player crosshair and enemy center at T0.

        Eye offsets: player eye = Z + 64, enemy center = Z + 36.
        Returns None if either row missing at t0_tick.
        """
        p_rows = all_ticks_df[
            (all_ticks_df["steamid"] == self.player_steamid)
            & (all_ticks_df["tick"] == t0_tick)
        ]
        e_rows = all_ticks_df[
            (all_ticks_df["steamid"] == enemy_steamid)
            & (all_ticks_df["tick"] == t0_tick)
        ]
        if p_rows.empty or e_rows.empty:
            return None

        p = p_rows.iloc[0]
        e = e_rows.iloc[0]

        px, py, pz = float(p["X"]), float(p["Y"]), float(p["Z"]) + 64.0
        ex, ey, ez = float(e["X"]), float(e["Y"]), float(e["Z"]) + 36.0
        dx, dy, dz = ex - px, ey - py, ez - pz
        if dx == 0.0 and dy == 0.0 and dz == 0.0:
            return None

        des_p, des_y = self.get_desired_angles(px, py, pz, ex, ey, ez)
        d_pitch = self.angular_diff(float(p["pitch"]), des_p)
        d_yaw   = self.angular_diff(float(p["yaw"]),   des_y)
        return round(math.sqrt(d_pitch ** 2 + d_yaw ** 2), 1)

    def _detect_t1(
        self, t0_tick: int, t2_tick: int, target_enemy_id: str,
        all_ticks_df: pd.DataFrame, tag: str,
    ) -> Tuple[int, str]:
        """Detect T1 (reactive aim start). Returns (t1_tick, t1_source).

        t1_source ∈ {"sustained_aim", "pre_aimed", "none"}.

        Pre-aim branch (B-4 fix, 2026-05-16, REVIEW-2026-05-16.md B-4):
        if player crosshair is within T1_NOT_AIMED_THRESHOLD of enemy at T0
        AND remains within it for T1_SUSTAINED_AIM_TICKS ticks → return
        (t0_tick, "pre_aimed"). Perception+motion-planning was complete
        before visibility; rt_visible_to_aim_ms = 0.

        Else fall through to sustained-aim loop (unchanged math). On hit,
        return (potential_t1, "sustained_aim"). On no-detection or empty
        window, return (-1, "none").
        """
        grace_ticks = int(T1_GRACE_MS / (1000 / self.tickrate))
        aim_search_start = t0_tick + grace_ticks

        # B-4 fix (2026-05-16, REVIEW-2026-05-16.md B-4): pre-aimed branch.
        # If player crosshair is already on target at T0 (within
        # T1_NOT_AIMED_THRESHOLD) AND stays there for T1_SUSTAINED_AIM_TICKS
        # ticks, perception+motion-planning was complete before visibility.
        # Set T1=T0, rt_visible_to_aim_ms=0. Else fall through to sustained
        # -aim loop. Without this branch, pre-aimed engagements get NaN'd
        # out (inverse survivorship — see feedback_pre_aim_censorship_
        # inverse_survivorship.md). Source flag persisted via t1_source.
        pre_aim_window = all_ticks_df[
            (all_ticks_df["steamid"] == self.player_steamid)
            & (all_ticks_df["tick"] >= t0_tick)
            & (all_ticks_df["tick"] <= t0_tick + T1_SUSTAINED_AIM_TICKS)
        ].sort_values("tick")
        # Gate requires player row at EVERY tick of [T0, T0+T1_SUSTAINED_AIM_TICKS]
        # — that is T1_SUSTAINED_AIM_TICKS+1 rows (3 with default constant). With
        # only T1_SUSTAINED_AIM_TICKS rows the "sustained for N ticks" predicate
        # cannot be evaluated; fall through to sustained-aim loop. Rule 1 fix on
        # top of plan spec (2026-05-16): plan's `>= T1_SUSTAINED_AIM_TICKS` lets
        # 2-row velocity-seed fixtures spuriously trigger pre_aimed — see
        # feedback_test_fixture_scope_window_mismatch.md.
        if len(pre_aim_window) >= T1_SUSTAINED_AIM_TICKS + 1:
            on_target_all = True
            for _, r in pre_aim_window.head(T1_SUSTAINED_AIM_TICKS + 1).iterrows():
                e_row = all_ticks_df[
                    (all_ticks_df["tick"] == int(r["tick"]))
                    & (all_ticks_df["steamid"] == int(target_enemy_id))
                ]
                if e_row.empty:
                    on_target_all = False
                    break
                e = e_row.iloc[0]
                des_p, des_y = self.get_desired_angles(
                    r["X"], r["Y"], r["Z"],
                    e["X"], e["Y"], e["Z"],
                )
                dist = math.hypot(
                    self.angular_diff(r["yaw"], des_y),
                    self.angular_diff(r["pitch"], des_p),
                )
                if dist > T1_NOT_AIMED_THRESHOLD:
                    on_target_all = False
                    break
            if on_target_all:
                self.logger.info(f"{tag} T1={t0_tick} (pre_aimed)")
                return t0_tick, "pre_aimed"

        player_aim_ticks = all_ticks_df[
            (all_ticks_df["steamid"] == self.player_steamid)
            & (all_ticks_df["tick"] >= aim_search_start)
            & (all_ticks_df["tick"] < t2_tick)
        ].copy()

        if len(player_aim_ticks) < 2:
            self.logger.warning(f"{tag} T1 not found — no sustained aiming detected.")
            return -1, "none"

        consecutive = 0
        potential_t1 = -1
        for i in range(len(player_aim_ticks) - 1):
            curr = player_aim_ticks.iloc[i]
            nxt = player_aim_ticks.iloc[i + 1]

            enemy_at_tick = all_ticks_df[
                (all_ticks_df["tick"] == curr["tick"])
                & (all_ticks_df["steamid"] == int(target_enemy_id))
            ]
            if enemy_at_tick.empty:
                consecutive = 0
                continue

            e = enemy_at_tick.iloc[0]
            des_p, des_y = self.get_desired_angles(
                curr["X"], curr["Y"], curr["Z"],
                e["X"], e["Y"], e["Z"],
            )

            d_yaw   = abs(self.angular_diff(curr["yaw"], nxt["yaw"]))
            d_pitch = abs(self.angular_diff(curr["pitch"], nxt["pitch"]))
            sig_change = d_yaw > T1_MIN_ANGLE_CHANGE or d_pitch > T1_MIN_ANGLE_CHANGE

            curr_dist = math.hypot(
                self.angular_diff(curr["yaw"], des_y),
                self.angular_diff(curr["pitch"], des_p),
            )
            nxt_dist = math.hypot(
                self.angular_diff(nxt["yaw"], des_y),
                self.angular_diff(nxt["pitch"], des_p),
            )
            moving_towards = nxt_dist < (curr_dist - T1_MOVING_TOWARDS_TOLERANCE)

            if sig_change and moving_towards and curr_dist > T1_NOT_AIMED_THRESHOLD:
                if consecutive == 0:
                    potential_t1 = int(nxt["tick"])
                consecutive += 1
            else:
                consecutive = 0
                potential_t1 = -1

            if self.debug_prints:
                self.logger.debug(
                    f"  Tick {int(curr['tick'])}: dYaw={d_yaw:.4f} dPitch={d_pitch:.4f} "
                    f"sig={sig_change} towards={moving_towards} dist={curr_dist:.2f}"
                )

            if consecutive >= T1_SUSTAINED_AIM_TICKS:
                self.logger.info(f"{tag} T1={potential_t1} (after {consecutive} aim ticks)")
                return potential_t1, "sustained_aim"

        self.logger.warning(f"{tag} T1 not found — no sustained aiming detected.")
        return -1, "none"

    def _classify_engagement(self, velocity_ups: float) -> str:
        """Return 'peek' or 'hold' based on player velocity at T0."""
        if not math.isnan(velocity_ups) and velocity_ups >= self.player_velocity_threshold:
            return "peek"
        return "hold"

    def _compute_round_phase(
        self, t0_tick: int, round_start_ticks: Optional[List[int]], tag: str,
        round_freeze_end_ticks: Optional[List[int]] = None,
    ) -> Tuple[Optional[float], Optional[str], Optional[int]]:
        """Return (round_time_s, round_phase, round_number) for the given T0 tick.

        round_number uses ``round_start_ticks`` (freeze BEGIN — round
        boundary). round_time_s anchors on ``round_freeze_end_ticks`` when
        provided so it measures **gameplay time** (excludes the 20s buy
        phase). Without freeze_end fallback, the value mistakenly includes
        freeze duration — bug surfaced 2026-05-14 via donk groundtruth check
        (engagement at "round_time_s=48.77" actually occurred at in-game
        timer 1:26, not 1:07).

        Branches (preserve existing semantics; do NOT collapse warmup to None
        round_phase — phase chart relies on the literal "unknown" tag):

        - empty/None ``round_start_ticks`` → ``(None, None, None)``
        - ``t0`` precedes first round_start (warmup) → ``(None, "unknown", None)``
        - otherwise → 1-indexed round_number alongside time/phase
        """
        if not round_start_ticks:
            return None, None, None
        idx = bisect.bisect_right(round_start_ticks, t0_tick) - 1
        if idx >= 0:
            ms_per_tick = 1000 / self.tickrate
            # Prefer round_freeze_end as gameplay-start anchor. Match by bisect
            # so non-aligned counts (e.g., demos with mismatched event totals)
            # still pair correctly to the round in question.
            anchor_tick = round_start_ticks[idx]
            if round_freeze_end_ticks:
                fe_idx = bisect.bisect_right(round_freeze_end_ticks, t0_tick) - 1
                if (
                    fe_idx >= 0
                    and round_freeze_end_ticks[fe_idx] >= round_start_ticks[idx]
                ):
                    anchor_tick = round_freeze_end_ticks[fe_idx]
            round_time_s = round((t0_tick - anchor_tick) * ms_per_tick / 1000, 2)
            # Guard: if t0 falls inside the freeze window (between round_start
            # and round_freeze_end), round_time_s would be negative. Clamp to
            # 0 so downstream phase classification stays sane.
            if round_time_s < 0:
                round_time_s = 0.0
            if round_time_s < _ROUND_EARLY_MAX_S:
                round_phase = "early"
            elif round_time_s < _ROUND_MID_MAX_S:
                round_phase = "mid"
            else:
                round_phase = "late"
            round_number = idx + 1  # 1-indexed
            return round_time_s, round_phase, round_number
        self.logger.warning(
            f"{tag} T0 tick {t0_tick} precedes first round_start event — "
            f"round_phase='unknown', engagement excluded from phase chart"
        )
        return None, "unknown", None

    # ── Episode analysis (orchestrator) ────────────────────────────────────────

    def analyze_engagement_episode(
        self,
        moment_info: AnalysisMoment,
        all_ticks_df: pd.DataFrame,
        player_fire_events_df: pd.DataFrame,
        all_player_hurt_events_df: pd.DataFrame,
        round_start_ticks: Optional[List[int]] = None,
        smoke_events: Optional[pd.DataFrame] = None,
        ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
        round_freeze_end_ticks: Optional[List[int]] = None,
        player_death_ticks: Optional[List[int]] = None,
    ) -> Optional[Dict]:
        tag = f"[{moment_info.timestamp}]"
        self.logger.info(f"{tag} Starting — {moment_info.description}")

        result = self._resolve_t0(
            moment_info, all_ticks_df, all_player_hurt_events_df, smoke_events, tag,
            ticks_by_sid=ticks_by_sid,
        )
        if result is None:
            return None
        t0_tick, t0_source = result

        # Bug C gate (2026-05-14): reject engagements where the player was
        # already dead at T0. T0Detector iterates BVH visibility for the
        # player_steamid even after their death tick (corpse / spectator
        # frames persist in tick data), fabricating phantom engagements.
        # Compare t0_tick against the most recent player_death within the
        # round: if a death precedes t0 inside the round window, skip.
        if player_death_ticks and round_start_ticks:
            r_idx = bisect.bisect_right(round_start_ticks, t0_tick) - 1
            if r_idx >= 0:
                round_lo = round_start_ticks[r_idx]
                round_hi = (
                    round_start_ticks[r_idx + 1]
                    if r_idx + 1 < len(round_start_ticks)
                    else 10**12
                )
                for d_tick in player_death_ticks:
                    if round_lo <= d_tick < round_hi and d_tick < t0_tick:
                        self.logger.warning(
                            f"{tag} REJECTED — player died at tick {d_tick} "
                            f"before T0 {t0_tick} in same round "
                            f"(phantom-after-death gate)"
                        )
                        return None

        # Cap window at T0_TO_T2_MAX_TICKS (1.5s) to prevent cluster bleed:
        # auto_build_moments groups events 5s apart; without this cap, T2 can
        # capture a hit from a separate firefight on the same target.
        window_end_tick = min(
            t0_tick + moment_info.analysis_window_seconds_after_t0 * self.tickrate,
            t0_tick + T0_TO_T2_MAX_TICKS,
        )

        t2 = self._find_t2(t0_tick, window_end_tick, all_player_hurt_events_df, tag)
        if t2 is None:
            return None
        t2_tick, target_enemy_id, hit_weapon = t2

        try:
            enemy_sid_int = int(target_enemy_id)
        except (ValueError, TypeError):
            enemy_sid_int = None
        crosshair_angle = (
            self._compute_crosshair_angle_at_t0(t0_tick, enemy_sid_int, all_ticks_df)
            if enemy_sid_int is not None
            else None
        )

        is_clean, reason = self.is_1v1_duel(all_player_hurt_events_df, t0_tick, t2_tick, target_enemy_id)
        if not is_clean:
            self.logger.warning(f"{tag} REJECTED — not a clean 1v1: {reason}")
            return None

        # Teammate gate (D-09): reject if phantom kill detected
        if self._teammate_hurt_target(all_player_hurt_events_df, t0_tick, t2_tick, target_enemy_id):
            self.logger.warning(f"{tag} REJECTED — teammate phantom kill detected in [T0..T2]")
            return None

        enemy_vel = self._compute_velocity(int(target_enemy_id), t0_tick, all_ticks_df)
        self.logger.info(f"{tag} enemy velocity@T0={enemy_vel:.1f} u/s")
        if not math.isnan(enemy_vel) and enemy_vel >= self.enemy_velocity_threshold:
            self.logger.warning(
                f"{tag} REJECTED — enemy also moving at T0: {enemy_vel:.1f} u/s "
                f"(threshold={self.enemy_velocity_threshold} u/s)"
            )
            return None

        t1_tick, t1_source = self._detect_t1(t0_tick, t2_tick, target_enemy_id, all_ticks_df, tag)
        player_vel = self._compute_velocity(self.player_steamid, t0_tick, all_ticks_df)
        self.logger.info(f"{tag} velocity@T0={player_vel:.1f} u/s → {self._classify_engagement(player_vel)}")
        engagement_type = self._classify_engagement(player_vel)
        # TODO Bug B (2026-05-14): peek/hold rule keys on player_velocity only.
        # Strafe-hold (player moving fast but holding angle, e.g. side-to-side
        # micro-movement) gets mis-classified as peek. Needs position-stability
        # detector or enemy-velocity cross-check. Defer to next pass.
        round_time_s, round_phase, round_number = self._compute_round_phase(
            t0_tick, round_start_ticks, tag,
            round_freeze_end_ticks=round_freeze_end_ticks,
        )
        self.logger.info(
            f"{tag} round_time_s={round_time_s}, round_phase={round_phase}, "
            f"round_number={round_number}"
        )

        # ── Compute intervals ─────────────────────────────────────────────────
        ms = 1000 / self.tickrate

        rt_t0_t1 = (
            max(0.0, (t1_tick - t0_tick) * ms)
            if t1_tick != -1
            else np.nan
        )
        rt_t1_t2 = np.nan
        if t1_tick != -1 and t2_tick >= t1_tick:
            rt_t1_t2 = (t2_tick - t1_tick) * ms
        rt_t0_t2 = (
            (t2_tick - t0_tick) * ms
            if t2_tick >= t0_tick
            else np.nan
        )

        # Bug A gate (2026-05-14): T0→T2 ≤ 2 ticks (≤31ms) is below human
        # reaction floor (~150ms minimum). These are prefire artifacts where
        # T0 fired the moment a smoke cleared on an enemy who was already
        # being shot at — bullets in flight produce T2 the next tick.
        # BVH+AABB does NOT include smoke geometry (CLAUDE.md known limit),
        # so we filter at engagement-extraction time.
        if t2_tick - t0_tick <= 2:
            self.logger.warning(
                f"{tag} REJECTED — T0→T2={t2_tick - t0_tick} ticks "
                f"(≤2 = prefire artifact, below human reaction floor)"
            )
            return None

        self.logger.info(
            f"{tag} ACCEPTED — T0→T1={rt_t0_t1:.1f}ms  "
            f"T1→T2={rt_t1_t2:.1f}ms  T0→T2={rt_t0_t2:.1f}ms"
        )

        return {
            "match_id": self.match_id,
            "player_steamid": self.player_steamid,  # D-05: Path 1 schema
            "map_name": self.map_name,
            "moment_timestamp": moment_info.timestamp,
            "description": moment_info.description,
            "t0_source": t0_source,
            "t0_manual_tick": int(t0_tick),
            "t1_aim_start_tick": int(t1_tick) if t1_tick != -1 else np.nan,
            "t2_first_hit_tick": int(t2_tick),
            "rt_visible_to_aim_ms": rt_t0_t1,
            "rt_aim_to_hit_ms": rt_t1_t2,
            "rt_visible_to_hit_ms": rt_t0_t2,
            "target_enemy_id": str(target_enemy_id),
            "player_velocity_at_t0_ups": round(player_vel, 1) if not math.isnan(player_vel) else np.nan,
            "enemy_velocity_at_t0_ups": round(enemy_vel, 1) if not math.isnan(enemy_vel) else np.nan,
            "engagement_type": engagement_type,
            "crosshair_angle_at_t0_deg": crosshair_angle,
            "round_time_s": round_time_s,
            "round_phase": round_phase,
            # D-01: 1-indexed round_number for narrative attribution (Phase v2).
            "round_number": round_number,
            # Phase 10 (B-4 fix, 2026-05-16): T1 detection branch label.
            # ∈ {"sustained_aim", "pre_aimed", "none"}. NULL on legacy
            # (pre-Phase-10) rows when re-read from DB without re-batch.
            "t1_source": t1_source,
        }

    # ── Selective parse_ticks helpers (Phase 9.1 SC3) ─────────────────────────

    def _build_tick_window_union(self, anchor_ticks: List[int]) -> List[int]:
        """Vectorized union of tick windows around player_hurt anchors.

        Empty input returns []. Caller MUST guard on len() before passing
        to parse_ticks (Pitfall #1: ticks=[] silently triggers full parse).
        """
        if not anchor_ticks:
            return []
        arrs = [
            np.arange(
                t - _SELECTIVE_WINDOW_BEFORE_TICKS,
                t + _SELECTIVE_WINDOW_AFTER_TICKS,
                dtype=np.int32,
            )
            for t in anchor_ticks
        ]
        union = np.unique(np.concatenate(arrs))
        union = union[union >= 0]
        return union.tolist()

    def _parse_ticks_maybe_selective(self, props, anchor_ticks):
        """Selective parse_ticks if flag enabled AND anchors present AND window non-empty.

        Pitfall #1: ticks=[] silently triggers full parse — guard explicitly
        with `len(window) > 0` before passing the kwarg.
        """
        if (
            config.PARSE_TICKS_SELECTIVE
            and anchor_ticks is not None
            and len(anchor_ticks) > 0
        ):
            window = self._build_tick_window_union(anchor_ticks)
            if len(window) > 0:
                return pd.DataFrame(self.parser.parse_ticks(props, ticks=window))
        return pd.DataFrame(self.parser.parse_ticks(props))

    # ── Demo-level processing ─────────────────────────────────────────────────

    def analyze_demo(
        self,
        bulk_mode: bool = False,
        profile: bool = False,
        attempts_mode: bool = False,
    ) -> Tuple[pd.DataFrame, List[DuelAttempt]]:
        if profile:
            tracemalloc.start()
            _t_start = time.perf_counter()
            if _PSUTIL_AVAILABLE:
                _proc = _psutil.Process(os.getpid())
                _ram_before = _proc.memory_info().rss

        self.logger.info(f"=== Parsing: {os.path.basename(self.demo_path)} (match_id={self.match_id}) ===")

        # Phase 9.1 SC2: single batched parse_events([...]) call replaces 4 separate
        # parse_event() invocations. Pitfall #2 mitigation: convert list-of-tuples to
        # a name-keyed dict via dict(by_name) BEFORE any access — order is not guaranteed.
        # Pitfall #6 mitigation: weapon_fire `player=` arg is broken-ish on parse_events,
        # so per-player filtering stays in Python post-parse.
        # Phase 9.1 SC3: events parsed BEFORE parse_ticks so player_hurt anchors can drive
        # selective tick windowing via _parse_ticks_maybe_selective.
        events_to_parse: List[str] = ["player_hurt", "player_death", "weapon_fire", "round_start", "round_freeze_end"]
        try:
            raw_events = self.parser.parse_events(events_to_parse)
            by_name: Dict[str, pd.DataFrame] = {
                name: (df if isinstance(df, pd.DataFrame) else pd.DataFrame(df or []))
                for name, df in raw_events
            }
        except Exception as e:
            self.logger.warning(f"parse_events batch failed, falling back to empty event frames: {e}")
            by_name = {}

        all_hurt_df = by_name.get(
            "player_hurt", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
        )
        all_death_df = by_name.get(
            "player_death", pd.DataFrame(columns=["tick", "attacker_steamid", "user_steamid"])
        )
        fire_df_all = by_name.get("weapon_fire", pd.DataFrame(columns=["tick"]))
        rs_df = by_name.get("round_start", pd.DataFrame(columns=["tick"]))

        # Per-player filtering of weapon_fire (post-parse — see Pitfall #6).
        if not fire_df_all.empty and "user_steamid" in fire_df_all.columns:
            player_fire_df = fire_df_all[
                fire_df_all["user_steamid"].astype(str) == str(self.player_steamid)
            ]
        else:
            player_fire_df = pd.DataFrame(columns=["tick"])

        if not all_hurt_df.empty and "tick" in all_hurt_df.columns:
            all_hurt_df["tick"] = pd.to_numeric(all_hurt_df["tick"], errors="coerce")
            for col in ("attacker_steamid", "user_steamid"):
                if col in all_hurt_df.columns:
                    all_hurt_df[col] = all_hurt_df[col].astype(str)
        self.logger.info(f"Parsed {len(all_hurt_df):,} player_hurt events.")

        # Phase 9.1 SC3: anchor ticks for selective parse_ticks. Filter to hits where
        # the player was the attacker — those are the engagement neighborhoods worth
        # parsing tick-level state for. Empty list → wrapper falls back to full parse.
        if (
            not all_hurt_df.empty
            and "attacker_steamid" in all_hurt_df.columns
            and "tick" in all_hurt_df.columns
        ):
            hurt_ticks: List[int] = (
                all_hurt_df.loc[
                    all_hurt_df["attacker_steamid"].astype(str) == str(self.player_steamid),
                    "tick",
                ]
                .dropna()
                .astype(int)
                .tolist()
            )
        else:
            hurt_ticks = []

        all_props = self._TICKS_REQUIRED + self._TICKS_OPTIONAL
        try:
            all_ticks_df = self._parse_ticks_maybe_selective(all_props, anchor_ticks=hurt_ticks)
        except Exception as e:
            self.logger.warning(f"Optional tick props unavailable, falling back to required only: {e}")
            all_ticks_df = self._parse_ticks_maybe_selective(self._TICKS_REQUIRED, anchor_ticks=hurt_ticks)

        all_ticks_df["steamid"] = pd.to_numeric(all_ticks_df["steamid"], errors="coerce")
        all_ticks_df.dropna(subset=["steamid"], inplace=True)
        all_ticks_df["steamid"] = all_ticks_df["steamid"].astype(np.int64)
        self.logger.info(f"Parsed {len(all_ticks_df):,} tick rows.")

        # Phase 9.1 SC4: per-steamid frame cache. Built once after coercion;
        # threaded through analyze_engagement_episode → find_t0 to avoid
        # repeated bool-filter scans of the full all_ticks_df. groupby with
        # sort=False is required for measured 3.23x speedup over 30 engagements
        # (D-04). Cached frames must NOT be mutated by callees.
        ticks_by_sid: Dict[int, pd.DataFrame] = {
            int(sid): g.sort_values("tick")
            for sid, g in all_ticks_df.groupby("steamid", sort=False)
        }

        if not all_death_df.empty and "tick" in all_death_df.columns:
            all_death_df["tick"] = pd.to_numeric(all_death_df["tick"], errors="coerce")
            for col in ("attacker_steamid", "user_steamid"):
                if col in all_death_df.columns:
                    all_death_df[col] = all_death_df[col].astype(str)
        self.logger.info(f"Parsed {len(all_death_df):,} player_death events.")

        self.logger.info(f"DIAG player_hurt columns: {list(all_hurt_df.columns)}")
        if not all_hurt_df.empty and "attacker_steamid" in all_hurt_df.columns:
            sample_attackers = all_hurt_df["attacker_steamid"].unique()[:5].tolist()
            self.logger.info(f"DIAG sample attacker_steamid values (raw): {sample_attackers}")
            donk_hits = all_hurt_df[
                all_hurt_df["attacker_steamid"].astype(str) == str(self.player_steamid)
            ]
            if donk_hits.empty:
                self.logger.warning(
                    f"DIAG player steamid={self.player_steamid} NOT FOUND in attacker_steamid. "
                    f"Check format mismatch above."
                )
            else:
                hit_ticks = sorted(donk_hits["tick"].astype(int).tolist())
                self.logger.info(
                    f"DIAG player has {len(donk_hits)} hits total, "
                    f"tick range: {hit_ticks[0]}–{hit_ticks[-1]}"
                )
                self.logger.info(f"DIAG all hit ticks: {hit_ticks}")

        smoke_events = T0Detector.parse_smoke_events(self.parser, tickrate=self.tickrate)
        self.logger.info(f"Parsed {len(smoke_events)} smoke intervals.")

        # round_start ticks already extracted from the batched parse_events above.
        try:
            round_start_ticks: List[int] = sorted(
                pd.to_numeric(rs_df["tick"], errors="coerce").dropna().astype(int).tolist()
            ) if not rs_df.empty and "tick" in rs_df.columns else []
        except Exception:
            round_start_ticks = []
        self.logger.info(f"Parsed {len(round_start_ticks)} round_start ticks.")

        # round_freeze_end ticks — true gameplay-start anchor for round_time_s.
        # Discovered 2026-05-14 via donk groundtruth: round_start fires at freeze
        # BEGIN (includes 20s buy phase); using it for time-anchor overcounts
        # round_time_s by ~20s and mis-classifies round_phase. round_freeze_end
        # is the action-start tick; match it to round_start[idx] by bisect.
        rfe_df = by_name.get("round_freeze_end", pd.DataFrame(columns=["tick"]))
        try:
            round_freeze_end_ticks: List[int] = sorted(
                pd.to_numeric(rfe_df["tick"], errors="coerce").dropna().astype(int).tolist()
            ) if not rfe_df.empty and "tick" in rfe_df.columns else []
        except Exception:
            round_freeze_end_ticks = []
        self.logger.info(f"Parsed {len(round_freeze_end_ticks)} round_freeze_end ticks.")

        # Player death ticks — Bug C gate (2026-05-14): T0Detector currently
        # fabricates visibility events for dead players (corpse/spectator
        # frames), producing phantom engagements after death. Reject any
        # engagement whose t0_tick > player's death_tick within the same round.
        if not all_death_df.empty and "user_steamid" in all_death_df.columns:
            player_death_ticks: List[int] = sorted(
                all_death_df.loc[
                    all_death_df["user_steamid"].astype(str) == str(self.player_steamid),
                    "tick",
                ].dropna().astype(int).tolist()
            )
        else:
            player_death_ticks = []
        self.logger.info(f"Player has {len(player_death_ticks)} deaths in demo.")

        if bulk_mode:
            n = self.auto_build_moments(all_hurt_df)
            self.logger.info(f"Bulk mode: {n} engagement moments generated.")
            if n == 0:
                return pd.DataFrame(), []

        results = []
        for moment in self.analysis_moments:
            result = self.analyze_engagement_episode(
                moment, all_ticks_df, player_fire_df, all_hurt_df,
                round_start_ticks, smoke_events=smoke_events,
                ticks_by_sid=ticks_by_sid,
                round_freeze_end_ticks=round_freeze_end_ticks,
                player_death_ticks=player_death_ticks,
            )
            if result:
                first_hit = result.get("t2_first_hit_tick")
                if (
                    self.last_accepted_t2_tick is not None
                    and isinstance(first_hit, (int, float))
                    and not math.isnan(float(first_hit))
                    and int(first_hit) < self.last_accepted_t2_tick + 300
                ):
                    self.logger.warning(
                        f"Overlapping window rejected: first_hit={first_hit} < "
                        f"last_accepted_t2={self.last_accepted_t2_tick} + 300"
                    )
                else:
                    results.append(result)
                    if isinstance(first_hit, (int, float)) and not math.isnan(float(first_hit)):
                        self.last_accepted_t2_tick = int(first_hit)

        # Dedup: two moments that resolved to the same T0 tick are the same engagement
        seen_t0: set[int] = set()
        deduped = []
        for r in results:
            t0 = r["t0_manual_tick"]
            if t0 not in seen_t0:
                seen_t0.add(t0)
                deduped.append(r)
            else:
                self.logger.warning(
                    f"DEDUP: dropped duplicate T0={t0} "
                    f"(moment {r['moment_timestamp']} — same engagement as earlier result)"
                )
        if len(deduped) < len(results):
            self.logger.info(f"Dedup removed {len(results) - len(deduped)} duplicate(s).")
        results = deduped

        accepted = len(results)
        total = len(self.analysis_moments)
        self.logger.info(f"Done: {accepted}/{total} moments accepted.")
        print(f"\nAccepted {accepted}/{total} moments.")

        if profile:
            wall_s = time.perf_counter() - _t_start
            _, peak_bytes = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            demo_mb = os.path.getsize(self.demo_path) / 1024 / 1024
            print("\n-- Profile Summary ----------------------------------")
            print(f"  Demo file size : {demo_mb:.1f} MB")
            print(f"  Wall time      : {wall_s:.1f}s")
            print(f"  Peak RAM (py)  : {peak_bytes / 1024 / 1024:.1f} MB  (tracemalloc)")
            if _PSUTIL_AVAILABLE:
                rss_now = _proc.memory_info().rss
                print(f"  RSS delta      : {(rss_now - _ram_before) / 1024 / 1024:+.1f} MB  (psutil)")
                print(f"  RSS total      : {rss_now / 1024 / 1024:.1f} MB")
            else:
                print("  RSS            : install psutil for OS-level RAM stats")
            print("-----------------------------------------------------\n")

        attempts: List[DuelAttempt] = []
        if attempts_mode:
            attempts = self.find_all_duel_attempts(
                player_fire_df=player_fire_df,
                all_ticks_df=all_ticks_df,
                all_hurt_df=all_hurt_df,
                all_death_df=all_death_df,
                active_smokes=smoke_events,
            )

        results_df = pd.DataFrame(results)
        if not results_df.empty:
            results_df["demo_name"] = self.demo_name
        db_utils.save_to_db(results_df, DB_PATH, "engagements", self.match_id)
        return results_df, attempts
