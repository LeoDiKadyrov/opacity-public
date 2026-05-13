# Phase v2-interpretation-narrative — Context

**Gathered:** 2026-05-12
**Status:** Ready for planning

<domain>
## Phase Boundary

Phase v2 превращает statistical tier table (Phase 8 output) в prose AI-coach отчёт через LLM layer + per-moment attribution. Adds new narrative block to existing HTML report (`report_generator.py`) без замены tier table. Closes "I would buy it" conversion gap identified in `project_vision_djok` — current report has metrics, not coaching.

</domain>

<spec_lock>
## Requirements (locked via SPEC.md)

**11 requirements are locked.** See `v2-interpretation-SPEC.md` for full REQ-1..11, locked decisions L-1..6, success criteria SC-1..6, and open-question resolutions.

Downstream agents MUST read `v2-interpretation-SPEC.md` before planning or implementing. Requirements are not duplicated here.

**In scope (from SPEC.md):**
- New module `interpretation_narrative.py` with `build_narrative_report()` entry
- Top-N worst+best moments query joining engagements + duel_attempts
- LLM call abstraction (Claude API, sonnet-4-6 default)
- Output validator (hallucination guard)
- Caching layer (`narrative_cache` table in `analytics.db`)
- Integration in `report_generator.py` (narrative between header + tier table)
- Eval set + manual rating harness
- Fail-soft fallback to tier-table-only behavior

**Out of scope (from SPEC.md, defer to v2.1+):**
- Trajectory tracking (weekly snapshots, w-o-w deltas)
- Map/site/role breakdown (per-map metric splits)
- Bilingual EN/RU output split (locked to RU primary)
- DDM integration (dead per [[project_ddm_validation_final_2026_05_12]])
- Streamlit UI narrative panel
- Real-time / in-game coaching

</spec_lock>

<decisions>
## Implementation Decisions

### Attribution Detail (Area 1)

- **D-01:** Round-number upstream extraction IN SCOPE. Add `round_number INTEGER` column to `engagements` table via schema migration. Compute from `round_start` event ticks already parsed by DDMAnalyzer. Adds ~1 day to phase scope.
- **D-02:** Backfill `round_number` for existing 30-player DB via one-shot script `scripts/backfill_round_number.py`. Idempotent (skip rows where already set).
- **D-03:** Top-moments shape — **N=2 worst + N=1 best per metric** = 3 moments × 6 metrics = 18 moments max per report. Best moments enable positive reinforcement in narrative ("vs round 18 ты среагировал 167ms — best").
- **D-04:** Each moment dict carries `{demo_name, t0_tick, map_name, round_number, round_phase, round_time_s, player_value, benchmark_p50, gap_vs_benchmark}`. Source columns already in `engagements` + new `round_number` after D-01.
- **D-05:** Ordering rule — worst-N selected by absolute `gap_vs_benchmark` in direction-of-metric. Best-N selected by inverse-gap (most-below for lower-is-better metrics, most-above for higher-is-better).

### Validator Strictness (Area 2)

- **D-06:** Hybrid validator strategy. Numeric refs (`tick`, `round_number`) — strict exact match against `allowed_refs` set. Common nouns (map names from `engagements.map_name` set, plus locked vocabulary `{"peek", "hold", "aim", "crosshair", "pre-aim", "deathmatch", "DM", "VOD"}`) — whitelist allowed without attribution.
- **D-07:** Single LLM call attempt per report. On validator fail, log to `narrative_failures.log` (reason + raw output for debugging) and fall back to tier-table-only behavior. No retry loop in v2 (cost control).
- **D-08:** `allowed_refs` built per-report = union of (demo_names mentioned in top_moments) + (tick numbers from top_moments) + (round_numbers from top_moments) + (map_names from top_moments) + (player nickname from `PLAYER_NAMES` config) + (locked common-nouns whitelist).
- **D-09:** Validator returns structured `(is_valid: bool, violations: list[dict])` where each violation has `{type, value, context_snippet}`. Logged for prompt iteration.

### Narrative Tone + Length + Structure (Area 3)

- **D-10:** Tone calibration — **brutally honest coach**. Prompt instructs: "Без flattery, без хеджирования. Прямые actionable observations. Address player by nickname. Если данные показывают слабость — называй прямо."
- **D-11:** Output language — Russian (locked via REQ-11). Prompt template + eval rubric + tone calibration all in RU. Eval set rated in RU.
- **D-12:** Length target — **500 words** ± 100. Hard cap in prompt: "Не превышай 600 слов". Cost estimate: ~5k input tokens + ~1.5k output tokens @ sonnet-4-6 = ~$0.08/report (within SC-4 $0.10 budget).
- **D-13:** Structure — fixed sections in markdown:
  ```
  ## Что у тебя получается  (Strength — based on best-N moments)
  ## Где теряешь время  (Weakness — based on worst-N moments + bottleneck)
  ## Action этой недели  (Action — 1-2 concrete next steps from DIRECTIONS pool)
  ```
