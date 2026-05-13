# Phase v2-interpretation-narrative — Research

**Researched:** 2026-05-12
**Domain:** LLM-driven narrative coaching layer (Anthropic Claude API integration) on top of existing tier-table interpretation
**Confidence:** HIGH (locked SPEC + CONTEXT + verified Anthropic SDK 0.89.0 already installed + verified pricing from official docs)
**Language:** RU (per REQ-11) for prompt + eval, EN allowed in code/comments

## Summary

Phase v2 — это первый cloud API integration в проекте. Anthropic SDK 0.89.0 уже установлен в venv (verified `python -c "import anthropic; print(anthropic.__version__)"`). Pricing подтверждён по официальной странице platform.claude.com/docs/en/about-claude/pricing: Sonnet 4.6 = **$3 / MTok input, $15 / MTok output, $3.75 cache write 5m, $0.30 cache read** (10% от input). Model ID = `claude-sonnet-4-6` (alias = pinned snapshot, начиная с 4.6 generation). На еval-set (10 reports) бюджет ≈ **$0.66** холодный + $0.13 после прогрева кэша = full iteration ~$0.80. Ship cost SC-4 ($0.10/report) — выполнимо.

Архитектурно фаза разбивается на **6 строго локализованных модулей**: `interpretation_narrative.py` (entry + LLM client + cache I/O), `prompts/coaching_v2.md` (versioned), `evals/` (3 файла + roster), `scripts/backfill_round_number.py` (one-shot), `db_utils.py` patches (две новые таблицы, _ALLOWED_TABLES extension), `report_generator.py` patch (один insertion point + try/except fail-soft). Существующий `interpretation.compute_interpretation()` остаётся **untouched** — v2 wraps, не replaces.

**Primary recommendation:** Реализовать Wave-style: W0 = baseline (round_number migration + backfill, narrative_cache table, fixtures), W1 параллельно (validator regex, top_moments query, LLM client wrapper с recorded fixtures), W2 (prompt + integration в report_generator), W3 (eval harness + side-by-side), W4 (cost-report CLI + iterate prompt до SC-1 PASS). Никаких retry-loops в LLM client — single attempt → fail-soft (D-07 lock). Использовать `system=[TextBlockParam{cache_control}]` для статичного prompt body; user message несёт только структурированный JSON-context.

## User Constraints (from CONTEXT.md)

### Locked Decisions

**SPEC L-1..L-6 (model + format + caching):**
- L-1: LLM provider = Claude API (anthropic SDK). No local LLM, no OpenAI.
- L-2: Model default = `claude-sonnet-4-6`. `claude-opus-4-7` доступен через `LLM_MODEL` env var.
- L-3: Output format = markdown (renders в HTML report через существующий pipeline).
- L-4: Language = Russian primary (REQ-11).
- L-5: No tool use / function calling. Single prompt → single completion. Anthropic prompt caching enabled для статичного system prompt block.
- L-6: Caching mandatory для shipping — REQ-7 not optional.

**CONTEXT D-01..D-20 (implementation):**
- D-01: `round_number INTEGER` column в engagements via schema migration. Compute из `round_start` event ticks (already parsed `_compute_round_phase` ddm_analyzer.py:591).
- D-02: One-shot backfill script `scripts/backfill_round_number.py`, idempotent (skip rows where set).
- D-03: Top-moments shape = **N=2 worst + N=1 best per metric × 6 metrics = 18 moments max**.
- D-04: Each moment dict = `{demo_name, t0_tick, map_name, round_number, round_phase, round_time_s, player_value, benchmark_p50, gap_vs_benchmark}`.
- D-05: worst-N by absolute `gap_vs_benchmark` в направлении метрики; best-N inverse-gap.
- D-06: Hybrid validator. Numeric refs (tick, round) — strict exact match. Common nouns (map names + locked vocab `{"peek", "hold", "aim", "crosshair", "pre-aim", "deathmatch", "DM", "VOD"}`) — whitelist.
- D-07: Single LLM call per report. On validator fail → log + fall back. **No retry loop in v2.**
- D-08: `allowed_refs` = union(demo_names + ticks + round_numbers + map_names from top_moments) ∪ player nickname ∪ locked common-nouns whitelist.
- D-09: Validator returns `(is_valid: bool, violations: list[dict])` где violation = `{type, value, context_snippet}`.
- D-10: Brutally honest tone. Без flattery, без хеджирования. Address player by nickname.
- D-11: RU. Prompt + eval rubric + tone calibration все в RU.
- D-12: Length 500w ± 100, hard cap 600w в prompt. Cost estimate ~$0.08/report (within SC-4 $0.10).
- D-13: Fixed sections — `## Что у тебя получается / ## Где теряешь время / ## Action этой недели`.
- D-14: Narrative MUST reference at least one DIRECTION title verbatim (anchor in v1 system). Validator whitelists DIRECTIONS titles set.
- D-15: 10 players locked в `evals/v2_eval_player_roster.json` — 3 top + 4 mid + 3 bottom (трибутерные quotas из CONTEXT).
- D-16: Single rater (Arystan). Solo-rater limitation документировано.
- D-17: 5 rating dimensions (1-5): `factual_accuracy`, `actionability`, `tone`, `attribution`, `hallucinations`. SC-1 ≥4.0 average + per-dim floor SC-1b ≥3.5.
- D-18: Full re-rate on prompt content_hash change (diff-rate deferred к v2.1).
- D-19: `evals/interpretation_v2_ratings.csv` columns `(report_id, player_steamid, prompt_hash, dim, score, notes, rated_at)`. CSV append+dedup by `(report_id, prompt_hash, dim)`.
- D-20: SC-6 side-by-side — 5 reports v1 (tier table) vs v2 (narrative + table) на same players. `would_pay_for_this` 1-5. v2 mean ≥4.0, v1 mean ≤3.0, delta ≥1.0.

### Claude's Discretion

- Prompt iteration count before ship (no preset; iterate until SC-1 passes).
- Exact CTA/copy в narrative sections (locked by tone D-10 + structure D-13).
- Test-file location convention (follow `tests/test_interpretation.py`).
- LLM error retry policy на transient failures (HTTP 5xx, rate limit) — short backoff OK before counting as fail. **Recommendation:** SDK built-in retries (default `max_retries=2`) включаем, но НЕ оборачиваем в свой retry loop — D-07 единственная попытка после SDK retry.
- Cost-tracking CLI flag naming (`cost-report` vs `report-cost`). **Recommendation:** `cost-report`.

### Deferred Ideas (OUT OF SCOPE)

- Trajectory tracking (weekly snapshots, w-o-w deltas) — v2.1.
- Per-map / per-site breakdown — v2.1.
- Bilingual EN translation — v2.1.
- Streamlit UI narrative panel — v2 ships HTML report only.
- Cohort percentile phrasing ("better than 67% of FACEIT-8") — separate phase.
- Confidence framing UI surface — v2.1 (но fold caveat в prompt context для tone modulation).
- LLM-generated drill prescription (replace static DIRECTIONS) — defer post-v2.
- DDM (EZ-Diffusion) integration — dead per `project_ddm_validation_final_2026_05_12`.

## Phase Requirements

