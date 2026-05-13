---
phase: v2-interpretation-narrative
plan: 05
type: execute
wave: 3
depends_on: [02, 03, 04]
files_modified:
  - interpretation_narrative.py
  - evals/v2_eval_player_roster.json
  - evals/README.md
  - tests/test_eval_harness.py
autonomous: true
requirements: [REQ-8, REQ-9]
must_haves:
  truths:
    - "evals/v2_eval_player_roster.json exists with 10 entries (3 top + 4 mid + 3 bottom per D-15)"
    - "interpretation_narrative gains CLI subcommands: cost-report, eval-rate, generate-eval-set, generate-side-by-side, score, score-side-by-side, record-fixture"
    - "save_rating helper writes evals/interpretation_v2_ratings.csv with append+dedup by (report_id, prompt_hash, dim) per D-19"
    - "save_side_by_side helper writes evals/v2_side_by_side.csv with columns per D-20 + preferred_version extension"
    - "evals/README.md documents 5 dims (D-17), SC-1 ≥4.0 + ≥3.5 floor, D-16 solo-rater, D-18 full re-rate, D-20 side-by-side protocol"
    - "cost-report CLI prints total tokens + USD using PRICING dict from W2"
    - "eval-rate CLI accepts --report-id --player --dim --score --notes; appends row; dedup by (report_id, prompt_hash, dim)"
    - "generate-eval-set CLI iterates roster + emits 10 HTML reports under evals/generated/v2_<name>.html (calls report_generator.generate_html_report with no_narrative=False)"
    - "generate-side-by-side CLI emits 5 v1 (no_narrative=True) + 5 v2 paired HTML files for SC-6"
    - "score CLI aggregates ratings.csv → prints SC-1 verdict (PASS/FAIL + per-dim breakdown)"
    - "score-side-by-side CLI prints SC-6 verdict (PASS/FAIL + v1/v2 means + delta + preferred_version distribution)"
    - "score-cost CLI (B-6) asserts total_cost / n_reports <= $0.10 — SC-4 hard gate; PASS/FAIL exit code"
    - "interpretation_narrative gains 8 CLI subcommands now: cost-report, score-cost, eval-rate, generate-eval-set, generate-side-by-side, score, score-side-by-side, rate-side-by-side, record-fixture"
  artifacts:
    - path: "evals/v2_eval_player_roster.json"
      provides: "Locked 10-player D-15 roster"
      contains: "donk"
      min_lines: 15
    - path: "evals/README.md"
      provides: "Rubric definitions + solo-rater limitation + workflow docs"
      min_lines: 60
    - path: "interpretation_narrative.py"
      provides: "CLI subcommands + save_rating + save_side_by_side helpers + score aggregations"
      contains: "cost-report"
    - path: "tests/test_eval_harness.py"
      provides: "CSV append/dedup + CLI smoke tests"
      min_lines: 100
  key_links:
    - from: "interpretation_narrative.cli (cost-report)"
      to: "narrative_cache table tokens_in/tokens_out + PRICING dict"
      via: "SELECT SUM aggregations + per-row _row_cost"
      pattern: "PRICING"
    - from: "interpretation_narrative.cli (generate-eval-set)"
      to: "report_generator.generate_html_report + roster JSON"
      via: "load roster → loop → write HTML files"
      pattern: "generate_html_report"
    - from: "interpretation_narrative.cli (score)"
      to: "evals/interpretation_v2_ratings.csv"
      via: "pandas read + groupby dim + mean compare to thresholds 4.0 / 3.5"
      pattern: "score"
---

<objective>
Ship the eval harness that proves SC-1, SC-4, SC-5, SC-6 + REQ-8 + REQ-9. CLI subcommands: cost-report, eval-rate, generate-eval-set, generate-side-by-side, score, score-side-by-side, record-fixture.

Purpose: Without this harness, SC-1 (≥4.0 avg + ≥3.5 floor) and SC-6 (v2 ≥4.0, v1 ≤3.0, delta ≥1.0) cannot be measured — those are the hard ship gates. CLI is self-service so user can run rate → score → see verdict in one terminal session. cost-report (REQ-9) gives ongoing cost visibility post-ship. record-fixture replaces W0's placeholder fixtures with real captured outputs once prompt converges.

Output:
- `evals/v2_eval_player_roster.json` — D-15 locked 10-player roster
- `evals/README.md` — rubric + solo-rater + workflow docs
- `interpretation_narrative.py` — CLI subcommands appended (cost-report, eval-rate, generate-eval-set, generate-side-by-side, score, score-side-by-side, record-fixture)
- `tests/test_eval_harness.py` — CSV roundtrip + CLI smoke tests
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-02-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-03-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-04-SUMMARY.md
@CLAUDE.md
@interpretation_narrative.py
@csv_utils.py
@report_generator.py

