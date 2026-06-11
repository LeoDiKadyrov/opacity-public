# Phase OF-3: Re-validation + Metric + Measurability Gate - Context

**Gathered:** 2026-06-10
**Status:** Ready for planning
**Source:** OF-2 closed 2026-06-10 + user decisions (AskUserQuestion 2026-06-10) + milestone roadmap OF-3 sketch

<domain>
## Phase Boundary

OF-3 makes the **T0→T1→T2 reaction methodology work again** on top of the ground-truth foundation OF-2 shipped. Reaction timing is computed per `duel_episodes` row (KNOWN opponent from events): T0 via backward visibility search (`find_t0` on the known enemy), redefined T1 with **crosshair-LANDS semantics (B-5 fix)**, RT derived. Then: distribution-shape regression suite, staged re-batch of donk corpus + gate players, counter-peek/hold-success metric on clean data, and the **CAVEAT-1 measurability/stability gate** before any coaching/marketing claim.

**IN scope:**
- New T1 detector with LANDS semantics in the outcome-first path (NOT a rewrite of old `_detect_t1`)
- T0 backward search per episode on the KNOWN opponent (BVH `find_t0` reuse)
- Timing columns added to `duel_episodes` (idempotent `_migrate_schema`)
- `tests/test_distribution_shape.py` — two-tier (synthetic pytest + `@requires_db` live-DB checks)
- Staged re-batch N=1→5→81 (donk) + gate players, manual checkpoints + inspection artifact
- Gate-A (win-rate slices) + Gate-B (RT stability) measurability gate; gate numbers designed by researcher, user-approved BEFORE the run

**OUT of scope:**
- Old engagements pipeline rewrite/deletion — DEPRECATED, untouched
- Dashboard/report switch to duel_episodes source — separate phase/backlog
- Landing refresh / banner removal / marketing content — only AFTER gate verdict (CAVEAT-1)
- Merge to main — branch `outcome-first` until «всё прям будет работать»

</domain>

<decisions>
## Implementation Decisions

### T1 redefinition (B-5 fix)
- **D-01:** Predicate is Claude's discretion with a locked mandate — user verbatim: «выбирай то, что считаешь, что реально исправит ситуацию и оживит проект». Starting default: **T1 = first tick where angular dist ≤ TARGET_REACHED_THRESHOLD AND it holds ≤threshold for T1_SUSTAINED_AIM_TICKS (2) more ticks** (flick-overshoot protection). Validate via distribution shape on staged run; adjust if shape shows artifact.
- **D-02:** Threshold value (fixed 3° vs distance-scaled by hitbox angular size) — **decided by data**: researcher/executor runs both variants on 1 demo, picks by distribution shape. New constant `TARGET_REACHED_THRESHOLD` lives in config.py with rationale comment (≥3× quantization rule: demoparser2 angular step ~0.022°, both candidates clear it).
- **D-03:** Crosshair never reaches threshold before first hit (spray-transfer, lucky flick) → **`t1_source="never_landed"`, T1=NULL, row stays in DB**. Mirrors unresolved-as-label. never_landed share is itself a diagnostic signal.
- **D-04:** Old `_detect_t1` + engagements timing path → **DEPRECATED, untouched**. New detector lives in the outcome-first path (new module/method). No valid-T1-on-invalid-duels half-fix.

### T0 backward search
- **D-05:** Window algorithm is Claude's discretion. Leaning: **backward scan to the start of the continuous visibility run containing the first event, with a cost cap; long-visibility episodes labeled (e.g. `long_visible`), not clamped**. Hard constraint: NO fixed-window clamp that truncates T0 at the window edge — that recreates the B-1 floor-artifact class. Researcher validates choice on data + cost.
- **D-06:** Enemy never visible before first hit (wallbang/smoke/molly) → **`t0_source="never_visible"`, T0=NULL, row stays in DB**.
- **D-07:** **Correctness first, profile on staged run.** No upfront BVH optimization (share/cache). Optimize only if 81-demo re-batch becomes impractical; hardware ceiling notes in `reference_hardware_capacity_2026_05_17` memory apply.
- **D-08:** Timing computed for **ALL episodes including unresolved** — labels filter at metric level; full picture needed for distribution-shape checks.

