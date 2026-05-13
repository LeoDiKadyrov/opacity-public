# Project Research Summary

**Project:** Djok — CS2 Reaction Analysis Tool
**Domain:** Esports performance analytics / B2C SaaS
**Researched:** 2026-04-30
**Confidence:** HIGH

## Executive Summary

Djok is a B2C esports analytics tool built on a technically irreplaceable stack: demoparser2 for per-tick kinematic state and awpy's BVH+AABB VisibilityChecker for geometric T0 detection. No competitor decomposes reaction time into T0→T1 (perceptual lag) and T1→T2 (aim execution) — this is the primary technical moat. The architecture is correct for 6 demos; it requires three specific changes before scaling to 100+: add `player_steamid` to the schema, migrate CSV to SQLite, and add a parallel batch runner. These must happen before interpretation work begins, because interpretation thresholds require real distributions from N>100 games to be defensible.

The highest-risk gap is not technical — it is the interpretation layer. Every competitor (Leetify, scope.gg, Tracker.gg) has solved data extraction and failed identically: metrics without meaning cause session-one churn. The "aha" moment identified as missing in the project is exactly the gap the entire competitor field has also failed to close. Djok's path is: metric → plain-English meaning → gap vs. donk → specific drill prescription. Leetify provides steps 1–3 implicitly; no tool provides step 4 explicitly. That explicit coaching directive is the differentiator.

