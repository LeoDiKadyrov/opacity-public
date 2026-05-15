---
phase: v2-interpretation-narrative
plan: 04
subsystem: report_generator
tags: [html-report, narrative, llm-integration, fail-soft, markdown-to-html, dev-fail-fast]

# Dependency graph
requires:
  - phase: v2-interpretation-narrative
    plan: 02
    provides: build_narrative_report orchestrator + fetch_top_moments + NarrativeBuildError
  - phase: v2-interpretation-narrative
    plan: 01
    provides: narrative_validator (deferred-imported by build_narrative_report)
provides:
  - "generate_html_report narrative wiring (REQ-6)"
  - "fail-soft on NarrativeBuildError (REQ-10)"
  - "DEV_FAIL_FAST=1 unexpected-Exception escape hatch (R-9)"
  - "no_narrative=False/True toggle for SC-6 v1-baseline rendering"
  - "_markdown_to_html_minimal converter for v2 prompt shape"
affects:
  - "v2-interpretation-narrative plan 05 (eval harness — generates reports for scoring)"
  - "v2-interpretation-narrative plan 06 (app.py wire-through + USER-SETUP)"
  - "v2-interpretation-narrative SC-6 (v1-baseline side-by-side)"

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Fail-soft narrative path: NarrativeBuildError → empty section + tier table preserved"
    - "DEV_FAIL_FAST env-var escape hatch for swallowed unexpected exceptions (R-9 mitigation)"
    - "Deferred imports (interpretation_narrative + config.get_logger) inside try block — keeps no_narrative=True path zero-cost on heavy LLM dep"
    - "_markdown_to_html_minimal: regex-split on blank lines + ## prefix detection (no markdown lib dep)"

key-files:
  created: []
  modified:
    - "report_generator.py — generate_html_report signature + narrative block + _markdown_to_html_minimal helper + narrative CSS rules"
    - "tests/test_report_generator.py — TestNarrativeIntegration class (7 tests) + populated_db_for_report fixture extension"

key-decisions:
  - "Pre-attach list-handler to logger by name (DDM.report.{steamid}) instead of caplog because config.get_logger sets propagate=False"
  - "populated_db_for_report fixture creates narrative_cache table inline so build_narrative_report's _cache_get/_cache_put don't OperationalError in tests"
  - "Deferred import of interpretation_narrative inside the try block (not at module top) so no_narrative=True path skips loading the anthropic SDK entirely"
  - "_markdown_to_html_minimal kept hand-rolled (per plan §interfaces decision) — v2 prompt only emits ## headers + paragraphs; swap to markdown lib only if v2.1 grows tables/lists"
  - "Use stub via monkeypatch (compute_interpretation + fetch_top_moments) per plan note — faster than full DB schema mock"

patterns-established:
  - "Fail-soft + dev-fail-fast pair: try/except NarrativeBuildError (expected) followed by try/except Exception with DEV_FAIL_FAST=1 re-raise (unexpected)"
  - "Test capture for non-propagating loggers: attach list handler directly to logger instance, clean up in finally"

requirements-completed: [REQ-6, REQ-10]

# Metrics
duration: 9min
completed: 2026-05-12
---

# Phase v2-interpretation-narrative Plan 04: report_generator narrative integration Summary

**Wires build_narrative_report into generate_html_report between sub-header and Interpretation section with fail-soft on NarrativeBuildError, DEV_FAIL_FAST=1 escape hatch for unexpected exceptions, no_narrative=True toggle for SC-6, and a 20-line _markdown_to_html_minimal converter that turns the v2 prompt's `## Header` + paragraph shape into <h3> + <p> blocks.**

## Performance

- **Duration:** ~9 min
- **Started:** 2026-05-12T13:28:43Z
- **Completed:** 2026-05-12T13:37:59Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 2 (report_generator.py, tests/test_report_generator.py)

## Accomplishments

