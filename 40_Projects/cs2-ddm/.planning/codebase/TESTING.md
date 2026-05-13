# Testing Patterns

_Generated: 2026-04-30_
_Focus: quality_

## Summary

215 pytest tests across 11 files. Tests cover core pipeline logic, geometry, BVH T0 detection, and the new DuelAttemptFinder. No integration tests against real .dem files — all tests use mocked/synthetic data.

## Test Count by File

| File | Tests | Covers |
|-|-|-|
| test_ddm_analyzer_core.py | ~56 | DDMAnalyzer init, orchestration, auto_build_moments, analyze_engagement_episode, compute_round_phase |
| test_ddm_analyzer_t1.py | 15 | T1 aim-start detection |
| test_ddm_analyzer_geometry.py | ~29 | angular_diff, get_desired_angles, compute_crosshair_angle_at_t0 |
| test_ddm_analyzer_quality.py | 12 | is_1v1_duel filter |
| test_t0_detector_find_t0.py | 13 | find_t0() BVH logic |
| test_t0_detector_smoke.py | 15 | is_smoke_obscured() sphere intersection |
| test_t0_detector_parsing.py | 20 | parse_flash_intervals(), parse_smoke_events() |
| test_t0_detector_first_visible_window.py | ? | find_first_visible_enemy_in_window() (NEW) |
| test_duel_attempts.py | 14 | DuelAttemptFinder (NEW) |
| test_csv_utils.py | 12 | save_results(), load_existing_results() |
| test_config.py | 18 | constants, AnalysisMoment dataclass, logger factory |

## Test Structure

```
tests/
├── conftest.py                          # shared fixtures
├── test_ddm_analyzer_core.py
├── test_ddm_analyzer_geometry.py
├── test_ddm_analyzer_quality.py
├── test_ddm_analyzer_t1.py
├── test_t0_detector_find_t0.py
├── test_t0_detector_smoke.py
├── test_t0_detector_parsing.py
├── test_t0_detector_first_visible_window.py  # added with kill-rate feature
├── test_duel_attempts.py                     # added with kill-rate feature
├── test_csv_utils.py
└── test_config.py
```

## Fixtures (conftest.py)

Shared fixtures provide synthetic DataFrames mimicking demoparser2 output — no real .dem files needed.

## Running Tests

```bash
python -m pytest              # full run with coverage
python -m pytest -p no:cov    # fast run (used by hooks)
python -m pytest --cov        # coverage report
```

## What Is Tested

- BVH T0 detection logic (mocked VisibilityChecker)
- Smoke sphere intersection math
- Flash interval parsing and suppression
- T1 aim-start detection (yaw/pitch spike detection)
- Angular geometry (crosshair angle at T0)
- CSV append/dedup behavior
- DuelAttemptFinder cluster detection and attempt construction
- `find_first_visible_enemy_in_window()` boundary conditions

## What Is NOT Tested

- End-to-end pipeline against real .dem files (live testing only)
- Streamlit dashboard (app.py)
- visualize_results.py chart generation
- kill_rate_analysis.py script (entry point, not unit-tested)
- BVH mesh loading / .tri file existence

## Coverage

~51% line coverage (from hook run output). Low coverage in csv_utils.py (16%) and entry point scripts. Core analysis logic in ddm_analyzer.py and t0_detector.py has higher coverage.
