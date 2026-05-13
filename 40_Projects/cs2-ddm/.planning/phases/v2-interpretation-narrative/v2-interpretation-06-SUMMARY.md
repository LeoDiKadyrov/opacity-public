---
phase: v2-interpretation-narrative
plan: 06
subsystem: ship-gate
tags: [claude-md, sc-3, sc-1, sc-6, manual-gate, operator-handoff, b-2-nyquist]

requires:
  - phase: v2-interpretation-narrative
    plan: 05
    provides: "interpretation_narrative CLI (generate-eval-set --emit-timings, eval-rate, score, generate-side-by-side, rate-side-by-side, score-side-by-side, score-cost, record-fixture, cost-report), evals/v2_eval_player_roster.json (10 real D-15 players), evals/README.md rubric"
  - phase: v2-interpretation-narrative
    plan: 04
    provides: "generate_html_report narrative wiring (no_narrative flag for SC-6)"
provides:
  - "CLAUDE.md Phase v2 LLM coaching layer setup section (ANTHROPIC_API_KEY documentation)"
  - "tests/test_claude_md.py B-2 Nyquist gate (3 grep tests)"
  - "tests/test_v2_sc3_p95.py SC-3 P95 timings.json schema smoke (4 tests)"
  - "Operator handoff: 4 of 6 tasks remain — backfill (Task 2), real-API eval generation (Task 3 remainder), SC-1 rating (Task 4), SC-6 side-by-side (Task 5), final ship verification (Task 6)"
affects:
  - "Wave 4 ship gate — SC-1, SC-3, SC-4, SC-6 hard gates pending operator execution"
  - "Verifier (v2-07-verify if planned) — will rely on these gates being closed"

tech-stack:
  added: []
  patterns:
    - "Nyquist gate test pattern: tiny grep-only pytest module that converts a CLAUDE.md edit into automated-verifiable type='auto' task per Plan-checker Rule 8a"
    - "Targeted gate-named test file (test_v2_sc3_p95.py) keeps SC-3 verifier grep-discoverable independent of broader CLI suite"

key-files:
  created:
    - tests/test_claude_md.py
    - tests/test_v2_sc3_p95.py
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-06-SUMMARY.md
  modified:
    - CLAUDE.md

key-decisions:
  - "Split Plan 06 into auto-now (Tasks 1 + 3-sub) and operator-pending (Tasks 2, 3-remainder, 4, 5, 6); user-context constraint 'I need to leave computer' makes any live-API task non-executable by the agent."
  - "Plan 06's Task 3 example snippet referenced 'seconds' / 'status' keys, but the actual --emit-timings JSON (shipped Plan 05) uses 'elapsed_s' / 'ok' inside per-entry dicts plus top-level 'p95_s'. New SC-3 schema smoke binds to the real Plan 05 contract (D-04 ok-only p95 decision), not the plan text."
  - "STATE.md / ROADMAP.md NOT modified per parallel_execution constraint — orchestrator owns those."

requirements-completed: []
requirements-pending: [REQ-3, REQ-8, REQ-11]

duration: ~12 min (auto portion)
completed: 2026-05-12 (auto portion only — operator gates pending)
---

# Phase v2-interpretation-narrative Plan 06: Wave 4 Ship Gate Summary

**Auto portion complete (2 of 6 tasks); 4 operator-pending checkpoints surfaced for user to execute when back at machine.**

## Status Table

| # | Task | Type | Status | Commit / Note |
|-|-|-|-|-|
| 1 | CLAUDE.md ANTHROPIC_API_KEY + v2 quickstart + B-2 Nyquist gate | auto | DONE | `ff22e5a` |
| 2 | Backfill round_number overnight (R-2 mitigation) | checkpoint:human-action | PENDING-OPERATOR | optional skip allowed |
| 3 | Generate v2 eval set + 1 live smoke + 2 fixture refresh + cost-report | auto + operator | AUTO SUB DONE (`d832336` SC-3 schema smoke); LIVE-API SUB PENDING-OPERATOR | requires ANTHROPIC_API_KEY |
| 4 | Rate 10 reports × 5 dims (SC-1 hard gate, 50 ratings) | checkpoint:human-verify | PENDING-OPERATOR | blocking ship |
| 5 | Side-by-side 5 pairs rated (SC-6 hard gate) | checkpoint:human-verify | PENDING-OPERATOR | blocking ship |
| 6 | Final cost-report + ship verification (full pytest + score + score-side-by-side + score-cost) | auto | PENDING-OPERATOR | depends on 4 + 5 |

