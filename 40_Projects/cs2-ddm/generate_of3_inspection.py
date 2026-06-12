"""Generate of3_inspection.md -- 7-section manual review artifact for the OF-3
staged re-batch (D-14).

Queries `duel_episodes` EXCLUSIVELY (Pitfall 5 -- never the deprecated legacy
per-engagement table) via sqlite3 cursor.fetchall() (never the pandas SQL
reader on sid columns). EVERY table carries `crosshair_angle_at_t0_deg`, the
physics-bounded column mandated by the B-5 post-mortem
(feedback_inspection_without_physics_sanity_columns_misses_bugs_2026_05_19).

Sections:
  1. Aggregate -- n_episodes, t0_source/t1_source breakdowns, rt distribution
  2. Per-unit (per-demo) -- n_episodes, median rt, %@tick-quantum pinning, max angle
  3. Per-actor (donk) -- median rt, never_landed%, crosshair-angle buckets (b5_smoking_gun mirror)
  4. Full list of resolved rows (capped sample if huge)
  5. Anomaly buckets -- b5-class impossible rows, negative rt, low median rt, tick-quantum clusters
  6. Random sample (~20 rows) for manual spot-check
  7. Pre-vs-post -- episode counts vs OF-2 baseline (won=1428/lost=1090, D-08)

Ends with an explicit acceptance checklist (model: of2_parity_inspection.md).

CLI: py generate_of3_inspection.py --db <path> --out of3_inspection.md
"""

from __future__ import annotations

import argparse
import sqlite3
import statistics
from contextlib import closing
from pathlib import Path

DONK_SID = 76561198386265483
TICK_QUANTA_MS = [15.625, 31.25, 46.875, 62.5]
TARGET_REACHED_THRESHOLD = 3.0  # config.py D-02 lock; b5-class = > 2x this

# OF-2 baseline (of2_parity_inspection.md Section 1, D-08 invariant)
OF2_BASELINE_WON = 1428
OF2_BASELINE_LOST = 1090


def fmt_num(v) -> str:
    if v is None:
        return "-"
    if isinstance(v, float):
        return f"{v:.2f}"
    return str(v)


def pct(p: float, vals: list[float]) -> float | None:
    if not vals:
        return None
    if len(vals) < 2:
        return vals[0]
    return statistics.quantiles(vals, n=100)[max(0, min(98, int(p) - 1))]


def angle_bucket(angle: float | None) -> str:
    if angle is None:
        return "n/a"
    if angle <= 1:
        return "<=1"
    if angle <= 3:
        return "1-3"
    if angle <= 10:
        return "3-10"
    if angle <= 30:
        return "10-30"
    return "30+"


