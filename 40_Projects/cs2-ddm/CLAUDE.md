## CLAUDE.md: DDM Reaction Analysis

### Quick Start

```bash
pip install -r requirements.txt
# awpy requires: pip install awpy --ignore-requires-python
python run_analysis.py          # Run full analysis pipeline
streamlit run app.py            # Launch visualization dashboard
python -m pytest                # Run test suite (322 tests)
python -m pytest --override-ini="addopts=--strict-markers"  # Run without coverage (faster)
python -m pytest --cov          # Run with full coverage report
```

### Phase v2 — LLM coaching layer setup

Phase v2 (`interpretation_narrative`) uses **Claude Code Max subscription** via `claude -p` subprocess (Path B chosen 2026-05-12). No `ANTHROPIC_API_KEY` required — auth flows through your existing Claude Code OAuth session.

```bash
# 1. Verify Claude Code installed (provides `claude` CLI)
which claude   # → /c/Users/Leo/.local/bin/claude

# 2. Generate eval set (10 reports, ~40s wall, charged to Max sub)
python -m interpretation_narrative generate-eval-set --emit-timings evals/generated/timings.json

# 3. Rate per dim (50 ratings minimum for SC-1)
python -m interpretation_narrative eval-rate --report-id v2_donk --player 76561198386265483 \
    --dim tone --score 4 --notes "немного хеджирует"

# 4. Check verdict
python -m interpretation_narrative score

# 5. Cost report (informational under subscription — PRICING-table estimate)
python -m interpretation_narrative cost-report
python -m interpretation_narrative score-cost   # Always PASS in sub mode
```

**Path B tradeoffs** (vs original anthropic SDK design):
- **Cost:** flat-rate Max sub absorbs token spend → marginal cost $0/report; SC-4 gate becomes informational
- **Cache:** Claude Code injects ~45k system-prompt overhead per call; cache hits within 5min keep subsequent calls cheap (sub-second + free)
- **Auth:** OAuth via existing Claude Code session (no API key required)
- **Locked decisions broken:** L-1 (anthropic SDK), L-5 (cache_control breakpoints), SC-4 (cost gate) — documented exception

If `claude` CLI is missing or returns non-zero exit, HTML reports still ship via fail-soft path inside `interpretation_narrative` (tier table preserved, narrative section silently omitted). Diagnostic events land in `narrative_failures.log`.

### Directory Layout

```
cs2-ddm/
├── ddm_analyzer.py        # Core analysis class
├── t0_detector.py         # BVH+AABB T0 detection
├── config.py              # Constants and thresholds
├── csv_utils.py           # CSV append/dedup
├── visualize_results.py   # Chart generation
├── app.py                 # Streamlit dashboard
├── run_analysis.py        # CLI entry point
├── requirements.txt
├── tests/                 # 322 pytest tests
│   ├── conftest.py
│   ├── test_ddm_analyzer_core.py
│   ├── test_ddm_analyzer_geometry.py
│   ├── test_ddm_analyzer_quality.py
│   ├── test_ddm_analyzer_t1.py
│   ├── test_t0_detector_find_t0.py
│   ├── test_t0_detector_first_visible_window.py
│   ├── test_t0_detector_parsing.py
│   ├── test_t0_detector_smoke.py
│   ├── test_csv_utils.py
│   ├── test_config.py
│   ├── test_duel_attempts.py
│   ├── test_kill_rate_analysis.py
│   ├── test_db_utils.py
│   ├── test_batch_runner.py
│   ├── test_interpretation.py
│   └── test_report_generator.py
├── db_utils.py            # SQLite dual-write (analytics.db)
├── duel_attempts.py       # DuelAttemptFinder
├── kill_rate_analysis.py  # Kill rate pipeline
├── batch_runner.py        # Parallel batch processing (ProcessPoolExecutor)
├── _batch_state.py        # Singleton shared state for Streamlit batch UI
├── interpretation.py      # Per-player coaching interpretation layer
├── report_generator.py    # HTML report builder with base64-embedded charts
├── analytics.db           # SQLite results DB (Phase 6+)
├── timing_summary_stats.csv  # Per-session summary stats
├── for_analysis/          # Drop .dem files here for pipeline input
├── analysis_plots/        # Generated charts output
├── docs/                  # Plans and documentation
├── .claude/               # Claude Code config (hooks, skills)
├── cs2_engagement_analysis_results.csv   # persistent results DB (write-protected via hook)
└── DEPRECATED/            # old notes and phase summaries
```

### Key Files

