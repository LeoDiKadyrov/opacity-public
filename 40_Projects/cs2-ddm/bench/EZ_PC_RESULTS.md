# EZ-Diffusion Pc Validation — Results

**Spike spec:** `.planning/spikes/ez-pc-validation/SPEC.md`
**Generated:** 2026-05-08 (run via `python bench/ez_pc_validation.py`)

## Data summary

| Player | engagement_type | N (rt<=1500ms) |
|-|-|-|
| donk | peek | 521 |
| karrigan | peek | 266 |

**Constraint vs SPEC:** SPEC asked for >=3 players. analytics.db has only 2 players with >=50 engagements (rt<=1500ms gate applied), peek only. hold engagement_type has zero rows in `engagements` with valid RT. Discriminant test degraded to pairwise; convergent (population corr v vs hit_rate) reported as DEGRADED.

## Synthetic recovery (sanity check on EZ math)

N trials per run: 100, runs per condition: 30

| true v | true a | true t_er | recovered v | recovered a | recovered t_er | v bias % | a bias % | t_er bias % | n runs |
|-|-|-|-|-|-|-|-|-|-|
| 0.18 | 0.12 | 0.30 | 0.185 | 0.124 | 0.301 | +2.9 | +3.2 | +0.4 | 30 |
| 0.30 | 0.15 | 0.25 | 0.305 | 0.155 | 0.250 | +1.6 | +3.3 | -0.2 | 30 |
| 0.10 | 0.10 | 0.40 | 0.104 | 0.103 | 0.402 | +4.0 | +3.3 | +0.4 | 30 |

**Recovery verdict:** PASS (SPEC requires |bias| <= 15% on all 3 params at N=100)

## Per-Pc results

### pc1_first_shot_hit

| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |
|-|-|-|-|-|-|
| donk | 0.689 | 405 | 0.0772 [0.0568, 0.0994] (w/p=0.55) | 0.1029 [0.0938, 0.1113] (w/p=0.17) | 0.1679 [0.1413, 0.1945] (w/p=0.32) |
| karrigan | 0.730 | 185 | 0.0888 [0.0627, 0.1182] (w/p=0.62) | 0.1119 [0.0986, 0.1227] (w/p=0.22) | 0.1613 [0.1243, 0.2077] (w/p=0.52) |

**Verdict: RED**

- STABILITY FAIL (max CI95 width / point = 0.62, need <=0.30)
- DISCRIMINANT FAIL — donk vs karrigan (v: d=0.33, a: d=0.60, t_er: d=0.13)
- CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), population corr undefined. Treat as N/A.

### pc2_won_duel

| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |
|-|-|-|-|-|-|
| donk | 0.649 | 405 | 0.0554 [0.0379, 0.0747] (w/p=0.66) | 0.1112 [0.1031, 0.1181] (w/p=0.14) | 0.1761 [0.1537, 0.2024] (w/p=0.28) |
| karrigan | 0.573 | 185 | 0.0246 [0.0010, 0.0490] (w/p=1.95) | 0.1194 [0.1080, 0.1283] (w/p=0.17) | 0.1674 [0.1311, 0.2108] (w/p=0.48) |

**Verdict: YELLOW**

- STABILITY FAIL (max CI95 width / point = 1.95, need <=0.30)
- DISCRIMINANT PASS (v: d=1.02, a: d=0.65, t_er: d=0.18)
- CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), population corr undefined. Treat as N/A.

### pc3a_crosshair_lt_3deg

| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |
|-|-|-|-|-|-|
| donk | 0.313 | 521 | -0.0669 [-0.0844, -0.0522] (w/p=0.48) | 0.1176 [0.1071, 0.1261] (w/p=0.16) | 0.1551 [0.1224, 0.1928] (w/p=0.45) |
| karrigan | 0.256 | 266 | -0.0825 [-0.1089, -0.0623] (w/p=0.56) | 0.1295 [0.1108, 0.1437] (w/p=0.25) | 0.1418 [0.0808, 0.2153] (w/p=0.95) |

**Verdict: RED**

- STABILITY FAIL (max CI95 width / point = 0.95, need <=0.30)
- DISCRIMINANT FAIL — donk vs karrigan (v: d=0.55, a: d=0.63, t_er: d=0.17)
- CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), population corr undefined. Treat as N/A.

### pc3b_crosshair_lt_5deg

| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |
|-|-|-|-|-|-|
| donk | 0.549 | 521 | 0.0174 [0.0016, 0.0330] (w/p=1.80) | 0.1127 [0.1047, 0.1194] (w/p=0.13) | 0.1689 [0.1458, 0.1962] (w/p=0.30) |
| karrigan | 0.477 | 266 | -0.0073 [-0.0268, 0.0120] (w/p=5.33) | 0.1241 [0.1113, 0.1334] (w/p=0.18) | 0.1447 [0.1012, 0.1904] (w/p=0.62) |

**Verdict: RED**

- STABILITY FAIL (max CI95 width / point = 5.33, need <=0.30)
- DISCRIMINANT FAIL — donk vs karrigan (v: d=0.99, a: d=0.86, t_er: d=0.47)
- CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), population corr undefined. Treat as N/A.

### pc3c_crosshair_lt_8deg

| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |
|-|-|-|-|-|-|
| donk | 0.743 | 521 | 0.0864 [0.0708, 0.1010] (w/p=0.35) | 0.1228 [0.1155, 0.1291] (w/p=0.11) | 0.1613 [0.1393, 0.1854] (w/p=0.29) |
| karrigan | 0.677 | 266 | 0.0571 [0.0367, 0.0780] (w/p=0.72) | 0.1293 [0.1201, 0.1371] (w/p=0.13) | 0.1551 [0.1200, 0.1914] (w/p=0.46) |

**Verdict: YELLOW**

- STABILITY FAIL (max CI95 width / point = 0.72, need <=0.30)
- DISCRIMINANT PASS (v: d=1.14, a: d=0.60, t_er: d=0.14)
- CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), population corr undefined. Treat as N/A.

## Summary verdict matrix

| Pc | Verdict |
|-|-|
| pc1_first_shot_hit | **RED** |
| pc2_won_duel | **YELLOW** |
| pc3a_crosshair_lt_3deg | **RED** |
| pc3b_crosshair_lt_5deg | **RED** |
| pc3c_crosshair_lt_8deg | **YELLOW** |

## Recommendation

**No Pc fully passed; YELLOW: pc2_won_duel, pc3c_crosshair_lt_8deg.**

Route options: (1) hybrid Pc spike-2 combining best two YELLOW signals, (2) narrow Phase 10 scope to peek-only with explicit experimental disclaimer, (3) defer until DB scale increases (stability check may pass with more players).

## Caveats / known gaps

- **Convergent check degraded** (only 2 players). Cannot compute population corr v vs hit_rate. Verdict relies on stability + discriminant only — 2/3 checks instead of 3/3.
- **Hold engagement_type unsupported** at current data scale. Findings apply to peek only.
- **pc1/pc2 lose ~20% of engagements** to the `engagements` <-> `duel_attempts` tick-proximity join (405/502 matched for donk peek). Pc=NaN trials silently dropped.
- **EZ scale param S=0.1** is the Wagenmakers 2007 convention. Different choice would rescale `v` and `a` proportionally; ratios and verdicts unchanged.
