"""Phase A item 6 — staged re-batch driver for top-5 corpus demos.

Sequential per-demo invocation of multi_player_analyze.py CLI. Each demo
processes all ~10 roster players. Stops on first non-zero exit.

Demos resolved 2026-05-16 in external corpus folder
(D:\\Obsidian\\opacity\\40_Projects\\for_analysis\\).
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).parent.resolve()

# Force UTF-8 on subprocess stdout/stderr/file handlers — Windows Python 3.14
# defaults to cp1252 which crashes on `→` characters in print/log strings
# scattered across the codebase (22 files contain U+2192). Same workaround
# Wave 0 Task 1 needed for grace_experiment.py.
_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

DEMOS = [
    "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-the-mongolz-m2-ancient.dem",
    "D:/Obsidian/opacity/40_Projects/for_analysis/faze/passion-ua-vs-faze-m2-nuke.dem",
    "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/mouz-vs-spirit-m2-mirage.dem",
    "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-the-mongolz-m2-mirage.dem",
    "D:/Obsidian/opacity/40_Projects/for_analysis/spirit/spirit-vs-vitality-m1-mirage.dem",
]


def main() -> int:
    t_start = time.time()
    for i, demo_path in enumerate(DEMOS, 1):
        print(f"\n{'=' * 60}", flush=True)
        print(f"DEMO {i}/{len(DEMOS)}: {Path(demo_path).name}", flush=True)
        print(f"{'=' * 60}", flush=True)
        if not Path(demo_path).exists():
            print(f"FAIL: demo not found: {demo_path}", flush=True)
            return 1
        t0 = time.time()
        result = subprocess.run(
            [sys.executable, "multi_player_analyze.py", demo_path],
            cwd=str(REPO),
            env=_UTF8_ENV,
        )
        dt = time.time() - t0
        print(f"\nDemo {i}/{len(DEMOS)} done in {dt:.1f}s (exit {result.returncode})", flush=True)
        if result.returncode != 0:
            print(f"FAILED on {demo_path}", flush=True)
            return result.returncode
    total = time.time() - t_start
    print(f"\n{'=' * 60}", flush=True)
    print(f"ALL {len(DEMOS)} DEMOS COMPLETE in {total / 60:.1f} min", flush=True)
    print(f"{'=' * 60}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