The critical tension between research docs: ARCHITECTURE.md says "scale first, interpret second" (accumulate 100 games before building thresholds), while STACK.md and FEATURES.md argue interpretation is the product and should be built now. Resolution: build the interpretation framework and UI structure now using donk-as-reference framing (costs one session, doesn't require population percentiles), but populate tier thresholds only after the 100-game dataset exists.

---

## Key Findings

### Recommended Stack

Keep the entire current stack without migration. demoparser2 + awpy is the only Python path for BVH geometric T0 detection. Streamlit is adequate for internal use and early-access MVP; the industry pattern is a web app with per-player report pages and shareable URLs. Pragmatic path for a solo developer: deploy Streamlit publicly (Railway/Render) with bundled `.tri` files as the early-access MVP, then upgrade to FastAPI only when user volume justifies it.

**Core technologies:**
- demoparser2 0.41.2+: per-tick kinematic state — no viable Python alternative; pin version, monitor patches
- awpy 2.0.2: BVH VisibilityChecker for geometric LOS — irreplaceable for T0 detection
- pandas + numpy: data manipulation — no reason to migrate; Polars rewrite has no current payoff
- SQLite: replace both CSVs — zero infra, native SQL, WAL mode for concurrent writes
- ProcessPoolExecutor: parallel batch — pool by CPU core, one VisibilityChecker per map per worker (not per demo)
- Streamlit → FastAPI: delivery surface progression — Streamlit for MVP, upgrade when needed

### Expected Features

**Must have (table stakes):**
- Benchmark context per metric — "180ms" means nothing; "vs. donk: 6°" means something
- Plain-English metric explanation inline — users cannot act on numbers without "what this means"
- Composite → component drill-down — RT_visible_to_hit_ms (headline) → T0→T1 + T1→T2 (diagnosis)
- Side-by-side comparison view — user metric | tier | donk benchmark | gap
- Shareable report output — primary B2C acquisition channel
- Survivorship bias caveat on RT — always note "measured on hits only"

**Should have (differentiators):**
- Explicit coaching directive per worst metric — specific drill, not "practice more"
- Peek vs. hold classification throughout — never conflate; different training signals
- Kill rate alongside RT — 320ms + 30% kill rate is a different player from 320ms + 70%
- T0→T1 vs. T1→T2 breakdown as primary decomposition — no competitor has this

**Defer (v2+):**
- Percentile rankings — meaningless without 500+ player dataset; use donk as named reference
- Per-map / per-position breakdown — requires 50+ matches per position
- FACEIT OAuth auto-pull — manual match-URL input is fine for early access
- Team analytics — different data model, different product
- Real-time overlay — different architecture entirely

### Architecture Approach

The current architecture breaks at 100+ demos on three dimensions: runtime (BVH is CPU-bound and linear), storage (CSV has no `player_steamid` FK, no query capability), and ergonomics (multi-player comparison requires manual DataFrame merging). Recommended build order: schema migration → parallel batch runner → data accumulation → interpretation layer → B2C delivery. Do not invert.

**Major components:**
1. Schema + storage migration — add `player_steamid` to both output schemas, migrate to SQLite (`analytics.db` with `engagements`, `duel_attempts`, `processed_matches` tables)
2. Phase 6 quality gates — must ship before batch runner: T0-at-search-start rejection, overlapping window dedup, DuelAttemptFinder dedup, `.tri` existence check with explicit error
3. Parallel batch runner (`run_batch.py`) — ProcessPoolExecutor, one VisibilityChecker per map per worker, idempotent via `processed_matches` table
4. Interpretation layer — metric → threshold tier → plain-English label → gap vs. donk → specific drill; built as standalone report generator
5. B2C delivery surface — Streamlit public deploy for MVP; FastAPI + Redis/RQ job queue for multi-user scale

### Critical Pitfalls

1. **Dashboard without interpretation = session-one churn** — Already validated by the project. Every metric must ship with: what it means, whether the player's value is notable, what to do about it. The interpretation layer is the product, not the chart.

2. **Building thresholds on insufficient data** — Tier cutoffs on 6 matches will be invalidated at 100 games. Build interpretation UI structure now with donk-reference framing; populate thresholds only after data accumulation.

3. **Parallelizing before quality gates are complete** — T0-at-search-start (4688ms observed), overlapping window duplicates, and DuelAttemptFinder dedup must be fixed before batch runner ships. Parallelizing corrupt moments produces a corrupt dataset at 10× speed.

4. **Cross-player RT comparison without matched conditions** — Comparing user RT to donk RT without controlling for engagement_type, weapon, enemy velocity produces numbers users draw wrong training conclusions from. Present donk as named reference range in matched strata only.

5. **Schema migration after data accumulation** — Adding `player_steamid` after 100 games requires migrating all existing rows. Do it in Phase 6, before the batch runner runs.

6. **demoparser2 patch regression** — CS2 patches break the parser (0.41.1→0.41.2 precedent). Pin version, run full test suite after any CS2 update, never upgrade mid-dataset.

---

## Implications for Roadmap

### Phase 6: Quality Gates + Schema Migration
**Rationale:** Correctness before scale. All three quality gate fixes are fully documented. Schema migration (`player_steamid`, SQLite) is the prerequisite for everything that follows.
**Delivers:** Correct moment data, player-keyed storage, idempotency infrastructure
**Avoids:** Parallelizing corrupt data; schema migration pain after 100 games are ingested

### Phase 7: Parallel Batch Runner + Data Accumulation
**Rationale:** ProcessPoolExecutor with per-map VisibilityChecker caching reduces 100-demo runtime from ~3.3 hours to ~33 minutes. Data accumulation (target: 100 donk FACEIT demos) is the prerequisite for defensible interpretation thresholds.
**Delivers:** `run_batch.py`, idempotent processing, ~100 donk games in SQLite
**Risk:** FACEIT Downloads API approval has 30-day response time — research this early; prepare manual bulk-download fallback

### Phase 8: Interpretation Layer
**Rationale:** Interpretation is the product differentiator and the B2C blocker. Build as standalone report generator (not tied to Streamlit). Framework can ship with donk-reference framing before thresholds are finalized.
**Delivers:** Metric → tier → plain-English label → gap vs. donk → specific drill prescription for: crosshair_angle_at_t0_deg, rt_visible_to_aim_ms, rt_aim_to_hit_ms, kill rate, engagement type split
**Pattern:** Leetify's benchmark model + explicit coaching directives (their known gap); composite → component drill-down

### Phase 9: B2C MVP Delivery
**Rationale:** Only after interpretation is validated on real users. Streamlit public deploy is the fastest path for a solo developer.
**Delivers:** Public-accessible analysis, shareable report URL, email-gated early access, one coaching recommendation per worst metric
**Avoids:** Web upload interface (3–4× complexity); real-time analysis; percentile claims without population

### Phase Ordering Rationale
- Quality gates must precede batch runner: corrupt data at scale is exponentially harder to fix
- Schema migration must precede data accumulation: retroactive migration across 100 games is painful
- Data accumulation must precede interpretation thresholds: 6 matches cannot produce defensible tier cutoffs
- Interpretation framework can be built in parallel with accumulation using donk-reference framing; thresholds finalize after data
- B2C delivery is last: the gap between "interesting tool" and "tool I pay for" is the interpretation layer

### Research Flags

Needs research during planning:
- **Phase 7:** FACEIT Downloads API approval timeline (30-day response) may gate demo acquisition. Research manual bulk-download alternatives before committing to timeline.
- **Phase 9:** Streamlit auth options and Railway/Render deployment with bundled `.tri` files need validation. Redis/RQ vs. Celery for single-VPS job queue needs concrete comparison.

Standard patterns (skip research-phase):
- **Phase 6:** All three quality gate fixes are fully documented in MEMORY.md and PITFALLS.md. No unknowns.
- **Phase 8:** Interpretation framework is defined. Leetify's model is fully documented. Implementation is a coding task.

---

## Confidence Assessment

| Area | Confidence | Notes |
|-|-|-|
| Stack | HIGH | demoparser2 + awpy confirmed working in production. Delivery surface pattern is documented industry standard. |
| Features | HIGH | Leetify/scope.gg competitor analysis thorough. Table stakes and differentiators are clear. |
| Architecture | HIGH | Schema migration and ProcessPoolExecutor are standard. SQLite fit is well-reasoned for this data size. |
| Pitfalls | HIGH | Most pitfalls validated against real data (BVH vs. manual T0 gap, flash suppression, NaN tick crash, 4688ms outlier). |

**Overall confidence:** HIGH

### Gaps to Address

- **FACEIT Downloads API approval:** 30-day response time may block Phase 7. Investigate early; prepare fallback.
- **Interpretation threshold values:** Crosshair angle tier cutoffs (< 10° / 10–25° / > 25°) are estimates from Leetify aggregated data. Validate against actual donk dataset distribution before publishing.
- **T1 detection false-positive rate:** Pitch/yaw second derivative heuristic behavior on recoil patterns is undocumented. Do not surface T1 as primary user metric in v1; revisit after N > 200 confirmed moments.
- **awpy Python 3.14 compatibility:** Installed with `--ignore-requires-python`. Monitor on any awpy or numpy minor update.

---

*Research completed: 2026-04-30*
*Ready for roadmap: yes*
