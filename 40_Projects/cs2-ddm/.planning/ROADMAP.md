# Roadmap: Djok — CS2 Reaction Analysis

## Overview

Brownfield project: Phases 1–5c and the Kill-Rate feature are shipped (BVH T0 detection, bulk pipeline, velocity/weapon filters, crosshair angle, DuelAttemptFinder). Remaining work is four phases: quality gates + schema migration to make data trustworthy at scale, parallel batch runner to accumulate 100+ donk demos, an interpretation layer that converts metrics into actionable coaching, and B2C delivery that puts it in front of paying users.

## Milestones

- ✅ **v0.x Analysis Engine** — Phases 1–KR (shipped 2026-04-30)
- ✅ **v1.0 Djok MVP** — Phases 6, 7, 8, 9, 9.1 (shipped 2026-05-07) — see [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md), [v1.0-MILESTONE-AUDIT.md](v1.0-MILESTONE-AUDIT.md)

## Phases

<details>
<summary>✅ v0.x Analysis Engine (Phases 1–KR) — SHIPPED 2026-04-30</summary>

- [x] **Phase 1: CSV Pipeline** — Append/dedup CSV output with match_id integrity
- [x] **Phase 2: BVH T0 Detection** — BVH+AABB geometric first-visibility detection
- [x] **Phase 3: T0→T1→T2 Benchmark** — Manual validation on 6 moments, 3 critical bugs fixed
- [x] **Phase 4: Bulk Pipeline** — auto_build_moments from player_hurt clusters
- [x] **Phase 5: Velocity Filter + Dashboard** — peek/hold classification, Streamlit dashboard
- [x] **Phase 5b: Weapon + Enemy Velocity Gate** — AWP/knife exclusion, enemy velocity filter
- [x] **Phase 5c: Crosshair Angle** — crosshair_angle_at_t0_deg column, 215 tests
- [x] **Kill-Rate Feature** — DuelAttemptFinder, T0-anchored kill rate, kill_rate_analysis.py

</details>

<details>
<summary>✅ v1.0 Djok MVP (Phases 6, 7, 8, 9, 9.1) — SHIPPED 2026-05-07 — see <a href="milestones/v1.0-ROADMAP.md">milestones/v1.0-ROADMAP.md</a></summary>

22/22 plans, 215 → 330 tests. End-to-end Djok delivery operational. SC1/SC2 of Phase 9 (public deploy + FACEIT URL) deferred to Phase 10. Audit: [v1.0-MILESTONE-AUDIT.md](v1.0-MILESTONE-AUDIT.md).

</details>

## Phase Details

### Phase v2: Interpretation narrative (LLM coaching layer)

**Goal:** Convert compute_interpretation tier-table output into prose AI-coach report (RU) via Anthropic Claude API + per-engagement attribution. Closes the "I would buy it" gap from project_vision_djok — current report has metrics, not coaching.

**Plans:** 7 plans (W0 baseline → W1 validator + LLM client → W2 prompt + report integration → W3 eval harness → W4 manual SC-1/SC-6 ratings).

Plans:
- [ ] v2-interpretation-00-PLAN.md — DB schema (round_number + narrative_cache) + test infra (no-real-API guard, 7 fixtures) + backfill script skeleton
- [ ] v2-interpretation-01-PLAN.md — narrative_validator.py (REQ-5, hallucination guard, D-14 anchor)
- [ ] v2-interpretation-02-PLAN.md — interpretation_narrative.py (fetch_top_moments + _call_llm + cache I/O + build_narrative_report)
- [ ] v2-interpretation-03-PLAN.md — prompts/coaching_v2.md + PLAYER_NAMES expansion (D-15 roster)
- [ ] v2-interpretation-04-PLAN.md — report_generator.py integration + fail-soft + no_narrative toggle
- [ ] v2-interpretation-05-PLAN.md — eval CLI (cost-report, eval-rate, generate-eval-set, score, side-by-side, record-fixture) + roster JSON + README
- [ ] v2-interpretation-06-PLAN.md — manual SC-1 + SC-6 gate execution + backfill + fixture refresh + CLAUDE.md update

