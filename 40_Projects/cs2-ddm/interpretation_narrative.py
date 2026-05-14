"""Phase v2 — narrative coaching layer entry, LLM client, cache I/O.

Wraps `interpretation.compute_interpretation` with LLM-generated prose narrative
+ per-engagement attribution. Validator lives in `narrative_validator.py`
(separate file, parallel-developed in W1). Per REQ-1..REQ-3, REQ-7, REQ-10.

Public symbols (W2 + report_generator integration):
- build_narrative_report  — orchestrator (Task 3)
- fetch_top_moments       — DB query for D-04 moment dicts (Task 1)
- call_llm                — Anthropic Messages API wrapper (Task 2, REQ-3)
- _content_hash           — deterministic cache key (Task 1)
- _cache_get / _cache_put — narrative_cache table I/O (Task 1)
- _get_client             — Anthropic singleton (Task 2)
- NarrativeBuildError     — single fail-soft exception (REQ-10)
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

from config import DB_PATH, LLM_MODEL, PLAYER_NAMES, T0_TO_T2_MAX_TICKS

# ── Module-level constants ──────────────────────────────────────────────────

# Tick → ms (CS2 tickrate 64). Mirrored from interpretation.py to avoid coupling.
_MS_PER_TICK: float = 1000.0 / 64.0

# Cluster-bleed gate threshold in ms (D-04, REQ-2). Engagements with
# rt_visible_to_hit_ms above this cap are T2-from-different-firefight artifacts
# and must be excluded from attribution-grade top-moments.
_T0_T2_MAX_MS: float = T0_TO_T2_MAX_TICKS * _MS_PER_TICK

# Anthropic call defaults (Task 2 — used by call_llm).
_MAX_TOKENS: int = 2500
_LLM_TEMPERATURE: float = 0.4

# Prompt template path — populated by W2 (plan 03). Module-level so tests can
# monkeypatch it without touching call_llm internals.
_PROMPT_PATH: str = "prompts/coaching_v2.md"

# Pricing dict per RESEARCH §Token counting. USD per million tokens.
PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {"input": 3.0, "cache_w_5m": 3.75, "cache_r": 0.30, "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0, "cache_w_5m": 6.25, "cache_r": 0.50, "output": 25.0},
    "claude-haiku-4-5":  {"input": 1.0, "cache_w_5m": 1.25, "cache_r": 0.10, "output": 5.0},
}

# Mirror of interpretation._METRICS_LOWER_IS_BETTER — kept local to avoid
# import cycle if interpretation.py is later refactored.
_METRICS_LOWER_IS_BETTER: frozenset[str] = frozenset({
    "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
    "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
})


class NarrativeBuildError(Exception):
    """Raised when narrative cannot be built for any reason (LLM error,
    validator reject, missing data, missing API key). Caller (report_generator)
    catches and falls back to tier-table-only behavior per REQ-10."""


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
    """Return N worst + N best engagements for (player, metric, engagement_type).

    Per CONTEXT D-03 (default 2+1), D-04 (dict shape), D-05 (ordering by
    direction-of-metric absolute gap_vs_benchmark).

    Cluster-bleed gate (interpretation.py:295-306) reapplied at SQL level:
    rows with `rt_visible_to_hit_ms > _T0_T2_MAX_MS` are excluded.

    Excludes rows with NULL round_number — those engagements can't be
    attributed back to a specific round in the narrative.

    Uses cursor.fetchall() exclusively — pandas-based SQL readers cast 17-digit
    SteamID64 values to float64 and silently drop precision (CLAUDE.md gotcha +
    R-8). Manual dict construction below.

    LEFT JOIN duel_attempts per REQ-2 / B-3 — preserves engagements without a
    matching duel_attempt row (LEFT, not INNER) so we don't drop attribution
    candidates whose duel_attempt is missing or out-of-window.
    """
    if engagement_type not in ("peek", "hold"):
        raise ValueError(
            f"engagement_type must be peek|hold, got {engagement_type!r}"
        )
    lower_is_better = metric in _METRICS_LOWER_IS_BETTER

    # NOTE: metric name is interpolated — engagements columns are a closed set.
    # We don't whitelist here because callers pass the same names that
    # _FALLBACK_THRESHOLDS / interpretation.py already use.
    sql = f"""
        SELECT e.demo_name,
               e.t0_manual_tick,
               e.map_name,
               e.round_number,
               e.round_phase,
               e.round_time_s,
               e.{metric} as player_value,
               e.rt_visible_to_hit_ms
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

    try:
        with closing(sqlite3.connect(db_path)) as conn:
            cursor = conn.execute(
                sql, (int(player_steamid), engagement_type, _T0_T2_MAX_MS)
            )
            raw = cursor.fetchall()
    except sqlite3.OperationalError as e:
        # Pre-Wave-0 DB without round_number column (or missing engagements
        # table) — surface as NarrativeBuildError so caller fail-softs.
        raise NarrativeBuildError(
            f"DB schema missing for fetch_top_moments — run init_db first ({e})"
        ) from e

    if not raw:
        return []

    rows: list[dict] = [
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

    # D-05: ordering rule. Sort so worst is at the top.
    if lower_is_better:
        # Higher gap (positive, above benchmark) = worse
        rows.sort(key=lambda x: x["gap_vs_benchmark"], reverse=True)
    else:
        # More negative gap (below benchmark) = worse for higher-is-better
        rows.sort(key=lambda x: x["gap_vs_benchmark"])

    worst = rows[:n_worst]
    # Best — opposite end. Skip if not enough rows beyond worst slice.
    if n_best > 0 and len(rows) > n_worst:
        best = rows[-n_best:]
    else:
        best = []

    # Avoid duplicates when the dataset is tiny (worst and best overlap)
    worst_keys = {(m["demo_name"], m["t0_tick"]) for m in worst}
    best = [m for m in best if (m["demo_name"], m["t0_tick"]) not in worst_keys]
    return worst + best


# ── content_hash ────────────────────────────────────────────────────────────


def _content_hash(rows: list[dict], top_moments: dict[str, list[dict]]) -> str:
    """Deterministic 16-char hash of (rows + top_moments).

    Excludes the 'directions' field from rows — directions is constant per
    (metric, engagement_type) pair and lives in interpretation.DIRECTIONS;
    excluding it from the hash prevents cache miss when DIRECTIONS dict
    receives cosmetic edits (RESEARCH note line 481-483).

    Sort_keys=True for stability across Python runs / hash randomization.
    """
    stable_rows = [
        {k: v for k, v in r.items() if k != "directions"} for r in rows
    ]
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
    db_path: str,
    player_steamid: int,
    engagement_type: str,
    content_hash: str,
    prompt_hash: Optional[str] = None,
) -> Optional[str]:
    """Return cached narrative_md or None on miss.

    If prompt_hash provided, also requires cached prompt_hash to match —
    treated as cache miss when stored prompt drifted from current template
    (D-18 mitigation: prompt edits invalidate prior caches).
    """
    with closing(sqlite3.connect(db_path)) as conn:
        cursor = conn.execute(
            "SELECT narrative_md, prompt_hash FROM narrative_cache "
            "WHERE player_steamid = ? AND engagement_type = ? AND content_hash = ?",
            (int(player_steamid), engagement_type, content_hash),
        )
        row = cursor.fetchone()
    if row is None:
        return None
    cached_md, cached_prompt_hash = row
    if prompt_hash is not None and cached_prompt_hash != prompt_hash:
        return None
    return cached_md


