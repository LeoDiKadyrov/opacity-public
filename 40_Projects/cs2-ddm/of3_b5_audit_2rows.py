"""One-off audit of the 2 b5-class rows from stage N=81 (doubt trigger).

For each row: parse a small tick window around T0, print per-tick crosshair
angular distance to the opponent and the crosshair angular velocity, to test
the mid-flick hypothesis (motion already in progress before T0).
"""

import os
import sys

os.environ.setdefault("PYTHONUTF8", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

import pandas as pd

from outcome_first import _coerce_sid, _TIMING_TICK_PROPS
from reaction_timing import _angular_dist_at_tick, _row_at_tick
from ddm_analyzer import DDMAnalyzer
import math

CORPUS = r"D:\Obsidian\opacity\40_Projects\for_analysis\spirit"

CASES = [
    {
        "demo": "pain-vs-spirit-m1-ancient-p2",
        "player": 76561198386265483,
        "enemy": 76561198216891576,
        "t0": 113420,
        "t1": 113421,
        "first_event": 113471,
    },
    {
        "demo": "spirit-vs-the-mongolz-m3-ancient",
        "player": 76561198386265483,
        "enemy": 76561198920720017,
        "t0": 37727,
        "t1": 37728,
        "first_event": 37761,
    },
]


def main() -> int:
    from demoparser2 import DemoParser

    for case in CASES:
        demo_path = os.path.join(CORPUS, case["demo"] + ".dem")
        if not os.path.exists(demo_path):
            # search subfolders
            for root, _dirs, files in os.walk(os.path.dirname(CORPUS)):
                if case["demo"] + ".dem" in files:
                    demo_path = os.path.join(root, case["demo"] + ".dem")
                    break
        print(f"\n=== {case['demo']} (T0={case['t0']}, T1={case['t1']}) ===")
        print(f"demo: {demo_path}")

        lo, hi = case["t0"] - 8, case["t1"] + 8
        parser = DemoParser(demo_path)
        ticks_df = pd.DataFrame(
            parser.parse_ticks(_TIMING_TICK_PROPS, ticks=list(range(lo, hi + 1)))
        )
        ticks_df["steamid"] = _coerce_sid(ticks_df["steamid"])
        ticks_df["tick"] = pd.to_numeric(ticks_df["tick"], errors="coerce")

        prev_yaw = prev_pitch = None
        print(f"{'tick':>8} {'rel':>4} {'ang_to_enemy':>12} {'xhair_vel_deg_s':>15}")
        for tick in range(lo, hi + 1):
            ang = _angular_dist_at_tick(
                ticks_df, case["player"], case["enemy"], tick
            )
            p_row = _row_at_tick(ticks_df, case["player"], tick)
            vel = None
            if p_row is not None:
                yaw, pitch = float(p_row["yaw"]), float(p_row["pitch"])
                if prev_yaw is not None:
                    dyaw = DDMAnalyzer.angular_diff(yaw, prev_yaw)
                    dpitch = DDMAnalyzer.angular_diff(pitch, prev_pitch)
                    vel = math.hypot(dyaw, dpitch) / 0.015625
                prev_yaw, prev_pitch = yaw, pitch
            rel = tick - case["t0"]
            ang_s = f"{ang:.2f}" if ang is not None else "-"
            vel_s = f"{vel:.0f}" if vel is not None else "-"
            marker = " <-- T0" if tick == case["t0"] else (" <-- T1" if tick == case["t1"] else "")
            print(f"{tick:>8} {rel:>4} {ang_s:>12} {vel_s:>15}{marker}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
