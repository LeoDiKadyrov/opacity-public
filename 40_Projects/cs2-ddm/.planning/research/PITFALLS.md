# Pitfalls Research
_Generated: 2026-04-30_

## Summary

This document catalogs known and researched pitfalls for the Djok/CS2 DDM project across four domains: technical demo parsing, interpretation/coaching validity, B2C product delivery, and solo developer scope creep. Several project-specific pitfalls are already partially mitigated; the phase mapping section notes which gaps remain open.

---

## Technical Pitfalls

### 1. GOTV demo data is silently incomplete
**What goes wrong:** Valve matchmaking GOTV demos omit fields that are documented in the game's API — `m_bSpotted`, `m_bSpottedByMask`, voice audio, and some assist events are simply absent. Analysis code that depends on these fields either silently returns null or produces wrong results.
**Status:** Already known. `m_bSpotted` is documented as never populated. Explicitly guarded against.
**Residual risk:** Any new field added to analysis (e.g., for Phase 6 quality gating) must be validated against actual demo output, not assumed present from Valve documentation.

### 2. Valve matchmaking demos vs FACEIT demos are not interchangeable
**What goes wrong:** FACEIT demos preserve all game events. Valve MM demos are missing key assist events and other structured data. Analysis built on FACEIT demos may silently fail or produce incomplete output on MM demos. The project has only validated against FACEIT demos.
**Prevention:** Add a demo-source header check before analysis. If MM demo detected, emit explicit warning and disable features that depend on FACEIT-complete event data.

### 3. CS2 patches break parsers without warning
**What goes wrong:** demoparser2 required upgrade 0.41.1→0.41.2 when CS2 patch 14155 shipped. NaN ticks appeared in fields that previously returned integers. The next patch may introduce a different breaking change.
**Status:** NaN crash fixed in `duel_attempts.py:106,249`. High regression risk on next demoparser2 upgrade.
**Prevention:** Pin demoparser2 version in requirements.txt. After any CS2 update, run full test suite before processing new demos. Never upgrade parser mid-dataset without re-validating all 6 existing matches.

### 4. BVH T0 is geometric first-visibility, not player perception
**What goes wrong:** BVH T0 fires the tick an enemy bounding box corner becomes ray-unobstructed. The player has not necessarily perceived the enemy yet. If the enemy is in peripheral vision, or if the player's attention is elsewhere, BVH T0 precedes conscious reaction by an unknown amount (anecdotally 4–65 ticks earlier than human-marked T0 in validation set).
**Consequence for interpretation:** Reporting "RT = 281ms" when T0→T1 is 281ms conflates geometric visibility with perceptual onset. For players with good crosshair placement, BVH T0 may occur when the enemy is already in the crosshair — making T0→T1 meaningless as a reaction measure.
**Prevention:** Always display T0 source in output. Flag engagements where crosshair_angle_at_t0_deg < 5° as "pre-aimed" rather than reactive. Do not present these as reaction time data.

### 5. T0 at search_start inflates reaction times
**What goes wrong:** When BVH finds T0 = search_start tick, the enemy was visible before the lookback window. The reported RT (e.g., 4688ms) is meaningless — it measures the lookback duration, not a real reaction.
**Status:** Documented edge case, fix deferred to Phase 6.
**Prevention (Phase 6):** Reject moments where `t0_tick < search_start + 20`.

### 6. Overlapping search windows produce duplicate-enemy moments
**What goes wrong:** Two engagements < 300 ticks apart cause the second moment's auto-discovery to pick the first engagement's enemy. Produces phantom "moments" that are actually continuations of the previous kill.
**Status:** Documented, deferred to Phase 6.
**Prevention (Phase 6):** Reject if `first_hit_tick < prev_accepted_T2 + 300`.

### 7. awpy installed with `--ignore-requires-python`
**What goes wrong:** awpy 2.0.2 does not officially support Python 3.14. Works now but may silently break on minor awpy updates, Python patch releases, or numpy/pandas version bumps.
**Prevention:** Do not upgrade awpy without testing. Lock awpy version. Keep a known-good requirements.txt snapshot.

### 8. `.tri` mesh missing → silent wrong results
**What goes wrong:** If the map's `.tri` file is absent from `C:\Users\Leo\.awpy\tris\`, `VisibilityChecker` may raise or return wrong LOS results with no explicit error visible in the pipeline output.
**Prevention:** Add explicit `.tri` file existence check at `T0Detector.__init__`. Raise `FileNotFoundError` with actionable message rather than allowing corrupt analysis to proceed.

---

## Interpretation Pitfalls

