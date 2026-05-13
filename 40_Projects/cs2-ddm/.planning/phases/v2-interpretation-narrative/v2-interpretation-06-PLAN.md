---
phase: v2-interpretation-narrative
plan: 06
type: execute
wave: 4
depends_on: [03, 04, 05]
files_modified:
  - tests/fixtures/anthropic_recorded/ok_donk_peek.json
  - tests/fixtures/anthropic_recorded/clean_paraphrase.json
  - prompts/coaching_v2.md
  - evals/interpretation_v2_ratings.csv
  - evals/v2_side_by_side.csv
  - CLAUDE.md
  - tests/test_claude_md.py
autonomous: false
requirements: [REQ-8, REQ-11, REQ-3]
must_haves:
  truths:
    - "ANTHROPIC_API_KEY env var documented in CLAUDE.md (operator setup gate)"
    - "scripts/backfill_round_number.py executed against analytics.db (operator gate from W0) — round_number populated for ≥80% of existing rows OR explicitly skipped with rationale"
    - "10 v2 reports generated under evals/generated/ via generate-eval-set"
    - "All 10 reports rated on 5 dims (50 ratings min) → score command returns SC-1 PASS (≥4.0 avg, ≥3.5 floor)"
    - "5 side-by-side pairs generated + rated → score-side-by-side returns SC-6 PASS (v2 ≥4.0, v1 ≤3.0, delta ≥1.0)"
    - "1 live smoke call against real Claude API succeeded (REQ-3 manual smoke)"
    - "≥2 W0 recorded fixtures refreshed with real-API output (ok_donk_peek.json, clean_paraphrase.json)"
    - "Cost-report shows total cost ≤$5 across the eval iteration"
  artifacts:
    - path: "evals/interpretation_v2_ratings.csv"
      provides: "Filled rating data — ≥50 rows for SC-1"
      min_lines: 50
    - path: "evals/v2_side_by_side.csv"
      provides: "Filled side-by-side data — 5 rows for SC-6"
      min_lines: 5
    - path: "tests/fixtures/anthropic_recorded/ok_donk_peek.json"
      provides: "Refreshed real-API capture (replaces W0 placeholder)"
      contains: "captured_at"
    - path: "CLAUDE.md"
      provides: "ANTHROPIC_API_KEY setup section + cost notes"
      contains: "ANTHROPIC_API_KEY"
  key_links:
    - from: "operator gate (manual)"
      to: "evals/interpretation_v2_ratings.csv"
      via: "user rates 50 entries via eval-rate CLI"
      pattern: "rated_at"
    - from: "score CLI"
      to: "SC-1 verdict"
      via: "aggregation against ratings.csv with prompt_hash filter"
      pattern: "SC-1 verdict"
---

<objective>
Wave 4 ship gate. This plan operationalizes manual gates that automation cannot bypass: backfill execution, prompt iteration to SC-1 PASS, side-by-side rating to SC-6 PASS, fixture refresh, CLAUDE.md doc updates.

Purpose: SC-1 + SC-6 are the hard ship gates per SPEC. They require human rating on real-API output. This plan walks the operator (Arystan) through the exact sequence with breakpoints between automated steps for verification + decision.

Output:
- Backfill executed (operator-night run, optional but recommended for attribution coverage)
- prompts/coaching_v2.md tuned to SC-1 PASS (may iterate 1-5 times)
- evals/interpretation_v2_ratings.csv populated with ≥50 rated rows
- evals/v2_side_by_side.csv populated with 5 rated pairs
- 2 fixtures refreshed
- CLAUDE.md gains "ANTHROPIC_API_KEY setup" section
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-00-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-01-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-02-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-03-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-04-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-05-SUMMARY.md
@CLAUDE.md
</context>

<tasks>

