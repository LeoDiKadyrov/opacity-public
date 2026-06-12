"""Two-tier distribution-shape regression suite (OF-3 D-15).

Tier 1 (TestSyntheticDistributionShape): always-on, no DB, no demo files.
  Imports reaction_timing.compute_timing -> RED until OF-3-02 implements it
  (expected Wave-0 TDD state, same as tests/test_reaction_timing.py).

Tier 2 (TestLiveDistributionShape): @pytest.mark.requires_db, runs against the
  real analytics.db duel_episodes table after each staged re-batch (OF-3-03).
  SKIPS gracefully when analytics.db is absent or duel_episodes has no
  resolved timing rows yet (pre-rebatch) -- so this tier is green-or-skipped
  before OF-3-03's re-batch populates data.

b5_smoking_gun.md is the physics-bounded regression both tiers guard against:
  a row where t1_tick == t0_tick + 1 (1-tick "landing") AND
  crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD is physically
  impossible -- a >=6deg flick cannot land+sustain in a single 15.625ms tick.
"""

from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from config import DB_PATH, TARGET_REACHED_THRESHOLD

MS_PER_TICK = 1000.0 / 64.0
TICK_QUANTA_MS = [15.625, 31.25, 46.875, 62.5]


def _load_resolved_rt() -> list[tuple]:
    """Open analytics.db and fetch (rt_visible_to_land_ms, t1_tick, t0_tick,
    crosshair_angle_at_t0_deg) for rows with t1_source == 'lands'.

    Uses cursor.fetchall() (never the pandas SQL-frame reader) per project
    SteamID-precision convention -- though these columns are floats/ints, not
    SteamIDs, the fetchall convention is kept for consistency across
    DB-reading tests.

    Returns an empty list if analytics.db is absent, duel_episodes does not
    exist, or no rows have resolved timing yet.
    """
    import os

    if not os.path.exists(DB_PATH):
        return []
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            cur = conn.execute(
                "SELECT rt_visible_to_land_ms, t1_tick, t0_tick, crosshair_angle_at_t0_deg "
                "FROM duel_episodes WHERE t1_source = 'lands' "
                "AND rt_visible_to_land_ms IS NOT NULL"
            )
            return cur.fetchall()
    except sqlite3.OperationalError:
        return []


def _load_t1_source_counts() -> dict:
    """Open analytics.db and return counts of each t1_source value.

    Returns an empty dict if analytics.db/duel_episodes is absent or empty.
    """
    import os

    if not os.path.exists(DB_PATH):
        return {}
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            cur = conn.execute(
                "SELECT t1_source, COUNT(*) FROM duel_episodes "
                "WHERE t1_source IS NOT NULL GROUP BY t1_source"
            )
            return dict(cur.fetchall())
    except sqlite3.OperationalError:
        return {}


def _load_t0_source_counts() -> dict:
    """Open analytics.db and return counts of each t0_source value.

    Returns an empty dict if analytics.db/duel_episodes is absent or empty.
    """
    import os

    if not os.path.exists(DB_PATH):
        return {}
    try:
        with closing(sqlite3.connect(DB_PATH)) as conn:
            cur = conn.execute(
                "SELECT t0_source, COUNT(*) FROM duel_episodes "
                "WHERE t0_source IS NOT NULL GROUP BY t0_source"
            )
            return dict(cur.fetchall())
    except sqlite3.OperationalError:
        return {}