### 1. Survivorship bias: only hits are analyzed
**What goes wrong:** T0/T1/T2 metrics are measured only on engagements that resulted in a hit. Misses have no T2. This means the RT sample is biased toward engagements the player executed well — bad engagements (peeked, saw nothing, died) are invisible.
**Status:** Partially mitigated by kill-rate feature (DuelAttemptFinder counts hit + miss attempts). However, RT distribution itself still only covers successful hits.
**Residual risk:** Telling a user "your average RT is 320ms" understates their true average because all missed/lost duels are excluded.
**Prevention:** In interpretation copy, always caveat RT metrics with "measured on hits only." Consider flagging kill rate alongside RT — a player with 320ms RT but 30% kill rate is very different from 320ms with 70% kill rate.

### 2. Cross-player RT comparison requires matched conditions
**What goes wrong:** Comparing a user's RT against donk's RT without controlling for engagement_type (peek vs hold), map position, enemy velocity, crosshair_angle_at_t0, and weapon creates a meaningless number. Donk's demo set may have different distributions of peek vs hold, long-range vs close-range, etc.
**Consequence:** User sees "donk reacts 80ms faster than you" and draws a training conclusion that is not supported by the data.
**Prevention:** Only compare within matched strata. In v1, avoid cross-player comparisons entirely unless engagement_type and weapon are controlled. Present donk data as reference range, not benchmark.

### 3. Small sample (6 matches, ~30 moments) makes percentiles meaningless
**What goes wrong:** Calculating "you're in the 73rd percentile of T0→T1 times" from 30 data points produces numbers with massive confidence intervals. Any percentile claim is statistically noise.
**Prevention:** Do not present percentile rankings until N > 200 moments (roughly 20+ matches). Use ranges and distributions instead. Explicitly note sample size in all visualizations.

### 4. Crosshair angle at T0 conflates placement quality with map structure
**What goes wrong:** A high crosshair_angle_at_t0_deg may mean the player has poor crosshair placement, or it may mean the engagement scenario geometrically required a wide pan (unexpected peek from off-angle). Without controlling for scenario type, the metric is ambiguous.
**Prevention:** Only use crosshair_angle_at_t0_deg as a training signal within same map/position clusters. Tag moments with position metadata before drawing placement conclusions.

### 5. T1 detection (aim-start) is a heuristic, not ground truth
**What goes wrong:** T1 is inferred from second derivative spikes in pitch/yaw. This can false-positive on weapon recoil, mouse micro-corrections, or pre-spray. A player who fires immediately without a visible aim correction will have no detectable T1, which is correct — but one whose recoil pattern mimics an aim-start spike will get a wrong T1.
**Prevention:** Never surface raw T1 detection confidence to users. Treat T1 as internal decomposition tool. In user-facing output, focus on T0→T2 (total reaction) which is more robust than T0→T1.

### 6. Correlation between metrics is not causation for training
**What goes wrong:** Observing "your RT is higher when enemy velocity is higher" doesn't mean "train against moving targets to reduce RT." The relationship may be confounded by scenario type, map position, or weapon choice.
**Prevention:** Frame all findings as "observations in your data" not "causes of your performance." Avoid prescriptive training advice that isn't backed by controlled experiment or established coaching literature.

---

## B2C Product Pitfalls

### 1. Dashboard without interpretation = confusion, not value
**What goes wrong:** Users see histograms of RT distributions and numbers in milliseconds. They don't know if 320ms is good or bad, whether they should train or if the number is even meaningful. The "aha" moment never arrives. This is the project's own validated gap (see PROJECT.md: "эврика так и не наступила — нет интерпретации").
**Prevention:** The interpretation layer is the product, not the chart. Every metric must be accompanied by: (a) what it means, (b) whether this player's value is notable, (c) what — if anything — to do about it.

### 2. Complexity kills first-session retention
**What goes wrong:** Analytics tools that require users to understand methodology before seeing value lose most users in the first session. CS2 players are not data scientists. Asking them to understand T0/T1/T2/BVH/AABB before seeing a result will cause drop-off.
**Prevention:** First screen = one sentence verdict. "Your biggest gap vs donk is crosshair placement at first visibility — you're on average 23° off-target vs his 8°." Technical methodology goes in a collapsible "how this works" section, not the lead.

### 3. Building a product that serves the builder's curiosity, not the user's question
**What goes wrong:** The tool measures what's technically measurable (BVH T0, velocity at T0, AABB corner rays) rather than starting from what the user wants to know ("am I improving?", "what should I practice?"). Features get added because they're interesting to build, not because they answer a user question.
**Prevention:** Before each new feature, write the user-facing sentence it would produce. If you can't write it, don't build it. The kill-rate feature is a good example of the right order: insight first (hit rate was biased), then measurement.

