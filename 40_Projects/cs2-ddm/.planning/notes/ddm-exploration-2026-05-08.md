---
title: DDM (EZ-Diffusion) Exploration — Findings + Routing
date: 2026-05-08
context: /gsd-explore session evaluating draft `D:/Obsidian/opacity/40_Projects/zhiz/drafts/ddm-метрики-reply.md` for cs2-ddm fit
related:
  - .planning/spikes/ez-pc-validation/SPEC.md
  - .planning/seeds/ddm-archetype-clustering.md
  - ROADMAP.md Phase 999.3 (deception t_er splits)
---

# DDM Exploration Findings — 2026-05-08

## Source draft

Arystan's earlier reply to a question about applying EZ-Diffusion to cs2-ddm. Draft proposed v/a/t_er decomposition as core product feature.

Path: `D:/Obsidian/opacity/40_Projects/zhiz/drafts/ddm-метрики-reply.md`

Key claims of the draft:
- DDM-параметры give specific actionable feedback vs win-rate-style metrics
- Suggested 3 connection threads: cs2-ddm product, briefing.py personal cybernetics, AI-tagged drafts
- Acknowledged sample size (~50 trials EZ minimum, ~100+ better) and t_er hardware confound (ping/input lag)
- Suggested speed-up tactics for demo parsing

## Pre-existing question

**What does DDM say that current `interpretation.py` doesn't already say?**

For donk peek baseline 2026-05-07:
- RT = 172ms (Elite)
- crosshair = 5.2° (Elite)
- hit_rate = Good

If DDM produces v=0.21, a=0.14, t_er=72ms — what coaching action emerges that wasn't already in the tier output?

User answer: honestly didn't know, requested research.

## Research pass (gsd-phase-researcher, 2026-05-08)

| Source | Finding | Implication |
|-|-|-|
| Green/Pouget/Bavelier 2010 (Current Biology) | Action gamers ↑v, ↓a, ===t_er | FPS skill = evidence accumulation + decision threshold, NOT motor reflex |
| Van Ravenzwaaij 2014 (J Exp Psychol Gen) | Replication failed | Methodology fragile |
| Liu 2026 (Brain Sciences) | Open-skill athletes ↑v only | Pro vs amateur ranking by v feasible |
| Chen 2025 (Psychology of Sport and Exercise) | Deception inflates t_er in experts | t_er meaningful only in deception scenarios |
| Lerche 2024 (Journal of Cognition) | a drops fast (sessions), v rises slow (weeks) | **PERIODISATION DIAGNOSTIC** — RT+accuracy aggregate, DDM shows which lever moved |
| (negative) | NO published FPS DDM work. NO commercial product exposes v/a/t_er | Greenfield + risk: nobody validated mapping |

**Researcher verdict:** "DDM offers modest, asymmetric coaching value... treat it as a research-grade lens, not validated coaching tech."

## Three angles surfaced

| Угол | Definition | Routing | Artifact |
|-|-|-|-|
| **A — Longitudinal lens** | DDM as delta-tracker across sessions/weeks. NOT replacement for tier'ы. Periodisation insight ($a$ vs $v$ change at different rates) is the unique value over interpretation.py | Act now | `.planning/spikes/ez-pc-validation/SPEC.md` |
| **B — Archetype clustering** | DDM-параметры → player archetypes ("careful sniper" vs "fast rusher"). Requires ≥30 players in DB | Seed (dormant) | `.planning/seeds/ddm-archetype-clustering.md` |
| **C — Deception-scenario splits** | t_er activates only in deception (Chen 2025) — measure separately for smoke peek / fake peek / wide swing | Roadmap defer | `ROADMAP.md` Backlog Phase 999.3 |

## Load-bearing unknown: Pc definition

EZ-Diffusion math requires binary correct/incorrect per trial. CS duel has multiple plausible Pc definitions:

| Pc | Definition | Concern |
|-|-|-|
| pc1 | first_shot_hit | Confounds aim quality |
| pc2 | won_duel | Mix decision + aim + position + luck |
| pc3 | crosshair_angle_at_t0 < 5° | Closest to decision quality, threshold arbitrary |
| pc4 | engagement_started | Trivially binary (degenerate) |

Wrong Pc → garbage v/a/t_er → users get advice from noise → trust collapses. Spike `ez-pc-validation` is the go/no-go gate.

## Verbatim user quotes

> "если честно нет, нужен research может ли он дать уникальный инсайт, на примере возможно других проектов где это использовались, или исследований. Ну и дальше brainstorming"

> "А - прямо сейчас. для В - я собираю >30 игроков в DB. С - в роадмапу, но сейчас точно нет"

> "Сложно, хорошо, что ты подсветил проблемы, но теперь бы понять, во что эти проблемы могут вылиться в будущем? Или можем ли мы протестировать все варианты на каком-нибудь очень маленьком sample из analytics.db и понять, что в реальности будет лучше?"

> "сначала spike spec потом execute"

## Why this matters for Djok

If GREEN verdict on spike + Phase 10 ships:
- Periodisation diagnostic = first product feature delivering temporal evolution insight (vs snapshot)
- "No commercial product exposes DDM" = differentiator vs Senaptec/NeuroTracker class
- Risk: ship'нуть на shaky Pc → users get advice from noise → trust collapse worse than not shipping. Spike de-risks.

## Spike outcome (2026-05-08 same session)

**Result:** 0 GREEN, 2 YELLOW (`pc2_won_duel`, `pc3c_crosshair_lt_8deg`), 3 RED. See `bench/EZ_PC_RESULTS.md`.

**Why:** universal stability fail. Bootstrap CI95/point = 0.30-5.33 vs ≤0.30 SPEC requirement. EZ math itself validated via synthetic recovery (|bias| ≤4%). Discriminant signal exists (donk vs karrigan separates by `v`, Cohen's `d` ≈ 1.0+). Root cause is N/player — donk's 521 trials still too few for stable per-player EZ fit.

**Routing decision:** Phase 10a infra-only path.

| Path | Status |
|-|-|
| Pure defer (option 1) | Rejected — loses passive data accumulation |
| Full disclaimer ship (option 2) | Rejected — trust collapse risk on CI95 width = 30-180% |
| **Phase 10a infra-only (chosen)** | Build compute + persist DDM, NO user-facing UI. Forces data accumulation. Zero user-facing trust risk |

**Phase 10b (UI + coaching insights)** gated on spike re-run returning GREEN at DB ≥30 players. Same trigger unlocks Угол B seed (`.planning/seeds/ddm-archetype-clustering.md`).

**Next action:** when ready to start Phase 10a, invoke `/gsd-spec-phase` with scope: "compute v/a/t_er per session per player per engagement_type, persist as new analytics.db columns; no UI surface; reuse `bench/ez_pc_validation.py` math; expose internal admin-only inspection."

## Methodological pitfalls noted (for execution reference)

- Use `cursor.fetchall()` not `pd.read_sql` for SteamID64 (precision loss)
- Filter `rt_visible_to_hit_ms > 1500ms` before EZ (Phase 6+ ungradeable gate)
- engagement_type split (peek vs hold) mandatory per Phase 5b convention
- EZ math is closed-form (Wagenmakers 2007) — three division ops, ~30 lines, not MCMC
- Pc=`crosshair_angle_at_t0 < 5°` threshold is arbitrary — sweep 3°, 5°, 8°
