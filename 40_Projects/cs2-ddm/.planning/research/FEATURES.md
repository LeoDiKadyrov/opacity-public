# Features Research
_Generated: 2026-04-30_

## Summary

The B2C esports analytics space (Leetify, scope.gg, Noesis, csstats.gg) has converged on a clear pattern: raw metrics without context create confusion, not improvement. The tools that retain users longest give every metric a rank-relative benchmark, a plain-English explanation of what it means, and a concrete next action. Djok has a unique technical edge — the T0/T1/T2 decomposition is more precise than anything Leetify or scope.gg offer — but without an interpretation layer, users experience the same "so what?" dead end they get elsewhere.

---

## Table Stakes Features

These are the minimum bar. Without them, users churn within one session.

| Feature | Why Expected | Source Evidence |
|-|-|-|
| Benchmark / percentile per metric | Users need context. "180ms" means nothing; "top 15% for your rank" means something. Leetify's entire Aim Rating system is built on z-scores vs. rank-matched population. | Leetify benchmarks blog, Steam discussions |
| Plain-English metric explanation | Every metric needs a one-sentence "what this means" in-context. Leetify provides a glossary + inline tooltips. Without this, users can't act. | Leetify Stats Glossary, scope.gg guides |
| Separation of composite vs. atomic metrics | Leetify explicitly warns "Time to Damage is NOT reaction time — it's accuracy + crosshair placement + RT combined." Conflation destroys actionability. | Steam CS2 discussions on TTD |
| Friend / self comparison | Side-by-side comparison is the highest-engagement feature in Leetify ("compare two players" is a top-linked page). The "friend vs. donk" example in PROJECT.md is the core use case. | Leetify compare URL structure, user quotes |
| Trend over time | Single-session snapshots don't drive retention. Users return when they can see progress (or regression) across matches. | General analytics tool pattern, Leetify match history |
| Export / shareable result | Users sharing their stats on Discord/Reddit is a primary B2C acquisition channel. Leetify, csstats, tracker.gg all invest heavily in shareable cards. | Community behavior pattern |

---

## Differentiators

Features that set tools apart — not expected, but cause "this is the tool I actually use."

| Feature | Value Proposition | Who Does It | Notes |
|-|-|-|-|
| Atomic decomposition of RT (T0/T1/T2) | No existing tool separates "time to first see enemy" from "time to start aiming" from "time to hit." This is Djok's unique claim. | Nobody currently | Leetify's "crosshair placement" conflates T0→T1 and T1→T2 into TTD |
| Crosshair angle at T0 in degrees | Exact angular error at the moment of first visibility. More precise than Leetify's averaged TTD-derived crosshair score. | Nobody at this precision | Leetify derives from TTD, not geometric T0 |
| Peek vs. hold classification | Separating high-velocity peek reactions from static angle holds gives meaningfully different coaching signals. | Partially in scope.gg | Djok's velocity gate is more principled |
| Pro comparison (donk as reference) | "Here's how your T0→T1 compares to donk's on the same map geometry" is a concrete, emotionally resonant benchmark. | HLTV has aggregate pro stats; nobody does per-metric pro comparison this granularly | Requires donk dataset to grow |
| Kill rate normalized by duel attempts | Most tools report K/D or HS%. Kill rate anchored to visible-duel attempts (hits + misses) is a more honest measure of conversion efficiency. | Nobody | Djok already built this (DuelAttemptFinder) |

---

## Interpretation & Coaching Patterns

How the best tools translate a number into an action.

### Pattern 1: Threshold with color coding, no prose needed at first glance
Leetify uses green/yellow/red relative to rank median. User sees red on "crosshair placement" → knows this is the problem area before reading a word. Color removes cognitive load for the initial scan.

Implication for Djok: For crosshair_angle_at_t0_deg, define thresholds. Based on Leetify's crosshair placement data (elite players average <5° offset at damage, amateur average ~15-25°), reasonable tiers:
- < 10°: good (green)
- 10–25°: needs work (yellow)
- > 25°: primary problem (red)

### Pattern 2: Metric → Cause → Drill (the coaching chain)
The pattern used by every effective esports coaching tool:
1. Metric: "Your crosshair angle at T0 averages 28°"
2. Cause: "This means you're not pre-aiming common positions — your crosshair is far from enemy when they appear"
3. Drill: "Practice aim_botz with position-specific pre-aim scenarios on this map"

Leetify does this explicitly in its improvement guides. Scope.gg links metrics directly to their Learning Center guides. The critical insight: the drill recommendation must be specific, not generic ("practice more" is useless).

