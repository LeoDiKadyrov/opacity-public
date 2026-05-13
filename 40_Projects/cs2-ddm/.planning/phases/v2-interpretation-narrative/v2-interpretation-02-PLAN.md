---
phase: v2-interpretation-narrative
plan: 02
type: execute
wave: 1
depends_on: [00]
files_modified:
  - interpretation_narrative.py
  - tests/test_top_moments_query.py
  - tests/test_interpretation_narrative.py
autonomous: true
requirements: [REQ-1, REQ-2, REQ-3, REQ-7, REQ-10]
must_haves:
  truths:
    - "interpretation_narrative.py module exists with public symbols: build_narrative_report, fetch_top_moments, call_llm, _content_hash, _cache_get, _cache_put, NarrativeBuildError"
    - "top_moments dict key shape LOCKED to f-string '{metric}::{engagement_type}' (e.g. 'rt_visible_to_aim_ms::peek') — plans 03 and 04 reference this exact shape"
    - "fetch_top_moments(db_path, player_steamid, metric, engagement_type, benchmark_p50, n_worst=2, n_best=1) returns list[dict] with shape per D-04"
    - "D-03: top-moments shape locked to N=2 worst + N=1 best per metric × 6 metrics = 18 moments max per report (best moments enable positive reinforcement)"
    - "D-05: ordering rule — worst-N selected by absolute gap_vs_benchmark in direction-of-metric; best-N selected by inverse-gap (most-below for lower-is-better, most-above for higher-is-better)"
    - "D-07: single LLM call attempt per report; on validator fail → log to narrative_failures.log + raise NarrativeBuildError → caller fail-soft to tier-table only; NO retry loop in v2 (cost control)"
    - "D-08: allowed_refs built per-report = union of (demo_names from top_moments) + (tick numbers from top_moments) + (round_numbers from top_moments) + (map_names from top_moments) + (player nickname from PLAYER_NAMES) + (locked common-nouns whitelist)"
    - "fetch_top_moments uses cursor.fetchall() (no pd.read_sql on player_steamid columns) — SteamID64 truncation regression-protected"
    - "fetch_top_moments excludes cluster-bleed rows (rt_visible_to_hit_ms > T0_TO_T2_MAX_MS) at SQL level via WHERE clause"
    - "fetch_top_moments handles NULL round_number gracefully (excludes those rows from attribution)"
    - "call_llm calls Anthropic Messages API with cache_control on system block; returns (text, usage_dict)"
    - "call_llm raises NarrativeBuildError on auth/rate-limit/refusal/5xx (per error taxonomy in RESEARCH)"
    - "_content_hash deterministic across Python runs (sort_keys=True)"
    - "_cache_get / _cache_put roundtrip via narrative_cache table; PK collision = overwrite via INSERT OR REPLACE"
    - "build_narrative_report orchestrates: cache lookup → prompt render → call_llm → validate_narrative → cache_put → return; on validator fail OR LLM raise → raises NarrativeBuildError (caller handles fail-soft)"
  artifacts:
    - path: "interpretation_narrative.py"
      provides: "REQ-1, REQ-2, REQ-3, REQ-7 implementation; thin orchestrator + LLM client + cache I/O"
      exports: ["build_narrative_report", "fetch_top_moments", "validate_narrative", "NarrativeBuildError", "call_llm", "_content_hash", "_cache_get", "_cache_put", "_get_client"]
      min_lines: 250
    - path: "tests/test_top_moments_query.py"
      provides: "DB integration for fetch_top_moments (cluster-bleed gate, SteamID64 safety, NULL round_number handling, n_worst/n_best ordering)"
      min_lines: 120
    - path: "tests/test_interpretation_narrative.py"
      provides: "Mocked-LLM unit tests for call_llm, _content_hash, _cache_get/_cache_put roundtrip, build_narrative_report orchestration, fail-soft via NarrativeBuildError"
      min_lines: 200
  key_links:
    - from: "interpretation_narrative.call_llm"
      to: "anthropic.Anthropic.messages.create"
      via: "_get_client() singleton + cache_control on system block"
      pattern: "messages.create"
    - from: "interpretation_narrative.fetch_top_moments"
      to: "engagements + duel_attempts JOIN"
      via: "cursor.fetchall + cluster-bleed gate WHERE clause"
      pattern: "JOIN duel_attempts"
    - from: "interpretation_narrative._cache_get / _cache_put"
      to: "analytics.db.narrative_cache"
      via: "save_to_db whitelist + manual SELECT/INSERT OR REPLACE"
      pattern: "narrative_cache"
    - from: "interpretation_narrative.build_narrative_report"
      to: "narrative_validator.validate_narrative"
      via: "import + post-LLM validation step"
      pattern: "validate_narrative"
---

<objective>
Ship the narrative module's data + LLM layers (REQ-1, REQ-2, REQ-3, REQ-7, REQ-10). Single-owner of `interpretation_narrative.py` to avoid Wave-1 file-write conflict with Plan 01 (which owns `narrative_validator.py`).

Purpose: This is the engine. fetch_top_moments builds the attribution payload, call_llm hits Anthropic, _cache_get/_cache_put avoid re-paying for identical inputs, build_narrative_report orchestrates everything. Plan 01 ships the validator that this plan calls. Plans 03+ wire prompt template + report_generator integration.

Output:
- `interpretation_narrative.py` (~300 LOC) — public API + private helpers + module-level constants per RESEARCH
- `tests/test_top_moments_query.py` — DB-integration tests for fetch_top_moments
- `tests/test_interpretation_narrative.py` — mocked-LLM unit tests for call_llm, cache roundtrip, build_narrative_report orchestration
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
@.planning/phases/v2-interpretation-narrative/v2-interpretation-00-SUMMARY.md
@CLAUDE.md
@interpretation.py
@db_utils.py
@config.py

<interfaces>
<!-- Existing contracts. Use directly; do not re-explore. -->