<interfaces>
CSV append+dedup pattern from csv_utils.py:38-53 (replicate for save_rating + save_side_by_side):
```python
def save_results(results_df, filename, match_id) -> None:
    existing = load_existing_results(filename)
    if not existing.empty and "match_id" in existing.columns:
        existing = existing[existing["match_id"].astype(str) != str(match_id)]
        combined = pd.concat([existing, results_df], ignore_index=True)
    else:
        combined = results_df
    combined.to_csv(filename, index=False)
```

PRICING dict from W2 (interpretation_narrative.PRICING):
```python
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "cache_w_5m": 3.75, "cache_r": 0.30, "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0, "cache_w_5m": 6.25, "cache_r": 0.50, "output": 25.0},
    "claude-haiku-4-5":  {"input": 1.0, "cache_w_5m": 1.25, "cache_r": 0.10, "output": 5.0},
}
```

D-19 rating CSV schema:
- columns: `(report_id, player_steamid, prompt_hash, dim, score, notes, rated_at)`
- dedup key: `(report_id, prompt_hash, dim)` — re-rate same dim overwrites; new prompt_hash creates new row

D-20 + RESEARCH side-by-side schema (with preferred_version extension):
- columns: `(pair_id, player_steamid, preferred_version, v1_rating, v2_rating, notes, rated_at)`
- dedup key: `(pair_id, player_steamid)`

D-15 roster (CONTEXT):
- 3 top: donk, karrigan, frozen (by trial count)
- 4 mid: twistzz, jcobbb, sh1ro, 1 random Spirit ≥100 trials
- 3 bottom: 3 lowest-trial players passing min-trials gate

D-17 rating dimensions: factual_accuracy, actionability, tone, attribution, hallucinations (1-5; hallucinations is INVERSE — 5 = none).

SC-1 gate: avg ≥4.0 across all dims, per-dim floor ≥3.5.
SC-6 gate: v2 mean ≥4.0, v1 mean ≤3.0, delta ≥1.0.

