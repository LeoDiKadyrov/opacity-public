"""
Entry point for the DDM bulk analysis pipeline.

Usage:
    python run_analysis.py

Add/remove demos from the DEMOS list. Each match_id must be unique — re-running
a match_id replaces that match's rows in the CSV (idempotent).
"""

import pandas as pd
from typing import List

from ddm_analyzer import DDMAnalyzer
from csv_utils import save_results

try:
    from obsidian_writer import write_analysis_note
    _OBSIDIAN_WRITER_AVAILABLE = True
except ImportError:
    _OBSIDIAN_WRITER_AVAILABLE = False


BASE = r"D:\Steam\steamapps\common\Counter-Strike Global Offensive\game\csgo"

DEMOS = [
    (1, "abdra_mirage_faceit_hahablya.dem"),
]

PLAYER_STEAMID = 76561198388053181  # donk SteamID64
OUTPUT_FILE    = "cs2_engagement_analysis_results.csv"
DEBUG_PRINTS   = False


def main():
    grand_total_accepted = 0
    all_results: List[pd.DataFrame] = []

    for match_id, filename in DEMOS:
        demo_path = rf"{BASE}\{filename}"
        print(f"\n{'='*60}")
        print(f"Match {match_id}: {filename}")
        print(f"{'='*60}")

        try:
            analyzer = DDMAnalyzer(
                demo_path, PLAYER_STEAMID,
                match_id=match_id, tickrate=64, debug_prints=DEBUG_PRINTS,
            )
        except Exception as e:
            print(f"  ERROR initialising analyzer: {e}")
            continue

        try:
            results_df, _ = analyzer.analyze_demo(bulk_mode=True)
        except Exception as e:
            print(f"  ERROR during analysis: {e}")
            continue

        if not results_df.empty:
            save_results(results_df, OUTPUT_FILE, match_id)
            # db_utils.save_to_db is already called inside analyze_demo(); no duplicate write needed
            n = len(results_df)
            grand_total_accepted += n
            all_results.append(results_df)
            print(f"  Saved {n} engagements for match {match_id}.")
            if _OBSIDIAN_WRITER_AVAILABLE:
                try:
                    write_analysis_note(
                        df=results_df,
                        demo_name=filename,
                    )
                except Exception as e:
                    print(f"[obsidian_writer] Warning: {e}")
        else:
            print(f"  No valid engagements found.")

    # Grand summary across all matches
    if all_results:
        combined = pd.concat(all_results, ignore_index=True)
        print(f"\n{'='*60}")
        print(f"ALL MATCHES — {grand_total_accepted} accepted engagements total")
        print(f"{'='*60}")
        if "engagement_type" in combined.columns:
            for etype in ("peek", "hold"):
                subset = combined[combined["engagement_type"] == etype]
                if subset.empty:
                    continue
                print(f"\n  [{etype.upper()}]  n={len(subset)}")
                for col in ("rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"):
                    valid = subset[col].dropna()
                    if not valid.empty:
                        print(f"    {col}: mean={valid.mean():.1f}ms  "
                              f"median={valid.median():.1f}ms  "
                              f"min={valid.min():.1f}ms  max={valid.max():.1f}ms")


if __name__ == "__main__":
    main()
