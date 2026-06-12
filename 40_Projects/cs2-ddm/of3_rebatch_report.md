
## Stage N=1 (2026-06-11 10:04:50)

| # | demo | n_episodes | t0_source | t1_source | secs |
|-|-|-|-|-|-|
| 1 | 9z-vs-spirit-m1-overpass | 42 | [('BVH+AABB', 42)] | [('lands', 37), ('never_landed', 5)] | 153 |

**Stage N=1 finished:** 2026-06-11 10:07:25 (elapsed 2.6min, processed=1, no-donk-skipped=0)

### Distribution-shape summary after stage N=1

- n_resolved (lands): **37**
- min rt_visible_to_land_ms: **0.000ms**
- p10 rt_visible_to_land_ms: **0.000ms**
- %@tick-quantum pinning: **8.1%**
- never_landed%: **11.9%** (of 42 t1_source rows; {'lands': 37, 'never_landed': 5})
- never_visible%: **0.0%** (of 42 t0_source rows; {'BVH+AABB': 42})
- b5-class impossible rows (t1=t0+1 AND angle>6deg): **0**

## Stage N=1 (2026-06-11 10:12:28)

| # | demo | n_episodes | t0_source | t1_source | secs |
|-|-|-|-|-|-|
| 1 | 9z-vs-spirit-m1-overpass | 42 | [('BVH+AABB', 42)] | [('lands', 37), ('never_landed', 5)] | 145 |

**Stage N=1 finished:** 2026-06-11 10:14:53 (elapsed 2.4min, processed=1, no-donk-skipped=0)

### Distribution-shape summary after stage N=1

- n_resolved (lands): **37**
- min rt_visible_to_land_ms: **0.000ms**
- p10 rt_visible_to_land_ms: **0.000ms**
- %@tick-quantum pinning: **8.1%**
- never_landed%: **11.9%** (of 42 t1_source rows; {'lands': 37, 'never_landed': 5})
- never_visible%: **0.0%** (of 42 t0_source rows; {'BVH+AABB': 42})
- b5-class impossible rows (t1=t0+1 AND angle>6deg): **0**

## Stage N=5 (2026-06-11 10:15:18)

| # | demo | n_episodes | t0_source | t1_source | secs |
|-|-|-|-|-|-|
| 1 | 9z-vs-spirit-m1-overpass | 42 (skip) | - | - | - |
| 2 | 9z-vs-spirit-m2-dust2 | 43 | [('BVH+AABB', 41), ('never_visible', 2)] | [('lands', 35), ('never_landed', 6), ('no_t0', 2)] | 193 |
| 3 | astralis-vs-spirit-m1-dust2-p1 | 11 | [('BVH+AABB', 11)] | [('lands', 9), ('never_landed', 2)] | 41 |
| 4 | astralis-vs-spirit-m1-dust2-p2 | 24 | [('BVH+AABB', 24)] | [('lands', 14), ('never_landed', 10)] | 107 |
| 5 | astralis-vs-spirit-m2-ancient | 37 | [('BVH+AABB', 37)] | [('lands', 28), ('never_landed', 9)] | 241 |

**Stage N=5 finished:** 2026-06-11 10:25:03 (elapsed 9.8min, processed=5, no-donk-skipped=0)

### Distribution-shape summary after stage N=5

- n_resolved (lands): **123**
- min rt_visible_to_land_ms: **0.000ms**
- p10 rt_visible_to_land_ms: **0.000ms**
- %@tick-quantum pinning: **12.2%**
- never_landed%: **20.4%** (of 157 t1_source rows; {'lands': 123, 'never_landed': 32, 'no_t0': 2})
- never_visible%: **1.3%** (of 157 t0_source rows; {'BVH+AABB': 155, 'never_visible': 2})
- b5-class impossible rows (t1=t0+1 AND angle>6deg): **0**

**DOUBT TRIGGER:** tick-quantum pinning = 12.2% (>10% threshold)


## Stage N=5 (2026-06-11 10:25:44)

