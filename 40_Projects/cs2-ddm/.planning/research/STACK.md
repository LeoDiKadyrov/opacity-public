# Stack Research
_Generated: 2026-04-30_

## Summary

demoparser2 + awpy is the correct and current standard stack for CS2 demo analysis in Python — no credible alternative exists for the BVH geometric visibility work that Djok requires. The open B2C delivery question is how to package a Python CLI pipeline for paying users; the industry pattern is a web app with per-report pages, not PDF or Discord. The interpretation gap (metrics without meaning) is the primary unsolved UX problem across all competitors.

---

## Current Stack Assessment

### demoparser2

**Status: Keep. No viable alternative.**

demoparser2 (Rust-backed, by LaihoE) is the de facto CS2 demo parser for Python. awpy 2.x itself uses demoparser2 as its parsing backend. No other Python-native CS2 parser with comparable tick-level state extraction exists. The Rust backend gives it enough throughput for bulk processing — community projects (e.g., FlynnFc/CS2-Demo-parser) use it for batch-to-CSV pipelines without special multiprocessing tricks.

Alternatives exist in other languages only:
- Go: `demoinfocs-golang` (markus-wa) — not Python, rewrite required
- C#: `demofile-net` (saul) — not Python
- Java: `clarity` (skadistats) — not Python

For Djok's BVH+AABB T0 detection, there is no path forward without demoparser2 providing per-tick kinematic state.

**Version discipline:** Stay on 0.41.2+. CS2 patch 14155 broke 0.41.1 — the upgrade pattern will recur with future patches. Pin to `>=0.41.2` and monitor LaihoE/demoparser releases.

### awpy

**Status: Keep. The VisibilityChecker is irreplaceable for this project.**

awpy 2.0.2 provides the only accessible Python BVH Möller-Trumbore ray-triangle intersection against map .tri meshes. There is no drop-in replacement. The `VisibilityChecker` is the entire reason T0 detection works correctly for peek scenarios.

Constraint to document: `.tri` files must be present locally. This blocks any cloud deployment path unless .tri files are bundled with the server environment.

### Pandas + NumPy

**Status: Keep.** Standard, no reason to migrate. awpy 2.x internally uses Polars for its own DataFrames, but Djok's pipeline uses pandas throughout — migrating to Polars would be a rewrite with no current payoff. If bulk processing at 100+ demos shows memory pressure, revisit.

### Streamlit

**Status: Adequate for internal use; wrong for B2C delivery.**

Streamlit works well as an internal analysis dashboard but is a poor B2C delivery mechanism: it requires the user to run Python locally, has no auth, no persistent user state, and no shareable report URLs. For paying Djok users, Streamlit is a tool for Arystan to analyze data — not the product surface itself.

### Bulk Processing at 100+ Demos

No specific demoparser2 multiprocessing documentation found. Standard Python `multiprocessing.Pool` applies: each demo parse is CPU-bound and independent, making `Pool.map()` over a list of .dem paths the natural pattern. The Rust backend releases the GIL during parse, so `ProcessPoolExecutor` is safe. Practical limit: .tri file loading (awpy VisibilityChecker init) is expensive — instantiate one checker per map name per process, not per demo.

Architecture for 100+ demos:
```
ProcessPoolExecutor(max_workers=cpu_count)
  └─ per worker: load VisibilityChecker once per map, process N demos sequentially
```
Results stream to CSV via csv_utils append+dedup — already designed for this.

---

## Delivery Patterns

### How comparable tools deliver results to B2C users

**Leetify (industry reference):**
- Web app only. Per-match report pages with drill-down tabs (Rating Breakdown, Focus Areas, Accuracy, Utility).
- Demo uploaded via browser or browser extension (FACEIT demo auto-submit extension).
- No PDF export. No Discord bot. No CLI.
- Match list view → click match → full breakdown. Shareable URLs per match report.
- Subscription gates depth: free tier shows summary; paid shows per-round breakdown.

**Scope.gg:**
- Web app + 2D demo viewer rendered in browser (no game client required).
- Automatic highlight extraction, match history storage (Valve deletes demos after 14 days — scope.gg stores permanently).
- Subscription model with hard feature limits on free tier.

**Tracker.gg:**
- Web app, no demo required — pulls from public API/match history.
- Less depth than Leetify (no per-round breakdown), but broader game coverage.
- Insight layer: trend charts, personal benchmarks ("raise KD to X this week"), map/agent filters.

**Pattern consensus:**
| Delivery format | Used by | Notes |
|-|-|-|
| Web app (per-match report) | Leetify, Scope.gg, Tracker.gg | Industry standard |
| PDF report | None found | Not used by any major platform |
| Discord bot | None found at scale | Community bots exist but not primary delivery |
| CLI / local Python | None (internal tools only) | Not viable for paying B2C users |

**Implication for Djok:** The correct delivery surface is a web app with a per-player report page. For MVP with a solo developer, this means a minimal web interface that accepts a .dem file upload, runs the pipeline server-side, and returns a formatted report page. A shareable URL per analysis is table stakes.

**Simplest viable MVP path:** Streamlit served publicly (e.g., Railway, Render) with auth via email/token is faster to ship than a full web framework. Upgrade to FastAPI + React later when user volume justifies it. The .tri mesh constraint means cloud deployment must bundle map mesh files.

---

## Interpretation Layer Patterns

### How coaching insight is presented in comparable tools

