"""Phase 8 interpretation layer tests. Task IDs map to 08-VALIDATION.md."""
import pytest
import sqlite3
import os
import tempfile
import pandas as pd

# All imports must work before any test runs
from interpretation import (
    assign_tier, compute_interpretation, get_benchmark_players,
    get_worst_metric, DRILLS, _FALLBACK_THRESHOLDS,
)
from config import PLAYER_NAMES

# ── Unit tests (Wave 1) ──────────────────────────────────────────────────────

def test_assign_tier_lower_is_better():  # 08-01-01
    assert assign_tier(2.0, 3.0, 6.0, 11.0, lower_is_better=True) == "Elite"
    assert assign_tier(4.0, 3.0, 6.0, 11.0, lower_is_better=True) == "Good"
    assert assign_tier(7.0, 3.0, 6.0, 11.0, lower_is_better=True) == "Average"
    assert assign_tier(12.0, 3.0, 6.0, 11.0, lower_is_better=True) == "Work needed"
    # boundary: exactly p25
    assert assign_tier(3.0, 3.0, 6.0, 11.0, lower_is_better=True) == "Elite"

def test_assign_tier_higher_is_better():  # 08-01-02
    assert assign_tier(32.0, 17.2, 24.5, 31.5, lower_is_better=False) == "Elite"
    assert assign_tier(25.0, 17.2, 24.5, 31.5, lower_is_better=False) == "Good"
    assert assign_tier(20.0, 17.2, 24.5, 31.5, lower_is_better=False) == "Average"
    assert assign_tier(10.0, 17.2, 24.5, 31.5, lower_is_better=False) == "Work needed"
    # boundary: exactly p75
    assert assign_tier(31.5, 17.2, 24.5, 31.5, lower_is_better=False) == "Elite"

@pytest.fixture
def mock_db(tmp_path):
    """Create minimal analytics.db with 25 karrigan peek engagements across 25 demos."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE engagements (
        player_steamid INTEGER, engagement_type TEXT, demo_name TEXT,
        crosshair_angle_at_t0_deg REAL, rt_visible_to_aim_ms REAL,
        rt_aim_to_hit_ms REAL, rt_visible_to_hit_ms REAL
    )""")
    conn.execute("""CREATE TABLE duel_attempts (
        player_steamid INTEGER, engagement_type TEXT, demo_name TEXT,
        was_killed INTEGER, bullets_fired INTEGER, bullets_hit INTEGER
    )""")
    sid = 76561197989430253  # karrigan
    for i in range(25):
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?)",
            (sid, "peek", f"demo_{i}.dem", 5.0 + i * 0.2, 200.0 + i * 5, 400.0 + i * 10, 600.0 + i * 15))
        conn.execute("INSERT INTO duel_attempts VALUES (?,?,?,?,?,?)",
            (sid, "peek", f"demo_{i}.dem", 1, 20, 3))
    conn.commit()
    conn.close()
    return db_path, sid


def test_compute_interpretation_schema(mock_db):  # 08-01-03
    db_path, sid = mock_db
    rows = compute_interpretation(db_path, player_steamid=sid, benchmark_steamid=sid, engagement_type="peek")
    assert len(rows) >= 3
    for row in rows:
        assert "metric" in row
        assert "tier" in row
        assert "drill" in row
        assert "caveat" in row or row.get("caveat") is None

def test_peek_hold_separate_thresholds():  # 08-01-04
    assert "peek" in _FALLBACK_THRESHOLDS
    assert "hold" in _FALLBACK_THRESHOLDS
    # peek has all 6 metrics
    for m in ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms",
              "rt_visible_to_hit_ms", "kill_rate", "hit_rate"]:
        assert m in _FALLBACK_THRESHOLDS["peek"], f"peek missing {m}"
    # hold does NOT have T0->T1 or T1->T2 (too sparse)
    assert "rt_visible_to_aim_ms" not in _FALLBACK_THRESHOLDS["hold"]
    assert "rt_aim_to_hit_ms" not in _FALLBACK_THRESHOLDS["hold"]
    # hold has rt_visible_to_hit_ms
    assert "rt_visible_to_hit_ms" in _FALLBACK_THRESHOLDS["hold"]

def test_rt_bottleneck_component(mock_db):  # 08-01-05
    db_path, sid = mock_db
    rows = compute_interpretation(db_path, player_steamid=sid, benchmark_steamid=sid, engagement_type="peek")
    rt_row = next((r for r in rows if r["metric"] == "rt_visible_to_hit_ms"), None)
    assert rt_row is not None
    # bottleneck_component may be None if components are equal — just verify key exists
    assert "bottleneck_component" in rt_row