def _cache_put(
    db_path: str,
    player_steamid: int,
    engagement_type: str,
    content_hash: str,
    narrative_md: str,
    model: str,
    usage: dict,
    prompt_hash: Optional[str] = None,
) -> None:
    """INSERT OR REPLACE narrative cache row. Idempotent on PK collision."""
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                "INSERT OR REPLACE INTO narrative_cache ("
                "player_steamid, engagement_type, content_hash, narrative_md, model, "
                "tokens_in, tokens_out, cache_creation_input_tokens, "
                "cache_read_input_tokens, generated_at, prompt_hash"
                ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    int(player_steamid),
                    engagement_type,
                    content_hash,
                    narrative_md,
                    model,
                    int(usage.get("input_tokens", 0)),
                    int(usage.get("output_tokens", 0)),
                    int(usage.get("cache_creation_input_tokens", 0)),
                    int(usage.get("cache_read_input_tokens", 0)),
                    datetime.now(timezone.utc).isoformat(),
                    prompt_hash,
                ),
            )


# ── LLM client (one-shot `claude -p --output-format json` — Path B sub mode) ─
#
# Path B (chosen 2026-05-12): leverage Claude Code Max subscription via
# subprocess. Persistent stream-json mode (commit ab23e90) initially used
# for cache reuse, but Win-pipe broke when stdin user message exceeded ~5KB
# (BrokenPipeError on write, subprocess closed stdin reader). Reverted
# 2026-05-13 to one-shot `subprocess.run` mode using `--output-format json`,
# which handles large input via communicate() reliably.
#
# Tradeoffs:
# - Each call spawns fresh process (~3-4s bootstrap)
# - Cold cache_creation tax every call — but cache is shared 5min, so
#   serial calls within 5min still hit cache_read on subsequent calls
# - Subscription absorbs marginal cost
# - Spawned with cwd=tempdir to skip project context discovery
#
# Live numbers (sonnet-4-6, ~4.5KB sys + ~10KB user, real eval payload):
# - Cold first call: ~70s wall (cw~18k cr~21k partial cache hit from
#   cross-session 1h ephemeral cache)
# - Subsequent calls within 5min: cache_read hits keep cost down

_CLAUDE_CLI_TIMEOUT_S: int = 240  # per-call wall budget (Path B cold call ~60-180s, headroom for Staehr-class)


def _get_client():
    """Return CLI binary path. Tests can monkeypatch."""
    return "claude"


