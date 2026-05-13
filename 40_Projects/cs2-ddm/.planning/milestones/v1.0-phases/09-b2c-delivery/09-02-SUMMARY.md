---
phase: 09-b2c-delivery
plan: "02"
subsystem: report_generator
tags: [html-report, matplotlib, base64, charts, tdd, b2c-delivery]

requires:
  - phase: 09-01
    provides: [report_generator.generate_html_report, placeholder charts-section div]

provides:
  - _fig_to_b64(fig) -> str: BytesIO-based base64 PNG serializer
  - _chart_for_metric(): histogram with Djok brand colors and player mean overlay
  - _generate_charts_html(): full Distributions section with benchmark distribution charts

affects: [app.py (plan 09-03), manual verify (plan 09-04)]

tech-stack:
  added: [matplotlib (Agg backend), base64, io.BytesIO]
  patterns:
    - matplotlib.use("Agg") at module import — no GUI display, safe for server/Streamlit
    - _KNOWN_COLS whitelist guard for dynamic SQL column names (T-09-05 mitigation)
    - plt.close(fig) after _fig_to_b64() call in every code path

key-files:
  created: []
  modified:
    - report_generator.py
    - tests/test_report_generator.py

key-decisions:
  - "matplotlib.use('Agg') at module level, not inside function — avoids threading issues on repeated calls"
  - "_KNOWN_COLS frozenset whitelist added for T-09-05 SQL column name injection guard"
  - "interp_rows_by_type passed from generate_html_report() to _generate_charts_html() — avoids second DB query for player mean; reuses already-computed interpretation data"

patterns-established:
  - "_fig_to_b64 pattern: BytesIO + savefig(format=png, dpi=96, bbox_inches=tight) + b64encode"

requirements-completed:
  - Djok delivery format for paying users
  - shareable report output

duration: 8min
completed: 2026-05-07
---

# Phase 9 Plan 02: Base64 Chart Generation — Distributions Section

**Matplotlib histogram charts (Djok brand colors, player mean line) embedded as base64 PNG data URIs in the HTML report's Distributions section.**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-05-07T~session
- **Completed:** 2026-05-07
- **Tasks:** 2 (TDD: RED + GREEN)
- **Files modified:** 2

## Accomplishments

- `_fig_to_b64(fig)` — serializes any matplotlib figure to base64 PNG string via BytesIO at 96dpi
- `_chart_for_metric()` — renders histogram (color `#7a7a90`), optional player mean vertical line (`#e8b84b`), full Djok dark theme (bg `#0e0e12`, axes `#16161d`, grid `#2a2a35`)
- `_generate_charts_html()` — queries benchmark player's distribution per metric per engagement type; overlays player mean from already-computed interpretation rows; returns full Distributions section HTML
- `generate_html_report()` updated — placeholder `<div id="charts-section">` replaced with real chart output; falls back to "No distribution data available" when benchmark has no data
- 5 new tests added; full suite grows from 314 to 319 tests

## Task Commits

1. **RED — test(09-02): failing tests for base64 chart functions** — `b9860ef`
2. **GREEN — feat(09-02): _fig_to_b64, _chart_for_metric, _generate_charts_html** — `c631533`

## Files Created/Modified

- `report_generator.py` — added matplotlib imports + 3 chart helper functions + updated generate_html_report()
- `tests/test_report_generator.py` — 5 new tests: _fig_to_b64, distributions base64, section header, caption pattern, safety gate

## Decisions Made

- `matplotlib.use("Agg")` placed at module level (not inside function) to avoid backend switching errors on repeated calls from Streamlit threads.
- `_KNOWN_COLS` frozenset whitelist + `assert col in _KNOWN_COLS` guard implemented for T-09-05 SQL column name injection mitigation, per threat register.
- `interp_rows_by_type` dict passed from `generate_html_report()` into `_generate_charts_html()` — reuses already-computed interpretation rows for player mean, avoiding a redundant DB query.

## Deviations from Plan

None — plan executed exactly as written.

## TDD Gate Compliance

- RED commit: `b9860ef` — 3 failing tests (AttributeError: _fig_to_b64 not found, missing caption pattern — correct)
- GREEN commit: `c631533` — all 19 tests pass

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. All chart data comes from local analytics.db (same DB used in plan 01). SQL column names guarded by `_KNOWN_COLS` whitelist (T-09-05).

## Known Stubs

None. Distributions section is now fully populated with real chart output.

## Self-Check: PASSED

- FOUND: `report_generator.py` (modified)
- FOUND: `tests/test_report_generator.py` (modified)
- Commit `b9860ef` exists (RED)
- Commit `c631533` exists (GREEN)
- 319 tests pass (5 new, no regressions)
- `data:image/png;base64,` present in real donk report output
- External URL safety gate: PASS

## Next Phase Readiness

Plan 09-03 can now add `st.download_button` to app.py — `generate_html_report()` returns complete HTML with charts embedded. No further changes to report_generator.py needed for delivery.

---
*Phase: 09-b2c-delivery*
*Completed: 2026-05-07*
