"""
CSV persistence helpers for the DDM reaction analysis pipeline.

Strategy: replace-or-append per match_id (idempotent re-runs).
"""

import os
import pandas as pd


def load_existing_results(filename: str) -> pd.DataFrame:
    """
    Load the CSV and strip duplicate header rows that were created by
    the old naive-append workflow (the root cause of repeated headers).
    """
    if not os.path.exists(filename) or os.path.getsize(filename) == 0:
        return pd.DataFrame()
    try:
        df = pd.read_csv(filename, dtype=str)
        # Drop rows where 'match_id' literally equals 'match_id' (embedded headers)
        if "match_id" in df.columns:
            df = df[df["match_id"] != "match_id"]
        # Coerce numeric columns back to numbers
        numeric_cols = [
            "t0_manual_tick", "t1_aim_start_tick", "t2_first_hit_tick",
            "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
            "player_velocity_at_t0_ups", "enemy_velocity_at_t0_ups", "round_time_s",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        return df
    except (pd.errors.ParserError, OSError, ValueError) as e:
        print(f"Warning: could not read '{filename}': {e}")
        return pd.DataFrame()


def save_results(results_df: pd.DataFrame, filename: str, match_id: int | str) -> None:
    """
    Replace-or-append strategy:
    - All existing rows for `match_id` are removed (idempotent re-run).
    - New results are appended.
    - A single clean header is always written.
    """
    existing = load_existing_results(filename)
    if not existing.empty and "match_id" in existing.columns:
        existing = existing[existing["match_id"].astype(str) != str(match_id)]
        combined = pd.concat([existing, results_df], ignore_index=True)
    else:
        combined = results_df
    combined.to_csv(filename, index=False)
    print(f"  → Saved {len(results_df)} rows for match_id={match_id} "
          f"(CSV total: {len(combined)} rows).")
