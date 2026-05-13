---
phase: 09-b2c-delivery
plan: "03"
subsystem: ui
tags: [streamlit, download-button, report-generator, html-report, b2c-delivery]

requires:
  - phase: 09-02
    provides: [report_generator.generate_html_report returning complete HTML bytes with charts]

provides:
  - st.download_button(label="Download Report") wired to report_generator.generate_html_report() in app.py Interpretation section
  - Error state display when report generation fails
  - 3 app.py integration smoke tests

affects: [09-04-manual-verify]

tech-stack:
  added: []
  patterns:
    - import report_generator at module level alongside interpretation imports
    - try/except around generate_html_report() call — st.error() on any exception, no traceback exposed
    - download button placed after for-loop over engagement type tabs, inside if _benchmark_players: block

key-files:
  created: []
  modified:
    - app.py
    - tests/test_report_generator.py

key-decisions:
  - "No st.cache_data on generate_html_report() call — caching deferred (MVP: fast enough, adding cache would require function-scope refactor out of phase scope)"
  - "except Exception (broad catch) in download button block — operator-only local app, no silent failure; st.error() surfaces problem without exposing traceback"

patterns-established:
  - "Broad except + st.error() pattern for in-Streamlit report generation calls"

requirements-completed:
  - Djok delivery format for paying users
  - shareable report output

duration: 5min
completed: 2026-05-07
---

# Phase 9 Plan 03: Streamlit Download Button — app.py Integration

**`st.download_button("Download Report")` wired to `report_generator.generate_html_report()` in app.py Interpretation section — operator can now download a complete self-contained HTML report for any analyzed player.**

## Performance

- **Duration:** ~5 min
- **Started:** 2026-05-07
- **Completed:** 2026-05-07
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- `import report_generator` added to app.py imports (after interpretation import)
- `st.download_button(label="Download Report", data=_html_bytes, file_name=f"djok_report_{_interp_player_sid}.html", mime="text/html")` placed after the peek/hold tabs loop inside `if _benchmark_players:` block (D-08)
- Error fallback: `st.error("Report generation failed. Check that analytics.db contains data for this player.")` on any exception
- 3 integration smoke tests added to `tests/test_report_generator.py`: import check, download button presence, AST syntax validity
- Full test suite: 322 tests pass (was 319, +3 new)

## Task Commits

1. **Task 1: Add report_generator import and st.download_button to app.py** — `bbca9bb` (feat)
2. **Task 2: Integration smoke tests** — `1b567b7` (test)

## Files Created/Modified

- `app.py` — added `import report_generator` + 20-line download button block in Interpretation section
- `tests/test_report_generator.py` — 3 new static integration smoke tests (no DB, no Streamlit run required)

## Decisions Made

- `st.cache_data` deferred — report generation is fast enough for local MVP; caching would require moving to function scope which is out of phase scope.
- `except Exception` (broad catch) chosen deliberately — operator-only local app, `st.error()` surfaces the problem without exposing a Python traceback in the UI.

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Minor: `open('app.py')` in verification command failed with `cp1252` codec error (Windows encoding). Fixed by adding `encoding='utf-8'` in test file reads. Same fix applied to the 3 new test functions.

## Threat Surface Scan

No new network endpoints, auth paths, or trust boundaries introduced. `st.download_button` serves data in-memory to the operator's browser only. T-09-06 (data exposure) and T-09-07 (blocking main thread) both accepted per plan threat register — local-only Phase 9 deployment.

## Known Stubs

None. Download button is fully wired — `generate_html_report()` produces real HTML with charts and data.

## Self-Check

- FOUND: `app.py` (modified — `import report_generator` + `st.download_button` block present)
- FOUND: `tests/test_report_generator.py` (modified — 3 new tests)
- Commit `bbca9bb` exists (feat Task 1)
- Commit `1b567b7` exists (test Task 2)
- 322 tests pass (no regressions)

## Self-Check: PASSED

## Next Phase Readiness

Plan 09-04 (manual verify) can now launch `streamlit run app.py`, select a player, and click "Download Report" to verify the full operator delivery workflow end-to-end.

---
*Phase: 09-b2c-delivery*
*Completed: 2026-05-07*
