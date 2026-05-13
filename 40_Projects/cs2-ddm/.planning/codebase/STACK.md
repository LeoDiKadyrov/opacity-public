    # Technology Stack

_Generated: 2026-04-30_
_Focus: tech_

## Summary

Python 3.14 project that parses CS2 GOTV demo files and measures player reaction times. The pipeline uses `demoparser2` for state/kinematics extraction and `awpy` for BVH geometric visibility checks. A Streamlit dashboard provides interactive exploration of results stored in a flat CSV database.

## Languages

**Primary:**
- Python 3.14+ — all analysis, pipeline, and UI code

**Type Annotations:**
- Full `typing` module usage (`Tuple`, `List`, `Dict`, `Optional`)
- `from __future__ import annotations` used in newer modules (`duel_attempts.py`, `kill_rate_analysis.py`)

## Runtime

**Environment:**
- CPython 3.14.3 (Windows 11)
- No virtual env file tracked — install manually via pip

**Package Manager:**
- pip (no Poetry or uv detected)
- Lockfile: absent — only `requirements.txt` with `>=` version pins

## Frameworks

**Web / Dashboard:**
- Streamlit `>=1.35` — `app.py` — interactive analysis dashboard with file upload, sliders, and chart rendering

**Testing:**
- pytest `>=7.4.0` — 215 tests across `tests/`
- pytest-cov `>=4.1.0` — coverage reporting (disabled in hooks via `-p no:cov` for speed)

**Build/Dev:**
- black — code formatting (applied via pre-edit hook)
- ruff — linting (applied via pre-edit hook)
- No build system (no pyproject.toml, no setup.py)

## Key Dependencies

**Critical:**
- `demoparser2 >=0.41.1` (pinned runtime: 0.41.2) — Rust-backed CS2 demo parser; extracts per-tick player state, events (`player_hurt`, `weapon_fire`, `player_death`, flash events), and kinematic props. Required CS2 patch 14155+ support added in 0.41.2.
- `awpy >=2.0.2` — CS2 analytics library; provides `VisibilityChecker` (BVH Möller-Trumbore ray-triangle intersection) and `TRIS_DIR` path reference. Must be installed with `--ignore-requires-python`.
- `pandas >=2.0` — primary data structure for tick DataFrames, CSV I/O, event filtering
- `numpy >=1.26` — AABB corner computation, angular math in T0/T1 detection

**Visualization:**
- `matplotlib >=3.7` — chart backend; uses `Agg` non-interactive backend in Streamlit context
- `seaborn >=0.13` — histogram, boxplot, stacked bar chart generation in `visualize_results.py`

## Data Model

**Core dataclasses (all in `config.py`):**
- `AnalysisMoment` — per-engagement metadata passed through the manual/bulk pipeline
- `DuelAttempt` (in `duel_attempts.py`) — T0-anchored kill rate record with `was_killed`, `bullets_fired`, `bullets_hit`, `engagement_type`, `crosshair_angle_deg`, `hurt_victims_in_window`

## Configuration

**Constants file:** `config.py`
- All named thresholds and timing parameters (no magic numbers in logic files)
- `get_logger()` factory — dual-handler (file + stdout) logger scoped per match_id

**Key configurable values:**
- `VELOCITY_PEEK_THRESHOLD_UPS = 50.0` — minimum player speed (u/s) to classify as peek
- `ENEMY_VELOCITY_HOLD_THRESHOLD_UPS = 120.0` — max enemy speed before engagement rejected
- `_FIRE_CLUSTER_GAP_TICKS = 128` — max gap between weapon_fire events in same cluster
- `_FIRE_CLUSTER_MAX_SPAN_TICKS = 192` — hard cap on cluster duration (prevents merged engagements)
- `T0_MIN_OFFSET_TICKS = 20` — quality gate: T0 must be >=20 ticks after search start
- `_KILL_CONFIRM_WINDOW_TICKS = 320` — window after T0 for kill attribution
- `_BULLETS_FOR_HIT_RATE = 5` — first-burst bullets counted for hit rate metric

**Logging:**
- File: `ddm_analysis.log` (auto-archived when >10MB via Claude hook)
- Format: `%(asctime)s [%(name)s] %(levelname)s: %(message)s`

**Environment variables:** None required — demo paths are hardcoded per-script constants

## Platform Requirements

**Development:**
- Windows only (paths use raw strings with backslashes: `r"D:\Steam\..."`)
- `.tri` mesh files required at `C:\Users\Leo\.awpy\tris\` for BVH visibility checks
- CS2 installed locally (demo files sourced from CS2 install directory)

**Production:**
- No cloud deployment — runs locally only
- Streamlit dashboard served locally via `streamlit run app.py`

---

_Stack analysis: 2026-04-30_
