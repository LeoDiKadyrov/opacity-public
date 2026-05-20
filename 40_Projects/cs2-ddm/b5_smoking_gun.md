## B-5 SMOKING GUN -- random 15 rows where algorithm says T1=T0+1tick (15.6ms) despite crosshair NOT on target

| demo | player | round | T0 | T1 | T2 | crosshair_deg@T0 | type |
|-|-|-|-|-|-|-|-|
| parivision-vs-spirit-m2-ancient.dem | 76561198210626739 | 9 | 73243 | 73244 | 73263 | **11.4** <-- IMPOSSIBLE | peek |
| faze-vs-parivision-m2-ancient.dem | 76561198253670517 | 14 | 106258 | 106259 | 106306 | **86.4** <-- IMPOSSIBLE | peek |
| faze-vs-pain-m2-dust2.dem | 76561197989430253 | 3 | 27362 | 27363 | 27412 | **3.5** | peek |
| spirit-vs-the-mongolz-m3-mirage.dem | 76561198045898864 | 19 | 150425 | 150426 | 150444 | **16.1** <-- IMPOSSIBLE | peek |
| faze-vs-pain-m1-nuke.dem | 76561198015308884 | 12 | 104124 | 104125 | 104150 | **11.9** <-- IMPOSSIBLE | peek |
| eyeballers-vs-faze-m3-inferno.dem | 76561198016255205 | 22 | 161112 | 161113 | 161143 | **3.7** | hold |
| parivision-vs-spirit-m2-ancient.dem | 76561198081484775 | 11 | 89939 | 89940 | 89963 | **5.0** | peek |
| spirit-vs-furia-m3-nuke.dem | 76561198134401925 | 5 | 44299 | 44300 | 44323 | **5.9** <-- IMPOSSIBLE | peek |
| parivision-vs-spirit-m2-ancient.dem | 76561198995880877 | 18 | 148221 | 148222 | 148293 | **4.5** | peek |
| faze-vs-pain-m2-dust2.dem | 76561198350342505 | 20 | 182502 | 182503 | 182518 | **11.8** <-- IMPOSSIBLE | peek |
| spirit-vs-heroic-m1-ancient.dem | 76561199137143905 | 18 | 141370 | 141371 | 141409 | **6.3** <-- IMPOSSIBLE | peek |
| spirit-vs-vitality-m2-nuke.dem | 76561197978835160 | 18 | 154293 | 154294 | 154327 | **19.5** <-- IMPOSSIBLE | peek |
| 3dmax-vs-falcons-m2-ancient.dem | 76561198074762801 | 3 | 14059 | 14060 | 14079 | **8.2** <-- IMPOSSIBLE | peek |
| faze-vs-pain-m1-nuke.dem | 76561198068422762 | 21 | 187262 | 187263 | 187341 | **44.6** <-- IMPOSSIBLE | peek |
| spirit-vs-vitality-m2-nuke.dem | 76561199063238565 | 13 | 116489 | 116490 | 116516 | **4.4** | peek |

## Crosshair-angle distribution at 15.625ms sustained_aim rows (N=1027)

| angle_deg@T0 | count | pct | interpretation |
|-|-|-|-|
| **<=1 deg** | 11 | 1.1% | should have been pre_aimed branch -- algorithm missed |
| 1-3 deg | 198 | 19.3% | borderline pre-aim, defensible 1-tick |
| **3-10 deg** | 553 | 53.8% | minor adjust -- 1-tick land impossible (needs ~5deg/tick rotation) |
| **10-30 deg** | 195 | 19.0% | flick -- 1-tick land physically impossible |
| **30+ deg** | 70 | 6.8% | hard flick -- 1-tick land laughable, this row alone proves bug |

## Same rows by engagement_type
| type | n | avg_angle | max_angle |
|-|-|-|-|
| hold | 50 | 17.8 | 153.5 |
| peek | 977 | 10.8 | 192.8 |