**Requirements:** REQ-1..11 (locked in v2-interpretation-SPEC.md)

**Success criteria (hard gates):** SC-1 eval ≥4.0 avg + ≥3.5 floor; SC-2 0/10 hallucinations caught; SC-3 P95 ≤30s; SC-4 ≤$0.10/report; SC-5 fall-back ≤5%; SC-6 side-by-side delta ≥1.0.

**Linked artifacts:**
- SPEC: `.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md`
- CONTEXT: `.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md` (D-01..20)
- RESEARCH: `.planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md`
- PATTERNS: `.planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md`
- VALIDATION: `.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md`

---

### Phase 10: T1 detection fix batch (B-1 + B-4)

**Goal:** Eliminate the 125ms hard floor on `rt_visible_to_aim_ms` (B-1: `T1_GRACE_MS=120` redundant filter) and the silent pre-aim censorship (B-4: `T1_NOT_AIMED_THRESHOLD=1.0°` drops best engagements to NaN). Per REVIEW-2026-05-16.md these MUST ship together — fixing only one leaves the other class of distribution distortion intact. Blocks public re-posting (donk 172ms / m0NESY 203ms numbers currently artifact-compromised).

**Scope (in):**
1. `T1_GRACE_MS = 0` in `config.py` (or remove grace logic from `_detect_t1`); keep `moving_towards + sustained + sig_change` semantic chain intact
2. Pre-aimed branch in `ddm_analyzer._detect_t1`: when `curr_dist ≤ T1_NOT_AIMED_THRESHOLD` at T0+grace with no significant correction → set T1=T0, `rt_visible_to_aim_ms=0`
3. Optional: new column `t1_source ∈ {"sustained_aim", "pre_aimed"}` for downstream visibility (B-4 makes the branch explicit in DB)
4. Rewrite `tests/test_ddm_analyzer_t1.py::test_t1_grace_period_excludes_early_ticks` — currently asserts buggy behaviour (`T1=NaN` when aim happens before grace); must assert grace-removed behaviour
5. New `tests/test_ddm_analyzer_t1.py::test_t1_pre_aimed_returns_t0` — coverage for B-4 branch
6. Empirical validation: run pipeline on 1 reference demo (e.g. donk-furia-m3-nuke), query T0→T1 min / p10 / median; assert no pinning at 125ms (or at any tick-quantum value) and left tail present
7. `grace_experiment.py` cross-check: production behaviour matches the `grace=0` variant of the 3-variant comparison

**Out of scope (later phases):**
- B-2 (DuelAttemptFinder is_alive gate) — separate pipeline, Phase A item 3
- B-3 (`find_first_visible_enemy_in_window` flash gate) — separate pipeline, Phase A item 4
- Full corpus re-batch — gated on this phase shipping (Phase A item 6)
- Threshold re-derivation (`_ABSOLUTE_ELITE_CEILING`, `_FALLBACK_THRESHOLDS`) — needs clean re-batched data (Phase A item 7)
- Distribution-shape regression suite (`tests/test_distribution_shape.py`) — Phase A item 5, separate phase
- W-3 fix (`T1_MOVING_TOWARDS_TOLERANCE`) — Phase B per REVIEW

**Success criteria (hard gates):**
- SC-1: `T1_GRACE_MS=0` (or removed) shipped; `test_t1_grace_period_excludes_early_ticks` rewritten
- SC-2: Pre-aimed branch shipped; `test_t1_pre_aimed_returns_t0` green
- SC-3: All existing tests pass (367+ pre-fix → 368+ post-fix)
- SC-4: Single demo re-analysis shows T0→T1 distribution unflattened — `min < 125ms`, no value pinning >10% of N at any tick-quantum
- SC-5: `grace_experiment.py` output validates production = `grace=0` variant

**Plans:** 3 plans (Wave 0 test rewrite + frozen baseline → Wave 1 code fixes → Wave 2 manual gates).

