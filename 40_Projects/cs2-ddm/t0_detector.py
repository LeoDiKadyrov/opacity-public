"""
T0Detector — geometric visibility-based T0 detection for DDM reaction analysis.

Architecture (per research directive):
  - demoparser2  : state/kinematics extraction (done in ddm_analyzer.py)
  - awpy BVH     : Möller-Trumbore ray-triangle LOS verification (this module)

Usage:
    detector = T0Detector(map_name="de_ancient")
    t0_tick, method = detector.find_t0(
        all_ticks_df, player_steamid, enemy_steamid,
        search_start_tick, search_end_tick,
        active_smokes=smoke_events_df,     # optional
        flash_intervals=None,              # optional: list of (start_tick, end_tick)
    )
"""

from __future__ import annotations

import math
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from awpy.data import TRIS_DIR
from awpy.visibility import VisibilityChecker

logger = logging.getLogger("DDM.T0Detector")

# ── CS2 collision hull constants (Source units) ──────────────────────────────
_EYE_HEIGHT_STANDING  = 64.0   # Z offset from entity origin to eye level
_EYE_HEIGHT_CROUCHING = 46.0
_HULL_HALF_WIDTH      = 16.0   # ± X and Y from entity origin (32u wide hull)
_HULL_HEIGHT_STANDING  = 72.0
_HULL_HEIGHT_CROUCHING = 54.0
_SMOKE_RADIUS_UNITS   = 144.0  # CS2 smoke grenade visual radius in world units

_SMOKE_FALLBACK_DURATION_S: int = 18   # seconds used when no expired event matched
_SMOKE_POSITION_MATCH_RADIUS: float = 50.0  # max XY distance to pair detonate→expire

# 8 corners of the AABB relative to the entity origin, as (dx, dy, dz_frac)
# dz_frac is a fraction of total hull height: 0=feet, 0.5=center, 1.0=top
_AABB_OFFSETS: List[Tuple[float, float, float]] = [
    (0.0,               0.0,               0.5),   # center mass — most-likely-visible, check first
    (-_HULL_HALF_WIDTH, -_HULL_HALF_WIDTH, 0.2),   # lower corners
    ( _HULL_HALF_WIDTH, -_HULL_HALF_WIDTH, 0.2),
    (-_HULL_HALF_WIDTH,  _HULL_HALF_WIDTH, 0.2),
    ( _HULL_HALF_WIDTH,  _HULL_HALF_WIDTH, 0.2),
    (-_HULL_HALF_WIDTH, -_HULL_HALF_WIDTH, 0.8),   # upper corners
    ( _HULL_HALF_WIDTH, -_HULL_HALF_WIDTH, 0.8),
    (-_HULL_HALF_WIDTH,  _HULL_HALF_WIDTH, 0.8),
    ( _HULL_HALF_WIDTH,  _HULL_HALF_WIDTH, 0.8),
]


def _find_column(df: pd.DataFrame, *candidates: str) -> Optional[str]:
    """Return the first column name from *candidates* that exists in *df*."""
    for c in candidates:
        if c in df.columns:
            return c
    return None