**Leetify's model (most sophisticated reference):**
1. **Metric → benchmark comparison**: Every stat is shown against a percentile band (player pool average, FACEIT level X average). Color-coded: green = above average, orange/red = below. The player sees immediately where they sit relative to peers.
2. **Named focus areas**: Leetify groups metrics into named skill areas (Crosshair Placement, Accuracy, Utility, etc.) with a single score per area. Each area links to a dedicated drill-down.
3. **Plain English definitions**: Every metric has a glossary entry. "Crosshair placement = average degrees between your crosshair and the enemy from first spotting them to first damage." Not just a number — a definition of what it measures.
4. **Implicit coaching via benchmark**: Leetify does NOT say "train X." Instead it shows "your crosshair placement is 18°, FACEIT level 10 average is 11.2°" — the gap IS the recommendation. Users self-interpret.
5. **No explicit drill recommendations**: Leetify links to focus areas but does not prescribe "do aim_botz for 30 min." This gap is a known product limitation users complain about.

**Time to damage** — Leetify's closest metric to Djok's T0→T2:
- Defined as: time from first seeing enemy to first dealing damage. Excludes 1s+ (trigger discipline).
- Shown as a mean across matches, benchmarked against player pool.
- No decomposition into sub-components (Leetify does not have T0/T1/T2 — it treats the whole interval as one).

**Djok's differentiation is the decomposition**: T0→T1 (reaction lag) vs T1→T2 (aim execution) is not available in any competitor. This is the primary hook for interpretation: "your total time-to-damage is average, but your aim execution (T1→T2) is the bottleneck, not your reaction (T0→T1)."

**Crosshair angle at T0 (Djok-specific):**
Leetify measures crosshair-to-enemy distance as "crosshair placement." Djok measures it at the precise T0 moment (BVH geometric first visibility), which is more accurate. The interpretation pattern is identical to Leetify's: show degrees, show a benchmark, name the gap.

**Coaching recommendation format that works:**
Based on Leetify's pattern and the project's own hypothesis ("raw RT similar, crosshair angle is the gap"):
```
Metric: Crosshair angle at T0
Your value: 22°
Reference (donk): 8°
Gap: 14°
What this means: When enemies first become visible, your crosshair is 22° away from them.
  That gap is time lost before aim adjustment begins.
What to train: Crosshair placement drills (e.g., aim_botz static targets, prefire maps).
  Focus on: common angles on [map], reduce pre-engagement crosshair drift.
```
This is the explicit coaching format Leetify does NOT provide. It is Djok's differentiator.

---

## Recommendations

### 1. Keep the full current stack

demoparser2 + awpy + pandas + numpy — no changes. The BVH T0 detection is the core technical moat. Any migration away from awpy's VisibilityChecker eliminates it.

### 2. Deliver interpretation before delivery surface

The interpretation layer (metric → benchmark → gap → coaching directive) is the product differentiator. Build it in Python as a report generator first — the output can be rendered anywhere (Streamlit, HTML email, web app). Don't block interpretation work on choosing a delivery format.

### 3. Delivery surface: Streamlit public deployment as MVP

For a solo developer, Streamlit deployed publicly (Railway or Render, ~$5/mo) with .tri files bundled is the fastest path to a B2C-accessible report. Add email-gated access (Tally form already exists per landing page) for early access users. Upgrade to FastAPI + minimal frontend only when Streamlit's limitations block growth.

### 4. Bulk pipeline: ProcessPoolExecutor with per-map VisibilityChecker caching

Do not instantiate a new VisibilityChecker per demo. Cache by map name within each worker process. Use `concurrent.futures.ProcessPoolExecutor` with `max_workers=os.cpu_count()`. Stream results to CSV via existing csv_utils as each demo completes.

### 5. Interpretation layer structure

Use Leetify's benchmark model but add explicit coaching directives (their known gap):
- Show player metric vs donk/reference value
- Name the gap in plain language
- Map gap to specific training prescription
- Color-code by severity (red = biggest gap from reference)

Priority order of metrics to interpret (based on differentiation value):
1. T0→T1 vs T1→T2 breakdown (unique to Djok — no competitor has this)
2. Crosshair angle at T0 (more precise than Leetify's crosshair placement)
3. Kill rate (T0-anchored — already implemented)
4. Engagement type split (peek vs hold RT separately)

---

## Sources

- [demoparser2 GitHub (LaihoE)](https://github.com/LaihoE/demoparser)
- [awpy 2.0.2 PyPI](https://pypi.org/project/awpy/)
- [awpy documentation](https://awpy.readthedocs.io/en/latest/examples/parse_demo.html)
- [FlynnFc CS2-Demo-parser (bulk reference)](https://github.com/FlynnFc/CS2-Demo-parser)
- [Leetify Stats Glossary](https://leetify.com/blog/leetify-stats-glossary/)
- [Leetify CS2 Benchmarks](https://leetify.com/blog/cs2-benchmarks/)
- [Leetify Rating Breakdown](https://leetify.com/blog/rating-breakdown/)
- [Leetify FACEIT Demo Upload](https://leetify.com/blog/faceit-uploads/)
- [Scope.gg CS2 analytics overview](https://scope.gg/)
- [Leetify Aim Rating explanation (zleague)](https://www.zleague.gg/theportal/demystifying-leetifys-aim-rating-in-counter-strike-a-gamers-guide/)
- [Leetify time to damage (Steam discussion)](https://steamcommunity.com/app/730/discussions/0/4417550330718783276/)