### Pattern 3: Composite → Components (drill down)
Leetify's Aim Rating (composite) → TTD, crosshair placement, spotted accuracy (components). Users who want to understand drill into the breakdown. This prevents overwhelming beginners while satisfying advanced users.

For Djok: RT_visible_to_hit_ms (composite) → RT_visible_to_aim_ms (T0→T1) + RT_aim_to_hit_ms (T1→T2). The composite should be the headline; the components are the diagnosis.

### Pattern 4: "Compare to pros" requires careful framing
The raw reaction time of pro players is 130-160ms on simple stimulus tests, but in-game T0→T2 for donk is in the 150-400ms range depending on crosshair placement and engagement type. The survivorship bias issue (only successful duels are measurable) must be called out explicitly — Leetify's blog post on benchmarks addresses this.

For Djok: framing is "here's how your peek mechanics compare to donk on equivalent engagement types" not "your RT vs. donk's RT." The distinction prevents users from dismissing valid data ("he's just a pro, of course he's faster").

### Pattern 5: Minimum viable interpretation = percentile + one sentence
The floor for actionable output is: a number, where you rank among a reference group, and one sentence of "this means X." Everything else is enhancement. Leetify's initial version used this exact minimum.

---

## Anti-Features

Things deliberately NOT to build in v1.

| Anti-Feature | Why Avoid | What to Do Instead |
|-|-|-|
| Map/position breakdown | Requires 100+ demos per position to be statistically meaningful. False precision misleads. | Add this only after dataset covers 50+ matches |
| Opponent difficulty weighting | Leetify tried this; users found it confusing and disputed the methodology. | Keep kill rate normalized, don't add opponent ELO adjustment yet |
| "Your reaction time is X ms" as a headline metric | RT in isolation is the metric users misinterpret most. They'll compare to YouTube reaction tests (simple RT ≠ in-game RT). | Lead with crosshair angle at T0 as the primary actionable insight, RT as secondary |
| Biometric correlation | Oura/sleep integration is a far-future feature. No existing tool does this at B2C scale. | Explicitly out of scope per PROJECT.md |
| Real-time coaching overlay | Different architecture, different product. Not buildable with current GOTV demo pipeline. | Post-match analysis only |
| Percentile rankings before you have a population | Without 1000+ player dataset, percentile comparisons are meaningless. | Use donk as the reference benchmark instead; phrase as "vs. pro reference" |

---

## Recommendations for Djok

Ordered by impact-to-effort ratio for next phases.

**1. Interpretation layer with thresholds (highest priority, matches PROJECT.md Active)**

For each key metric, define three tiers with labels and one-sentence explanations. Minimum set:
- `crosshair_angle_at_t0_deg`: < 10° (sharp pre-aim), 10–25° (needs positioning work), > 25° (primary problem)
- `rt_visible_to_aim_ms` (T0→T1): < 150ms (fast pickup), 150–300ms (normal), > 300ms (slow recognition)
- `rt_aim_to_hit_ms` (T1→T2): < 100ms (efficient execution), 100–200ms (normal), > 200ms (accuracy issue)

Each tier should link to a specific drill or category of drill. This transforms the Streamlit dashboard from a data display to a coaching report.

**2. Side-by-side comparison view (donk as reference)**

The "friend vs. donk" use case from PROJECT.md validation is the hook that creates the "aha" moment. Build a comparison table: player metric | player tier | donk benchmark | gap. This requires only the existing data — no new detection logic.

**3. Composite → component drill-down in the UI**

Surface RT_visible_to_hit_ms as the headline, then let users expand to see T0→T1 and T1→T2 separately. This matches the Leetify pattern that works: simple score first, breakdown for diagnosis.

**4. Shareable report card (medium priority, acquisition channel)**

A static HTML or image export with: top 3 metrics, color-coded status, "compared to pro reference." This is how B2C analytics tools get organic distribution. Even a screenshot-friendly Streamlit layout serves this purpose initially.

**5. Do NOT build percentiles yet**

Without 500+ analyzed players, percentile rankings will be misleading. Use donk as the single reference point. Frame it as "pro benchmark comparison" — this is more honest and more emotionally engaging than a synthetic percentile.

**6. One coaching recommendation per weakest metric**

After ranking the player's metrics, surface one specific recommendation for their worst-performing metric. One recommendation, not five. Specificity beats comprehensiveness — this is the pattern that distinguishes tools users actually act on from tools they abandon after two sessions.
