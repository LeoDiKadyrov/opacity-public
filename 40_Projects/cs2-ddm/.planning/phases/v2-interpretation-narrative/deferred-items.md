# Phase v2-interpretation-narrative — Deferred Items

Items discovered during execution that are out of scope for current plan.

## Pre-existing test failures (not caused by Wave 0)

The following 4 tests fail in this worktree because the cwd-local `analytics.db`
is empty / lacks real-data columns that the integration tests expect. These are
pre-existing failures observed BEFORE any Wave 0 changes (verified via `git stash`
on 2026-05-12 during plan 00 execution).

- `tests/test_interpretation.py::test_integration_live_db` — requires populated `analytics.db`
- `tests/test_report_generator.py::test_donk_report_returns_bytes` — same
- `tests/test_report_generator.py::test_donk_report_no_external_urls` — same
- `tests/test_report_generator.py::test_donk_report_has_interpretation_header` — same

**Root cause:** Worktrees clone source but inherit `.gitignore`'d `analytics.db`
state from main (or empty). Integration tests marked with `integration` pytest
mark per `pytest.ini` line 19 ("cwd-sensitive, skip in CI") were not deselected
in the default suite invocation.

**Status:** Out of scope for Wave 0. Will resurface in Wave 4 manual gate when
backfill script runs against real DB on operator's main checkout.

## Notes for downstream plans

- `tests/test_claude_md.py` mentioned in VALIDATION.md Wave 0 Requirements list
  is NOT created in plan 00 (PLAN.md tasks 1–3 don't ship it). Plan 06 task 3
  (`v2-W4-claude-md-doc`) appears to be the rightful owner — flagged for plan
  06 author / verifier.
- `tests/test_eval_harness.py::TestScoreCost` (B-6 SC-4 enforcement) —
  shipped by plan 05 (Wave 3, this commit). 4 tests covering PASS / FAIL /
  SKIP / custom --max-per-report.
