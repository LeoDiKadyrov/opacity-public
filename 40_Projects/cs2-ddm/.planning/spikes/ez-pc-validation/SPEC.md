# Spike: EZ-Diffusion Pc Validation

**Slug:** `ez-pc-validation`
**Created:** 2026-05-08
**Executed:** 2026-05-08 (same session via `bench/ez_pc_validation.py`)
**Status:** EXECUTED — verdict YELLOW/RED (no GREEN). Routing: Phase 10a infra-only path.
**Result file:** `bench/EZ_PC_RESULTS.md`
**Source:** `/gsd-explore` session 2026-05-08, exploring DDM-метрики draft (`D:/Obsidian/opacity/40_Projects/zhiz/drafts/ddm-метрики-reply.md`)

---

## Outcome (added 2026-05-08 post-execution)

**Verdict matrix:** 0 GREEN, 2 YELLOW (`pc2_won_duel`, `pc3c_crosshair_lt_8deg`), 3 RED.

**Why all stability failed:** N per player. Bootstrap CI95 width / point ratio = 0.30 to 5.33; SPEC required ≤ 0.30. Even donk (n=521, best case in DB) failed at ~0.66 for `pc2`. Root cause is N-bound, not Pc-choice-bound — hybrid Pc spike-2 would not resolve.

**EZ math validated:** synthetic recovery test passed with |bias| ≤ 4% on all v/a/t_er parameters. Implementation is correct; instability is in the real-data fits, not the closed-form math.