cost-report SQL aggregation:
```sql
SELECT model, COUNT(*), SUM(tokens_in), SUM(tokens_out),
       SUM(cache_creation_input_tokens), SUM(cache_read_input_tokens)
FROM narrative_cache GROUP BY model;
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Roster JSON + evals/README.md (rubric + solo-rater + workflow docs)</name>
  <files>evals/v2_eval_player_roster.json, evals/README.md</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md (D-15, D-16, D-17, D-18, D-20)
    - config.py PLAYER_NAMES (W3 expanded to 10 entries)
  </read_first>
  <action>
    1. Query analytics.db for trial counts per player:
    ```bash
    python -c "import sqlite3; c = sqlite3.connect('analytics.db'); rows = c.execute('SELECT player_steamid, COUNT(*) FROM engagements GROUP BY player_steamid HAVING COUNT(*) >= 30 ORDER BY COUNT(*) DESC').fetchall(); print(rows[:30])"
    ```
    Identify top 3, mid 4, bottom 3 by trial count. Cross-reference with W3 PLAYER_NAMES for display names.

    2. Write `evals/v2_eval_player_roster.json` per the schema in Interfaces. Tier_quotas: top=3, mid=4, bottom=3, total=10. Include `frozen_at` ISO timestamp.

    **HARD BLOCK per D-15 (B-1 + B-4 revision, no placeholders allowed):** if fewer than 10 REAL players pass the min-trials gate from the current `analytics.db`, raise a `RosterResolutionError` (define inline in this script) listing exactly which roster slots could not be filled and the per-tier shortfall. STOP. Do NOT write a roster JSON with `tier="placeholder"` entries. Surface the error so the operator knows to either (a) lower the min-trials gate explicitly with rationale, or (b) ingest more demos to grow the player pool. Resume only after a 10-real-player roster is achievable.

    3. Write `evals/README.md` covering:
    - 5 rating dimensions (D-17) with anchor descriptions per dim
    - SC-1 hard gate (≥4.0 avg + ≥3.5 floor)
    - SC-6 side-by-side gate
    - D-16 solo-rater limitation
    - D-18 re-rate workflow on prompt change
    - CSV schemas (D-19 + D-20)
    - 5-step workflow (generate-eval-set → eval-rate per dim → score → if FAIL iterate prompt → generate-side-by-side → score-side-by-side)
    - cost-report monitoring (REQ-9)

    Document the inverse semantic for `hallucinations` dim explicitly: 5 = no hallucinations, 1 = many.
  </action>
  <verify>
    <automated>python -c "import json; r = json.loads(open('evals/v2_eval_player_roster.json').read()); assert len(r['players']) == 10; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f evals/v2_eval_player_roster.json && test -f evals/README.md` succeed
    - `python -c "import json; r = json.loads(open('evals/v2_eval_player_roster.json').read()); assert len(r['players']) == 10; assert all('steamid' in p and 'tier' in p for p in r['players']); print('OK')"` prints "OK"
    - `grep -c "factual_accuracy\|actionability\|tone\|attribution\|hallucinations" evals/README.md` ≥ 5 (all 5 dims documented)
    - `grep -c "≥4.0\|>= 4.0" evals/README.md` ≥ 1 (SC-1 gate noted)
    - `grep -c "≥3.5\|>= 3.5" evals/README.md` ≥ 1 (per-dim floor noted)
    - `grep -c "solo-rater\|single rater\|D-16" evals/README.md` ≥ 1 (limitation documented)
    - `wc -l evals/README.md` ≥ 60
    - `wc -l evals/v2_eval_player_roster.json` ≥ 15
  </acceptance_criteria>
  <done>
    Roster locked. Rubric documented. Solo-rater limitation flagged. Re-rate workflow specified. The user knows exactly what each dim means before sitting down to rate 50 entries.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: CLI subcommands + save_rating + save_side_by_side + score helpers</name>
  <files>interpretation_narrative.py, tests/test_eval_harness.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Eval Harness Pattern lines 446-520
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md interpretation_narrative.py CLI section (lines 105-117)
    - csv_utils.py:38-90 (save_results pattern + load_existing_results)
    - interpretation_narrative.py current state (W2 + W3 — append CLI to bottom of file)
    - bench/multi_player_batch_loop.py top 50 lines (argparse subcommand pattern reference)
  </read_first>
  <behavior>
    RED tests in `tests/test_eval_harness.py`:

    **TestSaveRating:**
    - `test_save_rating_appends_new_row(tmp_path)` — write 2 ratings with same report_id but different dims; assert CSV has 2 rows
    - `test_save_rating_overwrites_same_dedup_key(tmp_path)` — write 2 ratings with identical (report_id, prompt_hash, dim); second wins; CSV has 1 row with second score
    - `test_save_rating_new_prompt_hash_creates_new_row(tmp_path)` — same report_id + dim, different prompt_hash → 2 rows preserved (D-18 iteration history)
    - `test_save_rating_csv_schema_fields(tmp_path)` — assert columns exactly == ["report_id", "player_steamid", "prompt_hash", "dim", "score", "notes", "rated_at"]
    - `test_save_rating_handles_unicode_notes(tmp_path)` — notes with Russian text round-trips intact

    **TestSaveSideBySide:**
    - `test_save_side_by_side_appends(tmp_path)` — write 2 distinct pair_ids; assert 2 rows
    - `test_save_side_by_side_overwrites_same_pair(tmp_path)` — same (pair_id, player_steamid); second wins
    - `test_save_side_by_side_schema(tmp_path)` — columns == ["pair_id", "player_steamid", "preferred_version", "v1_rating", "v2_rating", "notes", "rated_at"]

    **TestScoreSC1:**
    - `test_score_pass_when_avg_geq_4_and_per_dim_geq_3_5(tmp_path)` — write fixture CSV with 10 reports × 5 dims, all scores 4.5; call `score(csv_path)`; assert returns dict `{"pass": True, "avg": 4.5, "per_dim": {dim: 4.5 for ...}}` and exit code 0
    - `test_score_fail_on_avg_below_4(tmp_path)` — all scores 3.5; assert pass=False
    - `test_score_fail_on_per_dim_floor(tmp_path)` — 4 dims at 5.0, 1 dim at 3.0 (avg 4.6 — passes avg gate, fails floor gate); assert pass=False with reason mentioning the failing dim
    - `test_score_handles_partial_eval_set(tmp_path)` — only 3 reports rated (instead of 10); assert score still computes + flags incomplete eval

    **TestScoreCost (B-6 — SC-4 gate):**
    - `test_score_cost_pass_when_under_threshold(tmp_path)` — populate narrative_cache with 5 rows total spending $0.30 (avg $0.06/report); call score_cost CLI logic; assert PASS + exit 0
    - `test_score_cost_fail_when_over_threshold(tmp_path)` — 5 rows spending $1.00 (avg $0.20); assert FAIL + exit 2
    - `test_score_cost_skip_when_empty_cache(tmp_path)` — 0 rows; assert SKIP + exit 0 (no division by zero)
    - `test_score_cost_respects_custom_max_per_report(tmp_path)` — pass --max-per-report 0.50; with avg $0.20 → PASS

    **TestScoreSideBySide:**
    - `test_side_by_side_pass(tmp_path)` — 5 pairs, v1_rating=2 mean, v2_rating=4.5 mean → pass=True (delta 2.5 ≥ 1.0; v1 ≤ 3.0; v2 ≥ 4.0)
    - `test_side_by_side_fail_on_delta(tmp_path)` — v1=3.5, v2=4.0 (delta 0.5) → fail
    - `test_side_by_side_fail_on_v1_too_high(tmp_path)` — v1=3.5 mean → fail (v1 must be ≤ 3.0)

    **TestCostReport:**
    - `test_cost_report_sums_correctly(tmp_path)` — populate narrative_cache fixture with 3 rows known token counts + model; call cost-report logic; assert total USD matches manual computation per PRICING
    - `test_cost_report_handles_empty_cache(tmp_path)` — fresh DB; cost-report exits 0 with "0 reports, $0.00"
    - `test_cost_report_groups_by_model(tmp_path)` — mix of sonnet + opus rows; assert per-model breakdown printed

    **TestRecordFixture (W-7 — real-API guard):**
    - `test_record_fixture_argparse_smoke(tmp_path)` — argparse-only smoke (no real API, no skip): invoke `_cli_main(["record-fixture", "--help"])` (or via subprocess); assert help text mentions `--player`, `--type`, `--out`. NO skip marker — this is a pure argparse contract test.
    - `test_record_fixture_integration_real_api(tmp_path)` — REAL-API integration test: place at top of body `pytest.skip("requires real ANTHROPIC_API_KEY; run manually with python -m pytest tests/test_eval_harness.py::test_record_fixture_integration_real_api")`. The skip ensures CI never accidentally hits the real API. When operator wants to run, they remove the skip locally OR invoke via the manual W4 fixture-refresh workflow (Plan 06 Task 3).

    **TestCLISmoke** (use subprocess via `subprocess.run([sys.executable, '-m', 'interpretation_narrative', '--help'], ...)`):
    - `test_help_lists_all_subcommands` — stdout contains "cost-report", "eval-rate", "generate-eval-set", "generate-side-by-side", "score", "score-side-by-side", "record-fixture"
    - `test_cost_report_smoke(tmp_path, monkeypatch)` — point --db at tmp DB with init_db; assert exit 0
    - `test_eval_rate_smoke(tmp_path)` — invoke with --report-id, --player, --dim, --score, --notes args + --csv flag pointing to tmp file; assert CSV row written

    GREEN — append CLI section to `interpretation_narrative.py`:
    ```python
    # ── CSV append+dedup helpers (D-19, D-20) ──────────────────────────────────

    def save_rating(csv_path: str, row: dict) -> None:
        """Append rating to CSV; dedup by (report_id, prompt_hash, dim) per D-19."""
        import pandas as pd
        from pathlib import Path
        cols = ["report_id", "player_steamid", "prompt_hash", "dim", "score", "notes", "rated_at"]
        if Path(csv_path).exists() and Path(csv_path).stat().st_size > 0:
            existing = pd.read_csv(csv_path, dtype={"player_steamid": "Int64"})
        else:
            existing = pd.DataFrame(columns=cols)
        if not existing.empty:
            mask = (
                (existing["report_id"].astype(str) == str(row["report_id"]))
                & (existing["prompt_hash"].astype(str) == str(row["prompt_hash"]))
                & (existing["dim"].astype(str) == str(row["dim"]))
            )
            existing = existing[~mask]
        combined = pd.concat([existing, pd.DataFrame([row], columns=cols)], ignore_index=True)
        combined.to_csv(csv_path, index=False, encoding="utf-8")

    def save_side_by_side(csv_path: str, row: dict) -> None:
        """Append side-by-side rating; dedup by (pair_id, player_steamid) per D-20."""
        import pandas as pd
        from pathlib import Path
        cols = ["pair_id", "player_steamid", "preferred_version", "v1_rating", "v2_rating", "notes", "rated_at"]
        if Path(csv_path).exists() and Path(csv_path).stat().st_size > 0:
            existing = pd.read_csv(csv_path, dtype={"player_steamid": "Int64"})
        else:
            existing = pd.DataFrame(columns=cols)
        if not existing.empty:
            mask = (
                (existing["pair_id"].astype(str) == str(row["pair_id"]))
                & (existing["player_steamid"].astype(str) == str(row["player_steamid"]))
            )
            existing = existing[~mask]
        combined = pd.concat([existing, pd.DataFrame([row], columns=cols)], ignore_index=True)
        combined.to_csv(csv_path, index=False, encoding="utf-8")

    # ── Score aggregations (SC-1, SC-6) ────────────────────────────────────────

    def score_sc1(csv_path: str = "evals/interpretation_v2_ratings.csv") -> dict:
        """Aggregate ratings → SC-1 verdict. Returns {pass, avg, per_dim, n_reports, prompt_hash, fail_reasons}."""
        import pandas as pd
        from pathlib import Path
        if not Path(csv_path).exists():
            return {"pass": False, "avg": None, "per_dim": {}, "n_reports": 0, "fail_reasons": ["no eval CSV"]}
        df = pd.read_csv(csv_path)
        if df.empty:
            return {"pass": False, "avg": None, "per_dim": {}, "n_reports": 0, "fail_reasons": ["empty CSV"]}
        # Use latest prompt_hash only
        latest_ph = df.sort_values("rated_at").iloc[-1]["prompt_hash"]
        latest = df[df["prompt_hash"] == latest_ph]
        per_dim = latest.groupby("dim")["score"].mean().to_dict()
        avg = float(latest["score"].mean())
        n_reports = latest["report_id"].nunique()
        fail_reasons = []
        if avg < 4.0:
            fail_reasons.append(f"avg {avg:.2f} < 4.0")
        for dim, m in per_dim.items():
            if m < 3.5:
                fail_reasons.append(f"dim {dim}={m:.2f} < 3.5 floor")
        return {
            "pass": len(fail_reasons) == 0, "avg": avg, "per_dim": per_dim,
            "n_reports": int(n_reports), "prompt_hash": latest_ph, "fail_reasons": fail_reasons,
        }

    def score_sc6(csv_path: str = "evals/v2_side_by_side.csv") -> dict:
        """Aggregate side-by-side → SC-6 verdict."""
        import pandas as pd
        from pathlib import Path
        if not Path(csv_path).exists():
            return {"pass": False, "v1_mean": None, "v2_mean": None, "delta": None, "n_pairs": 0, "fail_reasons": ["no CSV"]}
        df = pd.read_csv(csv_path)
        if df.empty:
            return {"pass": False, "v1_mean": None, "v2_mean": None, "delta": None, "n_pairs": 0, "fail_reasons": ["empty CSV"]}
        v1_mean = float(df["v1_rating"].mean())
        v2_mean = float(df["v2_rating"].mean())
        delta = v2_mean - v1_mean
        preferred_dist = df["preferred_version"].value_counts().to_dict()
        fail_reasons = []
        if v2_mean < 4.0: fail_reasons.append(f"v2_mean {v2_mean:.2f} < 4.0")
        if v1_mean > 3.0: fail_reasons.append(f"v1_mean {v1_mean:.2f} > 3.0")
        if delta < 1.0: fail_reasons.append(f"delta {delta:.2f} < 1.0")
        return {
            "pass": len(fail_reasons) == 0, "v1_mean": v1_mean, "v2_mean": v2_mean,
            "delta": delta, "n_pairs": int(len(df)), "preferred_dist": preferred_dist,
            "fail_reasons": fail_reasons,
        }

    # ── Cost report (REQ-9) ────────────────────────────────────────────────────

    def _row_cost(model: str, in_tok: int, out_tok: int, cw: int, cr: int) -> float:
        p = PRICING.get(model, PRICING["claude-sonnet-4-6"])
        return (
            in_tok * p["input"] / 1_000_000
            + cw * p["cache_w_5m"] / 1_000_000
            + cr * p["cache_r"] / 1_000_000
            + out_tok * p["output"] / 1_000_000
        )

    def cost_report(db_path: str = DB_PATH) -> dict:
        """Compute total cost from narrative_cache table. Returns dict for CLI rendering."""
        with closing(sqlite3.connect(db_path)) as conn:
            try:
                rows = conn.execute("""
                    SELECT model, COUNT(*), SUM(tokens_in), SUM(tokens_out),
                           SUM(cache_creation_input_tokens), SUM(cache_read_input_tokens)
                    FROM narrative_cache GROUP BY model
                """).fetchall()
                last7 = conn.execute("""
                    SELECT COUNT(*), SUM(tokens_in), SUM(tokens_out),
                           SUM(cache_creation_input_tokens), SUM(cache_read_input_tokens),
                           model
                    FROM narrative_cache
                    WHERE generated_at > datetime('now', '-7 days')
                    GROUP BY model
                """).fetchall()
            except sqlite3.OperationalError:
                return {"error": "narrative_cache table not found — run init_db first", "total_usd": 0.0, "by_model": {}}
        by_model = {}
        total_usd = 0.0
        for model, n, in_t, out_t, cw, cr in rows:
            cost = _row_cost(model, in_t or 0, out_t or 0, cw or 0, cr or 0)
            by_model[model] = {"reports": int(n), "in": int(in_t or 0), "out": int(out_t or 0),
                               "cw": int(cw or 0), "cr": int(cr or 0), "usd": round(cost, 4)}
            total_usd += cost
        last7_data = []
        for n, in_t, out_t, cw, cr, model in last7:
            cost7 = _row_cost(model, in_t or 0, out_t or 0, cw or 0, cr or 0)
            last7_data.append({"model": model, "reports": int(n), "usd": round(cost7, 4)})
        return {"total_usd": round(total_usd, 4), "by_model": by_model, "last_7d": last7_data}

    # ── CLI subcommands ────────────────────────────────────────────────────────

    def _cli_main(argv=None) -> int:
        import argparse
        from datetime import datetime, timezone
        p = argparse.ArgumentParser(prog="interpretation_narrative")
        sub = p.add_subparsers(dest="cmd", required=True)

        # cost-report
        cr = sub.add_parser("cost-report"); cr.add_argument("--db", default=DB_PATH)

        # eval-rate
        er = sub.add_parser("eval-rate")
        er.add_argument("--csv", default="evals/interpretation_v2_ratings.csv")
        er.add_argument("--report-id", required=True)
        er.add_argument("--player", type=int, required=True)
        er.add_argument("--dim", required=True, choices=["factual_accuracy", "actionability", "tone", "attribution", "hallucinations"])
        er.add_argument("--score", type=int, required=True, choices=[1, 2, 3, 4, 5])
        er.add_argument("--notes", default="")
        er.add_argument("--prompt-hash", default=None)

        # generate-eval-set
        ge = sub.add_parser("generate-eval-set")
        ge.add_argument("--roster", default="evals/v2_eval_player_roster.json")
        ge.add_argument("--out-dir", default="evals/generated")
        ge.add_argument("--db", default=DB_PATH)
        ge.add_argument("--benchmark", type=int, default=76561198386265483)  # donk default
        ge.add_argument("--emit-timings", default=None,
            help="Path to JSON file. When set, write per-report wall-time timings + P95 (B-A: SC-3 enforcement input for plan 06 Task 3)")

        # generate-side-by-side
        gs = sub.add_parser("generate-side-by-side")
        gs.add_argument("--roster", default="evals/v2_eval_player_roster.json")
        gs.add_argument("--out-dir", default="evals/generated")
        gs.add_argument("--db", default=DB_PATH)
        gs.add_argument("--benchmark", type=int, default=76561198386265483)
        gs.add_argument("--pairs", type=int, default=5)

        # score
        sc = sub.add_parser("score"); sc.add_argument("--csv", default="evals/interpretation_v2_ratings.csv")

        # score-side-by-side
        ss = sub.add_parser("score-side-by-side"); ss.add_argument("--csv", default="evals/v2_side_by_side.csv")

        # score-cost (B-6 — SC-4 gate)
        scost = sub.add_parser("score-cost")
        scost.add_argument("--db", default=DB_PATH)
        scost.add_argument("--max-per-report", type=float, default=0.10)

        # rate-side-by-side (companion to generate-side-by-side)
        rs = sub.add_parser("rate-side-by-side")
        rs.add_argument("--csv", default="evals/v2_side_by_side.csv")
        rs.add_argument("--pair-id", required=True)
        rs.add_argument("--player", type=int, required=True)
        rs.add_argument("--preferred", choices=["v1", "v2", "neither"], required=True)
        rs.add_argument("--v1-rating", type=int, required=True, choices=[1, 2, 3, 4, 5])
        rs.add_argument("--v2-rating", type=int, required=True, choices=[1, 2, 3, 4, 5])
        rs.add_argument("--notes", default="")

        # record-fixture (one-shot real-API capture for W0 fixture refresh)
        rf = sub.add_parser("record-fixture")
        rf.add_argument("--player", type=int, required=True)
        rf.add_argument("--type", choices=["peek", "hold"], required=True)
        rf.add_argument("--out", required=True)
        rf.add_argument("--db", default=DB_PATH)

        args = p.parse_args(argv)
        now = datetime.now(timezone.utc).isoformat()

        if args.cmd == "cost-report":
            data = cost_report(args.db)
            if "error" in data:
                print(f"ERROR: {data['error']}")
                return 1
            print(f"Reports generated: {sum(m['reports'] for m in data['by_model'].values())}")
            for model, m in data["by_model"].items():
                print(f"  {model}: {m['reports']} reports, ${m['usd']:.4f} (in={m['in']:,}, out={m['out']:,}, cw={m['cw']:,}, cr={m['cr']:,})")
            print(f"Total cost (USD): ${data['total_usd']:.4f}")
            print(f"Last 7 days:")
            for entry in data["last_7d"]:
                print(f"  {entry['model']}: {entry['reports']} reports, ${entry['usd']:.4f}")
            return 0

        if args.cmd == "eval-rate":
            ph = args.prompt_hash or _prompt_hash()
            row = {
                "report_id": args.report_id, "player_steamid": args.player, "prompt_hash": ph,
                "dim": args.dim, "score": args.score, "notes": args.notes, "rated_at": now,
            }
            save_rating(args.csv, row)
            print(f"Rated: {args.report_id} dim={args.dim} score={args.score}")
            return 0

        if args.cmd == "generate-eval-set":
            from report_generator import generate_html_report
            from pathlib import Path as _P
            import time as _time, math as _math
            roster = json.loads(_P(args.roster).read_text(encoding="utf-8"))
            _P(args.out_dir).mkdir(parents=True, exist_ok=True)
            timings: list[dict] = []  # B-A: per-report timing for SC-3 P95 ≤30s gate
            for p_entry in roster["players"]:
                sid = int(p_entry["steamid"])
                name = p_entry.get("name", f"player_{str(sid)[-4:]}")
                out_path = _P(args.out_dir) / f"v2_{name}.html"
                t0 = _time.perf_counter()
                ok = False
                try:
                    html = generate_html_report(sid, args.benchmark, "donk", db_path=args.db)
                    out_path.write_bytes(html)
                    ok = True
                    print(f"Generated: {out_path}")
                except Exception as e:
                    print(f"FAILED for {name} ({sid}): {e!r}")
                elapsed_s = _time.perf_counter() - t0
                timings.append({"player_steamid": sid, "name": name, "ok": ok, "elapsed_s": elapsed_s})
            if args.emit_timings:
                durations = sorted(t["elapsed_s"] for t in timings if t["ok"])
                if durations:
                    p95_idx = max(0, _math.ceil(0.95 * len(durations)) - 1)
                    p95 = durations[p95_idx]
                else:
                    p95 = None
                payload = {"timings": timings, "p95_s": p95, "n_ok": sum(1 for t in timings if t["ok"]), "n_total": len(timings)}
                _P(args.emit_timings).parent.mkdir(parents=True, exist_ok=True)
                _P(args.emit_timings).write_text(json.dumps(payload, indent=2), encoding="utf-8")
                print(f"Timings → {args.emit_timings} (p95={p95!r}s, n_ok={payload['n_ok']}/{payload['n_total']})")
            return 0

        if args.cmd == "generate-side-by-side":
            from report_generator import generate_html_report
            from pathlib import Path as _P
            roster = json.loads(_P(args.roster).read_text(encoding="utf-8"))
            _P(args.out_dir).mkdir(parents=True, exist_ok=True)
            picked = roster["players"][:args.pairs]
            for i, p_entry in enumerate(picked):
                sid = int(p_entry["steamid"])
                name = p_entry.get("name", f"player_{str(sid)[-4:]}")
                pair_id = f"pair_{i+1:03d}"
                v1_html = generate_html_report(sid, args.benchmark, "donk", db_path=args.db, no_narrative=True)
                v2_html = generate_html_report(sid, args.benchmark, "donk", db_path=args.db, no_narrative=False)
                (_P(args.out_dir) / f"{pair_id}_{name}_v1.html").write_bytes(v1_html)
                (_P(args.out_dir) / f"{pair_id}_{name}_v2.html").write_bytes(v2_html)
                print(f"Generated pair: {pair_id} for {name}")
            return 0

        if args.cmd == "score":
            data = score_sc1(args.csv)
            verdict = "PASS" if data["pass"] else "FAIL"
            print(f"SC-1 verdict: {verdict}")
            if data["avg"] is not None:
                print(f"  avg: {data['avg']:.2f} (gate ≥4.0)")
                print(f"  n_reports: {data['n_reports']}")
                print(f"  prompt_hash: {data.get('prompt_hash', '?')}")
                for dim, m in data["per_dim"].items():
                    floor_ok = "OK" if m >= 3.5 else "FAIL"
                    print(f"  {dim}: {m:.2f} [{floor_ok}]")
            for r in data["fail_reasons"]:
                print(f"  fail: {r}")
            return 0 if data["pass"] else 2

        if args.cmd == "score-side-by-side":
            data = score_sc6(args.csv)
            verdict = "PASS" if data["pass"] else "FAIL"
            print(f"SC-6 verdict: {verdict}")
            if data["v1_mean"] is not None:
                print(f"  v1_mean: {data['v1_mean']:.2f} (gate ≤3.0)")
                print(f"  v2_mean: {data['v2_mean']:.2f} (gate ≥4.0)")
                print(f"  delta:   {data['delta']:.2f} (gate ≥1.0)")
                print(f"  n_pairs: {data['n_pairs']}")
                print(f"  preferred: {data.get('preferred_dist', {})}")
            for r in data["fail_reasons"]:
                print(f"  fail: {r}")
            return 0 if data["pass"] else 2

        if args.cmd == "score-cost":
            # B-6: SC-4 hard gate — average cost per report must not exceed --max-per-report (default $0.10)
            data = cost_report(args.db)
            n_reports = sum(m["reports"] for m in data.get("by_model", {}).values())
            total_usd = data.get("total_usd", 0.0)
            if n_reports == 0:
                print("SC-4 verdict: SKIP — no reports in narrative_cache yet")
                return 0
            avg = total_usd / n_reports
            verdict = "PASS" if avg <= args.max_per_report else "FAIL"
            print(f"SC-4 verdict: {verdict}")
            print(f"  n_reports: {n_reports}")
            print(f"  total_usd: ${total_usd:.4f}")
            print(f"  avg_per_report: ${avg:.4f} (gate ≤${args.max_per_report:.2f})")
            return 0 if verdict == "PASS" else 2

        if args.cmd == "rate-side-by-side":
            row = {
                "pair_id": args.pair_id, "player_steamid": args.player,
                "preferred_version": args.preferred,
                "v1_rating": args.v1_rating, "v2_rating": args.v2_rating,
                "notes": args.notes, "rated_at": now,
            }
            save_side_by_side(args.csv, row)
            print(f"Rated pair: {args.pair_id} preferred={args.preferred} v1={args.v1_rating} v2={args.v2_rating}")
            return 0

        if args.cmd == "record-fixture":
            # One-shot real-API capture for W0 fixture refresh. Requires ANTHROPIC_API_KEY.
            from report_generator import generate_html_report  # noqa
            # Build top_moments + rows using same pipeline as report_generator
            from interpretation import compute_interpretation
            rows = compute_interpretation(
                db_path=args.db, player_steamid=args.player,
                benchmark_steamid=args.player, engagement_type=args.type,
            )
            top_moments = {}
            metrics_attribute = ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"]
            for metric in metrics_attribute:
                bench_row = next((r for r in rows if r.get("metric") == metric), None)
                if bench_row is None or bench_row.get("benchmark_p50") is None:
                    continue
                moments = fetch_top_moments(args.db, args.player, metric, args.type, float(bench_row["benchmark_p50"]))
                if moments:
                    top_moments[f"{metric}::{args.type}"] = moments
            player_context = {
                "player_steamid": args.player,
                "player_name": PLAYER_NAMES.get(args.player, f"player_{str(args.player)[-4:]}"),
                "engagement_type": args.type,
                "n_total_engagements": len(rows),
            }
            system, user = _render_prompt(rows, top_moments, player_context)
            text, usage = call_llm(system, user)
            fixture = {
                "text": text, "usage": usage, "model": usage.get("model", "claude-sonnet-4-6"),
                "stop_reason": "end_turn",  # if we got here, no refusal
                "captured_at": now,
            }
            from pathlib import Path as _P
            _P(args.out).parent.mkdir(parents=True, exist_ok=True)
            _P(args.out).write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
            print(f"Fixture captured: {args.out}")
            return 0

        return 1

    if __name__ == "__main__":
        raise SystemExit(_cli_main())
    ```

    Tests should monkeypatch `call_llm` (for record-fixture path) so the autouse no-real-anthropic guard isn't broken.

    Note: CLI tests must respect the autouse `_no_real_anthropic` fixture from W0. Tests for `generate-eval-set` and `record-fixture` must monkeypatch `interpretation_narrative._get_client` or skip with a marker if real API needed. Recommend the `record-fixture` test merely tests the argparse path (use --help) and skips the actual call.
  </behavior>
  <action>
    1. Write RED tests in `tests/test_eval_harness.py` covering all helper functions + CLI smoke. Commit (`test(v2-05): RED eval harness CSV helpers + score + cost-report + CLI`).
    2. Append the entire CLI block above to `interpretation_narrative.py` (after build_narrative_report). Adjust imports as needed (json, sqlite3, datetime already imported in W2).
    3. Verify all tests pass.
    4. Smoke test from terminal:
       ```bash
       python -m interpretation_narrative --help  # should list all 7 subcommands
       python -m interpretation_narrative cost-report  # should exit 0 even if narrative_cache empty
       ```
  </action>
  <verify>
    <automated>python -m pytest tests/test_eval_harness.py -p no:cov -x && python -m interpretation_narrative --help</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "def save_rating" interpretation_narrative.py` == 1
    - `grep -c "def save_side_by_side" interpretation_narrative.py` == 1
    - `grep -c "def score_sc1" interpretation_narrative.py` == 1
    - `grep -c "def score_sc6" interpretation_narrative.py` == 1
    - `grep -c "def cost_report" interpretation_narrative.py` == 1
    - `grep -c "def _cli_main" interpretation_narrative.py` == 1
    - `python -m interpretation_narrative --help 2>&1 | grep -c "cost-report\|score-cost\|eval-rate\|generate-eval-set\|generate-side-by-side\|score-side-by-side\|score\|record-fixture\|rate-side-by-side"` ≥ 8 (B-6 added score-cost)
    - `python -m interpretation_narrative score-cost --db analytics.db` exits 0 (PASS or SKIP — depending on cache state)
    - `python -m interpretation_narrative cost-report --db analytics.db` exits 0
    - `python -m pytest tests/test_eval_harness.py -p no:cov` ALL PASS (≥18 tests)
    - `python -m pytest -p no:cov` full suite green
    - `python -m interpretation_narrative eval-rate --csv /tmp/test_ratings.csv --report-id smoke --player 76561198386265483 --dim tone --score 4 --notes test --prompt-hash abc123` exits 0 and creates the CSV
  </acceptance_criteria>
  <done>
    All eval CLI shipped. User can: generate-eval-set → eval-rate per dim per report → score → see SC-1 verdict in 1 session. Side-by-side flow analogous for SC-6. cost-report ready for ongoing monitoring (REQ-9). record-fixture ready for W4 to refresh W0 placeholder fixtures with real-API output once prompt converges.
  </done>
</task>

</tasks>

<verification>
- `python -m pytest -p no:cov` full suite green
- `python -m interpretation_narrative --help` lists all subcommands
- `python -m interpretation_narrative cost-report` exits 0 (or 1 if narrative_cache table missing — error message is clear)
- evals/v2_eval_player_roster.json + evals/README.md committed
</verification>

<success_criteria>
- Locked roster + rubric documentation
- 7 CLI subcommands available
- Score helpers compute SC-1 + SC-6 verdicts deterministically from CSV
- cost-report reflects real DB state (post-W0 schema migration)
- record-fixture available to refresh W0 placeholder fixtures during W4 prompt iteration
- All harness pieces ready for W4 manual run
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-05-SUMMARY.md` documenting:
- Final 10-REAL-player roster (no placeholders permitted per B-1+B-4 revision); if RosterResolutionError was raised, document tier-by-tier shortfall + operator path forward
- All 7+ CLI subcommands with their flag signatures
- Test count delta
- Whether cost-report on the real analytics.db reveals existing rows (likely 0 pre-W4 — that's expected)
- Any deviation from D-19 / D-20 schemas
</output>