**Auto-done × 2 | Operator-pending × 4**

## Auto Work Completed

### Task 1 — CLAUDE.md updates + B-2 Nyquist gate (commit `ff22e5a`)

Inserted new "Phase v2 — LLM coaching layer setup" section after the existing Quick Start code block:

- API key export instruction (sk-ant-... format, console.anthropic.com link)
- 5-step CLI workflow (cost-report → generate-eval-set → eval-rate → score)
- Cost expectations (~\$0.026/report, cold-cache eval ~\$0.26, SC-4 \$0.10/report hard gate)
- Fail-soft semantics: missing key → tier table preserved, narrative silently empty, diagnostic in `narrative_failures.log`

Added two new Critical Gotchas:

- conftest.py autouse fixture blocks the real Anthropic client; unit tests must monkeypatch `interpretation_narrative._get_client`; real-API calls only via `record-fixture` CLI + manual eval workflow.
- Rate v1 + v2 in random order to reduce halo bias on own product (R-10 mitigation); refer to `evals/README.md` for the 5-dim rubric.

Created `tests/test_claude_md.py` (B-2 Nyquist gate, 3 tests):

- `test_anthropic_api_key_documented` — asserts `ANTHROPIC_API_KEY` substring present
- `test_interpretation_narrative_module_referenced` — asserts module name referenced
- `test_narrative_failures_log_referenced` — asserts diagnostic log location documented

Grep counts (acceptance criteria thresholds):

| Substring | Count | Gate |
|-|-|-|
| `ANTHROPIC_API_KEY` | 3 | ≥2 PASS |
| `interpretation_narrative` | 10 | ≥3 PASS |
| `narrative_failures.log` | 1 | ≥1 PASS |

Pytest: 3/3 PASS via `--override-ini="addopts=--strict-markers" -p no:cov`.

### Task 3 auto sub — SC-3 P95 schema smoke (commit `d832336`)

The real SC-3 ≤30s gate is operator-executed (Task 3 generate-eval-set step requires `ANTHROPIC_API_KEY` + ~10 live LLM calls, ~\$0.26 spend). The auto-verifiable sub is the contract that lets the operator's `assert p95 <= 30.0` command actually work end-to-end.

Created `tests/test_v2_sc3_p95.py` (4 tests, monkeypatched `report_generator.generate_html_report` — no DB / no LLM):

- `test_timings_payload_top_level_schema` — payload has `timings, p95_s, n_ok, n_total`
- `test_timings_per_entry_schema` — each row has `player_steamid (int), name, ok (bool), elapsed_s (≥0)`
- `test_p95_uses_ok_only_samples` — D-04 decision (ok-only p95) preserved
- `test_sc3_gate_assert_is_expressible` — replicates Plan 06 operator's `assert p95 <= 30.0` against stub data, proving the wiring

Pytest: 4/4 PASS.

**Why a separate file instead of folding into `test_eval_harness.py`?** SC-3 is its own success criterion; grep-by-criterion (e.g. `rg "SC-3"`) should land in one place. Plan 05's `TestCLISmoke.test_generate_eval_set_emit_timings_flag_recognized` covers the broader contract; this file is the targeted gate-named verifier for Plan 06.

## Operator-Pending Tasks (Resume Instructions)

### Task 2 — Backfill `round_number` overnight (R-2 mitigation, optional)

**What to run:**

```bash
# 1. Backup before
cp analytics.db analytics.db.pre-v2-backfill

# 2. Dry-run scope check
python scripts/backfill_round_number.py --db analytics.db \
    --demo-dir ../for_analysis/spirit ../for_analysis/faze --dry-run

# 3. Real overnight run (~6h wall)
python scripts/backfill_round_number.py --db analytics.db \
    --demo-dir ../for_analysis/spirit ../for_analysis/faze

# 4. Coverage check
python -c "import sqlite3; c=sqlite3.connect('analytics.db'); \
total=c.execute('SELECT COUNT(*) FROM engagements').fetchone()[0]; \
with_rn=c.execute('SELECT COUNT(*) FROM engagements WHERE round_number IS NOT NULL').fetchone()[0]; \
print(f'{with_rn}/{total} = {100*with_rn/total:.1f}%')"
```

**Exit gate:** `round_number IS NOT NULL` ≥80% of total, OR explicit skip with rationale logged ("attribution will be sparser this iteration; revisit v2.1").