| ID | Description | Research Support |
|-|-|-|
| REQ-1 | `interpretation_narrative.build_narrative_report(rows, top_moments, player_context) → str` | Existing `interpretation.compute_interpretation` returns `list[dict]` rows (interpretation.py:261); top_moments built by REQ-2; player_context из PLAYER_NAMES + COUNT engagements |
| REQ-2 | `fetch_top_moments(db_path, player_steamid, metric, engagement_type, n=3) → list[dict]` join engagements + duel_attempts | Existing pattern uses `cursor.fetchall()` (CLAUDE.md gotcha); cluster-bleed gate at interpretation.py:295-306 must reapply |
| REQ-3 | `_call_llm(prompt, max_tokens) → (text, usage_metadata)` Claude API sonnet-4-6 default; provider+model env-configurable | anthropic SDK 0.89.0 installed, verified; `client.messages.create()` returns Message object with `.content[0].text` + `.usage.input_tokens/output_tokens/cache_*` |
| REQ-4 | Prompt template `prompts/coaching_v2.md` — context block + anti-hallucination + tone + format | New dir `prompts/` doesn't exist yet (verified glob); D-13 fixed sections + D-12 length cap go here |
| REQ-5 | `validate_narrative(text, allowed_refs) → (is_valid, violations)` | Hybrid regex strategy per D-06 + D-08; см. Validator Design ниже |
| REQ-6 | `report_generator.py` integration — narrative block; fail-soft fallback | Single insertion in `generate_html_report()` line 633 (между header + interpretation_section); try/except wrap |
| REQ-7 | `narrative_cache` SQLite table; `content_hash = sha256(json(rows) + json(top_moments))` | Phase 10a worktree precedent: `_ALLOWED_TABLES` extended to include `ddm_fits` (db_utils.py:18 worktree); same pattern applies — main has `{"engagements", "duel_attempts"}` only |
| REQ-8 | 10 sample reports rated 1-5 на 5 dims; `evals/interpretation_v2_ratings.csv` | New `evals/` dir; CSV append+dedup pattern из csv_utils.py |
| REQ-9 | CLI `python -m interpretation_narrative cost-report` | Use `if __name__ == "__main__":` with argparse subcommand |
| REQ-10 | Fail-soft на LLM raise OR validator reject; log в `narrative_failures.log` | gitignore add; log format: timestamp + reason + raw output + violations |
| REQ-11 | RU output language; prompt + eval set RU | D-11 lock; eval rubric translates 5 dims |

## Recommended Approach

**Pattern:** thin module that orchestrates 4 stateless helpers + 2 I/O helpers, all behind single public entry `build_narrative_report()`. SDK call is the ONLY non-pure function — everything else (validator, content_hash, top_moments query, prompt rendering) is unit-testable without network.

**File layout:**

```
cs2-ddm/
├── interpretation_narrative.py     # ~350 LOC — entry + LLM client + cache + cost CLI
├── prompts/
│   └── coaching_v2.md              # ~80 lines RU prompt template (versioned)
├── evals/
│   ├── v2_eval_player_roster.json  # 10 SteamIDs locked (D-15)
│   ├── interpretation_v2_ratings.csv  # generated by `python -m interpretation_narrative eval-rate`
│   ├── v2_side_by_side.csv         # SC-6 forced-choice ratings
│   └── README.md                   # solo-rater limitation note (D-16)
├── scripts/
│   └── backfill_round_number.py    # one-shot, idempotent (D-02)
├── tests/
│   ├── test_interpretation_narrative.py  # unit + integration (mocked anthropic)
│   ├── test_narrative_validator.py       # adversarial fixtures
│   ├── test_top_moments_query.py         # DB integration
│   └── fixtures/
│       └── narrative_responses/          # recorded mock responses (no real API)
│           ├── ok_donk_peek.json
│           ├── hallucinated_tick.json
│           └── empty_response.json
├── narrative_failures.log          # gitignored (REQ-10)
└── .gitignore                      # add narrative_failures.log + evals/.cache/
```

**Public API of `interpretation_narrative.py`:**

```python
def build_narrative_report(
    rows: list[dict],
    top_moments: dict[str, list[dict]],
    player_context: dict,
) -> str:
    """Returns markdown narrative or raises NarrativeBuildError on terminal fail.
    Caller (report_generator) catches NarrativeBuildError → falls back to tier table only."""

def fetch_top_moments(
    db_path: str,
    player_steamid: int,
    metric: str,
    engagement_type: str,
    benchmark_p50: float,
    n_worst: int = 2,
    n_best: int = 1,
) -> list[dict]: ...

def validate_narrative(
    text: str,
    allowed_refs: dict[str, set],  # {"ticks": {...}, "rounds": {...}, "demos": {...}, "maps": {...}}
) -> tuple[bool, list[dict]]: ...

def _call_llm(prompt_system: str, prompt_user: str, max_tokens: int) -> tuple[str, dict]: ...
def _content_hash(rows: list[dict], top_moments: dict) -> str: ...
def _cache_get(db_path, player_steamid, engagement_type, content_hash) -> Optional[str]: ...
def _cache_put(db_path, player_steamid, engagement_type, content_hash, narrative, model, usage) -> None: ...

class NarrativeBuildError(Exception): ...
```

**Naming convention:** snake_case per existing project; `_private_` for helpers; public symbols re-exportable for tests.

## File-Level Plan

| File | Role | LOC est. | New / Modified |
|-|-|-|-|
| `interpretation_narrative.py` | Entry + LLM client + cache I/O + cost CLI + content_hash + NarrativeBuildError | ~350 | NEW |
| `prompts/coaching_v2.md` | RU prompt template (system block + user template) | ~80 lines | NEW |
| `scripts/backfill_round_number.py` | One-shot DB migration, idempotent | ~80 | NEW |
| `tests/test_interpretation_narrative.py` | Build + integration with mocked anthropic | ~250 | NEW |
| `tests/test_narrative_validator.py` | Validator unit + adversarial | ~200 | NEW |
| `tests/test_top_moments_query.py` | DB integration | ~150 | NEW |
| `tests/fixtures/narrative_responses/*.json` | Recorded mock LLM responses | ~5 files × 30 lines | NEW |
| `evals/v2_eval_player_roster.json` | Locked 10 player SteamIDs | ~30 lines | NEW |
| `evals/interpretation_v2_ratings.csv` | Rating data (generated) | runtime | NEW |
| `evals/v2_side_by_side.csv` | SC-6 data (generated) | runtime | NEW |
| `evals/README.md` | Rubric definitions + solo-rater note | ~60 lines | NEW |
| `db_utils.py` | +narrative_cache CREATE TABLE; +round_number ALTER; +"narrative_cache" в _ALLOWED_TABLES | +~30 | MODIFIED |
| `ddm_analyzer.py` | Inject `round_number = bisect.bisect_right(round_start_ticks, t0_tick)` в `_compute_round_phase()` return; add to result dict | +~10 | MODIFIED |
| `report_generator.py` | Insert narrative block; try/except fail-soft | +~25 | MODIFIED |
| `config.py` | +`LLM_PROVIDER`, `LLM_MODEL`, `NARRATIVE_COMMON_NOUNS_WHITELIST` constants; expand `PLAYER_NAMES` (current = 2 names, 100+ players in DB) | +~20 | MODIFIED |
| `requirements.txt` | +`anthropic>=0.89` | +1 | MODIFIED |
| `.gitignore` | +`narrative_failures.log` | +1 | MODIFIED |
| `CLAUDE.md` | +section about ANTHROPIC_API_KEY env var + cost estimates | +~10 | MODIFIED |

**Total NEW:** ~1450 LOC + ~9 files. **Total MODIFIED:** ~95 LOC across 7 files.

## Anthropic SDK Integration Notes

### Verified state on machine

```bash
$ python -c "import anthropic; print(anthropic.__version__)"
0.89.0
```

Already installed in working env. `requirements.txt` нужно дописать `anthropic>=0.89` для воспроизводимости.

### Init pattern

