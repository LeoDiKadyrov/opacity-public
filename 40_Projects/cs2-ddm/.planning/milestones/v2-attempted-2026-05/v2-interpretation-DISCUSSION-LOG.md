# Phase v2-interpretation-narrative — Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-12
**Phase:** v2-interpretation-narrative
**Areas discussed:** Attribution detail level, Validator strictness, Narrative tone + length, Eval set composition + iter

---

## Attribution Detail Level

| Option | Description | Selected |
|-|-|-|
| Minimal, N=3 worst | tick + map_name + round_phase + round_time_s. No upstream schema change. N=3 worst per metric. Scope-clean. | |
| Minimal + best/worst mix | tick+map+phase. N=2 worst + N=1 best per metric — narrative includes positive reinforcement. Context +30%. | |
| Round number extraction (+1 day) | Bump scope: add `round_number` column to engagements via round_start event parsing. Narrative can say "round 14". | |
| Round extraction + best/worst | Max attribution: round_number + map + N=2 worst + N=1 best per metric. Most coach-like. Scope +1 day, context +30%. | ✓ |

**User's choice:** Round extraction + best/worst combo
**Notes:** Bumps phase scope ~1 day. Schema migration + backfill required. D-01..05 in CONTEXT.md capture full attribution shape.

---

## Validator Strictness

| Option | Description | Selected |
|-|-|-|
| Hybrid | Strict for numeric refs (tick, round_number). Whitelist common nouns (map names, "peek", "hold"). 1 attempt, fallback on fail. | ✓ |
| Strict + retry | Any not-in-allowed-refs = fail. 2 retries with stricter prompt. Fallback. Higher cost, max trust. | |
| Strict, single try | Strict rule, 1 attempt, fallback on any violation. Cheap, higher fail rate. | |
| Lax — demo+tick only | Only demo_name + tick strict. Maps/rounds/phases logged-warn but don't fail. Lower fail rate, higher hallucination risk. | |

**User's choice:** Hybrid (Recommended)
**Notes:** Balance precision vs recall. D-06..09 in CONTEXT.md specify `allowed_refs` composition + single-attempt policy + structured violation reporting.

---

## Narrative Tone + Length + Structure

| Option | Description | Selected |
|-|-|-|
| Brutally honest, 500w, structured | Tone: brutally honest coach (RU). 500 words. Structure: Strength → Weakness → Action sections. Cost ~$0.08/report. | ✓ |
| Brutally honest, 500w, free-form | Same tone, no fixed sections. More natural prose, worse scan-ability. | |
| Brutally honest, 300w, structured | Shorter, cheaper (~$0.05). Less attribution space. Risk: "trivial" rating in SC-1. | |
| Coach-style, 500w, structured | Less brutally, more supportive. Doesn't match user 90_Meta. Not recommended for RU target. | |

**User's choice:** Brutally honest, 500w, structured (Recommended)
**Notes:** Structure sections locked in D-13. DIRECTIONS reference policy via paraphrase + title-anchor in D-14.

---

## Eval Set Composition + Iteration

| Option | Description | Selected |
|-|-|-|
| Tier-mix + diff-rate | 10 = top 3 + mid 4 + bottom 3 by trials. User-only. Diff-rate on prompt change. Faster iteration. | |
| Tier-mix + full re-rate | Same tier mix, full re-rate of all 10 on every prompt change. Stronger baseline, higher iteration cost. | ✓ |
| Top players only | 10 = top by n_trials (donk, karrigan, …). Best signal density. Bias against new/low-tier users. | |
| 10 random | Random sample from 30 DB. Less representative by tier. No selection bias. | |

**User's choice:** Tier-mix + full re-rate
**Notes:** Full re-rate trades iteration cost for baseline integrity. D-15..20 in CONTEXT.md specify exact roster, rating dimensions, storage, SC-6 side-by-side protocol.

---

## Claude's Discretion

User did not specify, planner/Claude decides:
- Prompt iteration count before ship (iterate until SC-1 passes)
- Exact CTA/copy in narrative sections (tone D-10 + structure D-13 constrain)
- Test-file location convention (follow `tests/test_interpretation.py` pattern)
- LLM transient-failure retry policy (HTTP 5xx, rate limit — short backoff OK)
- Cost-tracking CLI flag naming

## Deferred Ideas

(Full list in CONTEXT.md `<deferred>` section.)

- Trajectory tracking (weekly snapshots, w-o-w deltas) → phase v2.1
- Per-map / per-site breakdown → separate phase, needs more data
- Bilingual EN translation → v2.1+
- Streamlit live narrative panel → separate phase if user demand emerges
- Cohort percentile phrasing → needs FACEIT-tier mapping not currently available
- Explicit confidence framing UI surface → v2.1
- LLM-generated drill prescription → defer to post-v2 evaluation (higher hallucination surface)
- DDM (EZ-Diffusion) integration → DEAD per `project_ddm_validation_final_2026_05_12`, do not re-introduce