**Status:** SHIPPED 2026-05-16 — all 5 SCs PASS. 11 commits across 3 waves (99cb296..801f722). 370/370 pytest GREEN. SC-4 single-demo (5-pro subset of dust2): min=0.0ms, n_at_125ms=0, n_pre_aimed=n_with_flag=2. SC-5 grace=0 parity %@125ms delta=0.0pp. Full corpus re-batch (Phase A item 6) gated AFTER this ship before any marketing claim refresh.

Plans:
- [x] 10-00-PLAN.md — Wave 0: rewrite 2 T1 tests + add 5 new RED tests + freeze pre-fix grace_experiment baseline (SHIPPED 2026-05-16)
- [x] 10-01-PLAN.md — Wave 1: T1_GRACE_MS=0 + _detect_t1 pre-aim branch + t1_source schema migration + full pytest GREEN (SHIPPED 2026-05-16)
- [x] 10-02-PLAN.md — Wave 2: /check-phase6 gate + SC-4 single-demo distribution + SC-5 grace_experiment parity diff (SHIPPED 2026-05-16)

**Linked artifacts:**
- Audit: `.planning/REVIEW-2026-05-16.md` (BLOCKER section B-1 + B-4, Phase A items 1-2)
- Brief: `.planning/CODE_REVIEW_BRIEF_2026_05_16.md`
- DB evidence: `memory/project_t1_grace_floor_bug_2026_05_16.md` (1145 engagements pinned at 8-tick delta; 25-43% per-pro pinning rate)
- Methodology principle: `memory/feedback_redundant_grace_filter_creates_floor_artifact_2026_05_16.md`
- Pattern (B-4): `memory/feedback_pre_aim_censorship_inverse_survivorship.md`
- Validation tooling: `grace_experiment.py` (3-variant in-memory experiment)

---

