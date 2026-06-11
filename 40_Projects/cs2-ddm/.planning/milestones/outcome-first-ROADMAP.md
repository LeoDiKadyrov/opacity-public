---
milestone: outcome-first
name: Outcome-First Duel Reconstruction
status: in-progress  # OF-1 PASS (GO) → OF-2 SHIPPED+CLOSED 2026-06-10 → OF-3 next (discuss/plan)
created: 2026-06-05
author_diagnosis: 2026-06-05 conversation (djok post-mortem) — see OF-1-CONTEXT.md §Death diagnosis
depends_on: v1.0 (shipped 2026-05-07, archived), Phase 10 (T1 fix, shipped 2026-05-16)
supersedes_intent: "Phase A re-batch / v1.1" — the real blocker is architectural, not data freshness
phases: [OF-1, OF-2, OF-3]
gate: "OF-1 is a STOP/GO gate. OF-2 and OF-3 only exist if OF-1 PASSES."
---

# Milestone: Outcome-First Duel Reconstruction

## Milestone Goal

Replace djok's **geometry-first** duel detection — which mis-identifies the opponent in ~94% of recorded "duels" — with **outcome-first** reconstruction anchored on ground-truth `player_hurt` / `player_death` events. Then PROVE, via a cheap validation gate (Phase OF-1), that outcome-first duels yield a measurable, interpretable metric (counter-peek / hold-success). **If the gate fails, park djok permanently.**

## Why this milestone exists

A 2026-06-05 post-mortem (full code-level diagnosis in `OF-1-CONTEXT.md`) found djok's core disease: the demo gives ground truth only for *events* (who fired / hurt / killed — each with explicit attacker+victim steamids), NOT for *who you were dueling*, *when you reacted*, or *whether you were holding*. djok **invents** those from proxies (BVH "closest visible enemy", crosshair "moving toward", velocity threshold) and then joins **real** outcomes onto **fabricated** subjects. Result: precise statistics about fictional duels. Empirically: of donk's 3285 "hold duels", only **5.9% (195)** register any hit on the nominal (BVH-selected) enemy. Survival proxy inflated win-rate to an implausible 92.7%.

