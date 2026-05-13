"""Phase v2-interpretation-narrative Plan 02 Task 1 — fetch_top_moments DB integration tests.

Test IDs map to v2-VALIDATION.md (D-03/D-04/D-05 + R-8 SteamID64 safety + cluster-bleed gate).
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from db_utils import init_db


_DONK_SID = 76561198386265483  # 17-digit real SteamID — guards against pd.read_sql float64 cast
_OTHER_SID = 76561197989430253  # karrigan — unrelated player rows must NOT leak


@pytest.fixture
def populated_top_moments_db(tmp_path):
    """Build minimal analytics.db with an engagements + duel_attempts mix designed
    to exercise: cluster-bleed exclusion, NULL round_number exclusion, SteamID64
    integrity, ordering by gap_vs_benchmark, and best+worst splits.

    Layout (donk, peek, rt_visible_to_aim_ms):
      - 22 "clean" rows with rt_visible_to_aim_ms ∈ [150, 360] step 10ms (round_number 1..22)
      - 5 "cluster-bleed" rows: rt_visible_to_hit_ms = 9000ms (>1500ms cap) — must be excluded
      - 3 "null round_number" rows — must be excluded
      - 5 unrelated karrigan rows — must NOT appear in donk's results
    """
    db_path = str(tmp_path / "test.db")
    init_db(db_path)

    # init_db only creates the canonical Wave-0 schema cols
    # (match_id, demo_name, player_steamid, map_name, crosshair_angle_at_t0_deg,
    #  round_time_s, round_phase, round_number). Production engagements gets the
    # rest via save_to_db / df.to_sql(if_exists='append'). Tests build rows
    # directly so we add the columns we need explicitly.
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute("ALTER TABLE engagements ADD COLUMN t0_manual_tick INTEGER DEFAULT NULL")
            conn.execute("ALTER TABLE engagements ADD COLUMN rt_visible_to_aim_ms REAL DEFAULT NULL")
            conn.execute("ALTER TABLE engagements ADD COLUMN rt_visible_to_hit_ms REAL DEFAULT NULL")
            conn.execute("ALTER TABLE engagements ADD COLUMN engagement_type TEXT DEFAULT NULL")

    rows: list[tuple] = []

    # Clean donk rows: 22 distinct values 150..360, demo + tick + map + round all set
    # round_number 1..22 — all distinct so attribution unambiguous in tests
    for i in range(22):
        rt_aim = 150.0 + i * 10.0  # 150,160,...,360 ms
        rt_hit = 600.0 + i * 5.0  # all <= 1500 (cap)
        demo = f"clean_{i}.dem"
        tick = 100000 + i * 64
        rows.append(
            (
                "1",  # match_id
                demo,
                _DONK_SID,
                "de_mirage",  # map_name
                rt_aim,  # rt_visible_to_aim_ms
                10.0 + i * 0.1,  # crosshair_angle_at_t0_deg (unused in this test but populated)
                30.0,  # round_time_s
                "mid",  # round_phase
                "peek",  # engagement_type
                tick,  # t0_manual_tick
                rt_hit,  # rt_visible_to_hit_ms
                i + 1,  # round_number 1..22
            )
        )

    # Cluster-bleed donk rows (5) — rt_visible_to_hit_ms > 1500ms
    for i in range(5):
        demo = f"bleed_{i}.dem"
        tick = 200000 + i * 64
        rows.append(
            (
                "1",
                demo,
                _DONK_SID,
                "de_mirage",
                500.0,
                12.0,
                30.0,
                "mid",
                "peek",
                tick,
                9000.0,  # ungradeable
                25 + i,  # round_number set, but bleed gate excludes regardless
            )
        )

    # NULL round_number donk rows (3)
    for i in range(3):
        demo = f"noround_{i}.dem"
        tick = 300000 + i * 64
        rows.append(
            (
                "1",
                demo,
                _DONK_SID,
                "de_mirage",
                500.0,
                12.0,
                30.0,
                "mid",
                "peek",
                tick,
                700.0,
                None,  # round_number IS NULL → excluded
            )
        )

    # Unrelated karrigan rows (5) — must not surface
    for i in range(5):
        demo = f"karrigan_{i}.dem"
        tick = 400000 + i * 64
        rows.append(
            (
                "2",
                demo,
                _OTHER_SID,
                "de_inferno",
                100.0 + i,  # very low — would top "best" if leak
                5.0,
                30.0,
                "mid",
                "peek",
                tick,
                500.0,
                10 + i,
            )
        )

    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.executemany(
                """INSERT INTO engagements (
                    match_id, demo_name, player_steamid, map_name,
                    rt_visible_to_aim_ms, crosshair_angle_at_t0_deg,
                    round_time_s, round_phase, engagement_type,
                    t0_manual_tick, rt_visible_to_hit_ms, round_number
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
            # Add a few duel_attempts rows for join coverage (not all engagements
            # need a duel_attempt, but some should — LEFT JOIN must not drop rows
            # that lack a matching duel_attempt).
            conn.executemany(
                """INSERT INTO duel_attempts (
                    match_id, map_name, demo_name, player_steamid, t0_tick,
                    enemy_steamid, was_killed, bullets_fired, bullets_hit,
                    engagement_type
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    ("1", "de_mirage", "clean_0.dem", _DONK_SID, 100000,
                     999, 1, 5, 3, "peek"),
                    ("1", "de_mirage", "clean_1.dem", _DONK_SID, 100064,
                     999, 0, 5, 0, "peek"),
                ],
            )

    return db_path


# ── Tests ────────────────────────────────────────────────────────────────────


class TestFetchTopMoments:
    """fetch_top_moments — Plan 02 Task 1 D-03/D-04/D-05 enforcement."""

    def test_fetch_top_moments_returns_n_worst_per_metric(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
            n_worst=2,
            n_best=1,
        )
        assert len(moments) == 3
        # First two are worst (lower_is_better → highest player_value first)
        assert moments[0]["player_value"] >= moments[1]["player_value"]
        # Last is best (lowest player_value, well below benchmark 200)
        assert moments[2]["player_value"] < moments[1]["player_value"]
        assert moments[2]["player_value"] <= 200.0

    def test_fetch_top_moments_excludes_cluster_bleed_rows(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
            n_worst=10,  # ask for many — cluster-bleed must STILL be filtered
            n_best=10,
        )
        # No bleed_*.dem moments should surface
        demos = {m["demo_name"] for m in moments}
        assert not any(d.startswith("bleed_") for d in demos), (
            f"cluster-bleed leak: {demos}"
        )

    def test_fetch_top_moments_excludes_null_round_number(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
            n_worst=10,
            n_best=10,
        )
        for m in moments:
            assert m["round_number"] is not None
            assert isinstance(m["round_number"], int)
        # Also: no noround_*.dem leaked
        demos = {m["demo_name"] for m in moments}
        assert not any(d.startswith("noround_") for d in demos)

    def test_fetch_top_moments_steamid64_no_truncation(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
        )
        # No exception, returns dicts; t0_tick must be int (not float — float would
        # signal pd.read_sql cast or accidental float coercion).
        assert moments
        for m in moments:
            assert isinstance(m["t0_tick"], int)

    def test_fetch_top_moments_dict_shape(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
        )
        required_keys = {
            "demo_name", "t0_tick", "map_name", "round_number",
            "round_phase", "round_time_s", "player_value",
            "benchmark_p50", "gap_vs_benchmark",
        }
        for m in moments:
            assert required_keys.issubset(m.keys()), (
                f"missing keys: {required_keys - set(m.keys())}"
            )

    def test_fetch_top_moments_empty_returns_empty_list(self, tmp_path):
        from interpretation_narrative import fetch_top_moments

        db_path = str(tmp_path / "fresh.db")
        init_db(db_path)
        # Add the runtime-supplied columns the query references
        with closing(sqlite3.connect(db_path)) as conn:
            with conn:
                conn.execute("ALTER TABLE engagements ADD COLUMN t0_manual_tick INTEGER DEFAULT NULL")
                conn.execute("ALTER TABLE engagements ADD COLUMN rt_visible_to_aim_ms REAL DEFAULT NULL")
                conn.execute("ALTER TABLE engagements ADD COLUMN rt_visible_to_hit_ms REAL DEFAULT NULL")
                conn.execute("ALTER TABLE engagements ADD COLUMN engagement_type TEXT DEFAULT NULL")
        result = fetch_top_moments(
            db_path, player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms", engagement_type="peek",
            benchmark_p50=200.0,
        )
        assert result == []

    def test_fetch_top_moments_unrelated_player_does_not_leak(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
            n_worst=20,
            n_best=20,
        )
        demos = {m["demo_name"] for m in moments}
        # karrigan rows must NOT surface
        assert not any(d.startswith("karrigan_") for d in demos), (
            f"unrelated-player leak: {demos}"
        )

    def test_fetch_top_moments_invalid_engagement_type_raises(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        with pytest.raises(ValueError, match="engagement_type"):
            fetch_top_moments(
                populated_top_moments_db,
                player_steamid=_DONK_SID,
                metric="rt_visible_to_aim_ms",
                engagement_type="bogus",
                benchmark_p50=200.0,
            )

    def test_fetch_top_moments_gap_vs_benchmark_correct(self, populated_top_moments_db):
        from interpretation_narrative import fetch_top_moments

        moments = fetch_top_moments(
            populated_top_moments_db,
            player_steamid=_DONK_SID,
            metric="rt_visible_to_aim_ms",
            engagement_type="peek",
            benchmark_p50=200.0,
            n_worst=2,
            n_best=1,
        )
        for m in moments:
            assert m["gap_vs_benchmark"] == m["player_value"] - 200.0
            assert m["benchmark_p50"] == 200.0
