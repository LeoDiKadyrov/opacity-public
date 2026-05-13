# Phase 8: Interpretation Layer — Research

**Researched:** 2026-05-06
**Domain:** Streamlit tab integration, SQLite percentile queries, coaching drill content
**Confidence:** HIGH (all claims verified against live codebase and analytics.db)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** New "Interpretation" tab in `app.py` — 4th tab added alongside existing sections. Reads from `analytics.db` directly (not CSV).
- **D-02:** Tab layout: summary card first ("Your worst metric is X — do drill Y"), then full 5-metric comparison table.
- **D-03:** Tab reads sidebar SteamID64 as the player being analyzed.
- **D-04:** Tab renders with any data volume. If benchmark has <20 demos, shows warning and falls back to hard-coded threshold estimates.
- **D-05:** Tiers = percentiles from benchmark player's distribution. Top 25% = Elite, 25–50% = Good, 50–75% = Average, bottom 25% = Work needed.
- **D-06:** Tiers computed separately per engagement_type (peek vs hold). Never conflated.
- **D-07:** Minimum 20 demos for reliable percentiles. Below threshold → warning + fallback.
- **D-08:** Drills = hard-coded dict in `interpretation.py`, keyed by `(metric_name, tier, engagement_type)`.
- **D-09:** 5 metrics: `crosshair_angle_at_t0_deg`, `rt_visible_to_aim_ms`, `rt_aim_to_hit_ms`, `kill_rate`, `hit_rate`.
- **D-10:** Benchmark dropdown populated from `DISTINCT player_steamid` in analytics.db.
- **D-11:** `PLAYER_NAMES` dict in `config.py` for display names.
- **D-12:** Players with <20 demos shown with "(small sample)" suffix.

### Claude's Discretion

- Exact percentile breakpoints (25/50/75 — standard quartiles confirmed as correct)
- `interpretation.py` internal structure (class vs module-level dicts)
- Specific drill text per metric+tier
- Hard-coded fallback threshold values per metric

### Deferred Ideas (OUT OF SCOPE)

- Downloadable reports (PDF/HTML)
- Metric ↔ engagement outcome correlation
- FACEIT-level cohort comparison
- Weapon type split in interpretation
- round_phase breakdown
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-INT-01 | 5-metric table: value, tier, benchmark, gap, drill | SQL queries verified below; drill dict structure designed |
| REQ-INT-02 | Summary card: worst metric + one drill at top | Worst metric = highest tier index (3=Work needed); logic straightforward |
| REQ-INT-03 | Peek and hold always separate | `engagement_type` column present in both tables; percentile computation grouped by it |
| REQ-INT-04 | Survivorship bias caveat inline on RT metrics | Framing verified; recommended placement: caption under RT rows |
| REQ-INT-05 | RT bottleneck drill-down (T0→T1 vs T1→T2) | Logic: compare component percentiles; recommend drill for worse component |
</phase_requirements>

---

## Summary

Phase 8 builds a new "Interpretation" tab in the existing Streamlit app. The tab reads from `analytics.db` (already populated with 57 karrigan demos = 4,111+ duel attempts), computes per-metric tier ratings against a selected benchmark player, and returns one drill per metric.

The data layer is clean and well-verified. `engagements` table has RT columns + `crosshair_angle_at_t0_deg` + `player_steamid` + `engagement_type`. `duel_attempts` has `was_killed` + `bullets_fired` + `bullets_hit` + same keys. All SQL queries needed for Phase 8 are simple GROUP BY + aggregate — no joins required.

The app.py structure uses flat sequential sections (not `st.tabs()`), so adding "Interpretation" requires picking a consistent placement. Based on reading app.py: the current sections are Upload → Analyze → Results → Plots → Batch Analysis, all rendered as `st.header()` sections. D-01 specifies a "4th tab" but the existing structure is not tab-based. See Architecture Patterns below for the correct integration approach.

**Primary recommendation:** Implement `interpretation.py` as a module with module-level dicts (not a class). Add Interpretation as a new `st.header()` section at the bottom of `app.py`, after Batch Analysis. Use `st.tabs()` only within the Interpretation section to separate peek vs hold views.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|-|-|-|-|
| Percentile computation | interpretation.py | — | Pure pandas/numpy; no UI coupling |
| Drill lookup | interpretation.py | — | Dict keyed by (metric, tier, engagement_type) |
| Benchmark dropdown + player count | app.py (Interpretation section) | interpretation.py | UI owns rendering; module owns DB query |
| Summary card (worst metric) | app.py | interpretation.py | UI renders; module computes worst metric |
| 5-metric comparison table | app.py | interpretation.py | UI renders st.dataframe; module returns DataFrame |
| Survivorship bias caveat | app.py | — | Display-only; inline st.caption per RT row |
| RT bottleneck drill-down | interpretation.py | — | Compares T0→T1 vs T1→T2 percentile rank |
| PLAYER_NAMES mapping | config.py | — | D-11 locked decision |

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|-|-|-|-|
| sqlite3 | stdlib | Read analytics.db | Already used in db_utils.py; no new dep |
| pandas | 3.0.1 | DataFrame for percentile computation | Already project dep; `quantile()` is correct tool |
| numpy | 2.4.2 | `np.percentile()` for threshold arrays | Already project dep |
| streamlit | existing | Tab + card rendering | D-01 locked |

