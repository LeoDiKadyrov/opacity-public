"""Full corpus watcher — wait for rebatch_full.log completion, run final SQL
distribution check across ALL post-fix demos, write final_report.md.

Acceptance criteria same as overnight_watcher.py but applied to the full
corpus (top-10 + 132 remaining = ~142 demos, ~4900 expected engagements).

Halts cleanly on failure or yellow signal. Writes to final_report.md
incrementally so progress visible at any point.
"""

from __future__ import annotations

import os
import sqlite3
import statistics
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.resolve()
DB = REPO / "analytics.db"
LOG = REPO / "rebatch_full.log"
REPORT = REPO / "final_report.md"


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write(s: str, append: bool = True) -> None:
    mode = "a" if append else "w"
    with open(REPORT, mode, encoding="utf-8") as f:
        f.write(s)


def wait_for_log_marker(log_path: Path, ok_markers: list[str], fail_markers: list[str]) -> str:
    while True:
        if log_path.exists():
            try:
                content = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception:
                content = ""
            for ok in ok_markers:
                if ok in content:
                    return "ok"
            for f in fail_markers:
                if f in content:
                    return "fail"
        time.sleep(120)


def fmt(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.1f}"
    return str(v)


def pct(p: float, vals: list[float]) -> float:
    if not vals:
        return float("nan")
    if len(vals) < 2:
        return vals[0]
    return statistics.quantiles(vals, n=100)[max(0, min(98, int(p) - 1))]


