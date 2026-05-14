# SPEC — Phase v2-interpretation-narrative

**Status:** DRAFT (ambiguity ~0.30, run `/gsd-discuss-phase v2-interpretation-narrative` to resolve open questions before `/gsd-plan-phase`)
**Created:** 2026-05-12
**Author:** Arystan (drafted by Claude)

## Goal

Convert `compute_interpretation` output (rows with tier/gap/directions) into prose coaching report via LLM layer + per-engagement attachment. Closes the "I would buy it" gap identified in [project vision: Djok](../../../C:/Users/Leo/.claude/projects/D--Obsidian-opacity-40-Projects-cs2-ddm/memory/project_vision_djok.md) — current interpretation produces a tier table; users want narrative coaching with attribution to specific moments in their own demos.

## Motivation

Current `interpretation.py` (427 LOC, shipped Phase 8 2026-05-07) produces:
- 6 metrics × tier (Elite/Good/Average/Work needed) vs benchmark p25/p50/p75
- 3 DIRECTIONS per metric (Demo review / DM / VOD / aim_botz templates)
- Bottleneck detection (T0→T1 vs T1→T2 tier comparison)

**Gaps preventing conversion:**

1. Generic templates — "Watch your last 5 deaths" is advice, not coaching. A coach says "demo X round 14 on A site you pre-aimed dark, should have been upper window — here's that frame."
2. Snapshot, not trajectory — static tier table without progression has no retention loop.
3. Tier-as-label, no story — "Average" means nothing without narrative context.
4. No per-engagement attribution — metrics float as aggregates, not tied to real moments.
5. Weak confidence framing — 12 vs 200 peeks give very different reliability; user can't see.
6. No cohort-relative phrasing — "Average" is opaque; "better than 67% of FACEIT-8" is clear.

This phase tackles #1 + #4 (narrative + attribution). Trajectory (#2) and cohort phrasing (#6) deferred to v2.1.

## In scope

- New module `interpretation_narrative.py` exposing `build_narrative_report(rows, top_moments, player_context) → str` (markdown)
- Top-N worst moments query — joins `engagements` + `duel_attempts`, sorts by gap vs benchmark, attaches `(demo_name, tick, round_number, map_name)` per metric
- LLM call abstraction (Claude API via `anthropic` SDK)
- Output validator (hallucination guard)
- Caching layer (avoid re-call per same data hash)
- Integration into `report_generator.py` — narrative block between header and tier table
- Eval set + manual rating harness
- Fail-soft fallback to existing tier-table behavior on LLM/validator failure

## Out of scope (defer to v2.1+)

- Trajectory tracking (weekly snapshots, week-over-week deltas) — separate phase
- Map/site/role breakdown (per-map metric splits) — separate phase
- Bilingual EN/RU output split — locked to RU primary in REQ-11
- DDM integration — dead per [project DDM validation final 2026-05-12](../../../C:/Users/Leo/.claude/projects/D--Obsidian-opacity-40-Projects-cs2-ddm/memory/project_ddm_validation_final_2026_05_12.md)
- Streamlit UI narrative panel — HTML report only for v2
- Real-time / in-game coaching surface

## Requirements (falsifiable)

**REQ-1.** Module `interpretation_narrative.py` exports `build_narrative_report(rows: list[dict], top_moments: dict[str, list[dict]], player_context: dict) → str`. Returns markdown string. Input `rows` comes from existing `compute_interpretation()`; `top_moments` keyed by metric name; `player_context` has `{player_steamid, player_name, engagement_type, n_total_engagements}`.

**REQ-2.** `fetch_top_moments(db_path, player_steamid, metric, engagement_type, n=3) → list[dict]` returns N worst (by direction-of-metric) engagements joined to duel_attempts. Each dict has `{demo_name, tick, round_number, map_name, player_value, benchmark_p50, gap}`. Excludes rows flagged by cluster-bleed gate (per existing `interpretation.py:295-306`).

**REQ-3.** LLM call abstracted via single function `_call_llm(prompt: str, max_tokens: int) → tuple[str, dict]` returning `(text, usage_metadata)`. Default provider Claude API, model `claude-sonnet-4-6`. Provider + model configurable via env vars `LLM_PROVIDER`, `LLM_MODEL`.

**REQ-4.** Prompt template stored at `prompts/coaching_v2.md` (versioned in repo). Contains:
- Structured context block (player tier per metric + top moments + benchmarks + caveats)
- Explicit "do not invent demo events, ticks, rounds, maps — only reference items from input" instruction
- Tone calibration ("brutally honest coach, no flattery, actionable specifics, address player by name")
- Output format spec (markdown headings, max ~500 words — see Q-4)