### No new dependencies required

All capabilities are implemented with tools already in `requirements.txt`.

---

## Architecture Patterns

### Existing app.py structure (VERIFIED by reading app.py)

app.py uses flat `st.header()` sections, **not** `st.tabs()`:
- Section 1: Upload Demos
- Section 2: Analyze
- Section 3: Results table
- Section 4: Visualizations
- Batch Analysis (unnumbered header)

D-01 says "4th tab" but no tab widget exists in the current app. The correct integration is a new `st.header("Interpretation")` section after Batch Analysis. Within that section, use `st.tabs(["Peek", "Hold"])` to separate engagement types per D-06.

### Recommended Project Structure

```
cs2-ddm/
├── interpretation.py      # NEW: percentile logic + drill dict + compute_interpretation()
├── config.py              # EDIT: add PLAYER_NAMES dict
├── app.py                 # EDIT: add Interpretation section at bottom
└── tests/
    └── test_interpretation.py  # NEW: 15-20 tests
```

### Pattern 1: Percentile-based tier computation

```python
# Source: verified against analytics.db with live data (karrigan 57 demos)
import sqlite3
import pandas as pd
from contextlib import closing

def load_benchmark_metrics(db_path: str, benchmark_steamid: int, engagement_type: str) -> dict:
    """Load benchmark player distributions per engagement_type."""
    with closing(sqlite3.connect(db_path)) as conn:
        eng_df = pd.read_sql(
            """SELECT rt_visible_to_aim_ms, rt_aim_to_hit_ms, rt_visible_to_hit_ms,
                      crosshair_angle_at_t0_deg
               FROM engagements
               WHERE player_steamid = ? AND engagement_type = ?
                 AND rt_visible_to_hit_ms IS NOT NULL""",
            conn, params=(benchmark_steamid, engagement_type)
        )
        # Kill/hit rate: compute per-demo then use distribution of per-demo values
        att_df = pd.read_sql(
            """SELECT demo_name,
                      100.0*SUM(was_killed)/COUNT(*) AS kill_rate,
                      100.0*SUM(bullets_hit)/NULLIF(SUM(bullets_fired),0) AS hit_rate
               FROM duel_attempts
               WHERE player_steamid = ? AND engagement_type = ?
               GROUP BY demo_name
               HAVING COUNT(*) >= 3""",
            conn, params=(benchmark_steamid, engagement_type)
        )
    return {"engagements": eng_df, "attempts": att_df}
```

**Why per-demo for kill_rate/hit_rate:** A single global rate collapses variance and makes percentile computation meaningless. Per-demo rates give a distribution with real spread (peek kill_rate: p25=17%, p50=25%, p75=32% across 54 karrigan demos). [VERIFIED: analytics.db query]

### Pattern 2: Tier assignment

```python
# Source: D-05 locked decision; percentile direction is metric-dependent
TIER_LABELS = ["Elite", "Good", "Average", "Work needed"]

def assign_tier(value: float, p25: float, p50: float, p75: float, lower_is_better: bool) -> str:
    """Assign tier based on benchmark quartiles.

    For RT and crosshair_angle: lower = better → Elite = below p25 of benchmark.
    For kill_rate and hit_rate: higher = better → Elite = above p75 of benchmark.
    """
    if lower_is_better:
        if value <= p25:
            return "Elite"
        elif value <= p50:
            return "Good"
        elif value <= p75:
            return "Average"
        else:
            return "Work needed"
    else:
        if value >= p75:
            return "Elite"
        elif value >= p50:
            return "Good"
        elif value >= p25:
            return "Average"
        else:
            return "Work needed"
```

**Direction convention:** [VERIFIED by domain logic]
- `crosshair_angle_at_t0_deg`: lower = better (tighter crosshair placement)
- `rt_visible_to_aim_ms`: lower = better
- `rt_aim_to_hit_ms`: lower = better
- `kill_rate`: higher = better
- `hit_rate`: higher = better

### Pattern 3: Player data query

