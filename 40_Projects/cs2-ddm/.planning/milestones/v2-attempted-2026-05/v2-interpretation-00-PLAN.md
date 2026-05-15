---
phase: v2-interpretation-narrative
plan: 00
type: execute
wave: 0
depends_on: []
files_modified:
  - db_utils.py
  - ddm_analyzer.py
  - config.py
  - requirements.txt
  - .gitignore
  - tests/conftest.py
  - tests/test_db_utils.py
  - tests/test_no_real_api.py
  - tests/test_ddm_analyzer_core.py
  - tests/fixtures/anthropic_recorded/ok_donk_peek.json
  - tests/fixtures/anthropic_recorded/hallucinated_tick.json
  - tests/fixtures/anthropic_recorded/hallucinated_demo.json
  - tests/fixtures/anthropic_recorded/no_direction_anchor.json
  - tests/fixtures/anthropic_recorded/refusal.json
  - tests/fixtures/anthropic_recorded/truncated_max_tokens.json
  - tests/fixtures/anthropic_recorded/clean_paraphrase.json
  - tests/fixtures/test_fixtures_load.py
  - scripts/backfill_round_number.py
  - prompts/.gitkeep
  - evals/.gitkeep
autonomous: true
requirements: [REQ-7, REQ-11]
must_haves:
  truths:
    - "D-01: round_number INTEGER column added to engagements via idempotent ALTER (computed from round_start ticks parsed by DDMAnalyzer); D-02: scripts/backfill_round_number.py one-shot idempotent backfill ships in this plan"
    - "engagements table has round_number INTEGER column (NULL allowed, idempotent ALTER)"
    - "narrative_cache table exists with PK (player_steamid, engagement_type, content_hash) and prompt_hash + cache_creation/read_input_tokens columns"
    - "_ALLOWED_TABLES on main contains exactly {engagements, duel_attempts, narrative_cache}"
    - "ddm_analyzer.analyze_engagement_episode emits round_number in result dict for new runs"
    - "tests/conftest.py blocks real anthropic.Anthropic() instantiation via autouse fixture"
    - "7 recorded fixture JSONs exist under tests/fixtures/anthropic_recorded/ and parse"
    - "scripts/backfill_round_number.py supports --dry-run and exits 0 idempotently"
    - "prompts/ and evals/ directories exist (with .gitkeep so future writes have a target)"
    - "anthropic>=0.89 pinned in requirements.txt"
    - "narrative_failures.log added to .gitignore"
  artifacts:
    - path: "db_utils.py"
      provides: "narrative_cache CREATE TABLE + round_number ALTER + _ALLOWED_TABLES extension"
      contains: "narrative_cache"
    - path: "ddm_analyzer.py"
      provides: "round_number triple from _compute_round_phase + result dict key"
      contains: "round_number"
    - path: "tests/conftest.py"
      provides: "_no_real_anthropic autouse fixture"
      contains: "_no_real_anthropic"
    - path: "scripts/backfill_round_number.py"
      provides: "Idempotent re-parse-based round_number backfill CLI"
      exports: ["backfill", "main"]
    - path: "tests/fixtures/anthropic_recorded/ok_donk_peek.json"
      provides: "Clean-output recorded LLM response fixture"
      contains: "Что у тебя получается"
  key_links:
    - from: "ddm_analyzer._compute_round_phase"
      to: "engagements.round_number column"
      via: "result dict propagated through analyze_engagement_episode"
      pattern: "round_number"
    - from: "tests/conftest.py"
      to: "anthropic.Anthropic"
      via: "monkeypatch autouse fixture raising RuntimeError"
      pattern: "Real Anthropic client requested"
---

<objective>
Wave 0 baseline. Migrate DB schema (round_number column on engagements + narrative_cache table), wire round_number emission in ddm_analyzer, install network-isolation guard for tests, drop the 7 recorded LLM response fixtures, scaffold the one-shot round_number backfill script, create prompts/ + evals/ directories, and pin the anthropic dependency. NO LLM call code in this plan — that lands in W1. NO public API of interpretation_narrative — only the soil downstream waves grow on.

Purpose: Every later wave depends on (a) DB schema present, (b) ddm_analyzer emitting round_number for new analyses, (c) recorded fixtures available to tests, (d) tests cannot hit real Anthropic API. Without this baseline, W1 cannot be tested deterministically and report_generator integration in W2 has no data to render.

