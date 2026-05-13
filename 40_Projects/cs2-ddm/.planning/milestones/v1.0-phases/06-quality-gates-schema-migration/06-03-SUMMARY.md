# Plan 06-03 Summary — SQLite Dual-Write

## What was built

- **`db_utils.py`** — new module with two functions:
  - `save_to_db(df, db_path, table, match_id)` — replace-or-append per match_id (idempotent), mirrors csv_utils pattern
  - `_table_exists(conn, table)` — SQLite master table lookup

- **`config.py`** — added `DB_PATH: str = "analytics.db"` constant

- **Dual-write wired in three places:**
  - `ddm_analyzer.py` (`analyze_demo()`) → writes `engagements` table to `analytics.db`
  - `run_analysis.py` (after `save_results()`) → same engagements table at CLI level
  - `kill_rate_analysis.py` (`save_attempts()`) → writes `duel_attempts` table to `analytics.db`

- **`tests/test_db_utils.py`** — 9 new tests covering:
  - `_table_exists()` False/True
  - `save_to_db()` create+insert, idempotency, accumulation, corrupted DB, player_steamid query
  - `test_csv_sqlite_row_parity` (SC4 parity test)
  - `test_save_attempts_calls_save_to_db` (integration mock test)

## Test counts

| State | Count |
|-|-|
| Before | 243 |
| After | 252 |
| Delta | +9 |

## Deviations from plan

- `save_results` is called in `run_analysis.py`, not `analyze_demo()`. Added dual-write in both `analyze_demo()` (as plan specified) and `run_analysis.py` (as the actual save_results call site). This results in two SQLite writes per demo run when using run_analysis.py — the second write is idempotent (deduped by match_id), so no data integrity issue.
- DuelAttempt field names in the mock test were corrected (`enemy_steamid`, `player_velocity_ups`, `crosshair_angle_deg`) to match the actual dataclass definition.
