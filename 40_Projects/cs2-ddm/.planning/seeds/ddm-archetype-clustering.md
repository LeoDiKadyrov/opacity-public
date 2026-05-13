---
title: DDM Player Archetype Clustering
trigger_condition: analytics.db has ≥30 distinct players with ≥50 engagements each per engagement_type
planted_date: 2026-05-08
related_spike: .planning/spikes/ez-pc-validation/SPEC.md
related_phase: TBD (post-Phase-10 if longitudinal lens ships GREEN)
status: dormant
---

# DDM Player Archetype Clustering (Угол B)

## Idea

Use EZ-Diffusion DDM-параметры (v, a, t_er) computed per player to surface **archetypes** invisible in flat RT/hit_rate metrics. Coaches and players intuitively name patterns ("careful sniper", "fast rusher") — DDM gives a quantitative axis for these.

## Hypothesis

Players cluster into ≥2 distinct (v, a) regions in the parameter space:
- **Careful sniper:** low v + high a — slow evidence accumulation but waits for high certainty before committing
- **Fast rusher:** high v + low a — quick decision under low evidence threshold
- **Mixed:** medium v + medium a — no specific style
- Possibly more clusters surface empirically (don't presume k=3)

Cluster membership predicts engagement_type performance differently than RT/hit_rate alone:
- Snipers excel at hold engagements but underperform in peek scrambles
- Rushers reverse pattern
- Coach insight: "you're playing peeks like a sniper — your a is too high for the engagement"

## Trigger condition

**DB ≥30 distinct players** with ≥50 engagements per engagement_type (peek + hold separately).

Current state 2026-05-08: 1042 engagements across donk + karrigan + ~83 spirit demos worth of opponents. Likely <10 players meet the threshold today. Trigger fires when:

```sql
SELECT COUNT(*) FROM (
  SELECT player_steamid, engagement_type, COUNT(*) as n
  FROM engagements
  GROUP BY player_steamid, engagement_type
  HAVING n >= 50
) t WHERE t.engagement_type = 'peek'
-- ≥30 rows = trigger
```

## Prerequisites before this seed activates

1. **Spike `ez-pc-validation` re-run returns GREEN** — initial run 2026-05-08 returned YELLOW/RED at N=2 players. Re-run must validate stability + discriminant + convergent on a larger DB
2. **Phase 10b (UI + coaching) shipped** — DDM machinery in pipeline AND user-facing surface unlocked. Phase 10a (infra-only) ships first; 10b gated on the re-run
3. **DB scale reached** — 30+ players threshold hit (same trigger as Phase 10b unlock). Likely requires sustained ingestion period after Phase 10a ships.

If spike re-run returns RED at scale → this seed is also dead, archive both.

## Update 2026-05-08

Initial spike returned YELLOW/RED on stability (universal CI95 width fail). Routing decision was Phase 10a infra-only (compute + persist DDM, no UI). This seed remains dormant. The trigger condition above now serves a dual purpose: it gates BOTH Phase 10b unlock AND this seed's activation.

## Implementation sketch (when activated)

1. Per-player EZ-Diffusion fit (already built in Phase 10)
2. K-means or HDBSCAN on (v, a, t_er) space — try k=2-5, evaluate silhouette
3. Validate clusters against external behavioral data:
   - role from match metadata (AWP / rifler / IGL)
   - map preference distribution
   - smoke usage rate (from utility events)
4. UI: scatter plot in cs2-ddm dashboard with player position highlighted, cluster centroids shown
5. Coaching insight per cluster — text generation in `interpretation.py` extension

## Open questions (for later, not for trigger)

- Are clusters stable across maps or per-map specific?
- Do clusters predict tier ranking (Elite/Good/Average) better than raw v?
- Is cluster *transition* across sessions a useful signal (player drift)?

## Why dormant now

- Insufficient DB scale → clustering on <10 points is noise
- Phase 10 (longitudinal lens) hasn't shipped — DDM machinery doesn't exist in pipeline yet
- Spike not run — Pc validity unknown

## When triggered

Run `/gsd-explore "DDM archetype clustering — DB now has N players, clustering feasible"` to formalize Phase 11+ plan.