class TestSyntheticDistributionShape:
    """Tier 1 -- always-on, no DB, no demos (D-15).

    Imports reaction_timing -> RED until OF-3-02.
    """

    def test_flick_batch_no_impossible_one_tick_lands(self):
        from reaction_timing import compute_timing  # RED until OF-3-02
        from ddm_analyzer import DDMAnalyzer

        P = 76561198386265483
        E = 76561198113666193
        P_POS = (0.0, 0.0, 0.0)
        E_POS = (500.0, 0.0, 0.0)
        _, desired_yaw = DDMAnalyzer.get_desired_angles(
            P_POS[0], P_POS[1], P_POS[2], E_POS[0], E_POS[1], E_POS[2]
        )
        desired_pitch, _ = DDMAnalyzer.get_desired_angles(
            P_POS[0], P_POS[1], P_POS[2], E_POS[0], E_POS[1], E_POS[2]
        )

        class _StubT0Detector:
            def __init__(self, visible_ticks):
                self.visible_ticks = visible_ticks

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

        import pandas as pd

        def _make_ticks_df(start_tick, end_tick, yaw_by_tick):
            rows = []
            for tick in range(start_tick, end_tick + 1):
                yaw = yaw_by_tick.get(tick, desired_yaw)
                rows.append(
                    {
                        "tick": tick,
                        "steamid": P,
                        "X": P_POS[0],
                        "Y": P_POS[1],
                        "Z": P_POS[2],
                        "pitch": desired_pitch,
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

        results = []
        # Build N=5 synthetic flick episodes: crosshair 30deg off at T0,
        # converging only several ticks later -- never a 1-tick land.
        for i in range(5):
            t0 = 1000 + i * 100
            t2 = t0 + 20
            off_yaw = desired_yaw + 30.0
            yaw_by_tick = {}
            for tick in range(t0, t0 + 5):
                yaw_by_tick[tick] = off_yaw
            for tick in range(t0 + 5, t2 + 1):
                yaw_by_tick[tick] = desired_yaw

            ticks_df = _make_ticks_df(t0 - 5, t2 + 5, yaw_by_tick)
            detector = _StubT0Detector(visible_ticks=set(range(t0, t2 + 1)))
            episode = {
                "player_steamid": P,
                "opponent_steamid": E,
                "first_event_tick": t2,
                "last_event_tick": t2,
            }
            results.append(compute_timing(episode, ticks_df, detector))

        # Physics-bounded invariant (b5_smoking_gun.md): 0 rows where
        # t1_tick == t0_tick + 1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD.
        impossible = [
            r
            for r in results
            if r["t0_tick"] is not None
            and r["t1_tick"] is not None
            and r["t1_tick"] == r["t0_tick"] + 1
            and r["crosshair_angle_at_t0_deg"] is not None
            and r["crosshair_angle_at_t0_deg"] > 2 * TARGET_REACHED_THRESHOLD
        ]
        assert impossible == []


class TestLiveDistributionShape:
    """Tier 2 -- @requires_db, runs after each re-batch stage (D-15)."""

    @pytest.mark.requires_db
    def test_tick_quantum_pinning_below_10pct(self):
        # Per-quantum check per OF-3-CONTEXT.md: "no >10% cluster at ANY
        # tick-quantum value (15.625/31.25/46.875ms)". A floor/pin artifact
        # (B-1/B-5 class) concentrates rows on ONE quantum; physically real
        # near-threshold micro-corrections spread across quanta. The aggregate
        # across all quanta is therefore NOT the gate (N=5 checkpoint verdict
        # 2026-06-11: 12.2% aggregate / ~3-5% per quantum accepted by user).
        rows = _load_resolved_rt()
        if not rows:
            pytest.skip("duel_episodes has no resolved timing rows yet (pre-rebatch)")
        values = [r[0] for r in rows]
        for q in TICK_QUANTA_MS:
            pinned_at_q = sum(1 for v in values if abs(v - q) < 0.01)
            share = pinned_at_q / len(values)
            assert share < 0.10, (
                f"pinning cluster at {q}ms: {pinned_at_q}/{len(values)}"
                f" = {share:.1%} (>10% at a single tick-quantum value)"
            )

    @pytest.mark.requires_db
    def test_min_rt_non_negative(self):
        rows = _load_resolved_rt()
        if not rows:
            pytest.skip("duel_episodes has no resolved timing rows yet (pre-rebatch)")
        values = [r[0] for r in rows]
        assert min(values) >= 0

    @pytest.mark.requires_db
    def test_no_impossible_one_tick_lands(self):
        rows = _load_resolved_rt()
        if not rows:
            pytest.skip("duel_episodes has no resolved timing rows yet (pre-rebatch)")
        impossible = [
            r
            for r in rows
            if r[1] is not None
            and r[2] is not None
            and r[1] == r[2] + 1
            and r[3] is not None
            and r[3] > 2 * TARGET_REACHED_THRESHOLD
        ]
        assert impossible == []

    @pytest.mark.requires_db
    def test_never_landed_never_visible_pct_reported(self):
        t1_counts = _load_t1_source_counts()
        t0_counts = _load_t0_source_counts()
        if not t1_counts and not t0_counts:
            pytest.skip("duel_episodes has no timing-source rows yet (pre-rebatch)")

        if t1_counts:
            t1_total = sum(t1_counts.values())
            never_landed_pct = t1_counts.get("never_landed", 0) / t1_total
            # diagnostic soft-flag, not a hard failure mode for row validity --
            # but >50% never_landed indicates the T1 predicate may be too strict.
            assert (
                never_landed_pct <= 0.50
            ), f"never_landed = {never_landed_pct:.1%} of {t1_total} rows (>50% flagged)"

        if t0_counts:
            t0_total = sum(t0_counts.values())
            never_visible_pct = t0_counts.get("never_visible", 0) / t0_total
            assert (
                never_visible_pct <= 0.50
            ), f"never_visible = {never_visible_pct:.1%} of {t0_total} rows (>50% flagged)"