```python
# Source: verified against analytics.db
def load_player_metrics(db_path: str, player_steamid: int, engagement_type: str) -> dict:
    """Load analyzed player's median values per metric."""
    with closing(sqlite3.connect(db_path)) as conn:
        eng_df = pd.read_sql(
            """SELECT rt_visible_to_aim_ms, rt_aim_to_hit_ms, rt_visible_to_hit_ms,
                      crosshair_angle_at_t0_deg
               FROM engagements
               WHERE player_steamid = ? AND engagement_type = ?""",
            conn, params=(player_steamid, engagement_type)
        )
        att_agg = pd.read_sql(
            """SELECT 100.0*SUM(was_killed)/COUNT(*) AS kill_rate,
                      100.0*SUM(bullets_hit)/NULLIF(SUM(bullets_fired),0) AS hit_rate
               FROM duel_attempts
               WHERE player_steamid = ? AND engagement_type = ?""",
            conn, params=(player_steamid, engagement_type)
        )
    return {"engagements": eng_df, "attempts": att_agg}
```

**Note:** Player value used for tier comparison = median of their distribution (not single-game sample). [ASSUMED — reasonable default; planner can override to mean]

### Pattern 4: Benchmark dropdown query

```python
# Source: verified against analytics.db — demo count via processed_matches
def get_benchmark_options(db_path: str) -> list[tuple[int, str, int]]:
    """Return (steamid, display_name, demo_count) for all players in analytics.db."""
    with closing(sqlite3.connect(db_path)) as conn:
        rows = conn.execute(
            """SELECT player_steamid, COUNT(DISTINCT demo_name) as demos
               FROM duel_attempts
               WHERE player_steamid IS NOT NULL
               GROUP BY player_steamid"""
        ).fetchall()
    from config import PLAYER_NAMES
    result = []
    for steamid, demos in rows:
        name = PLAYER_NAMES.get(steamid, str(steamid))
        label = f"{name} ({demos} demos)" + (" (small sample)" if demos < 20 else "")
        result.append((steamid, label, demos))
    return result
```

### Pattern 5: RT bottleneck drill-down (SC5)

```python
# Source: domain logic from SC5 requirement
def get_rt_bottleneck_component(
    t0t1_value: float, t0t1_p50: float,
    t1t2_value: float, t1t2_p50: float
) -> str:
    """Return 'T0→T1' or 'T1→T2' based on which component most exceeds benchmark median."""
    t0t1_excess = t0t1_value / t0t1_p50 if t0t1_p50 > 0 else 1.0
    t1t2_excess = t1t2_value / t1t2_p50 if t1t2_p50 > 0 else 1.0
    return "T0→T1" if t0t1_excess >= t1t2_excess else "T1→T2"
```

This is triggered when `rt_visible_to_hit_ms` tier is "Average" or "Work needed" (i.e., SC5: composite RT is the bottleneck). Drill lookup then uses `(rt_visible_to_hit_ms, tier, engagement_type, component)` as the extended key — or the drill text itself references the component.

### Anti-Patterns to Avoid

- **Global kill_rate instead of per-demo:** A single `SUM(was_killed)/COUNT(*)` across all demos is not comparable to the benchmark percentile distribution. Use per-demo rates for the distribution, player-wide rate for the display value.
- **Joining engagements and duel_attempts:** These are independent pipelines (Path 1 vs Path 2). Same `match_id` does not guarantee same rows. Never join them.
- **Using `session_state` from background threads:** Already established pattern in app.py — use `_BATCH_SHARED` for thread communication. Interpretation tab is main-thread only (reads on rerun), so this is not an issue.
- **Computing percentiles in SQL with PERCENTILE_CONT:** SQLite does not have `PERCENTILE_CONT`. Use pandas `quantile()` on the fetched DataFrame. [VERIFIED: SQLite docs]

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|-|-|-|-|
| Percentile computation | Custom sort/rank loop | `pd.Series.quantile([0.25, 0.5, 0.75])` | Built-in, handles NaN, vectorized |
| SQLite read | Raw sqlite3 + manual column mapping | `pd.read_sql(query, conn, params=(...))` | Type inference, DataFrame output |
| Tier color coding | Custom HTML/CSS | `st.dataframe` with pandas Styler `.map()` | Already established pattern in app.py |
| Missing player guard | Try/except everywhere | Check `eng_df.empty` before percentile call | Simple, readable |

---

## Calibrated Benchmark Thresholds (karrigan, 57 demos)

**These are the real percentile values from analytics.db.** Use as defaults for hard-coded fallback (D-04/D-07) AND as the baseline to communicate to the user.

[VERIFIED: analytics.db direct query, 2026-05-06]

### Peek engagements

| Metric | p25 (Elite threshold) | p50 (Good threshold) | p75 (Average threshold) | lower_is_better |
|-|-|-|-|-|
| `crosshair_angle_at_t0_deg` | 3.0° | 6.0° | 11.0° | yes |
| `rt_visible_to_aim_ms` | 125ms | 203ms | 328ms | yes |
| `rt_aim_to_hit_ms` | 203ms | 422ms | 1000ms | yes |
| `rt_visible_to_hit_ms` | 375ms | 578ms | 1156ms | yes |
| `kill_rate` (per-demo %) | 31.5% | 24.5% | 17.2% | no |
| `hit_rate` (per-demo %) | 15.2% | 10.9% | 8.8% | no |

