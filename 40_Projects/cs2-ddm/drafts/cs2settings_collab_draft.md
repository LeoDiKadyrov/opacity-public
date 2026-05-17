# cs2settings.com collab — pre-aim angle analysis draft

**Status:** DATA COLLECTION PENDING — do not post yet. See checklist below.

---

## Reach-out to chazeftw (Reddit comment or DM)

Reply to his r/GlobalOffensive "Parsed every demo from HLTV in April — crosshair edition" post, or DM:

---

Great project. I've been running a parallel analysis from a different angle — per-duel crosshair placement at the moment an enemy becomes visible (what I call T0). Basically how far off-target a pro's crosshair is at the instant the enemy appears.

For 12 pros across ~2500 duels I'm getting per-player medians ranging 6.8° to 10.4°. The Spirit players cluster noticeably lower than FaZe, which is independently interesting.

But the question I can't answer alone: does crosshair geometry (your size/gap data) correlate with pre-aim angle? Hypothesis is weak — pre-aim is mostly game sense, not crosshair — but it would be cool to actually test it rather than assume.

You have crosshair settings for these players at the match level. I have per-duel angles. Want to do a joint post with the merge? No agenda on my end, just curious if the data says anything.

---

## Reddit post skeleton (fill after data merge)

**Title options:**
- A: I measured how off-target 12 pros' crosshairs are at the moment of first contact. Does crosshair size matter?
- B: Pre-aim angle vs crosshair gap for 12 top pros — collab with cs2settings.com

---

I've been parsing pro demos to measure crosshair placement at T0 — the tick when an enemy first enters visibility. "Crosshair angle at T0" = degrees between where the pro's crosshair is and where the enemy is. Lower = better pre-aim.

12 pros, [N_TOTAL] duels, [TOURNAMENT] demos. Crosshair settings from cs2settings.com (u/chazeftw), pre-aim angles from my pipeline.

**Results: pre-aim angle by player** (median, peek scenarios, angle <90° only):

| Player | Team | Median angle (°) | N duels | Crosshair gap |
|-|-|-|-|-|
| frozen | FaZe | 6.8 | 207 | [GAP] |
| zweih | Spirit | 6.9 | 209 | [GAP] |
| magixx | Spirit | 7.1 | 173 | [GAP] |
| sh1ro | Spirit | 7.4 | 176 | [GAP] |
| jcobbb | FaZe | 7.5 | 170 | [GAP] |
| zont1x | Spirit | 7.5 | 231 | [GAP] |
| donk | Spirit | 7.6 | 377 | [GAP] |
| chopper | Spirit | 8.0 | 137 | [GAP] |
| tN1R | Spirit | 9.4 | 243 | [GAP] |
| karrigan | FaZe | 9.5 | 258 | [GAP] |
| twistzz | FaZe | 9.6 | 243 | [GAP] |
| broky | FaZe | 10.4 | 115 | [GAP] |

[CHART: scatter crosshair_gap vs median_angle — or bar chart sorted by angle with gap as color]

**Does crosshair gap correlate with pre-aim angle?** [FINDING — fill with actual result]

**Caveats:**
- Pre-aim angle is primarily game sense and positioning, not crosshair geometry. We're testing a weak prior.
- Demos are Spirit + FaZe corpus ([TOURNAMENT LIST]). Both teams in the data — team-level differences may swamp any crosshair effect.
- Spirit cluster (zweih/magixx/sh1ro/zont1x) is systematically lower than FaZe cluster. Confound: Spirit ≠ FaZe in playstyle, roles, and opponents faced.
- N varies per player. karrigan N=258 is reliable; broky N=115 is marginal.
- 64-tick demos, ~15.6ms granularity on T0 detection.

**Method:** BVH + AABB ray casting for T0. Viewangle delta for T1. `player_hurt` for T2. Crosshair settings from cs2settings.com match-level data merged by player + tournament window.

Built this for [Djok](LINK). DM if you want your own pre-aim breakdown.

---

## Data collection checklist

### Have (in analytics.db):
- [x] `crosshair_angle_at_t0_deg` per engagement, all 12 players
- [x] Per-player N and median (filtered >90°, N>=100)
- [x] Player → SteamID → name mapping

### Need before posting:

**From chazeftw / cs2settings.com:**
- [ ] Crosshair size, gap, thickness, dot (bool) for each of the 12 players
  - Scope: match-level data for same tournaments as our corpus
  - Our corpus: Spirit demos + FaZe demos (specific tournaments — confirm which ones from demo filenames)

**Our own pipeline:**
- [ ] Confirm which tournaments are in the corpus (query demo_name for distinct tournament names)
- [ ] Verify median vs mean choice — run actual median query (current numbers are avg, not median)
- [ ] Chart: scatter plot crosshair_gap vs median_angle_at_T0 (or bar chart sorted)
- [ ] Correlation coefficient: Pearson/Spearman crosshair_gap vs angle across 12 players

**Decision gates before posting:**
- [ ] Does chazeftw agree to collab? → if no, still post as standalone (table is interesting without crosshair data, just rename column)
- [ ] Is Spirit vs FaZe team difference significant enough to be the main story? (gap 6.8–8.0° Spirit vs 7.5–10.4° FaZe)
- [ ] Is crosshair correlation signal or noise? → if noise (r<0.3), lead with team story, relegate crosshair to null-result caveat

### SQL to run:
```sql
-- Actual median (approximate via percentile_cont workaround)
SELECT player_steamid,
       COUNT(*) as n,
       AVG(crosshair_angle_at_t0_deg) as mean_angle,
       -- median approximation: order-based
       (SELECT crosshair_angle_at_t0_deg 
        FROM engagements e2 
        WHERE e2.player_steamid = e1.player_steamid 
          AND crosshair_angle_at_t0_deg IS NOT NULL
          AND crosshair_angle_at_t0_deg < 90
        ORDER BY crosshair_angle_at_t0_deg
        LIMIT 1 OFFSET (COUNT(*)/2)) as approx_median
FROM engagements e1
WHERE crosshair_angle_at_t0_deg IS NOT NULL
  AND crosshair_angle_at_t0_deg < 90
GROUP BY player_steamid
HAVING n >= 100;

-- Tournament list in corpus
SELECT DISTINCT demo_name FROM engagements ORDER BY demo_name;
```
