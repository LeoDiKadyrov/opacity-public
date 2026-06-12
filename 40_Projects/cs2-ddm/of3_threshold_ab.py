"""OF-3-02 Task 3: D-02 threshold A/B comparison on 1 demo.

Runs the OF-3 timing pass (reaction_timing.compute_timing via
outcome_first.reconstruct_all_players) on
for_analysis/spirit/spirit-vs-the-mongolz-m2-ancient.dem for donk, under TWO
TARGET_REACHED_THRESHOLD variants:
  - fixed 3.0 (current config default)
  - distance-scaled: max(degrees(atan2(16, distance_to_enemy)), 0.5)

Writes results into a scratch/throwaway DB (NOT analytics.db), then prints +
saves a comparison table to of3_threshold_ab.md.

Distance-scaled variant: since compute_timing's _angular_dist_at_tick already
has player/enemy positions, we monkeypatch reaction_timing.TARGET_REACHED_THRESHOLD
to a per-call dynamic value is not directly supported by the fixed-constant
interface -- so for the distance-scaled variant we monkeypatch
reaction_timing._find_t1's threshold lookup via a wrapper that recomputes
distance per-tick. To keep this a clean, throwaway A/B without touching
production code, we patch TARGET_REACHED_THRESHOLD module global per run AND,
for the distance-scaled variant, patch _angular_dist_at_tick-adjacent logic
via a monkeypatched _find_t1 that uses a distance-based threshold function.
"""
from __future__ import annotations

import math
import os
import sqlite3
from contextlib import closing

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import reaction_timing
from db_utils import init_db, get_next_match_id
from outcome_first import (
    _parse_demo_events,
    _parse_timing_ticks,
    _parse_demo_header_map,
    discover_player_sids,
    collect_exchanges,
    group_episodes,
)
from t0_detector import T0Detector
from config import TARGET_REACHED_THRESHOLD as FIXED_THRESHOLD

DEMO = r"D:\Obsidian\opacity\40_Projects\for_analysis\spirit\spirit-vs-the-mongolz-m2-ancient.dem"
DONK_SID = 76561198386265483
SCRATCH_DB = "of3_threshold_ab_scratch.db"
MS_PER_TICK = 1000.0 / 64.0
TICK_QUANTA_MS = [15.625, 31.25, 46.875, 62.5]


def _distance_scaled_threshold(dist: float) -> float:
    """max(degrees(atan2(16, distance_to_enemy)), 0.5) per D-02."""
    return max(math.degrees(math.atan2(16.0, max(dist, 1e-6))), 0.5)


def _make_distance_scaled_find_t1(orig_find_t1):
    """Wrap _find_t1 so TARGET_REACHED_THRESHOLD comparison is replaced with a
    per-tick distance-scaled threshold.
    """
    import config as cfg

    def wrapped(ticks_df, player_sid, enemy_sid, t0_tick, first_event_tick, ticks_by_sid=None):
        window_size = cfg.T1_SUSTAINED_AIM_TICKS + 1

        def _on_target(t):
            d = reaction_timing._angular_dist_at_tick(ticks_df, player_sid, enemy_sid, t, ticks_by_sid)
            if d is None:
                return False, d
            p_row = reaction_timing._row_at_tick(ticks_df, player_sid, t, ticks_by_sid)
            e_row = reaction_timing._row_at_tick(ticks_df, enemy_sid, t, ticks_by_sid)
            if p_row is None or e_row is None:
                return False, d
            dx = float(e_row["X"]) - float(p_row["X"])
            dy = float(e_row["Y"]) - float(p_row["Y"])
            dz = float(e_row["Z"]) - float(p_row["Z"])
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            thresh = _distance_scaled_threshold(dist)
            return d <= thresh, d

        for t in range(t0_tick, first_event_tick + 1):
            ok = True
            for wt in range(t, t + window_size):
                on_target, _ = _on_target(wt)
                if not on_target:
                    ok = False
                    break
            if ok:
                return t, "lands"
        return None, "never_landed"

    return wrapped


def _run_variant(variant: str, db_path: str) -> None:
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(db_path)

    orig_find_t1 = reaction_timing._find_t1
    if variant == "distance_scaled":
        reaction_timing._find_t1 = _make_distance_scaled_find_t1(orig_find_t1)

    try:
        hurt_df, death_df, fires_df = _parse_demo_events(DEMO)
        sid = DONK_SID
        demo_name = os.path.splitext(os.path.basename(DEMO))[0]
        match_id = get_next_match_id(db_path)

        events = collect_exchanges(hurt_df, death_df, sid)
        eps = group_episodes(events, fires_df, sid, demo=demo_name, match_id=str(match_id))
        episodes_by_sid = {sid: eps}

        ticks_df, ticks_by_sid = _parse_timing_ticks(DEMO, episodes_by_sid)
        map_name = _parse_demo_header_map(DEMO)
        t0_detector = T0Detector(map_name)

        import pandas as pd
        from db_utils import save_to_db

        timing_cols = [
            "t0_tick", "t0_source", "t1_tick", "t1_source",
            "crosshair_angle_at_t0_deg", "rt_visible_to_land_ms", "rt_visible_to_hit_ms",
        ]
        df = pd.DataFrame(eps)
        df["player_steamid"] = sid
        df = df.rename(columns={"n_hits_P_on_E": "n_hits_p_on_e", "n_hits_E_on_P": "n_hits_e_on_p"})
        if "opponent" in df.columns:
            df = df.drop(columns=["opponent"])

        timings = []
        for _, row in df.iterrows():
            t = reaction_timing.compute_timing(row.to_dict(), ticks_df, t0_detector, ticks_by_sid=ticks_by_sid)
            timings.append(t)
        timing_df = pd.DataFrame(timings, index=df.index, columns=timing_cols)
        df = pd.concat([df, timing_df], axis=1)

        save_to_db(df, db_path, "duel_episodes", match_id)
        print(f"[{variant}] wrote {len(df)} episodes to {db_path}")
    finally:
        reaction_timing._find_t1 = orig_find_t1