(All v1.0 phase details archived to [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md). Future phase details live here as they're added.)

## Progress

| Milestone | Phases | Plans | Status | Completed |
|-|-|-|-|-|
| v0.x Analysis Engine | 1, 2, 3, 4, 5, 5b, 5c, KR | — | Shipped | 2026-04-30 |
| v1.0 Djok MVP | 6, 7, 8, 9, 9.1 | 22/22 | Shipped | 2026-05-07 |
| v1.1 — Phase v2 narrative | v2-interpretation-narrative | 0/7 | Planned | — |


## Proposed next phases (candidates for v1.1)

### Phase 10a: DDM (EZ-Diffusion) data collection infra (CANDIDATE — surfaced by /gsd-explore 2026-05-08)

**Goal:** Build EZ-Diffusion DDM compute + persistence machinery into the analysis pipeline. Compute drift rate `v`, threshold `a`, and non-decision time `t_er` per player × engagement_type per session, persist to new `analytics.db` columns. **No user-facing UI surface.** Internal admin-only inspection only.

**Motivation:** `/gsd-explore` 2026-05-08 evaluated DDM as a coaching feature for cs2-ddm. Spike `bench/ez_pc_validation.py` proved EZ math works (synthetic recovery |bias| ≤4%) but bootstrap stability fails universally at current data scale (CI95 width / point = 0.30 to 5.33 vs ≤0.30 SPEC). Direct user-facing DDM ship would surface noise as advice → trust collapse risk. Phase 10a builds the machinery without exposing it, accumulating per-session DDM rows passively while users keep using validated tier'ы. Speeds up convergence to the DB scale needed for Phase 10b unlock.

**Scope:**
1. Promote EZ-Diffusion math (`ez_diffusion()`, edge correction, scale `S=0.1`) from `bench/ez_pc_validation.py` to a reusable module (e.g. `ddm_compute.py`)
2. Hook into existing aggregation pipeline — compute v/a/t_er per (player_steamid, engagement_type, session_id, Pc_definition)
3. Schema migration: new table `ddm_fits` (player_steamid, engagement_type, session_id, pc_definition, n_trials, pc, v, a, t_er, ci95_width_ratios, computed_at)
4. Capture multiple Pc candidates simultaneously (`pc2_won_duel`, `pc3c_crosshair_lt_8deg` are the YELLOW candidates from spike) — don't lock Pc choice until 10b
5. Internal admin-only Streamlit page or CLI dump for inspecting DDM fit values
6. Tests: TDD against synthetic-recovery harness from spike (re-use simulator)

**Out of scope (deferred to Phase 10b):**
- Any user-facing UI surface for DDM
- Any DDM-derived coaching insight in `interpretation.py`
- Cross-player comparisons / archetype clustering (= Угол B seed)
- Deception-scenario splits (= Phase 999.3 backlog)
- Locking the Pc definition

**Phase 10b unlock criteria (gating):**
1. analytics.db has ≥30 distinct players with ≥50 engagements per engagement_type
2. Spike re-run (`bench/ez_pc_validation.py` or successor) returns GREEN on at least one Pc
3. Stability CI95 width / point ≤0.30 on all 3 params for at least one Pc
4. Discriminant validity confirmed across more than 2 players (population-level)
5. Convergent validity testable (population corr `v` vs hit_rate ∈ [0.3, 0.75])

**Risks:**
- Schema migration on existing analytics.db needs idempotency
- Per-session segmentation may produce per-cell N too small even at large N/player → may need session-aggregation strategy (sliding window, monthly bins)
- DDM compute cost per demo run — should be near-free (closed-form, ms-scale) but verify

**Requirements:** TBD (will materialize via `/gsd-spec-phase` and `/gsd-discuss-phase`)
**Plans:** 0 plans

Plans:
- [ ] TBD (start with `/gsd-spec-phase` when ready to commit to Phase 10a)

**Linked artifacts:**
- Exploration note: `.planning/notes/ddm-exploration-2026-05-08.md`
- Spike spec: `.planning/spikes/ez-pc-validation/SPEC.md`
- Spike result: `bench/EZ_PC_RESULTS.md`
- Spike code (graduates to `ddm_compute.py`): `bench/ez_pc_validation.py`
- Seed (Phase 10b unlock dependency): `.planning/seeds/ddm-archetype-clustering.md`
- Backlog (post Phase 10b): Phase 999.3 — DDM deception-scenario t_er splits

---

## Backlog

### Phase 999.1: parse_ticks selective window optimization (BACKLOG — SUPERSEDED by Phase 9.1 SC3)

**Goal:** Pass `ticks=` parameter to `parse_ticks()` for early exit instead of parsing entire demo. Only parse tick windows around `player_hurt` anchors (±300 ticks per engagement).
**Motivation:** Current code reads 100k ticks per demo. Only ~9k ticks actually needed (~15 windows × 600 ticks). Theoretical ~10x speedup on tick parsing step. demoparser2 already supports this natively.
**Implementation sketch:**
1. First pass: `parse_event("player_hurt")` → get anchor ticks (already fast, no change)
2. Second pass: `parse_ticks(props, ticks=list(range(start-300, start+600)))` per engagement window
3. Merge per-window DataFrames instead of slicing one giant DataFrame
**Risks:** Multiple `parse_ticks` calls may have per-call overhead; benchmark first.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.2: Profile-driven hot-path optimization (BACKLOG — surfaced by Phase 9.1 SC5 miss)

**Goal:** Identify and optimize the actual cold-cache `analyze_demo()` walltime hot path. Phase 9.1 delivered 1.08× because the optimized paths (parse_events batch, selective parse_ticks, ticks_by_sid cache, AABB ordering) are <30% of total walltime. The dominant unprofiled load is `find_visible_enemies_at_tick` BVH raycast loops (per-tick, expensive) and `.tri` mesh load.
**Motivation:** Reach the original ≥3× target. Required for Phase 7 batch runner scalability at 100+ demos.
**Implementation sketch:**
1. Add per-step `time.perf_counter()` markers to `analyze_demo` (D-01 instrumentation gap from Phase 9.1)
2. Run `cProfile` / `py-spy` against a representative spirit demo
3. Targets in priority order: (a) shared `.tri` BVH mesh cache across subprocesses, (b) `find_visible_enemies_at_tick` raycast batching, (c) per-tick state coercion in parse_ticks post-processing
**Risks:** BVH cache sharing across ProcessPool needs careful design; ray-cast batching may break existing test mocks.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.4: T0/T1/T2 detection ground-truth refresh validation (BACKLOG — surfaced by drill research 2026-05-12)

**Goal:** Refresh manual ground-truth validation of T0/T1/T2 detection. Original n=10 calibration at project start (mid-2025) was deleted; major pipeline changes since (Phase 5 T2-cluster-bleed fix, Phase 6 quality gates, Phase 7 crosshair angle, Phase 10a multi-pipeline) may have drifted detection bias/variance. Document artifact in `.planning/validation/` so it survives future changes.

**Motivation:** Drill research 2026-05-12 (Parallel AI deep) flagged "Djok metrics themselves lack independent, ground-truth validation" as primary methodological risk. Without re-validation, "172ms donk" claim has unknown bias relative to true reaction time. Honest disclosure on landing requires documented validation evidence.

**Implementation sketch:**
1. Pick 20-30 demos covering peek + hold engagements, multiple maps, mix of pro + amateur
2. Per duel: manual frame-by-frame annotation of T0 (first geometric visibility), T1 (crosshair-motion start), T2 (first hit). Video record + tickdata sync. Single rater (user) — note inter-rater limitation.
3. Run current pipeline on same demos → algorithmic T0/T1/T2 per duel
4. Compare per-duel + aggregate: bias (mean offset, ms), variance (std, ms), worst-case outlier
5. Write `.planning/validation/2026-XX-ground-truth-refresh.md` with results table, methodology, sample list
6. If bias > X ms or variance > Y ms → identify root cause + fix before landing v2 claim updates
7. Update landing disclosure copy with documented numbers

**Estimated scope:** 2-3 days (annotation tedious but bounded). NOT 100-demo from-scratch as research initially over-scoped.

**Prerequisites:**
1. Phase 10a merge OR worktree analytics.db stable (current state OK)
2. Sample of 20-30 demos with synced video (Cybershoke / FACEIT demos already have video; pro POV demos need separate video capture)

**Risks:**
- Manual annotation tedium → low completion likelihood unless time-boxed
- Single-rater (user) → no inter-rater reliability. Note in disclosure.
- Subtick architecture (CS2) — T2 quantized to 64Hz tickrate = ±15.6ms baseline variance unavoidable

**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when ready)

