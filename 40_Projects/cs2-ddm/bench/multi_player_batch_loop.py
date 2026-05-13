"""
Batch loop wrapper around multi_player_analyze.py.

Walks every .dem under a directory, runs multi_player_analyze for each,
and logs progress. Designed to run in the background (long wall-clock).

Usage:
    python bench/multi_player_batch_loop.py D:/Obsidian/opacity/40_Projects/for_analysis/spirit
"""

from __future__ import annotations

import glob
import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: multi_player_batch_loop.py <demo_dir>")
        sys.exit(1)

    demo_dir = sys.argv[1]
    demos = sorted(glob.glob(os.path.join(demo_dir, "*.dem")))
    if not demos:
        print(f"No demos found in {demo_dir}")
        sys.exit(1)

    repo_root = Path(__file__).resolve().parent.parent
    wrapper = repo_root / "multi_player_analyze.py"

    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    overall_start = time.time()

    print(f"=== batch loop: {len(demos)} demos in {demo_dir} ===", flush=True)
    for i, demo in enumerate(demos, 1):
        name = os.path.basename(demo)
        elapsed = time.time() - overall_start
        print(f"\n[batch {i}/{len(demos)}] {name}  (elapsed {elapsed/60:.1f} min)", flush=True)
        rc = subprocess.run(
            [sys.executable, str(wrapper), demo, "--skip-existing"],
            env=env,
            cwd=str(repo_root),
        ).returncode
        if rc != 0:
            print(f"  [WARN] non-zero exit code {rc} on {name}", flush=True)

    total = time.time() - overall_start
    print(f"\n=== batch done — {len(demos)} demos in {total/60:.1f} min ===", flush=True)


if __name__ == "__main__":
    main()
