# Reddit r/GlobalOffensive draft — Spirit vs FaZe pre-aim angle

**Status:** DRAFT — not posted. Fill [PLACEHOLDERS] before posting.
**Target:** r/GlobalOffensive, Tips & Guides flair
**CTA:** Djok link in first OP comment (not in body — Rule 8)

---

## Title

**SELECTED: C**

> Spirit out-pre-aims FaZe. I measured crosshair placement at first contact for 13 pros across 2400 duels.

---

## Post body

For every duel in a demo there's a moment when the enemy first becomes visible — I call it T0. At that exact tick I measure how many degrees separate the crosshair from the enemy center. Lower = your crosshair was already closer to the right spot. It's a direct measurement of pre-aim positioning, not reaction speed.

13 pros, 2400+ duels, 144 demos (Spirit + FaZe + Astralis HLTV matches). Metric: median crosshair angle at T0, peek scenarios, angles under 90° only (180°+ = crosshair not near enemy at all, pulls the average but not the median).

**Results:**

| Player | Team | Median angle at T0 (°) | N duels |
|-|-|-|-|
| chopper | Spirit | 3.9 | 137 |
| magixx | Spirit | 3.9 | 173 |
| sh1ro | Spirit | 4.2 | 176 |
| donk | Spirit | 4.3 | 377 |
| frozen | FaZe | 4.3 | 207 |
| jcobbb | FaZe | 4.4 | 170 |
| zont1x | Spirit | 4.4 | 231 |
| zweih | Spirit | 4.4 | 209 |
| tN1R | Spirit | 4.8 | 243 |
| twistzz | FaZe | 4.8 | 243 |
| broky | FaZe | 5.1 | 115 |
| karrigan | FaZe | 5.3 | 258 |
| Staehr | Astralis | 6.3 | 58 |

The IGL split: chopper (Spirit's IGL) = 3.9° — bottom of the table. karrigan (FaZe's IGL) = 5.3° — top of the FaZe table. Same role, ~1.4° apart.

Spirit cluster: 3.9°–4.8°. FaZe cluster: 4.3°–5.3°. Two FaZe players (frozen, jcobbb) overlap with Spirit's range. karrigan and broky sit clearly higher.

**Caveats — worth reading:**

- 1.4° difference between IGLs sounds small. At typical engagement distance in CS2 (~10m), 1° ≈ 17cm. So karrigan's crosshair is ~24cm further from the enemy center at first contact than chopper's, median. Whether that's meaningful to reaction time is a separate question.
- Spirit demos are Spirit-vs-opponent, FaZe demos are FaZe-vs-opponent. These are different opponents at different events. Spirit's opponents may hold different positions than FaZe's opponents, which changes pre-aim difficulty entirely. This is not a controlled experiment.
- karrigan plays a more aggressive, entry-fragger role than chopper despite both being IGLs. Aggressive peekers structurally have higher angles — they're manufacturing duels, not waiting in pre-aimed positions.
- Staehr N=58 is small. Don't read too much into the 6.3° outlier.
- 64-tick demos, ~15.6ms T0 detection granularity.

**Method:** BVH + AABB ray casting to enemy hitbox corners for T0. Viewangle delta threshold for T1. `player_hurt` for T2. T0 suppressed during flash intervals and smoke geometry.

Built this for [Djok](LINK-IN-COMMENT). DM if you want your own pre-aim breakdown.

[image: analysis_plots/preaim_team_comparison.png]

---

## First OP comment (post immediately after posting)

> Full breakdown + Djok link: [DJOK_URL]
>
> Happy to run this for more teams if there's interest — G2, NaVi, Vitality. Just need HLTV demos.

---

## Pre-posting checklist

- [ ] Confirm N totals match latest analytics.db (numbers above from 2026-05-16 query)
- [ ] Decide title A or B
- [ ] Add image: bar chart sorted by median angle, color-coded by team (Spirit blue, FaZe orange, Astralis red)
- [ ] Fill Djok URL
- [ ] Post body → no links. CTA link only in first comment.
- UTM already set: `djok.din02winchester25.workers.dev?utm_source=reddit&utm_medium=post&utm_campaign=preaim_team`

## Chart spec for image

Bar chart, horizontal, sorted ascending by median angle.
X-axis: "Median crosshair angle at T0 (°)", range 0–7
Y-axis: player names
Colors: Spirit = #1565C0 (blue), FaZe = #E65100 (orange), Astralis = #B71C1C (red)
Title: "How close were pros' crosshairs to the enemy at first contact?"
Subtitle: "Median angle at T0 — 13 pros, 2400+ duels, 144 HLTV demos"
Footer: "djok.din02winchester25.workers.dev · data: Spirit + FaZe + Astralis HLTV matches"