Output:
- `db_utils.py` extended (narrative_cache table, round_number column, _ALLOWED_TABLES)
- `ddm_analyzer.py` `_compute_round_phase` returns 3-tuple; result dict gains `round_number` key
- `tests/conftest.py` autouse `_no_real_anthropic` fixture
- 7 JSON fixtures under `tests/fixtures/anthropic_recorded/`
- `scripts/backfill_round_number.py` (idempotent, --dry-run support)
- `prompts/` + `evals/` dirs with `.gitkeep`
- `requirements.txt` pins `anthropic>=0.89`
- `.gitignore` excludes `narrative_failures.log`
- New tests: `tests/test_no_real_api.py`, `tests/test_db_utils.py` extended, `tests/fixtures/test_fixtures_load.py`
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md
@CLAUDE.md
@db_utils.py
@ddm_analyzer.py
@tests/conftest.py
@tests/test_db_utils.py

<interfaces>
<!-- Existing contracts the executor will modify or extend. Do NOT explore the codebase to rediscover these. -->

From `db_utils.py` (current main):
```python
_ALLOWED_TABLES = {"engagements", "duel_attempts"}  # line 15

def save_to_db(df, db_path, table, match_id) -> None: ...
def init_db(db_path) -> None: ...
def _migrate_schema(conn) -> None: ...  # the only place to add narrative_cache + round_number
```

`_eng_migrations` list (db_utils.py:83-90) — APPEND `("round_number", "INTEGER DEFAULT NULL")` here. DO NOT reorder existing entries.

From `ddm_analyzer.py:591-612`:
```python
def _compute_round_phase(
    self, t0_tick: int, round_start_ticks: Optional[List[int]], tag: str,
) -> Tuple[Optional[float], Optional[str]]:
    # current return: (round_time_s, round_phase)
    # NEW return:    (round_time_s, round_phase, round_number)
    # round_number = idx + 1 when idx >= 0 (1-indexed); None for warmup before first round_start
```

Single caller at `analyze_engagement_episode` — search for `_compute_round_phase(` to find the unpack site, update both unpack and the result dict adjacent to existing `"round_phase": round_phase,` (around line 727).

From `tests/conftest.py` (current — only `fake_parser`): append the new `_no_real_anthropic` autouse fixture after `fake_parser`. Do NOT remove or modify `fake_parser`.

Pattern from RESEARCH §Testing Strategy (recorded fixture JSON shape):
```json
{
  "text": "## Что у тебя получается\n... (RU markdown body)",
  "usage": {"input_tokens": 4400, "output_tokens": 712, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0},
  "model": "claude-sonnet-4-6",
  "stop_reason": "end_turn",
  "captured_at": "2026-05-13T10:00:00Z"
}
```