**Skip allowed:** This gate is documented in plan as optional — eval-set generation works without round_number, narrative just gets fewer attribution callouts.

### Task 3 remainder — Real-API eval generation + 2 fixture refresh

**Prerequisites:** `ANTHROPIC_API_KEY` exported (Task 1 docs the source).

**What to run:**

```bash
# 1. Verify key present
python -c "import os; assert os.environ.get('ANTHROPIC_API_KEY'), 'NO API KEY'; print('OK')"

# 2. Generate eval set + timings (cold cache — first call hits LLM for all 10)
python -m interpretation_narrative generate-eval-set \
    --out-dir evals/generated --emit-timings evals/generated/timings.json

# 3. Enforce SC-3 ≤30s gate (reads timings.json p95_s)
python -c "import json; d=json.load(open('evals/generated/timings.json')); \
p95=d['p95_s']; assert p95 is not None and p95 <= 30.0, \
f'SC-3 FAIL: p95={p95}s'; print(f'SC-3 PASS: p95={p95:.2f}s, n_ok={d[\"n_ok\"]}/{d[\"n_total\"]}')"

# 4. Manual HTML smoke — open ONE generated v2_*.html in browser, verify:
#    - "Coach Narrative" section at top (above Interpretation)
#    - 3 sub-sections: "Что у тебя получается", "Где теряешь время", "Action этой недели"
#    - At least one DIRECTIONS title cited verbatim
#    - No hallucination (tick/round refs match player's data)
#    - Length ≤600 words

# 5. Refresh 2 W0 placeholder fixtures with real-API output
python -m interpretation_narrative record-fixture \
    --player 76561198386265483 --type peek \
    --out tests/fixtures/anthropic_recorded/ok_donk_peek.json
python -m interpretation_narrative record-fixture \
    --player 76561197989430253 --type peek \
    --out tests/fixtures/anthropic_recorded/clean_paraphrase.json

# 6. Verify refreshed fixtures still pass schema check
python -m pytest tests/fixtures/test_fixtures_load.py tests/test_narrative_validator.py \
    --override-ini="addopts=--strict-markers" -p no:cov

# 7. Cost-report sanity (≤ $0.50 for 10 reports + 2 fixtures)
python -m interpretation_narrative cost-report
```

**Exit gates:**

- `ls evals/generated/v2_*.html | wc -l` ≥ 8
- `grep -l "Coach Narrative" evals/generated/v2_*.html | wc -l` ≥ 8
- `timings.json` `p95_s` ≤ 30 (SC-3)
- `ok_donk_peek.json` `captured_at` is a real recent timestamp (not the W0 placeholder `2026-05-13T10:00:00Z`)
- `pytest tests/fixtures/test_fixtures_load.py` PASS
- `cost-report` shows non-zero total, ≤\$0.50

**Spend cap:** if `cost-report` shows ≥\$2 after one generate-eval-set + 2 record-fixture, STOP and investigate (max_tokens cap? retries?).

### Task 4 — Rate 10 reports × 5 dimensions (SC-1 hard gate)

**Prerequisites:** Task 3 generated `evals/generated/v2_*.html` (10 files).

**What to run** (for EACH of 10 reports):

```bash
# Open HTML in browser, then 5 CLI invocations per report:
python -m interpretation_narrative eval-rate \
    --report-id v2_donk --player 76561198386265483 \
    --dim factual_accuracy --score 4 --notes "..."
python -m interpretation_narrative eval-rate \
    --report-id v2_donk --player 76561198386265483 \
    --dim actionability --score 5 --notes "..."
python -m interpretation_narrative eval-rate \
    --report-id v2_donk --player 76561198386265483 \
    --dim tone --score 4 --notes "..."
python -m interpretation_narrative eval-rate \
    --report-id v2_donk --player 76561198386265483 \
    --dim attribution --score 5 --notes "..."
python -m interpretation_narrative eval-rate \
    --report-id v2_donk --player 76561198386265483 \
    --dim hallucinations --score 5 --notes "..."  # INVERSE: 5=none, 1=many

# After all 50 ratings:
python -m interpretation_narrative score
```

**Rubric:** `evals/README.md` (172 lines, 5-dim anchored).

**Exit gate (SC-1 PASS):** `avg ≥4.0 AND per-dim ≥3.5 AND n_reports ≥10 AND row_count ≥50 AND n_distinct_real_players ≥10`. Every rated SteamID must map to a non-placeholder PLAYER_NAMES entry (B-1+B-4 + B-C revision — see Plan 04 acceptance criterion verbatim).