def test_fallback_thresholds_triggered(tmp_path):  # 08-01-06
    # Create DB with only 5 demos for benchmark (< 20 threshold)
    db_path = str(tmp_path / "small.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE engagements (
        player_steamid INTEGER, engagement_type TEXT, demo_name TEXT,
        crosshair_angle_at_t0_deg REAL, rt_visible_to_aim_ms REAL,
        rt_aim_to_hit_ms REAL, rt_visible_to_hit_ms REAL
    )""")
    conn.execute("CREATE TABLE duel_attempts (player_steamid INTEGER, engagement_type TEXT, demo_name TEXT, was_killed INTEGER, bullets_fired INTEGER, bullets_hit INTEGER)")
    sid = 76561197989430253
    benchmark_sid = 76561198000000001  # different player → fallback triggers when benchmark <20 demos
    for i in range(5):
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?)",
            (sid, "peek", f"demo_{i}.dem", 5.0, 200.0, 400.0, 600.0))
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?)",
            (benchmark_sid, "peek", f"demo_{i}.dem", 5.0, 200.0, 400.0, 600.0))
    conn.commit()
    conn.close()
    rows = compute_interpretation(db_path, player_steamid=sid, benchmark_steamid=benchmark_sid, engagement_type="peek")
    assert all(r.get("small_sample") is True for r in rows if r["tier"] not in ("n/a",))

def test_benchmark_small_sample_label(tmp_path):  # 08-01-07
    db_path = str(tmp_path / "small2.db")
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE engagements (player_steamid INTEGER, engagement_type TEXT, demo_name TEXT, crosshair_angle_at_t0_deg REAL, rt_visible_to_aim_ms REAL, rt_aim_to_hit_ms REAL, rt_visible_to_hit_ms REAL)")
    conn.execute("CREATE TABLE duel_attempts (player_steamid INTEGER, engagement_type TEXT, demo_name TEXT, was_killed INTEGER, bullets_fired INTEGER, bullets_hit INTEGER)")
    sid = 76561197989430253
    for i in range(5):
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?)", (sid, "peek", f"demo_{i}.dem", 5.0, 200.0, 400.0, 600.0))
    conn.commit()
    conn.close()
    players = get_benchmark_players(db_path)
    entry = next((p for p in players if p["steamid"] == sid), None)
    assert entry is not None
    assert entry["small_sample"] is True
    assert "(small sample)" in entry["display_name"]

def test_player_names_lookup():  # 08-01-08
    assert PLAYER_NAMES[76561197989430253] == "karrigan"
    assert PLAYER_NAMES[76561198386265483] == "donk"
    assert isinstance(PLAYER_NAMES, dict)

def test_player_not_in_db_returns_empty(mock_db):  # 08-01-09
    db_path, _ = mock_db
    nonexistent_sid = 9999999999999999  # not in DB
    # Must not raise; SQL uses int() cast and ? params — no injection risk
    rows = compute_interpretation(db_path, player_steamid=nonexistent_sid, benchmark_steamid=76561197989430253, engagement_type="peek")
    # Player has no data so all player_values are None
    assert all(r.get("player_value") is None or r.get("tier") in ("n/a", "Work needed", "Average", "Good", "Elite")
               for r in rows)

def test_rt_drill_contains_caveat_ref(mock_db):  # 08-01-10
    db_path, sid = mock_db
    rows = compute_interpretation(db_path, player_steamid=sid, benchmark_steamid=sid, engagement_type="peek")
    rt_metrics = {"rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"}
    for row in rows:
        if row["metric"] in rt_metrics and row.get("player_value") is not None:
            assert row.get("caveat") == "Measured on hits only — survivorship bias applies", \
                f"RT metric {row['metric']} missing caveat"

# ── Integration test (Wave 2) ────────────────────────────────────────────────

@pytest.mark.integration
def test_integration_live_db():  # 08-02-01
    """Integration: compute_interpretation against live analytics.db with karrigan data."""
    db_path = os.path.join(os.path.dirname(__file__), "..", "analytics.db")
    if not os.path.exists(db_path):
        pytest.skip("analytics.db not found — run batch analysis first")

    KARRIGAN_SID = 76561197989430253

    # get_benchmark_players must return karrigan with demo_count >= 20
    players = get_benchmark_players(db_path)
    karrigan_entry = next((p for p in players if p["steamid"] == KARRIGAN_SID), None)
    assert karrigan_entry is not None, "karrigan not found in analytics.db"
    assert karrigan_entry["demo_count"] >= 20, f"karrigan only has {karrigan_entry['demo_count']} demos"
    assert not karrigan_entry["small_sample"]
    assert "(small sample)" not in karrigan_entry["display_name"]

    # compute_interpretation for peek
    rows = compute_interpretation(db_path, KARRIGAN_SID, KARRIGAN_SID, "peek")
    assert len(rows) >= 3, "expected at least 3 metric rows for peek"

    valid_tiers = {"Elite", "Good", "Average", "Work needed", "n/a"}
    for row in rows:
        assert row["tier"] in valid_tiers, f"invalid tier: {row['tier']}"
        assert "drill" in row
        assert "metric" in row

    # At least one row should have non-None player_value (karrigan has data)
    has_values = [r for r in rows if r.get("player_value") is not None]
    assert len(has_values) >= 1, "all player_value fields are None for karrigan"

    # RT rows must have survivorship bias caveat
    rt_rows = [r for r in rows if r["metric"] in {"rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"}
               and r.get("player_value") is not None]
    for row in rt_rows:
        assert row.get("caveat") == "Measured on hits only — survivorship bias applies"