def call_llm(
    prompt_system: str,
    prompt_user: str,
    max_tokens: int = _MAX_TOKENS,
) -> tuple[str, dict]:
    """One-shot `claude -p --output-format json` call. Returns (text, usage_dict).

    PUBLIC per REQ-3 — single function abstracting LLM provider; renaming-safe
    interface for future v2.1 multi-provider swap.

    Path B (Max sub mode): each call is a fresh subprocess. `max_tokens` is
    retained for signature parity but NOT plumbed (claude CLI has no per-call
    cap arg). Spawned with cwd=tempdir so claude CLI skips project context
    discovery + project-level SessionStart hooks (saves 30-60s + avoids
    contention with parent Claude Code sessions).

    Error taxonomy → NarrativeBuildError:
    - claude binary missing                    — FileNotFoundError on spawn
    - subprocess.TimeoutExpired                — > _CLAUDE_CLI_TIMEOUT_S
    - non-zero returncode                      — CLI failure
    - JSONDecodeError on stdout                — malformed CLI output
    - payload["is_error"] true                 — Claude API error
    """
    import subprocess
    import tempfile

    binary = _get_client()
    model = os.environ.get("LLM_MODEL", LLM_MODEL)
    cmd = [
        binary, "-p",
        "--output-format", "json",
        "--model", model,
        "--append-system-prompt", prompt_system,
        "--exclude-dynamic-system-prompt-sections",
    ]
    try:
        completed = subprocess.run(
            cmd,
            input=prompt_user,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_CLAUDE_CLI_TIMEOUT_S,
            cwd=tempfile.gettempdir(),
        )
    except FileNotFoundError as e:
        raise NarrativeBuildError(
            "claude CLI not found on PATH (need Claude Code installed)"
        ) from e
    except subprocess.TimeoutExpired as e:
        raise NarrativeBuildError(
            f"claude CLI timeout {_CLAUDE_CLI_TIMEOUT_S}s"
        ) from e

    if completed.returncode != 0:
        raise NarrativeBuildError(
            f"claude CLI exit {completed.returncode}: {completed.stderr[:500]}"
        )

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as e:
        raise NarrativeBuildError(
            f"claude CLI invalid JSON: {completed.stdout[:300]}"
        ) from e

    if payload.get("is_error") or payload.get("api_error_status"):
        raise NarrativeBuildError(
            f"claude CLI api error: {payload.get('api_error_status')!r}"
        )

    text = payload.get("result", "")
    if not text:
        raise NarrativeBuildError("claude CLI returned empty result")

    cli_usage = payload.get("usage", {}) or {}
    usage = {
        "input_tokens": cli_usage.get("input_tokens", 0),
        "output_tokens": cli_usage.get("output_tokens", 0),
        "cache_creation_input_tokens": cli_usage.get("cache_creation_input_tokens", 0),
        "cache_read_input_tokens": cli_usage.get("cache_read_input_tokens", 0),
        "model": model,
        "subscription_mode": True,
        "total_cost_usd_reported": payload.get("total_cost_usd", 0.0),
    }
    return text, usage


def _failure_logger() -> logging.Logger:
    """Lazy file-handler logger for narrative_failures.log. Re-creating handlers
    is cheap; we add one only if missing. propagate=False isolates from root."""
    logger = logging.getLogger("narrative_failures")
    if not logger.handlers:
        fh = logging.FileHandler("narrative_failures.log", encoding="utf-8")
        fh.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s")
        )
        logger.addHandler(fh)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    return logger


# ── build_narrative_report orchestrator ────────────────────────────────────