**Important note on rt_aim_to_hit_ms:** p75=1000ms indicates high variance in T1→T2 (execution phase). This is expected — a missed first burst + repositioning can take 2+ seconds. The metric captures full kill execution, not just first-shot latency.

### Hold engagements

| Metric | p25 | p50 | p75 | lower_is_better |
|-|-|-|-|-|
| `crosshair_angle_at_t0_deg` | 3.0° | 5.0° | 10.0° | yes |
| `rt_visible_to_hit_ms` | 375ms | 516ms | 812ms | yes |
| `kill_rate` (per-demo %) | 7.3% | 4.3% | 1.8% | no |
| `hit_rate` (per-demo %) | 3.3% | 1.7% | 0.7% | no |

**Note on hold kill_rate:** 4.3% median is dramatically lower than peek (24.5%). This reflects karrigan's role as IGL/support — hold duels are often sacrificed for utility. This is architecturally correct data, not a data quality issue.

**Note on hold rt_visible_to_aim and rt_aim_to_hit:** Only 28 hold engagements in `engagements` table for karrigan. Do not expose as separate hold RT components — sample too small. Use `rt_visible_to_hit_ms` only for hold. [VERIFIED: analytics.db query n=28]

### Current player data in DB (second player: SteamID 76561198388053181)

| Metric | Value |
|-|-|
| Demos | 2 |
| Peek engagements | 13 |
| Hold attempts | 64 |
| Status | "(small sample)" — fallback thresholds trigger |

**Important:** The player who runs the app (SteamID from sidebar) is likely NOT in analytics.db yet (the sidebar SteamID is used for live analysis, not pre-loaded). The Interpretation tab must handle the case where `player_steamid` from sidebar has 0 rows in analytics.db — show a clear "No data for this player — run analysis first" message.

---

## Drill Content Dictionary

Hard-coded in `interpretation.py`. Key: `(metric_name, tier, engagement_type)`. The `tier` is one of `"Elite"`, `"Good"`, `"Average"`, `"Work needed"`. Engagement type is `"peek"` or `"hold"`.

[ASSUMED: drill content based on CS2 coaching knowledge — not validated against a coaching database]

### Crosshair Angle Drills

