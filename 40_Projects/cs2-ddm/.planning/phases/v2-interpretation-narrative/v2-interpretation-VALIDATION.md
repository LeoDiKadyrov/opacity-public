---
phase: v2-interpretation
slug: v2-interpretation-narrative
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-12
---

# Phase v2-interpretation-narrative — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Sourced from RESEARCH.md `## Validation Architecture` table.

---

## Test Infrastructure

| Property | Value |
|-|-|
| **Framework** | pytest 8.x |
| **Config file** | `pyproject.toml` (existing — extends with `tests/test_interpretation_narrative.py`, `tests/test_narrative_validator.py`, `tests/test_top_moments_query.py`) |
| **Quick run command** | `python -m pytest tests/test_interpretation_narrative.py tests/test_narrative_validator.py tests/test_top_moments_query.py tests/test_backfill_round_number.py tests/test_eval_harness.py tests/test_claude_md.py tests/test_no_real_api.py -p no:cov` |
| **Full suite command** | `python -m pytest -p no:cov` |
| **Estimated runtime** | ~45s quick / ~180s full (current 322 tests + ~50 new) |

---

## Sampling Rate

- **After every task commit:** quick run command (covers narrative + validator + top_moments)
- **After every plan wave:** full suite command (regression check across 322 existing tests)
- **Before `/gsd-verify-work`:** full suite green AND eval gate SC-1 ≥4.0 average AND SC-6 side-by-side delta ≥1.0
- **Max feedback latency:** 60s for quick, 240s for full

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|-|-|-|-|-|-|-|-|-|-|
| v2-W0-round-migration | 00 | 0 | upstream-D-01 | — | idempotent ALTER TABLE; no row loss | integration | `python -m pytest tests/test_db_utils.py::test_round_number_migration_idempotent -p no:cov` | ❌ W0 | ⬜ |
| v2-W0-narrative-cache | 00 | 0 | REQ-7 | — | CREATE TABLE narrative_cache idempotent; PK collision → UPSERT | integration | `python -m pytest tests/test_db_utils.py::test_narrative_cache_schema -p no:cov` | ❌ W0 | ⬜ |
| v2-W0-conftest-no-real-api | 00 | 0 | testing-discipline | T-LLM-01 (live API leak) | autouse fixture raises if `ANTHROPIC_API_KEY` resolved during test | unit | `python -m pytest tests/test_no_real_api.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W0-fixtures | 00 | 0 | REQ-3,5 | — | 7 recorded fixtures: clean / with-tick-ref / hallucinated-tick / refusal / max_tokens / 5xx / rate-limit | unit | `python -m pytest tests/fixtures/test_fixtures_load.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W0-backfill-script | 00 | 0 | upstream-D-02 | — | dry-run mode + idempotent re-run | integration | `python scripts/backfill_round_number.py --dry-run` | ❌ W0 | ⬜ |
| v2-W1-validator | 01 | 1 | REQ-5 | T-LLM-02 (hallucination) | tick/round numeric strict; common nouns whitelisted; RU case-insens | unit | `python -m pytest tests/test_narrative_validator.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W1-top-moments | 02 | 1 | REQ-2 | — | excludes cluster-bleed rows; uses cursor.fetchall (SteamID safe) | integration | `python -m pytest tests/test_top_moments_query.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W1-llm-client | 03 | 1 | REQ-3 | T-LLM-03 (cost runaway) | sync Messages API; cache_control on system; usage extracted; SDK retries=2 | unit (mocked) | `python -m pytest tests/test_interpretation_narrative.py::test_call_llm_mocked -p no:cov` | ❌ W0 | ⬜ |
| v2-W2-prompt-template | 04 | 2 | REQ-4 | — | `prompts/coaching_v2.md` exists; contains tone + structure + no-invent instruction | unit | `python -m pytest tests/test_interpretation_narrative.py::test_prompt_template_loaded -p no:cov` | ❌ W0 | ⬜ |
| v2-W2-build-narrative | 05 | 2 | REQ-1 | — | signature `build_narrative_report(rows, top_moments, player_context) → str`; returns markdown | unit (mocked LLM) | `python -m pytest tests/test_interpretation_narrative.py::test_build_narrative_signature -p no:cov` | ❌ W0 | ⬜ |
| v2-W2-report-integration | 06 | 2 | REQ-6,10 | T-LLM-04 (broken report) | narrative inserted between header + tier table; LLM fail → fallback path; logged to `narrative_failures.log` | integration | `python -m pytest tests/test_report_generator.py::test_narrative_pass_path tests/test_report_generator.py::test_narrative_fallback_path -p no:cov` | ❌ W0 | ⬜ |
| v2-W3-eval-harness | 07 | 3 | REQ-8 | — | `evals/interpretation_v2_ratings.csv` schema; 10-row min after eval run | integration | `python -m pytest tests/test_eval_harness.py::test_csv_schema -p no:cov` | ❌ W0 | ⬜ |
| v2-W3-side-by-side | 08 | 3 | SC-6 | — | `evals/v2_side_by_side.csv` schema; 5-row min | integration | `python -m pytest tests/test_eval_harness.py::test_side_by_side_schema -p no:cov` | ❌ W0 | ⬜ |
| v2-W4-cost-cli | 09 | 4 | REQ-9 | — | `python -m interpretation_narrative cost-report` exit 0; tokens + USD printed | smoke | `python -m interpretation_narrative cost-report` | ❌ W0 | ⬜ |
| v2-W4-language-gate | 09 | 4 | REQ-11 | — | eval rubric language = RU; output language detection on 10 reports | manual | rate dim `language` = RU on all 10 | — | ⬜ |
| v2-W0-backfill-tests | 00 | 0 | upstream-D-02 | — | dry-run + idempotent re-run + script exit 0 on empty corpus | unit + integration | `python -m pytest tests/test_backfill_round_number.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W3-score-cost | 05 | 3 | REQ-9, SC-4 | — | `score-cost` CLI exits PASS when avg/report ≤ $0.10, FAIL otherwise | unit + smoke | `python -m pytest tests/test_eval_harness.py::TestScoreCost -p no:cov` | ❌ W0 | ⬜ |
| v2-W4-claude-md-doc | 06 | 4 | REQ-11 (doc) | — | CLAUDE.md mentions `ANTHROPIC_API_KEY` + `interpretation_narrative` after operator update | unit | `python -m pytest tests/test_claude_md.py -p no:cov` | ❌ W0 | ⬜ |
| v2-W4-p95-timing | 06 | 4 | SC-3 | — | `generate-eval-set --emit-timings` writes timings.json; P95 ≤ 30s asserted by plan 06 Task 3 | smoke | `python -m interpretation_narrative generate-eval-set --emit-timings evals/generated/timings.json && python -c "import json; t=json.load(open('evals/generated/timings.json')); assert t['p95_s'] is None or t['p95_s'] <= 30, t"` | ❌ W0 | ⬜ |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_db_utils.py` — extend with `test_round_number_migration_idempotent`, `test_narrative_cache_schema`
- [ ] `tests/test_backfill_round_number.py` — RED + GREEN tests for one-shot backfill script (dry-run + idempotent re-run)
- [ ] `tests/test_claude_md.py` — pytest test asserting `'ANTHROPIC_API_KEY' in CLAUDE.md` + `'interpretation_narrative' in CLAUDE.md` (B-2 fix; ~10 LOC)
- [ ] `tests/test_eval_harness.py::TestScoreCost` — RED + GREEN tests for `score-cost` CLI subcommand (B-6 SC-4 enforcement)
- [ ] `tests/test_no_real_api.py` — autouse fixture blocks live `anthropic.Anthropic()` calls when no `_TEST_ALLOW_LIVE` flag
- [ ] `tests/fixtures/anthropic_recorded/` — 7 JSON fixtures (clean / tick-ref / hallucinated / refusal / max_tokens / 5xx / rate_limit)
- [ ] `tests/fixtures/test_fixtures_load.py` — assert all 7 fixtures parse + minimum field set
- [ ] `tests/test_interpretation_narrative.py` — file stub + signature tests for REQ-1, REQ-3
- [ ] `tests/test_narrative_validator.py` — file stub + adversarial fixtures for REQ-5
- [ ] `tests/test_top_moments_query.py` — file stub for REQ-2 (uses test fixture analytics.db with 30 engagements)
- [ ] `tests/test_eval_harness.py` — file stub for REQ-8, SC-6
- [ ] `tests/conftest.py` — extend with `recorded_anthropic_response` fixture loader
- [ ] `scripts/backfill_round_number.py` — one-shot backfill skeleton (dry-run mode required)
- [ ] `requirements.txt` += `anthropic>=0.89` (already installed in venv per RESEARCH; lock for reproducibility)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|-|-|-|-|
| Eval rating SC-1 ≥4.0 avg + per-dim ≥3.5 | SC-1 | Solo rater Arystan rates 5 dims × 1-5 on 10 reports | Run `python -m interpretation_narrative generate-eval-set` → open generated reports → fill `evals/interpretation_v2_ratings.csv` → run `python -m interpretation_narrative score` |
| Side-by-side SC-6: v2 mean ≥4.0, v1 mean ≤3.0, delta ≥1.0 | SC-6 | Subjective "would_pay_for_this" 1-5 rating on 5 paired reports | Run `python -m interpretation_narrative generate-side-by-side` → rate v1 + v2 per player in `evals/v2_side_by_side.csv` → run `python -m interpretation_narrative score-side-by-side` |
| Tone calibration = brutally honest RU coach | D-10 | Subjective tone judgement during eval rating | Rate `tone` dimension during SC-1 eval pass |
| 1 live smoke call against real Claude API | REQ-3 | Requires real API key; cost ~$0.03; not safe in CI | `_TEST_ALLOW_LIVE=1 python -m pytest tests/test_interpretation_narrative.py::test_live_smoke -p no:cov` (run once before ship; document in eval README) |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (test stubs + fixtures + scripts)
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s (quick) / 240s (full)
- [ ] `nyquist_compliant: true` set in frontmatter (set after planner verifies VALIDATION.md against PLAN.md task IDs)

**Approval:** pending