**FAIL branches:**

- Avg fail → iterate `prompts/coaching_v2.md` → re-generate (Task 3 step 2) → re-rate. Old ratings preserved in CSV under prior `prompt_hash`.
- Per-dim floor fail → target the failing dim (e.g. attribution<3.5 → add "В каждой секции упомяни хотя бы 1 момент с demo + раунд + тик" to prompt).

**Budget:** ~\$0.30 per iteration × 5 iterations max = \$1.50 ceiling before scope-shift discussion.

### Task 5 — Side-by-side 5 pairs (SC-6 hard gate)

**Prerequisites:** Task 4 SC-1 PASS.

```bash
# 1. Generate 5 paired reports (v1 = no_narrative, v2 = full)
python -m interpretation_narrative generate-side-by-side --pairs 5

# 2. For each of 5 pairs: open BOTH HTML files side-by-side in browser, decide
#    "which would you pay for?", then rate:
python -m interpretation_narrative rate-side-by-side \
    --pair-id pair_001 --player <sid> \
    --preferred v2 --v1-rating 2 --v2-rating 4 \
    --notes "v2 tells me what to do, v1 just gives a table"

# 3. Verdict
python -m interpretation_narrative score-side-by-side
```

**Exit gate (SC-6 PASS):** `v2_mean ≥4.0 AND v1_mean ≤3.0 AND delta ≥1.0 AND n_pairs ≥5`.

**FAIL branches:** plan documents 3 distinct failure modes (v2 too low / v1 too high / delta too small) each with iteration plan.

**Soft signal:** if `preferred_dist` < 4/5 prefer v2 despite Likert gates passing, document in next SUMMARY iteration as "passed but forced-choice 60/40 — not yet definitive win".

### Task 6 — Final ship verification (auto, post-4+5)

```bash
# 1. Final cost-report (expected ≤$5 total across phase)
python -m interpretation_narrative cost-report

# 2. Re-run all 3 verdict gates
python -m interpretation_narrative score
python -m interpretation_narrative score-side-by-side
python -m interpretation_narrative score-cost

# 3. Fail-soft verification (no narrative path preserved)
env -u ANTHROPIC_API_KEY python -c "from report_generator import generate_html_report; \
html = generate_html_report(76561198386265483, 76561198386265483, 'donk').decode(); \
assert 'Coach Narrative' not in html; assert 'Interpretation' in html; \
print('fail-soft OK — tier table preserved')"

# 4. Full pytest suite (≥350 tests, must be green except pre-existing
#    test_interpretation.py::test_integration_live_db documented in
#    deferred-items.md — empty worktree analytics.db, out of scope)
python -m pytest --override-ini="addopts=--strict-markers" -p no:cov

# 5. Fall-back rate sample (SC-5: ≤5% on ≥15 reports = ≤1 failure)
python -c "import sqlite3; c=sqlite3.connect('analytics.db'); \
print('cached:', c.execute('SELECT COUNT(*) FROM narrative_cache').fetchone()[0])"
wc -l narrative_failures.log 2>/dev/null || echo "0 narrative_failures.log"
```

**Exit gates:** all 4 CLIs exit 0, fail-soft passes, full pytest green (modulo pre-existing live-DB skip), fall-back ≤1 failure.

## Deviations from Plan

**None on the auto portion.** All Task 1 and Task 3-sub work matched plan text verbatim. Two minor observations carried forward as Plan-text accuracy notes (not behavioral deviations):

1. **Plan 06 Task 3 example timings JSON shape** (lines 220-227) shows `{"seconds": 18.4, "status": "ok"}` per entry. Real implementation (Plan 05, `--emit-timings` shipped via D-04 decision) writes `{"elapsed_s": 18.4, "ok": true}` and the top-level shape is `{timings: [...], p95_s, n_ok, n_total}`. The new SC-3 schema smoke binds to the real Plan 05 contract. Plan 06 operator commands later in the same Task (line 230) actually use `d['seconds']` which would `KeyError` — operator Task 3 retry command is the canonical version: `assert d['p95_s'] <= 30.0`. Documented in Task 3 resume instructions above.

2. **Pytest invocation** must use `--override-ini="addopts=--strict-markers" -p no:cov` (the CLAUDE.md Quick Start pattern) because `pytest.ini` `addopts` injects `--cov=*` flags that the cov plugin no longer accepts on Python 3.14. Plan 05 SUMMARY already documented this; Plan 06 SUMMARY restates it for any operator running the gates fresh.

