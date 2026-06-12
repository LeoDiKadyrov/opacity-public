"""OF-3 staged re-batch driver -- donk corpus, N=1 -> 5 -> 81 (D-14).

Re-runs outcome_first.reconstruct_all_players for donk's 81-demo corpus
(D:\\Obsidian\\opacity\\40_Projects\\for_analysis\\spirit) so duel_episodes
gains the OF-3 timing columns (t0_tick/t0_source/t1_tick/t1_source/
crosshair_angle_at_t0_deg/rt_visible_to_land_ms/rt_visible_to_hit_ms).

OF-2 already wrote 3352 timing-less donk rows (t0_source IS NULL). This
driver DELETEs each demo's donk rows before re-running reconstruct_all_players
(force-reprocess), so the rewritten rows carry timing -- match_id is
reassigned via get_next_match_id (no collisions, D-14/T-OF3-05).

Skip-existing (resume-safe, T-OF3-06): a demo is "done" when its donk rows
in duel_episodes have t0_source IS NOT NULL.

Staging: --stage {1,5,81} processes the first N demos (sorted filename order,
deterministic, N=1 subset of N=5 subset of N=81).

Subprocess/UTF-8: this driver runs INLINE (no subprocess to multi_player_analyze
-- reconstruct_all_players is called directly), but the UTF-8 env vars are set
at process start per the Windows cp1252 gotcha (outcome_first.py also sets
these defensively).
"""

from __future__ import annotations

import argparse
import os
import sqlite3
import sys
import time
from contextlib import closing
from pathlib import Path

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
os.environ.setdefault("PYTHONUTF8", "1")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

REPO = Path(__file__).parent.resolve()
CORPUS_DEFAULT = r"D:\Obsidian\opacity\40_Projects\for_analysis\spirit"
DONK_SID = 76561198386265483

LOG = REPO / "of3_rebatch.log"
REPORT = REPO / "of3_rebatch_report.md"

TICK_QUANTA_MS = [15.625, 31.25, 46.875, 62.5]


def log(msg: str) -> None:
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def report_append(line: str) -> None:
    with open(REPORT, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def discover_donk_demos(corpus: str) -> list[Path]:
    """Return the donk .dem files in `corpus`, sorted by filename.

    Deterministic ordering so N=1 subset of N=5 subset of N=81. A demo is
    included only if it has at least one player_hurt/player_death event
    involving DONK_SID -- determined lazily during processing, NOT here
    (parsing every demo twice is wasteful). This function returns ALL .dem
    files sorted; the caller filters out demos with 0 donk episodes after
    `reconstruct_all_players` runs (results[DONK_SID] == 0).
    """
    p = Path(corpus)
    return sorted(p.glob("*.dem"), key=lambda f: f.name)


def of3_done(demo_name: str, db: str) -> bool:
    """A demo is done for donk when its duel_episodes rows have t0_source IS NOT NULL."""
    if not Path(db).exists():
        return False
    with closing(sqlite3.connect(db)) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes "
            "WHERE demo_name=? AND player_steamid=? AND t0_source IS NOT NULL",
            (demo_name, DONK_SID),
        ).fetchone()[0]
    return n > 0


def delete_donk_timing_rows(demo_name: str, db: str) -> int:
    """DELETE this demo's donk rows from duel_episodes (force-reprocess).

    reconstruct_all_players reinserts WITH timing under a fresh match_id
    (T-OF3-05). Bound int param for sid -- never pd.read_sql on sid columns.
    """
    with closing(sqlite3.connect(db)) as conn:
        n = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE demo_name=? AND player_steamid=?",
            (demo_name, DONK_SID),
        ).fetchone()[0]
        conn.execute(
            "DELETE FROM duel_episodes WHERE demo_name=? AND player_steamid=?",
            (demo_name, DONK_SID),
        )
        conn.commit()
    return n