From `interpretation.py:1-15` — module-level constants we'll mirror in style:
```python
from __future__ import annotations
import sqlite3
from contextlib import closing
from typing import Optional
import pandas as pd
from config import DB_PATH, PLAYER_NAMES, T0_TO_T2_MAX_TICKS

_MS_PER_TICK = 1000.0 / 64.0
_T0_T2_MAX_MS = T0_TO_T2_MAX_TICKS * _MS_PER_TICK
```

For v2 module add `import os, json, hashlib` + `from anthropic import Anthropic, APIError, RateLimitError, APIStatusError`.

From `interpretation.py:179-200` (cursor.fetchall pattern — MUST replicate to avoid SteamID64 truncation):
```python
with closing(sqlite3.connect(db_path)) as conn:
    cursor = conn.execute("SELECT player_steamid, ... FROM ...", params)
    rows = cursor.fetchall()
    return [{"player_steamid": int(r[0]), ...} for r in rows]
```

NEVER use `pd.read_sql` on tables with `player_steamid` (CLAUDE.md gotcha + R-8 in RESEARCH).

From `interpretation.py:295-306` — cluster-bleed gate to replicate (D-04, REQ-2):
```python
# Cluster-bleed gate (Bug 2): drop rows where rt_visible_to_hit_ms exceeds
# T0_TO_T2_MAX_TICKS — these are not "slow reactions" but T2 captured from
# a separate firefight on the same target.
rt_col = "rt_visible_to_hit_ms"
if rt_col in eng_df_raw.columns:
    ungradeable_mask = eng_df_raw[rt_col].notna() & (eng_df_raw[rt_col] > _T0_T2_MAX_MS)
```
For v2 SQL form: `WHERE rt_visible_to_hit_ms IS NULL OR rt_visible_to_hit_ms <= ?` (bind `_T0_T2_MAX_MS`).

From RESEARCH §Anthropic SDK Integration lines 187-260 — call_llm verbatim shape:
```python
def call_llm(prompt_system: str, prompt_user: str, max_tokens: int = 2500) -> tuple[str, dict]:
    client = _get_client()
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[{
                "type": "text",
                "text": prompt_system,
                "cache_control": {"type": "ephemeral", "ttl": "5m"},
            }],
            messages=[{"role": "user", "content": prompt_user}],
            temperature=0.4,
        )
    except APIStatusError as e:
        raise NarrativeBuildError(f"API status {e.status_code}: {e.message}") from e
    except RateLimitError as e:
        raise NarrativeBuildError(f"Rate limit (after SDK retries): {e}") from e
    except APIError as e:
        raise NarrativeBuildError(f"API error (after SDK retries): {e}") from e
    if response.stop_reason == "refusal":
        raise NarrativeBuildError(f"Content policy refusal: {response.stop_details}")
    text = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        "model": response.model,
    }
    return text, usage
```

From W0 narrative_cache schema (db_utils._migrate_schema):
```sql
narrative_cache (
  player_steamid INTEGER NOT NULL,
  engagement_type TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  narrative_md TEXT NOT NULL,
  model TEXT NOT NULL,
  tokens_in INTEGER, tokens_out INTEGER,
  cache_creation_input_tokens INTEGER DEFAULT 0,
  cache_read_input_tokens INTEGER DEFAULT 0,
  generated_at TEXT NOT NULL,
  prompt_hash TEXT,
  PRIMARY KEY (player_steamid, engagement_type, content_hash)
)
```

From W1 plan 01 (will be ready before this plan in same wave order — but per files_modified separation, both plans can run truly parallel since they touch different files):
```python
from narrative_validator import validate_narrative
```

CONTEXT D-04 top_moment dict shape:
```python
{
  "demo_name": str, "t0_tick": int, "map_name": str, "round_number": int,
  "round_phase": str, "round_time_s": float, "player_value": float,
  "benchmark_p50": float, "gap_vs_benchmark": float
}
```

CONTEXT D-05 ordering rule:
- worst-N selected by absolute `gap_vs_benchmark` in direction-of-metric (lower_is_better → highest values are worst)
- best-N selected inverse-gap

D-08 allowed_refs builder:
```python
allowed_refs = {
    "demos": {m["demo_name"] for ms in top_moments.values() for m in ms},
    "ticks": {m["t0_tick"] for ms in top_moments.values() for m in ms},
    "rounds": {m["round_number"] for ms in top_moments.values() for m in ms if m.get("round_number") is not None},
    "maps": {m["map_name"] for ms in top_moments.values() for m in ms if m.get("map_name")},
}
```