**Total Rule 1-4 invocations:** 0.

## Files Created / Modified

- `CLAUDE.md` — modified: +27 lines Phase v2 setup section, +2 Critical Gotchas
- `tests/test_claude_md.py` — created: 36 lines, 3 grep tests (B-2 Nyquist)
- `tests/test_v2_sc3_p95.py` — created: 137 lines, 4 schema smoke tests
- `.planning/phases/v2-interpretation-narrative/v2-interpretation-06-SUMMARY.md` — this file

**STATE.md / ROADMAP.md NOT modified** — orchestrator owns those per parallel-execution constraint.

## Task Commits

1. **Task 1 (auto):** `ff22e5a` — `docs(v2-06): CLAUDE.md adds ANTHROPIC_API_KEY + v2 quickstart (B-2)`
2. **Task 3 sub (auto):** `d832336` — `test(v2-06): SC-3 P95 timings.json schema smoke (Task 3 auto sub)`

## Test Counts

- Plan 06 net add: +7 tests (3 in `test_claude_md.py`, 4 in `test_v2_sc3_p95.py`)
- All 7 PASS via `--override-ini="addopts=--strict-markers" -p no:cov`
- Full suite at SUMMARY time: 485 pass / 4 skip / 1 pre-existing fail (`test_integration_live_db` — documented in Plan 05 `deferred-items.md`, out of scope per executor scope-boundary rule)
- Net regression: 0

## Issues Encountered

- **`pytest.ini` cov plugin override.** Default `python -m pytest` injects `--cov=csv_utils --cov=config ...` which cov plugin rejects on Python 3.14. Used `--override-ini="addopts=--strict-markers"` per CLAUDE.md Quick Start. No code change.
- **Worktree base commit drift.** Worktree HEAD at session start was `8f1049f` (docs AGENTS.md commit) not the expected base `f8d8a83`. Hard-reset to `f8d8a83` per executor `<worktree_branch_check>` protocol before starting Task 1. Verified `git rev-parse HEAD == f8d8a83` post-reset.

## Self-Check: PASSED

Verified files + commits in tree:

- `CLAUDE.md` Phase v2 section — FOUND (grep `ANTHROPIC_API_KEY` = 3)
- `tests/test_claude_md.py` — FOUND (3 tests pass)
- `tests/test_v2_sc3_p95.py` — FOUND (4 tests pass)
- Commit `ff22e5a` (Task 1 — CLAUDE.md + Nyquist) — FOUND in `git log`
- Commit `d832336` (Task 3 sub — SC-3 schema smoke) — FOUND in `git log`

## Threat Flags

None. Plan 06 added documentation + test-only files. No new network endpoints, auth paths, file access patterns, or schema changes.

## Known Stubs

None. All shipped code is test infrastructure or documentation; no UI stubs introduced.

## Next Phase Readiness

**For the operator (Arystan) when back at machine:**

1. Read this SUMMARY's "Operator-Pending Tasks" section top to bottom.
2. Decide Task 2 (skip or run overnight before bed). If skipping, log rationale in next SUMMARY iteration.
3. Set `ANTHROPIC_API_KEY` env var.
4. Run Task 3 remainder (~\$0.26, ~5 min wall).
5. Manually browse one HTML report to smoke-check.
6. Rate Task 4 (50 invocations, ~30-45 min focused).
7. If SC-1 PASS: proceed to Task 5 (~30 min).
8. If SC-1 FAIL: iterate `prompts/coaching_v2.md`, re-run Task 3 step 2, re-rate. Budget 5 iterations max.
9. After SC-1 + SC-6 both PASS: run Task 6 auto verification commands.
10. Hand off to `/gsd-verify-work v2-interpretation-narrative` once Task 6 prints all green.

**For the orchestrator:**

- This SUMMARY is intentionally NOT a "plan complete" signal. The plan has 4 operator-pending tasks remaining (Tasks 2, 3-remainder, 4, 5, 6). Do NOT advance STATE.md `current_plan` past 06 until operator confirms Task 6 ship verification PASS.
- Auto portion (Tasks 1 + Task 3 sub) is shippable as a standalone increment to the v2 worktree — adds documentation + 7 tests, 0 regressions.

---
*Phase: v2-interpretation-narrative*
*Plan 06 — Wave 4 ship gate*
*Auto portion completed: 2026-05-12 (operator gates pending)*
