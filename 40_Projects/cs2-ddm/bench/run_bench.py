"""
Phase 9.1 cold-cache benchmark harness for full-demo analysis walltime.

Per CONTEXT.md D-01:
  - 10 demos (subset of for_analysis/, prefer ≥3 distinct maps for .tri load
    variance; if fewer demos available, run with whatever is on disk).
  - For EACH demo, spawn a fresh subprocess so the BVH .tri load is cold.
  - Each subprocess instantiates DDMAnalyzer, calls
    analyze_demo(profile=True, bulk_mode=True), prints a JSON line with
    walltime_s + step_seconds dict + n_moments to stdout.
  - Parent collects each line and writes to --output (default
    bench/bench_results.json).
  - SC5 acceptance: post-change walltime ≥ 3× faster than baseline.

CLI:
  python bench/run_bench.py --output bench/baseline.json
  python bench/run_bench.py --output bench/post_change.json
  python bench/run_bench.py --compare bench/baseline.json bench/post_change.json
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DEMO_DIR = REPO_ROOT / "for_analysis"
DEFAULT_OUTPUT = REPO_ROOT / "bench" / "bench_results.json"
DEFAULT_PLAYER_STEAMID = 76561198386265483  # donk — matches project memory
MAX_DEMOS = 10

# Single-demo runner inlined as a string so we can pass it via `python -c`.
# Keeps the parent harness self-contained — no extra worker module to maintain.
_RUNNER_TEMPLATE = r"""
import json, os, sys, time, traceback
from pathlib import Path

sys.path.insert(0, r"{repo_root}")
os.chdir(r"{repo_root}")

demo_path = r"{demo_path}"
player_steamid = {player_steamid}

t_start = time.perf_counter()
try:
    from ddm_analyzer import DDMAnalyzer
    analyzer = DDMAnalyzer(
        demo_path=demo_path,
        player_steamid=player_steamid,
        match_id="bench",
        debug_prints=False,
    )
    t_construct = time.perf_counter() - t_start
    df, _ = analyzer.analyze_demo(bulk_mode=True, profile=True)
    walltime = time.perf_counter() - t_start
    n_moments = int(len(df)) if df is not None else 0
    step_seconds = getattr(analyzer, "_last_profile", None) or {{}}
    step_seconds = {{k: float(v) for k, v in dict(step_seconds).items()}}
    step_seconds.setdefault("construct", t_construct)
    payload = {{
        "demo": os.path.basename(demo_path),
        "walltime_s": walltime,
        "step_seconds": step_seconds,
        "n_moments": n_moments,
        "ok": True,
    }}
except Exception as exc:
    payload = {{
        "demo": os.path.basename(demo_path),
        "walltime_s": time.perf_counter() - t_start,
        "step_seconds": {{}},
        "n_moments": 0,
        "ok": False,
        "error": f"{{type(exc).__name__}}: {{exc}}",
        "traceback": traceback.format_exc(),
    }}

