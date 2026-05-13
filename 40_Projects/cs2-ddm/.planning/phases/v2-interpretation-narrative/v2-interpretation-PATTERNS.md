# Phase v2-interpretation-narrative — Pattern Map

**Mapped:** 2026-05-12
**Files analyzed:** 17 (9 NEW, 7 MODIFIED, 1 NEW dir convention)
**Analogs found:** 16 / 17 (only `tests/fixtures/anthropic_recorded/*.json` is novel — recorded JSON pattern, no project precedent)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-|-|-|-|-|
| `interpretation_narrative.py` | new module — entry + LLM client + cache I/O + cost CLI | request-response (sync HTTP) + DB read/write + transform | `interpretation.py` | role-match (no LLM precedent in repo) |
| `prompts/coaching_v2.md` | versioned prompt template (RU markdown) | static asset, content-hashed | NONE (new convention; closest = `.planning/PROJECT.md` markdown style) | new convention |
| `scripts/backfill_round_number.py` | one-shot DB migration (idempotent) | batch transform | `bench/multi_player_batch_loop.py` (CLI orchestrator) + `db_utils._migrate_schema` (idempotent shape) | role-match (new dir `scripts/` doesn't exist yet) |
| `tests/test_interpretation_narrative.py` | unit + integration (mocked anthropic) | request-response | `tests/test_interpretation.py` | exact |
| `tests/test_narrative_validator.py` | adversarial regex unit tests | transform / pure-fn | `tests/test_csv_utils.py` (TestClass-grouped unit pattern) | role-match |
| `tests/test_top_moments_query.py` | DB integration (joins + cluster-bleed gate) | DB read | `tests/test_db_utils.py` + `tests/test_interpretation.py::mock_db` fixture | exact |
| `tests/test_eval_harness.py` | CLI smoke + CSV append/dedup eval-rate | CRUD on CSV | `tests/test_csv_utils.py` (`save_results` dedup tests) | exact |
| `tests/test_no_real_api.py` | autouse anti-network fixture verification | guard | `tests/conftest.py` `fake_parser` autouse-style fixture | role-match |
| `tests/fixtures/anthropic_recorded/*.json` | recorded LLM response fixtures | static asset | NONE — first recorded-response convention in repo | new convention |
| `evals/v2_eval_player_roster.json` | locked 10-player SteamID list | static config | `config.py:PLAYER_NAMES` dict (SteamID → name lookup) | role-match (different format) |
| `evals/interpretation_v2_ratings.csv` | append+dedup rating data | CSV append/dedup | `csv_utils.save_results()` | exact (same dedup pattern, different key) |
| `evals/v2_side_by_side.csv` | SC-6 forced-choice ratings | CSV append/dedup | `csv_utils.save_results()` | exact |
| `evals/README.md` | rubric + solo-rater limitation | doc | `.planning/PROJECT.md` | role-match |
| `db_utils.py` | MODIFIED — extend `_ALLOWED_TABLES` + add `narrative_cache` CREATE + add `round_number` to `_eng_migrations` | DB schema | self (Phase 6 + Phase 10a worktree precedent) | exact |
| `ddm_analyzer.py` | MODIFIED — extend `_compute_round_phase` to return round_number; add to result dict | transform | `_compute_round_phase` (line 591) itself | exact |
| `report_generator.py` | MODIFIED — insert narrative block between header + interpretation_section; try/except fail-soft | request-response composition | `_section()` + `generate_html_report()` lines 595–663 | exact |
| `config.py` | MODIFIED — add `LLM_PROVIDER`, `LLM_MODEL`, `NARRATIVE_COMMON_NOUNS_WHITELIST` constants; expand `PLAYER_NAMES` | static config | `config.py:PLAYER_NAMES` (line 172) + `T0_TO_T2_MAX_TICKS` (line 104) | exact |

## Pattern Assignments

### `interpretation_narrative.py` (new module — request-response + DB I/O + transform)

**Analog:** `interpretation.py` (427 LOC, Phase 8 layer; v2 wraps this without replacing per CONTEXT line 145).

**Imports pattern** (interpretation.py:1-7):
```python
"""Interpretation layer: tier computation, drill lookup, benchmark percentiles."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from typing import Optional
import pandas as pd
from config import DB_PATH, PLAYER_NAMES, T0_TO_T2_MAX_TICKS
```
**Apply to v2:** Same `from __future__ import annotations` + `from contextlib import closing` for sqlite. Add `import os` (env vars), `import json/hashlib` (content_hash), `from anthropic import Anthropic, APIError, RateLimitError, APIStatusError` (per RESEARCH §Anthropic SDK Integration).

**Module-level constants pattern** (interpretation.py:10-35 — `_MS_PER_TICK`, `_T0_T2_MAX_MS`, `_METRICS_LOWER_IS_BETTER`, `_ABSOLUTE_ELITE_CEILING`):
```python
# Tick → ms (CS2 tickrate 64). Inline to avoid coupling.
_MS_PER_TICK = 1000.0 / 64.0
_T0_T2_MAX_MS = T0_TO_T2_MAX_TICKS * _MS_PER_TICK

_METRICS_LOWER_IS_BETTER = {
    "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
    "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
}
```
**Apply to v2:** Hoist `PRICING` dict + `_LLM_TEMPERATURE = 0.4` + `_MAX_TOKENS = 2500` + `_PROMPT_PATH = "prompts/coaching_v2.md"` as module-level constants with detailed comment-justifications (this codebase favors named constants — see CLAUDE.md "Code Style: no magic numbers").

**Public API pattern** (interpretation.py:140 `assign_tier()`, 261 `compute_interpretation()`, 422 `get_worst_metric()`):
```python
def assign_tier(
    value: float,
    p25: float,
    p50: float,
    p75: float,
    lower_is_better: bool,
    absolute_elite: Optional[float] = None,
) -> str:
    """Tier from benchmark quartiles, with optional absolute Elite ceiling.
    ...
    """
```
**Apply to v2:** Strict typing, `Optional` for nullable, multi-line docstring with rationale. Public functions per RESEARCH `build_narrative_report`, `fetch_top_moments`, `validate_narrative`. Private helpers prefixed `_`.

**SQLite connection + SteamID-safe query** (interpretation.py:179-200, `get_benchmark_players`):
```python
def get_benchmark_players(db_path: str = DB_PATH) -> list[dict]:
    """Return list of {steamid, display_name, demo_count, small_sample} for all players in analytics.db."""
    with closing(sqlite3.connect(db_path)) as conn:
        # Use cursor directly — pd.read_sql casts large int64 steamids to float64,
        # which loses precision on 17-digit SteamID64 values.
        cursor = conn.execute(
            ...
        )
```
**Apply to v2:** `fetch_top_moments()` MUST use `cursor.fetchall()` not `pd.read_sql` for any column containing `player_steamid` or `enemy_steamid` (CLAUDE.md gotcha + R-8 in RESEARCH). Use `with closing(sqlite3.connect(db_path)) as conn:` context manager pattern.

**Cluster-bleed gate (mandatory reuse per D-04 + RESEARCH REQ-2)** (interpretation.py:295-306):
```python
# Cluster-bleed gate (Bug 2): drop rows where rt_visible_to_hit_ms exceeds
# T0_TO_T2_MAX_TICKS — these are not "slow reactions" but T2 captured from
# a separate firefight on the same target. Future runs cap at source in
# ddm_analyzer; this filter cleans existing DB rows from before the fix.
rt_col = "rt_visible_to_hit_ms"
if rt_col in eng_df_raw.columns:
    ungradeable_mask = eng_df_raw[rt_col].notna() & (eng_df_raw[rt_col] > _T0_T2_MAX_MS)
    n_ungradeable = int(ungradeable_mask.sum())
    eng_df = eng_df_raw[~ungradeable_mask].copy()
```
**Apply to v2:** `fetch_top_moments()` query MUST include `WHERE rt_visible_to_hit_ms IS NULL OR rt_visible_to_hit_ms <= ?` with `_T0_T2_MAX_MS` as bound parameter (same gate, server-side). Top-moments are derived from already-filtered rows.

**CLI entry pattern** (no precise project precedent — closest is `bench/multi_player_batch_loop.py` argparse). Use:
```python
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(prog="interpretation_narrative")
    sub = parser.add_subparsers(dest="cmd", required=True)
    cost = sub.add_parser("cost-report")
    cost.add_argument("--db", default=DB_PATH)
    rate = sub.add_parser("eval-rate")
    rate.add_argument("--player", type=int, required=True)
    record = sub.add_parser("record-fixture")
    args = parser.parse_args()
    ...
```
**Apply to v2:** REQ-9 cost-report subcommand + REQ-8 eval-rate + RESEARCH `record-fixture` for one-shot real-API capture.

**Logger pattern** (config.py:186-201 `get_logger`):
```python
def get_logger(match_id: int | str, debug: bool = False) -> logging.Logger:
    name = f"DDM.{match_id}"
    logger = logging.getLogger(name)
    if not logger.handlers:
        fh = logging.FileHandler("ddm_analysis.log", encoding="utf-8")
        ...
```
**Apply to v2:** `narrative_failures.log` writer should reuse this logger factory pattern (NOT print). Use `logger.error(f"NARRATIVE_FAIL kind={kind} reason={reason} raw={raw[:500]!r}")` for fail-soft path (REQ-10).

---

### `prompts/coaching_v2.md` (new convention — versioned RU prompt)

**Analog:** NONE in code; closest is `.planning/PROJECT.md` markdown convention + RESEARCH §Anthropic SDK Integration which dictates structure.

**Pattern from RESEARCH (§Anthropic SDK Integration → Prompt caching, lines 263-294):**
```
[STATIC SYSTEM BLOCK — cacheable]
- Role/tone calibration (~300-400 tokens) — D-10 brutally honest coach, address by nickname, без flattery
- Output structure spec (D-13 sections):
  ## Что у тебя получается
  ## Где теряешь время
  ## Action этой недели
- Length cap (D-12: 500w ± 100, hard cap "Не превышай 600 слов")
- Anti-hallucination instruction (REQ-4): "do not invent demo events, ticks, rounds, maps — only reference items from input"
- DIRECTIONS reference policy (D-14): MUST cite at least one DIRECTION title verbatim

[DYNAMIC USER BLOCK — NOT cached, per call]
- Player context (nickname, n_engagements, engagement_type)
- Tier table rows (6 metrics × tier/value/benchmark from compute_interpretation output)
- Top moments (18 items: 2 worst + 1 best per metric × 6 metrics)
- Bottleneck info
```

**Apply to v2:** File is plain markdown loaded via `Path("prompts/coaching_v2.md").read_text(encoding="utf-8")` then split into static/dynamic via `{{DYNAMIC_USER_BLOCK}}` placeholder. Static portion cached via `cache_control={"type": "ephemeral", "ttl": "5m"}` (RESEARCH line 270).

---

### `scripts/backfill_round_number.py` (new module — one-shot batch transform)

**Analog:** `bench/multi_player_batch_loop.py` (CLI orchestrator) + `db_utils._migrate_schema()` (idempotent shape).

**Idempotency pattern from `db_utils._migrate_schema`** (db_utils.py:72-93):
```python
def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migration. Adds columns/tables if missing."""
    # ...
    cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
    _eng_migrations = [
        ("demo_name", "TEXT DEFAULT NULL"),
        ...
    ]
    for col, col_def in _eng_migrations:
        if col not in cols:
            conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
```
**Apply to v2:** Backfill script loop must be re-runnable. Use `WHERE round_number IS NULL` filter (D-02 + RESEARCH §Schema Migration step 6) so partial runs resume cleanly.

**Demo re-parse pattern + bisect** (ddm_analyzer.py:597 + RESEARCH §Schema Migration step 6 lines 776-815):
```python
import sqlite3, bisect
from pathlib import Path
from contextlib import closing
from demoparser2 import DemoParser

def backfill(db_path: str, demo_dir: str) -> dict:
    """Idempotent: update rows where round_number IS NULL."""
    with closing(sqlite3.connect(db_path)) as conn:
        cur = conn.execute("""
            SELECT DISTINCT demo_name FROM engagements
            WHERE round_number IS NULL AND demo_name IS NOT NULL
        """)
        ...
        for demo_name in demos:
            parser = DemoParser(str(demo_path))
            events = parser.parse_events(["round_start"])
            rs_df = next((df for name, df in events if name == "round_start"), None)
            if rs_df is None or rs_df.empty:
                continue
            round_start_ticks = sorted(rs_df["tick"].astype(int).tolist())
            with conn:
                for row in conn.execute(
                    "SELECT rowid, t0_manual_tick FROM engagements "
                    "WHERE demo_name = ? AND round_number IS NULL",
                    (demo_name,),
                ).fetchall():
                    rid, t0 = row
                    if t0 is None: continue
                    rn = bisect.bisect_right(round_start_ticks, int(t0))
                    conn.execute("UPDATE engagements SET round_number = ? WHERE rowid = ?", (rn, rid))
```
**Apply to v2:** `bisect.bisect_right` already used for round_phase in ddm_analyzer.py:597 — same algorithm, same `round_start_ticks` source. `with conn:` per-demo for transaction granularity (small enough chunks; DB lock not held across all 5557 rows).

**CLI argparse pattern** (bench/multi_player_batch_loop.py is the closest analog; reuse its shape):
```python
if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--db", default="analytics.db")
    p.add_argument("--demo-dir", nargs="+", required=True)
    args = p.parse_args()
    stats = backfill(args.db, args.demo_dir)
    print(f"Demos processed: {stats['demos_processed']}, rows updated: {stats['rows_updated']}")
    if stats["demos_missing"]:
        print(f"Demos missing on disk: {len(stats['demos_missing'])}")
```

---

### `tests/test_interpretation_narrative.py` (new — exact mirror of test_interpretation.py)

**Analog:** `tests/test_interpretation.py` (184 LOC, 322-test suite participant).

**Module docstring + import pattern** (test_interpretation.py:1-13):
```python
"""Phase 8 interpretation layer tests. Task IDs map to 08-VALIDATION.md."""
import pytest
import sqlite3
import os
import tempfile
import pandas as pd

# All imports must work before any test runs
from interpretation import (
    assign_tier, compute_interpretation, get_benchmark_players,
    get_worst_metric, DRILLS, _FALLBACK_THRESHOLDS,
)
from config import PLAYER_NAMES
```
**Apply to v2:** Module docstring `"""Phase v2 narrative coaching layer tests. Task IDs map to v2-VALIDATION.md."""`. Import all public + private (`_call_llm`, `_content_hash`, `_cache_get`, `_cache_put`, `NarrativeBuildError`) so tests can poke internals.

**Mock DB fixture pattern** (test_interpretation.py:33-55):
```python
@pytest.fixture
def mock_db(tmp_path):
    """Create minimal analytics.db with 25 karrigan peek engagements across 25 demos."""
    db_path = str(tmp_path / "test.db")
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE engagements (
        player_steamid INTEGER, engagement_type TEXT, demo_name TEXT,
        crosshair_angle_at_t0_deg REAL, rt_visible_to_aim_ms REAL,
        rt_aim_to_hit_ms REAL, rt_visible_to_hit_ms REAL
    )""")
    ...
    sid = 76561197989430253  # karrigan
    for i in range(25):
        conn.execute("INSERT INTO engagements VALUES (?,?,?,?,?,?,?)",
            (sid, "peek", f"demo_{i}.dem", 5.0 + i * 0.2, 200.0 + i * 5, 400.0 + i * 10, 600.0 + i * 15))
        ...
    conn.commit()
    conn.close()
    return db_path, sid
```
**Apply to v2:** `mock_db_with_round_number` fixture — extend with `round_number INTEGER`, `map_name TEXT`, `t0_manual_tick INTEGER` columns. Use real 17-digit SteamID `76561198386265483` (donk) to catch SteamID64 truncation regressions (R-8). Add `duel_attempts` table population for `fetch_top_moments` join coverage.

**Mock anthropic pattern (from RESEARCH §Testing Strategy lines 528-569):**
```python
class _FakeMessage:
    def __init__(self, text: str, usage: dict, stop_reason: str = "end_turn", model: str = "claude-sonnet-4-6"):
        from types import SimpleNamespace
        self.content = [SimpleNamespace(text=text, type="text")]
        self.usage = SimpleNamespace(**usage)
        self.stop_reason = stop_reason
        self.stop_details = None
        self.model = model

class FakeAnthropic:
    def __init__(self, response: _FakeMessage): self.messages = _FakeMessages(response)

@pytest.fixture
def mock_anthropic_ok(monkeypatch):
    fixture = load_fixture("ok_donk_peek")
    fake = FakeAnthropic(_FakeMessage(text=fixture["text"], usage={...}))
    monkeypatch.setattr(inv, "_get_client", lambda: fake)
    return fake
```
**Apply to v2:** Place `FakeAnthropic` + `load_fixture` helpers in `tests/conftest.py` (autouse-friendly) — same convention as existing `fake_parser` fixture (conftest.py:38-65).

**Schema-shape assertion pattern** (test_interpretation.py:58-67):
```python
def test_compute_interpretation_schema(mock_db):  # 08-01-03
    db_path, sid = mock_db
    rows = compute_interpretation(db_path, player_steamid=sid, benchmark_steamid=sid, engagement_type="peek")
    assert len(rows) >= 3
    for row in rows:
        assert "metric" in row
        assert "tier" in row
        assert "drill" in row
```
**Apply to v2:** `test_build_narrative_returns_markdown_with_d13_sections`:
```python
def test_build_narrative_d13_sections(mock_db_with_round_number, mock_anthropic_ok):
    md = build_narrative_report(rows, top_moments, player_context)
    assert "## Что у тебя получается" in md
    assert "## Где теряешь время" in md
    assert "## Action этой недели" in md
```

**Test ID convention** (test_interpretation.py inline `# 08-01-03` comments) — apply per VALIDATION.md mapping (`# v2-NN-NN`).

---

### `tests/test_narrative_validator.py` (new — adversarial regex unit tests)

**Analog:** `tests/test_csv_utils.py` (TestClass-grouped unit tests, 271 LOC).

**TestClass grouping pattern** (test_csv_utils.py:21-30):
```python
# ─────────────────────────────────────────────────────────────────────────────
# UNIT TESTS (Mocked I/O)
# ─────────────────────────────────────────────────────────────────────────────

class TestLoadExistingResults:
    """Unit tests for load_existing_results() with mocked files."""

    def test_load_nonexistent_file_returns_empty_dataframe(self):
        """Loading a non-existent file should return empty DataFrame."""
        result = load_existing_results("/nonexistent/file.csv")
        assert isinstance(result, pd.DataFrame)
        assert result.empty
```
**Apply to v2:**
```python
class TestValidateDemoRefs:
    """Pass 1 — demo filename detection."""

    def test_demo_in_allowed_passes(self):
        ok, viols = validate_narrative("review demo spirit-vs-faze.dem", {"demos": {"spirit-vs-faze.dem"}, "ticks": set(), "rounds": set(), "maps": set()})
        assert ok is True
        assert viols == []

    def test_demo_not_in_allowed_fails(self):
        ok, viols = validate_narrative("review fakedemo123.dem", {"demos": {"real.dem"}, "ticks": set(), "rounds": set(), "maps": set()})
        assert ok is False
        assert any(v["type"] == "demo" and v["value"] == "fakedemo123.dem" for v in viols)

class TestValidateTicks: ...
class TestValidateRounds: ...
class TestValidateDirectionAnchor: ...  # D-14
class TestValidateRussianMorphology: ...  # R-3 in RESEARCH (тика/тиком/тике)
```

**Adversarial fixture set** (per RESEARCH §Testing Strategy lines 591-600 — 7 fixtures):
1. `ok_donk_peek.json` — clean
2. `hallucinated_tick.json` — fake tick
3. `hallucinated_demo.json` — fake demo
4. `no_direction_anchor.json` — D-14 fail
5. `refusal.json` — `stop_reason="refusal"`
6. `truncated_max_tokens.json` — `stop_reason="max_tokens"`
7. `clean_paraphrase.json` — no explicit refs (validator passes)

---

### `tests/test_top_moments_query.py` (new — DB integration)

**Analog:** `tests/test_db_utils.py` (332 LOC) for DB-roundtrip pattern + `tests/test_interpretation.py::mock_db` for fixture shape.

**Roundtrip pattern** (test_db_utils.py:40-58):
```python
def test_save_to_db_creates_table_and_inserts_rows(tmp_path):
    db = str(tmp_path / "test.db")
    df = _sample_df()
    db_utils.save_to_db(df, db, "engagements", "match1")
    with closing(sqlite3.connect(db)) as conn:
        result = pd.read_sql("SELECT * FROM engagements", conn)
    assert len(result) == 2
    assert set(result.columns) >= {"match_id", "player_steamid", "rt_visible_to_hit_ms"}


def test_save_to_db_same_match_id_replaces_old_rows(tmp_path):
    """Idempotency: re-saving same match_id keeps N rows, not 2N."""
    ...
```
**Apply to v2:**
```python
def test_fetch_top_moments_returns_n_worst_per_metric(populated_db):
    moments = fetch_top_moments(populated_db, player_steamid=76561198386265483,
                                metric="rt_visible_to_aim_ms", engagement_type="peek",
                                benchmark_p50=200.0, n_worst=2, n_best=1)
    assert len(moments) == 3
    # worst 2 first (by gap_vs_benchmark, lower_is_better → highest values)
    assert moments[0]["player_value"] >= moments[1]["player_value"] >= moments[2]["player_value"]

def test_fetch_top_moments_excludes_cluster_bleed_rows(populated_db_with_bleed):
    """Rows with rt_visible_to_hit_ms > T0_TO_T2_MAX_MS must be excluded."""
    moments = fetch_top_moments(populated_db_with_bleed, ...)
    assert all(m["rt_visible_to_hit_ms"] <= _T0_T2_MAX_MS for m in moments if m.get("rt_visible_to_hit_ms"))

def test_fetch_top_moments_steamid64_no_truncation(populated_db):
    """Regression: cursor.fetchall not pd.read_sql for SteamID columns (CLAUDE.md gotcha)."""
    moments = fetch_top_moments(populated_db, player_steamid=76561198386265483, ...)
    # demo_name + tick must come back stably — no float64 cast
    assert isinstance(moments[0]["t0_tick"], int)
```

---

### `tests/test_eval_harness.py` (new — CSV append/dedup smoke)

**Analog:** `tests/test_csv_utils.py` (271 LOC).

**Dedup test pattern** (test_csv_utils.py:46-81 — the embedded-header-strip + dedup tests):
```python
def test_load_csv_strips_duplicate_headers(self):
    """Loading CSV with embedded header rows strips them."""
    csv_content = """match_id,moment_timestamp,rt_visible_to_aim_ms
1,2:30,150
match_id,moment_timestamp,rt_visible_to_aim_ms
2,3:15,200"""
    ...
```
**Apply to v2:** `evals/interpretation_v2_ratings.csv` dedup key per D-19 = `(report_id, prompt_hash, dim)`. Test pattern:
```python
def test_eval_rate_appends_new_row(tmp_path):
    csv = tmp_path / "ratings.csv"
    _write_rating(csv, report_id="r1", player_steamid=..., prompt_hash="abc", dim="actionability", score=4)
    _write_rating(csv, report_id="r1", player_steamid=..., prompt_hash="abc", dim="tone", score=5)
    df = pd.read_csv(csv)
    assert len(df) == 2

def test_eval_rate_overwrites_same_key(tmp_path):
    """Re-rate same (report_id, prompt_hash, dim) overwrites — D-19 dedup key."""
    csv = tmp_path / "ratings.csv"
    _write_rating(csv, report_id="r1", prompt_hash="abc", dim="tone", score=3)
    _write_rating(csv, report_id="r1", prompt_hash="abc", dim="tone", score=5)  # re-rate
    df = pd.read_csv(csv)
    assert len(df) == 1
    assert df.iloc[0]["score"] == 5

def test_eval_rate_new_prompt_hash_creates_new_row(tmp_path):
    """D-18: prompt_hash change → new row, NOT overwrite (preserves iteration history)."""
    ...
```

---

### `tests/test_no_real_api.py` (new — autouse anti-network guard)

**Analog:** `tests/conftest.py:38-65` `fake_parser` fixture (autouse-style discipline) + RESEARCH §Testing Strategy lines 624-634.

**Pattern from RESEARCH (lines 624-634):**
```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def _no_real_anthropic(monkeypatch):
    """Fail loud if any test forgets to mock anthropic."""
    def _boom(*a, **kw):
        raise RuntimeError("Real Anthropic client requested in test — add monkeypatch.")
    monkeypatch.setattr("anthropic.Anthropic", _boom)
```
**Apply to v2:** Place in `tests/conftest.py` alongside existing `fake_parser` fixture. Add `tests/test_no_real_api.py` with positive assertions:
```python
def test_no_anthropic_call_without_monkeypatch():
    """Verify autouse fixture blocks real Anthropic instantiation."""
    import anthropic
    with pytest.raises(RuntimeError, match="Real Anthropic client"):
        anthropic.Anthropic(api_key="fake")

def test_get_client_raises_without_api_key(monkeypatch):
    """REQ-10 fail-soft trigger: missing key surfaces as NarrativeBuildError."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr("anthropic.Anthropic", anthropic.Anthropic)  # restore real
    with pytest.raises(NarrativeBuildError, match="ANTHROPIC_API_KEY"):
        _get_client()
```

---

### `tests/fixtures/anthropic_recorded/*.json` (new convention — recorded responses)

**Analog:** NONE — first recorded-response fixture pattern. Closest precedent = `tests/fixtures/phase10a_regression_baseline.json` (Phase 10a worktree — frozen JSON for regression).

**Pattern from RESEARCH §Testing Strategy lines 580-590:**
```json
{
  "text": "## Что у тебя получается\n...",
  "usage": {"input_tokens": 4400, "output_tokens": 712, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0},
  "model": "claude-sonnet-4-6",
  "stop_reason": "end_turn",
  "captured_at": "2026-05-13T10:00:00Z"
}
```
**Apply to v2:** Create `tests/fixtures/` dir (does not exist yet — verified). 7 fixture files per RESEARCH §Testing Strategy. Generate via one-shot CLI: `python -m interpretation_narrative record-fixture --player <sid> --type peek --out tests/fixtures/anthropic_recorded/ok_donk_peek.json`.

---

### `evals/v2_eval_player_roster.json` (new — locked 10-player config)

**Analog:** `config.py:PLAYER_NAMES` (line 172) — SteamID → name lookup precedent.

**Existing pattern** (config.py:172-175):
```python
PLAYER_NAMES: dict[int, str] = {
    76561197989430253: "karrigan",
    76561198386265483: "donk",
}
```
**Apply to v2:** JSON shape per D-15 (3 top + 4 mid + 3 bottom):
```json
{
  "version": "v2-2026-05-12",
  "tier_quotas": {"top": 3, "mid": 4, "bottom": 3},
  "players": [
    {"steamid": 76561198386265483, "name": "donk", "tier": "top"},
    {"steamid": 76561197989430253, "name": "karrigan", "tier": "top"},
    ...
  ]
}
```
Loaded once via `json.loads(Path("evals/v2_eval_player_roster.json").read_text())`. Frozen — version-bump on change.

---

### `evals/interpretation_v2_ratings.csv` + `evals/v2_side_by_side.csv` (new — append+dedup CSVs)

**Analog:** `csv_utils.save_results()` (csv_utils.py:38-53) — replace-or-append-by-key pattern.

**Pattern** (csv_utils.py:38-53):
```python
def save_results(results_df: pd.DataFrame, filename: str, match_id: int | str) -> None:
    """
    Replace-or-append strategy:
    - All existing rows for `match_id` are removed (idempotent re-run).
    - New results are appended.
    - A single clean header is always written.
    """
    existing = load_existing_results(filename)
    if not existing.empty and "match_id" in existing.columns:
        existing = existing[existing["match_id"].astype(str) != str(match_id)]
        combined = pd.concat([existing, results_df], ignore_index=True)
    else:
        combined = results_df
    combined.to_csv(filename, index=False)
```
**Apply to v2:** New helper in `interpretation_narrative.py` (or thin `eval_csv_utils.py` if keeping module size in check):
```python
def save_rating(csv_path: str, row: dict, dedup_keys: tuple[str, ...]) -> None:
    """Replace-or-append by composite key. dedup_keys per D-19 = ('report_id', 'prompt_hash', 'dim')."""
    existing = pd.read_csv(csv_path) if Path(csv_path).exists() and Path(csv_path).stat().st_size > 0 else pd.DataFrame()
    if not existing.empty and all(k in existing.columns for k in dedup_keys):
        mask = pd.Series([True] * len(existing))
        for k in dedup_keys:
            mask &= existing[k].astype(str) == str(row[k])
        existing = existing[~mask]
    combined = pd.concat([existing, pd.DataFrame([row])], ignore_index=True)
    combined.to_csv(csv_path, index=False)
```
Schema for ratings (D-19): `report_id, player_steamid, prompt_hash, dim, score, notes, rated_at`.
Schema for side-by-side (D-20 + RESEARCH §Eval Harness lines 504-510 recommended extension): `pair_id, player_steamid, preferred_version, v1_rating, v2_rating, notes, rated_at`.

---

### `evals/README.md` (new — rubric + solo-rater limitation)

**Analog:** `.planning/PROJECT.md` (project-level docstring; markdown-with-headings convention).

**Apply to v2:** Sections per CONTEXT decisions:
- 5 rating dimensions definitions (D-17): factual_accuracy, actionability, tone, attribution, hallucinations (each 1-5 with anchor descriptions)
- SC-1 hard gate: ≥4.0 average + ≥3.5 per-dim floor
- D-16 solo-rater limitation note: "Single rater (Arystan). No inter-rater reliability for v2."
- D-18 re-rate workflow: full re-rate on `prompts/coaching_v2.md` content_hash change
- D-20 side-by-side protocol + bias mitigation (forced-choice column added per RESEARCH recommendation)

---

### `db_utils.py` MODIFIED — DB schema extension

**Analog:** Self — Phase 6 + Phase 10a worktree precedent (CONTEXT line 149 + RESEARCH §Schema Migration).

**`_ALLOWED_TABLES` extension pattern** (db_utils.py:14-15 + Phase 10a worktree precedent at db_utils.py:18 worktree):
```python
# CR-01: whitelist allowed table names to prevent SQL injection via f-string interpolation
_ALLOWED_TABLES = {"engagements", "duel_attempts"}
```
**Apply to v2:** `_ALLOWED_TABLES = {"engagements", "duel_attempts", "narrative_cache"}`. **Do NOT pull in Phase 10a's `"ddm_fits"`** — that branch is dead per memory (DDM dropped 2026-05-12 + branch not merging). Stay minimal (R-11 mitigation).

**CREATE TABLE pattern in `_migrate_schema`** (db_utils.py:96-113 — `duel_attempts` block is the closest analog for adding a new table):
```python
conn.execute("""
    CREATE TABLE IF NOT EXISTS duel_attempts (
        match_id TEXT,
        map_name TEXT,
        ...
    )
""")
```
**Apply to v2:** Add per RESEARCH §Schema Migration step 2:
```python
conn.execute("""
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
""")
```

**ALTER TABLE pattern for `round_number`** (db_utils.py:82-93):
```python
cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
_eng_migrations = [
    ("demo_name", "TEXT DEFAULT NULL"),
    ("player_steamid", "INTEGER DEFAULT NULL"),
    ("map_name", "TEXT DEFAULT NULL"),
    ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
    ("round_time_s", "REAL DEFAULT NULL"),
    ("round_phase", "TEXT DEFAULT NULL"),
]
for col, col_def in _eng_migrations:
    if col not in cols:
        conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
```
**Apply to v2:** Append `("round_number", "INTEGER DEFAULT NULL")` to `_eng_migrations`. Idempotent — re-runs are no-op for existing column.

---

### `ddm_analyzer.py` MODIFIED — emit `round_number` per engagement

**Analog:** Self — `_compute_round_phase()` (ddm_analyzer.py:591-612) already uses `bisect.bisect_right` on `round_start_ticks`.

**Existing pattern** (ddm_analyzer.py:591-612):
```python
def _compute_round_phase(
    self, t0_tick: int, round_start_ticks: Optional[List[int]], tag: str,
) -> Tuple[Optional[float], Optional[str]]:
    """Return (round_time_s, round_phase) for the given T0 tick."""
    if not round_start_ticks:
        return None, None
    idx = bisect.bisect_right(round_start_ticks, t0_tick) - 1
    if idx >= 0:
        ms_per_tick = 1000 / self.tickrate
        round_time_s = round((t0_tick - round_start_ticks[idx]) * ms_per_tick / 1000, 2)
        if round_time_s < _ROUND_EARLY_MAX_S:
            round_phase = "early"
        ...
        return round_time_s, round_phase
```
**Apply to v2:** Extend signature to `Tuple[Optional[float], Optional[str], Optional[int]]` — add `round_number = idx + 1` (1-indexed; warmup before first round_start = `None`). Single caller at line 683 must unpack new triple:
```python
# BEFORE:
round_time_s, round_phase = self._compute_round_phase(t0_tick, round_start_ticks, tag)
# AFTER:
round_time_s, round_phase, round_number = self._compute_round_phase(t0_tick, round_start_ticks, tag)
```
And add `"round_number": round_number,` to result dict (ddm_analyzer.py:727 — adjacent to existing `"round_phase": round_phase`).

**Hook awareness:** Editing `ddm_analyzer.py` triggers black + ruff + pytest auto-run (CLAUDE.md hook). All 322 existing tests must still pass; specifically `test_ddm_analyzer_*.py` test files mock `_compute_round_phase` return and need triple-unpack updates. Map every test invocation BEFORE editing.

---

### `report_generator.py` MODIFIED — narrative block insertion + fail-soft

**Analog:** Self — `generate_html_report()` (report_generator.py:595-665) + `_section()` helper (line 585).

**Existing composition pattern** (report_generator.py:611-665):
```python
def generate_html_report(
    player_steamid: int,
    benchmark_steamid: int,
    benchmark_name: str,
    db_path: str = DB_PATH,
) -> bytes:
    ...
    # ── Interpretation section ─────────────────────────────────────────────────
    interp_parts: list[str] = []
    interp_rows_by_type: dict[str, list[dict]] = {}
    for engagement_type in ["peek", "hold"]:
        ...
        rows = compute_interpretation(
            db_path=db_path, player_steamid=player_steamid,
            benchmark_steamid=benchmark_steamid, engagement_type=engagement_type,
        )
        interp_rows_by_type[engagement_type] = rows
        ...
    interp_content = "\n".join(interp_parts)
    interpretation_section = _section("Interpretation", interp_content)
    ...
    html = f"""<!DOCTYPE html>
    ...
    <h1>Djok Reaction Report</h1>
    <div class="sub-header">{player_steamid} vs {benchmark_name} · Generated {today}</div>
    {interpretation_section}
    {distributions_section}
    {raw_section}
    """
```
**Apply to v2:** Insert narrative block BETWEEN sub-header and `{interpretation_section}` (REQ-6 + CONTEXT line 162). Use `_section("Coach Narrative", narrative_html)` to keep visual consistency. Fail-soft pattern (REQ-10 + R-9 in RESEARCH):
```python
# ── Narrative section (v2 — fail-soft) ─────────────────────────────────────
narrative_section = ""
if not no_narrative:  # SC-6 v1 mode toggle (RESEARCH Open Q-6)
    try:
        from interpretation_narrative import build_narrative_report, fetch_top_moments, NarrativeBuildError
        # ... build top_moments + player_context, call build_narrative_report ...
        narrative_md = build_narrative_report(rows_combined, top_moments, player_context)
        narrative_html = _markdown_to_html(narrative_md)  # reuse existing pipeline
        narrative_section = _section("Coach Narrative", narrative_html)
    except NarrativeBuildError as e:
        # Expected fail-soft path — log and continue with tier table only.
        logger = get_logger(f"report.{player_steamid}")
        logger.warning(f"Narrative build failed (fail-soft): {e}")
    except Exception as e:
        # R-9: do NOT silently swallow unexpected exceptions in dev.
        if os.environ.get("DEV_FAIL_FAST") == "1":
            raise
        logger = get_logger(f"report.{player_steamid}")
        logger.error(f"Unexpected narrative error (fail-soft): {e!r}")

html = f"""...
{narrative_section}
{interpretation_section}
..."""
```
Add `no_narrative: bool = False` parameter to `generate_html_report()` for SC-6 v1 baseline generation.

---

### `config.py` MODIFIED — LLM env defaults + whitelist + PLAYER_NAMES expansion

**Analog:** Self — `PLAYER_NAMES` (line 172) + `T0_TO_T2_MAX_TICKS` (line 104, named-constant-with-comment pattern).

**Existing PLAYER_NAMES pattern** (config.py:169-175):
```python
# ─────────────────────────────────────────────────────────────────────────────
# Player display names (Phase 8 interpretation layer)
# ─────────────────────────────────────────────────────────────────────────────

PLAYER_NAMES: dict[int, str] = {
    76561197989430253: "karrigan",
    76561198386265483: "donk",
}
```
**Apply to v2:** Expand to ≥10 entries (R-1 mitigation — D-15 roster + benchmark players). Add new section header below:
```python
# ─────────────────────────────────────────────────────────────────────────────
# Phase v2 — LLM narrative coaching layer
# ─────────────────────────────────────────────────────────────────────────────

# LLM provider abstraction (REQ-3). Currently Anthropic-only; future-proof env hook.
LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "anthropic")

# Default model — claude-sonnet-4-6 per L-2 (quality/cost balance, $3/$15 MTok).
# Override via env `LLM_MODEL=claude-opus-4-7` for ~5× cost / higher quality.
LLM_MODEL: str = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

# Locked common-noun whitelist — D-06 hybrid validator allows these without
# attribution. Keep tight: every token here is a free-pass to the LLM.
NARRATIVE_COMMON_NOUNS_WHITELIST: frozenset[str] = frozenset({
    "peek", "hold", "aim", "crosshair", "pre-aim",
    "deathmatch", "DM", "VOD",
})
```
Note: `import os` already implicit via Python stdlib but currently missing at top of config.py — add explicit `import os` near `import logging` line 9.

## Shared Patterns

### Hook-driven format (cross-cutting on every `*.py` edit)

**Source:** `CLAUDE.md` "Claude Code Automations" + `.claude/` config
**Apply to:** Every `*.py` file in this phase (interpretation_narrative.py, scripts/backfill_round_number.py, db_utils.py, ddm_analyzer.py, report_generator.py, config.py, every test file)

**Constraint:** Edits trigger `black + ruff + pytest -p no:cov` automatically. Files MUST pass:
- `black .` formatting (88-col line length default)
- `ruff check .` linting
- `pytest -p no:cov -x` full suite (currently 322 tests; v2 adds ~100 new)

**Implication for planner:** Every plan task that edits `*.py` carries an implicit "hooks pass" success criterion. Adversarial changes (e.g. ddm_analyzer.py round_number triple-unpack) MUST grep all callers + test mocks BEFORE editing.

### SteamID64 truncation (cross-cutting on every DB read)

**Source:** `interpretation.py:179-185` (cursor.fetchall pattern) + `CLAUDE.md` Critical Gotchas + RESEARCH R-8
**Apply to:** `fetch_top_moments`, `_cache_get`, `_cache_put`, all `tests/test_top_moments_query.py` queries

```python
with closing(sqlite3.connect(db_path)) as conn:
    # Use cursor directly — pd.read_sql casts large int64 steamids to float64,
    # which loses precision on 17-digit SteamID64 values.
    cursor = conn.execute(
        "SELECT player_steamid, demo_name, t0_manual_tick, ... FROM engagements WHERE ...",
        (player_steamid, engagement_type),
    )
    rows = cursor.fetchall()
    return [
        {"player_steamid": int(r[0]), "demo_name": r[1], "t0_tick": int(r[2]), ...}
        for r in rows
    ]
```

**NEVER:** `pd.read_sql("SELECT player_steamid FROM ...", conn)` on any column with 17-digit SteamIDs.

### Idempotent SQLite migration (cross-cutting on `db_utils.py` + `scripts/backfill_round_number.py`)

**Source:** `db_utils.py:_migrate_schema()` (lines 72-93)
**Apply to:** v2 schema additions (narrative_cache CREATE, round_number ALTER) AND backfill script

**Pattern:**
- `CREATE TABLE IF NOT EXISTS` for new tables
- `PRAGMA table_info(...)` set check before `ALTER TABLE ADD COLUMN` for new columns
- `WHERE round_number IS NULL` filter for backfill — re-runs are no-op

### Error handling — fail-soft for narrative path

**Source:** RESEARCH §Error taxonomy + REQ-10
**Apply to:** `interpretation_narrative._call_llm`, `report_generator.generate_html_report` integration

**Pattern:**
- LLM/SDK errors → `NarrativeBuildError` (single custom exception)
- Caller wraps: `try: ... except NarrativeBuildError as e: log + fall back`
- `R-9 mitigation:` separate `except Exception` branch with `DEV_FAIL_FAST` env hook to re-raise in dev

### Strict typing + Optional + dataclass (cross-cutting Python style)

**Source:** `CLAUDE.md` "Code Style" + `config.py:AnalysisMoment` (line 143) + `interpretation.py` signatures
**Apply to:** ALL new public functions + helpers

```python
from typing import Optional
from dataclasses import dataclass

@dataclass
class NarrativeContext:
    player_steamid: int
    player_name: str
    engagement_type: str
    n_total_engagements: int
    rows: list[dict]
    top_moments: dict[str, list[dict]]
```

### Named constants — no magic numbers (cross-cutting `config.py` rule)

**Source:** `CLAUDE.md` "Code Style" + every constant in `config.py`
**Apply to:** PRICING dict, PROMPT_PATH, _MAX_TOKENS, _LLM_TEMPERATURE, _CACHE_TTL all hoisted to module level (NOT inline) with comment-justifications matching `T0_TO_T2_MAX_TICKS` style (config.py:97-104).

## No Analog Found

Files with no close match in the codebase (planner should use RESEARCH.md patterns instead):

| File | Role | Data Flow | Reason |
|-|-|-|-|
| `tests/fixtures/anthropic_recorded/*.json` | recorded LLM response fixtures | static asset | First recorded-API-response convention. Closest precedent = Phase 10a worktree `tests/fixtures/phase10a_regression_baseline.json` (frozen baseline JSON) but that's not in main yet. **Use RESEARCH §Testing Strategy lines 580-590 shape verbatim.** |
| `prompts/coaching_v2.md` | versioned RU prompt template | static asset | First versioned prompt. **Use RESEARCH §Anthropic SDK Integration §Prompt caching for static/dynamic split structure.** |

## Notes for Planner

1. **Phase 10a worktree isolation:** R-11 (RESEARCH) — `phase-10a-ddm-infra` branch has invasive `db_utils.py` changes (`busy_timeout=30000`, `@retry_on_locked` decorator, `ddm_fits` table). v2 is on `main` (or new branch off `main`). Do NOT cherry-pick 10a's db_utils edits. Keep v2 db_utils additions minimal: only `narrative_cache` + `round_number` ALTER + `"narrative_cache"` in `_ALLOWED_TABLES`.

2. **Round_number backfill is operator gate, not auto-runtime:** R-2 (RESEARCH) — 5557 rows × ~5 min/demo re-parse = ~6.5h overnight job. Plan must mark this as **operator-run, NOT CI**, and ensure `fetch_top_moments` query handles `WHERE round_number IS NOT NULL` gracefully (skip moments without attribution rather than crash).

3. **Test file conventions:** All new test files go in `tests/` flat (no subdirectories) — matches existing `tests/test_*.py` layout (verified `wc -l` on 9 existing test files, all flat). Test IDs follow `# vN-NN-NN` comments inline (per Phase 8 precedent in `test_interpretation.py`).

4. **`tests/conftest.py` extension:** Both `_no_real_anthropic` autouse fixture (RESEARCH lines 624-634) AND `FakeAnthropic`/`load_fixture` helpers go here, alongside existing `fake_parser` fixture (conftest.py:38-65). Keep conftest.py < 200 LOC for readability.

5. **`scripts/` directory does not exist yet** — verified via `ls`. Plan task 0 (Wave 0 baseline) MUST `mkdir scripts/` before writing `scripts/backfill_round_number.py`. Same for `evals/`, `prompts/`, `tests/fixtures/anthropic_recorded/`.

6. **CLAUDE.md update:** Memory entry references `# Codebase map` at `.planning/codebase/`. v2 adds first cloud API integration — `.planning/codebase/INTEGRATIONS.md` likely needs update post-ship to record Anthropic API as the first external integration. Out of scope for plan tasks but flag for `/gsd-verify-work` step.

## Metadata

**Analog search scope:**
- `D:/Obsidian/opacity/40_Projects/cs2-ddm/*.py` (top-level modules)
- `D:/Obsidian/opacity/40_Projects/cs2-ddm/tests/*.py` (existing test patterns)
- `D:/Obsidian/opacity/40_Projects/cs2-ddm/bench/` (CLI orchestrator precedent)
- `D:/Obsidian/opacity/40_Projects/cs2-ddm/.planning/codebase/` (architecture docs — referenced not re-read in this pass)

**Files scanned:** 17 source files (interpretation.py, db_utils.py, csv_utils.py, config.py, report_generator.py 580-665, ddm_analyzer.py 580-735, conftest.py, test_interpretation.py, test_csv_utils.py, test_db_utils.py + RESEARCH.md + CONTEXT.md + SPEC.md)

**Pattern extraction date:** 2026-05-12

## PATTERN MAPPING COMPLETE