| File | Role |
|-|-|
| `ddm_analyzer.py` | DDMAnalyzer class — bulk pipeline, T1 detection, CSV output |
| `t0_detector.py` | T0Detector — BVH+AABB visibility, smoke/flash suppression |
| `config.py` | Named constants (tickrate, thresholds, paths) |
| `csv_utils.py` | Append/dedup CSV logic — protects match_id integrity |
| `db_utils.py` | SQLite dual-write — writes to analytics.db alongside CSV |
| `duel_attempts.py` | DuelAttemptFinder — T0-anchored duel attempt pipeline |
| `kill_rate_analysis.py` | Kill rate analysis pipeline |
| `batch_runner.py` | ProcessPoolExecutor batch runner — parallel demo analysis |
| `_batch_state.py` | Singleton module for cross-thread Streamlit state |
| `interpretation.py` | Per-player coaching interpretation layer |
| `report_generator.py` | HTML report builder with base64-embedded charts |
| `visualize_results.py` | Chart generation (histograms, stacked bars, boxplots) |
| `app.py` | Streamlit dashboard |
| `run_analysis.py` | CLI entry point for pipeline |

### Implementation Status (Phase 9 complete, Phase 9.1 next)

- Phases 1–9: DONE (bulk pipeline, BVH T0, filters, dashboard, quality gates, SQLite, batch runner, interpretation, HTML report)
- Phase 9.1 (TODO): performance optimizations (center-ray ordering, selective parse_ticks, per-steamid cache)

### Critical Gotchas

- **Streamlit + ProcessPoolExecutor PicklingError**: Streamlit hot-reload replaces `sys.modules['batch_runner']`; old `analyze_demo_worker` ref ≠ new module object → pickle identity check fails. Fix: `_worker = sys.modules[__name__].analyze_demo_worker` in `BatchRunner.run()` before `pool.submit`.
- **`pd.read_sql` truncates SteamID64**: float64 silently drops precision on 17-digit IDs. Use `cursor.fetchall()` + manual dict construction, never `pd.read_sql` for SteamID columns.
- **`m_bSpotted` / `m_bSpottedByMask`**: Never populated in CS2 GOTV demos — do not use
- **FOV-only T0 detection always fails** for peek scenarios (enemy behind wall in FOV cone)
- **BVH+AABB is the only correct T0 approach** — casts rays to 8 corners of enemy bounding box
- **.tri mesh files** required at `C:\Users\Leo\.awpy\tris\` (download via `awpy_cli(['get','tris'])`)
- **Tick numbers from video timestamps are unreliable** for later rounds — use `player_hurt` events as anchor
- **Flash intervals** use `parse_flash_intervals()` (returns list of tuples) — `parse_flash_end_tick()` was removed
- **`ANTHROPIC_API_KEY` not set in test runs**: `tests/conftest.py` autouse fixture blocks the real Anthropic client; unit tests must monkeypatch `interpretation_narrative._get_client`. Real-API calls only via `python -m interpretation_narrative record-fixture` + the manual eval workflow (`generate-eval-set`, `generate-side-by-side`).
- **Eval rating workflow**: rate v1 + v2 in random order to reduce halo bias on own product (R-10 mitigation). Refer to `evals/README.md` for the 5-dim rubric, SC-1 / SC-6 gates, and the `interpretation_narrative` rate CLI usage.

### CSV Schema (must stay stable)

```
match_id, moment_timestamp, description, t0_source, t0_manual_tick,
t1_aim_start_tick, t2_first_hit_tick, rt_visible_to_aim_ms, rt_aim_to_hit_ms,
rt_visible_to_hit_ms, target_enemy_id, player_velocity_at_t0_ups,
enemy_velocity_at_t0_ups, engagement_type, crosshair_angle_at_t0_deg
```

**Column Details:**
- `crosshair_angle_at_t0_deg`: degrees between player crosshair and enemy at T0; float, None if tick data missing

### Tech Stack & Core Rules

- **Environment:** Python 3.14+ using `demoparser2`, `pandas`, `numpy`, `seaborn`, `streamlit`.
- **Tickrate:** 64 (CS2 demo standard), ms per tick = 15.625ms. Formula: `ticks × (1000 / tickrate)`
- **Isolation Rule:** Never combine data across unrelated categories unless explicitly requested.

### Claude Code Automations

**Hooks** (активны при редактировании через Claude):
- Edit/Write `*.py` → автоформат black + ruff + запуск pytest (`-p no:cov`)
- Edit/Write `cs2_engagement_analysis_results.csv` или `.env` → заблокировано
- `ddm_analysis.log` > 10MB → автоархивирование в `logs/`

**Skills** (вызывать командой `/name`):
- `/add-demo` — запустить пайплайн на новом `.dem` файле в `for_analysis/`
- `/check-phase6` — чеклист edge cases для t0_detector.py / ddm_analyzer.py

### Landing Page

Landing moved to standalone repo: `D:/Obsidian/opacity/40_Projects/djok-landing/` (https://github.com/LeoDiKadyrov/djok-landing). Edit there, not in this repo.

### Code Style

- Strict `typing` hints (Tuple, List, Dict, Optional)
- `@dataclass` for state management (e.g., `AnalysisMoment`)
- Named constants in `config.py` — no magic numbers in logic files