### Metric + measurability gate
- **D-09:** Gate has **two independent layers**: **Gate-A** = win-rate slices (hold/counter vs initiate; expected PASS — 9.7pp≈5σ in OF-1), **Gate-B** = RT (T0→T1) stability — the real risk (prior DDM gate closed RED 1/30 on 2026-05-12). Product can ship on Gate-A even if Gate-B is RED.
- **D-10:** **Researcher designs the concrete gate tests + PASS thresholds** (e.g. split-half reliability with explicit r and N floors), with written rationale in RESEARCH.md. **Numbers are locked in PLAN with a user checkpoint BEFORE the gate run** — no moving goalposts after launch. (Lesson: OF-2 ±5% band miscalibration.)
- **D-11:** **Gate-B FAIL → STOP + checkpoint, user decides**: park / pivot to win-rate-only / one more methodology iteration. No auto-pivot, no auto-park.
- **D-12:** Gate sample = **donk (81 demos) + 2-4 pros from the same on-disk corpus** (opponents in the same demos — multi-player API from OF-2 makes this free). Cross-player check without new demos.

### Re-batch + data schema
- **D-13:** Timing lives as **columns on `duel_episodes`** (1:1 with episode): `t0_tick`, `t0_source`, `t1_tick`, `t1_source`, plus derived RT. Added via idempotent `_migrate_schema` (existing pattern). No new table.
- **D-14:** Re-batch is **staged N=1→5→81 with manual checkpoints**: distribution-shape SQL between steps (tick-quantum pinning %, min/p10, never_landed/never_visible %), doubt = STOP. **Inspection artifact at N=5 reviewed by user before full run** — every table carries ≥1 physics-bounded column (crosshair_angle@T0 class), per the B-5 post-mortem lesson.
- **D-15:** `tests/test_distribution_shape.py` is **two-tier**: (1) synthetic fixtures in regular pytest (algorithm regression, always runs), (2) `@requires_db` checks against live analytics.db (run after every re-batch).
- **D-16:** Old invalid timing data in `engagements` (post-Phase-10 rebatches ~40 demos + monesy) → **left as-is; path deprecated**. All claims sourced ONLY from `duel_episodes`. Keeps pre/post material for methodology content.

### Claude's Discretion
- T1 predicate exact form (D-01 mandate) and threshold mode (D-02 data-driven)
- T0 backward-search algorithm details within D-05 constraints
- Episode→tick-parse batching strategy (per-round parse_ticks windows etc.)
- Exact derived-column set beyond t0/t1/source (e.g. rt_visible_to_land_ms naming)
- Gate-A slice definitions beyond hold/initiate (aux slices allowed)
- staged_rebatch driver reuse vs new script (skip-existing + pause/resume patterns from memory apply)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Milestone & gates
- `.planning/milestones/outcome-first-ROADMAP.md` — milestone goal, SC-3, CAVEAT-1/2, OF-3 sketch
- `.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md` — gate numbers, caveats carried forward, found-bug (steamid coercion)
- `.planning/phases/OF-2-core-rebuild/OF-2-PARITY.md` — R-8 parity verdict, band-miscalibration lesson (gate numbers must be justified, not guessed)
- `.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md` — OF-2 locked decisions inherited here (gun-only, unresolved-as-label, find_t0 kept)

### B-5 evidence (what the T1 fix must kill)
- `b5_smoking_gun.md` (repo root) — 15 impossible rows + crosshair-angle distribution at 1-tick T1; the new detector must produce 0 rows of this class
- `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/10-RESEARCH.md` — prior T1 fix research (grace floor + pre-aim), constants context

