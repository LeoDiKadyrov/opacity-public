---
phase: 09-b2c-delivery
plan: "01"
subsystem: report_generator
tags: [html-report, interpretation, tdd, b2c-delivery]
dependency_graph:
  requires: [interpretation.py, config.py, analytics.db]
  provides: [report_generator.generate_html_report]
  affects: [app.py (plan 09-03)]
tech_stack:
  added: []
  patterns: [sqlite3 cursor.fetchall for SteamID64 safety, inline CSS f-string template, TDD RED/GREEN]
key_files:
  created:
    - report_generator.py
    - tests/test_report_generator.py
  modified: []
decisions:
  - Pure f-string templating chosen over Jinja2 — simpler, no dependency, sufficient for static structure
  - cursor.fetchall() enforced in raw data query — never pd.read_sql (SteamID64 float64 precision loss)
  - empty_db fixture schema must include demo_name column — interpretation.py queries it in _get_percentiles
metrics:
  duration: "4 minutes"
  completed: "2026-05-07"
  tasks_completed: 2
  files_changed: 2
---

# Phase 9 Plan 01: HTML Report Generator — Skeleton + Interpretation Summary

**One-liner:** Self-contained HTML report module with Djok brand tokens, worst-metric card, tier table, and survivorship-bias caveat rows — all CSS inline, zero external URLs.

## What Was Built

`report_generator.py` — new module at project root:
- `generate_html_report(player_steamid, benchmark_steamid, benchmark_name, db_path) -> bytes`
- Calls `compute_interpretation()` + `get_worst_metric()` from `interpretation.py`
- Worst metric card: `#e8b84b` accent border, 28px metric name, gap line, drill text
- Tier table: badge colors per 09-UI-SPEC.md (Elite → `#4ecdc4`, Work needed → `#e8b84b`)
- Survivorship bias caveat rows inserted after each RT metric row
- Raw data via `cursor.fetchall()` — SteamID64 precision preserved
- Distributions section placeholder `<div id="charts-section">` for plan 02
- Passes external-URL safety gate: zero `href`/`src` pointing to `https://`

`tests/test_report_generator.py` — 14 tests:
- 11 unit tests using `empty_db` fixture (minimal in-memory schema)
- 3 integration tests skipped when `analytics.db` absent
- All 14 pass. Full suite: **314 tests pass** (was 300 pre-plan)

## TDD Gate Compliance

- RED commit: `227681e` — 14 failing tests (ModuleNotFoundError — correct)
- GREEN commit: `2a4f43a` — implementation + fixture fix, all 14 pass

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] empty_db fixture missing demo_name column**
- **Found during:** GREEN phase, first test run
- **Issue:** `interpretation.py`'s `_get_percentiles()` queries `demo_name` in `engagements` table. The fixture created the table without that column, causing `pandas.errors.DatabaseError` for all tests.
- **Fix:** Added `demo_name TEXT` to both `engagements` and `duel_attempts` in the fixture schema.
- **Files modified:** `tests/test_report_generator.py`
- **Commit:** `2a4f43a` (combined with implementation)

## Known Stubs

- `<div id="charts-section">` — charts placeholder, intentional. Will be populated by plan 09-02 (base64 chart generation).

## Threat Surface Scan

| Flag | File | Description |
|-|-|-|
| (none) | report_generator.py | All SQL uses parameterised queries (`?` placeholders). No new network endpoints. |

T-09-01 (SQL injection) mitigated: `cursor.execute("... WHERE player_steamid = ?", (player_steamid,))` — no f-string interpolation in SQL.
T-09-03 (external URL) mitigated: regex gate verified in tests and plan verification step.

## Self-Check: PASSED

- FOUND: `report_generator.py`
- FOUND: `tests/test_report_generator.py`
- Commit `227681e` exists (RED)
- Commit `2a4f43a` exists (GREEN)
- 314 tests pass (no regressions)