def main() -> int:
    ap = argparse.ArgumentParser(description="OF-3 inspection artifact generator")
    ap.add_argument("--db", type=str, default="analytics.db")
    ap.add_argument("--out", type=str, default="of3_inspection.md")
    args = ap.parse_args()

    out: list[str] = []
    out.append("# OF-3 Re-batch Inspection -- donk timing pass (D-14)\n")
    out.append(f"**Source:** `{args.db}` (`duel_episodes` table only -- Pitfall 5)\n")
    out.append(f"**Player:** donk ({DONK_SID})\n")
    out.append(
        "**Purpose:** Independent manual review artifact for the N=5 checkpoint "
        "(D-14). Every table carries `crosshair_angle_at_t0_deg` -- the "
        "physics-bounded column mandated by the B-5 post-mortem.\n"
    )
    out.append("\n---\n\n")

    with closing(sqlite3.connect(args.db)) as conn:
        # ── Section 1: Aggregate ────────────────────────────────────────
        out.append("## 1. Aggregate\n\n")

        n_total = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=?",
            (DONK_SID,),
        ).fetchone()[0]
        n_t0_resolved = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=? AND t0_tick IS NOT NULL",
            (DONK_SID,),
        ).fetchone()[0]
        n_t1_resolved = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=? AND t1_tick IS NOT NULL",
            (DONK_SID,),
        ).fetchone()[0]

        t0_source_counts = dict(
            conn.execute(
                "SELECT t0_source, COUNT(*) FROM duel_episodes "
                "WHERE player_steamid=? AND t0_source IS NOT NULL GROUP BY t0_source",
                (DONK_SID,),
            ).fetchall()
        )
        t1_source_counts = dict(
            conn.execute(
                "SELECT t1_source, COUNT(*) FROM duel_episodes "
                "WHERE player_steamid=? AND t1_source IS NOT NULL GROUP BY t1_source",
                (DONK_SID,),
            ).fetchall()
        )

        rt_rows = conn.execute(
            "SELECT rt_visible_to_land_ms, crosshair_angle_at_t0_deg FROM duel_episodes "
            "WHERE player_steamid=? AND t1_source='lands' AND rt_visible_to_land_ms IS NOT NULL",
            (DONK_SID,),
        ).fetchall()
        rt_vals = sorted(r[0] for r in rt_rows)

        out.append("| Metric | Value |\n|-|-|\n")
        out.append(f"| n_episodes (total, donk) | {n_total} |\n")
        out.append(f"| n with t0_tick resolved | {n_t0_resolved} |\n")
        out.append(f"| n with t1_tick resolved | {n_t1_resolved} |\n")
        t0_total = sum(t0_source_counts.values())
        for src, cnt in sorted(t0_source_counts.items()):
            p = cnt / t0_total * 100 if t0_total else 0.0
            out.append(f"| t0_source = {src} | {cnt} ({p:.1f}%) |\n")
        t1_total = sum(t1_source_counts.values())
        for src, cnt in sorted(t1_source_counts.items()):
            p = cnt / t1_total * 100 if t1_total else 0.0
            out.append(f"| t1_source = {src} | {cnt} ({p:.1f}%) |\n")

        if rt_vals:
            out.append(f"| rt_visible_to_land_ms min | {fmt_num(rt_vals[0])} |\n")
            out.append(f"| rt_visible_to_land_ms p10 | {fmt_num(pct(10, rt_vals))} |\n")
            out.append(f"| rt_visible_to_land_ms p25 | {fmt_num(pct(25, rt_vals))} |\n")
            out.append(
                f"| rt_visible_to_land_ms median | {fmt_num(pct(50, rt_vals))} |\n"
            )
            out.append(
                f"| rt_visible_to_land_ms mean | {fmt_num(sum(rt_vals) / len(rt_vals))} |\n"
            )
            out.append(f"| rt_visible_to_land_ms max | {fmt_num(rt_vals[-1])} |\n")
            angles_on_lands = [r[1] for r in rt_rows if r[1] is not None]
            out.append(
                f"| crosshair_angle_at_t0_deg (lands) max | "
                f"{fmt_num(max(angles_on_lands)) if angles_on_lands else '-'} |\n"
            )
        else:
            out.append("| rt_visible_to_land_ms distribution | n/a (0 lands rows) |\n")

        out.append("\n---\n\n")

        # ── Section 2: Per-unit (per-demo) ──────────────────────────────
        out.append("## 2. Per-Demo Breakdown\n\n")
        out.append(
            "| Demo | n_episodes | median rt_ms | %@tick-quantum | max crosshair_angle_at_t0_deg |\n"
            "|-|-|-|-|-|\n"
        )
        demos = [
            r[0]
            for r in conn.execute(
                "SELECT DISTINCT demo_name FROM duel_episodes WHERE player_steamid=? "
                "AND t0_source IS NOT NULL ORDER BY demo_name",
                (DONK_SID,),
            ).fetchall()
        ]
        for demo in demos:
            n_eps = conn.execute(
                "SELECT COUNT(*) FROM duel_episodes WHERE demo_name=? AND player_steamid=?",
                (demo, DONK_SID),
            ).fetchone()[0]
            rows = conn.execute(
                "SELECT rt_visible_to_land_ms, crosshair_angle_at_t0_deg FROM duel_episodes "
                "WHERE demo_name=? AND player_steamid=? AND t1_source='lands' "
                "AND rt_visible_to_land_ms IS NOT NULL",
                (demo, DONK_SID),
            ).fetchall()
            d_rts = sorted(r[0] for r in rows)
            d_angles = [r[1] for r in rows if r[1] is not None]
            if d_rts:
                med = pct(50, d_rts)
                pinned = sum(
                    1 for v in d_rts if any(abs(v - q) < 0.01 for q in TICK_QUANTA_MS)
                )
                pinned_pct = pinned / len(d_rts) * 100
                max_angle = max(d_angles) if d_angles else None
                out.append(
                    f"| {demo} | {n_eps} | {fmt_num(med)} | {pinned_pct:.1f}% | {fmt_num(max_angle)} |\n"
                )
            else:
                out.append(f"| {demo} | {n_eps} | - | - | - |\n")

        out.append("\n---\n\n")

        # ── Section 3: Per-actor (donk) ─────────────────────────────────
        out.append(
            "## 3. Per-Actor (donk) -- Crosshair-Angle Distribution on Lands\n\n"
        )
        if rt_vals:
            never_landed = t1_source_counts.get("never_landed", 0)
            never_landed_pct = never_landed / t1_total * 100 if t1_total else 0.0
            out.append(
                f"- median rt_visible_to_land_ms: **{fmt_num(pct(50, rt_vals))}**\n"
            )
            out.append(
                f"- never_landed%: **{never_landed_pct:.1f}%** "
                f"({never_landed} of {t1_total} t1_source rows)\n\n"
            )
            angles_on_lands = [r[1] for r in rt_rows if r[1] is not None]
            buckets = {"<=1": 0, "1-3": 0, "3-10": 0, "10-30": 0, "30+": 0}
            for a in angles_on_lands:
                buckets[angle_bucket(a)] += 1
            n_ang = len(angles_on_lands) or 1
            out.append(
                "| angle_deg@T0 (on lands) | count | pct | interpretation |\n"
                "|-|-|-|-|\n"
            )
            interp = {
                "<=1": "already on-target -- pre-aim-class, defensible 1-tick land",
                "1-3": "borderline, defensible near-instant land",
                "3-10": "minor adjust -- multi-tick land expected",
                "10-30": "flick -- multi-tick land expected",
                "30+": "hard flick -- multi-tick land expected",
            }
            for b in ["<=1", "1-3", "3-10", "10-30", "30+"]:
                cnt = buckets[b]
                out.append(
                    f"| {b} deg | {cnt} | {cnt/n_ang*100:.1f}% | {interp[b]} |\n"
                )
        else:
            out.append("*(no lands rows)*\n")

        out.append("\n---\n\n")

        # ── Section 4: Full list of resolved rows (capped) ──────────────
        out.append("## 4. Full List of Resolved Rows (lands, capped at 200)\n\n")
        out.append(
            "| demo | round/tick | t0_tick | t1_tick | t2 (first_event_tick) | "
            "rt_visible_to_land_ms | crosshair_angle_at_t0_deg | t1_source |\n"
            "|-|-|-|-|-|-|-|-|\n"
        )
        full_rows = conn.execute(
            "SELECT demo_name, first_event_tick, t0_tick, t1_tick, "
            "rt_visible_to_land_ms, crosshair_angle_at_t0_deg, t1_source "
            "FROM duel_episodes WHERE player_steamid=? AND t1_source IS NOT NULL "
            "ORDER BY demo_name, first_event_tick LIMIT 200",
            (DONK_SID,),
        ).fetchall()
        for demo, t2, t0t, t1t, rt, angle, src in full_rows:
            out.append(
                f"| {demo} | {t2} | {fmt_num(t0t)} | {fmt_num(t1t)} | {t2} | "
                f"{fmt_num(rt)} | {fmt_num(angle)} | {src} |\n"
            )
        n_total_resolved = conn.execute(
            "SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=? AND t1_source IS NOT NULL",
            (DONK_SID,),
        ).fetchone()[0]
        if n_total_resolved > 200:
            out.append(f"\n*(showing 200 of {n_total_resolved} rows)*\n")

        out.append("\n---\n\n")

        # ── Section 5: Anomaly buckets ───────────────────────────────────
        out.append("## 5. Anomaly Buckets\n\n")

        # (a) b5-class impossible rows
        b5_rows = conn.execute(
            "SELECT demo_name, first_event_tick, t0_tick, t1_tick, crosshair_angle_at_t0_deg, "
            "rt_visible_to_land_ms FROM duel_episodes WHERE player_steamid=? "
            f"AND t1_tick = t0_tick + 1 AND crosshair_angle_at_t0_deg > {2 * TARGET_REACHED_THRESHOLD}",
            (DONK_SID,),
        ).fetchall()
        out.append(
            f"### (a) b5-class impossible rows: t1=t0+1 AND angle > 2*TARGET_REACHED_THRESHOLD ({2 * TARGET_REACHED_THRESHOLD} deg)\n\n"
        )
        out.append(f"**Count: {len(b5_rows)}** (MUST be 0)\n\n")
        if b5_rows:
            out.append(
                "| demo | first_event_tick | t0_tick | t1_tick | crosshair_angle_at_t0_deg | rt_ms |\n"
                "|-|-|-|-|-|-|\n"
            )
            for r in b5_rows:
                out.append(
                    f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {fmt_num(r[4])} | {fmt_num(r[5])} |\n"
                )
        out.append("\n")

        # (b) negative rt
        neg_rt = conn.execute(
            "SELECT demo_name, first_event_tick, t0_tick, t1_tick, crosshair_angle_at_t0_deg, "
            "rt_visible_to_land_ms FROM duel_episodes WHERE player_steamid=? "
            "AND rt_visible_to_land_ms < 0",
            (DONK_SID,),
        ).fetchall()
        out.append(
            f"### (b) negative rt_visible_to_land_ms\n\n**Count: {len(neg_rt)}**\n\n"
        )
        if neg_rt:
            out.append(
                "| demo | first_event_tick | t0_tick | t1_tick | crosshair_angle_at_t0_deg | rt_ms |\n"
                "|-|-|-|-|-|-|\n"
            )
            for r in neg_rt:
                out.append(
                    f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {fmt_num(r[4])} | {fmt_num(r[5])} |\n"
                )
        out.append("\n")

        # (c) per-demo median rt < 100ms
        out.append(
            "### (c) per-demo median rt_visible_to_land_ms < 100ms (physiology floor flag)\n\n"
        )
        low_median_demos = []
        for demo in demos:
            d_rts = sorted(
                r[0]
                for r in conn.execute(
                    "SELECT rt_visible_to_land_ms FROM duel_episodes WHERE demo_name=? "
                    "AND player_steamid=? AND t1_source='lands' AND rt_visible_to_land_ms IS NOT NULL",
                    (demo, DONK_SID),
                ).fetchall()
            )
            if d_rts:
                med = pct(50, d_rts)
                if med is not None and med < 100:
                    low_median_demos.append((demo, med, len(d_rts)))
        if low_median_demos:
            out.append("| demo | median_rt_ms | n |\n|-|-|-|\n")
            for demo, med, n in low_median_demos:
                out.append(f"| {demo} | {fmt_num(med)} | {n} |\n")
        else:
            out.append("*(none)*\n")
        out.append("\n")

        # (d) tick-quantum clusters > 10%
        out.append("### (d) tick-quantum clusters >10% (aggregate)\n\n")
        if rt_vals:
            out.append("| quantum_ms | count | pct |\n|-|-|-|\n")
            for q in TICK_QUANTA_MS:
                cnt = sum(1 for v in rt_vals if abs(v - q) < 0.01)
                p = cnt / len(rt_vals) * 100
                flag = " <-- >10%" if p > 10 else ""
                out.append(f"| {q} | {cnt} | {p:.1f}%{flag} |\n")
        else:
            out.append("*(no lands rows)*\n")

        out.append("\n---\n\n")

        # ── Section 6: Random sample (~20 rows) ──────────────────────────
        out.append("## 6. Random Sample (~20 rows, manual spot-check)\n\n")
        out.append(
            "| demo | first_event_tick | t0_tick | t0_source | t1_tick | t1_source | "
            "rt_visible_to_land_ms | rt_visible_to_hit_ms | crosshair_angle_at_t0_deg |\n"
            "|-|-|-|-|-|-|-|-|-|\n"
        )
        sample_rows = conn.execute(
            "SELECT demo_name, first_event_tick, t0_tick, t0_source, t1_tick, t1_source, "
            "rt_visible_to_land_ms, rt_visible_to_hit_ms, crosshair_angle_at_t0_deg "
            "FROM duel_episodes WHERE player_steamid=? AND t0_source IS NOT NULL "
            "ORDER BY RANDOM() LIMIT 20",
            (DONK_SID,),
        ).fetchall()
        for r in sample_rows:
            out.append(
                f"| {r[0]} | {r[1]} | {fmt_num(r[2])} | {r[3]} | {fmt_num(r[4])} | {r[5]} | "
                f"{fmt_num(r[6])} | {fmt_num(r[7])} | {fmt_num(r[8])} |\n"
            )

        out.append("\n---\n\n")

        # ── Section 7: Pre-vs-post ────────────────────────────────────────
        out.append("## 7. Pre-vs-Post (episode counts vs OF-2 baseline, D-08)\n\n")
        won_lost = dict(
            conn.execute(
                "SELECT outcome, COUNT(*) FROM duel_episodes WHERE player_steamid=? GROUP BY outcome",
                (DONK_SID,),
            ).fetchall()
        )
        cur_won = won_lost.get("won", 0)
        cur_lost = won_lost.get("lost", 0)
        out.append(
            "| Metric | OF-2 baseline | Current (this stage) | Delta |\n|-|-|-|-|\n"
        )
        out.append(
            f"| won | {OF2_BASELINE_WON} | {cur_won} | {cur_won - OF2_BASELINE_WON} |\n"
        )
        out.append(
            f"| lost | {OF2_BASELINE_LOST} | {cur_lost} | {cur_lost - OF2_BASELINE_LOST} |\n"
        )
        out.append(
            "\nTiming pass adds columns, never drops episodes (D-08). For a partial "
            "stage (N=1 or N=5), won/lost will be a SUBSET of the OF-2 baseline -- "
            "deltas are negative until N=81 completes, where deltas MUST be 0.\n"
        )
        out.append(
            "\n*Distribution of rt_visible_to_land_ms is NEW (no OF-2 baseline to compare).*\n"
        )

    out.append("\n---\n\n")

    # ── Acceptance checklist ────────────────────────────────────────────
    out.append("## Acceptance Checklist\n\n")
    out.append("- [ ] Section 5(a): 0 b5-class impossible rows\n")
    out.append("- [ ] Section 5(d): pinning <10% at every tick-quantum\n")
    out.append("- [ ] Section 1/3: never_landed% is plausible (2-50%)\n")
    out.append("- [ ] Section 5(c): no per-player median rt <100ms unexplained\n")
    out.append(
        "- [ ] Section 7: episode counts unchanged vs OF-2 (only true at N=81; "
        "for N=1/N=5 confirm no episodes were DROPPED for the processed demos)\n"
    )

    Path(args.out).write_text("".join(out), encoding="utf-8")
    print(f"Wrote {args.out} ({len(''.join(out))} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