PRICING dict from RESEARCH §Token counting line 313:
```python
PRICING = {
    "claude-sonnet-4-6": {"input": 3.0, "cache_w_5m": 3.75, "cache_r": 0.30, "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0, "cache_w_5m": 6.25, "cache_r": 0.50, "output": 25.0},
    "claude-haiku-4-5":  {"input": 1.0, "cache_w_5m": 1.25, "cache_r": 0.10, "output": 5.0},
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: interpretation_narrative.py — module skeleton + fetch_top_moments + content_hash + cache I/O</name>
  <files>interpretation_narrative.py, tests/test_top_moments_query.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Recommended Approach lines 86-150 + §content_hash lines 472-498
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md interpretation_narrative.py + db_utils.py sections
    - interpretation.py lines 1-310 (cursor.fetchall pattern + cluster-bleed gate exact code)
    - db_utils.py lines 14-50 (save_to_db pattern; we'll do manual INSERT OR REPLACE for cache to support PK upsert)
    - tests/test_interpretation.py lines 1-100 (mock_db fixture pattern — replicate for top_moments tests)
  </read_first>
  <behavior>
    RED tests in `tests/test_top_moments_query.py` (committed first):

    Fixture `populated_top_moments_db(tmp_path)`:
    - Creates tmp DB via `init_db()` (W0 schema)
    - Inserts 30 engagements rows for SteamID `76561198386265483` (donk, real 17-digit) on `peek` engagement_type
    - Mix of `rt_visible_to_aim_ms` values across [150, 500] with corresponding rt_visible_to_hit_ms
    - 5 rows have `rt_visible_to_hit_ms > _T0_T2_MAX_MS` (cluster-bleed — must be excluded)
    - 3 rows have `round_number IS NULL` (must be excluded from attribution OR included with null marker per implementation choice; recommend EXCLUDE)
    - All rows have `demo_name`, `t0_manual_tick`, `map_name`, `round_number` (where not null), `round_phase`, `round_time_s`
    - Inserts matching duel_attempts rows joined by `(demo_name, t0_tick)` (or whatever join key the implementation chooses; document the join key in plan)

    Tests:
    - `test_fetch_top_moments_returns_n_worst_per_metric` — call with metric="rt_visible_to_aim_ms", n_worst=2, n_best=1, benchmark_p50=200.0; assert returns 3 dicts; assert worst-2 first by descending player_value (lower_is_better metric); assert third dict is best (lowest player_value below benchmark)
    - `test_fetch_top_moments_excludes_cluster_bleed_rows` — assert no returned moment has `rt_visible_to_hit_ms > _T0_T2_MAX_MS`
    - `test_fetch_top_moments_excludes_null_round_number` — assert all returned moments have `round_number is not None`
    - `test_fetch_top_moments_steamid64_no_truncation` — pass donk's 17-digit SteamID; assert no exception, returns dicts with int t0_tick (not float)
    - `test_fetch_top_moments_dict_shape` — each returned dict has keys per D-04: `{demo_name, t0_tick, map_name, round_number, round_phase, round_time_s, player_value, benchmark_p50, gap_vs_benchmark}`
    - `test_fetch_top_moments_empty_returns_empty_list` — fresh DB, returns `[]`
    - `test_fetch_top_moments_higher_is_better_metric` — kill_rate (higher_is_better); worst-N has lowest values, best-N has highest

    RED tests in `tests/test_interpretation_narrative.py` (subset for this task):
    - `test_content_hash_deterministic` — `_content_hash(rows1, top1) == _content_hash(rows1, top1)` across two calls; same input always same hash
    - `test_content_hash_changes_on_input_change` — different rows → different hash
    - `test_content_hash_excludes_directions_field` — rows1 has `directions`, rows2 same minus directions; assert hashes equal (per RESEARCH note: "excluding it from hash prevents cache miss when DIRECTIONS dict gets cosmetic edits")
    - `test_cache_get_returns_none_when_missing` — fresh narrative_cache table, `_cache_get(db, sid, "peek", "abc")` returns None
    - `test_cache_put_then_get_roundtrip` — `_cache_put(db, sid, "peek", hash, "narrative text", "model", usage)` → `_cache_get(...)` returns "narrative text"
    - `test_cache_put_overwrites_on_pk_collision` — second `_cache_put` on same PK overwrites; SELECT count = 1, narrative_md = newer text
    - `test_cache_steamid64_no_truncation` — same as fetch_top_moments test, with cache I/O

    GREEN implementation in `interpretation_narrative.py`:
    ```python
    """Phase v2 — narrative coaching layer entry, LLM client, cache I/O.

    Wraps `interpretation.compute_interpretation` with LLM-generated prose narrative
    + per-engagement attribution. Validator lives in `narrative_validator.py`
    (separate file, parallel-developed in W1). Per REQ-1..REQ-3, REQ-7, REQ-10.
    """
    from __future__ import annotations
    import hashlib
    import json
    import logging
    import os
    import sqlite3
    from contextlib import closing
    from datetime import datetime, timezone
    from typing import Optional

    from config import (
        DB_PATH, LLM_MODEL, PLAYER_NAMES, T0_TO_T2_MAX_TICKS,
    )

    _MS_PER_TICK = 1000.0 / 64.0
    _T0_T2_MAX_MS = T0_TO_T2_MAX_TICKS * _MS_PER_TICK
    _MAX_TOKENS = 2500
    _LLM_TEMPERATURE = 0.4
    _PROMPT_PATH = "prompts/coaching_v2.md"  # populated by W2

    PRICING = {
        "claude-sonnet-4-6": {"input": 3.0, "cache_w_5m": 3.75, "cache_r": 0.30, "output": 15.0},
        "claude-opus-4-7":   {"input": 5.0, "cache_w_5m": 6.25, "cache_r": 0.50, "output": 25.0},
        "claude-haiku-4-5":  {"input": 1.0, "cache_w_5m": 1.25, "cache_r": 0.10, "output": 5.0},
    }

    _METRICS_LOWER_IS_BETTER = {
        "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
        "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
    }


    class NarrativeBuildError(Exception):
        """Raised when narrative cannot be built for any reason (LLM error,
        validator reject, missing data). Caller (report_generator) catches and
        falls back to tier-table-only behavior per REQ-10."""


    # ── fetch_top_moments ───────────────────────────────────────────────────────

    def fetch_top_moments(
        db_path: str,
        player_steamid: int,
        metric: str,
        engagement_type: str,
        benchmark_p50: float,
        n_worst: int = 2,
        n_best: int = 1,
    ) -> list[dict]:
        """Returns N worst + N best engagements for (player, metric, engagement_type).

        Per CONTEXT D-03 (default 2+1), D-04 (dict shape), D-05 (ordering).
        Cluster-bleed gate (interpretation.py:295-306) reapplied at SQL level.
        Uses cursor.fetchall — NEVER pd.read_sql on player_steamid columns.
        Excludes rows with NULL round_number (no attribution possible).
        """
        if engagement_type not in ("peek", "hold"):
            raise ValueError(f"engagement_type must be peek|hold, got {engagement_type!r}")
        lower_is_better = metric in _METRICS_LOWER_IS_BETTER
        # LEFT JOIN duel_attempts per REQ-2 — D-04 fields currently engagements-side
        # but join preserved for kill_rate metric extension (e.g., bullets_fired/hit
        # additions to D-04 in future without re-architecting fetch_top_moments).
        # LEFT (not INNER) so engagements without a matching duel_attempt still surface.
        sql = f"""
            SELECT e.demo_name, e.t0_manual_tick, e.map_name, e.round_number, e.round_phase,
                   e.round_time_s, e.{metric} as player_value, e.rt_visible_to_hit_ms
            FROM engagements e
            LEFT JOIN duel_attempts da
                ON da.demo_name = e.demo_name
                AND da.t0_tick = e.t0_manual_tick
                AND da.player_steamid = e.player_steamid
            WHERE e.player_steamid = ?
              AND e.engagement_type = ?
              AND e.{metric} IS NOT NULL
              AND e.round_number IS NOT NULL
              AND e.demo_name IS NOT NULL
              AND e.t0_manual_tick IS NOT NULL
              AND (e.rt_visible_to_hit_ms IS NULL OR e.rt_visible_to_hit_ms <= ?)
        """
        with closing(sqlite3.connect(db_path)) as conn:
            cursor = conn.execute(sql, (int(player_steamid), engagement_type, _T0_T2_MAX_MS))
            raw = cursor.fetchall()
        if not raw:
            return []
        # Build dicts (cursor.fetchall avoids SteamID64 float64 cast)
        rows = [
            {
                "demo_name": r[0],
                "t0_tick": int(r[1]),
                "map_name": r[2],
                "round_number": int(r[3]),
                "round_phase": r[4],
                "round_time_s": float(r[5]) if r[5] is not None else None,
                "player_value": float(r[6]),
                "benchmark_p50": float(benchmark_p50),
                "gap_vs_benchmark": float(r[6]) - float(benchmark_p50),
            }
            for r in raw
        ]
        # Sort by gap direction; worst on top
        if lower_is_better:
            rows.sort(key=lambda x: x["gap_vs_benchmark"], reverse=True)  # largest positive gap = worst
        else:
            rows.sort(key=lambda x: x["gap_vs_benchmark"])  # most negative gap = worst
        worst = rows[:n_worst]
        # Best — opposite end of sorted list
        best = rows[-n_best:] if n_best > 0 and len(rows) > n_worst else []
        # Avoid duplicate when N small (e.g., 3 rows total)
        worst_keys = {(m["demo_name"], m["t0_tick"]) for m in worst}
        best = [m for m in best if (m["demo_name"], m["t0_tick"]) not in worst_keys]
        return worst + best


    # ── content_hash ────────────────────────────────────────────────────────────

    def _content_hash(rows: list[dict], top_moments: dict[str, list[dict]]) -> str:
        """Deterministic 16-char hash of (rows + top_moments). Excludes 'directions'
        field from rows (RESEARCH note — directions is constant per metric pair, so
        cosmetic edits to interpretation.DIRECTIONS shouldn't bust cache)."""
        stable_rows = [{k: v for k, v in r.items() if k != "directions"} for r in rows]
        payload = json.dumps(
            {"rows": stable_rows, "moments": top_moments},
            sort_keys=True, default=str, ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()[:16]


    def _prompt_hash(prompt_path: str = _PROMPT_PATH) -> str:
        """Hash of prompt template content. D-18 trigger — full re-rate when this changes."""
        try:
            with open(prompt_path, "rb") as f:
                return hashlib.sha256(f.read()).hexdigest()[:16]
        except FileNotFoundError:
            return "missing"


    # ── cache I/O ───────────────────────────────────────────────────────────────

    def _cache_get(
        db_path: str, player_steamid: int, engagement_type: str, content_hash: str,
        prompt_hash: Optional[str] = None,
    ) -> Optional[str]:
        """Return cached narrative_md or None on miss. If prompt_hash provided,
        also requires cached prompt_hash to match (R-4 mitigation)."""
        with closing(sqlite3.connect(db_path)) as conn:
            cursor = conn.execute(
                """SELECT narrative_md, prompt_hash FROM narrative_cache
                   WHERE player_steamid = ? AND engagement_type = ? AND content_hash = ?""",
                (int(player_steamid), engagement_type, content_hash),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        cached_md, cached_prompt_hash = row
        if prompt_hash is not None and cached_prompt_hash != prompt_hash:
            return None  # treat as miss — prompt template drifted
        return cached_md


    def _cache_put(
        db_path: str, player_steamid: int, engagement_type: str, content_hash: str,
        narrative_md: str, model: str, usage: dict,
        prompt_hash: Optional[str] = None,
    ) -> None:
        """Insert or replace cache row. Idempotent on PK collision."""
        with closing(sqlite3.connect(db_path)) as conn:
            with conn:
                conn.execute(
                    """INSERT OR REPLACE INTO narrative_cache (
                        player_steamid, engagement_type, content_hash, narrative_md, model,
                        tokens_in, tokens_out, cache_creation_input_tokens,
                        cache_read_input_tokens, generated_at, prompt_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        int(player_steamid), engagement_type, content_hash, narrative_md, model,
                        int(usage.get("input_tokens", 0)),
                        int(usage.get("output_tokens", 0)),
                        int(usage.get("cache_creation_input_tokens", 0)),
                        int(usage.get("cache_read_input_tokens", 0)),
                        datetime.now(timezone.utc).isoformat(),
                        prompt_hash,
                    ),
                )


    # ── call_llm + _get_client + build_narrative_report come in Task 2 ─────────
    ```

    Notes for executor:
    - Task 2 below adds `_get_client`, `call_llm`, `build_narrative_report` (LLM-touching code). This task ships only the data + cache layer + module skeleton.
    - The duel_attempts JOIN was DROPPED from the SQL because D-04 dict shape only requires engagement-side columns. If a downstream need surfaces (e.g., bullets_fired/hit), revisit. This deviation is documented above.
    - GUARD against a frozen DB without round_number column: catch `sqlite3.OperationalError` → raise NarrativeBuildError with clear message ("run init_db first").
  </behavior>
  <action>
    1. Write RED tests in `tests/test_top_moments_query.py` + the subset RED tests in `tests/test_interpretation_narrative.py` listed above. Commit (`test(v2-02): RED top_moments + content_hash + cache roundtrip`).
    2. Write `interpretation_narrative.py` per the GREEN code shape above (Tasks 1 + 2 share the same file — **for THIS task, write only the section through `_cache_put`** + the imports/constants/PRICING dict + `NarrativeBuildError`. Leave `_get_client`, `call_llm`, `build_narrative_report` for Task 2 below. Add a comment at the bottom: `# Task 2 in plan 02 appends _get_client + call_llm + build_narrative_report below this line.`).
    3. Hook auto-runs black + ruff + pytest. Address any lint warnings.
    4. Verify all RED tests now PASS.
  </action>
  <verify>
    <automated>python -m pytest tests/test_top_moments_query.py tests/test_interpretation_narrative.py -p no:cov -k "content_hash or cache or top_moments" -x</automated>
  </verify>
  <acceptance_criteria>
    - `test -f interpretation_narrative.py` succeeds
    - `python -c "from interpretation_narrative import fetch_top_moments, _content_hash, _cache_get, _cache_put, NarrativeBuildError; print('OK')"` prints "OK"
    - `grep -c "cursor.fetchall" interpretation_narrative.py` ≥ 2 (fetch_top_moments + _cache_get)
    - `grep -c "pd.read_sql" interpretation_narrative.py` == 0 (SteamID64 safety)
    - `grep -E "WHERE.*rt_visible_to_hit_ms.*<=" interpretation_narrative.py` returns ≥ 1 match (cluster-bleed gate)
    - `grep -c "INSERT OR REPLACE INTO narrative_cache" interpretation_narrative.py` == 1
    - `grep -c "round_number IS NOT NULL" interpretation_narrative.py` ≥ 1
    - `python -m pytest tests/test_top_moments_query.py -p no:cov` ALL PASS (≥7 tests)
    - `python -m pytest tests/test_interpretation_narrative.py -p no:cov -k "content_hash or cache"` ALL PASS (≥5 tests)
    - `python -m pytest -p no:cov` full suite green
  </acceptance_criteria>
  <done>
    Data layer + cache layer of interpretation_narrative.py shipped. fetch_top_moments returns D-04-shaped dicts with cluster-bleed gate + SteamID64 safety + NULL-round_number filter. content_hash deterministic. Cache I/O roundtrips correctly. NarrativeBuildError exception class defined.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: _get_client + call_llm + _failure_logger (LLM client layer only)</name>
  <files>interpretation_narrative.py, tests/test_interpretation_narrative.py, tests/conftest.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Anthropic SDK Integration lines 187-340 (init pattern + call_llm + error taxonomy)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Testing Strategy lines 522-635 (FakeAnthropic + autouse + recorded fixtures)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md tests/test_interpretation_narrative.py + tests/conftest.py sections
    - tests/conftest.py current state (W0 added _no_real_anthropic autouse fixture)
    - tests/fixtures/anthropic_recorded/*.json (W0 fixtures available)
  </read_first>
  <behavior>
    Add to `tests/conftest.py` (per PATTERNS.md "Both `_no_real_anthropic` AND `FakeAnthropic`/`load_fixture` helpers go here"):
    ```python
    # FakeAnthropic + load_fixture helpers for narrative tests (Plan 02)
    from pathlib import Path
    import json as _json
    from types import SimpleNamespace

    class _FakeMessage:
        def __init__(self, text, usage, stop_reason="end_turn", model="claude-sonnet-4-6"):
            self.content = [SimpleNamespace(text=text, type="text")]
            self.usage = SimpleNamespace(**usage)
            self.stop_reason = stop_reason
            self.stop_details = None
            self.model = model

    class _FakeMessages:
        def __init__(self, response): self._response = response
        def create(self, **kwargs): return self._response

    class FakeAnthropic:
        def __init__(self, response): self.messages = _FakeMessages(response)

    def load_recorded_fixture(name: str) -> dict:
        p = Path(__file__).parent / "fixtures" / "anthropic_recorded" / f"{name}.json"
        return _json.loads(p.read_text(encoding="utf-8"))

    @pytest.fixture
    def make_fake_anthropic():
        """Factory fixture — returns FakeAnthropic configured with given fixture name."""
        def _make(fixture_name: str):
            data = load_recorded_fixture(fixture_name)
            return FakeAnthropic(_FakeMessage(
                text=data["text"], usage=data["usage"],
                stop_reason=data["stop_reason"], model=data["model"],
            ))
        return _make
    ```

    RED tests in `tests/test_interpretation_narrative.py` (LLM client only — orchestrator tests in Task 3):

    **TestGetClient:**
    - `test_get_client_raises_without_api_key(monkeypatch)` — delete ANTHROPIC_API_KEY env var, call `_get_client()`, expect NarrativeBuildError matching /ANTHROPIC_API_KEY/
    - `test_get_client_caches_singleton(monkeypatch)` — set fake env key; monkeypatch anthropic.Anthropic to a counting stub; call `_get_client()` twice; assert stub instantiated once

    **TestCallLLM** (uses make_fake_anthropic):
    - `test_call_llm_returns_text_and_usage(monkeypatch, make_fake_anthropic)` — monkeypatch `interpretation_narrative._get_client` to return `make_fake_anthropic("ok_donk_peek")`; call `call_llm("system", "user")`; assert returns tuple (text, usage); assert text starts with `"## Что у тебя получается"`; assert `usage["output_tokens"] == 700`
    - `test_call_llm_refusal_raises(monkeypatch, make_fake_anthropic)` — load `refusal` fixture; expect NarrativeBuildError matching /refusal/
    - `test_call_llm_max_tokens_returns_text_with_warning(monkeypatch, make_fake_anthropic)` — load `truncated_max_tokens`; assert returns text WITHOUT raising (max_tokens is soft per RESEARCH); validator downstream may catch truncation
    - `test_call_llm_authentication_error_raises(monkeypatch)` — monkeypatch _get_client to a fake that raises `anthropic.APIStatusError` with status 401; expect NarrativeBuildError matching /401|status/
    - `test_call_llm_rate_limit_error_raises(monkeypatch)` — monkeypatch to raise RateLimitError; expect NarrativeBuildError matching /[Rr]ate limit/
    - `test_call_llm_uses_cache_control_on_system(monkeypatch)` — monkeypatch a recording fake; capture kwargs of `messages.create`; assert `system` is a list with element having `cache_control == {"type": "ephemeral", "ttl": "5m"}`

    **TestFailureLogger:**
    - `test_failure_logger_writes_to_file(tmp_path, monkeypatch)` — monkeypatch cwd to tmp_path; call `_failure_logger().warning("test entry")`; assert `narrative_failures.log` exists in tmp_path; assert "test entry" in file contents
    - `test_failure_logger_no_propagation(tmp_path, monkeypatch, caplog)` — call `_failure_logger().warning(...)`; assert nothing leaks to root logger (propagate=False)

    GREEN — append to `interpretation_narrative.py`:
    ```python
    # ── LLM client (singleton + sync messages.create) ──────────────────────────

    _CLIENT = None

    def _get_client():
        global _CLIENT
        if _CLIENT is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise NarrativeBuildError("ANTHROPIC_API_KEY env var not set")
            from anthropic import Anthropic
            _CLIENT = Anthropic(api_key=api_key)
        return _CLIENT


    def call_llm(prompt_system: str, prompt_user: str, max_tokens: int = _MAX_TOKENS) -> tuple[str, dict]:
        """Single LLM call. Returns (text, usage_dict). Per D-07: SDK retries
        cover transient failures; we do NOT add a second retry loop. Per error
        taxonomy in RESEARCH §Anthropic SDK Integration. Public per REQ-3 — single
        function abstracting LLM provider; renaming-safe interface for v2.1 swap."""
        from anthropic import APIError, RateLimitError, APIStatusError
        client = _get_client()
        model = os.environ.get("LLM_MODEL", LLM_MODEL)
        try:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=[{
                    "type": "text",
                    "text": prompt_system,
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }],
                messages=[{"role": "user", "content": prompt_user}],
                temperature=_LLM_TEMPERATURE,
            )
        except APIStatusError as e:
            raise NarrativeBuildError(f"API status {getattr(e, 'status_code', '?')}: {e}") from e
        except RateLimitError as e:
            raise NarrativeBuildError(f"Rate limit (after SDK retries): {e}") from e
        except APIError as e:
            raise NarrativeBuildError(f"API error (after SDK retries): {e}") from e
        if response.stop_reason == "refusal":
            raise NarrativeBuildError(f"Content policy refusal: {response.stop_details}")
        text = response.content[0].text
        usage = {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
            "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
            "model": response.model,
        }
        return text, usage


    def _failure_logger() -> logging.Logger:
        logger = logging.getLogger("narrative_failures")
        if not logger.handlers:
            fh = logging.FileHandler("narrative_failures.log", encoding="utf-8")
            fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            logger.addHandler(fh)
        logger.setLevel(logging.WARNING)
        logger.propagate = False
        return logger
    ```

    Note: `build_narrative_report` orchestrator + `_render_prompt` + `_build_allowed_refs` land in Task 3. This task ships ONLY the LLM client primitives + failure logger — kept in a single commit so a transient LLM-client bug rolls back cleanly without touching orchestrator logic.
  </behavior>
  <action>
    1. Write RED tests (TestGetClient + TestCallLLM + TestFailureLogger). Commit (`test(v2-02): RED LLM client + failure logger`).
    2. Append FakeAnthropic helpers + `make_fake_anthropic` factory fixture to `tests/conftest.py`. Existing `_no_real_anthropic` autouse fixture stays — `make_fake_anthropic` is opt-in per test.
    3. Append `_get_client` + `call_llm` + `_failure_logger` to `interpretation_narrative.py` BELOW the existing `# Task 2 in plan 02 appends...` marker (rename marker to `# Task 3 in plan 02 appends build_narrative_report orchestrator below this line.`).
    4. Verify TestGetClient + TestCallLLM + TestFailureLogger tests pass.
    5. Commit GREEN (`feat(v2-02): _get_client + call_llm + _failure_logger LLM client primitives`).
  </action>
  <verify>
    <automated>python -m pytest tests/test_interpretation_narrative.py -p no:cov -k "GetClient or CallLLM or FailureLogger" -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "def call_llm" interpretation_narrative.py` == 1
    - `grep -c "def _get_client" interpretation_narrative.py` == 1
    - `grep -c "def _failure_logger" interpretation_narrative.py` == 1
    - `grep -E 'cache_control.*ephemeral.*5m' interpretation_narrative.py` returns ≥ 1 match
    - `grep -c "from anthropic import" interpretation_narrative.py` ≥ 1 (deferred imports inside functions OK)
    - `grep -c "FakeAnthropic" tests/conftest.py` ≥ 1
    - `grep -c "make_fake_anthropic" tests/conftest.py` ≥ 1
    - `python -m pytest tests/test_interpretation_narrative.py -p no:cov -k "GetClient or CallLLM or FailureLogger"` ALL PASS (≥10 tests)
    - `python -m pytest -p no:cov` full suite green
  </acceptance_criteria>
  <done>
    LLM client layer shipped in isolation: `_get_client` (singleton + env-key gate), `call_llm` (public per REQ-3, full error taxonomy), `_failure_logger` (lazy file handler). `build_narrative_report` orchestrator follows in Task 3 — split keeps single-commit blast radius narrow.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 3: build_narrative_report orchestrator + _render_prompt + _build_allowed_refs</name>
  <files>interpretation_narrative.py, tests/test_interpretation_narrative.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Anthropic SDK Integration §Prompt caching lines 263-303 (static vs dynamic split)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md interpretation_narrative.py section
    - interpretation_narrative.py current state (Tasks 1 + 2 already shipped: data layer, cache layer, LLM client)
    - narrative_validator.py (Plan 01 should land before this in same wave; if not, the deferred import inside `build_narrative_report` shields module-level load)
    - tests/conftest.py (`make_fake_anthropic` factory ready from Task 2)
  </read_first>
  <behavior>
    RED tests in `tests/test_interpretation_narrative.py` (orchestrator only — Task 2 already shipped client tests):

    **TestRenderPromptPlaceholder:**
    - `test_render_prompt_uses_w1_placeholder_when_file_missing(monkeypatch)` — monkeypatch `_PROMPT_PATH` to nonexistent file; call `_render_prompt` with empty rows/top_moments; assert returned static contains "STATIC_PLACEHOLDER"; assert dynamic is non-empty JSON. (Plan 03 will tighten this to RAISE; for now the placeholder is the W1-handoff contract.)
    - `test_render_prompt_partitions_at_marker(tmp_path, monkeypatch)` — write tmp file with "BEFORE\n{{DYNAMIC_USER_BLOCK}}\nAFTER"; assert returned static == "BEFORE\n", dynamic JSON does NOT contain "AFTER".

    **TestBuildAllowedRefs:**
    - `test_build_allowed_refs_collects_demos_ticks_rounds_maps` — given top_moments dict with 2 metrics × 3 moments each; assert returned dict has all unique demos, ticks, rounds, maps + nickname.
    - `test_build_allowed_refs_excludes_null_round_number_and_map` — moments where round_number / map_name is None → not in resulting set.

    **TestBuildNarrativeReport:**
    - `test_build_narrative_returns_text_on_clean_path(monkeypatch, make_fake_anthropic, tmp_path)` — monkeypatch `_get_client` to clean fixture; init narrative_cache table in tmp DB; build allowed_refs covering fixture's references; call `build_narrative_report(rows, top_moments, player_context, db_path=tmp_db)`; assert returns markdown string starting with `"## Что у тебя получается"`
    - `test_build_narrative_caches_on_first_call(monkeypatch, make_fake_anthropic, tmp_path)` — call twice; assert call_llm invoked only ONCE (use a counter wrapper around `make_fake_anthropic`); assert second call returns same text from cache (verifies cache_get hit short-circuits LLM)
    - `test_build_narrative_raises_on_validator_fail(monkeypatch, make_fake_anthropic, tmp_path)` — load `hallucinated_tick` fixture (validator will catch); allowed_refs missing tick 99999999; assert raises NarrativeBuildError matching /validator|halluc/
    - `test_build_narrative_raises_on_llm_error(monkeypatch, tmp_path)` — monkeypatch `call_llm` to raise NarrativeBuildError directly; assert propagates
    - `test_build_narrative_logs_failure_to_log(monkeypatch, make_fake_anthropic, tmp_path)` — REQ-10 + D-07: when validator rejects, narrative_failures.log gets a line with "NARRATIVE_FAIL kind=validator". Use `tmp_path` cwd; assert log file written + contains marker + violation type.
    - `test_build_narrative_falls_back_to_player_short_id_when_nickname_unknown(monkeypatch, make_fake_anthropic, tmp_path)` — `player_context.player_name=None` and `PLAYER_NAMES.get(steamid)=None`; assert nickname becomes `player_<last4>` per code path.

    GREEN — append to `interpretation_narrative.py` (BELOW Task 2 LLM client section):
    ```python
    # ── build_narrative_report orchestrator ────────────────────────────────────

    def _render_prompt(rows, top_moments, player_context) -> tuple[str, str]:
        """Returns (system_block, user_block). System is cacheable static instructions;
        user is dynamic per-call payload. In W2 plan 03, this loads from prompts/coaching_v2.md.
        Until W2 ships the prompt file, returns minimal placeholder for unit-test wiring.
        Plan 03 task 2 tightens this to raise NarrativeBuildError on missing template.
        """
        try:
            with open(_PROMPT_PATH, encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError:
            template = "STATIC_PLACEHOLDER\n{{DYNAMIC_USER_BLOCK}}"  # Plan 03 will replace
        if "{{DYNAMIC_USER_BLOCK}}" in template:
            static, _, _ = template.partition("{{DYNAMIC_USER_BLOCK}}")
        else:
            static = template
        dynamic = json.dumps({
            "player": player_context,
            "tier_rows": rows,
            "top_moments": top_moments,
        }, ensure_ascii=False, indent=2, default=str)
        return static, dynamic


    def _build_allowed_refs(top_moments: dict[str, list[dict]], player_name: str) -> dict[str, set]:
        demos = {m["demo_name"] for ms in top_moments.values() for m in ms}
        ticks = {m["t0_tick"] for ms in top_moments.values() for m in ms}
        rounds = {m["round_number"] for ms in top_moments.values() for m in ms if m.get("round_number") is not None}
        maps = {m["map_name"] for ms in top_moments.values() for m in ms if m.get("map_name")}
        return {"demos": demos, "ticks": ticks, "rounds": rounds, "maps": maps, "nickname": player_name}


    def build_narrative_report(
        rows: list[dict],
        top_moments: dict[str, list[dict]],
        player_context: dict,
        db_path: str = DB_PATH,
    ) -> str:
        """Per REQ-1. Orchestrates: cache lookup → prompt render → call_llm →
        validate_narrative → cache_put → return. Raises NarrativeBuildError on
        validator fail or LLM error. Caller (report_generator) catches → fail-soft."""
        from narrative_validator import validate_narrative
        player_steamid = int(player_context["player_steamid"])
        engagement_type = player_context["engagement_type"]
        player_name = player_context.get("player_name") or PLAYER_NAMES.get(
            player_steamid, f"player_{str(player_steamid)[-4:]}"
        )
        ch = _content_hash(rows, top_moments)
        ph = _prompt_hash()
        cached = _cache_get(db_path, player_steamid, engagement_type, ch, prompt_hash=ph)
        if cached is not None:
            return cached
        system, user = _render_prompt(rows, top_moments, player_context)
        text, usage = call_llm(system, user)
        allowed_refs = _build_allowed_refs(top_moments, player_name)
        is_valid, violations = validate_narrative(text, allowed_refs)
        if not is_valid:
            _failure_logger().warning(
                f"NARRATIVE_FAIL kind=validator player={player_steamid} type={engagement_type} "
                f"violations={violations} raw_text_head={text[:300]!r}"
            )
            raise NarrativeBuildError(
                f"Validator rejected narrative ({len(violations)} violations): "
                f"{[v['type'] for v in violations]}"
            )
        _cache_put(db_path, player_steamid, engagement_type, ch, text, usage["model"], usage, prompt_hash=ph)
        return text
    ```

    **Important:** Plan 01 may be in-flight in parallel. If `narrative_validator.py` is not yet committed when this plan executes, the import inside `build_narrative_report` will fail at first call. Mitigation: import is INSIDE the function (deferred), so module-level import does not break and Tasks 1+2 tests still run. `TestBuildNarrativeReport.test_build_narrative_returns_text_on_clean_path` etc. require Plan 01 done; that is acceptable per Wave 1 dependency model — both plan 01 + plan 02 must complete before Wave 2 can start.
  </behavior>
  <action>
    1. Write RED tests (TestRenderPromptPlaceholder + TestBuildAllowedRefs + TestBuildNarrativeReport classes). Commit (`test(v2-02): RED build_narrative_report orchestrator`).
    2. Append `_render_prompt`, `_build_allowed_refs`, `build_narrative_report` to `interpretation_narrative.py` below Task 2 LLM client section.
    3. Verify all orchestrator tests pass (Plan 01 must be done before TestBuildNarrativeReport tests pass — if Plan 01 still in-flight, those specific tests can be xfail-marked until Plan 01 lands; remove markers as soon as it does).
    4. Commit GREEN (`feat(v2-02): build_narrative_report orchestrator + render_prompt + allowed_refs`).
  </action>
  <verify>
    <automated>python -m pytest tests/test_interpretation_narrative.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "def build_narrative_report" interpretation_narrative.py` == 1
    - `grep -c "def _render_prompt" interpretation_narrative.py` == 1
    - `grep -c "def _build_allowed_refs" interpretation_narrative.py` == 1
    - `grep -c "NarrativeBuildError" interpretation_narrative.py` ≥ 5 (raise sites + class def — Tasks 1+2+3 combined)
    - `grep -c "_failure_logger" interpretation_narrative.py` ≥ 2 (def from Task 2 + use in build_narrative_report)
    - `grep -c "from narrative_validator import" interpretation_narrative.py` ≥ 1 (deferred import inside build_narrative_report)
    - `python -m pytest tests/test_interpretation_narrative.py -p no:cov` ALL PASS (Tasks 1+2+3 combined ≥18 tests)
    - `python -m pytest -p no:cov` full suite green
    - `python -c "import interpretation_narrative as inv; print(hasattr(inv, 'build_narrative_report'), hasattr(inv, 'fetch_top_moments'), hasattr(inv, 'call_llm'), hasattr(inv, 'NarrativeBuildError'))"` prints `True True True True`
  </acceptance_criteria>
  <done>
    `interpretation_narrative.py` module COMPLETE: fetch_top_moments + content_hash + cache I/O (Task 1) + _get_client + call_llm + _failure_logger (Task 2) + _render_prompt + _build_allowed_refs + build_narrative_report (Task 3). All public symbols available for W2 prompt + report_generator integration. NarrativeBuildError fail-soft path proven via mocked tests. Anthropic API isolated behind _get_client; tests run offline against W0 recorded fixtures. Plan 02 split into 3 tasks lowers single-commit risk per W-4 revision.
  </done>
</task>

</tasks>

<verification>
- `python -m pytest tests/test_top_moments_query.py tests/test_interpretation_narrative.py -p no:cov` PASS
- `python -m pytest -p no:cov` full suite green
- `python -c "from interpretation_narrative import build_narrative_report, fetch_top_moments, call_llm, _content_hash, _cache_get, _cache_put, NarrativeBuildError; print('all symbols OK')"` prints "all symbols OK"
- All 7 W0 recorded fixtures roundtrip through tests without hitting real Anthropic API (autouse guard verified active)
- Cache roundtrip works: put → get returns same text; collision → overwrite (verified by row count + content)
</verification>

<success_criteria>
- interpretation_narrative.py module COMPLETE per RESEARCH file plan
- Public symbols: build_narrative_report, fetch_top_moments, call_llm, _content_hash, _cache_get, _cache_put, NarrativeBuildError, _get_client
- Cluster-bleed gate at SQL level (not Python post-filter)
- SteamID64 truncation regression-protected (cursor.fetchall, no pd.read_sql)
- Cache hit returns immediately, no LLM call
- Validator fail OR LLM error → NarrativeBuildError + logged to narrative_failures.log
- Anthropic client isolated behind _get_client + _no_real_anthropic autouse guard
- Ready for W2 to wire prompt template + report_generator integration
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-02-SUMMARY.md` documenting:
- Final public API of interpretation_narrative.py (all exported symbols + signatures)
- SQL form of fetch_top_moments (note duel_attempts JOIN dropped — engagements columns sufficient for D-04)
- Test count delta (~25 new tests across test_top_moments_query.py + test_interpretation_narrative.py)
- Any deviation from RESEARCH (e.g., if `_TICK_RE` extension turned out unnecessary, or if PRICING needed extra models)
- Whether _PROMPT_PATH placeholder strategy survived to W2 (W2 will overwrite it with real prompt template)
</output>