| # | demo | n_episodes | t0_source | t1_source | secs |
|-|-|-|-|-|-|
| 1 | 9z-vs-spirit-m1-overpass | 42 (skip) | - | - | - |
| 2 | 9z-vs-spirit-m2-dust2 | 43 (skip) | - | - | - |
| 3 | astralis-vs-spirit-m1-dust2-p1 | 11 (skip) | - | - | - |
| 4 | astralis-vs-spirit-m1-dust2-p2 | 24 (skip) | - | - | - |
| 5 | astralis-vs-spirit-m2-ancient | 37 (skip) | - | - | - |

**Stage N=5 finished:** 2026-06-11 10:25:44 (elapsed 0.0min, processed=5, no-donk-skipped=0)

### Distribution-shape summary after stage N=5

- n_resolved (lands): **123**
- min rt_visible_to_land_ms: **0.000ms**
- p10 rt_visible_to_land_ms: **0.000ms**
- %@tick-quantum pinning: **12.2%**
- never_landed%: **20.4%** (of 157 t1_source rows; {'lands': 123, 'never_landed': 32, 'no_t0': 2})
- never_visible%: **1.3%** (of 157 t0_source rows; {'BVH+AABB': 155, 'never_visible': 2})
- b5-class impossible rows (t1=t0+1 AND angle>6deg): **0**

**DOUBT TRIGGER:** tick-quantum pinning = 12.2% (>10% threshold)


## Stage N=81 (2026-06-11 11:37:00)