sys.stdout.write("\n__BENCH_RESULT__" + json.dumps(payload) + "\n")
sys.stdout.flush()
"""


def _select_demos(demo_dir: Path, max_demos: int, recursive: bool = True) -> List[Path]:
    """Pick up to ``max_demos`` .dem files. Map diversity preferred but not
    required — falls back to first N alphabetically when parse_header fails
    or no demos beyond the cap exist.

    When ``recursive`` is True (default), demos are discovered via ``rglob``
    so deeply-nested layouts (e.g. ``ab/demos/nopros/faceit/<player>/*.dem``)
    are picked up. Pass ``recursive=False`` to restrict to the top-level
    directory (legacy ``iterdir`` behavior)."""
    if not demo_dir.exists():
        return []
    if recursive:
        candidates = sorted(
            p for p in demo_dir.rglob("*.dem") if p.is_file()
        )
    else:
        candidates = sorted(
            p for p in demo_dir.iterdir() if p.suffix.lower() == ".dem"
        )
    if len(candidates) <= max_demos:
        return candidates

    # Map-diversity sampling: read map_name from header, take demos covering
    # as many distinct maps as possible up to max_demos.
    by_map: Dict[str, List[Path]] = {}
    for p in candidates:
        m = _safe_read_map(p)
        by_map.setdefault(m, []).append(p)

    selected: List[Path] = []
    # Round-robin across maps until we hit the cap.
    while len(selected) < max_demos and any(by_map.values()):
        for m in list(by_map.keys()):
            if not by_map[m]:
                continue
            selected.append(by_map[m].pop(0))
            if len(selected) >= max_demos:
                break
    return selected[:max_demos]


def _safe_read_map(demo_path: Path) -> str:
    """Best-effort header read for map_name. Falls back to "unknown" on
    any failure — keeps demo selection robust against corrupt headers."""
    try:
        from demoparser2 import DemoParser

        return str(DemoParser(str(demo_path)).parse_header().get("map_name", "unknown"))
    except Exception:
        return "unknown"


def _run_one_demo(demo_path: Path, player_steamid: int, timeout_s: int) -> Dict[str, Any]:
    """Spawn fresh subprocess; return parsed JSON payload for the demo."""
    runner = _RUNNER_TEMPLATE.format(
        repo_root=str(REPO_ROOT).replace("\\", "\\\\"),
        demo_path=str(demo_path).replace("\\", "\\\\"),
        player_steamid=player_steamid,
    )
    try:
        proc = subprocess.run(
            [sys.executable, "-c", runner],
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=str(REPO_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "demo": demo_path.name,
            "walltime_s": float(timeout_s),
            "step_seconds": {},
            "n_moments": 0,
            "ok": False,
            "error": f"TimeoutExpired after {timeout_s}s: {exc}",
        }

    payload: Optional[Dict[str, Any]] = None
    for line in proc.stdout.splitlines():
        if line.startswith("__BENCH_RESULT__"):
            try:
                payload = json.loads(line[len("__BENCH_RESULT__"):])
            except json.JSONDecodeError:
                payload = None
    if payload is None:
        payload = {
            "demo": demo_path.name,
            "walltime_s": 0.0,
            "step_seconds": {},
            "n_moments": 0,
            "ok": False,
            "error": "no __BENCH_RESULT__ line in stdout",
            "stdout_tail": proc.stdout[-2000:],
            "stderr_tail": proc.stderr[-2000:],
        }
    return payload


def _capture(args: argparse.Namespace) -> int:
    demo_dir = Path(args.demo_dir).resolve()
    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    demos = _select_demos(demo_dir, args.max_demos, recursive=args.recursive)
    if not demos:
        print(f"[bench] WARNING: no .dem files found under {demo_dir}", file=sys.stderr)
        results = {
            "demos": [],
            "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "demo_dir": str(demo_dir),
            "n_demos": 0,
            "note": "no demos found; baseline empty (record this in SUMMARY)",
        }
        output.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(f"[bench] wrote empty baseline to {output}")
        return 0

    print(
        f"[bench] running {len(demos)} demo(s) cold-cache (subprocess each) "
        f"from {demo_dir} → {output}"
    )

    per_demo: List[Dict[str, Any]] = []
    t_total_start = time.perf_counter()
    for i, demo in enumerate(demos, 1):
        print(f"[bench] [{i}/{len(demos)}] {demo.name} ...", flush=True)
        payload = _run_one_demo(demo, args.player_steamid, args.timeout)
        ok = payload.get("ok", False)
        wall = payload.get("walltime_s", 0.0)
        n = payload.get("n_moments", 0)
        status = "ok" if ok else "FAIL"
        print(f"[bench]   {status}: walltime={wall:.2f}s, moments={n}")
        per_demo.append(payload)
    total_wall = time.perf_counter() - t_total_start

    successes = [d for d in per_demo if d.get("ok")]
    summary = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "demo_dir": str(demo_dir),
        "n_demos": len(per_demo),
        "n_ok": len(successes),
        "harness_walltime_s": total_wall,
        "mean_walltime_s": (
            sum(d["walltime_s"] for d in successes) / len(successes)
            if successes
            else 0.0
        ),
        "demos": per_demo,
    }
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(
        f"[bench] wrote {output} "
        f"(n_ok={summary['n_ok']}/{summary['n_demos']}, "
        f"mean walltime={summary['mean_walltime_s']:.2f}s)"
    )
    return 0


def _compare(args: argparse.Namespace) -> int:
    base = json.loads(Path(args.compare[0]).read_text(encoding="utf-8"))
    post = json.loads(Path(args.compare[1]).read_text(encoding="utf-8"))

    base_by_demo = {d["demo"]: d for d in base.get("demos", []) if d.get("ok")}
    post_by_demo = {d["demo"]: d for d in post.get("demos", []) if d.get("ok")}

    common = sorted(set(base_by_demo) & set(post_by_demo))
    if not common:
        print("[bench] no common demos between baseline and post-change runs.")
        return 1

    print(f"[bench] per-demo speedup (baseline → post-change), n={len(common)}:")
    ratios: List[float] = []
    for demo in common:
        b = base_by_demo[demo]["walltime_s"]
        p = post_by_demo[demo]["walltime_s"]
        ratio = (b / p) if p > 0 else float("inf")
        ratios.append(ratio)
        print(f"  {demo:50s}  {b:7.2f}s → {p:7.2f}s   speedup={ratio:5.2f}x")
    mean_ratio = sum(ratios) / len(ratios)
    print(f"[bench] mean speedup across {len(ratios)} demos: {mean_ratio:.2f}x")
    print("[bench] SC5 gate (≥3.00x): " + ("PASS" if mean_ratio >= 3.0 else "FAIL"))
    return 0 if mean_ratio >= 3.0 else 2


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_bench.py",
        description="Phase 9.1 cold-cache benchmark harness (D-01).",
    )
    p.add_argument(
        "--demo-dir",
        default=str(DEFAULT_DEMO_DIR),
        help=f"Directory of .dem files to bench (default: {DEFAULT_DEMO_DIR}).",
    )
    p.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT),
        help=(
            "Path to write bench results JSON. Use bench/baseline.json before "
            "any production change; bench/post_change.json afterwards."
        ),
    )
    p.add_argument(
        "--max-demos",
        type=int,
        default=MAX_DEMOS,
        help=f"Maximum demos to run (default: {MAX_DEMOS}).",
    )
    p.add_argument(
        "--player-steamid",
        type=int,
        default=DEFAULT_PLAYER_STEAMID,
        help="Player SteamID64 for analyze_demo (default: donk).",
    )
    p.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Per-demo subprocess timeout in seconds (default: 600).",
    )
    p.add_argument(
        "--compare",
        nargs=2,
        metavar=("BASELINE", "POST"),
        help="Compare two bench JSON files; print per-demo + mean speedup.",
    )
    p.add_argument(
        "--recursive",
        dest="recursive",
        action="store_true",
        default=True,
        help="Recursively discover .dem files under --demo-dir (default).",
    )
    p.add_argument(
        "--no-recursive",
        dest="recursive",
        action="store_false",
        help="Disable recursive discovery; use only top-level .dem files.",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.compare:
        return _compare(args)
    return _capture(args)


if __name__ == "__main__":
    raise SystemExit(main())
