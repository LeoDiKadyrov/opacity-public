# Codebase Structure

_Generated: 2026-04-30_
_Focus: arch_

## Summary

Flat root layout — all Python modules and entry points live directly in the project root. Tests in `tests/`. Input demos in `for_analysis/`. Generated outputs in `analysis_plots/`.

## Directory Layout

```
cs2-ddm/
├── ddm_analyzer.py          # DDMAnalyzer class — RT pipeline orchestrator
├── t0_detector.py           # T0Detector — BVH+AABB visibility engine
├── duel_attempts.py         # DuelAttemptFinder + DuelAttempt dataclass
├── config.py                # Named constants, AnalysisMoment dataclass, get_logger()
├── csv_utils.py             # load_existing_results(), save_results() — replace-or-append
├── run_analysis.py          # Entry point: RT analysis pipeline (Path 1)
├── kill_rate_analysis.py    # Entry point: kill rate pipeline (Path 2)
├── visualize_results.py     # Chart generation from cs2_engagement_analysis_results.csv
├── app.py                   # Streamlit dashboard
├── requirements.txt
├── cs2_engagement_analysis_results.csv   # Persistent RT results DB (write-protected by hook)
├── {player}_attempts.csv    # Kill rate output — e.g. donk_attempts.csv
├── ddm_analysis.log         # Rotating log (auto-archived by hook at >10MB)
├── for_analysis/            # Drop .dem files here for pipeline input
├── analysis_plots/          # Generated chart output (PNG files)
├── tests/                   # 215 pytest tests
│   ├── conftest.py
│   ├── test_ddm_analyzer_core.py
│   ├── test_ddm_analyzer_geometry.py
│   ├── test_ddm_analyzer_quality.py
│   ├── test_ddm_analyzer_t1.py
│   ├── test_t0_detector_find_t0.py
│   ├── test_t0_detector_parsing.py
│   ├── test_t0_detector_smoke.py
│   ├── test_t0_detector_first_visible_window.py
│   ├── test_duel_attempts.py
│   ├── test_csv_utils.py
│   └── test_config.py
├── docs/                    # Plans and documentation
├── .claude/                 # Claude Code config (hooks, skills)
├── .planning/               # GSD planning documents
│   └── codebase/            # Codebase map (7 documents)
└── DEPRECATED/              # Old notes and phase summaries
```

## Module Dependency Graph

```
run_analysis.py
    → ddm_analyzer.py
        → t0_detector.py
            → awpy.visibility (VisibilityChecker)
        → duel_attempts.py
            → config.py
        → config.py (AnalysisMoment, get_logger, constants)
        → csv_utils.py
        → demoparser2 (DemoParser)

kill_rate_analysis.py
    → ddm_analyzer.py (same tree)
    → duel_attempts.py (DuelAttempt)

app.py
    → csv_utils.load_existing_results
    → visualize_results.py
    → streamlit

visualize_results.py
    → csv_utils.load_existing_results
    → pandas, seaborn, matplotlib
```

`config.py` has no imports from other project modules — foundation layer.

## Entry Points

### `run_analysis.py` — Path 1 (RT Analysis)

```bash
python run_analysis.py
```

Iterates `DEMOS` list, creates `DDMAnalyzer` per demo, calls `analyze_demo(bulk_mode=True)`. Output: rows appended to `cs2_engagement_analysis_results.csv`. Configure: edit `DEMOS`, `PLAYER_STEAMID`, `OUTPUT_FILE` at top of file.

### `kill_rate_analysis.py` — Path 2 (Kill Rate)

```bash
python kill_rate_analysis.py               # process demos + save *_attempts.csv
python kill_rate_analysis.py --load-only   # load existing CSVs, print table only
```

Iterates `PLAYERS` dict, calls `analyze_demo(bulk_mode=True, attempts_mode=True)`. Configure: edit `PLAYERS` dict to add/remove players and demo paths.

### `app.py` — Streamlit Dashboard

```bash
streamlit run app.py
```

Loads `cs2_engagement_analysis_results.csv`, renders interactive charts and filters.

## Test File → Source Module Mapping

| Test file | Source module(s) covered |
|-|-|
| `test_ddm_analyzer_core.py` | `DDMAnalyzer.__init__`, `analyze_demo`, `auto_build_moments`, `compute_round_phase` |
| `test_ddm_analyzer_geometry.py` | `get_desired_angles`, `angular_diff`, `_compute_crosshair_angle_at_t0` |
| `test_ddm_analyzer_quality.py` | `is_1v1_duel`, `_compute_velocity`, `_classify_engagement` |
| `test_ddm_analyzer_t1.py` | `_detect_t1` |
| `test_t0_detector_find_t0.py` | `T0Detector.find_t0` |
| `test_t0_detector_first_visible_window.py` | `find_first_visible_enemy_in_window` |
| `test_t0_detector_parsing.py` | `parse_flash_intervals`, `parse_smoke_events` |
| `test_t0_detector_smoke.py` | `_is_smoke_obscured` |
| `test_duel_attempts.py` | `DuelAttemptFinder`, `DuelAttempt` |
| `test_csv_utils.py` | `load_existing_results`, `save_results` |
| `test_config.py` | constants, `AnalysisMoment` dataclass, logger factory |

## Where to Add New Code

**New engagement quality filter**: Add `_check_<condition>` to `DDMAnalyzer`, call inside `analyze_engagement_episode()` after `_find_t2()`. Return `None` on rejection. Tests → `test_ddm_analyzer_quality.py`.

**New constant/threshold**: Add to `config.py` with rationale comment. Import in consuming module. Test in `test_config.py`.

**New Path 1 output column**: Add to returned dict in `analyze_engagement_episode()`. Update `csv_utils.load_existing_results()` numeric_cols if float. Update `visualize_results.py` / `app.py` if charted.

**New Path 2 DuelAttempt field**: Add to `DuelAttempt` dataclass. Populate in `_process_cluster()`. `dataclasses.asdict()` picks it up automatically in `save_attempts()`.

**New player for kill rate**: Edit `PLAYERS` dict in `kill_rate_analysis.py`:
```python
PLAYERS: dict[str, tuple[int, list[str]]] = {
    "donk": (76561198386265483, [...]),
    "newplayer": (STEAMID64, [r"path\to\demo.dem"]),
}
```

**New demo for RT analysis**: Edit `DEMOS` list in `run_analysis.py` with unique `match_id`. Re-running same `match_id` replaces its rows (idempotent).