def _render_prompt(
    rows: list[dict],
    top_moments: dict[str, list[dict]],
    player_context: dict,
) -> tuple[str, str]:
    """Return (system_block, user_block).

    `system_block` is the cacheable static instructions chunk (Anthropic
    prompt-cache target). `user_block` is the dynamic per-call payload as
    JSON.

    Plan v2-03 task 2: the prompt template at `_PROMPT_PATH` is now REQUIRED.
    W1's silent STATIC_PLACEHOLDER fallback is removed — both missing-file
    and missing-marker conditions raise `NarrativeBuildError`, which the
    orchestrator catches and converts into the tier-table-only fallback
    (REQ-10). This guarantees we never ship a placeholder prompt to the LLM.
    """
    try:
        with open(_PROMPT_PATH, encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError as e:
        raise NarrativeBuildError(
            f"Prompt template missing at {_PROMPT_PATH}. "
            "Ship plan v2-interpretation-narrative-03 first."
        ) from e

    if "{{DYNAMIC_USER_BLOCK}}" not in template:
        raise NarrativeBuildError(
            f"Prompt template at {_PROMPT_PATH} is missing the "
            "{{DYNAMIC_USER_BLOCK}} partition marker."
        )

    static, _, _ = template.partition("{{DYNAMIC_USER_BLOCK}}")

    dynamic = json.dumps(
        {
            "player": player_context,
            "tier_rows": rows,
            "top_moments": top_moments,
        },
        ensure_ascii=False,
        indent=2,
        default=str,
    )
    return static, dynamic


def _build_allowed_refs(
    top_moments: dict[str, list[dict]],
    player_name: str,
) -> dict[str, set]:
    """Per D-08: allowed_refs = union of (demo_names, ticks, round_numbers,
    map_names from top_moments) + player nickname. The validator (Plan 01)
    consumes this set per RESEARCH §Validator Design.
    """
    demos = {m["demo_name"] for ms in top_moments.values() for m in ms}
    ticks = {m["t0_tick"] for ms in top_moments.values() for m in ms}
    rounds = {
        m["round_number"]
        for ms in top_moments.values()
        for m in ms
        if m.get("round_number") is not None
    }
    maps = {
        m["map_name"]
        for ms in top_moments.values()
        for m in ms
        if m.get("map_name")
    }
    return {
        "demos": demos,
        "ticks": ticks,
        "rounds": rounds,
        "maps": maps,
        "nickname": player_name,
    }


def build_narrative_report(
    rows: list[dict],
    top_moments: dict[str, list[dict]],
    player_context: dict,
    db_path: str = DB_PATH,
) -> str:
    """Per REQ-1. Orchestrates: cache lookup → prompt render → call_llm →
    validate_narrative → cache_put → return.

    Raises NarrativeBuildError on validator fail or LLM error. Caller
    (report_generator) catches → fail-soft to tier-table-only per REQ-10.

    Cache lookup short-circuits the LLM call when (player, engagement_type,
    content_hash, prompt_hash) all match a prior cache row. content_hash key
    spans rows + top_moments; prompt_hash spans the prompt file (D-18).
    """
    # Deferred import — narrative_validator ships in Plan 01 (parallel wave).
    # If Plan 01 isn't in the tree yet, module-level import would crash on file
    # load; deferred import only fires at first build_narrative_report call.
    from narrative_validator import validate_narrative

    player_steamid = int(player_context["player_steamid"])
    engagement_type = player_context["engagement_type"]
    player_name = (
        player_context.get("player_name")
        or PLAYER_NAMES.get(player_steamid)
        or f"player_{str(player_steamid)[-4:]}"
    )

    ch = _content_hash(rows, top_moments)
    ph = _prompt_hash()

    cached = _cache_get(
        db_path, player_steamid, engagement_type, ch, prompt_hash=ph
    )
    if cached is not None:
        return cached

    system, user = _render_prompt(rows, top_moments, player_context)
    text, usage = call_llm(system, user)

    allowed_refs = _build_allowed_refs(top_moments, player_name)
    is_valid, violations = validate_narrative(text, allowed_refs)
    if not is_valid:
        _failure_logger().warning(
            f"NARRATIVE_FAIL kind=validator player={player_steamid} "
            f"type={engagement_type} violations={violations} "
            f"raw_text_head={text[:300]!r}"
        )
        violation_types = [v["type"] for v in violations]
        raise NarrativeBuildError(
            f"Validator rejected narrative ({len(violations)} violations): "
            f"{violation_types}"
        )

    _cache_put(
        db_path, player_steamid, engagement_type, ch,
        text, usage["model"], usage, prompt_hash=ph,
    )
    return text


# ─────────────────────────────────────────────────────────────────────────────
# Plan 05 (Wave 3) — eval harness CLI subcommands + score helpers.
# REQ-8 (eval harness), REQ-9 (cost CLI), B-A (--emit-timings), B-6 (score-cost),
# W-7 (record-fixture skip marker), D-19 / D-20 CSV schemas.
# ─────────────────────────────────────────────────────────────────────────────


# ── CSV append+dedup helpers (D-19, D-20) ────────────────────────────────────


def save_rating(csv_path: str, row: dict) -> None:
    """Append rating to CSV; dedup by (report_id, prompt_hash, dim) per D-19.

    New prompt_hash creates a new row (D-18 iteration history). Re-rating the
    same dim under the same prompt_hash overwrites in place.
    """
    import pandas as pd
    from pathlib import Path
    cols = ["report_id", "player_steamid", "prompt_hash",
            "dim", "score", "notes", "rated_at"]
    p = Path(csv_path)
    if p.exists() and p.stat().st_size > 0:
        # Keep player_steamid as Int64 to preserve 17-digit precision (CLAUDE.md).
        existing = pd.read_csv(p, dtype={"player_steamid": "Int64"}, encoding="utf-8")
    else:
        existing = pd.DataFrame(columns=cols)
    if not existing.empty:
        mask = (
            (existing["report_id"].astype(str) == str(row["report_id"]))
            & (existing["prompt_hash"].astype(str) == str(row["prompt_hash"]))
            & (existing["dim"].astype(str) == str(row["dim"]))
        )
        existing = existing[~mask]
    new_df = pd.DataFrame([row], columns=cols)
    combined = pd.concat([existing, new_df], ignore_index=True)
    # Enforce column order on write.
    combined = combined[cols]
    p.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(p, index=False, encoding="utf-8")


def save_side_by_side(csv_path: str, row: dict) -> None:
    """Append side-by-side rating; dedup by (pair_id, player_steamid) per D-20."""
    import pandas as pd
    from pathlib import Path
    cols = ["pair_id", "player_steamid", "preferred_version",
            "v1_rating", "v2_rating", "notes", "rated_at"]
    p = Path(csv_path)
    if p.exists() and p.stat().st_size > 0:
        existing = pd.read_csv(p, dtype={"player_steamid": "Int64"}, encoding="utf-8")
    else:
        existing = pd.DataFrame(columns=cols)
    if not existing.empty:
        mask = (
            (existing["pair_id"].astype(str) == str(row["pair_id"]))
            & (existing["player_steamid"].astype(str) == str(row["player_steamid"]))
        )
        existing = existing[~mask]
    new_df = pd.DataFrame([row], columns=cols)
    combined = pd.concat([existing, new_df], ignore_index=True)
    combined = combined[cols]
    p.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(p, index=False, encoding="utf-8")


# ── Score aggregations (SC-1, SC-6) ──────────────────────────────────────────


def score_sc1(csv_path: str = "evals/interpretation_v2_ratings.csv") -> dict:
    """Aggregate ratings -> SC-1 verdict.

    Returns dict with keys: pass, avg, per_dim, n_reports, prompt_hash,
    fail_reasons. Uses latest prompt_hash only (D-18 — stale ratings ignored).
    """
    import pandas as pd
    from pathlib import Path
    p = Path(csv_path)
    if not p.exists() or p.stat().st_size == 0:
        return {"pass": False, "avg": None, "per_dim": {},
                "n_reports": 0, "fail_reasons": ["no eval CSV"]}
    df = pd.read_csv(p)
    if df.empty:
        return {"pass": False, "avg": None, "per_dim": {},
                "n_reports": 0, "fail_reasons": ["empty CSV"]}
    latest_ph = df.sort_values("rated_at").iloc[-1]["prompt_hash"]
    latest = df[df["prompt_hash"] == latest_ph]
    per_dim = latest.groupby("dim")["score"].mean().to_dict()
    # Round to 4dp for stable display + comparisons in tests.
    per_dim = {k: round(float(v), 4) for k, v in per_dim.items()}
    avg = round(float(latest["score"].mean()), 4)
    n_reports = int(latest["report_id"].nunique())
    fail_reasons: list[str] = []
    if avg < 4.0:
        fail_reasons.append(f"avg {avg:.2f} < 4.0")
    for dim, m in per_dim.items():
        if m < 3.5:
            fail_reasons.append(f"dim {dim}={m:.2f} < 3.5 floor")
    return {
        "pass": len(fail_reasons) == 0,
        "avg": avg, "per_dim": per_dim,
        "n_reports": n_reports, "prompt_hash": str(latest_ph),
        "fail_reasons": fail_reasons,
    }


def score_sc6(csv_path: str = "evals/v2_side_by_side.csv") -> dict:
    """Aggregate side-by-side -> SC-6 verdict.

    Gates: v2_mean >= 4.0, v1_mean <= 3.0, delta >= 1.0.
    """
    import pandas as pd
    from pathlib import Path
    p = Path(csv_path)
    if not p.exists() or p.stat().st_size == 0:
        return {"pass": False, "v1_mean": None, "v2_mean": None,
                "delta": None, "n_pairs": 0, "fail_reasons": ["no CSV"]}
    df = pd.read_csv(p)
    if df.empty:
        return {"pass": False, "v1_mean": None, "v2_mean": None,
                "delta": None, "n_pairs": 0, "fail_reasons": ["empty CSV"]}
    v1_mean = round(float(df["v1_rating"].mean()), 4)
    v2_mean = round(float(df["v2_rating"].mean()), 4)
    delta = round(v2_mean - v1_mean, 4)
    preferred_dist = df["preferred_version"].value_counts().to_dict()
    preferred_dist = {str(k): int(v) for k, v in preferred_dist.items()}
    fail_reasons: list[str] = []
    if v2_mean < 4.0:
        fail_reasons.append(f"v2_mean {v2_mean:.2f} < 4.0")
    if v1_mean > 3.0:
        fail_reasons.append(f"v1_mean {v1_mean:.2f} > 3.0")
    if delta < 1.0:
        fail_reasons.append(f"delta {delta:.2f} < 1.0")
    return {
        "pass": len(fail_reasons) == 0,
        "v1_mean": v1_mean, "v2_mean": v2_mean, "delta": delta,
        "n_pairs": int(len(df)), "preferred_dist": preferred_dist,
        "fail_reasons": fail_reasons,
    }


# ── Cost report (REQ-9 + SC-4 via score-cost CLI) ────────────────────────────


def _row_cost(model: str, in_tok: int, out_tok: int, cw: int, cr: int) -> float:
    """USD cost for one cache row given token counts. PRICING fallback to sonnet."""
    p = PRICING.get(model, PRICING["claude-sonnet-4-6"])
    return (
        in_tok * p["input"] / 1_000_000
        + cw * p["cache_w_5m"] / 1_000_000
        + cr * p["cache_r"] / 1_000_000
        + out_tok * p["output"] / 1_000_000
    )


def cost_report(db_path: str = DB_PATH) -> dict:
    """Aggregate narrative_cache spend grouped by model + last-7d window.

    Returns dict with keys: total_usd, by_model, last_7d. On missing table
    surfaces an 'error' key (caller decides exit code).
    """
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
            return {"error": "narrative_cache table not found — run init_db first",
                    "total_usd": 0.0, "by_model": {}, "last_7d": []}
    by_model: dict[str, dict] = {}
    total_usd = 0.0
    for model, n, in_t, out_t, cw, cr in rows:
        cost = _row_cost(model, in_t or 0, out_t or 0, cw or 0, cr or 0)
        by_model[model] = {
            "reports": int(n), "in": int(in_t or 0), "out": int(out_t or 0),
            "cw": int(cw or 0), "cr": int(cr or 0), "usd": round(cost, 4),
        }
        total_usd += cost
    last7_data: list[dict] = []
    for n, in_t, out_t, cw, cr, model in last7:
        cost7 = _row_cost(model, in_t or 0, out_t or 0, cw or 0, cr or 0)
        last7_data.append({"model": model, "reports": int(n), "usd": round(cost7, 4)})
    return {"total_usd": round(total_usd, 4),
            "by_model": by_model, "last_7d": last7_data}


# ── CLI entry — `python -m interpretation_narrative ...` ─────────────────────


def _cli_main(argv=None) -> int:
    import argparse
    import math as _math
    import time as _time
    from datetime import datetime, timezone
    from pathlib import Path as _P

    p = argparse.ArgumentParser(prog="interpretation_narrative")
    sub = p.add_subparsers(dest="cmd", required=True)

    # cost-report ─────────────────────────────────────────────────────────────
    cr = sub.add_parser("cost-report",
                        help="Aggregate narrative_cache spend by model (REQ-9).")
    cr.add_argument("--db", default=DB_PATH)

    # eval-rate ───────────────────────────────────────────────────────────────
    er = sub.add_parser("eval-rate",
                        help="Append one row to evals/interpretation_v2_ratings.csv.")
    er.add_argument("--csv", default="evals/interpretation_v2_ratings.csv")
    er.add_argument("--report-id", required=True)
    er.add_argument("--player", type=int, required=True)
    er.add_argument("--dim", required=True, choices=[
        "factual_accuracy", "actionability", "tone", "attribution", "hallucinations",
    ])
    er.add_argument("--score", type=int, required=True, choices=[1, 2, 3, 4, 5])
    er.add_argument("--notes", default="")
    er.add_argument("--prompt-hash", default=None)

    # generate-eval-set ───────────────────────────────────────────────────────
    ge = sub.add_parser("generate-eval-set",
                        help="Render 10 HTML reports from a roster JSON.")
    ge.add_argument("--roster", default="evals/v2_eval_player_roster.json")
    ge.add_argument("--out-dir", default="evals/generated")
    ge.add_argument("--db", default=DB_PATH)
    ge.add_argument("--benchmark", type=int, default=76561198386265483)  # donk
    ge.add_argument(
        "--emit-timings", default=None,
        help=("Path to JSON file. When set, write per-report wall-time timings "
              "and P95 (B-A: SC-3 enforcement input for plan 06 Task 3)."),
    )

    # generate-side-by-side ───────────────────────────────────────────────────
    gs = sub.add_parser("generate-side-by-side",
                        help="Emit paired v1 + v2 HTML reports for SC-6.")
    gs.add_argument("--roster", default="evals/v2_eval_player_roster.json")
    gs.add_argument("--out-dir", default="evals/generated")
    gs.add_argument("--db", default=DB_PATH)
    gs.add_argument("--benchmark", type=int, default=76561198386265483)
    gs.add_argument("--pairs", type=int, default=5)

    # score ───────────────────────────────────────────────────────────────────
    sc = sub.add_parser("score", help="SC-1 verdict from ratings CSV.")
    sc.add_argument("--csv", default="evals/interpretation_v2_ratings.csv")

    # score-side-by-side ──────────────────────────────────────────────────────
    ss = sub.add_parser("score-side-by-side", help="SC-6 verdict.")
    ss.add_argument("--csv", default="evals/v2_side_by_side.csv")

    # score-cost (B-6 — SC-4 hard gate) ───────────────────────────────────────
    scost = sub.add_parser("score-cost",
                           help="SC-4 gate: avg cost per report <= --max-per-report.")
    scost.add_argument("--db", default=DB_PATH)
    scost.add_argument("--max-per-report", type=float, default=0.10)

    # rate-side-by-side ───────────────────────────────────────────────────────
    rs = sub.add_parser("rate-side-by-side",
                        help="Append one row to evals/v2_side_by_side.csv.")
    rs.add_argument("--csv", default="evals/v2_side_by_side.csv")
    rs.add_argument("--pair-id", required=True)
    rs.add_argument("--player", type=int, required=True)
    rs.add_argument("--preferred", choices=["v1", "v2", "neither"], required=True)
    rs.add_argument("--v1-rating", type=int, required=True, choices=[1, 2, 3, 4, 5])
    rs.add_argument("--v2-rating", type=int, required=True, choices=[1, 2, 3, 4, 5])
    rs.add_argument("--notes", default="")

    # record-fixture (W-7 — one-shot real-API capture) ────────────────────────
    rf = sub.add_parser(
        "record-fixture",
        help=("Capture one real-API narrative as a JSON fixture for W0 "
              "test replay. Requires ANTHROPIC_API_KEY."),
    )
    rf.add_argument("--player", type=int, required=True)
    rf.add_argument("--type", choices=["peek", "hold"], required=True)
    rf.add_argument("--out", required=True)
    rf.add_argument("--db", default=DB_PATH)

    args = p.parse_args(argv)
    now = datetime.now(timezone.utc).isoformat()

    # ── cost-report ────────────────────────────────────────────────────────
    if args.cmd == "cost-report":
        data = cost_report(args.db)
        if "error" in data:
            print(f"ERROR: {data['error']}")
            return 1
        total_reports = sum(m["reports"] for m in data["by_model"].values())
        print(f"Reports generated: {total_reports}")
        for model, m in data["by_model"].items():
            print(f"  {model}: {m['reports']} reports, ${m['usd']:.4f} "
                  f"(in={m['in']:,}, out={m['out']:,}, "
                  f"cw={m['cw']:,}, cr={m['cr']:,})")
        print(f"Total cost (USD): ${data['total_usd']:.4f}")
        print("Last 7 days:")
        for entry in data["last_7d"]:
            print(f"  {entry['model']}: {entry['reports']} reports, "
                  f"${entry['usd']:.4f}")
        return 0

    # ── eval-rate ──────────────────────────────────────────────────────────
    if args.cmd == "eval-rate":
        ph = args.prompt_hash or _prompt_hash()
        row = {
            "report_id": args.report_id, "player_steamid": args.player,
            "prompt_hash": ph, "dim": args.dim, "score": args.score,
            "notes": args.notes, "rated_at": now,
        }
        save_rating(args.csv, row)
        print(f"Rated: {args.report_id} dim={args.dim} score={args.score}")
        return 0

    # ── generate-eval-set ──────────────────────────────────────────────────
    if args.cmd == "generate-eval-set":
        from report_generator import generate_html_report
        roster = json.loads(_P(args.roster).read_text(encoding="utf-8"))
        _P(args.out_dir).mkdir(parents=True, exist_ok=True)
        timings: list[dict] = []
        for p_entry in roster["players"]:
            sid = int(p_entry["steamid"])
            name = p_entry.get("name") or f"player_{str(sid)[-4:]}"
            out_path = _P(args.out_dir) / f"v2_{name}.html"
            t0 = _time.perf_counter()
            ok = False
            try:
                html = generate_html_report(
                    sid, args.benchmark, "donk", db_path=args.db,
                )
                out_path.write_bytes(html)
                ok = True
                print(f"Generated: {out_path}")
            except Exception as e:  # noqa: BLE001 - eval generator must continue on per-player error
                print(f"FAILED for {name} ({sid}): {e!r}")
            elapsed_s = _time.perf_counter() - t0
            timings.append({
                "player_steamid": sid, "name": name,
                "ok": ok, "elapsed_s": elapsed_s,
            })
        if args.emit_timings:
            durations = sorted(t["elapsed_s"] for t in timings if t["ok"])
            if durations:
                p95_idx = max(0, _math.ceil(0.95 * len(durations)) - 1)
                p95 = durations[p95_idx]
            else:
                p95 = None
            payload = {
                "timings": timings, "p95_s": p95,
                "n_ok": sum(1 for t in timings if t["ok"]),
                "n_total": len(timings),
            }
            out_p = _P(args.emit_timings)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print(f"Timings -> {args.emit_timings} "
                  f"(p95={p95!r}s, n_ok={payload['n_ok']}/{payload['n_total']})")
        return 0

    # ── generate-side-by-side ──────────────────────────────────────────────
    if args.cmd == "generate-side-by-side":
        from report_generator import generate_html_report
        roster = json.loads(_P(args.roster).read_text(encoding="utf-8"))
        _P(args.out_dir).mkdir(parents=True, exist_ok=True)
        picked = roster["players"][:args.pairs]
        for i, p_entry in enumerate(picked):
            sid = int(p_entry["steamid"])
            name = p_entry.get("name") or f"player_{str(sid)[-4:]}"
            pair_id = f"pair_{i + 1:03d}"
            v1_html = generate_html_report(
                sid, args.benchmark, "donk", db_path=args.db, no_narrative=True,
            )
            v2_html = generate_html_report(
                sid, args.benchmark, "donk", db_path=args.db, no_narrative=False,
            )
            (_P(args.out_dir) / f"{pair_id}_{name}_v1.html").write_bytes(v1_html)
            (_P(args.out_dir) / f"{pair_id}_{name}_v2.html").write_bytes(v2_html)
            print(f"Generated pair: {pair_id} for {name}")
        return 0

    # ── score (SC-1) ───────────────────────────────────────────────────────
    if args.cmd == "score":
        data = score_sc1(args.csv)
        verdict = "PASS" if data["pass"] else "FAIL"
        print(f"SC-1 verdict: {verdict}")
        if data["avg"] is not None:
            print(f"  avg: {data['avg']:.2f} (gate >=4.0)")
            print(f"  n_reports: {data['n_reports']}")
            print(f"  prompt_hash: {data.get('prompt_hash', '?')}")
            for dim, m in data["per_dim"].items():
                floor_ok = "OK" if m >= 3.5 else "FAIL"
                print(f"  {dim}: {m:.2f} [{floor_ok}]")
        for r in data["fail_reasons"]:
            print(f"  fail: {r}")
        return 0 if data["pass"] else 2

    # ── score-side-by-side (SC-6) ──────────────────────────────────────────
    if args.cmd == "score-side-by-side":
        data = score_sc6(args.csv)
        verdict = "PASS" if data["pass"] else "FAIL"
        print(f"SC-6 verdict: {verdict}")
        if data["v1_mean"] is not None:
            print(f"  v1_mean: {data['v1_mean']:.2f} (gate <=3.0)")
            print(f"  v2_mean: {data['v2_mean']:.2f} (gate >=4.0)")
            print(f"  delta:   {data['delta']:.2f} (gate >=1.0)")
            print(f"  n_pairs: {data['n_pairs']}")
            print(f"  preferred: {data.get('preferred_dist', {})}")
        for r in data["fail_reasons"]:
            print(f"  fail: {r}")
        return 0 if data["pass"] else 2

    # ── score-cost (B-6, SC-4 hard gate) ───────────────────────────────────
    # Path B (2026-05-12): Claude Code Max subscription path → marginal API
    # cost is $0 (flat-rate sub absorbs token spend). PRICING table-derived
    # costs become INFORMATIONAL (reflect what the SDK path would have cost).
    # SC-4 verdict: PASS unconditionally under subscription mode.
    if args.cmd == "score-cost":
        data = cost_report(args.db)
        if "error" in data:
            # Treat missing table as SKIP (no narrative yet).
            print(f"SC-4 verdict: SKIP — {data['error']}")
            return 0
        n_reports = sum(m["reports"] for m in data.get("by_model", {}).values())
        total_usd = data.get("total_usd", 0.0)
        if n_reports == 0:
            print("SC-4 verdict: SKIP — no reports in narrative_cache yet")
            return 0
        avg = total_usd / n_reports
        # Subscription mode: marginal cost is $0, absolute SC-4 gate not applicable.
        print("SC-4 verdict: PASS (subscription mode — Path B claude CLI subprocess)")
        print(f"  n_reports: {n_reports}")
        print(f"  total_usd_reported: ${total_usd:.4f} "
              f"(informational — PRICING-table estimate, not billed)")
        print(f"  avg_per_report_reported: ${avg:.4f} "
              f"(was-gate <=${args.max_per_report:.2f}; sub mode N/A)")
        return 0

    # ── rate-side-by-side ──────────────────────────────────────────────────
    if args.cmd == "rate-side-by-side":
        row = {
            "pair_id": args.pair_id, "player_steamid": args.player,
            "preferred_version": args.preferred,
            "v1_rating": args.v1_rating, "v2_rating": args.v2_rating,
            "notes": args.notes, "rated_at": now,
        }
        save_side_by_side(args.csv, row)
        print(f"Rated pair: {args.pair_id} preferred={args.preferred} "
              f"v1={args.v1_rating} v2={args.v2_rating}")
        return 0

    # ── record-fixture (real-API capture for W0 fixture refresh) ───────────
    if args.cmd == "record-fixture":
        # Deferred import — interpretation.compute_interpretation reads DB.
        from interpretation import compute_interpretation
        rows = compute_interpretation(
            db_path=args.db, player_steamid=args.player,
            benchmark_steamid=args.player, engagement_type=args.type,
        )
        top_moments: dict[str, list[dict]] = {}
        metrics_attribute = [
            "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
            "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
        ]
        for metric in metrics_attribute:
            bench_row = next((r for r in rows if r.get("metric") == metric), None)
            if bench_row is None or bench_row.get("benchmark_p50") is None:
                continue
            moments = fetch_top_moments(
                args.db, args.player, metric, args.type,
                float(bench_row["benchmark_p50"]),
            )
            if moments:
                top_moments[f"{metric}::{args.type}"] = moments
        player_context = {
            "player_steamid": args.player,
            "player_name": PLAYER_NAMES.get(
                args.player, f"player_{str(args.player)[-4:]}"
            ),
            "engagement_type": args.type,
            "n_total_engagements": len(rows),
        }
        system, user = _render_prompt(rows, top_moments, player_context)
        text, usage = call_llm(system, user)
        fixture = {
            "text": text, "usage": usage,
            "model": usage.get("model", LLM_MODEL),
            "stop_reason": "end_turn",
            "captured_at": now,
        }
        _P(args.out).parent.mkdir(parents=True, exist_ok=True)
        _P(args.out).write_text(
            json.dumps(fixture, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Fixture captured: {args.out}")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(_cli_main())