- **D-14:** DIRECTIONS reference policy — narrative may PARAPHRASE direction body but MUST reference at least one direction by title (e.g., "Запусти Aim_botz before pug") to anchor in existing v1 system. Validator whitelists DIRECTIONS titles set.

### Eval Set Composition + Iteration (Area 4)

- **D-15:** Sample composition — 10 players via tier-mix: 3 top (donk, karrigan, frozen by trial count), 4 mid (twistzz, jcobbb, sh1ro, 1 random from Spirit ≥100 trials), 3 bottom (3 lowest-trial players that still pass min-trials gate from current 30 DB). Locked list stored in `evals/v2_eval_player_roster.json`.
- **D-16:** Rating workflow — single rater (user/Arystan, solo project). Documented solo-rater limitation in eval README. No inter-rater reliability required for v2.
- **D-17:** Rating dimensions — 5 fixed scales (1-5): `factual_accuracy`, `actionability`, `tone`, `attribution`, `hallucinations`. Equal weights for SC-1 ≥4.0 average gate. Per-dimension floor SC-1b ≥3.5 (no single dimension drags average).
- **D-18:** Re-rate strategy — **full re-rate on prompt change**. All 10 reports re-generated + re-rated when `prompts/coaching_v2.md` content_hash changes. Diff-rate deferred to v2.1 if iteration cost becomes painful.
- **D-19:** Eval storage — `evals/interpretation_v2_ratings.csv` with columns `(report_id, player_steamid, prompt_hash, dim, score, notes, rated_at)`. CSV append+dedup by `(report_id, prompt_hash, dim)`.
- **D-20:** Side-by-side SC-6 protocol — 5 reports generated as v1 (current tier table HTML) + v2 (with narrative block) on same players. User rates each on `would_pay_for_this` 1-5 scale. Stored in `evals/v2_side_by_side.csv`. Gate: v2 mean ≥4.0, v1 mean ≤3.0, delta ≥1.0.

### Claude's Discretion

User did not specify these — Claude/planner makes the call:
- Prompt iteration count before ship (no preset; iterate until SC-1 passes)
- Exact CTA/copy in narrative sections (locked by tone D-10 + structure D-13)
- Test-file location convention (follow existing `tests/test_interpretation.py` pattern)
- LLM error retry policy on transient failures (HTTP 5xx, rate limit) — short backoff OK before counting as fail
- Cost-tracking CLI flag naming (`cost-report` vs `report-cost`)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase artifacts (this phase)
- `.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md` — **LOCKED REQUIREMENTS, MUST read before planning.** REQ-1..11 + L-1..6 + SC-1..6 + Q-1..8 + risks
- `.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md` — this file (D-01..20)

### Existing code (modification targets)
- `interpretation.py` — current 427 LOC tier+directions+bottleneck layer; v2 wraps this without replacing
- `report_generator.py` — current 667 LOC HTML report builder; v2 inserts narrative block between header + tier table
- `db_utils.py` — extend `_ALLOWED_TABLES` to include `narrative_cache` (per Phase 10a precedent in worktree)
- `ddm_analyzer.py` — `round_start` event parsing already present (`_compute_round_phase`); extract `round_number` here too

### Schema references
- `analytics.db` engagements table (current schema): see `.planning/codebase/ARCHITECTURE.md` CSV Schemas section
- `analytics.db` duel_attempts table (current schema): see `.planning/codebase/ARCHITECTURE.md` line 104+

### Codebase maps (read 2-3 most relevant)
- `.planning/codebase/ARCHITECTURE.md` — DDMAnalyzer + T0Detector + DuelAttemptFinder structure (CSV schemas at line 125+)
- `.planning/codebase/INTEGRATIONS.md` — NO external integrations exist yet; v2 is FIRST cloud API integration (Anthropic Claude API)
- `.planning/codebase/STACK.md` — Python 3.14 + demoparser2 + pandas; add `anthropic>=0.40` dependency

### Memory (Claude private memory — read for product context)
- `project_vision_djok` — "I would buy it" gap = v2 motivation
- `project_ddm_validation_final_2026_05_12` — DDM dead, do not re-introduce
- `feedback_user_delegates_principled_judgment` — execute, не задавай меню повторно
- `feedback_language` — RU primary (NOT Ukrainian, NOT mixed)

### Project-level
- `.planning/PROJECT.md` — core value "не просто метрики, а специфический инсайт"
- `.planning/STATE.md` — v1.0 archived, v1.1 not yet planned
- `.planning/ROADMAP.md` — v1.1 milestone TBD (phase belongs here once roadmap promoted)

### Future artifacts (created during execution)
- `interpretation_narrative.py` (new module)
- `prompts/coaching_v2.md` (versioned LLM prompt template)
- `evals/v2_eval_player_roster.json` (10-player locked roster)
- `evals/interpretation_v2_ratings.csv` (rating data)
- `evals/v2_side_by_side.csv` (SC-6 data)
- `scripts/backfill_round_number.py` (one-shot migration)
- `tests/test_interpretation_narrative.py`
- `tests/test_narrative_validator.py`
- `tests/test_top_moments_query.py`
- `narrative_failures.log` (runtime, gitignored)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets

- **`compute_interpretation(db_path, player_steamid, benchmark_steamid, engagement_type) → list[dict]`** (`interpretation.py:261`) — current tier-table builder. v2 consumes its `rows` output unchanged as input to `build_narrative_report()`.
- **`get_worst_metric(rows) → Optional[dict]`** (`interpretation.py:422`) — already finds worst row; can be reused or generalized to N-worst.
- **`DIRECTIONS` dict** (`interpretation.py:61`) — 3 directions per (metric, engagement_type). v2 narrative references at least 1 direction by title per D-14.
- **`PLAYER_NAMES` config** (`config.py`) — SteamID → nickname lookup, used in tone calibration D-10 ("address by nickname").
- **`db_utils.save_to_db()` with `_ALLOWED_TABLES` whitelist** — extension pattern shipped in Phase 10a worktree (commit `66b4b76` precedent); apply same for `narrative_cache`.
- **`report_generator.py` markdown embedding** — already converts markdown sections to HTML; narrative block uses same pipeline.
- **`PLAYER_NAMES` + `assign_tier()` logic** — narrative prompt context includes tier per metric verbatim from tier-table output.

### Established Patterns

- **Cluster-bleed gate** (`interpretation.py:295-306`) — drops `rt_visible_to_hit_ms > T0_TO_T2_MAX_MS` rows. Top-moments query MUST apply same filter (D-04 moments come from filtered subset).
- **`pd.read_sql` SteamID truncation pitfall** (CLAUDE.md gotcha) — use `cursor.fetchall()` for SteamID columns in `fetch_top_moments()`.
- **Test pattern** — TDD with `tests/test_interpretation.py` precedent (322 tests existing). v2 follows same: RED → GREEN → commit per task.
- **Hook-driven format** — `*.py` edits auto-run black + ruff + pytest. New module must pass pre-commit.

### Integration Points

- **`report_generator.py:generate_html_report()`** — entry where narrative block embeds. Wrap existing tier-table rendering: `narrative_md = try_build_narrative(...); if narrative_md: prepend before tier_table_html`.
- **`db_utils.py:init_db()`** — add `narrative_cache` CREATE TABLE statement; add `round_number` column migration to engagements (idempotent ALTER TABLE).
- **`config.py`** — add `LLM_PROVIDER`, `LLM_MODEL` env var defaults; add common-nouns whitelist constant.
- **`app.py` Streamlit** — no UI changes for v2 (out of scope). HTML report download button already exists from Phase 9.

</code_context>

<specifics>
## Specific Ideas

- **Tone reference example** (user 90_Meta + memory): inline "Вердикт: ..." review pattern. Narrative may use similar bracketed verdict callouts inside sections.
- **Length comparison**: 500 words ≈ this CONTEXT.md `<decisions>` section length. Verifiable target.
- **Brutally honest exemplar**: see [[feedback_validation_spike_routing_pattern]] — pattern is "name the failure mode directly, propose path, не disclaimer-ship". Narrative should match that voice.
- **Failure framing**: when player's metric is bad, narrative says "Твой T1→T2 = 380ms, Average tier. У донка 312ms. Разница не в врождённой aim speed — это myth. Разница в pre-aim discipline и trigger commitment". Educate while diagnosing.
- **No magic-number language** in narrative (per `config.py` codebase rule) — refer to tiers/percentages, not raw thresholds (those belong in tier-table data).

</specifics>

<deferred>
## Deferred Ideas

- **Trajectory tracking (weekly snapshots, w-o-w deltas)** — separate phase v2.1. Needs new `narrative_snapshots` table + cron/scheduled aggregation. High retention value but doubles scope.
- **Per-map / per-site breakdown** — separate phase. Needs map+site detection in DDMAnalyzer + revised tier thresholds per map. PROJECT.md flags "needs more data first".
- **Bilingual EN translation** — v2.1+. Adds eval cost (rate 2 languages × 10 reports per iteration).
- **Streamlit UI narrative panel** — v2 only ships HTML report integration. Streamlit live narrative = separate phase if user demand emerges.
- **Cohort percentile phrasing** ("better than 67% of FACEIT-8") — separate phase, requires FACEIT-tier mapping for DB players (not currently available).
- **Confidence framing** ("based on 47 peeks, high confidence") — could fold into v2 prompt context as "n_engagements" caveat for tone modulation, but explicit UI surface = v2.1.
- **LLM-generated drill prescription** (replace static DIRECTIONS with generated drills) — different risk profile (more hallucination surface, no validator anchor), defer to post-v2 evaluation.
- **DDM (EZ-Diffusion) integration** — dead per `project_ddm_validation_final_2026_05_12`. Do not re-introduce in v2.

### Reviewed Todos (not folded)

None — `gsd-sdk query todo.match-phase` returned 0 matches for this phase.

</deferred>

---

*Phase: v2-interpretation-narrative*
*Context gathered: 2026-05-12*