**REQ-5.** Output validator `validate_narrative(text: str, allowed_refs: set[str]) → tuple[bool, list[str]]`. Builds `allowed_refs` from `top_moments` (demo_names, tick numbers, round numbers, map names). Validates every demo_name / tick / round / map mentioned in text exists in `allowed_refs`. Returns `(is_valid, list_of_violations)`. Strictness rules locked via Q-3.

**REQ-6.** `report_generator.py` integration — narrative block embedded between report title and tier table. Falls back to current behavior if `build_narrative_report` raises OR validator returns `is_valid=False`. Fallback logged to `narrative_failures.log`.

**REQ-7.** Caching schema — new SQLite table `narrative_cache` in `analytics.db`:
```sql
CREATE TABLE narrative_cache (
  player_steamid INTEGER NOT NULL,
  engagement_type TEXT NOT NULL,
  content_hash TEXT NOT NULL,
  narrative_md TEXT NOT NULL,
  model TEXT NOT NULL,
  tokens_in INTEGER,
  tokens_out INTEGER,
  generated_at TEXT NOT NULL,
  PRIMARY KEY (player_steamid, engagement_type, content_hash)
);
```
`content_hash = sha256(json(rows) + json(top_moments))`. Re-call only when hash changes.

**REQ-8.** Eval set — 10 sample reports generated (10 distinct players from current DB). Each manually rated by user on 1-5 scale across 5 dimensions: `factual_accuracy`, `actionability`, `tone`, `attribution`, `hallucinations`. Ratings stored `evals/interpretation_v2_ratings.csv` with columns `(report_id, player_steamid, dim, score, notes, rated_at)`.

**REQ-9.** Cost telemetry — per-call token usage logged to `narrative_cache` (REQ-7). CLI utility `python -m interpretation_narrative cost-report` shows total tokens + estimated USD cost since launch (per-model pricing constant in module).

**REQ-10.** Fail-soft — if LLM call raises (network, rate-limit, content policy) OR validator returns `is_valid=False`, log incident with reason to `narrative_failures.log`, return existing tier-table-only behavior. User-visible report never broken by narrative layer.

**REQ-11.** Output language = Russian (primary user is Arystan, manual workflow per [project landing strategy](../../../C:/Users/Leo/.claude/projects/D--Obsidian-opacity-40-Projects-cs2-ddm/memory/project_landing_strategy.md)). Prompt template + eval set both in RU. EN translation = v2.1 scope.

## Success criteria (hard gates)

**SC-1.** Eval set average score ≥4.0/5 across all 5 dimensions on 10 reports (REQ-8). Per-dimension breakdown must show no single dimension <3.5/5. **(Hard gate for ship.)**

**SC-2.** 0/10 reports contain hallucinated references — validator catches all on eval set. **(Hard gate.)**

**SC-3.** ~~P95 generation time ≤30s per report (cold-cache, single LLM call). Cached call ≤100ms.~~ **DEFERRED 2026-05-13** — under Path B (Claude Code Max subscription via `claude -p` subprocess, see L-1 amendment) cold-call wall is 60-180s with no `cache_control` lever. Operator workflow at this stage is manual: user submits demo via landing → owner runs tool locally → report delivered within 48h. Speed not user-facing. SC-3 reactivates when project migrates to self-serve API (Anthropic SDK direct) at hosting/payment milestone. **(Not a ship gate at v2.)**

**SC-4.** ~~Cost ≤$0.10 per fresh report at default model (~5k input tokens, ~1.5k output @ sonnet-4-6 pricing).~~ **INFORMATIONAL under Path B** — Max sub absorbs token spend at flat rate. Cost telemetry preserved (`narrative_cache.usage_json`) for future migration; gate not enforced.

**SC-5.** Fall-back rate ≤5% on 50-report stress sample (LLM failures + validator rejections combined). Validates REQ-10 is rare path, not common.

**SC-6.** Side-by-side comparison — 5 reports v1 (tier table only) vs v2 (narrative + table) on same players. User rates "would_pay_for_this" 1-5 scale on each. v2 average ≥4.0, v1 average ≤3.0, delta ≥1.0. **(Hard gate — validates the "I would buy it" thesis.)**

## Locked decisions

- **L-1.** LLM provider = Claude API (anthropic SDK). No local LLM, no OpenAI for v2.
- **L-2.** Model default = `claude-sonnet-4-6` (quality/cost balance). `claude-opus-4-7` available as override via `LLM_MODEL` env var.
- **L-3.** Output format = markdown (renders in HTML report via existing markdown pipeline in `report_generator.py`).
- **L-4.** Language = Russian primary (REQ-11).
- **L-5.** No tool use / function calling in LLM call — single prompt → single completion. Anthropic prompt caching enabled for the static system prompt block.
- **L-6.** Caching is mandatory for shipping — REQ-7 not optional. Without it cost/latency unbounded.