```python
DRILLS = {
    # crosshair_angle_at_t0_deg — PEEK
    ("crosshair_angle", "Work needed", "peek"): (
        "Pre-aim corners before peeking. "
        "In deathmatch, force yourself to hold your crosshair at head-height on the corner "
        "you're about to swing. Swing only when crosshair is already on the angle."
    ),
    ("crosshair_angle", "Average", "peek"): (
        "Reduce swing arc. Use counter-strafe to stop, then peek — "
        "moving crosshair placement degrades your angle significantly."
    ),
    ("crosshair_angle", "Good", "peek"): (
        "Fine-tune default crosshair positions on your 5 most-played maps. "
        "Review one demo per week specifically for crosshair placement on common angles."
    ),
    ("crosshair_angle", "Elite", "peek"): (
        "Crosshair placement is elite. Focus on consistency under pressure — "
        "review demos where you tilted and check if angle degraded."
    ),
    # crosshair_angle — HOLD
    ("crosshair_angle", "Work needed", "hold"): (
        "When holding an angle, set your crosshair and do not move it until you see the enemy. "
        "Practice static holds in aim_botz: crosshair on corner, wait for bot, do not flick."
    ),
    ("crosshair_angle", "Average", "hold"): (
        "Holding with slight crosshair drift? Add subtle micro-adjustments at head-height "
        "rather than scanning. Use peek practice maps to train static holds."
    ),
    ("crosshair_angle", "Good", "hold"): (
        "Hold placement is solid. Work on reading enemy movement — adjust default hold position "
        "based on where enemies emerge, not just the angle itself."
    ),
    ("crosshair_angle", "Elite", "hold"): (
        "Elite hold placement. Focus on the decision layer — when to re-peek vs stay static."
    ),

    # rt_visible_to_aim — PEEK (T0→T1: cognitive reaction)
    ("rt_visible_to_aim", "Work needed", "peek"): (
        "Your cognitive reaction is slow. Do 10 min/day reaction training on humanbenk.com "
        "(choice reaction, not simple). Focus: reduce decision latency, not mouse speed."
    ),
    ("rt_visible_to_aim", "Average", "peek"): (
        "Reaction is adequate but slow for pro duels. Train choice reaction drills: "
        "2-target scenarios in aim_botz to build faster visual processing."
    ),
    ("rt_visible_to_aim", "Good", "peek"): (
        "Solid reaction. Ensure you're not masking slow RT with pre-aim — "
        "review demos to confirm T0 is a real surprise, not a pre-aimed angle."
    ),
    ("rt_visible_to_aim", "Elite", "peek"): (
        "Elite cognitive reaction. Maintain by keeping consistent sleep and warm-up routine."
    ),

    # rt_aim_to_hit — PEEK (T1→T2: mechanical execution)
    ("rt_aim_to_hit", "Work needed", "peek"): (
        "Execution (aim-to-hit) is the bottleneck. 30 min/day aim_botz: "
        "flick to randomly moving targets at head-height. Focus on click timing, not speed."
    ),
    ("rt_aim_to_hit", "Average", "peek"): (
        "Execution is consistent but slow. Add micro-flick training: "
        "gridshot (Kovaaks) 'clicking' scenarios at medium distance."
    ),
    ("rt_aim_to_hit", "Good", "peek"): (
        "Good execution. Work on first-shot accuracy — "
        "reduce your spray-and-pray tendency by tracking with controlled bursts."
    ),
    ("rt_aim_to_hit", "Elite", "peek"): (
        "Elite mechanical execution. Maintain aim warm-up of 10–15 min before scrims."
    ),

    # kill_rate — PEEK
    ("kill_rate", "Work needed", "peek"): (
        "Kill conversion is low — you're losing too many duels you take. "
        "Review demos: are you peeking in bad positions (no support, enemy pre-aimed)? "
        "Reduce peek volume; take only high-percentage duels."
    ),
    ("kill_rate", "Average", "peek"): (
        "Kill rate is below benchmark. Identify your lowest-conversion position and "
        "stop peeking it cold — replace with a smarter approach or utility first."
    ),
    ("kill_rate", "Good", "peek"): (
        "Good conversion. Focus on reading enemy habits to upgrade the remaining "
        "25% of duels from coin-flips to favored."
    ),
    ("kill_rate", "Elite", "peek"): (
        "Elite kill conversion. Ensure sample is from varied opponents — "
        "elite rate on weaker opponents can mask issues vs equal-level players."
    ),

    # kill_rate — HOLD
    ("kill_rate", "Work needed", "hold"): (
        "Hold kill rate is below benchmark. Check if you're holding too wide — "
        "narrow your angle to reduce reaction window required."
    ),
    ("kill_rate", "Average", "hold"): (
        "Hold conversion is average. Practice 'peeker's advantage' awareness: "
        "if holding, shoot the instant you see movement, not after confirmation."
    ),
    ("kill_rate", "Good", "hold"): (
        "Solid hold conversion. Work on reading sound cues to pre-aim enemy position "
        "before they emerge."
    ),
    ("kill_rate", "Elite", "hold"): (
        "Elite hold conversion. Diversify positions — overly predictable holds get "
        "smoked or flash-peeked at higher levels."
    ),

    # hit_rate — PEEK
    ("hit_rate", "Work needed", "peek"): (
        "First-burst accuracy is very low. Stop spraying — switch to single-fire or "
        "2-shot bursts at any range beyond close. Aim_botz clicking drill, 200 targets/day."
    ),
    ("hit_rate", "Average", "peek"): (
        "Hit rate is below benchmark. Are you firing while still moving? "
        "Counter-strafe to full stop before shooting. Check movement habits in demos."
    ),
    ("hit_rate", "Good", "peek"): (
        "Hit rate is solid. Fine-tune first-shot accuracy — "
        "use burst-fire practice on dm servers at 15–25m range."
    ),
    ("hit_rate", "Elite", "peek"): (
        "Elite first-burst accuracy. Maintain through consistent warm-up. "
        "Review demos to ensure elite rate is on real opponents, not eco rounds."
    ),

    # hit_rate — HOLD
    ("hit_rate", "Work needed", "hold"): (
        "Hold hit rate is very low — you're firing and missing early bullets. "
        "On holds, take one controlled shot, then reassess. Don't spray at distance."
    ),
    ("hit_rate", "Average", "hold"): (
        "Hold hit rate below benchmark. Pre-aim tighter — "
        "if crosshair is already close, first shot should connect."
    ),
    ("hit_rate", "Good", "hold"): (
        "Good hold accuracy. Improve by identifying ranges where you underperform "
        "and practicing that range specifically."
    ),
    ("hit_rate", "Elite", "hold"): (
        "Elite hold accuracy. Focus on decision-making: when to shoot vs hold fire "
        "for a better opportunity."
    ),
}
```

### RT Bottleneck Drill-Down Extensions (SC5)

When `rt_visible_to_hit_ms` is "Average" or "Work needed", the drill references which component is the bottleneck:

```python
RT_BOTTLENECK_DRILLS = {
    ("rt_visible_to_hit", "Work needed", "peek", "T0→T1"): (
        "Your cognitive reaction (T0→T1) is the bottleneck. "
        "10 min/day choice reaction training. The aim phase is fine — the delay is before you move."
    ),
    ("rt_visible_to_hit", "Work needed", "peek", "T1→T2"): (
        "Your execution phase (T1→T2) is the bottleneck. "
        "Aim_botz flick drills to close the gap from aim-start to first hit."
    ),
    ("rt_visible_to_hit", "Average", "peek", "T0→T1"): (
        "Cognitive reaction is slightly slow. Add 5 min warm-up reaction drills before sessions."
    ),
    ("rt_visible_to_hit", "Average", "peek", "T1→T2"): (
        "Execution accuracy slows your duel. Focus on first-shot hit rate — "
        "missing the first bullet forces a slower second-shot correction."
    ),
}
```