```python
import os
from anthropic import Anthropic, APIError, RateLimitError, APIStatusError

# Module-level singleton — sync client safe for re-use across calls.
# SDK reads ANTHROPIC_API_KEY from env automatically; explicit pass for clarity.
_CLIENT: Optional[Anthropic] = None

def _get_client() -> Anthropic:
    global _CLIENT
    if _CLIENT is None:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise NarrativeBuildError("ANTHROPIC_API_KEY env var not set")
        # max_retries=2 default — SDK auto-retries on 408/409/429/5xx with exp backoff.
        # Per D-07 we do NOT add another retry loop on top.
        _CLIENT = Anthropic(api_key=api_key)
    return _CLIENT
```

### Sync messages.create call (verified pattern)

Source: `/anthropics/anthropic-sdk-python` Context7 docs.

```python
def _call_llm(prompt_system: str, prompt_user: str, max_tokens: int = 2500) -> tuple[str, dict]:
    """Single LLM call. Returns (text, usage_dict). Raises NarrativeBuildError on
    terminal failure. SDK built-in retries cover 5xx + rate-limit transient errors."""
    client = _get_client()
    model = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")
    try:
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=[
                {
                    "type": "text",
                    "text": prompt_system,
                    "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            ],
            messages=[{"role": "user", "content": prompt_user}],
            temperature=0.4,  # mid — deterministic enough for SC-1 stability,
                              # creative enough for natural prose
        )
    except APIStatusError as e:
        # 4xx incl. 400 invalid_request, 401 auth, 403, 404, 413 too_large
        raise NarrativeBuildError(f"API status {e.status_code}: {e.message}") from e
    except RateLimitError as e:
        raise NarrativeBuildError(f"Rate limit (after SDK retries): {e}") from e
    except APIError as e:
        raise NarrativeBuildError(f"API error (after SDK retries): {e}") from e

    # stop_reason values: end_turn | max_tokens | stop_sequence | refusal
    if response.stop_reason == "refusal":
        raise NarrativeBuildError(f"Content policy refusal: {response.stop_details}")
    if response.stop_reason == "max_tokens":
        # Soft warning — caller decides if truncation is acceptable.
        # For 500w ±100 (~700 output tokens) we set max_tokens=2500 to leave headroom.
        pass

    text = response.content[0].text
    usage = {
        "input_tokens": response.usage.input_tokens,  # uncached portion
        "output_tokens": response.usage.output_tokens,
        "cache_creation_input_tokens": getattr(response.usage, "cache_creation_input_tokens", 0),
        "cache_read_input_tokens": getattr(response.usage, "cache_read_input_tokens", 0),
        "model": response.model,
    }
    return text, usage
```

### Prompt caching

**Verified syntax** (Context7 + official docs platform.claude.com):

```python
system=[
    {
        "type": "text",
        "text": "<long stable instructions block>",
        "cache_control": {"type": "ephemeral", "ttl": "5m"},
    }
]
```

**TTL choice:** `5m` (default, 1.25× write multiplier) is correct here. `1h` (2× write) пайдёт-off только если eval-set генерируется быстрее 1 часа AND prompt не меняется между вызовами. На 10-report eval set за один прогон — 5m TTL достаточно (вторая итерация прогона будет быстрее 5 мин если сети нормальные).

**Pricing (verified):**
- Cache write 5m = 1.25× base = $3.75 / MTok
- Cache write 1h = 2× base = $6.00 / MTok
- Cache read = 0.10× base = $0.30 / MTok

**Static parts to cache** (system block):
- Role/tone calibration (~300-400 tokens)
- Output structure spec (D-13 sections + D-12 length cap)
- Anti-hallucination instruction (REQ-4: "do not invent demo events, ticks, rounds, maps")
- DIRECTIONS reference policy (D-14 — must reference at least one direction title)

**Dynamic per-call (in user message, NOT cached):**
- Player context (nickname, n_engagements, engagement_type)
- Tier table rows (6 metrics × tier/value/benchmark)
- Top moments (18 items × {demo, tick, round, map, value, gap})
- Bottleneck info (T0→T1 vs T1→T2)

**Math check** (~5k input estimate):
- System (cacheable): ~600 tokens
- User dynamic: ~4400 tokens (rows JSON + 18 moments JSON)
- Output: ~700 tokens (500w RU ≈ 1.4× tokens)

First call cost: 600 × 3.75/M + 4400 × 3/M + 700 × 15/M = $0.0023 + $0.0132 + $0.0105 = **$0.026**
Cached subsequent: 600 × 0.30/M + 4400 × 3/M + 700 × 15/M = $0.0002 + $0.0132 + $0.0105 = **$0.024**

(D-12 estimate of $0.08 was conservative; actual ≈ $0.025-0.05/report.)

### Token counting (REQ-9)

`response.usage` already returns `input_tokens`, `output_tokens`, `cache_creation_input_tokens`, `cache_read_input_tokens`. Total billable input = `input_tokens + cache_creation + cache_read` (per docs Note: "Total input tokens in a request is the summation of `input_tokens`, `cache_creation_input_tokens`, and `cache_read_input_tokens`").

Cost CLI computes:

```python
PRICING = {  # USD per million tokens
    "claude-sonnet-4-6": {"input": 3.0, "cache_w_5m": 3.75, "cache_r": 0.30, "output": 15.0},
    "claude-opus-4-7":   {"input": 5.0, "cache_w_5m": 6.25, "cache_r": 0.50, "output": 25.0},
    "claude-haiku-4-5":  {"input": 1.0, "cache_w_5m": 1.25, "cache_r": 0.10, "output": 5.0},
}

def _row_cost(usage_row: dict) -> float:
    p = PRICING.get(usage_row["model"], PRICING["claude-sonnet-4-6"])
    return (
        usage_row["tokens_in"] * p["input"] / 1_000_000
        + usage_row.get("cache_creation_input_tokens", 0) * p["cache_w_5m"] / 1_000_000
        + usage_row.get("cache_read_input_tokens", 0) * p["cache_r"] / 1_000_000
        + usage_row["tokens_out"] * p["output"] / 1_000_000
    )
```

### Error taxonomy (verified)

| Exception | When | Action |
|-|-|-|
| `AuthenticationError` (401) | Bad/missing API key | NarrativeBuildError → fail-soft. Не retry. |
| `RateLimitError` (429) | After SDK auto-retry exhausted | NarrativeBuildError. **D-07 says don't retry locally** — SDK already retried 2×. |
| `APIStatusError` 4xx (400/403/413) | Bad request, perms, payload too large | NarrativeBuildError. Bug в коде, не transient. |
| `APIError` 5xx (500/529 overloaded) | Server-side after SDK retries | NarrativeBuildError. Anthropic outage. |
| `stop_reason="refusal"` | Content policy intervention | NarrativeBuildError со `stop_details`. Possible RU-content sensitivity. |
| `stop_reason="max_tokens"` | Truncated output | Soft-warn; pass text downstream. Validator может не пропустить если отрезало в середине ref. |

### SDK retry policy (built-in)

`Anthropic(max_retries=2)` is default. SDK retries on 408 / 409 / 429 / 5xx with exponential backoff (per SDK source). **Do not add a second retry loop** — D-07 explicit "single LLM call attempt per report". Если хочется усилить — увеличить `max_retries=3` в `Anthropic()` ctor, но не оборачивать в свой while loop.

## Validator Design

### Strategy (per D-06, D-08, D-09)

**Hybrid:** strict numeric + whitelist nouns. Three-pass scan over LLM output text.

**Pass 1 — Demo names** (filenames, e.g. `spirit-vs-faze-m1-mirage.dem`):
- Regex: `r"\b[\w\-]+\.dem\b"` (case-insensitive)
- Each match must be in `allowed_refs["demos"]` (set of demo_names from top_moments)