- `generate_html_report` now accepts `no_narrative: bool = False` (SC-6 v1-baseline toggle)
- Narrative block inserted between sub-header div and `{interpretation_section}` in assembled HTML
- Pass-path: `build_narrative_report` returns markdown → `_markdown_to_html_minimal` → wrapped in `_section("Coach Narrative", …)`
- REQ-10 fail-soft: `NarrativeBuildError` → empty narrative section + tier table preserved + WARNING log via `config.get_logger(f"report.{player_steamid}")` (writes to `ddm_analysis.log`)
- R-9 mitigation: unexpected `Exception` (not `NarrativeBuildError`) re-raises iff `DEV_FAIL_FAST=1`, else logs at ERROR level and falls back
- `top_moments` dict assembly: per (metric × engagement_type) cell, calls `fetch_top_moments` with the matching `benchmark_p50` from the tier-table row; skips cells with NULL benchmark
- `rows_combined` = peek + hold rows tagged with `engagement_type` marker for `build_narrative_report` consumption
- `player_context` dict: `player_steamid`, `player_name` (PLAYER_NAMES lookup with `player_{last4}` fallback), `engagement_type="combined"`, `n_total_engagements`
- Narrative CSS: `.narrative` (left-bordered card), `.narrative-header` (h3 styling), `.narrative-paragraph` (body text)

## Task Commits

1. **Task 1 (RED): TestNarrativeIntegration** — `af32fb2` (test)
2. **Task 1 (GREEN): wire build_narrative_report into generate_html_report** — `36db6c1` (feat)

## Files Created/Modified

- `report_generator.py` — added `import os`, `import re`, `_markdown_to_html_minimal` helper, narrative CSS rules in `_css()`, `no_narrative: bool = False` param on `generate_html_report`, narrative-section try/except block (NarrativeBuildError → fail-soft / Exception → DEV_FAIL_FAST gated), `{narrative_section}` placeholder in assembled HTML between sub-header and interpretation_section.
- `tests/test_report_generator.py` — added `TestNarrativeIntegration` class with 7 tests, `populated_db_for_report` fixture (extends `empty_db` with peek/hold rows + narrative_cache table mirror), `_stub_interpretation_rows` + `_stub_top_moments` + `_attach_capture_handler` helpers.

## Decisions Made

- **Stub via monkeypatch** (per plan §interfaces guidance "second is faster + isolates report_generator from DB schema details"). `compute_interpretation` and `fetch_top_moments` are monkeypatched to return canned dicts; the populated DB only needs to satisfy the tier-table render path + `narrative_cache` PK constraint.
- **List-handler attached to named logger** for failure-log assertions (instead of `caplog`) because `config.get_logger` sets `propagate=False` — `caplog` would not see the records. Handler attached pre-call on `logging.getLogger("DDM.report.1")` and removed in `finally` block.
- **Deferred imports inside try block**: `import interpretation_narrative` and `from config import get_logger` happen lazily inside the narrative path, so `no_narrative=True` skips loading the anthropic SDK entirely (zero cost when narrative path is opted out).
- **Markdown converter kept hand-rolled** (per plan §interfaces decision): 20-line `_markdown_to_html_minimal` regex-splits on `\n{2,}` blocks and detects `## ` prefix. v2 prompt output is constrained to 3 `##` headers + plain paragraphs; no need for a full markdown lib dep yet.

## Deviations from Plan

None — plan executed exactly as written.

The only adjustment was an in-fixture extension: `populated_db_for_report` had to also create the `narrative_cache` table so that `build_narrative_report`'s real `_cache_get`/`_cache_put` calls don't `OperationalError` during the pass-path tests. Plan §behavior already anticipated this via "Or stub via monkeypatch" guidance, but I chose to add the schema mirror to the fixture because the cache I/O is part of the orchestrator contract being exercised in the pass-path tests; bypassing it would have weakened the integration test.

## Issues Encountered