def _analyze(db_path: str, threshold: float) -> dict:
    with closing(sqlite3.connect(db_path)) as conn:
        cur = conn.execute(
            "SELECT t1_tick, t0_tick, t1_source, t0_source, "
            "rt_visible_to_land_ms, crosshair_angle_at_t0_deg FROM duel_episodes"
        )
        rows = cur.fetchall()

    n = len(rows)
    if n == 0:
        return {"n": 0}

    resolved = [r for r in rows if r[2] == "lands" and r[4] is not None]
    rt_values = [r[4] for r in resolved]

    pinned = sum(1 for v in rt_values if any(abs(v - q) < 0.01 for q in TICK_QUANTA_MS))
    pinned_pct = (pinned / len(rt_values) * 100) if rt_values else 0.0

    min_rt = min(rt_values) if rt_values else None
    rt_sorted = sorted(rt_values)
    p10_rt = rt_sorted[int(0.10 * len(rt_sorted))] if rt_sorted else None

    never_landed = sum(1 for r in rows if r[2] == "never_landed")
    never_landed_pct = (never_landed / n * 100) if n else 0.0

    impossible = sum(
        1 for r in rows
        if r[1] is not None and r[0] is not None
        and r[0] == r[1] + 1
        and r[5] is not None
        and r[5] > 2 * threshold
    )

    return {
        "n": n,
        "n_resolved_lands": len(resolved),
        "pinned_pct": pinned_pct,
        "min_rt_ms": min_rt,
        "p10_rt_ms": p10_rt,
        "never_landed_pct": never_landed_pct,
        "n_impossible_b5": impossible,
    }


def main() -> None:
    fixed_db = "of3_ab_fixed.db"
    scaled_db = "of3_ab_distance_scaled.db"

    _run_variant("fixed", fixed_db)
    _run_variant("distance_scaled", scaled_db)

    fixed_stats = _analyze(fixed_db, FIXED_THRESHOLD)
    # For impossible-row check on the distance-scaled variant, use the fixed
    # threshold's 2x value as the comparison bound too (D-02 acceptance text
    # references "2*threshold" generically; fixed=3.0 is the locked default
    # bound used for both variants' impossible-row count for comparability).
    scaled_stats = _analyze(scaled_db, FIXED_THRESHOLD)

    lines = []
    lines.append("# OF-3-02 D-02 Threshold A/B Comparison\n")
    lines.append(f"Demo: `spirit-vs-the-mongolz-m2-ancient.dem` (donk, {DONK_SID})\n")
    lines.append("| Metric | Fixed 3.0deg | Distance-scaled |")
    lines.append("|-|-|-|")
    lines.append(f"| n episodes | {fixed_stats.get('n')} | {scaled_stats.get('n')} |")
    lines.append(f"| n resolved (t1_source=lands) | {fixed_stats.get('n_resolved_lands')} | {scaled_stats.get('n_resolved_lands')} |")
    lines.append(f"| %@tick-quantum pinning | {fixed_stats.get('pinned_pct', 0):.1f}% | {scaled_stats.get('pinned_pct', 0):.1f}% |")
    lines.append(f"| min rt_visible_to_land_ms | {fixed_stats.get('min_rt_ms')} | {scaled_stats.get('min_rt_ms')} |")
    lines.append(f"| p10 rt_visible_to_land_ms | {fixed_stats.get('p10_rt_ms')} | {scaled_stats.get('p10_rt_ms')} |")
    lines.append(f"| never_landed% | {fixed_stats.get('never_landed_pct', 0):.1f}% | {scaled_stats.get('never_landed_pct', 0):.1f}% |")
    lines.append(f"| n b5-class impossible rows | {fixed_stats.get('n_impossible_b5')} | {scaled_stats.get('n_impossible_b5')} |")
    lines.append("")
    lines.append("## Decision rule (locked, D-02)")
    lines.append("KEEP fixed 3.0 UNLESS fixed produces >10% pinning OR >10 impossible "
                  "rows that distance-scaling resolves.")

    out = "\n".join(lines)
    print(out)
    with open("of3_threshold_ab.md", "w", encoding="utf-8") as fh:
        fh.write(out + "\n")


if __name__ == "__main__":
    main()