### Production code touched
- `outcome_first.py` — episodes pipeline; timing attaches here (`reconstruct_all_players`, `group_episodes` output dict)
- `t0_detector.py` — `find_t0` (L88) reuse for backward search on KNOWN enemy; smoke/flash suppression intact
- `ddm_analyzer.py` — `_detect_t1` (L477) reference of OLD semantics; DEPRECATED, do not edit
- `db_utils.py` — `_migrate_schema` idempotent column-add pattern; quad-touch checklist if any new table (none planned)
- `config.py` — new `TARGET_REACHED_THRESHOLD`; existing `T1_SUSTAINED_AIM_TICKS`, quantization-step doc at top of filtering modules

### Ops patterns (memory-verified)
- pytest: `py -m pytest --override-ini="addopts=--strict-markers" -q` (`-p no:cov` broken on this machine)
- Subprocess env: `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`
- SteamID: `_coerce_sid` string path; never `pd.to_numeric`/`pd.read_sql` on sid columns
- Demo corpus: `D:\Obsidian\opacity\40_Projects\for_analysis\` (donk: spirit/, 81 demos verified)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `t0_detector.find_t0` + `is_visible` (BVH+AABB, smoke/flash suppression) — correct for KNOWN enemy; this is exactly the OF-3 use case
- `outcome_first.reconstruct_all_players` — multi-player episode pipeline; timing pass slots in per episode
- `db_utils._migrate_schema` — idempotent ADD COLUMN pattern (t1_source precedent from Phase 10)
- Staged-rebatch tooling: `staged_rebatch`/`full_corpus_rebatch.py` drivers, pause/resume PowerShell wrappers, detached-watcher pattern
- Inspection-artifact generator pattern (`generate_top10_inspection.py`, `of2_parity_inspection.md` 7-section format)

### Established Patterns
- TDD Wave-0 RED tests first (project convention; OF-2 precedent: 9 RED tests → GREEN)
- Label-not-drop semantics (unresolved, pre_aimed, t1_source) — extended with never_landed / never_visible / long_visible
- Physics-bounded column in every inspection table (B-5 post-mortem rule)
- Threshold ≥3× quantization step (demoparser2 angular step ~0.022°)

### Integration Points
- Timing pass runs inside/after `reconstruct_all_players` per episode (needs parse_ticks window around episode bounds — selective parse per Phase 9.1 patterns)
- `duel_episodes` consumers (future dashboard/report) read timing columns — out of scope here but schema names should be final

</code_context>

<specifics>
## Specific Ideas

- User mandate on T1 (verbatim): «мне нужно, чтобы было использовано решение, которое сделает так, чтобы основная методология t0->t1->t2 заработала, поэтому выбирай то, что считаешь, что реально исправит ситуацию и оживит проект» — success = methodology alive, not a specific predicate
- Acceptance smell-test for the new T1: re-run the `b5_smoking_gun.md` query class on fresh data → 0 rows with large crosshair angle + 1-tick T1; no >10% cluster at any tick-quantum value (15.625/31.25/46.875ms)
- Pro-physiology sanity floor: per-player median RT < 100ms = suspicious, investigate before accepting

</specifics>

<deferred>
## Deferred Ideas

- Dashboard/report/interpretation switch from `engagements` to `duel_episodes` source — own phase after gate
- Landing claims refresh + data-refresh banner removal — blocked on gate verdict (CAVEAT-1)
- BVH share across players / visibility cache (perf) — only if staged run shows re-batch impractical (Phase 9.2 candidate)
- Initiator refinement via visibility/positioning — OF-3 candidate in OF-2 context, still deferred unless gate needs it
- `kill_rate_analysis.py` DEPRECATED path cleanup — backlog

</deferred>

---

*Phase: OF-3-revalidation-measurability-gate*
*Context gathered: 2026-06-10*