<task type="auto">
  <name>Task 1: CLAUDE.md update — ANTHROPIC_API_KEY setup + v2 quickstart + Nyquist-satisfying test</name>
  <files>CLAUDE.md, tests/test_claude_md.py</files>
  <read_first>
    - CLAUDE.md current (esp. "Quick Start" + "Tech Stack & Core Rules" sections)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §R-7 ANTHROPIC_API_KEY (line 891)
  </read_first>
  <action>
    Add a new section to CLAUDE.md after the existing "Quick Start" code block:
    ```markdown
    ### Phase v2 — LLM coaching layer setup

    Phase v2 (interpretation_narrative) requires Anthropic API access:

    ```bash
    # 1. Set API key (get from https://console.anthropic.com/settings/keys)
    export ANTHROPIC_API_KEY="sk-ant-..."

    # 2. Run cost monitoring
    python -m interpretation_narrative cost-report

    # 3. Generate eval set (10 reports)
    python -m interpretation_narrative generate-eval-set

    # 4. Rate per dim (50 ratings minimum for SC-1)
    python -m interpretation_narrative eval-rate --report-id v2_donk --player 76561198386265483 \
        --dim tone --score 4 --notes "немного хеджирует"

    # 5. Check verdict
    python -m interpretation_narrative score
    ```

    Cost: ~$0.026/report (sonnet-4-6, ~5k input + 700 output tokens).
    Eval set cold-cache: ~$0.26 per iteration.

    If `ANTHROPIC_API_KEY` is unset, HTML reports still ship via fail-soft (tier table only,
    narrative section silently empty). See `narrative_failures.log` for diagnostic.
    ```

    Also add to "Critical Gotchas" section:
    - "**`ANTHROPIC_API_KEY` not set in test runs**: tests/conftest.py autouse fixture blocks real Anthropic client; tests must monkeypatch `interpretation_narrative._get_client`. Real-API calls only in `record-fixture` CLI + manual eval workflow."
    - "**Eval rating workflow**: rate v1 + v2 in random order to reduce halo bias on own product (R-10 mitigation)."

    **B-2 (Nyquist gate satisfaction):** create `tests/test_claude_md.py` (~5 LOC) so this CLAUDE.md edit is automated-verifiable per Nyquist Rule 8a (otherwise `type="auto"` task would have grep-only verify):
    ```python
    """B-2 — Nyquist gate: confirm CLAUDE.md documents ANTHROPIC_API_KEY for v2."""
    from pathlib import Path

    def test_anthropic_api_key_documented():
        text = Path("CLAUDE.md").read_text(encoding="utf-8")
        assert "ANTHROPIC_API_KEY" in text, "v2 phase requires ANTHROPIC_API_KEY documented in CLAUDE.md"

    def test_interpretation_narrative_module_referenced():
        text = Path("CLAUDE.md").read_text(encoding="utf-8")
        assert "interpretation_narrative" in text, "CLAUDE.md must reference the v2 module name"
    ```
  </action>
  <verify>
    <automated>python -m pytest tests/test_claude_md.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "ANTHROPIC_API_KEY" CLAUDE.md` ≥ 2
    - `grep -c "interpretation_narrative" CLAUDE.md` ≥ 3
    - `grep -c "narrative_failures.log" CLAUDE.md` ≥ 1
    - `python -m pytest tests/test_claude_md.py -p no:cov` PASS (B-2 Nyquist gate)
  </acceptance_criteria>
  <done>
    CLAUDE.md documents the API key setup, cost expectations, and where logs land. Operator instructions for the v2 manual workflow are now in the canonical project doc.
  </done>
</task>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 2: Operator runs backfill_round_number.py overnight (R-2 mitigation)</name>
  <files>analytics.db</files>
  <action>
    OPERATOR-EXECUTED. Sequence:

    1. Backup analytics.db before running:
       ```bash
       cp analytics.db analytics.db.pre-v2-backfill
       ```

    2. Dry-run first to see scope:
       ```bash
       python scripts/backfill_round_number.py --db analytics.db \
           --demo-dir ../for_analysis/spirit ../for_analysis/faze --dry-run
       ```
       Expected output: "Demos processed: ~80, rows updated: ~5557". If counts look wrong, STOP and investigate.

    3. Real run (overnight, ~6h wall):
       ```bash
       python scripts/backfill_round_number.py --db analytics.db \
           --demo-dir ../for_analysis/spirit ../for_analysis/faze
       ```

    4. After completion, verify coverage:
       ```bash
       python -c "import sqlite3; c=sqlite3.connect('analytics.db'); total=c.execute('SELECT COUNT(*) FROM engagements').fetchone()[0]; with_rn=c.execute('SELECT COUNT(*) FROM engagements WHERE round_number IS NOT NULL').fetchone()[0]; print(f'{with_rn}/{total} = {100*with_rn/total:.1f}%')"
       ```
       Expect ≥80% coverage. Demos missing on disk are acceptable shortfall.

    5. **Optional skip:** this gate can be deferred if eval-set generation works without round_number attribution (validator just gets fewer allowed rounds → fewer attribution callouts in narrative). Skip with explicit rationale logged in summary: "round_number coverage at <X>%; narrative attribution will be sparser this iteration; revisit in v2.1".

    Resume signal to operator: type "backfill done <X>%" with coverage percent, OR "skipping backfill, proceeding without attribution polish".
  </action>
  <verify>
    <automated>python -c "import sqlite3; c=sqlite3.connect('analytics.db'); total=c.execute('SELECT COUNT(*) FROM engagements').fetchone()[0]; with_rn=c.execute('SELECT COUNT(*) FROM engagements WHERE round_number IS NOT NULL').fetchone()[0]; print(f'{with_rn}/{total}'); assert with_rn / total >= 0.80 if total > 0 else True"</automated>
  </verify>
  <acceptance_criteria>
    - Either: `round_number IS NOT NULL` rows ≥80% of total engagements rows
    - Or: explicit operator skip recorded in summary with rationale
    - analytics.db.pre-v2-backfill backup file exists on disk
  </acceptance_criteria>
  <done>
    Backfill complete (or explicitly deferred). Attribution baseline ready for narrative generation.
  </done>
</task>

<task type="auto">
  <name>Task 3: Generate v2 eval set + 1 live smoke call (REQ-3 manual smoke)</name>
  <files>tests/fixtures/anthropic_recorded/ok_donk_peek.json, tests/fixtures/anthropic_recorded/clean_paraphrase.json</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md (manual gates section)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-05-SUMMARY.md (CLI usage)
  </read_first>
  <action>
    1. Verify `ANTHROPIC_API_KEY` is set:
       ```bash
       python -c "import os; assert os.environ.get('ANTHROPIC_API_KEY'), 'NO API KEY'; print('OK')"
       ```

    2. Generate full eval set with per-report timing instrumentation (B-6 — SC-3 gate):
       ```bash
       python -m interpretation_narrative generate-eval-set --out-dir evals/generated --emit-timings evals/generated/timings.json
       ```
       The `--emit-timings` flag wraps each per-report build in `time.perf_counter()` (cold cache; the first generate-eval-set call has empty cache so all calls hit the LLM). Output JSON shape:
       ```json
       [
         {"player_steamid": 76561198386265483, "name": "donk", "seconds": 18.4, "status": "ok"},
         {"player_steamid": 76561197989430253, "name": "karrigan", "seconds": 22.1, "status": "ok"},
         ...
       ]
       ```
       After generation, compute SC-3 P95 gate:
       ```bash
       python -c "import json, statistics; data = json.load(open('evals/generated/timings.json')); ok = [d['seconds'] for d in data if d['status'] == 'ok']; assert ok, 'no successful generations to time'; ok.sort(); p95 = ok[int(len(ok) * 0.95)] if len(ok) >= 2 else ok[-1]; print(f'P95 = {p95:.2f}s (gate ≤30s, n={len(ok)})'); assert p95 <= 30.0, f'SC-3 FAIL: P95 {p95:.2f}s > 30s'"
       ```
       (Implementation note for the Plan 05 executor when this plan runs: add `--emit-timings` arg to the `generate-eval-set` argparse subcommand; wrap the per-iteration `generate_html_report(...)` call in `t0 = time.perf_counter(); ...; entries.append({...,"seconds": time.perf_counter() - t0})`; write `entries` to the path on completion. ~10 LOC addition.)

       Expected: 10 HTML files written under `evals/generated/v2_<name>.html`. Each must contain `Coach Narrative` section. If any FAILS (raise output captured), inspect `narrative_failures.log` and decide: (a) iterate prompt + retry, (b) skip the failing player + document. SC-3 P95 ≤30s gate emits explicit PASS/FAIL exit code via the assert.

    3. Smoke check 1 file manually — open one HTML in browser, verify:
       - "Coach Narrative" section appears at top (above Interpretation)
       - 3 sections present: "Что у тебя получается", "Где теряешь время", "Action этой недели"
       - At least one direction title from interpretation.DIRECTIONS cited verbatim
       - No obvious hallucination (specific tick/round/demo references match player's data)
       - Length ≤ 600 words (rough word count)

    4. Refresh 2 W0 placeholder fixtures with real-API output (replaces stub fixtures with actual sonnet-4-6 outputs):
       ```bash
       python -m interpretation_narrative record-fixture --player 76561198386265483 --type peek \
           --out tests/fixtures/anthropic_recorded/ok_donk_peek.json
       python -m interpretation_narrative record-fixture --player 76561197989430253 --type peek \
           --out tests/fixtures/anthropic_recorded/clean_paraphrase.json
       ```

    5. Run pytest to verify refreshed fixtures still pass schema check:
       ```bash
       python -m pytest tests/fixtures/test_fixtures_load.py tests/test_narrative_validator.py -p no:cov
       ```
       The validator should accept the new ok_donk_peek.json (real LLM output should respect prompt instructions); if validator fails, the LLM violated D-14 / hallucinated → ITERATE the prompt and regenerate.

    6. Run cost-report to confirm spend reasonable:
       ```bash
       python -m interpretation_narrative cost-report
       ```
       Expected ≤ $0.50 for 10-report eval + 2 fixture captures. If ≥$2, investigate (max_tokens cap? multiple retries?).
  </action>
  <verify>
    <automated>ls evals/generated/v2_*.html 2>/dev/null | wc -l</automated>
  </verify>
  <acceptance_criteria>
    - `ls evals/generated/v2_*.html | wc -l` ≥ 8 (at minimum 8/10 reports generated; up to 2 failures acceptable)
    - `grep -l "Coach Narrative" evals/generated/v2_*.html | wc -l` ≥ 8 (≥8 reports have narrative section)
    - `python -c "import json; d=json.loads(open('tests/fixtures/anthropic_recorded/ok_donk_peek.json').read()); assert d['captured_at'] != '2026-05-13T10:00:00Z', 'fixture not refreshed'; print('refreshed:', d['captured_at'])"` prints a real recent timestamp (not the W0 placeholder)
    - `python -m pytest tests/fixtures/test_fixtures_load.py -p no:cov` PASS
    - `python -m interpretation_narrative cost-report` exits 0 and prints non-zero total
    - B-6 SC-3 gate: `evals/generated/timings.json` exists; `python -c "import json, statistics; data = json.load(open('evals/generated/timings.json')); ok = [d['seconds'] for d in data if d['status'] == 'ok']; ok.sort(); p95 = ok[int(len(ok) * 0.95)] if len(ok) >= 2 else ok[-1]; assert p95 <= 30.0"` exits 0 (P95 generation time ≤30s per SC-3)
  </acceptance_criteria>
  <done>
    10 reports generated, 2 fixtures refreshed, cost within budget. Live smoke call (REQ-3) succeeded. Ready for manual rating. SC-3 P95 ≤30s closed via per-report perf_counter timings.json.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 4: Operator rates 10 reports × 5 dimensions (50 ratings) — SC-1 hard gate</name>
  <files>evals/interpretation_v2_ratings.csv, prompts/coaching_v2.md</files>
  <action>
    OPERATOR-EXECUTED. For each of 10 reports:

    1. Open HTML in browser
    2. Read narrative section
    3. Rate on 5 dims via CLI:
       ```bash
       python -m interpretation_narrative eval-rate \
           --report-id v2_donk \
           --player 76561198386265483 \
           --dim factual_accuracy --score 4 \
           --notes "Numbers match tier_rows; one minor rounding inconsistency on T1→T2"

       python -m interpretation_narrative eval-rate ... --dim actionability --score 5 ...
       python -m interpretation_narrative eval-rate ... --dim tone --score 4 ...
       python -m interpretation_narrative eval-rate ... --dim attribution --score 5 ...
       python -m interpretation_narrative eval-rate ... --dim hallucinations --score 5 ...
       ```
       (50 invocations total: 10 reports × 5 dims)

    Rate honestly per evals/README.md rubric. Hallucinations dim is INVERSE — 5 means none, 1 means many.

    4. After rating all 50, run:
       ```bash
       python -m interpretation_narrative score
       ```

    5. **Verdict branches:**
       - **PASS (avg ≥4.0 + per-dim ≥3.5):** SC-1 closed. Type "SC-1 PASS" + paste the score output. Proceed to Task 5.
       - **FAIL on avg:** prompt needs major rework. Iterate `prompts/coaching_v2.md` (tone? length? structure? attribution depth?) → re-generate eval set (Task 3 step 2) → re-rate. Old ratings preserved in CSV (different prompt_hash).
       - **FAIL on per-dim floor:** target the dim that failed. E.g. if `attribution=2.8`, prompt is not citing top_moments enough — add explicit instruction "В каждой секции упомяни хотя бы 1 момент с demo + раунд + тик из top_moments". Re-iterate.

    Cost per iteration: ~$0.30. Budget for 5 iterations (~$1.50) before considering scope-shift.

    6. **Optional/recommended:** rate v1 reports too (without narrative) for the SC-6 side-by-side. Skip if Task 5 will handle it via paired generation.

    Resume signal: type "SC-1 PASS — score output: <paste>" OR "iterating prompt, attempt N: <reason>". If 5 iterations and still FAIL, type "SC-1 FAIL after 5 iterations — escalate" and pause for design discussion.
  </action>
  <verify>
    <automated>python -m interpretation_narrative score --csv evals/interpretation_v2_ratings.csv</automated>
  </verify>
  <acceptance_criteria>
    - `python -m interpretation_narrative score` exits 0 (PASS verdict)
    - SC-1 verdict shows: avg ≥4.0 AND all per-dim means ≥3.5 AND n_reports ≥10
    - evals/interpretation_v2_ratings.csv has ≥50 rows under the latest prompt_hash
    - W-6 + B-1+B-4 + B-C tightened gate (NO placeholder skips count, real-nickname enforcement): `n_reports >= 10 AND row_count >= 50 AND n_distinct_real_players >= 10` AND every rated SteamID maps to a non-placeholder PLAYER_NAMES entry — verify via `python -c "import pandas as pd; from config import PLAYER_NAMES; df = pd.read_csv('evals/interpretation_v2_ratings.csv'); latest = df[df.prompt_hash == df.sort_values('rated_at').iloc[-1].prompt_hash]; assert latest.report_id.nunique() >= 10 and len(latest) >= 50 and latest.player_steamid.nunique() >= 10, f'count gate fail: reports={latest.report_id.nunique()} rows={len(latest)} players={latest.player_steamid.nunique()}'; rated_sids = set(latest.player_steamid.astype(int)); names = {sid: PLAYER_NAMES.get(sid, '') for sid in rated_sids}; assert all(n and not n.startswith('player_') for n in names.values()), f'placeholder nicknames in rated set: {names}'"`. The 10 distinct player_steamid values MUST all map to real D-15 roster nicknames in PLAYER_NAMES (no `player_<last4>` placeholders in the rated set per B-1+B-4 + B-C revision).
  </acceptance_criteria>
  <done>
    SC-1 closed. Prompt converged. Ready to test side-by-side comparison vs v1 baseline.
  </done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 5: Operator runs side-by-side SC-6 (5 paired reports rated)</name>
  <files>evals/v2_side_by_side.csv</files>
  <action>
    OPERATOR-EXECUTED. SC-1 passed. Now compare v2 (with narrative) vs v1 (tier table only) on same players.

    1. Generate 5 paired reports:
       ```bash
       python -m interpretation_narrative generate-side-by-side --pairs 5
       ```
       Outputs: `evals/generated/pair_001_<name>_v1.html`, `pair_001_<name>_v2.html`, ... (10 files total).

    2. For each pair (5 total):
       - Open both v1 + v2 HTML files SIDE-BY-SIDE in browser
       - Read both reports as if you were a paying user
       - Decide: which would you pay for?
       - Rate via CLI:
       ```bash
       python -m interpretation_narrative rate-side-by-side \
           --pair-id pair_001 \
           --player 76561198386265483 \
           --preferred v2 \
           --v1-rating 2 \
           --v2-rating 4 \
           --notes "v2 tells me what to do, v1 just gives a table"
       ```

    3. Run:
       ```bash
       python -m interpretation_narrative score-side-by-side
       ```

    4. **Verdict branches:**
       - **PASS (v2 ≥4.0 mean, v1 ≤3.0 mean, delta ≥1.0):** SC-6 closed. Phase ships. Type "SC-6 PASS — <output>".
       - **FAIL on v2 too low:** prompt lacks "would buy" punch. Iterate (more concrete advice? bolder tone? better attribution?). Re-rate.
       - **FAIL on v1 too high:** v1 baseline tier table is good enough on its own. Either (a) make narrative MORE differentiated (more specific, more directly useful), or (b) accept that the gap product needs more than narrative — surface other v2.1 ideas (trajectory, cohort phrasing).
       - **FAIL on delta:** narrative + table feels redundant or pasted-on. Restructure prompt to explicitly contrast / extend the table data, not duplicate it.

    Cost per side-by-side iteration: ~$0.13 (5 v2 reports). v1 reports are free (no LLM call).

    5. **Optional:** if SC-6 passes but `preferred_dist` shows < 4/5 prefer v2 (e.g. 3 v2, 2 neither), document in SUMMARY as soft signal — "passed Likert gates but forced-choice was 60/40 — narrative not yet definitive win".

    Resume signal: type "SC-6 PASS — score output: <paste>" OR "SC-6 FAIL: <verdict + iteration plan>". If 3 iterations and still FAIL, type "SC-6 FAIL after 3 iterations — escalate".
  </action>
  <verify>
    <automated>python -m interpretation_narrative score-side-by-side --csv evals/v2_side_by_side.csv</automated>
  </verify>
  <acceptance_criteria>
    - `python -m interpretation_narrative score-side-by-side` exits 0 (PASS verdict)
    - SC-6 verdict shows: v2_mean ≥4.0 AND v1_mean ≤3.0 AND delta ≥1.0 AND n_pairs ≥5
    - evals/v2_side_by_side.csv has ≥5 rows
  </acceptance_criteria>
  <done>
    SC-6 closed. v2 narrative measurably outperforms v1 baseline. Validates "I would buy it" thesis. Phase ready to ship.
  </done>
</task>

<task type="auto">
  <name>Task 6: Final cost report + ship verification</name>
  <files>.planning/STATE.md</files>
  <read_first>
    - All previous SUMMARY.md files (00-05)
  </read_first>
  <action>
    1. Run final cost report:
       ```bash
       python -m interpretation_narrative cost-report
       ```
       Capture output for SUMMARY. Expected: total ≤$5 across all eval iterations.

    2. Verify all SC gates closed by re-running scores:
       ```bash
       python -m interpretation_narrative score
       python -m interpretation_narrative score-side-by-side
       python -m interpretation_narrative score-cost
       ```
       All three should print PASS (score-cost may print SKIP if cache empty — populate via fresh generate-eval-set first if needed).

    3. Verify fail-soft path still works without narrative:
       ```bash
       env -u ANTHROPIC_API_KEY python -c "from report_generator import generate_html_report; html = generate_html_report(76561198386265483, 76561198386265483, 'donk').decode(); assert 'Coach Narrative' not in html; assert 'Interpretation' in html; print('fail-soft OK — tier table preserved')"
       ```

    4. Verify full test suite still green:
       ```bash
       python -m pytest -p no:cov
       ```
       Expected: ≥350 tests, all PASS.

    5. Check fall-back rate sample (SC-5):
       ```bash
       python -c "import sqlite3; c=sqlite3.connect('analytics.db'); n_cached=c.execute('SELECT COUNT(*) FROM narrative_cache').fetchone()[0]; print(f'cached_narratives: {n_cached}')"
       ```
       Then count narrative_failures.log entries:
       ```bash
       wc -l narrative_failures.log 2>/dev/null || echo "0 narrative_failures.log"
       ```
       SC-5 = ≤5% fall-back rate on 50-report stress. With ≤15 reports during eval (10 + 5 side-by-side), the 5% gate translates to ≤1 failure. Document actual rate in SUMMARY.

    6. Update STATE.md (via gsd-sdk if available, or manual edit):
       - last_activity: "2026-05-XX — Phase v2-interpretation-narrative SHIPPED. SC-1, SC-2, SC-5, SC-6 PASS. Full suite green."
       - status: "Phase v2 complete. v1.1 milestone in progress."
  </action>
  <verify>
    <automated>python -m pytest -p no:cov && python -m interpretation_narrative score && python -m interpretation_narrative score-side-by-side && python -m interpretation_narrative score-cost</automated>
  </verify>
  <acceptance_criteria>
    - `python -m pytest -p no:cov` exit 0 (full suite green)
    - `python -m interpretation_narrative score` exit 0 (SC-1 PASS)
    - `python -m interpretation_narrative score-side-by-side` exit 0 (SC-6 PASS)
    - `python -m interpretation_narrative score-cost` exit 0 (SC-4 PASS — avg per report ≤$0.10, B-6 gate)
    - `python -m interpretation_narrative cost-report` shows total ≤$5
    - Fall-back rate ≤5% (≤1 failure in narrative_failures.log across the eval iteration's 15+ reports)
    - STATE.md reflects ship state
  </acceptance_criteria>
  <done>
    Phase v2 SHIPPED. All hard gates closed: SC-1 (eval ≥4.0 + ≥3.5 floor), SC-2 (validator catches all hallucinations — already proven in W1), SC-5 (fall-back ≤5%), SC-6 (side-by-side delta ≥1.0). Cost within budget. Tests green. STATE.md updated. Ready for /gsd-verify-work or /gsd-new-milestone.
  </done>
</task>

</tasks>

<verification>
- All 6 tasks complete (Tasks 2, 4, 5 are checkpoints requiring user action)
- Final pytest suite green
- score + score-side-by-side both PASS
- Cost report ≤$5 total
- Fall-back rate ≤5%
- CLAUDE.md documents API key + workflow
</verification>

<success_criteria>
- SC-1 PASS — eval avg ≥4.0, per-dim ≥3.5 (operator gate)
- SC-2 PASS — validator catches all 7 fixture hallucinations (W1, already verified)
- SC-3 — P95 generation ≤30s (informally measured during eval; cached call ≤100ms via cache lookup)
- SC-4 PASS — cost ≤$0.10/report (verified by cost-report)
- SC-5 PASS — fall-back ≤5% (verified by narrative_failures.log line count)
- SC-6 PASS — side-by-side v2 ≥4.0, v1 ≤3.0, delta ≥1.0 (operator gate)
- REQ-3 PASS — 1 live smoke call against real API (Task 3)
- REQ-9 PASS — cost-report CLI ships
- REQ-11 PASS — RU output (verified during eval rating tone dim)
- All deferred ideas remain deferred (DDM still dead, no Streamlit panel, no trajectory)
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-06-SUMMARY.md` documenting:
- Final score outputs (SC-1 + SC-6)
- Cost summary (total spend across phase)
- Fall-back rate (failures / total reports)
- Number of prompt iterations to reach SC-1
- Any soft signals (preferred_dist on side-by-side, dims that just barely passed floor)
- Backfill outcome (round_number coverage achieved)
- Timestamp + recommendations for v2.1 (trajectory, cohort phrasing, EN bilingual based on what eval rating revealed)
- Final test count
</output>