## Open questions (resolve in `/gsd-discuss-phase`)

- **Q-1.** Top-N moments per metric — N=3, 5, or adaptive? Tradeoff: prompt context size vs richness for narrative.
- **Q-2.** Map name + round number — already present in `engagements` table, or requires upstream `ddm_analyzer` change? If absent, attachment scope expands and gates upstream work. **Critical: blocker if missing.**
- **Q-3.** Validator strictness — fail on any not-in-allowed-refs string match, or whitelist common nouns ("Mirage" mentioned generically without round attribution)? Strict = more false rejections; lax = harder to catch real hallucinations.
- **Q-4.** Narrative length cap — 300 / 500 / 800 words? Too short = trivial; too long = TL;DR.
- **Q-5.** Should narrative reference `DIRECTIONS` array verbatim or paraphrase? Verbatim = coherence with v1 + cheaper LLM; paraphrase = more personalized, more hallucination risk.
- **Q-6.** Eval rating — user-only or need ≥2 raters for inter-rater reliability? Solo project, likely user-only OK, but document the limitation.
- **Q-7.** New player edge case — n_engagements < 20 (very few demos): generate narrative with explicit caveat, or skip narrative and fall back to tier table?
- **Q-8.** Prompt versioning strategy — `prompts/coaching_v2.md` versioned in git, but how do we re-generate eval set when prompt changes? Re-rate all 10? Diff-rate (only re-rate reports that changed)?

## Risks

- **R-1.** Hallucination harms trust — a single fake demo reference trains "this AI is wrong like the others" reaction. Mitigation: REQ-5 hard validator + SC-2 hard gate.
- **R-2.** Cost balloon — 1000 reports/month × $0.10 = $100. Acceptable at current scale, but at 10k/mo → $1k. Mitigation: REQ-7 mandatory caching, REQ-9 monitoring, alert if monthly cost crosses threshold (out of scope for v2 alerting itself).
- **R-3.** Generic output — LLM may produce prose wrappings of the same templates ("Watch your peeks in your recent demos..."). Mitigation: SC-1 eval gate + REQ-4 prompt explicitly demands tick/round-level attribution.
- **R-4.** Vendor lock — Claude API outage → 100% fallback rate. Mitigation: REQ-3 abstraction means swap provider in one function.
- **R-5.** Russian output quality — sonnet-4-6 RU may be weaker than EN. Mitigation: RU explicit in REQ-11; eval set in RU forces SC-1 to catch RU-specific issues.
- **R-6.** Map/round data absent (Q-2) — invalidates attribution premise. Mitigation: discuss-phase resolves before plan-phase commits.
- **R-7.** Eval set bias — user rating own product. Mitigation: documented as solo-rater limitation (Q-6); use side-by-side SC-6 (forced choice) to reduce halo bias.

## Self-scored ambiguity

**~0.30 (MEDIUM)**.

Most uncertainty concentrated in Q-2 (data availability is a hard blocker if missing) and Q-4 (length cap materially shapes prompt design). Q-3, Q-7 are calibration questions, not blockers.

**Recommend** running `/gsd-discuss-phase v2-interpretation-narrative` to resolve Q-1..Q-8 before `/gsd-plan-phase`.

## Cost estimate

- Plan + execution: **3-5 days** (1 day eval set generation infrastructure, 1-2 days prompt iteration, 1 day integration + testing, 0.5 day docs)
- One-time API cost: ~$5-10 on eval set generation + prompt iteration
- Recurring per-user cost: ~$0.10/report (per SC-4)

## Linked artifacts

- Current code: `interpretation.py` (427 LOC), `report_generator.py` (667 LOC)
- Existing tests: `tests/test_interpretation.py`, `tests/test_report_generator.py`
- Memory (project vision): `project_vision_djok.md`
- Memory (DDM exclusion context): `project_ddm_validation_final_2026_05_12.md`
- Memory (landing strategy): `project_landing_strategy.md`
- Future artifacts: `prompts/coaching_v2.md`, `evals/interpretation_v2_ratings.csv`, `interpretation_narrative.py`, `tests/test_interpretation_narrative.py`

## Glossary

- **Narrative report** — prose markdown coaching block produced by LLM, attached to existing tier table.
- **Top moments** — N worst-performing engagements per metric, attributed to specific demo / tick / round / map.
- **Attribution** — referencing specific real demo events in the narrative (vs generic templates).
- **Hallucination** — narrative mentioning a demo/tick/round/map that does not exist in the input data.
- **Tier table** — existing Phase 8 output: 6 metrics × {Elite, Good, Average, Work needed}.