Backfill script idempotency pattern (RESEARCH §Schema Migration step 6):
```python
parser = DemoParser(str(demo_path))
events = parser.parse_events(["round_start"])
rs_df = next((df for name, df in events if name == "round_start"), None)
round_start_ticks = sorted(rs_df["tick"].astype(int).tolist())
rn = bisect.bisect_right(round_start_ticks, int(t0))  # 1-indexed natural fit
conn.execute("UPDATE engagements SET round_number = ? WHERE rowid = ?", (rn, rid))
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: DB schema + ddm_analyzer round_number emission (RED→GREEN, single concern: data layer)</name>
  <files>db_utils.py, ddm_analyzer.py, tests/test_db_utils.py, tests/test_ddm_analyzer_core.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md (REQ-7 narrative_cache schema)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md (D-01, D-02)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md (db_utils.py + ddm_analyzer.py sections)
    - db_utils.py (full file — _migrate_schema is the only edit site)
    - ddm_analyzer.py lines 580-735 (only the _compute_round_phase region + its single caller)
    - tests/test_db_utils.py (existing patterns; add new tests after the last existing test)
    - tests/test_ddm_analyzer_core.py (find tests touching _compute_round_phase or analyze_engagement_episode result dict)
  </read_first>
  <behavior>
    RED tests written FIRST (commit `test(v2-00): RED narrative_cache schema + round_number migration`):
    - Test 1 (db_utils): `test_narrative_cache_schema_created` — call init_db on tmp DB; assert sqlite_master contains `narrative_cache`; assert `PRAGMA table_info(narrative_cache)` returns columns `{player_steamid, engagement_type, content_hash, narrative_md, model, tokens_in, tokens_out, cache_creation_input_tokens, cache_read_input_tokens, generated_at, prompt_hash}` and PK = `(player_steamid, engagement_type, content_hash)`.
    - Test 2 (db_utils): `test_round_number_migration_idempotent` — init_db on existing DB twice; assert no error; assert `round_number` column present in engagements; assert running on fresh DB also creates the column.
    - Test 3 (db_utils): `test_allowed_tables_includes_narrative_cache` — `assert _ALLOWED_TABLES == {"engagements", "duel_attempts", "narrative_cache"}` (exact equality — guards against accidental Phase 10a `ddm_fits` leak).
    - Test 4 (db_utils): `test_save_to_db_rejects_unknown_table_still` — re-affirm CR-01 invariant survives _ALLOWED_TABLES extension.
    - Test 5 (ddm_analyzer): `test_compute_round_phase_returns_round_number` — instantiate DDMAnalyzer with stub config; call `_compute_round_phase(t0_tick=1500, round_start_ticks=[100, 1000, 2500], tag="x")`; assert returns `(round_time_s, round_phase, round_number)` 3-tuple; assert `round_number == 2` (1-indexed via bisect_right of t0=1500 in [100,1000,2500] → idx=1+1=2). Use `pytest.raises(TypeError)` first iteration if function returns 2-tuple to confirm RED.
    - Test 6 (ddm_analyzer): `test_compute_round_phase_warmup_returns_none_round_number` — t0_tick=50 (before any round_start in [100, 1000]); assert returns `(None, "unknown", None)` (preserves existing warmup semantics — see ddm_analyzer.py:608-612 — round_phase="unknown" surfaces in phase chart, do NOT change to None).
    - Test 7 (ddm_analyzer): `test_analyze_engagement_episode_result_includes_round_number` — find existing test that checks the result dict shape (search for `analyze_engagement_episode`); assert `"round_number"` is a key in the returned dict (mock the round_start_ticks input).

    GREEN implementation (separate commit `feat(v2-00): narrative_cache schema + round_number column + emission`):
    - Edit `db_utils.py:15`: `_ALLOWED_TABLES = {"engagements", "duel_attempts", "narrative_cache"}` (per D-09 in PATTERNS.md, do NOT pull in Phase 10a's `ddm_fits`).
    - Edit `db_utils.py:_migrate_schema`: append `("round_number", "INTEGER DEFAULT NULL")` to `_eng_migrations` list at the end.
    - Edit `db_utils.py:_migrate_schema`: add the `narrative_cache` CREATE TABLE statement AFTER `processed_matches` block, BEFORE the function returns. Use exact schema from RESEARCH §Schema Migration step 2 — including `cache_creation_input_tokens INTEGER DEFAULT 0`, `cache_read_input_tokens INTEGER DEFAULT 0`, `prompt_hash TEXT` columns. PK = `(player_steamid, engagement_type, content_hash)`.
    - Edit `ddm_analyzer.py:_compute_round_phase`: change return signature to `Tuple[Optional[float], Optional[str], Optional[int]]`. Compute `round_number = idx + 1` when `idx >= 0`, else `None`. Preserve EXISTING warmup semantics: warmup branch (idx < 0) returns `(None, "unknown", None)` — round_phase="unknown" surfaces in phase chart per ddm_analyzer.py:608-612, do NOT collapse it to None. "No round_start_ticks at all" branch (round_start_ticks empty/None) keeps returning `(None, None, None)`.
    - Edit `ddm_analyzer.analyze_engagement_episode` (single call site): unpack new triple, add `"round_number": round_number` to the result dict adjacent to existing `"round_phase": round_phase`.
    - Update any other tests that call `_compute_round_phase` and unpack 2-tuple — convert to 3-tuple unpack. Grep `_compute_round_phase(` across `tests/` first to enumerate.
  </behavior>
  <action>
    Implement per the behavior block above. Commit RED first to demonstrate failure, then GREEN. Pre-commit hook auto-runs `black + ruff + pytest -p no:cov` and is ALWAYS respected — `--no-verify` is FORBIDDEN. RED commit strategy: mark every RED test with `@pytest.mark.xfail(strict=True, reason="RED — implementation lands in next commit")`. Strict xfail means the test is "expected to fail" → pytest exit code 0 → hook passes. GREEN commit removes the xfail marker; with implementation now present, the test passes naturally. If a RED test cannot fail under xfail (e.g. import error at collection time), restructure the test to assert behavior conditionally rather than skip the hook.

    Schema MUST match REQ-7 verbatim (per D-09 in PATTERNS.md):
    ```sql
    CREATE TABLE IF NOT EXISTS narrative_cache (
      player_steamid INTEGER NOT NULL,
      engagement_type TEXT NOT NULL,
      content_hash TEXT NOT NULL,
      narrative_md TEXT NOT NULL,
      model TEXT NOT NULL,
      tokens_in INTEGER,
      tokens_out INTEGER,
      cache_creation_input_tokens INTEGER DEFAULT 0,
      cache_read_input_tokens INTEGER DEFAULT 0,
      generated_at TEXT NOT NULL,
      prompt_hash TEXT,
      PRIMARY KEY (player_steamid, engagement_type, content_hash)
    )
    ```

    Idempotency rule: `init_db(p); init_db(p)` MUST be no-op the second time (CREATE TABLE IF NOT EXISTS + ALTER TABLE guarded by `PRAGMA table_info` set check — pattern already present in db_utils.py:82-93, just extend the list).
  </action>
  <verify>
    <automated>python -m pytest tests/test_db_utils.py tests/test_ddm_analyzer_core.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "narrative_cache" db_utils.py` ≥ 2 (CREATE statement + _ALLOWED_TABLES entry)
    - `grep -c "round_number" db_utils.py` ≥ 1 (in _eng_migrations list)
    - `grep -E "_ALLOWED_TABLES = \{[^}]*\"narrative_cache\"[^}]*\}" db_utils.py` returns 1 match
    - `grep -E "_ALLOWED_TABLES.*ddm_fits" db_utils.py` returns 0 matches (Phase 10a not leaked)
    - `grep -c "round_number" ddm_analyzer.py` ≥ 2 (new return + result dict key)
    - `grep -E "Tuple\[Optional\[float\], Optional\[str\], Optional\[int\]\]" ddm_analyzer.py` returns 1 match (signature update)
    - `python -m pytest tests/test_db_utils.py::test_narrative_cache_schema_created tests/test_db_utils.py::test_round_number_migration_idempotent tests/test_db_utils.py::test_allowed_tables_includes_narrative_cache tests/test_ddm_analyzer_core.py::test_compute_round_phase_returns_round_number tests/test_ddm_analyzer_core.py::test_compute_round_phase_warmup_returns_none_round_number -p no:cov` all PASS
    - `python -m pytest -p no:cov` full suite green (no regressions in 322 existing tests after triple-unpack updates)
  </acceptance_criteria>
  <done>
    DB schema migration shipped + ddm_analyzer round_number emission shipped + all tests green. analytics.db migration is idempotent (verified by re-run). New schema lives on main without Phase 10a worktree noise.
  </done>
</task>

<task type="auto">
  <name>Task 2: Test isolation infra (no-real-API guard) + recorded fixtures + scaffolding dirs</name>
  <files>tests/conftest.py, tests/test_no_real_api.py, tests/fixtures/anthropic_recorded/ok_donk_peek.json, tests/fixtures/anthropic_recorded/hallucinated_tick.json, tests/fixtures/anthropic_recorded/hallucinated_demo.json, tests/fixtures/anthropic_recorded/no_direction_anchor.json, tests/fixtures/anthropic_recorded/refusal.json, tests/fixtures/anthropic_recorded/truncated_max_tokens.json, tests/fixtures/anthropic_recorded/clean_paraphrase.json, tests/fixtures/test_fixtures_load.py, requirements.txt, .gitignore, prompts/.gitkeep, evals/.gitkeep</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Testing Strategy lines 522-635 (mock anthropic + autouse fixture pattern)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md (Wave 0 Requirements list)
    - tests/conftest.py (current 65 LOC — append, do not edit existing fake_parser)
    - .gitignore (current — append narrative_failures.log under appropriate section)
    - requirements.txt (find current ordering — anthropic goes alphabetically)
  </read_first>
  <action>
    1. **Append `_no_real_anthropic` autouse fixture to `tests/conftest.py`** (do NOT remove `fake_parser`):
    ```python
    @pytest.fixture(autouse=True)
    def _no_real_anthropic(monkeypatch):
        """Block real Anthropic client instantiation in tests. Tests that need a
        fake client install their own monkeypatch (overriding this autouse).
        Per RESEARCH §Testing Strategy lines 624-634."""
        def _boom(*a, **kw):
            raise RuntimeError(
                "Real Anthropic client requested in test — add monkeypatch."
            )
        monkeypatch.setattr("anthropic.Anthropic", _boom)
    ```
    Note: anthropic must be importable at fixture install time. Since `requirements.txt` will now pin it (step 5 below), and anthropic is already installed in venv per RESEARCH (verified `0.89.0`), the import resolves. If anthropic import fails at collection time, wrap monkeypatch.setattr in try/except ImportError and skip the fixture (defensive — but RESEARCH confirms package present).

    2. **Create `tests/test_no_real_api.py`** with 2 tests:
    ```python
    """Wave 0 guard — verify the autouse fixture in conftest.py blocks real LLM calls."""
    import pytest

    def test_real_anthropic_client_raises():
        import anthropic
        with pytest.raises(RuntimeError, match="Real Anthropic client requested"):
            anthropic.Anthropic(api_key="fake-key-not-used")

    def test_fixture_does_not_break_other_tests():
        # Sanity: importing other modules works under autouse fixture
        import db_utils
        assert hasattr(db_utils, "save_to_db")
    ```

    3. **Create `tests/fixtures/anthropic_recorded/` dir** and write 7 JSON fixtures. Each must have keys `{text, usage, model, stop_reason, captured_at}`. Use the per-fixture content table below. Text bodies are short (~150 chars each) since they exist for unit-test mocking, NOT for SC-1 eval — those come from real API in Wave 4.

    Per D-13 narrative section names (Russian):
    - `## Что у тебя получается`
    - `## Где теряешь время`
    - `## Action этой недели`

    | Fixture | text content | stop_reason | Notes |
    |-|-|-|-|
    | ok_donk_peek.json | "## Что у тебя получается\nДонк, твой T1→T2 на пике 312мс — Elite. Демо spirit-vs-faze.dem раунд 14, тик 12345 — отличная реакция.\n## Где теряешь время\nT0→T1 = 250мс, отстаёт от benchmark.\n## Action этой недели\nDemo review последних 5 смертей." | end_turn | Clean — references valid demo, tick, round + DIRECTIONS title "Demo review" |
    | hallucinated_tick.json | "## Что у тебя получается\nДонк, в раунде 14 на тике 99999999 ты среагировал отлично. Demo review для проверки." | end_turn | Tick 99999999 will NOT be in allowed_refs — validator must catch |
    | hallucinated_demo.json | "## Что у тебя получается\nВ матче fakedemo123.dem ты показал хорошую реакцию. Demo review поможет." | end_turn | demo not in allowed_refs |
    | no_direction_anchor.json | "## Что у тебя получается\nДонк хорошо играет на пике.\n## Где теряешь время\nMedium reaction time.\n## Action этой недели\nПродолжай тренироваться." | end_turn | NO DIRECTIONS title cited — D-14 fail |
    | refusal.json | "I can't help with that request." | refusal | Triggers REQ-10 fail-soft; usage non-zero |
    | truncated_max_tokens.json | "## Что у тебя получается\nДонк, на пике твоя реакция — Elite. Demo review последних демо. На тике 1234" | max_tokens | Cut mid-tick — validator should catch tick 1234 not in allowed (per R-6) |
    | clean_paraphrase.json | "## Что у тебя получается\nХорошие пики на Mirage без явной слабости. Demo review укрепит ритуал.\n## Где теряешь время\nЕсть несколько медленных моментов.\n## Action этой недели\nПродолжай DM." | end_turn | No explicit refs (no .dem, no tick, no round#) — validator passes per D-06 lax for non-numeric. Cites "Demo review" anchor + map name "Mirage" (whitelisted). |

    `usage` block for non-refusal fixtures: `{"input_tokens": 4400, "output_tokens": 700, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0}`.
    `usage` block for `refusal.json`: `{"input_tokens": 4400, "output_tokens": 20, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0}`.
    `model`: `"claude-sonnet-4-6"` for all.
    `captured_at`: `"2026-05-13T10:00:00Z"` for all (placeholder; refresh during Wave 4 prompt iteration).

    4. **Create `tests/fixtures/test_fixtures_load.py`**:
    ```python
    """Wave 0 — assert all 7 recorded anthropic fixtures parse + minimum schema."""
    import json
    from pathlib import Path
    import pytest

    FIXTURES_DIR = Path(__file__).parent / "anthropic_recorded"
    EXPECTED_FIXTURES = [
        "ok_donk_peek", "hallucinated_tick", "hallucinated_demo",
        "no_direction_anchor", "refusal", "truncated_max_tokens", "clean_paraphrase",
    ]

    @pytest.mark.parametrize("name", EXPECTED_FIXTURES)
    def test_fixture_loads_and_has_required_keys(name):
        p = FIXTURES_DIR / f"{name}.json"
        data = json.loads(p.read_text(encoding="utf-8"))
        assert {"text", "usage", "model", "stop_reason", "captured_at"} <= set(data.keys())
        assert isinstance(data["text"], str) and len(data["text"]) > 0
        assert {"input_tokens", "output_tokens"} <= set(data["usage"].keys())

    def test_all_seven_fixtures_present():
        present = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))
        assert sorted(EXPECTED_FIXTURES) == present
    ```

    5. **Append `anthropic>=0.89` to `requirements.txt`** in alphabetical order (read current file first to find correct insert point — likely between alphabetical neighbors).

    6. **Append `narrative_failures.log` to `.gitignore`** under existing logs section, OR if no logs section, add a new `# Phase v2 narrative coaching layer` block.

    7. **Create `prompts/.gitkeep` and `evals/.gitkeep`** (empty files). These dirs must exist on disk so W2/W3 plans have a target.
  </action>
  <verify>
    <automated>python -m pytest tests/test_no_real_api.py tests/fixtures/test_fixtures_load.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "_no_real_anthropic" tests/conftest.py` ≥ 1
    - `grep -c "fake_parser" tests/conftest.py` ≥ 1 (preserved — did not remove existing fixture)
    - `ls tests/fixtures/anthropic_recorded/ | grep -c '\.json$'` == 7
    - `python -c "import json,sys; [json.loads(open(f'tests/fixtures/anthropic_recorded/{n}.json').read()) for n in ['ok_donk_peek','hallucinated_tick','hallucinated_demo','no_direction_anchor','refusal','truncated_max_tokens','clean_paraphrase']]; print('OK')"` prints "OK"
    - `grep -c "anthropic" requirements.txt` ≥ 1
    - `grep -c "narrative_failures.log" .gitignore` == 1
    - `test -d prompts && test -d evals` succeeds (both directories exist)
    - `python -m pytest tests/test_no_real_api.py tests/fixtures/test_fixtures_load.py -p no:cov` PASS (8 tests minimum: 2 in test_no_real_api + 7 parametrized + 1 presence in test_fixtures_load)
    - `python -m pytest -p no:cov` full suite still green (autouse fixture does not break existing 322+ tests)
  </acceptance_criteria>
  <done>
    All test infrastructure in place: real-API blocked by autouse fixture, 7 recorded fixtures available for downstream waves, dirs scaffolded, deps pinned, .gitignore updated. W1 unit tests can mock LLM via these fixtures with zero risk of accidentally hitting the real Anthropic API.
  </done>
</task>

<task type="auto">
  <name>Task 3: Backfill script skeleton + dry-run mode (operator-run, NOT auto)</name>
  <files>scripts/backfill_round_number.py, tests/test_backfill_round_number.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Schema Migration step 6 lines 770-816
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md "scripts/backfill_round_number.py" section
    - bench/multi_player_batch_loop.py (closest argparse CLI analog — read top 50 lines for shape)
    - ddm_analyzer.py imports section (verify `import bisect` line — already present, can copy import shape)
  </read_first>
  <action>
    Create `scripts/backfill_round_number.py` (idempotent one-shot CLI; operator-run, NOT in CI). Per D-02 + R-2: the FULL re-parse on existing analytics.db (5557 rows × ~5min/demo ≈ 6.5h) is an operator-run gate documented in CONTEXT, NOT executed by this task. This task ships the SCRIPT + DRY-RUN MODE only. Real backfill execution happens in Wave 4 manual gate (or operator night-job).

    Script shape:
    ```python
    """One-shot, idempotent backfill of engagements.round_number from re-parsed
    round_start events. Operator-run; safe to re-execute (WHERE round_number IS NULL).

    Per CONTEXT.md D-02. Cost: ~5min/demo × N demos. Use --dry-run to enumerate
    work without writing.
    """
    from __future__ import annotations
    import argparse
    import bisect
    import sqlite3
    from contextlib import closing
    from pathlib import Path

    def backfill(db_path: str, demo_dirs: list[str], dry_run: bool = False) -> dict:
        """Returns stats dict: {demos_processed, rows_updated, demos_missing}.
        Idempotent: only updates rows WHERE round_number IS NULL."""
        from demoparser2 import DemoParser
        stats = {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}
        with closing(sqlite3.connect(db_path)) as conn:
            cur = conn.execute("""
                SELECT DISTINCT demo_name FROM engagements
                WHERE round_number IS NULL AND demo_name IS NOT NULL
            """)
            demos = [r[0] for r in cur.fetchall()]
            for demo_name in demos:
                # Find demo on disk in any of the given demo_dirs
                demo_path = None
                for d in demo_dirs:
                    candidate = Path(d) / demo_name
                    if candidate.exists():
                        demo_path = candidate
                        break
                if demo_path is None:
                    stats["demos_missing"].append(demo_name)
                    continue
                if dry_run:
                    n_rows = conn.execute(
                        "SELECT COUNT(*) FROM engagements WHERE demo_name = ? AND round_number IS NULL",
                        (demo_name,),
                    ).fetchone()[0]
                    print(f"[dry-run] would re-parse {demo_name} and update {n_rows} rows")
                    stats["rows_updated"] += n_rows
                    stats["demos_processed"] += 1
                    continue
                parser = DemoParser(str(demo_path))
                events = parser.parse_events(["round_start"])
                rs_df = next((df for name, df in events if name == "round_start"), None)
                if rs_df is None or rs_df.empty:
                    continue
                round_start_ticks = sorted(rs_df["tick"].astype(int).tolist())
                with conn:
                    rows = conn.execute(
                        "SELECT rowid, t0_manual_tick FROM engagements "
                        "WHERE demo_name = ? AND round_number IS NULL",
                        (demo_name,),
                    ).fetchall()
                    for rid, t0 in rows:
                        if t0 is None:
                            continue
                        rn = bisect.bisect_right(round_start_ticks, int(t0))
                        conn.execute(
                            "UPDATE engagements SET round_number = ? WHERE rowid = ?",
                            (rn, rid),
                        )
                        stats["rows_updated"] += 1
                stats["demos_processed"] += 1
        return stats

    def main() -> int:
        p = argparse.ArgumentParser(prog="backfill_round_number")
        p.add_argument("--db", default="analytics.db")
        p.add_argument("--demo-dir", nargs="+", required=True,
                       help="One or more directories containing .dem files")
        p.add_argument("--dry-run", action="store_true",
                       help="Enumerate work without writing")
        args = p.parse_args()
        stats = backfill(args.db, args.demo_dir, dry_run=args.dry_run)
        print(f"Demos processed: {stats['demos_processed']}, rows updated: {stats['rows_updated']}")
        if stats["demos_missing"]:
            print(f"Demos missing on disk: {len(stats['demos_missing'])}")
            for n in stats["demos_missing"][:10]:
                print(f"  - {n}")
        return 0

    if __name__ == "__main__":
        raise SystemExit(main())
    ```

    Tests in `tests/test_backfill_round_number.py`:
    ```python
    """Wave 0 — backfill script idempotency + dry-run."""
    import sqlite3
    from contextlib import closing
    from pathlib import Path
    import pytest
    import sys

    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from backfill_round_number import backfill  # noqa: E402

    @pytest.fixture
    def empty_db(tmp_path, monkeypatch):
        db = str(tmp_path / "test.db")
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("""CREATE TABLE engagements (
                demo_name TEXT, t0_manual_tick INTEGER, round_number INTEGER
            )""")
            conn.execute("INSERT INTO engagements VALUES ('missing.dem', 100, NULL)")
            conn.commit()
        return db

    def test_backfill_dry_run_no_writes(empty_db):
        # Demo missing on disk → counted as missing, no DB writes
        stats = backfill(empty_db, demo_dirs=["/nonexistent"], dry_run=True)
        assert stats["rows_updated"] == 0
        assert "missing.dem" in stats["demos_missing"]

    def test_backfill_idempotent_on_no_null_rows(tmp_path):
        # All rows already have round_number → backfill is no-op
        db = str(tmp_path / "test.db")
        with closing(sqlite3.connect(db)) as conn:
            conn.execute("""CREATE TABLE engagements (
                demo_name TEXT, t0_manual_tick INTEGER, round_number INTEGER
            )""")
            conn.execute("INSERT INTO engagements VALUES ('any.dem', 100, 5)")
            conn.commit()
        stats = backfill(db, demo_dirs=["/nonexistent"], dry_run=False)
        assert stats["rows_updated"] == 0
        assert stats["demos_processed"] == 0
    ```

    Note: real-demo integration test would require a `.dem` file fixture; skip that — the manual operator gate in Wave 4 handles real-data validation. Wave 0 only proves the script is wired correctly + dry-run + idempotency on no-NULL-rows.
  </action>
  <verify>
    <automated>python -m pytest tests/test_backfill_round_number.py -p no:cov -x && python scripts/backfill_round_number.py --db analytics.db --demo-dir for_analysis --dry-run</automated>
  </verify>
  <acceptance_criteria>
    - `test -f scripts/backfill_round_number.py` succeeds
    - `python scripts/backfill_round_number.py --help` exits 0 and prints usage with --db, --demo-dir, --dry-run flags
    - `grep -c "WHERE round_number IS NULL" scripts/backfill_round_number.py` ≥ 2 (used for both SELECT and gating)
    - `grep -c "bisect.bisect_right" scripts/backfill_round_number.py` ≥ 1
    - `python -m pytest tests/test_backfill_round_number.py -p no:cov` PASS
    - Dry-run command exits 0 (does not require analytics.db to have nullable rows; just must not crash)
  </acceptance_criteria>
  <done>
    Backfill skeleton ready to run as operator gate. Real backfill execution deferred to Wave 4 manual checkpoint (per R-2). Script tested for idempotency on no-NULL-rows + dry-run mode. Operator can invoke `python scripts/backfill_round_number.py --db analytics.db --demo-dir ../for_analysis/spirit ../for_analysis/faze` overnight to populate round_number on existing 5557 rows.
  </done>
</task>

</tasks>

<verification>
- `python -m pytest -p no:cov` full suite green (322 existing + ~15 new = 337+ tests)
- `python -c "from db_utils import _ALLOWED_TABLES; assert _ALLOWED_TABLES == {'engagements', 'duel_attempts', 'narrative_cache'}"` exits 0
- `python -c "import sqlite3; from db_utils import init_db; import tempfile; t=tempfile.mktemp(suffix='.db'); init_db(t); init_db(t); c=sqlite3.connect(t); print(sorted(r[0] for r in c.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()))"` prints a list including `narrative_cache`
- `ls tests/fixtures/anthropic_recorded/*.json | wc -l` returns 7
- `test -d prompts && test -d evals && test -f scripts/backfill_round_number.py` all succeed
</verification>

<success_criteria>
- All 3 tasks complete with green tests
- DB schema migrations idempotent (verified by re-running init_db)
- ddm_analyzer.analyze_engagement_episode now writes round_number on every new engagement (downstream new analyses get attribution data automatically)
- Existing 322 tests still pass (no regressions from triple-unpack updates)
- W1 plans have all infrastructure they need: schema, fixtures, autouse no-real-API guard, scaffolded dirs, anthropic dep pinned
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-00-SUMMARY.md` documenting:
- DB schema changes shipped (narrative_cache table + round_number column + _ALLOWED_TABLES extension)
- ddm_analyzer signature change (return triple, result dict key)
- Test infrastructure shipped (autouse fixture, 7 JSON fixtures)
- Backfill script status (skeleton ready; operator gate deferred to Wave 4)
- Test count delta (322 → ~337)
- Any deviation from plan (e.g., if Phase 10a worktree had snuck a `narrative_cache` column already, or if a 4th caller of _compute_round_phase was discovered)
</output>