def main() -> int:
    write(f"# Full corpus rebatch — final report\n\n", append=False)
    write(f"**Started watcher:** {stamp()}\n\n")
    write(f"Waiting for `rebatch_full.log` completion marker (poll every 120s).\n\n")
    write("---\n\n")

    outcome = wait_for_log_marker(
        LOG,
        ok_markers=["ALL ", "DEMOS COMPLETE in "],
        fail_markers=["FAILED on"],
    )
    write(f"**Rebatch finished at {stamp()}: {outcome.upper()}**\n\n")

    if outcome == "fail":
        write("## HALTED — rebatch failed\n\nLast 40 log lines:\n\n```\n")
        try:
            tail = LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            write("\n".join(tail))
        except Exception as e:
            write(f"(failed to read log: {e})")
        write("\n```\n")
        return 1

    # ── Aggregate metrics ──────────────────────────────────────────────────
    write("## Aggregate Metrics (entire post-fix corpus)\n\n")
    conn = sqlite3.connect(str(DB))
    agg = conn.execute(
        """SELECT
              COUNT(*), MIN(rt_visible_to_aim_ms), MAX(rt_visible_to_aim_ms),
              SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END),
              SUM(CASE WHEN rt_visible_to_aim_ms = 0 THEN 1 ELSE 0 END),
              SUM(CASE WHEN t1_source='pre_aimed' THEN 1 ELSE 0 END),
              SUM(CASE WHEN t1_source='sustained_aim' THEN 1 ELSE 0 END),
              SUM(CASE WHEN t1_source='none' THEN 1 ELSE 0 END)
            FROM engagements
            WHERE rt_visible_to_aim_ms IS NOT NULL
              AND t1_source IS NOT NULL"""
    ).fetchone()
    n, mn, mx, at125, preaim_rt0, preaim_flag, sust, none_cnt = agg

    rts = [r[0] for r in conn.execute(
        "SELECT rt_visible_to_aim_ms FROM engagements WHERE rt_visible_to_aim_ms IS NOT NULL AND t1_source IS NOT NULL ORDER BY rt_visible_to_aim_ms"
    ).fetchall()]

    p10 = pct(10, rts)
    p25 = pct(25, rts)
    p50 = pct(50, rts)
    p75 = pct(75, rts)
    p90 = pct(90, rts)

    write("| Metric | Value |\n|-|-|\n")
    write(f"| n_total | {n} |\n")
    write(f"| min_ms | **{fmt(mn)}** |\n")
    write(f"| p10_ms | {fmt(p10)} |\n")
    write(f"| p25_ms | {fmt(p25)} |\n")
    write(f"| median_ms | {fmt(p50)} |\n")
    write(f"| p75_ms | {fmt(p75)} |\n")
    write(f"| p90_ms | {fmt(p90)} |\n")
    write(f"| max_ms | {fmt(mx)} |\n")
    write(f"| n_at_125ms | {at125} ({at125/n*100:.2f}%) |\n")
    write(f"| n_pre_aimed (rt=0) | {preaim_rt0} |\n")
    write(f"| n_pre_aimed (flag) | **{preaim_flag}** |\n")
    write(f"| n_sustained_aim | {sust} |\n")
    write(f"| n_none_sentinel | {none_cnt} |\n")
    write(f"| pre_aim rate | **{preaim_flag/n*100:.1f}%** |\n")
    write("\n")

    # ── Acceptance ─────────────────────────────────────────────────────────
    reasons = []
    if n == 0:
        reasons.append("n_total=0")
    if mn is None or mn >= 125.0:
        reasons.append(f"min_ms={mn} >= 125ms — floor NOT cleared")
    pct125 = (at125 / n * 100) if n else 0
    if pct125 > 10.0:
        reasons.append(f"pct_at_125ms={pct125:.1f}% > 10% threshold")
    if preaim_rt0 != preaim_flag:
        reasons.append(f"n_pre_aimed_rt0={preaim_rt0} != n_pre_aimed_flag={preaim_flag} — flag column inconsistent")

    # Per-demo regression check
    per_demo = conn.execute(
        """SELECT demo_name, COUNT(*), MIN(rt_visible_to_aim_ms),
                  SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END),
                  SUM(CASE WHEN t1_source='pre_aimed' THEN 1 ELSE 0 END)
           FROM engagements
           WHERE rt_visible_to_aim_ms IS NOT NULL AND t1_source IS NOT NULL
           GROUP BY demo_name
           ORDER BY 2 DESC"""
    ).fetchall()
    bad_demos = [(d, n_d, mn_d, a, p) for d, n_d, mn_d, a, p in per_demo if mn_d is None or mn_d >= 125.0]
    if bad_demos:
        names = ", ".join(d for d, _, _, _, _ in bad_demos[:5])
        reasons.append(f"per-demo regression — {len(bad_demos)} demos with min >= 125ms (first 5: {names})")

    if reasons:
        write(f"## ACCEPTANCE FAILED at {stamp()}\n\n")
        for r in reasons:
            write(f"- {r}\n")
        write("\n")
    else:
        write(f"## ALL CLEAR — full corpus acceptance PASSED at {stamp()}\n\n")
        write("Phase A item 6 (full corpus re-batch) complete. Cited landing numbers can now be refreshed in place.\n\n")

    # ── Per-demo table ─────────────────────────────────────────────────────
    write(f"## Per-Demo Summary ({len(per_demo)} demos)\n\n")
    write("| Demo | N | min | n_at_125 | n_pre_aimed |\n|-|-|-|-|-|\n")
    for d, n_d, mn_d, a, p in per_demo:
        out = f"| {d} | {n_d} | {fmt(mn_d)} | {a} | {p} |\n"
        write(out)
    write("\n")

    # ── Per-player table (top 30 by count) ─────────────────────────────────
    write("## Per-Player Summary (≥30 engagements)\n\n")
    players = conn.execute(
        """SELECT player_steamid, COUNT(*), MIN(rt_visible_to_aim_ms),
                  SUM(CASE WHEN t1_source='pre_aimed' THEN 1 ELSE 0 END)
           FROM engagements
           WHERE rt_visible_to_aim_ms IS NOT NULL AND t1_source IS NOT NULL
             AND player_steamid IS NOT NULL
           GROUP BY player_steamid
           HAVING COUNT(*) >= 30
           ORDER BY 2 DESC"""
    ).fetchall()
    write("| SteamID64 | n_engagements | min_rt | n_pre_aimed | pre_aim % |\n|-|-|-|-|-|\n")
    for sid, n_p, mn_p, npa in players:
        write(f"| {sid} | {n_p} | {fmt(mn_p)} | {npa} | {npa/n_p*100:.1f}% |\n")
    write("\n")

    # ── donk specific ──────────────────────────────────────────────────────
    DONK = 76561198386265483
    donk = conn.execute(
        f"""SELECT COUNT(*), MIN(rt_visible_to_aim_ms),
                   SUM(CASE WHEN t1_source='pre_aimed' THEN 1 ELSE 0 END)
            FROM engagements
            WHERE player_steamid={DONK}
              AND rt_visible_to_aim_ms IS NOT NULL
              AND t1_source IS NOT NULL"""
    ).fetchone()
    if donk[0] > 0:
        donk_rts = [r[0] for r in conn.execute(
            f"SELECT rt_visible_to_aim_ms FROM engagements WHERE player_steamid={DONK} AND rt_visible_to_aim_ms IS NOT NULL AND t1_source IS NOT NULL ORDER BY rt_visible_to_aim_ms"
        ).fetchall()]
        write(f"## donk Headline (SteamID64 {DONK})\n\n")
        write(f"- n = {donk[0]} engagements (post-fix)\n")
        write(f"- min = {fmt(donk[1])} ms\n")
        write(f"- median = {fmt(pct(50, donk_rts))} ms (previously cited: 172ms)\n")
        write(f"- pre_aim count = {donk[2]} ({donk[2]/donk[0]*100:.1f}% pre_aim rate)\n\n")

    conn.close()
    return 0 if not reasons else 2


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception:
        write(f"\n## EXCEPTION at {stamp()}\n\n```\n{traceback.format_exc()}\n```\n")
        sys.exit(99)