class T0Detector:
    """
    Geometric T0 detector using awpy BVH ray-triangle intersection testing.

    One instance per map (the BVH tree is built once from the .tri file and
    reused across all episodes in a demo).
    """

    def __init__(self, map_name: str):
        tri_path = Path(TRIS_DIR) / f"{map_name}.tri"
        if not tri_path.exists():
            raise FileNotFoundError(
                f"Missing .tri file for map '{map_name}': {tri_path}\n"
                f"Run: from awpy.cli import awpy_cli; awpy_cli(['get','tris'])"
            )
        logger.info(f"Loading BVH from {tri_path} ...")
        self.checker = VisibilityChecker(path=tri_path)
        self.map_name = map_name
        logger.info("BVH ready.")

    # ── Public API ────────────────────────────────────────────────────────────

    def find_t0(
        self,
        all_ticks_df: pd.DataFrame,
        player_steamid: int,
        enemy_steamid: int,
        search_start_tick: int,
        search_end_tick: int,
        active_smokes: Optional[pd.DataFrame] = None,
        flash_intervals: Optional[List[Tuple[int, int]]] = None,
        ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
    ) -> Tuple[Optional[int], str]:
        """
        Scan [search_start_tick, search_end_tick] and return the first tick
        where any ray from the player's eye to the enemy's AABB corners clears
        the map geometry (no wall intersection).

        Smoke volumes and flash blindness suppress the result even when the
        geometry is clear.

        Phase 9.1 SC4: when ``ticks_by_sid`` is supplied, per-steamid frames
        are looked up from the cache and only the tick-range filter is
        applied. When the kwarg is None or the sid is missing from the cache
        the original bool-filter path on ``all_ticks_df`` is used (D-04
        zero-regression contract).

        Returns:
            (t0_tick, method_string) or (None, "not_found")
        """
        if ticks_by_sid is not None and player_steamid in ticks_by_sid:
            p_cached = ticks_by_sid[player_steamid]
            p_df = p_cached[
                (p_cached["tick"] >= search_start_tick)
                & (p_cached["tick"] <= search_end_tick)
            ]
        else:
            p_df = all_ticks_df[
                (all_ticks_df["steamid"] == player_steamid)
                & (all_ticks_df["tick"] >= search_start_tick)
                & (all_ticks_df["tick"] <= search_end_tick)
            ].sort_values("tick")

        if ticks_by_sid is not None and enemy_steamid in ticks_by_sid:
            e_cached = ticks_by_sid[enemy_steamid]
            e_df = e_cached[
                (e_cached["tick"] >= search_start_tick)
                & (e_cached["tick"] <= search_end_tick)
            ].set_index("tick")
        else:
            e_df = all_ticks_df[
                (all_ticks_df["steamid"] == enemy_steamid)
                & (all_ticks_df["tick"] >= search_start_tick)
                & (all_ticks_df["tick"] <= search_end_tick)
            ].set_index("tick")

        if p_df.empty or e_df.empty:
            return None, "not_found"

        smoke_blocked_ticks = 0
        vis_failed_ticks = 0
        no_match_ticks = 0
        flash_skipped_ticks = 0

        for p_row in p_df.itertuples():
            tick = int(p_row.tick)

            # Skip if player is actively flash-blinded at this tick
            if flash_intervals and any(f0 <= tick <= f1 for f0, f1 in flash_intervals):
                flash_skipped_ticks += 1
                continue

            if tick not in e_df.index:
                no_match_ticks += 1
                continue

            e_row = e_df.loc[tick]
            # handle duplicate index entries (take first)
            if isinstance(e_row, pd.DataFrame):
                e_row = e_row.iloc[0]

            eye = (
                float(p_row.X),
                float(p_row.Y),
                float(p_row.Z) + _EYE_HEIGHT_STANDING,
            )

            is_crouching = float(e_row.get("duck_amount", 0)) > 0.5
            e_hull_h = _HULL_HEIGHT_CROUCHING if is_crouching else _HULL_HEIGHT_STANDING
            ex, ey, ez = float(e_row["X"]), float(e_row["Y"]), float(e_row["Z"])

            # Build all AABB target points
            targets = [
                (ex + dx, ey + dy, ez + dz * e_hull_h)
                for dx, dy, dz in _AABB_OFFSETS
            ]

            # Check each ray; categorise failure reason per tick
            tick_any_unsmoked = False
            for target in targets:
                if not self._is_smoke_obscured(eye, target, tick, active_smokes):
                    tick_any_unsmoked = True
                    if self.checker.is_visible(eye, target):
                        logger.debug(f"T0 found at tick {tick} (target={target}, method=BVH+AABB)")
                        return tick, "BVH+AABB"

            if tick_any_unsmoked:
                vis_failed_ticks += 1
            else:
                smoke_blocked_ticks += 1

        diag = (
            f"not_found("
            f"p={len(p_df)},e={len(e_df)},"
            f"no_match={no_match_ticks},"
            f"flash_skip={flash_skipped_ticks},"
            f"smoke_blocked={smoke_blocked_ticks},"
            f"vis_failed={vis_failed_ticks})"
        )
        return None, diag

    # ── Visible enemies at tick ────────────────────────────────────────────────

    def find_visible_enemies_at_tick(
        self,
        all_ticks_df: pd.DataFrame,
        player_steamid: int,
        tick: int,
        active_smokes: Optional[pd.DataFrame] = None,
    ) -> List[Tuple[int, float]]:
        """
        Return all enemies visible to player at tick as [(steamid, crosshair_angle_deg)].

        Same-team players and dead players are excluded.
        Smoke volumes suppress via _is_smoke_obscured.
        Returns [] if player has no data at tick or no candidate enemies exist.
        """
        p_at_tick = all_ticks_df[
            (all_ticks_df["steamid"] == player_steamid) & (all_ticks_df["tick"] == tick)
        ]
        if p_at_tick.empty:
            return []
        p_row = p_at_tick.iloc[0]

        player_team = int(p_row["team_num"]) if "team_num" in all_ticks_df.columns else -1
        eye = (
            float(p_row["X"]),
            float(p_row["Y"]),
            float(p_row["Z"]) + _EYE_HEIGHT_STANDING,
        )
        player_yaw_rad = math.radians(float(p_row["yaw"]))
        player_pitch_rad = math.radians(float(p_row["pitch"]))

        others = all_ticks_df[
            (all_ticks_df["steamid"] != player_steamid) & (all_ticks_df["tick"] == tick)
        ]
        if others.empty:
            return []

        visible: List[Tuple[int, float]] = []

        for _, e_row in others.iterrows():
            # Skip same team
            if "team_num" in others.columns:
                e_team = e_row["team_num"]
                if player_team != -1 and not (isinstance(e_team, float) and math.isnan(e_team)) and int(e_team) == player_team:
                    continue
            # Skip dead
            if "is_alive" in others.columns and not bool(e_row["is_alive"]):
                continue

            ex, ey, ez = float(e_row["X"]), float(e_row["Y"]), float(e_row["Z"])
            is_crouching = float(e_row.get("duck_amount", 0)) > 0.5
            e_hull_h = _HULL_HEIGHT_CROUCHING if is_crouching else _HULL_HEIGHT_STANDING

            targets = [
                (ex + dx, ey + dy, ez + dz * e_hull_h)
                for dx, dy, dz in _AABB_OFFSETS
            ]

            # Smoke suppression using existing method
            if self._is_smoke_obscured(eye, (ex, ey, ez + e_hull_h * 0.5), tick, active_smokes):
                continue

            # BVH: visible if any AABB corner ray clears geometry
            if not any(self.checker.is_visible(eye, t) for t in targets):
                continue

            # Crosshair angle to enemy center
            dx_e = ex - eye[0]
            dy_e = ey - eye[1]
            dz_e = (ez + e_hull_h * 0.5) - eye[2]
            h_dist = math.sqrt(dx_e * dx_e + dy_e * dy_e)
            desired_yaw_rad = math.atan2(dy_e, dx_e)
            desired_pitch_rad = -math.atan2(dz_e, max(h_dist, 1e-6))

            delta_yaw = math.degrees(desired_yaw_rad - player_yaw_rad)
            delta_yaw = (delta_yaw + 180) % 360 - 180
            delta_pitch = math.degrees(desired_pitch_rad - player_pitch_rad)
            crosshair_angle = math.sqrt(delta_yaw**2 + delta_pitch**2)

            visible.append((int(e_row["steamid"]), crosshair_angle))

        return visible

    # ── Smoke overlay ─────────────────────────────────────────────────────────

    def _is_smoke_obscured(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        tick: int,
        active_smokes: Optional[pd.DataFrame],
    ) -> bool:
        """
        Returns True if the ray passes through any active smoke volume
        (modelled as a sphere of radius _SMOKE_RADIUS_UNITS).
        """
        if active_smokes is None or active_smokes.empty:
            return False

        # Filter to smokes active at this tick
        smokes_now = active_smokes[
            (active_smokes["start_tick"] <= tick)
            & (active_smokes["end_tick"] >= tick)
        ]
        if smokes_now.empty:
            return False

        sx, sy, sz = start
        ex, ey, ez = end
        dx, dy, dz = ex - sx, ey - sy, ez - sz
        seg_len_sq = dx*dx + dy*dy + dz*dz
        if seg_len_sq < 1e-9:
            return False

        # Vectorized: test all smoke centers at once
        centers = smokes_now[["X", "Y", "Z"]].to_numpy(dtype=float)
        fx = centers[:, 0] - sx
        fy = centers[:, 1] - sy
        fz = centers[:, 2] - sz
        t = np.clip((fx*dx + fy*dy + fz*dz) / seg_len_sq, 0.0, 1.0)
        px = sx + t*dx
        py = sy + t*dy
        pz = sz + t*dz
        dist_sq = (px - centers[:, 0])**2 + (py - centers[:, 1])**2 + (pz - centers[:, 2])**2
        return bool(np.any(dist_sq <= _SMOKE_RADIUS_UNITS ** 2))


    # ── Smoke/flash event parsing (call once per demo) ────────────────────────

    @staticmethod
    def parse_smoke_events(parser, tickrate: int = 64) -> pd.DataFrame:
        """
        Build a DataFrame of active smoke intervals from demoparser2 events.
        Columns: X, Y, Z, start_tick, end_tick
        """
        try:
            det = parser.parse_event("smokegrenade_detonate")
            exp = parser.parse_event("smokegrenade_expired")
            det_df = det if isinstance(det, pd.DataFrame) else pd.DataFrame(det or [])
            exp_df = exp if isinstance(exp, pd.DataFrame) else pd.DataFrame(exp or [])
        except Exception as e:
            logger.warning(f"parse_smoke_events: failed to parse smoke events: {e}")
            return pd.DataFrame(columns=["X", "Y", "Z", "start_tick", "end_tick"])

        if det_df.empty:
            return pd.DataFrame(columns=["X", "Y", "Z", "start_tick", "end_tick"])

        rows = []
        for d_row in det_df.itertuples():
            end_tick = int(d_row.tick) + _SMOKE_FALLBACK_DURATION_S * tickrate
            x_col = _find_column(exp_df, "x", "X")
            y_col = _find_column(exp_df, "y", "Y")
            if not exp_df.empty and x_col is not None and y_col is not None:
                dx = exp_df[x_col] - getattr(d_row, "x", getattr(d_row, "X", 0))
                dy = exp_df[y_col] - getattr(d_row, "y", getattr(d_row, "Y", 0))
                dist = np.sqrt(dx**2 + dy**2)
                close = exp_df[dist < _SMOKE_POSITION_MATCH_RADIUS]
                if not close.empty:
                    end_tick = int(close.sort_values("tick").iloc[0]["tick"])
            rows.append({
                "X": getattr(d_row, "x", getattr(d_row, "X", 0)),
                "Y": getattr(d_row, "y", getattr(d_row, "Y", 0)),
                "Z": getattr(d_row, "z", getattr(d_row, "Z", 0)),
                "start_tick": int(d_row.tick),
                "end_tick": end_tick,
            })
        return pd.DataFrame(rows)

    @staticmethod
    def parse_flash_intervals(
        parser, player_steamid: int, search_start: int, search_end: int,
        tickrate: int = 64,
    ) -> List[Tuple[int, int]]:
        """
        Return a list of (flash_start_tick, flash_end_tick) intervals where the player
        is actively flash-blinded AND the interval overlaps [search_start, search_end].
        """
        try:
            blind = parser.parse_event("player_blind")
            blind_df = blind if isinstance(blind, pd.DataFrame) else pd.DataFrame(blind or [])
        except Exception:
            return []

        if blind_df.empty or "tick" not in blind_df.columns:
            return []

        blind_df["tick"] = pd.to_numeric(blind_df["tick"], errors="coerce")

        steamid_col = _find_column(blind_df, "userid_steamid", "user_steamid")
        if steamid_col is None:
            return []

        player_blinds = blind_df[
            blind_df[steamid_col].astype(str) == str(player_steamid)
        ]

        intervals: List[Tuple[int, int]] = []
        for row in player_blinds.itertuples():
            f_start = int(row.tick)
            bd = getattr(row, "blind_duration", None)
            duration_s = float(bd if bd is not None else getattr(row, "duration", 0))
            f_end = f_start + int(duration_s * tickrate)
            if f_end >= search_start and f_start <= search_end:
                intervals.append((f_start, f_end))

        return intervals


# Backwards-compatible module-level aliases (tests import these directly)
parse_smoke_events = T0Detector.parse_smoke_events
parse_flash_intervals = T0Detector.parse_flash_intervals