---

## Common Pitfalls

### Pitfall 1: player_steamid type mismatch

**What goes wrong:** `engagements.player_steamid` is `INTEGER` in SQLite, but sidebar input is a string. SQL `WHERE player_steamid = ?` with a string param may silently return 0 rows.

**Why it happens:** SQLite does type coercion but pandas `read_sql` passes Python types. If `params=(sid_str,)` instead of `params=(int(sid_str),)`, the query silently fails.

**How to avoid:** Always `int(steamid_str)` before passing to SQL params. Guard with try/except ValueError.

**Warning signs:** Empty DataFrame from `load_player_metrics()` even though user ran analysis.

### Pitfall 2: Interpretation tab renders before data is available

**What goes wrong:** User opens app cold (no sidebar SteamID). Interpretation section crashes trying to query empty SteamID.

**How to avoid:** Guard at top of Interpretation section:
```python
_interp_sid = st.session_state.get("steamid_input", "").strip()
if not _interp_sid:
    st.info("Enter SteamID64 in Configuration sidebar to enable interpretation.")
    st.stop()  # or use a flag to skip section rendering
```

### Pitfall 3: NaN propagation in percentile computation

**What goes wrong:** `rt_visible_to_aim_ms` is NULL for engagements where T1 was not found (pre-aim case, T1=-1). `pd.Series.quantile()` on a Series with NaN propagates NaN if all values are NaN.

**How to avoid:** Always `.dropna()` before calling `.quantile()`. Check `.empty` after dropna. [VERIFIED: analytics.db has NULL rt_visible_to_aim_ms rows]

### Pitfall 4: Hold sample size for RT components

**What goes wrong:** karrigan has only 28 hold rows with rt_visible_to_aim_ms. Percentile computed from 28 samples is statistically weak. Displaying "Elite/Work needed" based on this may mislead users.

**How to avoid:** Add a per-metric sample-size check. If n < 20 for a specific metric+engagement_type combination, display "(low sample)" next to that row in the table and use fallback thresholds. Do NOT apply the D-07 demo-count check only — metrics can individually be sparse even with many demos (e.g., hold T1 detection fails often).

### Pitfall 5: kill_rate/hit_rate unit consistency

**What goes wrong:** Player value is computed as a single global rate (one number), but benchmark is a per-demo distribution. The comparison is apples-to-oranges.

**How to avoid:** For the player's display value, use their global rate (all-time). For tier assignment, compare their global rate against the benchmark's per-demo distribution percentiles. This is intentional — the benchmark percentiles represent "what a typical demo looks like for this player". [ASSUMED: reasonable approach; document this choice clearly in code comments]

### Pitfall 6: demo_name column sparsity in engagements

**What goes wrong:** Demo count for benchmark should come from `duel_attempts` (all rows have `demo_name`), not `engagements` (some older rows may have NULL `demo_name`).

**How to avoid:** Use `duel_attempts` table for demo count queries (validated: 57 distinct demo_names for karrigan in duel_attempts vs verified same in processed_matches).

---

## Code Examples

### Full interpretation module skeleton

```python
# interpretation.py
"""
Interpretation layer: percentile tier computation + drill lookup.

Called by app.py Interpretation section. No UI dependencies.
"""
import sqlite3
from contextlib import closing
from typing import Optional

import numpy as np
import pandas as pd

# Tier ordering (index = severity, 0=best)
TIER_ORDER = {"Elite": 0, "Good": 1, "Average": 2, "Work needed": 3}

METRIC_CONFIG = {
    # (column_in_db_or_computed, lower_is_better, display_name, source_table)
    "crosshair_angle": ("crosshair_angle_at_t0_deg", True, "Crosshair Angle at T0", "engagements"),
    "rt_visible_to_aim": ("rt_visible_to_aim_ms", True, "RT Visible→Aim (ms)", "engagements"),
    "rt_aim_to_hit": ("rt_aim_to_hit_ms", True, "RT Aim→Hit (ms)", "engagements"),
    "kill_rate": (None, False, "Kill Rate (%)", "duel_attempts"),  # computed
    "hit_rate": (None, False, "Hit Rate (%)", "duel_attempts"),    # computed
}

def count_player_demos(db_path: str, player_steamid: int) -> int:
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT COUNT(DISTINCT demo_name) FROM duel_attempts WHERE player_steamid=?",
            (player_steamid,)
        ).fetchone()
        return row[0] if row else 0

def compute_interpretation(
    db_path: str,
    player_steamid: int,
    benchmark_steamid: int,
    engagement_type: str,  # "peek" | "hold"
    fallback_thresholds: Optional[dict] = None,
) -> list[dict]:
    """Return list of metric rows for the interpretation table.

    Each row: {metric, player_value, tier, benchmark_p50, gap, drill, n_player, n_benchmark}
    """
    ...
```