**Pass 2 — Numeric refs:**
- Tick numbers: `r"тик\s*(\d{4,})"` + `r"tick\s*(\d{4,})"` + bare `r"\b\d{5,}\b"` (5+ digits — avoids false-positives on % values, scores)
- Round numbers: `r"раунд[еауы]?\s*(\d{1,2})\b"` + `r"round\s*(\d{1,2})\b"`
- Each captured digit-group must be in `allowed_refs["ticks"]` / `allowed_refs["rounds"]`

**Pass 3 — Map names:**
- Iterate over `allowed_refs["maps"]` (e.g. `{"de_mirage", "de_inferno", "de_dust2"}`)
- Strip `de_` prefix variants for display matching: `Mirage|de_mirage|MIRAGE`
- Allowed without attribution per D-06 (whitelist, не fail).

**Pass 4 — DIRECTIONS titles:**
- D-14 requires narrative cite at least one DIRECTIONS title verbatim.
- Build set of all titles from `interpretation.DIRECTIONS` dict — e.g. `{"Demo review", "Aim_botz before pug", "Map study", ...}`
- Validate ≥1 title appears as substring (case-insensitive). Fail if zero matches.

**Pass 5 — Player nickname:**
- D-10 wants player addressed by nickname.
- Soft check: nickname appears at least once. Warn but don't fail (UX nice-to-have, not critical).

### Implementation skeleton

```python
import re
from interpretation import DIRECTIONS

_NICK_HINT_LOG_ONLY = True  # don't fail on missing nickname

# Note: \b before Cyrillic doesn't always work as expected with Python re.
# Use explicit anchors. Test on adversarial RU fixtures.
_TICK_RE = re.compile(r"(?:тик|tick)\s*(\d{4,})", re.IGNORECASE)
_TICK_BARE_RE = re.compile(r"(?<![\d.,])\d{5,}(?![\d.,])")  # 5+ digits, not part of decimal
_ROUND_RE = re.compile(r"(?:раунд[аеуыое]?|round)\s*(\d{1,2})\b", re.IGNORECASE)
_DEMO_RE = re.compile(r"\b[\w\-]+\.dem\b", re.IGNORECASE)

def validate_narrative(
    text: str, allowed_refs: dict[str, set]
) -> tuple[bool, list[dict]]:
    violations: list[dict] = []

    # demos
    for m in _DEMO_RE.finditer(text):
        demo = m.group(0).lower()
        if demo not in {d.lower() for d in allowed_refs["demos"]}:
            violations.append({
                "type": "demo", "value": demo,
                "context_snippet": _snippet(text, m.start(), m.end())
            })

    # ticks (both anchored and bare)
    for m in list(_TICK_RE.finditer(text)) + list(_TICK_BARE_RE.finditer(text)):
        tick = int(m.group(1) if m.lastindex else m.group(0))
        if tick not in allowed_refs["ticks"]:
            violations.append({"type": "tick", "value": tick, "context_snippet": _snippet(text, m.start(), m.end())})

    # rounds
    for m in _ROUND_RE.finditer(text):
        rnd = int(m.group(1))
        if rnd not in allowed_refs["rounds"]:
            violations.append({"type": "round", "value": rnd, "context_snippet": _snippet(text, m.start(), m.end())})

    # DIRECTIONS title anchor (D-14)
    titles_lower = {d["title"].lower() for ds in DIRECTIONS.values() for d in ds}
    text_lower = text.lower()
    if not any(t in text_lower for t in titles_lower):
        violations.append({"type": "no_direction_anchor", "value": None, "context_snippet": ""})

    return (len(violations) == 0, violations)
```

### RU regex gotchas

1. **`\b` + Cyrillic:** Python `re` module treats Cyrillic letters as word chars by default in Python 3 (uses Unicode by default). `\b` works — но проверить на fixture `"раундёх"` (генитив pl. `раундах`, etc.). **Mitigation:** explicit alternation `раунд[аеуыое]?` covers common case suffixes. Or use `regex` library (3rd-party) for `\p{L}+` — overkill для v2.

2. **Case-folding RU:** `.lower()` works for Cyrillic in Python 3 standard. No `casefold()` needed.

3. **LLM rephrasings:**
   - "tick 12345" / "тик 12345" / "тике 12345" — covered by alternation regex.
   - "12,345" with thousands separator — `_TICK_BARE_RE` excludes because `(?![\d.,])`.
   - "round 14" / "14-й раунд" / "в 14 раунде" — `_ROUND_RE` covers anchored variants. **Risk:** "в 14 раунде" matches `р[ое]?` only if added; current regex covers. Add fixture.

4. **False positive — score numbers:** "счёт 16-12" — `16` and `12` are 2-digit, won't match bare `_TICK_BARE_RE` (requires 5+ digits) and won't match `_ROUND_RE` (requires `раунд|round` anchor). OK.

