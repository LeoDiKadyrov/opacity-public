"""Overnight watcher — fully autonomous Phase A item 6 expansion.

Waits for the in-flight `staged_rebatch.py` (top-5 demos) to finish, runs
the SC-4-style SQL distribution check, and conditionally kicks off a
top-10 expansion if all acceptance criteria pass. All progress + verdicts
go to `overnight_report.md` for morning review.

Runs DETACHED from Claude session via PowerShell Start-Process. No user
intervention required between top-5 finish and top-10 ship. Halts cleanly
if any check fails — never auto-expands on a yellow signal.

Acceptance criteria (per Phase 10 Plan 02 SC-4 + project staged-validation
pattern [[feedback-staged-validation-with-doubt-threshold-2026-05-16]]):
  - n_total > 0
  - aggregate min_ms < 125.0  (B-1 floor cleared)
  - aggregate pct_at_125ms <= 10%  (no value pinning)
  - n_pre_aimed_rt0 == n_pre_aimed_flag  (B-4 flag column consistent)
  - no per-demo regression (every demo's min < 125ms)

Top-5 (already running):
  spirit-vs-the-mongolz-m2-ancient, passion-ua-vs-faze-m2-nuke,
  mouz-vs-spirit-m2-mirage, spirit-vs-the-mongolz-m2-mirage,
  spirit-vs-vitality-m1-mirage

Next-5 (auto-expansion candidates, ranks 6-10 by row count):
  spirit-vs-virtus-pro-m1-ancient, faze-vs-pain-m2-dust2,
  spirit-vs-the-mongolz-m1-nuke, faze-vs-pain-m1-nuke,
  passion-ua-vs-faze-m1-anubis
"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).parent.resolve()
DB = REPO / "analytics.db"
TOP5_LOG = REPO / "rebatch_top5.log"
TOP10_LOG = REPO / "rebatch_top10.log"
REPORT = REPO / "overnight_report.md"

UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

TOP5_DEMOS = [
    ("spirit-vs-the-mongolz-m2-ancient.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-the-mongolz-m2-ancient.dem"),
    ("passion-ua-vs-faze-m2-nuke.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/faze/passion-ua-vs-faze-m2-nuke.dem"),
    ("mouz-vs-spirit-m2-mirage.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/mouz-vs-spirit-m2-mirage.dem"),
    ("spirit-vs-the-mongolz-m2-mirage.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-the-mongolz-m2-mirage.dem"),
    ("spirit-vs-vitality-m1-mirage.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-vitality-m1-mirage.dem"),
]

NEXT5_DEMOS = [
    ("spirit-vs-virtus-pro-m1-ancient.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-virtus-pro-m1-ancient.dem"),
    ("faze-vs-pain-m2-dust2.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/faze/faze-vs-pain-m2-dust2.dem"),
    ("spirit-vs-the-mongolz-m1-nuke.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-the-mongolz-m1-nuke.dem"),
    ("faze-vs-pain-m1-nuke.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/faze/faze-vs-pain-m1-nuke.dem"),
    ("passion-ua-vs-faze-m1-anubis.dem",
     "D:/Obsidian/opacity/40_Projects/for_analysis/faze/passion-ua-vs-faze-m1-anubis.dem"),
]


def stamp() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def write(content: str, append: bool = True) -> None:
    mode = "a" if append else "w"
    with open(REPORT, mode, encoding="utf-8") as f:
        f.write(content)


def wait_for_log_marker(log_path: Path, ok_markers: list[str], fail_markers: list[str]) -> str:
    """Poll log every 60s until any ok or fail marker present."""
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
        time.sleep(60)


def sql_check(demo_names: list[str]) -> dict:
    conn = sqlite3.connect(str(DB))
    placeholders = ",".join("?" for _ in demo_names)
    overall = conn.execute(
        f"""SELECT
              COUNT(*) AS n,
              MIN(rt_visible_to_aim_ms) AS mn,
              MAX(rt_visible_to_aim_ms) AS mx,
              SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END) AS at125,
              SUM(CASE WHEN rt_visible_to_aim_ms = 0 THEN 1 ELSE 0 END) AS preaim_rt0,
              SUM(CASE WHEN t1_source = 'pre_aimed' THEN 1 ELSE 0 END) AS preaim_flag,
              SUM(CASE WHEN t1_source = 'sustained_aim' THEN 1 ELSE 0 END) AS sust,
              SUM(CASE WHEN t1_source = 'none' THEN 1 ELSE 0 END) AS none_cnt
            FROM engagements
            WHERE demo_name IN ({placeholders})
              AND rt_visible_to_aim_ms IS NOT NULL""",
        demo_names,
    ).fetchone()
    per_demo = conn.execute(
        f"""SELECT demo_name,
                   COUNT(*) AS n,
                   MIN(rt_visible_to_aim_ms) AS mn,
                   SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END) AS at125
            FROM engagements
            WHERE demo_name IN ({placeholders})
              AND rt_visible_to_aim_ms IS NOT NULL
            GROUP BY demo_name""",
        demo_names,
    ).fetchall()
    conn.close()
    n, mn, mx, at125, preaim_rt0, preaim_flag, sust, none_cnt = overall
    return {
        "n_total": n,
        "min_ms": mn,
        "max_ms": mx,
        "n_at_125ms": at125,
        "n_pre_aimed_rt0": preaim_rt0,
        "n_pre_aimed_flag": preaim_flag,
        "n_sustained_aim": sust,
        "n_none_sentinel": none_cnt,
        "pct_at_125ms": (at125 / n * 100) if n else 0,
        "per_demo": [tuple(r) for r in per_demo],
    }


def acceptance_check(m: dict) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if m["n_total"] == 0:
        return False, ["n_total=0 — no engagements produced"]
    if m["min_ms"] is None or m["min_ms"] >= 125.0:
        reasons.append(f"min_ms={m['min_ms']} — floor NOT cleared (must be < 125ms)")
    if m["pct_at_125ms"] > 10.0:
        reasons.append(f"pct_at_125ms={m['pct_at_125ms']:.1f}% > 10% threshold")
    if m["n_pre_aimed_rt0"] != m["n_pre_aimed_flag"]:
        reasons.append(
            f"n_pre_aimed_rt0={m['n_pre_aimed_rt0']} != n_pre_aimed_flag={m['n_pre_aimed_flag']} — flag column inconsistent"
        )
    per_demo_bad = [(d, n, mn, a) for d, n, mn, a in m["per_demo"] if mn is None or mn >= 125.0]
    if per_demo_bad:
        names = ", ".join(d for d, _, _, _ in per_demo_bad)
        reasons.append(f"per-demo regression — {len(per_demo_bad)} demos with min >= 125ms: {names}")
    return (len(reasons) == 0), reasons


def fmt_metrics(m: dict, label: str) -> str:
    lines = [
        f"### {label}",
        "",
        "```",
        f"n_total:             {m['n_total']}",
        f"min_ms:              {m['min_ms']}",
        f"max_ms:              {m['max_ms']}",
        f"n_at_125ms:          {m['n_at_125ms']} ({m['pct_at_125ms']:.1f}%)",
        f"n_pre_aimed (rt=0):  {m['n_pre_aimed_rt0']}",
        f"n_pre_aimed (flag):  {m['n_pre_aimed_flag']}",
        f"n_sustained_aim:     {m['n_sustained_aim']}",
        f"n_none_sentinel:     {m['n_none_sentinel']}",
        "```",
        "",
        "Per-demo:",
        "",
        "| Demo | N | min_ms | n_at_125 |",
        "|-|-|-|-|",
    ]
    for d, n, mn, a in m["per_demo"]:
        lines.append(f"| {d} | {n} | {mn} | {a} |")
    lines.append("")
    return "\n".join(lines)


def delete_prefix_rows(demo_names: list[str]) -> int:
    conn = sqlite3.connect(str(DB))
    placeholders = ",".join("?" for _ in demo_names)
    before = conn.execute(
        f"SELECT COUNT(*) FROM engagements WHERE demo_name IN ({placeholders})",
        demo_names,
    ).fetchone()[0]
    conn.execute(f"DELETE FROM engagements WHERE demo_name IN ({placeholders})", demo_names)
    conn.execute(f"DELETE FROM duel_attempts WHERE demo_name IN ({placeholders})", demo_names)
    conn.commit()
    conn.close()
    return before


def run_demo_loop(demos: list[tuple[str, str]], log_path: Path) -> tuple[bool, str | None]:
    log_path.write_text("", encoding="utf-8")
    for i, (name, path) in enumerate(demos, 1):
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{'=' * 60}\nDEMO {i}/{len(demos)}: {name}\n{'=' * 60}\n")
        if not Path(path).exists():
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"FAIL: demo file not found: {path}\n")
            return False, f"Demo {i} ({name}) — file not found at {path}"
        t0 = time.time()
        with open(log_path, "a", encoding="utf-8") as out_fh:
            result = subprocess.run(
                [sys.executable, "multi_player_analyze.py", path],
                cwd=str(REPO),
                env=UTF8_ENV,
                stdout=out_fh,
                stderr=subprocess.STDOUT,
            )
        dt = time.time() - t0
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\nDemo {i}/{len(demos)} done in {dt:.1f}s (exit {result.returncode})\n")
        if result.returncode != 0:
            return False, f"Demo {i} ({name}) failed exit {result.returncode} after {dt:.1f}s"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'=' * 60}\nALL {len(demos)} DEMOS COMPLETE\n{'=' * 60}\n")
    return True, None


def main() -> int:
    write(f"# Overnight watcher report\n\n", append=False)
    write(f"**Started:** {stamp()}\n\n")
    write(f"**Task:** wait for top-5 rebatch → SQL distribution check → if PASS auto-expand to top-10 → final check\n\n")
    write("---\n\n")

    write(f"## Phase 1 — wait for top-5 rebatch\n\n")
    write(f"Polling `{TOP5_LOG.name}` every 60s for completion or failure marker.\n\n")
    outcome = wait_for_log_marker(
        TOP5_LOG,
        ok_markers=["ALL 5 DEMOS COMPLETE", "ALL DEMOS COMPLETE"],
        fail_markers=["FAILED on"],
    )
    write(f"**Top-5 rebatch finished at {stamp()}: {outcome.upper()}**\n\n")

    if outcome == "fail":
        write("## HALTED — top-5 rebatch failed\n\n")
        write("Last 40 log lines:\n\n```\n")
        try:
            tail = TOP5_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            write("\n".join(tail))
        except Exception as e:
            write(f"(failed to read log: {e})")
        write("\n```\n\nNo auto-expansion. Investigate before continuing.\n")
        return 1

    write(f"## Phase 2 — SQL distribution check (top-5)\n\n")
    top5_names = [n for n, _ in TOP5_DEMOS]
    m5 = sql_check(top5_names)
    write(fmt_metrics(m5, "Top-5 metrics"))

    passed5, reasons5 = acceptance_check(m5)
    if not passed5:
        write(f"\n### HALTED — acceptance check FAILED\n\n")
        for r in reasons5:
            write(f"- {r}\n")
        write("\nNo auto-expansion. Investigate before continuing.\n")
        return 2

    write(f"\n### Top-5 acceptance PASSED at {stamp()}\n\nAuto-expanding to top-10.\n\n")

    write(f"## Phase 3 — delete pre-fix rows for next-5 + run rebatch\n\n")
    next5_names = [n for n, _ in NEXT5_DEMOS]
    deleted = delete_prefix_rows(next5_names)
    write(f"Deleted {deleted} pre-fix engagement rows for next-5 demos.\n\n")
    write(f"Starting next-5 rebatch at {stamp()} (sequential, log: `{TOP10_LOG.name}`)\n\n")
    success, error = run_demo_loop(NEXT5_DEMOS, TOP10_LOG)
    if not success:
        write(f"\n### HALTED — next-5 rebatch failed at {stamp()}\n\n{error}\n\nLast 40 log lines:\n\n```\n")
        try:
            tail = TOP10_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-40:]
            write("\n".join(tail))
        except Exception as e:
            write(f"(failed to read log: {e})")
        write("\n```\n")
        return 3
    write(f"Next-5 rebatch finished at {stamp()}: OK\n\n")

    write(f"## Phase 4 — SQL distribution check (top-10)\n\n")
    all10_names = top5_names + next5_names
    m10 = sql_check(all10_names)
    write(fmt_metrics(m10, "Top-10 metrics"))

    passed10, reasons10 = acceptance_check(m10)
    if passed10:
        write(f"\n## ALL CLEAR — top-10 acceptance PASSED at {stamp()}\n\n")
        write("Next user action: review report, decide whether to expand to full corpus (~73 more demos). Recommended: spawn /gsd-execute style task or run third batch driver if confidence high.\n")
        return 0
    write(f"\n### Top-10 acceptance FAILED at {stamp()}\n\n")
    for r in reasons10:
        write(f"- {r}\n")
    write("\nNote: top-5 passed, top-10 fails — investigate whether next-5 demos exposed an edge case top-5 didn't.\n")
    return 4


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        write(f"\n## EXCEPTION at {stamp()}\n\n```\n{traceback.format_exc()}\n```\n")
        sys.exit(99)