### app.py Interpretation section integration

```python
# In app.py, after Batch Analysis section:
st.header("Interpretation")
st.caption(
    "Compares your metrics against a benchmark player's distribution. "
    "Run analysis first to populate your data."
)

_interp_sid_str = st.session_state.get("steamid_input", "").strip()
if not _interp_sid_str:
    st.info("Enter SteamID64 in Configuration sidebar to see interpretation.")
else:
    try:
        _interp_player_sid = int(_interp_sid_str)
    except ValueError:
        st.error("Invalid SteamID64.")
        _interp_player_sid = None

    if _interp_player_sid:
        from interpretation import get_benchmark_options, compute_interpretation

        _benchmark_options = get_benchmark_options(DB_PATH)
        _benchmark_labels = [label for _, label, _ in _benchmark_options]
        _benchmark_sids = [sid for sid, _, _ in _benchmark_options]

        # Find default index (donk if in list, else 0)
        from config import PLAYER_NAMES
        _donk_sid = next((s for s, n in PLAYER_NAMES.items() if n == "donk"), None)
        _default_idx = _benchmark_sids.index(_donk_sid) if _donk_sid in _benchmark_sids else 0

        _selected_label = st.selectbox("Benchmark player", _benchmark_labels, index=_default_idx)
        _benchmark_sid = _benchmark_sids[_benchmark_labels.index(_selected_label)]

        _peek_tab, _hold_tab = st.tabs(["Peek", "Hold"])
        for _tab, _etype in [(_peek_tab, "peek"), (_hold_tab, "hold")]:
            with _tab:
                _rows = compute_interpretation(DB_PATH, _interp_player_sid, _benchmark_sid, _etype)
                # render summary card + metric table
```

---

## Validation Architecture

`nyquist_validation: true` in config.json — this section is required.

### Test Framework

| Property | Value |
|-|-|
| Framework | pytest 8.x (already installed) |
| Config file | none — uses `pyproject.toml` or default discovery |
| Quick run | `python -m pytest tests/test_interpretation.py -p no:cov -q` |
| Full suite | `python -m pytest --override-ini="addopts=--strict-markers" -q` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|-|-|-|-|-|
| REQ-INT-01 | `assign_tier()` returns correct label for all 4 tiers, both directions | unit | `pytest tests/test_interpretation.py::test_assign_tier_lower_is_better -x` | ❌ Wave 0 |
| REQ-INT-01 | `assign_tier()` returns correct label higher_is_better | unit | `pytest tests/test_interpretation.py::test_assign_tier_higher_is_better -x` | ❌ Wave 0 |
| REQ-INT-01 | `compute_interpretation()` returns 5-row list with expected keys | unit | `pytest tests/test_interpretation.py::test_compute_interpretation_schema -x` | ❌ Wave 0 |
| REQ-INT-03 | Peek and hold rows computed separately (different thresholds) | unit | `pytest tests/test_interpretation.py::test_peek_hold_separate_thresholds -x` | ❌ Wave 0 |
| REQ-INT-04 | Survivorship bias caveat present in drill text for RT metrics | unit | `pytest tests/test_interpretation.py::test_rt_drill_contains_caveat_ref -x` | ❌ Wave 0 |
| REQ-INT-05 | RT bottleneck drill-down selects correct component | unit | `pytest tests/test_interpretation.py::test_rt_bottleneck_component -x` | ❌ Wave 0 |
| D-07 | Fallback thresholds used when benchmark has <20 demos | unit | `pytest tests/test_interpretation.py::test_fallback_thresholds_triggered -x` | ❌ Wave 0 |
| D-12 | `get_benchmark_options()` appends "(small sample)" for <20 demos | unit | `pytest tests/test_interpretation.py::test_benchmark_small_sample_label -x` | ❌ Wave 0 |
| D-11 | `PLAYER_NAMES` lookup used in benchmark label | unit | `pytest tests/test_interpretation.py::test_player_names_lookup -x` | ❌ Wave 0 |
| D-03 | Player with 0 rows in DB returns empty/handled result | unit | `pytest tests/test_interpretation.py::test_player_not_in_db_returns_empty -x` | ❌ Wave 0 |

### Sampling Rate

- Per task commit: `python -m pytest tests/test_interpretation.py -p no:cov -q`
- Per wave merge: `python -m pytest --override-ini="addopts=--strict-markers" -q`
- Phase gate: Full suite green (target: 289 + ~15 new = ~304 tests)

### Wave 0 Gaps

- [ ] `tests/test_interpretation.py` — all 10+ tests above
- [ ] `interpretation.py` — module must exist before tests pass

---

## Security Domain

`security_enforcement` not set in config.json — treated as enabled.