- **`-p no:cov` not honored by pytest.ini's `--cov*` addopts** — first test invocation errored with "unrecognized arguments: --cov=…". Fixed by switching to `--override-ini="addopts=--strict-markers"` per CLAUDE.md Quick Start guidance ("Run without coverage (faster)").
- **Pre-existing test failures** (4 total: `test_integration_live_db`, 3 `test_donk_report_*`) — verified via `git stash` that these fail on the unchanged baseline; root cause is the worktree's `analytics.db` carrying an old pre-Phase-6 schema (no `player_steamid` column). Already documented in `.planning/phases/v2-interpretation-narrative/deferred-items.md`. Out of scope per executor SCOPE BOUNDARY rule.

## Acceptance Criteria

| Check | Result |
|-|-|
| `grep -c "build_narrative_report" report_generator.py` ≥ 1 | 1 |
| `grep -c "fetch_top_moments" report_generator.py` ≥ 1 | 1 |
| `grep -c "NarrativeBuildError" report_generator.py` ≥ 1 | 3 |
| `grep -c "no_narrative" report_generator.py` ≥ 2 | 5 |
| `grep -c "DEV_FAIL_FAST" report_generator.py` ≥ 1 | 2 |
| `grep -c "_markdown_to_html_minimal" report_generator.py` ≥ 2 | 2 |
| `grep -cE "narrative-header\|narrative-paragraph\|class=\"narrative\"" report_generator.py` ≥ 3 | 6 |
| `inspect.signature(generate_html_report)` contains `no_narrative` | OK |
| `python -c "from config import get_logger; print(get_logger.__qualname__)"` (W2 smoke) | `get_logger` |
| `pytest tests/test_report_generator.py::TestNarrativeIntegration` | 7 PASS |
| `pytest tests/test_report_generator.py` | 26 pass / 3 pre-existing skip (no-DB integration) |
| `pytest` full suite | 441 pass / 4 pre-existing fail (deferred-items.md) |

## Notes for Plan Output Section

- **Final `generate_html_report` signature:** `(player_steamid: int, benchmark_steamid: int, benchmark_name: str, db_path: str = DB_PATH, no_narrative: bool = False) -> bytes`
- **`_markdown_to_html_minimal` extension status:** Did NOT need extension beyond `## Header` + paragraphs. The v2 prompt fixture (`tests/fixtures/anthropic_recorded/ok_donk_peek.json`) emits exactly this shape — 3 `##` headers + plain text — and the converter handled it cleanly. No bold/italic/lists in scope.
- **CSS additions:** 3 new rules in `_css()` — `.narrative` (left-bordered card with `#1a1a25` background and `#6a8caf` border), `.narrative-header` (h3 styling, `#c4d4e8` color, font-size 16px font-weight 600), `.narrative-paragraph` (body text, `#d4d4e0` color, line-height 1.6).
- **Test count delta:** +7 tests (TestNarrativeIntegration class). `tests/test_report_generator.py` collected count went from 22 → 29.
- **Behavior with real API key:** Not exercised in this plan's session — would require both `ANTHROPIC_API_KEY` env var and a populated `analytics.db`. The deferred manual smoke from plan §verification (`python -c "from report_generator import generate_html_report; …"`) belongs to plan 06 / Wave 4 manual gate.

## Next Phase Readiness

- **Plan 05** (eval harness) can call `generate_html_report` and rely on the narrative section appearing when LLM cooperates and silently degrading when it doesn't — the fail-soft contract is now testable end-to-end.
- **Plan 06** (app.py + USER-SETUP) can wire a Streamlit UI toggle to pass `no_narrative=True/False` for the SC-6 baseline-vs-narrative side-by-side.
- **No blockers** — narrative path is opt-out via the new param; existing v1 behavior (tier table only) is preserved when `no_narrative=True` is passed.

## Self-Check: PASSED

Files verified:
- `report_generator.py` modified: FOUND
- `tests/test_report_generator.py` modified: FOUND
- `.planning/phases/v2-interpretation-narrative/v2-interpretation-04-SUMMARY.md`: FOUND (this file)

Commits verified:
- `af32fb2` (RED test): FOUND in `git log`
- `36db6c1` (GREEN feat): FOUND in `git log`

---
*Phase: v2-interpretation-narrative*
*Plan: 04*
*Completed: 2026-05-12*