### Phase 999.3: DDM deception-scenario t_er splits (BACKLOG — surfaced by /gsd-explore 2026-05-08)

**Goal:** Compute and surface EZ-Diffusion non-decision time (t_er) separately for deception-laden engagement subtypes — smoke peek, fake peek, wide swing — vs regular open-angle engagements. Per Chen 2025 (Psychology of Sport and Exercise), t_er is a meaningful axis only in deception scenarios; flat per-player t_er is uninformative.
**Motivation:** Without splits, t_er is dead weight in DDM output. With splits, it surfaces "this player is slow to recover from fake peeks" — actionable insight no current metric provides.
**Prerequisites:**
1. Spike `.planning/spikes/ez-pc-validation/SPEC.md` returns GREEN — DDM viable for cs2-ddm
2. Phase 10 (Longitudinal DDM lens, Угол A) shipped — DDM machinery in pipeline
3. Engagement subtype classifier exists (smoke detection from utility events; fake-peek = movement reversal within 200ms; wide swing = velocity profile)
**Implementation sketch:**
1. Add `engagement_subtype` column to `engagements` table (smoke_peek / fake_peek / wide_swing / open / other)
2. Per-player × per-subtype EZ fit
3. UI: t_er broken out per subtype in player profile
4. Coaching insight: highlight subtype where player's t_er deviates >1.5σ from their own baseline
**Risks:** Subtype classifier needs validation; deception scenarios may be too rare per player for stable EZ fit (sample size risk). May require ≥100 deception engagements per subtype per player.
**Requirements:** TBD
**Plans:** 0 plans

Plans:
- [ ] TBD (promote with /gsd-review-backlog when DDM Phase 10 ships)