### 4. No dedup in B2C pipeline means corrupt re-runs poison the dataset
**What goes wrong:** If a user submits the same demo twice, `DuelAttemptFinder` accumulates duplicate attempts in `*_attempts.csv`. Over time, kill rate numbers become silently wrong.
**Status:** Known gap in CONCERNS.md.
**Prevention:** Add dedup by `(match_id, moment_tick)` in DuelAttemptFinder before any B2C data processing.

### 5. Demo upload friction is higher than users expect
**What goes wrong:** FACEIT demos must be downloaded within 30 days. Valve MM demos have 7–14 day windows. If the B2C delivery flow requires a user to upload their own demo file, a significant fraction will have expired demos, download failures, or wrong demo format (POV vs GOTV).
**Prevention:** In v1, operate as a service: user provides match URL or match ID, you download and process. Don't require users to manage demo files manually.

### 6. Promising insights before you can deliver them at scale
**What goes wrong:** Landing page creates expectation of "analyze your demos." If the pipeline processes 1 demo/hour manually, early access users who signed up based on the promise will churn when the turnaround is days.
**Prevention:** Be explicit about turnaround time in early access. Set expectation before payment. Manual processing is fine in v1 if framed correctly ("we personally analyze each submission").

---

## Solo Developer Traps

### 1. Do NOT build a web upload interface in v1
Streamlit + manual pipeline is sufficient for early access. A web upload interface requires: file storage, job queue, background workers, error handling for malformed demos, and a frontend. That's 3–4x the complexity for a user base of 10–50. Email/form submission with manual processing scales to 100+ customers.

### 2. Do NOT build real-time or live analysis
Real-time analysis requires a fundamentally different architecture (GSI, game state integration, <100ms latency). GOTV demo analysis is batch-only. These are separate products. Do not let feature requests pull the project toward real-time without a full rewrite scope assessment.

### 3. Do NOT add per-map or per-position breakdown before N > 500 moments
Map/position breakdown slices an already small sample into meaningless strata. With 30 moments across 6 matches, position analysis produces noise. Defer until the dataset is large enough that each position bucket has > 30 moments.

### 4. Do NOT build team analytics as an extension of the solo-player tool
Team analytics (rotation timing, trade fragging, utility coordination) require different data structures, different T0 definitions, different interpretation frameworks. It is a separate product that happens to share the demo parsing layer. Do not scope-creep the B2C individual analysis tool into team analysis.

### 5. Do NOT surface T1 as a primary user-facing metric in v1
T1 detection is the least validated metric in the pipeline. It's useful for internal decomposition and research. Presenting it to users as "your aim-start latency is 109ms" implies precision the method doesn't have. Focus v1 user output on T0→T2 (total reaction) and kill rate, which are more robust.

### 6. Do NOT promise percentile comparisons until the dataset justifies them
Percentile claims ("you're in the top 15%") require a reference population. Currently: 1 player (donk), 6 matches. This is a reference, not a population. Do not present donk's numbers as a percentile scale. Present them as a named benchmark: "donk averaged X in comparable situations."

### 7. Do NOT parallelize the pipeline before the quality gate is done
Adding multiprocessing to `analyze_demo()` before Phase 6 quality gates are in place means parallelizing corrupt moments (T0 at search_start, duplicate enemies). Fix correctness first, then optimize throughput.

---

## Phase Mapping

| Pitfall | Phase to Address | Priority |
|-|-|-|
| T0 = search_start outlier inflation | Phase 6 | High |
| Overlapping search windows / duplicate enemy | Phase 6 | High |
| No dedup in DuelAttemptFinder | Phase 6 or before B2C | High |
| `.tri` file missing → no explicit error | Phase 6 (quick fix) | Medium |
| T1 as primary user metric | Interpretation layer | High |
| Cross-player RT comparison without matched conditions | Interpretation layer | High |
| Dashboard without interpretation = confusion | Interpretation layer | Critical |
| Survivorship bias caveat in RT output | Interpretation layer | High |
| Crosshair angle without scenario context | Interpretation layer | Medium |
| Small sample / no percentile claims | Interpretation layer | High |
| Demo upload friction in B2C flow | Djok delivery phase | Medium |
| No web upload in v1 | Djok delivery phase | High |
| MM demo vs FACEIT demo validation | Future scale phase | Low |
| awpy Python 3.14 compatibility | Ongoing / locked deps | Low |
| demoparser2 patch regression | Ongoing / test suite | Medium |