def distribution_shape_summary(db: str) -> dict:
    """Compute the doubt-trigger distribution-shape summary for donk's lands rows.

    Returns a dict with: n_resolved, pinned_pct, min_rt, p10_rt,
    n_never_landed, n_t1_total, never_landed_pct, n_never_visible,
    n_t0_total, never_visible_pct, n_b5_class.
    """
    out: dict = {}
    if not Path(db).exists():
        return out
    with closing(sqlite3.connect(db)) as conn:
        rows = conn.execute(
            "SELECT rt_visible_to_land_ms, t1_tick, t0_tick, crosshair_angle_at_t0_deg "
            "FROM duel_episodes WHERE player_steamid=? AND t1_source='lands' "
            "AND rt_visible_to_land_ms IS NOT NULL",
            (DONK_SID,),
        ).fetchall()
        t1_counts = dict(
            conn.execute(
                "SELECT t1_source, COUNT(*) FROM duel_episodes "
                "WHERE player_steamid=? AND t1_source IS NOT NULL GROUP BY t1_source",
                (DONK_SID,),
            ).fetchall()
        )
        t0_counts = dict(
            conn.execute(
                "SELECT t0_source, COUNT(*) FROM duel_episodes "
                "WHERE player_steamid=? AND t0_source IS NOT NULL GROUP BY t0_source",
                (DONK_SID,),
            ).fetchall()
        )
        b5_class = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=? "
            "AND t1_tick = t0_tick + 1 AND crosshair_angle_at_t0_deg > 6.0",
            (DONK_SID,),
        ).fetchone()[0]

    out["n_resolved"] = len(rows)
    if rows:
        values = sorted(r[0] for r in rows)
        n = len(values)
        pinned = sum(
            1 for v in values if any(abs(v - q) < 0.01 for q in TICK_QUANTA_MS)
        )
        out["pinned_pct"] = pinned / n * 100
        out["min_rt"] = values[0]
        p10_idx = max(0, int(n * 0.10) - 1)
        out["p10_rt"] = values[p10_idx]
    else:
        out["pinned_pct"] = None
        out["min_rt"] = None
        out["p10_rt"] = None

    t1_total = sum(t1_counts.values())
    out["n_t1_total"] = t1_total
    out["never_landed_pct"] = (
        t1_counts.get("never_landed", 0) / t1_total * 100 if t1_total else None
    )

    t0_total = sum(t0_counts.values())
    out["n_t0_total"] = t0_total
    out["never_visible_pct"] = (
        t0_counts.get("never_visible", 0) / t0_total * 100 if t0_total else None
    )

    out["n_b5_class"] = b5_class
    out["t1_counts"] = t1_counts
    out["t0_counts"] = t0_counts
    return out


def fmt_summary(stage: int, summary: dict) -> str:
    lines = [f"### Distribution-shape summary after stage N={stage}\n"]
    lines.append(f"- n_resolved (lands): **{summary.get('n_resolved')}**")
    if summary.get("min_rt") is not None:
        lines.append(f"- min rt_visible_to_land_ms: **{summary['min_rt']:.3f}ms**")
        lines.append(f"- p10 rt_visible_to_land_ms: **{summary['p10_rt']:.3f}ms**")
        lines.append(f"- %@tick-quantum pinning: **{summary['pinned_pct']:.1f}%**")
    else:
        lines.append("- min/p10/pinning: n/a (0 resolved rows)")
    if summary.get("never_landed_pct") is not None:
        lines.append(
            f"- never_landed%: **{summary['never_landed_pct']:.1f}%** "
            f"(of {summary['n_t1_total']} t1_source rows; {summary.get('t1_counts')})"
        )
    if summary.get("never_visible_pct") is not None:
        lines.append(
            f"- never_visible%: **{summary['never_visible_pct']:.1f}%** "
            f"(of {summary['n_t0_total']} t0_source rows; {summary.get('t0_counts')})"
        )
    lines.append(
        f"- b5-class impossible rows (t1=t0+1 AND angle>6deg): **{summary.get('n_b5_class')}**"
    )
    return "\n".join(lines)


def doubt_trigger(summary: dict) -> str | None:
    """Return a human-readable doubt-trigger reason, or None if clean (D-14/D-15)."""
    if summary.get("n_b5_class", 0) > 0:
        return f"b5-class impossible rows = {summary['n_b5_class']} (must be 0)"
    if summary.get("pinned_pct") is not None and summary["pinned_pct"] > 10.0:
        return f"tick-quantum pinning = {summary['pinned_pct']:.1f}% (>10% threshold)"
    if summary.get("min_rt") is not None and summary["min_rt"] < 0:
        return f"min rt_visible_to_land_ms = {summary['min_rt']} (negative)"
    if (
        summary.get("never_landed_pct") is not None
        and summary["never_landed_pct"] > 50.0
    ):
        return f"never_landed% = {summary['never_landed_pct']:.1f}% (>50% threshold)"
    if (
        summary.get("never_visible_pct") is not None
        and summary["never_visible_pct"] > 50.0
    ):
        return f"never_visible% = {summary['never_visible_pct']:.1f}% (>50% threshold)"
    return None