The fix is an architecture inversion (owner's framing, verbatim):

> player_hurt / player_death — это ground truth с attacker+victim. Правильный дизайн был бы outcome-first: стартовать от «player_hurt где attacker=ты» → это твой настоящий оппонент и настоящее попадание → и оттуда искать реакцию НАЗАД. Весь нужный материал в коде уже есть (all_hurt_df, all_death_df) — но используется только для валидации геометрической догадки, а не как якорь. djok построен задом наперёд.

## TWO MANDATORY CAVEATS (do not lose these during execution)

**CAVEAT 1 — Opponent-identity fix ≠ methodology validity.**
Outcome-first fixes *who* the opponent was. It does NOT answer whether reaction-time / duel metrics are *measurable as a coaching signal at all*. The DDM coach-narrative layer closed **RED on 2026-05-12** (1/30 players passed the stability gate; owner verbatim: «Cross-player ship с 1/30 PASS = маркетинговая ложь»). Phase OF-3 MUST re-run a stability/measurability gate. A clean opponent does NOT imply a shippable metric. Do not skip OF-3's gate to "ship faster".

**CAVEAT 2 — This is the deferred tar pit. OF-1 is the stop-rule, not the rebuild.**
This rebuild was deliberately deferred (see memory `project-djok-strategic-verdict-2026-06`: djok PARKED 2026-06-05; owner's recovery month went to a different domain). OF-1 is a CHEAP standalone spike (days, no production code touched) whose only job is to GATE the rebuild. **Only if OF-1 passes do OF-2/OF-3 get planned.** If OF-1 fails → park djok permanently, no further capture/re-batch loops. Do not start OF-2 before OF-1's VERDICT.md says PASS.

## Phases

### Phase OF-1: Outcome-First Validation Spike (STOP/GO GATE) — executable now
**Goal:** Build a standalone outcome-first duel reconstructor, run it on donk's 81 on-disk demos, and decide STOP or GO.
**No production code touched.** New script only.
**GATE (all three must hold to GO):**
1. **Opponent-truth rate ≫ 5.9%** — fraction of reconstructed duels whose opponent is anchored on a real `player_hurt`/`player_death` involving the player. Target: ≥ ~80% by construction (opponent comes from the event, not a guess).
2. **Plausible win-rate** — a real holder wins roughly 40–70% of held angles (NOT 90%+, NOT ~0%).
3. **≥1 interpretable slice** — e.g. counter-peek/hold-success separates meaningfully by pre-aim readiness or by who-initiated. (Old slices showed zero separation.)
**Plans:** OF-1-00-PLAN.md (the spike)
**Output:** OF-1-VERDICT.md (PASS → OF-2 may be planned; FAIL → park, milestone closed)

### Phase OF-2: Core Rebuild (SHIPPED 2026-06-05, CLOSED 2026-06-10)
**Goal:** Make outcome-first the production duel path. Delete the geometry-first opponent guess (`DuelAttemptFinder` + `find_first_visible_enemy_in_window`). TDD (Wave 0 RED tests first). New `duel_episodes` table for ground-truth opponent + outcome + initiator. Keep `t0_detector.find_t0(known_enemy)` — BVH is correct when given a KNOWN enemy; it was only wrong as an opponent *selector*. Reaction timing → OF-3 (user decision 2026-06-05).
**Result:** 4/4 plans, 12 commits `cf4b62a..5a5f36b` (branch `outcome-first`), 365/365 tests GREEN. R-8 parity vs spike: won=1428/lost=1090 identical to the unit; win-rate 56.7%; initiator separation 10.4pp; dust2 17/16 exact; 0 corrupted steamids. Episode-count band FAIL* reclassified as **band miscalibration**: gun-only anchor removed exactly 816 episodes, all unresolved utility-only (19.6% of spike episodes, the ±5% band assumed ≤5%). User approved `of2_parity_inspection.md` 2026-06-10; verifier skipped by user decision. SC-2 satisfied.
**Plans:** OF-2-00 (Wave-0 RED tests) → OF-2-01 (outcome_first.py + db) → OF-2-02 (selector deletion + pipeline wiring) → OF-2-03 (R-8 parity, checkpoint). See `.planning/phases/OF-2-core-rebuild/`.

### Phase OF-3: Re-validation + Metric + Measurability Gate (PLAN ONLY AFTER OF-2)
**Goal:** Re-batch donk's corpus through outcome-first; build `tests/test_distribution_shape.py` regression suite (catches tick-quantum pinning + implausible distributions — the class of bug that hid for months); derive the counter-peek/hold-success metric on clean data; run a CAVEAT-1 measurability/stability gate before any marketing claim. If the metric fails the stability gate → that is the real, final answer on djok-as-coaching-product.
**Plans:** 4 plans in 4 waves (PLANNED 2026-06-10). Branch `outcome-first`; merge to main only when «всё прям будет работать».
- [ ] OF-3-01-PLAN.md — TDD Wave-0: RED tests (T1 LANDS + T0 backward) + duel_episodes timing migration + config constants + requires_db marker
- [ ] OF-3-02-PLAN.md — reaction_timing.py (T0 backward search D-05 + T1 LANDS detector D-01, kills B-5) wired into reconstruct_all_players; D-02 threshold A/B checkpoint
- [ ] OF-3-03-PLAN.md — staged N=1→5→81 donk re-batch (D-14) + 7-section physics-bounded inspection artifact + distribution-shape @requires_db tier (D-15); N=5 user checkpoint
- [ ] OF-3-04-PLAN.md — Gate-A (win-rate) + Gate-B (RT split-half reliability) measurability gate; thresholds approved pre-run (D-10); Gate-B FAIL→STOP (D-11); OF-3-VERDICT.md closes SC-3

## Milestone Success Criteria

- **SC-1:** OF-1 produces a VERDICT.md with an explicit PASS/FAIL on all three gate conditions, with donk's real numbers vs the old 5.9% / 92.7% baseline.
- **SC-2 (only if OF-1 PASS):** OF-2 ships outcome-first as the production duel path with Wave-0 RED tests green and the geometry-first opponent guess removed/deprecated.
- **SC-3 (only if OF-2 ships):** OF-3 produces a clean re-batched dataset + a distribution-shape regression suite + a measurability/stability verdict on the counter-peek metric.

## Assets to reuse (do NOT rebuild)

- **Parser core** (`ddm_analyzer.py` `parse_events([...])`, `parse_ticks`) — production-ready, decoupled, Windows/steamid-safe. The spike re-parses ONLY `player_hurt`, `player_death`, `weapon_fire`, and a tick window.
- **BVH** (`t0_detector.py` `find_t0`, `is_visible`) — correct for "when did P first see KNOWN enemy E". Reuse for the backward reaction search ONLY, never as opponent selector.
- **Demo corpus:** donk's 81 demos confirmed on disk at `D:\Obsidian\opacity\40_Projects\for_analysis\` (mostly `spirit/`). (The STATE.md "82/83 missing" blocker is stale for donk — verified 2026-06-05.)
- **Prior probe scripts** (reference starting points, uncommitted): `counter_peek_v1.py`, `counter_peek_v2_enrich.py`.

## Resume

A fresh session executes `OF-1-00-PLAN.md` inline (gsd-sdk CLI is NOT installed on this machine — read the PLAN directly and execute; do not call /gsd-* skills). Start by reading `OF-1-CONTEXT.md` for the full death diagnosis and the outcome-first design.