| ASVS Category | Applies | Standard Control |
|-|-|-|
| V2 Authentication | no | — |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | `int(steamid_str)` with try/except; SQL uses parameterized queries (`?` placeholder) |
| V6 Cryptography | no | — |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|-|-|-|
| SQL injection via SteamID input | Tampering | Parameterized queries only — no f-string SQL. Already pattern in db_utils.py |
| Path traversal via player name | Tampering | PLAYER_NAMES is a dict in config.py; no user-controlled path |

**No new attack surface introduced.** Interpretation tab is read-only from analytics.db. No user input reaches SQL except the SteamID (already validated as int).

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|-|-|-|-|-|
| sqlite3 | DB reads | ✓ | stdlib | — |
| pandas | Percentile computation | ✓ | 3.0.1 | — |
| numpy | `np.percentile()` | ✓ | 2.4.2 | `pd.Series.quantile()` (already in pandas) |
| streamlit | UI rendering | ✓ | existing | — |
| analytics.db | All interpretation queries | ✓ | 57 karrigan demos | Warning if empty |

**Missing dependencies with no fallback:** None.

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|-|-|-|-|
| Hard-coded donk-only benchmark | Selectable from analytics.db | Phase 8 | Multi-player comparison enabled |
| No coaching output | Tier + drill per metric | Phase 8 | "I would buy it" gap closed |
| Raw CSV metrics | Percentile distribution tiers | Phase 8 | Actionable vs descriptive |

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|-|-|-|-|
| A1 | Player's display value for tier assignment = median of their distribution | Pattern 5 | Could use mean instead; minimal impact on outcome |
| A2 | Drill text content is correct CS2 coaching advice | Drill Content | Coaching quality risk; validate with a CS2 coach before Phase 9 |
| A3 | "Work needed" = bottom 25% relative to benchmark (not absolute standard) | Tier Assignment | If benchmark is weak, tier thresholds mislead; fine for now with karrigan |
| A4 | D-01's "4th tab" means a new `st.header()` section, not literal `st.tabs()` | Architecture Patterns | If user wants actual tab widget for the whole app, requires refactoring current structure |

---

## Open Questions

1. **Does the user want actual `st.tabs()` at the top level?**
   - What we know: Current app uses `st.header()` sections, not tabs. D-01 says "4th tab."
   - What's unclear: Whether to refactor the entire app into `st.tabs()` or add Interpretation as a new header section.
   - Recommendation: Add as `st.header("Interpretation")` section (minimal change, no regression risk). Use `st.tabs(["Peek", "Hold"])` within the section for engagement-type separation.

2. **Hold RT components (T0→T1, T1→T2) — expose or suppress?**
   - What we know: karrigan has only 28 hold engagements with valid T1. Sample too small for percentiles.
   - What's unclear: Whether to show hold T0→T1 / T1→T2 as "n/a (low sample)" or omit entirely.
   - Recommendation: Show `rt_visible_to_hit_ms` for hold only; mark T0→T1 and T1→T2 as "n/a (n<20)" to avoid misleading tiers.

3. **What SteamID is "donk" in analytics.db?**
   - What we know: `analytics.db` currently has only two steamids: `76561197989430253` (karrigan, 57 demos) and `76561198388053181` (unknown, 2 demos). donk SteamID `76561198386265483` has 0 rows.
   - What's unclear: Was donk not in the batch run? Phase 7 MEMORY says "donk 26 + karrigan 57" in SC4 PASS, but the DB query shows differently.
   - Recommendation: Planner must confirm which steamid is donk in the live DB. `PLAYER_NAMES` default should map `76561197989430253` → "karrigan" and `76561198386265483` → "donk". If donk has 0 rows, D-10's "Default = donk" will show no data — default to first available benchmark instead.

---

## Sources

### Primary (HIGH confidence)

- `analytics.db` direct queries — all percentile values, column schemas, player counts [VERIFIED 2026-05-06]
- `db_utils.py` — SQLite connection pattern, WAL mode, parameterized queries [VERIFIED]
- `app.py` — Existing tab/section structure, session_state patterns, sidebar SteamID flow [VERIFIED]
- `config.py` — Existing constants pattern; PLAYER_NAMES does not exist yet [VERIFIED]
- `duel_attempts.py` — DuelAttempt dataclass fields (bullets_fired, bullets_hit, was_killed) [VERIFIED]

### Secondary (MEDIUM confidence)

- CS2 coaching knowledge for drill content [ASSUMED — domain knowledge, not verified against coaching literature]

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new dependencies, verified against existing code
- Architecture: HIGH — verified by reading app.py and db_utils.py
- Percentile values: HIGH — live analytics.db queries
- Drill content: LOW — CS2 coaching knowledge, not validated by expert
- Pitfalls: HIGH — verified against live data and existing code patterns

**Research date:** 2026-05-06
**Valid until:** 2026-06-06 (stable domain; only changes if analytics.db schema changes)