def run_stage(stage: int, corpus: str, db: str) -> int:
    from db_utils import get_next_match_id, init_db
    from outcome_first import _parse_demo_events, reconstruct_all_players

    init_db(db)

    all_demos = discover_donk_demos(corpus)
    target = all_demos[:stage]

    log(
        f"\n{'=' * 60}\nOF-3 RE-BATCH -- stage N={stage} -- {len(target)} demos\n{'=' * 60}\n"
    )
    report_append(f"\n## Stage N={stage} ({time.strftime('%Y-%m-%d %H:%M:%S')})\n")
    report_append("| # | demo | n_episodes | t0_source | t1_source | secs |")
    report_append("|-|-|-|-|-|-|")

    t_start = time.time()
    n_processed = 0
    n_skipped_no_donk = 0
    for i, demo_path in enumerate(target, 1):
        demo_name = demo_path.stem
        log(f"\n--- {i}/{len(target)}: {demo_name} ---")

        if of3_done(demo_name, db):
            log("SKIP: donk t0_source already populated (resume-safe)")
            with closing(sqlite3.connect(db)) as conn:
                n_eps = conn.execute(
                    "SELECT COUNT(*) FROM duel_episodes WHERE demo_name=? AND player_steamid=?",
                    (demo_name, DONK_SID),
                ).fetchone()[0]
            report_append(f"| {i} | {demo_name} | {n_eps} (skip) | - | - | - |")
            n_processed += 1
            continue

        # Quick check: does this demo even have donk events? Avoid wasted
        # delete+reconstruct cycles on demos with 0 donk episodes.
        try:
            hurt_df, _, _ = _parse_demo_events(str(demo_path))
        except Exception as exc:
            log(f"PARSE FAIL: {demo_name}: {exc}")
            report_append(f"| {i} | {demo_name} | PARSE FAIL | - | - | - |")
            continue

        from outcome_first import discover_player_sids

        sids = discover_player_sids(hurt_df)
        if DONK_SID not in sids:
            log("SKIP: demo has 0 donk events")
            report_append(f"| {i} | {demo_name} | 0 (no-donk) | - | - | - |")
            n_skipped_no_donk += 1
            continue

        deleted = delete_donk_timing_rows(demo_name, db)
        log(f"deleted {deleted} legacy/stale donk rows")

        match_id = get_next_match_id(db)
        t0 = time.time()
        results = reconstruct_all_players(
            str(demo_path), [DONK_SID], {DONK_SID: match_id}, db_path=db
        )
        dt = time.time() - t0
        n_eps = results.get(DONK_SID, 0)

        with closing(sqlite3.connect(db)) as conn:
            t0_src = conn.execute(
                "SELECT t0_source, COUNT(*) FROM duel_episodes "
                "WHERE demo_name=? AND player_steamid=? AND t0_source IS NOT NULL "
                "GROUP BY t0_source",
                (demo_name, DONK_SID),
            ).fetchall()
            t1_src = conn.execute(
                "SELECT t1_source, COUNT(*) FROM duel_episodes "
                "WHERE demo_name=? AND player_steamid=? AND t1_source IS NOT NULL "
                "GROUP BY t1_source",
                (demo_name, DONK_SID),
            ).fetchall()

        log(f"done {dt:.1f}s n_episodes={n_eps} t0_source={t0_src} t1_source={t1_src}")
        report_append(
            f"| {i} | {demo_name} | {n_eps} | {t0_src} | {t1_src} | {dt:.0f} |"
        )
        n_processed += 1

    total_min = (time.time() - t_start) / 60
    log(
        f"\nStage N={stage} done in {total_min:.1f}min "
        f"(processed={n_processed}, no-donk-skipped={n_skipped_no_donk})"
    )
    report_append(
        f"\n**Stage N={stage} finished:** {time.strftime('%Y-%m-%d %H:%M:%S')} "
        f"(elapsed {total_min:.1f}min, processed={n_processed}, no-donk-skipped={n_skipped_no_donk})\n"
    )

    summary = distribution_shape_summary(db)
    summary_md = fmt_summary(stage, summary)
    log("\n" + summary_md)
    report_append(summary_md)

    trigger = doubt_trigger(summary)
    if trigger:
        msg = f"\nDOUBT TRIGGER FIRED at stage N={stage}: {trigger}\n"
        log(msg)
        report_append(f"\n**DOUBT TRIGGER:** {trigger}\n")
        return 2

    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="OF-3 staged re-batch driver (D-14)")
    ap.add_argument("--stage", type=int, choices=[1, 5, 81], required=True)
    ap.add_argument("--db", type=str, default="analytics.db")
    ap.add_argument("--corpus", type=str, default=CORPUS_DEFAULT)
    args = ap.parse_args()

    return run_stage(args.stage, args.corpus, args.db)


if __name__ == "__main__":
    sys.exit(main())