**Discriminant signal exists:** donk vs karrigan separates by drift rate (Cohen's `d` ≈ 1.0+ on `v` for pc2, pc3b, pc3c). Confirms DDM extracts a real signal — but not stably enough at current scale to ship as coaching feedback.

**Routing decision (user choice 2026-05-08):** **Phase 10a infra-only path.**

- Build DDM compute + persistence machinery NOW (no user-facing UI)
- Each demo run accumulates per-session v/a/t_er rows in analytics.db
- Forces faster convergence to ≥30 players + larger N/player than pure defer
- Zero user-facing trust risk (no disclaimer fatigue, no noise-fed coaching)
- Phase 10b (UI surface + coaching insights) gated on spike re-run returning GREEN
- Phase 10b unlock trigger same as Угол B seed (DB ≥30 players, ≥50 trials/player/engagement_type)

**This SPEC is closed.** Re-run of the spike (with current code) at the gated trigger should write a new dated results file (e.g. `bench/EZ_PC_RESULTS_RERUN_<date>.md`) — do NOT overwrite this baseline.

---

---

## Hypothesis to validate

**H0 (null):** No Pc definition produces stable, discriminant, non-redundant DDM parameters on existing CS2 engagement data. EZ-Diffusion is not viable for cs2-ddm.

**H1 (alt):** At least one Pc definition produces $v$, $a$, $t_{er}$ that:
1. Are **stable** (bootstrap CI95 width ≤ 30% of point estimate)
2. **Discriminate** between players in ways RT alone cannot
3. Are **non-redundant** with hit_rate (correlation ∈ [0.3, 0.75] — related but unique signal)
4. **Recover** known synthetic parameters within 15% on simulated data

If H1 holds for one Pc → unblocks Phase 10 (Longitudinal DDM lens, Угол A from explore).
If H0 holds → DDM rejected for cs2-ddm. Idea archived as note.

---

## Background

`/gsd-explore` session surfaced:

- DDM has **modest, asymmetric** coaching value in fast perception-action domains (Green/Pouget/Bavelier 2010, Liu 2026), but **zero published FPS validation**. No commercial product exposes DDM parameters.
- Unique insight DDM offers vs RT+accuracy: **periodisation diagnostic** ($a$ drops fast, $v$ rises slow per Lerche 2024) — current `interpretation.py` cannot surface this.
- Load-bearing unknown: **Pc definition** in CS duels. EZ-Diffusion math requires binary correct/incorrect per trial; CS duels have multiple plausible Pc definitions.

Spike is a go/no-go gate before committing engineering to Угол A.

---

## Pc candidates

| ID | Definition | Pc for donk peek (estimated) | Concern |
|-|-|-|-|
| `pc1` | First shot landed (`first_shot_hit == True`) | ≈ 0.70-0.85 | Конкурирует с aim quality, not pure decision |
| `pc2` | Won duel (player killed enemy first) | ≈ 0.55-0.65 | Mix decision + aim + position + luck |
| `pc3` | Crosshair aligned at T1 (`crosshair_angle_at_t0_deg < 5°`) | ≈ 0.50-0.65 | Closest to decision quality but threshold arbitrary |
| `pc4` | Trigger pulled within RT window (engagement_started) | ≈ 0.95+ | Trivially binary — likely degenerate |

Each Pc gets full validation pass. Hybrid Pc (e.g. `pc1 AND pc2`) optional if individual results inconclusive.

---

## Data inputs

- `analytics.db` — current state: 1042 engagements, 10738 duel_attempts (per MEMORY.md 2026-05-07 snapshot)
- Players in scope: donk, karrigan + ≥3 additional players present in DB with ≥50 engagements each (filter at runtime)
- Engagement type split: peek + hold separately (per Phase 5b convention)

If insufficient players have ≥50 engagements → spike pauses, surface as finding (data scarcity).

---

## Method

Single script: `bench/ez_pc_validation.py` (new file, ~150-250 lines).

### 1. EZ-Diffusion math (closed-form, Wagenmakers 2007)

```
Inputs per player × engagement_type × Pc candidate:
  MRT = mean RT (correct trials)
  VRT = variance RT (correct trials)
  Pc  = proportion correct

Outputs:
  v   = drift rate
  a   = boundary
  t_er = non-decision time
```

No MCMC. Three closed-form expressions. ~30 lines.

### 2. Validity battery (per Pc × per player × per engagement_type)

**a. Stability — bootstrap**
- Resample trials with replacement 1000×
- Compute $v$/$a$/$t_{er}$ per resample
- Report CI95 width / point estimate ratio
- **Pass:** ratio ≤ 0.30 for all 3 params

**b. Discriminant validity**
- Compare donk vs karrigan on $v$/$a$/$t_{er}$ where their RT means overlap (no significant RT difference for engagement_type)
- **Pass:** at least one DDM param shows separation (Cohen's $d$ > 0.5) where RT $d$ < 0.3

**c. Convergent validity (non-redundancy)**
- Pearson correlation $v$ vs hit_rate across all players in scope
- **Pass:** correlation ∈ [0.3, 0.75]
- **Fail high:** correlation > 0.85 → redundant
- **Fail low:** correlation < 0.2 → unrelated, likely measuring noise

**d. Parameter recovery — synthetic**
- Generate synthetic 2-alternative diffusion process trials with known $v_{true}$, $a_{true}$, $t_{er,true}$ at 3 difficulty levels
- N trials per simulation = 50, 100, 200 (matches realistic per-session-per-engagement-type sample sizes)
- Run EZ recovery
- **Pass:** all 3 params recovered within ±15% at N=100

### 3. Output: `bench/EZ_PC_RESULTS.md`

Report sections:
1. Data summary (players × engagement types × N trials per cell)
2. Per-Pc validity table (4 Pc × 4 validity checks × 2 engagement_types)
3. Verdict matrix:
   - GREEN: passes all 4 checks → recommended
   - YELLOW: passes 2-3 checks → conditional, needs follow-up
   - RED: passes ≤1 check → rejected
4. Recommendation:
   - If ≥1 GREEN Pc → which one + rationale → unblocks Phase 10 spec
   - If only YELLOW → hybrid Pc proposal or scope-narrowing (e.g. peek-only)
   - If all RED → reject DDM; idea archived

---

## Success criteria for the spike itself

- [ ] Script runs end-to-end on existing `analytics.db` without modifying schema
- [ ] All 4 Pc candidates evaluated for ≥3 players with ≥50 engagements each per engagement_type
- [ ] Bootstrap stability runs complete in <10 min on dev machine
- [ ] `EZ_PC_RESULTS.md` written with verdict for each Pc
- [ ] Final recommendation classified as GREEN / YELLOW / RED

---

## Out of scope (defer)

- Building any UI for DDM parameters
- Modifying `interpretation.py` to expose DDM
- Schema changes to `analytics.db`
- Cross-player clustering (Угол B — seed)
- Deception-scenario splits (Угол C — roadmap)
- Personal cybernetics / briefing.py DDM (out of cs2-ddm product scope entirely)
- Validation against external/published baselines (separate research task)

---

## Estimated effort

**4-6 hours** total:
- 1h: EZ math + parameter recovery synthetic harness
- 1h: data extraction from `analytics.db` (cursor.fetchall pattern, not pd.read_sql — SteamID64 precision)
- 2h: 4 Pc × 4 validity checks loop + bootstrap
- 1h: results markdown + verdict logic
- 1h buffer: data scarcity edge cases (insufficient players, NaN handling)

---

## Risks

| Risk | Mitigation |
|-|-|
| Insufficient players in DB with ≥50 engagements | Lower threshold to ≥30, document as constraint, flag in verdict |
| All Pc candidates fail recovery on synthetic data | Suggests EZ-Diffusion library bug or math implementation error — investigate before declaring DDM dead |
| Bootstrap CI explodes due to RT outliers (e.g. flash-suppressed engagements) | Filter `rt_visible_to_hit_ms > 1500` (Phase 6+ ungradeable gate) before EZ |
| Pc=`crosshair_angle_at_t0_deg < 5°` threshold = arbitrary | Run sweep at 3°, 5°, 8° as sub-experiment |
| Result comes back YELLOW for all Pc | Acceptable — defines next research question, not a spike failure |

---

## Decision tree post-spike

| Outcome | Routing |
|-|-|
| ≥1 GREEN Pc | `/gsd-spec-phase` for Phase 10 (Longitudinal DDM lens) — Pc choice locked |
| Only YELLOW | Note + revised hypothesis. Either hybrid Pc spike-2 or narrow scope (peek-only Phase 10) |
| All RED | Note: "DDM rejected for cs2-ddm — Pc undefinable / parameters unrecoverable from CS data". Идея mертва. |

---

## Linked artifacts

- Source draft: `D:/Obsidian/opacity/40_Projects/zhiz/drafts/ddm-метрики-reply.md`
- Research findings: this spec's Background section (no separate file yet — capture in spike results if useful)
- Related seed (deferred): Угол B — DDM archetype clustering, trigger DB ≥30 players
- Related roadmap entry (deferred): Угол C — deception-scenario $t_{er}$ splits

---

## Execution

After review of this SPEC, run `/gsd-spike --quick` or implement `bench/ez_pc_validation.py` directly.