| # | demo | n_episodes | t0_source | t1_source | secs |
|-|-|-|-|-|-|
| 1 | 9z-vs-spirit-m1-overpass | 42 (skip) | - | - | - |
| 2 | 9z-vs-spirit-m2-dust2 | 43 (skip) | - | - | - |
| 3 | astralis-vs-spirit-m1-dust2-p1 | 11 (skip) | - | - | - |
| 4 | astralis-vs-spirit-m1-dust2-p2 | 24 (skip) | - | - | - |
| 5 | astralis-vs-spirit-m2-ancient | 37 (skip) | - | - | - |
| 6 | aurora-vs-spirit-m1-dust2-p1 | 22 | [('BVH+AABB', 21), ('long_visible', 1)] | [('lands', 14), ('never_landed', 8)] | 71 |
| 7 | aurora-vs-spirit-m1-dust2-p2 | 33 | [('BVH+AABB', 31), ('never_visible', 2)] | [('lands', 25), ('never_landed', 6), ('no_t0', 2)] | 84 |
| 8 | aurora-vs-spirit-m2-nuke | 62 | [('BVH+AABB', 62)] | [('lands', 50), ('never_landed', 12)] | 184 |
| 9 | falcons-vs-spirit-m1-dust2--iemRio | 35 | [('BVH+AABB', 33), ('never_visible', 2)] | [('lands', 25), ('never_landed', 8), ('no_t0', 2)] | 141 |
| 10 | falcons-vs-spirit-m1-dust2 | 36 | [('BVH+AABB', 36)] | [('lands', 27), ('never_landed', 9)] | 147 |
| 11 | falcons-vs-spirit-m2-ancient | 45 | [('BVH+AABB', 43), ('never_visible', 2)] | [('lands', 34), ('never_landed', 9), ('no_t0', 2)] | 206 |
| 12 | falcons-vs-spirit-m2-mirage | 32 | [('BVH+AABB', 32)] | [('lands', 28), ('never_landed', 4)] | 78 |
| 13 | g2-vs-spirit-m1-anubis | 51 | [('BVH+AABB', 51)] | [('lands', 34), ('never_landed', 17)] | 308 |
| 14 | g2-vs-spirit-m1-mirage | 40 | [('BVH+AABB', 39), ('never_visible', 1)] | [('lands', 35), ('never_landed', 4), ('no_t0', 1)] | 123 |
| 15 | g2-vs-spirit-m2-dust2 | 38 | [('BVH+AABB', 38)] | [('lands', 30), ('never_landed', 8)] | 157 |
| 16 | g2-vs-spirit-m2-overpass | 43 | [('BVH+AABB', 43)] | [('lands', 26), ('never_landed', 17)] | 225 |
| 17 | g2-vs-spirit-m3-dust2 | 57 | [('BVH+AABB', 57)] | [('lands', 42), ('never_landed', 15)] | 254 |
| 18 | heroic-vs-spirit-m1-overpass | 42 | [('BVH+AABB', 40), ('long_visible', 1), ('never_visible', 1)] | [('lands', 35), ('never_landed', 6), ('no_t0', 1)] | 169 |
| 19 | heroic-vs-spirit-m2-dust2-p1 | 50 | [('BVH+AABB', 47), ('never_visible', 3)] | [('lands', 37), ('never_landed', 10), ('no_t0', 3)] | 185 |
| 20 | heroic-vs-spirit-m2-dust2-p2 | 14 | [('BVH+AABB', 13), ('long_visible', 1)] | [('lands', 10), ('never_landed', 4)] | 57 |
| 21 | heroic-vs-spirit-m3-ancient | 38 | [('BVH+AABB', 37), ('long_visible', 1)] | [('lands', 31), ('never_landed', 7)] | 201 |
| 22 | mouz-vs-spirit-m1-ancient | 63 | [('BVH+AABB', 63)] | [('lands', 51), ('never_landed', 12)] | 260 |
| 23 | mouz-vs-spirit-m2-mirage | 91 | [('BVH+AABB', 91)] | [('lands', 70), ('never_landed', 21)] | 267 |
| 24 | mouz-vs-spirit-m3-overpass | 39 | [('BVH+AABB', 39)] | [('lands', 32), ('never_landed', 7)] | 140 |
| 25 | natus-vincere-vs-spirit-m1-mirage | 64 | [('BVH+AABB', 63), ('long_visible', 1)] | [('lands', 49), ('never_landed', 15)] | 161 |
| 26 | natus-vincere-vs-spirit-m2-dust2 | 28 | [('BVH+AABB', 28)] | [('lands', 24), ('never_landed', 4)] | 94 |
| 27 | pain-vs-spirit-m1-ancient-p1 | 9 | [('BVH+AABB', 9)] | [('lands', 6), ('never_landed', 3)] | 61 |
| 28 | pain-vs-spirit-m1-ancient-p2 | 39 | [('BVH+AABB', 38), ('never_visible', 1)] | [('lands', 28), ('never_landed', 10), ('no_t0', 1)] | 210 |
| 29 | pain-vs-spirit-m2-nuke | 43 | [('BVH+AABB', 43)] | [('lands', 32), ('never_landed', 11)] | 167 |
| 30 | parivision-vs-spirit-m1-anubis | 42 | [('BVH+AABB', 42)] | [('lands', 32), ('never_landed', 10)] | 160 |
| 31 | parivision-vs-spirit-m1-overpass | 41 | [('BVH+AABB', 41)] | [('lands', 30), ('never_landed', 11)] | 147 |
| 32 | parivision-vs-spirit-m2-ancient | 44 | [('BVH+AABB', 42), ('never_visible', 2)] | [('lands', 33), ('never_landed', 9), ('no_t0', 2)] | 202 |
| 33 | parivision-vs-spirit-m2-mirage | 45 | [('BVH+AABB', 44), ('long_visible', 1)] | [('lands', 38), ('never_landed', 7)] | 122 |
| 34 | parivision-vs-spirit-m3-ancient | 39 | [('BVH+AABB', 39)] | [('lands', 22), ('never_landed', 17)] | 268 |
| 35 | red-canids-vs-spirit-m1-mirage | 52 | [('BVH+AABB', 51), ('long_visible', 1)] | [('lands', 37), ('never_landed', 15)] | 150 |
| 36 | red-canids-vs-spirit-m2-ancient | 47 | [('BVH+AABB', 43), ('never_visible', 4)] | [('lands', 31), ('never_landed', 12), ('no_t0', 4)] | 157 |
| 37 | red-canids-vs-spirit-m3-overpass | 26 | [('BVH+AABB', 25), ('never_visible', 1)] | [('lands', 18), ('never_landed', 7), ('no_t0', 1)] | 91 |
| 38 | spirit-vs-3dmax-m1-nuke | 53 | [('BVH+AABB', 52), ('never_visible', 1)] | [('lands', 45), ('never_landed', 7), ('no_t0', 1)] | 194 |
| 39 | spirit-vs-3dmax-m2-overpass | 41 | [('BVH+AABB', 39), ('never_visible', 2)] | [('lands', 30), ('never_landed', 9), ('no_t0', 2)] | 145 |
| 40 | spirit-vs-astralis-m1-dust2 | 50 | [('BVH+AABB', 49), ('long_visible', 1)] | [('lands', 38), ('never_landed', 12)] | 217 |
| 41 | spirit-vs-astralis-m2-overpass | 44 | [('BVH+AABB', 43), ('never_visible', 1)] | [('lands', 30), ('never_landed', 13), ('no_t0', 1)] | 169 |
| 42 | spirit-vs-b8-m1-mirage-p1 | 3 | [('BVH+AABB', 3)] | [('lands', 3)] | 9 |
| 43 | spirit-vs-b8-m1-mirage-p2 | 29 | [('BVH+AABB', 29)] | [('lands', 17), ('never_landed', 12)] | 65 |
| 44 | spirit-vs-b8-m2-nuke-p1 | 25 | [('BVH+AABB', 24), ('long_visible', 1)] | [('lands', 14), ('never_landed', 11)] | 48 |
| 45 | spirit-vs-b8-m2-nuke-p2 | 24 | [('BVH+AABB', 24)] | [('lands', 17), ('never_landed', 7)] | 88 |
| 46 | spirit-vs-b8-m3-anubis | 32 | [('BVH+AABB', 32)] | [('lands', 28), ('never_landed', 4)] | 145 |
| 47 | spirit-vs-falcons-m1-anubis | 0 (no-donk) | - | - | - |
| 48 | spirit-vs-falcons-m2-mirage | 0 (no-donk) | - | - | - |
| 49 | spirit-vs-furia-m1-mirage | 75 | [('BVH+AABB', 74), ('long_visible', 1)] | [('lands', 56), ('never_landed', 19)] | 176 |
| 50 | spirit-vs-furia-m2-dust2 | 48 | [('BVH+AABB', 44), ('long_visible', 2), ('never_visible', 2)] | [('lands', 32), ('never_landed', 14), ('no_t0', 2)] | 193 |
| 51 | spirit-vs-furia-m3-nuke | 34 | [('BVH+AABB', 34)] | [('lands', 28), ('never_landed', 6)] | 114 |
| 52 | spirit-vs-g2-m1-ancient-p1 | 13 | [('BVH+AABB', 13)] | [('lands', 10), ('never_landed', 3)] | 121 |
| 53 | spirit-vs-g2-m1-ancient-p2 | 40 | [('BVH+AABB', 40)] | [('lands', 27), ('never_landed', 13)] | 211 |
| 54 | spirit-vs-g2-m2-anubis-p1 | 3 | [('BVH+AABB', 3)] | [('lands', 3)] | 47 |
| 55 | spirit-vs-g2-m2-anubis-p2 | 36 | [('BVH+AABB', 35), ('never_visible', 1)] | [('lands', 24), ('never_landed', 11), ('no_t0', 1)] | 186 |
| 56 | spirit-vs-heroic-m1-ancient | 76 | [('BVH+AABB', 75), ('never_visible', 1)] | [('lands', 58), ('never_landed', 17), ('no_t0', 1)] | 313 |
| 57 | spirit-vs-heroic-m2-nuke | 33 | [('BVH+AABB', 33)] | [('lands', 23), ('never_landed', 10)] | 88 |
| 58 | spirit-vs-liquid-m1-ancient-p1 | 0 (no-donk) | - | - | - |
| 59 | spirit-vs-liquid-m1-ancient-p2 | 0 (no-donk) | - | - | - |
| 60 | spirit-vs-liquid-m1-mirage | 51 | [('BVH+AABB', 50), ('long_visible', 1)] | [('lands', 41), ('never_landed', 10)] | 123 |
| 61 | spirit-vs-liquid-m2-ancient | 62 | [('BVH+AABB', 62)] | [('lands', 40), ('never_landed', 22)] | 248 |
| 62 | spirit-vs-liquid-m2-dust2 | 0 (no-donk) | - | - | - |
| 63 | spirit-vs-mouz-m1-dust2-iemRio | 41 | [('BVH+AABB', 40), ('never_visible', 1)] | [('lands', 30), ('never_landed', 10), ('no_t0', 1)] | 190 |
| 64 | spirit-vs-mouz-m1-dust2 | 39 | [('BVH+AABB', 39)] | [('lands', 29), ('never_landed', 10)] | 181 |
| 65 | spirit-vs-mouz-m1-mirage | 45 | [('BVH+AABB', 44), ('long_visible', 1)] | [('lands', 32), ('never_landed', 13)] | 134 |
| 66 | spirit-vs-mouz-m2-ancient-p1 | 28 | [('BVH+AABB', 27), ('never_visible', 1)] | [('lands', 14), ('never_landed', 13), ('no_t0', 1)] | 132 |
| 67 | spirit-vs-mouz-m2-ancient-p2 | 25 | [('BVH+AABB', 23), ('never_visible', 2)] | [('lands', 21), ('never_landed', 2), ('no_t0', 2)] | 150 |
| 68 | spirit-vs-mouz-m2-mirage-iemRio | 36 | [('BVH+AABB', 36)] | [('lands', 29), ('never_landed', 7)] | 92 |
| 69 | spirit-vs-mouz-m2-mirage | 28 | [('BVH+AABB', 27), ('never_visible', 1)] | [('lands', 21), ('never_landed', 6), ('no_t0', 1)] | 74 |
| 70 | spirit-vs-mouz-m3-nuke | 41 | [('BVH+AABB', 39), ('long_visible', 2)] | [('lands', 28), ('never_landed', 13)] | 140 |
| 71 | spirit-vs-natus-vincere-m1-mirage | 54 | [('BVH+AABB', 53), ('never_visible', 1)] | [('lands', 36), ('never_landed', 17), ('no_t0', 1)] | 155 |
| 72 | spirit-vs-natus-vincere-m2-nuke | 40 | [('BVH+AABB', 40)] | [('lands', 30), ('never_landed', 10)] | 115 |
| 73 | spirit-vs-natus-vincere-m3-ancient | 43 | [('BVH+AABB', 43)] | [('lands', 36), ('never_landed', 7)] | 226 |
| 74 | spirit-vs-the-mongolz-m1-dust2 | 41 | [('BVH+AABB', 41)] | [('lands', 36), ('never_landed', 5)] | 198 |
| 75 | spirit-vs-the-mongolz-m1-nuke | 46 | [('BVH+AABB', 45), ('never_visible', 1)] | [('lands', 34), ('never_landed', 11), ('no_t0', 1)] | 168 |
| 76 | spirit-vs-the-mongolz-m2-ancient | 80 | [('BVH+AABB', 79), ('never_visible', 1)] | [('lands', 62), ('never_landed', 17), ('no_t0', 1)] | 418 |
| 77 | spirit-vs-the-mongolz-m2-mirage | 57 | [('BVH+AABB', 55), ('never_visible', 2)] | [('lands', 43), ('never_landed', 12), ('no_t0', 2)] | 180 |
| 78 | spirit-vs-the-mongolz-m3-ancient | 51 | [('BVH+AABB', 51)] | [('lands', 38), ('never_landed', 13)] | 221 |
| 79 | spirit-vs-the-mongolz-m3-mirage | 43 | [('BVH+AABB', 42), ('never_visible', 1)] | [('lands', 32), ('never_landed', 10), ('no_t0', 1)] | 101 |
| 80 | spirit-vs-virtus-pro-m1-ancient | 59 | [('BVH+AABB', 59)] | [('lands', 48), ('never_landed', 11)] | 352 |
| 81 | spirit-vs-virtus-pro-m2-overpass | 41 | [('BVH+AABB', 41)] | [('lands', 36), ('never_landed', 5)] | 166 |

**Stage N=81 finished:** 2026-06-11 14:51:21 (elapsed 194.4min, processed=76, no-donk-skipped=5)

### Distribution-shape summary after stage N=81

- n_resolved (lands): **2338**
- min rt_visible_to_land_ms: **0.000ms**
- p10 rt_visible_to_land_ms: **0.000ms**
- %@tick-quantum pinning: **10.4%**
- never_landed%: **23.7%** (of 3117 t1_source rows; {'lands': 2338, 'never_landed': 739, 'no_t0': 40})
- never_visible%: **1.3%** (of 3117 t0_source rows; {'BVH+AABB': 3061, 'long_visible': 16, 'never_visible': 40})
- b5-class impossible rows (t1=t0+1 AND angle>6deg): **2**

**DOUBT TRIGGER:** b5-class impossible rows = 2 (must be 0)

