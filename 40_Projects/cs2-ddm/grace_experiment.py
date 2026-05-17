"""
T1_GRACE_MS floor experiment.

Re-analyzes a single demo for top pros with grace=120 (baseline) / 30 / 0,
in-memory (no DB writes), and reports T0->T1 distribution stats per variant.

Goal: confirm 125ms pinning is grace-induced + pick fix value.
"""

from __future__ import annotations

import sys
import importlib
import statistics
from pathlib import Path
from typing import Dict, List

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))

DEMO_PATH = str(REPO_ROOT / "temp_demos" / "astralis-vs-spirit-m1-dust2-p1.dem")

# Pros known to be in this demo (Spirit + Astralis rosters)
PROS = {
    76561198386265483: "donk",
    76561198872013168: "tN1R",
    76561198081484775: "sh1ro",
    76561198210626739: "zweih",
    76561198995880877: "zont1x",
    76561199063238565: "magixx",
    76561198045898864: "chopper",
    76561198005107817: "Staehr",
    76561197998926770: "HooXi",
    76561198120557348: "jabbi",
    76561197987713664: "device",
    76561198168401372: "ryu",
    76561198004115516: "cadiaN",
}


def run_variant(grace_ms: int) -> pd.DataFrame:
    """Run analyzer for each pro with given T1_GRACE_MS, return concatenated df."""
    import config as _cfg
    _cfg.T1_GRACE_MS = grace_ms
    # Force re-import of ddm_analyzer so it picks up new T1_GRACE_MS at module top-level if any
    if "ddm_analyzer" in sys.modules:
        importlib.reload(sys.modules["ddm_analyzer"])
    from ddm_analyzer import DDMAnalyzer

    rows: List[pd.DataFrame] = []
    for sid, name in PROS.items():
        try:
            analyzer = DDMAnalyzer(
                DEMO_PATH, sid,
                match_id=9000 + sid % 1000, tickrate=64, debug_prints=False,
            )
        except Exception as e:
            print(f"  [{name}] init error: {e}")
            continue
        try:
            df, _ = analyzer.analyze_demo(bulk_mode=True)
        except Exception as e:
            print(f"  [{name}] analysis error: {e}")
            continue
        if df is not None and not df.empty:
            df = df.copy()
            df["__player"] = name
            rows.append(df)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def summarize(df: pd.DataFrame, label: str) -> Dict:
    if df.empty:
        return {"label": label, "n": 0}
    peek = df[(df["engagement_type"] == "peek") & df["rt_visible_to_aim_ms"].notna()]
    vals = peek["rt_visible_to_aim_ms"].tolist()
    if not vals:
        return {"label": label, "n": 0}
    n_125 = sum(1 for v in vals if abs(v - 125.0) < 0.5)
    n_sub180 = sum(1 for v in vals if v < 180)
    return {
        "label": label,
        "n": len(vals),
        "min": min(vals),
        "median": statistics.median(vals),
        "p25": sorted(vals)[len(vals) // 4],
        "p75": sorted(vals)[3 * len(vals) // 4],
        "%@125ms": 100.0 * n_125 / len(vals),
        "%<180ms": 100.0 * n_sub180 / len(vals),
    }


def main():
    print(f"Demo: {DEMO_PATH}")
    print(f"Pros: {len(PROS)}\n")

    results = {}
    for grace in [120, 30, 0]:
        print(f"=== Running variant grace={grace}ms ===")
        df = run_variant(grace)
        results[grace] = df
        s = summarize(df, f"grace={grace}")
        print(f"  N={s.get('n', 0)} median={s.get('median')} %@125ms={s.get('%@125ms'):.1f}% %<180ms={s.get('%<180ms'):.1f}%")
        print()

    print("\n=== COMPARISON TABLE (peek engagements only) ===")
    print(f"{'variant':<14} | {'N':>4} | {'min':>5} | {'p25':>5} | {'med':>5} | {'p75':>5} | {'%@125ms':>8} | {'%<180ms':>8}")
    print("-" * 80)
    for grace in [120, 30, 0]:
        s = summarize(results[grace], f"grace={grace}")
        if s["n"] == 0:
            print(f"{s['label']:<14} | (no data)")
            continue
        print(f"{s['label']:<14} | {s['n']:>4} | {s['min']:>5.0f} | {s['p25']:>5.0f} | {s['median']:>5.0f} | {s['p75']:>5.0f} | {s['%@125ms']:>7.1f}% | {s['%<180ms']:>7.1f}%")

    # Per-player view for grace=0 vs baseline (most interesting)
    print("\n=== PER-PLAYER MEDIANS ===")
    print(f"{'player':<10} | {'baseline':>9} | {'grace=30':>9} | {'grace=0':>9}")
    print("-" * 50)
    for name in PROS.values():
        row = [name]
        for grace in [120, 30, 0]:
            df = results[grace]
            if df.empty:
                row.append("-")
                continue
            sub = df[(df["__player"] == name) & (df["engagement_type"] == "peek") & df["rt_visible_to_aim_ms"].notna()]
            if sub.empty:
                row.append("-")
            else:
                row.append(f"{statistics.median(sub['rt_visible_to_aim_ms'].tolist()):.0f}")
        print(f"{row[0]:<10} | {row[1]:>9} | {row[2]:>9} | {row[3]:>9}")


if __name__ == "__main__":
    main()