5. **False negative — paraphrased demo names:** LLM might write "в матче со Spirit" instead of `spirit-vs-faze.dem`. **D-08:** demo_name allowed_refs = ONLY exact filenames. Если LLM не использовал filename, validator не fail (just doesn't validate). Design choice: allow paraphrase, only fail on EXPLICIT FAKE filename.

### OSS validators

- **NeMo Guardrails** (NVIDIA) — heavy; YAML config language + LLM-based rails. Overkill для regex + set lookup. Skip.
- **Guardrails AI (`guardrails-ai`)** — Pydantic-style validators. Adds dep + runtime overhead. Useful for structured output (JSON), not freeform markdown. Skip.
- **DIY regex + set lookup** — ~80 LOC, zero deps, fully testable. **Recommended.**

Reasoning: validator is small (~80 LOC), fully unit-testable, no LLM judges (which would add cost + nondeterminism), zero new deps. OSS validators add complexity for no visible benefit at current scope.

## Eval Harness Pattern

### Storage (per D-19)

**Why CSV not SQLite:** existing project precedent — `csv_utils.save_results()` + `cs2_engagement_analysis_results.csv` is the established append+dedup pattern. CSV is human-readable, diffable, easy to manually edit a rating. Eval set ≤100 rows, no scaling concern. SQLite adds friction (sqlite browser to inspect) for zero benefit at this scale.

**Schema** (per D-19):

```csv
report_id,player_steamid,prompt_hash,dim,score,notes,rated_at
report_001,76561198386265483,a3f9b...,factual_accuracy,4,"Mostly accurate, one tick off",2026-05-13T10:23:00Z
report_001,76561198386265483,a3f9b...,actionability,5,"Clear next step",2026-05-13T10:23:00Z
...
```

Dedup key: `(report_id, prompt_hash, dim)`. Re-rate same report+prompt overwrites; rate different prompt for same report = new rows (lets us see prompt iteration impact).

**Side-by-side `evals/v2_side_by_side.csv`** (D-20):

```csv
pair_id,player_steamid,version,rating_would_pay_for_this,notes,rated_at
pair_001,76561198386265483,v1,2,"Numbers but no insight",2026-05-13T11:00:00Z
pair_001,76561198386265483,v2,4,"Names rounds, gives action",2026-05-13T11:00:00Z
```

Same player rated TWICE (once each version) — pair structure enables forced-choice analysis.

### content_hash (REQ-7)

```python
import hashlib, json

def _content_hash(rows: list[dict], top_moments: dict[str, list[dict]]) -> str:
    """Deterministic hash for cache key. Sort keys for stability across Python runs.
    Excludes None floats — they don't survive round-trip identically (NaN handling)."""
    # Strip volatile fields (e.g. anything with timestamp).
    stable_rows = [{k: v for k, v in r.items() if k not in {"directions"}} for r in rows]
    # directions list is constant per (metric, engagement_type) — already in DIRECTIONS dict;
    # excluding it from hash prevents cache miss when DIRECTIONS dict gets cosmetic edits.
    payload = json.dumps(
        {"rows": stable_rows, "moments": top_moments},
        sort_keys=True, default=str, ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:16]  # 64-bit prefix sufficient
```

**Prompt hash (D-18):** Separate hash on prompt file content for re-rate trigger:

```python
def _prompt_hash(prompt_path: str = "prompts/coaching_v2.md") -> str:
    with open(prompt_path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]
```

When `prompt_hash` changes → all 10 evals re-generated and re-rated (D-18 lock). Eval CLI `python -m interpretation_narrative eval-rebuild` flushes old `prompt_hash` rows and regenerates.

### Side-by-side protocol (SC-6, D-20)

**Forced-choice rationale:** Likert-only scales suffer halo bias for own-product rating. Forced-choice ("which would you pay for, A or B?") forces relative judgment. D-20 keeps Likert (`would_pay_for_this 1-5` per version) — accept this as user-locked, but ADD a preferred column:

Recommended add: `preferred_version` column ∈ `{v1, v2, neither}` per `pair_id`. Quick aggregate: `n_pairs where preferred=v2 / total`. Documents the bias if Likert deltas don't match preference distribution.

```csv
pair_id,player_steamid,preferred_version,v1_rating,v2_rating,notes,rated_at
pair_001,76561198386265483,v2,2,4,"Names rounds, gives action",2026-05-13T11:00:00Z
```

This is small extension to D-20 — flag for plan-checker as discretion.

### OSS eval frameworks

- **promptfoo** — TS-based, YAML config, focuses on regression testing across prompts. Adds Node.js dep. For 10 reports + 5 dims, overkill.
- **deepeval** — Python, pytest-style assertions, LLM-judge metrics. Useful if we wanted LLM-as-judge but D-16 is solo-rater.
- **langfuse** — observability + tracing platform. Future use if scaling, but adds external service.

**Recommendation: DIY.** 10 reports × 5 dims = 50 ratings. argparse CLI + CSV + manual rating in editor is faster to ship than learning any framework. Promote to promptfoo if v2.1 adds A/B at scale.

## Testing Strategy

### Mocking anthropic

**Pattern: monkeypatch `_get_client()` to return a fake client.** Avoids touching SDK internals; fastest test path.

```python
# tests/conftest.py
import json
from pathlib import Path

class _FakeMessage:
    def __init__(self, text: str, usage: dict, stop_reason: str = "end_turn", model: str = "claude-sonnet-4-6"):
        from types import SimpleNamespace
        self.content = [SimpleNamespace(text=text, type="text")]
        self.usage = SimpleNamespace(**usage)
        self.stop_reason = stop_reason
        self.stop_details = None
        self.model = model

class _FakeMessages:
    def __init__(self, response: _FakeMessage): self._response = response
    def create(self, **kwargs): return self._response

class FakeAnthropic:
    def __init__(self, response: _FakeMessage): self.messages = _FakeMessages(response)

def load_fixture(name: str) -> dict:
    p = Path(__file__).parent / "fixtures" / "narrative_responses" / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8"))
```

```python
# tests/test_interpretation_narrative.py
import pytest
import interpretation_narrative as inv

@pytest.fixture
def mock_anthropic_ok(monkeypatch):
    fixture = load_fixture("ok_donk_peek")
    fake = FakeAnthropic(_FakeMessage(
        text=fixture["text"],
        usage={"input_tokens": 4400, "output_tokens": 700,
               "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0},
    ))
    monkeypatch.setattr(inv, "_get_client", lambda: fake)
    return fake
```

### Recorded fixtures (no real API)

Generate fixtures ONCE manually:

```bash
# One-shot real-API call, save raw response to fixture
python -m interpretation_narrative record-fixture --player 76561198386265483 --type peek --out tests/fixtures/narrative_responses/ok_donk_peek.json
```

Fixture JSON shape:

```json
{
  "text": "## Что у тебя получается\n...",
  "usage": {"input_tokens": 4400, "output_tokens": 712, "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0},
  "model": "claude-sonnet-4-6",
  "stop_reason": "end_turn",
  "captured_at": "2026-05-13T10:00:00Z"
}
```

**Required fixtures:**
1. `ok_donk_peek.json` — clean valid output
2. `hallucinated_tick.json` — text mentions tick `99999999` not in allowed_refs (validator must catch)
3. `hallucinated_demo.json` — text mentions `fakedemo123.dem`
4. `no_direction_anchor.json` — no DIRECTIONS title cited (D-14 fail)
5. `refusal.json` — `stop_reason="refusal"` (REQ-10 fail-soft trigger)
6. `truncated_max_tokens.json` — `stop_reason="max_tokens"` ending mid-sentence (validator probably fails)
7. `clean_paraphrase.json` — narrative paraphrases without explicit refs (validator passes — D-06 lax for non-numeric)

### Property-based via hypothesis (validator)

Optional but valuable — adversarial input fuzz on validator regex:

```python
from hypothesis import given, strategies as st

@given(st.text(alphabet="0123456789абвгдежзийклмн tickтик "))
def test_validate_no_crash_on_random_input(s):
    is_valid, violations = validate_narrative(s, {"ticks": set(), "rounds": set(), "demos": set(), "maps": set()})
    # property: function never crashes regardless of input
    assert isinstance(is_valid, bool)
    assert isinstance(violations, list)
```

**Don't over-invest:** hypothesis on validator is nice but not blocking. Start with hand-written adversarial fixtures, add hypothesis if regex bugs surface.

### No-real-API discipline

**Hard rule:** all `pytest` runs must work offline / without `ANTHROPIC_API_KEY` set. CI later will fail fast if any test calls real API.

Enforcement: in `_get_client()` raise immediately if `ANTHROPIC_API_KEY` missing. All tests must `monkeypatch _get_client`. Add `tests/conftest.py` autouse fixture that asserts no real API calls happened (record-mode flag for fixture generation).

```python
# tests/conftest.py
@pytest.fixture(autouse=True)
def _no_real_anthropic(monkeypatch):
    """Fail loud if any test forgets to mock anthropic."""
    def _boom(*a, **kw):
        raise RuntimeError("Real Anthropic client requested in test — add monkeypatch.")
    monkeypatch.setattr("anthropic.Anthropic", _boom)
```

(Tests that need a fake client install their own monkeypatch, overriding this autouse.)

### Pre-commit hook compatibility

CLAUDE.md says hooks auto-run `black + ruff + pytest -p no:cov` on `*.py` edit. New files MUST pass. Strict typing per project convention — annotate all helpers.

## Cost Reality Check

### Verified pricing (2026-05-12)

Source: https://platform.claude.com/docs/en/about-claude/pricing — fetched live.

| Model | Input | Cache write 5m | Cache read | Output |
|-|-|-|-|-|
| **claude-sonnet-4-6** (default L-2) | $3 / MTok | $3.75 / MTok | $0.30 / MTok | $15 / MTok |
| claude-opus-4-7 (override) | $5 / MTok | $6.25 / MTok | $0.50 / MTok | $25 / MTok |
| claude-haiku-4-5 (если cost balloon) | $1 / MTok | $1.25 / MTok | $0.10 / MTok | $5 / MTok |

### Per-report math (sonnet-4-6 default)

Token estimates per report:
- Cacheable system prompt: ~600 tokens
- Dynamic user payload: ~4400 tokens (rows JSON ~1500 + 18 moments JSON ~2900)
- Output (RU 500w ≈ 700 tokens; RU tokenizes denser than EN, ~1.4 tokens/word)

**First call (cache miss):**
- 600 tokens × $3.75 / 1M = $0.00225 (cache write)
- 4400 tokens × $3.00 / 1M = $0.0132 (uncached input)
- 700 tokens × $15.00 / 1M = $0.0105 (output)
- **Total: $0.026**

**Subsequent call within 5m (cache hit):**
- 600 tokens × $0.30 / 1M = $0.00018 (cache read — 90% off)
- 4400 tokens × $3.00 / 1M = $0.0132
- 700 tokens × $15.00 / 1M = $0.0105
- **Total: $0.024**

(Cache savings small here because cacheable block = only ~12% of input. Worth keeping for latency + future prompt growth, but не source of major savings.)

### Eval set cost

10 reports × $0.026 = **$0.26 / iteration cold-cache**. With cache reuse if generated within 5min: ~$0.24.

### Iteration cost

If user iterates prompt 5× before SC-1 passes: 5 × $0.26 = **$1.30 total**.

### SC-4 gate

SC-4 = ≤$0.10 per fresh report. Estimate $0.026. **Comfortably within budget.** D-12 estimate of $0.08 was 3× conservative.

### Recurring at scale

- 100 reports/mo: ~$2.60. Trivial.
- 1000 reports/mo: ~$26. Acceptable.
- 10k reports/mo: ~$260. Fine; cache hit rate goes up at scale (same player re-running on new demos).

### Risks

- **Output blowing past 700 tokens:** RU is verbose. If LLM ignores 600w cap, output tokens 1500 → cost 2.1× ($0.054). Still under SC-4. Mitigation: hard `max_tokens=2500` AND validator could check word count (recommend adding word_count check to validator, fail >700 words).
- **Opus override:** if user sets `LLM_MODEL=claude-opus-4-7`, cost ~5× ($0.13/report) — exceeds SC-4. Document this in cost-report CLI output.

### What to monitor

CLI `python -m interpretation_narrative cost-report` (REQ-9) should print:

```
Reports generated: 47
Total tokens: in=212,500 / out=33,800 / cache_w=28,200 / cache_r=14,400
Total cost (USD): $1.23
By model:
  claude-sonnet-4-6: $1.23 (47 reports, $0.026 avg)
Last 7 days: 12 reports, $0.31
```

## Schema Migration Pattern

### Project precedent

**Idempotent ALTER TABLE pattern** in `db_utils.py:_migrate_schema()` (lines 75-93 main):

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

**Phase 6 schema migration pattern** (memory: "Schema migration BEFORE batch runner — retroactive migration across 100 games is painful") — current state is 5,557 engagements rows; migration must be idempotent because main+worktree DBs both touched.

### Phase 10a worktree precedent (referenced in CONTEXT)

`D:\...\cs2-ddm-phase-10a\db_utils.py:18` extends `_ALLOWED_TABLES = {"engagements", "duel_attempts", "ddm_fits"}`. Same edit needed for v2 on main: add `"narrative_cache"`.

Worktree also adds `@retry_on_locked` decorator (db_utils.py:21) + `busy_timeout=30000` (line 108) for ProcessPool contention. **v2 doesn't need these** — narrative cache writes are single-process Streamlit context. Don't pull in Phase 10a's WAL contention work; let Phase 10a own that merge separately.

### Migration steps for v2 (in order)

1. **Add to `_ALLOWED_TABLES`:** `{"engagements", "duel_attempts", "narrative_cache"}`.
2. **Add `narrative_cache` CREATE TABLE** in `_migrate_schema()`:
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
   (REQ-7 schema + добавляем `cache_creation/read_input_tokens` для accurate cost-report + `prompt_hash` для D-18 re-rate detection.)
3. **Add `round_number` column** to `_eng_migrations`:
   ```python
   ("round_number", "INTEGER DEFAULT NULL"),
   ```
   ALTER TABLE будет no-op для существующих rows (default NULL).
4. **Modify `ddm_analyzer.py:_compute_round_phase()`** — change return signature from `Tuple[Optional[float], Optional[str]]` to `Tuple[Optional[float], Optional[str], Optional[int]]` (third element = round_number). Update single caller in `analyze_engagement_episode()` (ddm_analyzer.py:683) to unpack and add to result dict at line 727.
5. **Run `scripts/backfill_round_number.py`** ONCE on main `analytics.db` (5557 rows) — idempotent: `UPDATE engagements SET round_number = ? WHERE rowid = ? AND round_number IS NULL`. Source ticks = re-derive from re-parsing each demo? **NO** — too expensive (5557 engagements × 20min/demo = weeks). Better: derive `round_number` from existing `round_time_s` + `round_phase` heuristic. **Even better:** for backfill, group by `(demo_name, match_id)`, sort `t0_manual_tick` ascending, and assign round_number = position in sorted list when `round_time_s` resets to small value. Round resets when `round_time_s_t < round_time_s_{t-1}` (next-round started).

   **Alt approach** (cleaner but slower): backfill script re-parses each unique demo, extracts round_start ticks, computes `round_number = bisect_right(round_start_ticks, t0_tick)` per row. Better attribution accuracy. Cost: ~5min/demo × ~80 demos = 6.5h. Acceptable as one-shot overnight script.

   **Recommended:** alt approach (re-parse demos). Heuristic from `round_time_s` resets is fragile (warmup rounds, retakes drop ticks). Re-parse is ground-truth source.

6. **One-shot script:**
   ```python
   # scripts/backfill_round_number.py
   import sqlite3, bisect
   from pathlib import Path
   from contextlib import closing
   from demoparser2 import DemoParser

   def backfill(db_path: str, demo_dir: str) -> dict:
       """Idempotent: update rows where round_number IS NULL."""
       with closing(sqlite3.connect(db_path)) as conn:
           # Group by demo to avoid re-parsing
           cur = conn.execute("""
               SELECT DISTINCT demo_name FROM engagements
               WHERE round_number IS NULL AND demo_name IS NOT NULL
           """)
           demos = [r[0] for r in cur.fetchall()]
           stats = {"demos_processed": 0, "rows_updated": 0, "demos_missing": []}
           for demo_name in demos:
               demo_path = Path(demo_dir) / demo_name
               if not demo_path.exists():
                   stats["demos_missing"].append(demo_name)
                   continue
               parser = DemoParser(str(demo_path))
               events = parser.parse_events(["round_start"])
               rs_df = next((df for name, df in events if name == "round_start"), None)
               if rs_df is None or rs_df.empty:
                   continue
               round_start_ticks = sorted(rs_df["tick"].astype(int).tolist())
               # Update each engagement row
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
                       stats["rows_updated"] += 1
               stats["demos_processed"] += 1
       return stats
   ```

   Operator-run: `python scripts/backfill_round_number.py --db analytics.db --demo-dir ../for_analysis/spirit ../for_analysis/faze`

## Validation Architecture

Per `.planning/config.json` `nyquist_validation: true`. Test framework = pytest 7.4+ (verified requirements.txt). Quick run command: `python -m pytest -p no:cov -x` (per CLAUDE.md hook command). Full suite: `python -m pytest`.

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|-|-|-|-|-|
| REQ-1 | `build_narrative_report()` signature + returns markdown | unit (mocked) | `pytest tests/test_interpretation_narrative.py::test_build_narrative_signature -x` | Wave 0 |
| REQ-2 | `fetch_top_moments()` joins engagements + duel_attempts; applies cluster-bleed gate | DB integration | `pytest tests/test_top_moments_query.py -x` | Wave 0 |
| REQ-3 | `_call_llm()` returns (text, usage); env-configurable model | unit (mocked) + 1 manual smoke | `pytest tests/test_interpretation_narrative.py::test_call_llm_mock -x` | Wave 0 |
| REQ-4 | Prompt template exists + has D-13 sections | file existence + grep | `pytest tests/test_interpretation_narrative.py::test_prompt_file_present -x` | Wave 0 |
| REQ-5 | Validator catches hallucinated demo/tick/round; passes whitelisted nouns; enforces D-14 anchor | unit + adversarial fixtures | `pytest tests/test_narrative_validator.py -x` | Wave 0 |
| REQ-6 | report_generator integration — happy path + fail-soft | integration test | `pytest tests/test_report_generator.py::test_narrative_inserts -x` + `::test_narrative_fails_falls_back -x` | Wave 0 + extend |
| REQ-7 | Cache table CREATE; content_hash deterministic; PK collision = overwrite | DB schema test + unit | `pytest tests/test_interpretation_narrative.py::test_cache_roundtrip -x` | Wave 0 |
| REQ-8 | Eval CSV exists + ≥10 rows after eval-rate command | file + row count | `pytest tests/test_interpretation_narrative.py::test_eval_csv_schema -x` (manual: ratings filled by user) | Wave 0 + manual |
| REQ-9 | CLI `cost-report` runs and outputs valid totals | CLI smoke | `python -m interpretation_narrative cost-report --db tests/fixtures/test_cache.db` (capture stdout in test) | Wave 0 |
| REQ-10 | Mock LLM raise → fallback to tier table; failure logged | fault injection test | `pytest tests/test_interpretation_narrative.py::test_fail_soft_logs -x` | Wave 0 |
| REQ-11 | Output language Russian; eval set rated in RU | linguistic check (manual SC-1) | manual review per eval row | Wave 0 + manual |

**Hard gate tests (block ship):**
- `test_validator_catches_all_hallucinations[7 fixtures]` — covers SC-2 (0/10 hallucinations on eval set)
- `test_fail_soft_returns_tier_table_only` — covers REQ-10 + SC-5 fall-back path

**Manual gates (cannot automate):**
- SC-1 (eval ≥4.0 avg, ≥3.5 floor) — user rates 10 reports manually
- SC-6 (side-by-side v2 ≥4.0, v1 ≤3.0, delta ≥1.0) — user rates 5 pairs

### Sampling Rate

- **Per task commit:** `pytest -p no:cov -x` (auto via Claude Code hook on `*.py` edit)
- **Per wave merge:** `pytest -p no:cov` (full suite — currently 322 tests, will grow to ~370+)
- **Phase gate:** Full suite green AND eval CSV ≥40 rated rows (10 reports × 4 dims minimum) before `/gsd-verify-work`

### Wave 0 Gaps

- [ ] `tests/test_interpretation_narrative.py` — entry-point tests covering REQ-1, REQ-3, REQ-7, REQ-9, REQ-10
- [ ] `tests/test_narrative_validator.py` — covers REQ-5 + adversarial fixtures
- [ ] `tests/test_top_moments_query.py` — covers REQ-2
- [ ] `tests/fixtures/narrative_responses/*.json` — 7 recorded fixtures (listed in Testing Strategy)
- [ ] Extend `tests/test_report_generator.py` — covers REQ-6 (integration insertion + fail-soft)
- [ ] `tests/conftest.py` — add `_no_real_anthropic` autouse fixture

Framework install: none — pytest 7.4+ already present (verified `requirements.txt`).

## Risks & Landmines

### R-1: PLAYER_NAMES coverage gap (MEDIUM impact, HIGH likelihood)

`config.py:172` PLAYER_NAMES has only 2 entries (donk, karrigan). Memory says DB has 100+ players post Phase 10a backfill. Validator nickname check + prompt context "address by nickname" both depend on PLAYER_NAMES lookup. **Mitigation:** validator nickname check is SOFT (warn, not fail) per Validator Design above. Prompt fallback: if nickname not in dict, use `"player_<short_steamid>"` placeholder. Still satisfies D-10 ("address player by nickname") loosely. **Action:** plan must include task to expand PLAYER_NAMES with at least the 10 eval-roster players (D-15).

### R-2: Round-number backfill cost (MEDIUM impact, MEDIUM likelihood)

5557 engagement rows × ~80 unique demos × ~5min/demo parse = ~6.5h wall-time. Operator-run, blocks downstream eval. **Mitigation:** parallelize via ProcessPool (Phase 10a worktree pattern), OR accept overnight run. Document as operator gate in plan. **Risk:** if some demos no longer on disk (deleted), backfill leaves NULL `round_number` for those rows — top_moments query must handle NULL gracefully (filter `WHERE round_number IS NOT NULL`).

### R-3: Validator false-positive on RU paraphrases (MEDIUM impact, HIGH likelihood)

LLM rephrases "tick 12345" as "тик 12345", "12345-й тик", "около тика 12 345" (with thin space). Strict regex misses some forms → validator throws on first call. **Mitigation:** corpus of fixture rephrasings; iterate regex on adversarial fixtures; accept some FPs in v2 because fail-soft means tier table still ships. R-1 framing in SPEC: "single fake demo reference trains 'this AI is wrong' reaction" — but validator's job is to FAIL on fake refs, even paraphrased. False POSITIVES (rejecting legit text) are less bad than false NEGATIVES (passing fake refs).

### R-4: Cache poison from prompt drift (LOW impact, MEDIUM likelihood)

If `prompt_hash` not stored alongside `content_hash`, prompt change leaves stale narratives in cache. **Mitigation:** include `prompt_hash` in `narrative_cache` PK or как separate column with explicit invalidation logic. Recommended schema (above) adds `prompt_hash TEXT` as non-PK column; cache lookup matches on `(player_steamid, engagement_type, content_hash)` AND verifies `prompt_hash` matches current; mismatch = treat as cache miss.

### R-5: Cyrillic word boundary in regex (MEDIUM impact, LOW likelihood)

Python 3 `re` module treats Cyrillic as word chars by default — `\b` works correctly. Verified by SDK examples + Python re module documentation. **But:** test on adversarial fixture с `тике/тика/тиком` суффиксы. Risk LOW because validator IS SOFT in failure mode (text still produced, just falls back).

### R-6: max_tokens truncation mid-reference (MEDIUM impact, LOW likelihood)

If `max_tokens=2500` ceiling hit mid-output, narrative might end mid-sentence with truncated tick number `"тике 1234"` (real value `12345`). Validator FAILS this as hallucinated tick `1234`. **Mitigation:** detect `stop_reason="max_tokens"` BEFORE validator runs; treat as fail-soft (fall back to tier table). Add explicit branch in `_call_llm()` return path or in `build_narrative_report()` orchestration.

### R-7: ANTHROPIC_API_KEY not set in dev env (LOW impact, HIGH likelihood)

Project is local-only (no cloud). Operator may not have key set on first run. **Mitigation:** `_get_client()` raises `NarrativeBuildError("ANTHROPIC_API_KEY env var not set")` with clear message. CLAUDE.md gets section: "Set `ANTHROPIC_API_KEY` env var before running v2 narrative". Streamlit `app.py` gracefully shows "narrative disabled — set API key" warning if absent (deferred to v2.1 — currently fail-soft just means HTML report ships без narrative section).

### R-8: SteamID64 truncation regression (HIGH impact, MEDIUM likelihood — well-known project trap)

Memory + CLAUDE.md gotcha: `pd.read_sql` casts int64 to float64 → loses precision on 17-digit SteamIDs. **Mitigation:** all top_moments + cache lookups use `cursor.fetchall()` + manual int(row[i]) construction. NEVER pd.read_sql on tables containing player_steamid column. Test fixture must include real 17-digit SteamID to catch regression.

### R-9: report_generator integration silently swallows narrative errors (MEDIUM impact, HIGH likelihood)

`except Exception` is overly broad — could mask real bugs in narrative module (typos, import errors). **Mitigation:** catch ONLY `NarrativeBuildError` + `Exception` separately; re-raise unexpected exceptions in dev (`if os.environ.get("DEV_FAIL_FAST") == "1"`). Production behavior = log + fall back. Existing `report_generator.py` Phase 9 precedent: broad `except Exception` for download button — but THAT was UI-only error surface; narrative is data-pipeline error surface, more hostile to silent swallowing.

### R-10: Eval ratings drift across prompt iterations (MEDIUM impact, MEDIUM likelihood)

User rates report A on prompt v1 = 4.2 avg. Iterate prompt to v2. Re-rate same report on prompt v2 = 4.5 avg. Is the lift real or rater fatigue? **Mitigation:** D-18 says full re-rate, no diff-rate. Document in eval README: "ratings between prompt versions are NOT directly comparable; report rater fatigue if rating session >30 min". Side-by-side SC-6 sidesteps this for the gate.

### R-11: phase-10a worktree merge conflict (LOW impact, MEDIUM likelihood)

Phase 10a worktree has invasive db_utils.py changes (busy_timeout 10000→30000, retry_on_locked decorator, ddm_fits table) NOT yet merged to main. v2 also touches db_utils.py (narrative_cache, round_number column, _ALLOWED_TABLES extension). When 10a eventually merges (or doesn't) → potential conflict. **Mitigation:** keep v2 db_utils edits minimal and explicit (only narrative_cache addition + round_number ALTER). Phase 10a's `_ALLOWED_TABLES = {..., "ddm_fits"}` is incompatible add — v2 should add `"narrative_cache"` to main's existing `{"engagements", "duel_attempts"}`. Memory says 10a NOT merging without further analysis; treat as cold branch for v2 purposes.

## Open Questions for Planner (RESOLVED)

1. **Streamlit cache eviction policy** — `narrative_cache` grows unbounded. After 10k reports, table = ~10MB (acceptable). After 100k, ~100MB starts straining sqlite. v2 SHIP без eviction, log size warning at 50MB. Add `cleanup-cache --older-than 90d` CLI in v2.1?
   **RESOLVED (planner, 2026-05-12):** Defer to v2.1. v2 has no Streamlit narrative panel (out-of-scope per CONTEXT.md). `narrative_cache` grows unbounded in v2; size warning + eviction CLI moved to v2.1 backlog.

2. **Recorded fixture refresh cadence** — fixtures are `claude-sonnet-4-6` outputs at 2026-05-12. Anthropic may swap underlying model weights silently behind the alias (per docs note: "Starting with the Claude 4.6 generation, model IDs use a dateless format that is also a pinned snapshot, not an evergreen pointer"). Risk LOW because pinned snapshot; but if test fixture text divergence appears, refresh fixtures. Plan explicit refresh checkpoint in v2.1?
   **RESOLVED (planner, 2026-05-12):** Refresh manually when SDK major version bumps OR every 6 months, whichever first. Document policy in `tests/fixtures/anthropic_recorded/README.md` (created in W4 alongside fixture-refresh task).

3. **Cost-report time bucketing** — cost-report CLI shows total + last 7d. Need by-day, by-week, by-month breakouts? Defer to v2.1; v2 ships flat total.
   **RESOLVED (planner, 2026-05-12):** v2 ships lifetime total + last 7d only. Per-month bucketing deferred to v2.1.

4. **Refusal handling localization** — `stop_reason="refusal"` triggers fail-soft. Should narrative_failures.log differentiate refusal vs network failure (different operator action — content rewrite vs retry later)? Recommend YES, log includes `failure_kind` enum.
   **RESOLVED (planner, 2026-05-12):** Log refusal reason + `failure_kind` enum in EN to `narrative_failures.log` (operator-facing diagnostic, EN consistent with rest of log). User-facing fallback is silent (tier table only, no localized error surface) — REQ-10 fail-soft semantics already cover this.

5. **Top-moments query — 18 moments × 6 metrics, what if metric has <3 valid moments?** E.g. hold engagement, player has only 5 hits over corpus. fetch_top_moments returns 5 moments not 3. Prompt context shape becomes uneven. Recommend: pad with `None` markers OR (better) document as soft expectation, prompt template handles "if no top moments for metric X, omit reference to X".
   **RESOLVED (planner, 2026-05-12):** Soft expectation. `fetch_top_moments` returns however many qualifying rows exist (may be 0). Prompt template instructs LLM to omit references to metrics without moments. Implemented in plan 02 + plan 03.

6. **Side-by-side v1 reports — how to generate?** `report_generator.generate_html_report()` always inserts narrative if available. Need explicit `narrative=False` flag in v2 to render v1-style report for SC-6 comparison. Single bool param to `generate_html_report()`.
   **RESOLVED (planner, 2026-05-12):** Add `no_narrative: bool = False` param to `generate_html_report()`. Implemented in plan 04 task 1; consumed by plan 05 `generate-side-by-side` CLI.

## Sources

### Primary (HIGH confidence)

- **Anthropic SDK 0.89.0 verified installed** — `python -c "import anthropic; print(anthropic.__version__)"` → `0.89.0`
- **Pricing:** https://platform.claude.com/docs/en/about-claude/pricing — fetched live 2026-05-12. Sonnet 4.6 = $3/$15 + 10% cache reads.
- **Model IDs:** https://platform.claude.com/docs/en/about-claude/models/overview — `claude-sonnet-4-6` (alias = pinned snapshot, no date suffix in 4.6 generation).
- **SDK Messages API + cache_control + retries:** Context7 `/anthropics/anthropic-sdk-python` queried for `prompt caching cache_control system message` and `error handling APIError RateLimitError APIStatusError retry max_retries`.
- **Project source files:** `interpretation.py` (DIRECTIONS, compute_interpretation, cluster-bleed gate at 295-306), `db_utils.py` (idempotent migration pattern, _ALLOWED_TABLES extension precedent), `ddm_analyzer.py:591` (_compute_round_phase + bisect already imported line 19), `report_generator.py:633` (insertion point), `config.py:172` (PLAYER_NAMES sparse).
- **Phase 10a worktree precedent:** `D:\Obsidian\opacity\40_Projects\cs2-ddm-phase-10a\db_utils.py:18` — `_ALLOWED_TABLES` extension + `@retry_on_locked` decorator pattern (NOT pulled into v2; v2 stays minimal).
- **CLAUDE.md gotchas:** SteamID64 truncation, hooks, hold-engagement metrics shape.

### Secondary (MEDIUM confidence)

- WebSearch verifications cross-checked at finout.io / pecollective / benchlm pricing pages — all agree on $3/$15 Sonnet 4.6.

### Tertiary (LOW confidence)

- RU regex word-boundary behavior on Cyrillic suffixes — based on Python 3 `re` standard module behavior; tested experimentally OK but adversarial RU fixtures should confirm during W1.

## Metadata

**Confidence breakdown:**
- Anthropic SDK integration: HIGH — SDK installed, docs verified live, pricing verified live
- File structure / project conventions: HIGH — read source directly, matched existing patterns
- Validator design: MEDIUM — regex patterns sound but RU edge cases require fixture testing
- Schema migration: HIGH — clear precedent in db_utils.py + Phase 10a worktree
- Cost math: HIGH — verified pricing × token estimates conservative
- Eval harness: MEDIUM — DIY pattern matches project precedent, but rating workflow ergonomics untested
- Risks: HIGH — derived from project memory + CLAUDE.md gotchas + observed precedent

**Research date:** 2026-05-12
**Valid until:** 2026-06-12 (30 days; pricing/model IDs may shift on Anthropic side, recheck before major prompt iteration)

## RESEARCH COMPLETE
