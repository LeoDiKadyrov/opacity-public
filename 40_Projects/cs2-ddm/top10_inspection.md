# Top-10 Rebatch — Manual Inspection Report
**Generated:** 2026-05-17 (post-Phase A item 6 staged validation)
**Source:** `analytics.db` (post-fix) vs `analytics.db.pre-staged-rebatch-2026-05-16` (pre-fix backup)
**Purpose:** Independent manual review of automated acceptance verdict from `overnight_report.md`.

---

## 1. Aggregate Metrics (Top-10)

| Metric | Value | Note |
|-|-|-|
| n_total | 785 | engagements with rt_visible_to_aim_ms NOT NULL |
| min_ms | **0.0** | B-1 floor check: must be < 125 |
| p25_ms | 15.6 | |
| median_ms | 46.9 | |
| p75_ms | 218.8 | |
| max_ms | 1328.1 | |
| n_at_125ms | 10 (1.3%) | < 10% threshold = no value pinning |
| n_pre_aimed (rt=0) | 71 | B-4 fix recovered these |
| n_pre_aimed (flag) | **71** | must == rt=0 count → consistency ✓ |
| n_sustained_aim | 714 | normal reactive engagements |
| n_none_sentinel | 0 | T1 detector failed completely |
| pre_aim rate | **9.0%** | cite-able for Reddit |

## 2. Per-Demo Breakdown

| Demo | N | min | p25 | median | p75 | max | n_at_125 | n_pre_aimed |
|-|-|-|-|-|-|-|-|-|
| spirit-vs-the-mongolz-m2-ancient.dem | 89 | 0.0 | 15.6 | 78.1 | 242.2 | 609.4 | 1 | 4 |
| passion-ua-vs-faze-m2-nuke.dem | 86 | 0.0 | 15.6 | 31.2 | 218.8 | 796.9 | 1 | 4 |
| mouz-vs-spirit-m2-mirage.dem | 112 | 0.0 | 15.6 | 46.9 | 230.5 | 1328.1 | 3 | 15 |
| spirit-vs-the-mongolz-m2-mirage.dem | 75 | 0.0 | 15.6 | 46.9 | 218.8 | 531.2 | 1 | 8 |
| spirit-vs-vitality-m1-mirage.dem | 74 | 0.0 | 15.6 | 31.2 | 179.7 | 765.6 | 2 | 6 |
| spirit-vs-virtus-pro-m1-ancient.dem | 71 | 0.0 | 15.6 | 62.5 | 234.4 | 1140.6 | 0 | 6 |
| faze-vs-pain-m2-dust2.dem | 71 | 0.0 | 15.6 | 62.5 | 203.1 | 1234.4 | 1 | 7 |
| spirit-vs-the-mongolz-m1-nuke.dem | 67 | 0.0 | 15.6 | 15.6 | 203.1 | 1187.5 | 0 | 6 |
| faze-vs-pain-m1-nuke.dem | 77 | 0.0 | 15.6 | 15.6 | 187.5 | 843.8 | 1 | 9 |
| passion-ua-vs-faze-m1-anubis.dem | 63 | 0.0 | 15.6 | 31.2 | 203.1 | 1000.0 | 0 | 6 |

## 3. Per-Player Breakdown (top-10 aggregate)

| SteamID64 | n_engagements | min_rt | n_pre_aimed | pre_aim % |
|-|-|-|-|-|
| 76561198386265483 (donk) | 63 | 0.0 | 10 | 15.9% |
| 76561198045898864 (rain) | 48 | 15.6 | 0 | 0.0% |
| 76561198210626739 (zweih) | 47 | 0.0 | 8 | 17.0% |
| 76561198016255205 (twistzz) | 42 | 0.0 | 2 | 4.8% |
| 76561198068422762 (frozen) | 39 | 0.0 | 5 | 12.8% |
| 76561198995880877 (magixx) | 34 | 0.0 | 3 | 8.8% |
| 76561198966340160 (zont1x) | 34 | 0.0 | 3 | 8.8% |
| 76561198178737429 (chopper) | 33 | 0.0 | 7 | 21.2% |
| 76561198920720017 (kyousuke) | 31 | 0.0 | 4 | 12.9% |
| 76561197989430253 (karrigan) | 28 | 0.0 | 2 | 7.1% |
| 76561198959824088 (baz) | 26 | 0.0 | 1 | 3.8% |
| 76561198081484775 (sh1ro) | 26 | 0.0 | 3 | 11.5% |
| 76561198872013168 (tN1R) | 22 | 15.6 | 0 | 0.0% |
| 76561198838822582 (mzinho) | 22 | 0.0 | 3 | 13.6% |
| 76561198845436666 (kvem) | 20 | 15.6 | 0 | 0.0% |
| 76561198015308884 (biguzera) | 18 | 0.0 | 3 | 16.7% |
| 76561198855375325 (nawwk) | 17 | 15.6 | 0 | 0.0% |
| 76561198396338183 (deko) | 17 | 0.0 | 2 | 11.8% |
| 76561198410085211 (jkaem) | 16 | 15.6 | 0 | 0.0% |
| 76561198377335846 (r3salt) | 16 | 0.0 | 3 | 18.8% |
| 76561198201620490 (nqz) | 16 | 15.6 | 0 | 0.0% |
| 76561198193174134 (X5G7V) | 16 | 0.0 | 3 | 18.8% |
| 76561198021715100 (skullz) | 15 | 15.6 | 0 | 0.0% |
| 76561198063336407 (insani) | 14 | 15.6 | 0 | 0.0% |
| 76561197991272318 (ropz) | 12 | 15.6 | 0 | 0.0% |
| 76561198362438171 (patsi) | 11 | 0.0 | 1 | 9.1% |
| 76561197973140692 (neo) | 11 | 15.6 | 0 | 0.0% |

*(Players with ≥10 engagements only.)*

## 4. All Pre-Aimed Engagements (B-4 fix proof — list every row)

These engagements would have been NaN-censored pre-fix and dropped from the distribution. Each row = one duel where the player's crosshair was already on target at T0.

| Demo | Round | Match | Player | T0 tick | T2 tick | rt_aim_to_hit | crosshair_at_T0 | Engagement type |
|-|-|-|-|-|-|-|-|-|
| fz-pn-m1-nuke | 2 | 9971 | 76561198396338183 | 18941 | 18957 | 250.0 | 1.7 | peek |
| fz-pn-m1-nuke | 2 | 9968 | 76561198377335846 | 21065 | 21080 | 234.4 | 3.5 | peek |
| fz-pn-m1-nuke | 13 | 9967 | 76561197989430253 | 118978 | 119062 | 1312.5 | 1.7 | peek |
| fz-pn-m1-nuke | 17 | 9966 | 76561198068422762 | 147060 | 147083 | 359.4 | 4.1 | peek |
| fz-pn-m1-nuke | 23 | 9962 | 76561198178737429 | 202622 | 202655 | 515.6 | 1.4 | peek |
| fz-pn-m1-nuke | 24 | 9968 | 76561198377335846 | 212857 | 212877 | 312.5 | 2.6 | peek |
| fz-pn-m1-nuke | 26 | 9971 | 76561198396338183 | 232425 | 232491 | 1031.2 | 2.2 | peek |
| fz-pn-m1-nuke | 26 | 9966 | 76561198068422762 | 232429 | 232481 | 812.5 | 1.6 | peek |
| fz-pn-m1-nuke | 28 | 9968 | 76561198377335846 | 247898 | 247956 | 906.2 | 2.5 | peek |
| fz-pn-m2-dust2 | 7 | 9942 | 76561198016255205 | 64974 | 64992 | 281.2 | 0.3 | peek |
| fz-pn-m2-dust2 | 7 | 9949 | 76561198015308884 | 65022 | 65055 | 515.6 | 3.1 | peek |
| fz-pn-m2-dust2 | 8 | 9949 | 76561198015308884 | 72202 | 72227 | 390.6 | 1.5 | peek |
| fz-pn-m2-dust2 | 11 | 9948 | 76561198178737429 | 100200 | 100260 | 937.5 | 1.7 | peek |
| fz-pn-m2-dust2 | 17 | 9948 | 76561198178737429 | 153088 | 153184 | 1500.0 | 0.9 | peek |
| fz-pn-m2-dust2 | 27 | 9949 | 76561198015308884 | 234995 | 235025 | 468.8 | 1.5 | peek |
| fz-pn-m2-dust2 | 28 | 9951 | 76561197989430253 | 246618 | 246658 | 625.0 | 1.7 | peek |
| mz-sp-m2-mirage | 1 | 9904 | 76561198193174134 | 2646 | 2685 | 609.4 | 1.8 | peek |
| mz-sp-m2-mirage | 2 | 9911 | 76561198210626739 | 12273 | 12309 | 562.5 | 1.2 | peek |
| mz-sp-m2-mirage | 3 | 9903 | 76561198386265483 | 15828 | 15847 | 296.9 | 1.8 | peek |
| mz-sp-m2-mirage | 7 | 9903 | 76561198386265483 | 52501 | 52539 | 593.8 | 0.7 | peek |
| mz-sp-m2-mirage | 16 | 9910 | 76561198081484775 | 136279 | 136301 | 343.8 | 1.1 | peek |
| mz-sp-m2-mirage | 18 | 9906 | 76561198995880877 | 152417 | 152454 | 578.1 | 2.0 | peek |
| mz-sp-m2-mirage | 20 | 9904 | 76561198193174134 | 165511 | 165557 | 718.8 | 2.4 | peek |
| mz-sp-m2-mirage | 23 | 9910 | 76561198081484775 | 194773 | 194801 | 437.5 | 1.6 | peek |
| mz-sp-m2-mirage | 27 | 9911 | 76561198210626739 | 231541 | 231560 | 296.9 | 1.3 | peek |
| mz-sp-m2-mirage | 27 | 9911 | 76561198210626739 | 232026 | 232045 | 296.9 | 1.1 | peek |
| mz-sp-m2-mirage | 27 | 9904 | 76561198193174134 | 233555 | 233599 | 687.5 | 2.4 | peek |
| mz-sp-m2-mirage | 38 | 9911 | 76561198210626739 | 334181 | 334198 | 265.6 | 1.3 | peek |
| mz-sp-m2-mirage | 38 | 9903 | 76561198386265483 | 334618 | 334656 | 593.8 | 1.2 | peek |
| mz-sp-m2-mirage | 39 | 9911 | 76561198210626739 | 340639 | 340667 | 437.5 | 2.7 | peek |
| mz-sp-m2-mirage | 40 | 9911 | 76561198210626739 | 349216 | 349240 | 375.0 | 2.6 | peek |
| psn-fz-m1-anubis | 4 | 9974 | 76561198068422762 | 23470 | 23493 | 359.4 | 0.4 | peek |
| psn-fz-m1-anubis | 9 | 9975 | 76561198178737429 | 63837 | 63855 | 281.2 | 3.0 | peek |
| psn-fz-m1-anubis | 11 | 9975 | 76561198178737429 | 81447 | 81491 | 687.5 | 1.1 | peek |
| psn-fz-m1-anubis | 13 | 9974 | 76561198068422762 | 98484 | 98542 | 906.2 | 2.1 | peek |
| psn-fz-m1-anubis | 19 | 9975 | 76561198178737429 | 148041 | 148071 | 468.8 | 3.5 | peek |
| psn-fz-m1-anubis | 21 | 9980 | 76561198016255205 | 172170 | 172184 | 218.8 | 1.5 | peek |
| psn-fz-m2-nuke | 11 | 9895 | 76561198920720017 | 80558 | 80620 | 968.8 | 1.2 | peek |
| psn-fz-m2-nuke | 13 | 9897 | 76561198068422762 | 106257 | 106279 | 343.8 | 2.7 | peek |
| psn-fz-m2-nuke | 27 | 9895 | 76561198920720017 | 244881 | 244934 | 828.1 | 2.8 | peek |
| psn-fz-m2-nuke | 29 | 9898 | 76561198178737429 | 265155 | 265168 | 203.1 | 3.8 | peek |
| s-mn-mongolz-m1-nuke | 10 | 9955 | 76561198210626739 | 67926 | 67948 | 343.8 | 0.5 | peek |
| s-mn-mongolz-m1-nuke | 12 | 9952 | 76561198386265483 | 82260 | 82281 | 328.1 | 3.6 | peek |
| s-mn-mongolz-m1-nuke | 12 | 9953 | 76561198966340160 | 83530 | 83550 | 312.5 | 2.5 | peek |
| s-mn-mongolz-m1-nuke | 14 | 9954 | 76561198995880877 | 106800 | 106841 | 640.6 | 1.5 | peek |
| s-mn-mongolz-m1-nuke | 16 | 9956 | 76561198081484775 | 127902 | 127949 | 734.4 | 2.1 | peek |
| s-mn-mongolz-m1-nuke | 24 | 9953 | 76561198966340160 | 193406 | 193493 | 1359.4 | 1.7 | peek |
| s-mn-mongolz-m2-ancient | 7 | 9889 | 76561198362438171 | 44264 | 44291 | 421.9 | 1.8 | hold |
| s-mn-mongolz-m2-ancient | 9 | 9884 | 76561199203563345 | 63218 | 63301 | 1296.9 | 2.7 | peek |
| s-mn-mongolz-m2-ancient | 22 | 9891 | 76561198959824088 | 167289 | 167339 | 781.2 | 2.2 | peek |
| s-mn-mongolz-m2-ancient | 27 | 9888 | 76561198210626739 | 207080 | 207115 | 546.9 | 5.1 | peek |
| s-mn-mongolz-m2-mirage | 9 | 9912 | 76561198838822582 | 74853 | 74872 | 296.9 | 1.6 | peek |
| s-mn-mongolz-m2-mirage | 10 | 9919 | 76561198920720017 | 86769 | 86815 | 718.8 | 2.7 | peek |
| s-mn-mongolz-m2-mirage | 12 | 9915 | 76561198995880877 | 99542 | 99564 | 343.8 | 1.3 | peek |
| s-mn-mongolz-m2-mirage | 16 | 9912 | 76561198838822582 | 143369 | 143380 | 171.9 | 1.6 | peek |
| s-mn-mongolz-m2-mirage | 17 | 9921 | 76561198386265483 | 152117 | 152148 | 484.4 | 2.0 | peek |
| s-mn-mongolz-m2-mirage | 20 | 9913 | 76561198966340160 | 179633 | 179705 | 1125.0 | 2.3 | peek |
| s-mn-mongolz-m2-mirage | 28 | 9919 | 76561198920720017 | 259163 | 259178 | 234.4 | 1.1 | peek |
| s-mn-mongolz-m2-mirage | 29 | 9912 | 76561198838822582 | 265793 | 265825 | 500.0 | 0.8 | peek |
| s-vp-m1-ancient | 6 | 9941 | 76561198386265483 | 43087 | 43107 | 312.5 | 1.9 | peek |
| s-vp-m1-ancient | 7 | 9941 | 76561198386265483 | 47962 | 47983 | 328.1 | 1.7 | peek |
| s-vp-m1-ancient | 7 | 9937 | 76561198044045107 | 48953 | 49004 | 796.9 | 2.7 | peek |
| s-vp-m1-ancient | 10 | 9941 | 76561198386265483 | 64939 | 64967 | 437.5 | 1.8 | peek |
| s-vp-m1-ancient | 19 | 9933 | 76561198055109028 | 164733 | 164767 | 531.2 | 3.2 | peek |
| s-vp-m1-ancient | 24 | 9941 | 76561198386265483 | 204545 | 204567 | 343.8 | 2.7 | peek |
| s-vit-m1-mirage | 10 | 9930 | 76561197978835160 | 69571 | 69590 | 296.9 | 1.8 | peek |
| s-vit-m1-mirage | 15 | 9925 | 76561198386265483 | 115302 | 115320 | 281.2 | 1.5 | peek |
| s-vit-m1-mirage | 22 | 9929 | 76561197989744167 | 178460 | 178486 | 406.2 | 1.0 | peek |
| s-vit-m1-mirage | 23 | 9922 | 76561199063238565 | 186848 | 186868 | 312.5 | 3.1 | peek |
| s-vit-m1-mirage | 24 | 9928 | 76561198113666193 | 194996 | 195010 | 218.8 | 5.2 | peek |
| s-vit-m1-mirage | 27 | 9922 | 76561199063238565 | 217650 | 217675 | 390.6 | 0.7 | peek |

## 5. Recovered Low-RT Engagements (sustained_aim with rt < 50ms)

These would have been clipped to ≥125ms pre-fix by the grace floor. Now they register accurately.

| Demo | Match | Player | T0 | T1 | rt_visible_to_aim | t1_source |
|-|-|-|-|-|-|-|
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 31154 | 31155.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 44673 | 44674.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 92158 | 92159.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 98922 | 98923.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 102082 | 102083.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 158622 | 158623.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 175250 | 175251.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 197150 | 197151.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9882 | 76561198386265483 | 242153 | 242154.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9883 | 76561198872013168 | 130780 | 130781.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9883 | 76561198872013168 | 136893 | 136894.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9883 | 76561198872013168 | 224680 | 224681.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9883 | 76561198872013168 | 232727 | 232728.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9884 | 76561199203563345 | 54844 | 54845.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9885 | 76561198838822582 | 188762 | 188763.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9885 | 76561198838822582 | 242426 | 242427.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 22405 | 22406.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 37816 | 37817.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 53678 | 53679.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 55773 | 55774.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9887 | 76561198966340160 | 229728 | 229729.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9887 | 76561198966340160 | 232909 | 232910.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9888 | 76561198210626739 | 250469 | 250470.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9889 | 76561198362438171 | 6663 | 6664.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9889 | 76561198362438171 | 37766 | 37767.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9889 | 76561198362438171 | 123618 | 123619.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9890 | 76561198081484775 | 94459 | 94460.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9890 | 76561198081484775 | 107898 | 107899.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9891 | 76561198959824088 | 22385 | 22386.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 20861 | 20862.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 28844 | 28845.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 96123 | 96124.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 122650 | 122651.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 183548 | 183549.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 190680 | 190681.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9892 | 76561198845436666 | 213274 | 213275.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9893 | 76561198201620490 | 11783 | 11784.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9893 | 76561198201620490 | 93320 | 93321.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9893 | 76561198201620490 | 140747 | 140748.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9893 | 76561198201620490 | 144580 | 144581.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9894 | 76561198410085211 | 53721 | 53722.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9894 | 76561198410085211 | 68988 | 68989.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9894 | 76561198410085211 | 80206 | 80207.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9894 | 76561198410085211 | 90872 | 90873.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9894 | 76561198410085211 | 163248 | 163249.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9895 | 76561198920720017 | 56253 | 56254.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9895 | 76561198920720017 | 128454 | 128455.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9895 | 76561198920720017 | 137603 | 137604.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9895 | 76561198920720017 | 143758 | 143759.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9896 | 76561198021715100 | 76016 | 76017.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9896 | 76561198021715100 | 80720 | 80721.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9896 | 76561198021715100 | 94189 | 94190.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9896 | 76561198021715100 | 183414 | 183415.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9897 | 76561198068422762 | 25354 | 25355.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9897 | 76561198068422762 | 53750 | 53751.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9897 | 76561198068422762 | 135949 | 135950.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9897 | 76561198068422762 | 155958 | 155959.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9898 | 76561198178737429 | 6462 | 6463.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9898 | 76561198178737429 | 67318 | 67319.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9898 | 76561198178737429 | 122263 | 122264.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9899 | 76561198016255205 | 11643 | 11644.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9899 | 76561198016255205 | 128415 | 128416.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9899 | 76561198016255205 | 163515 | 163516.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9899 | 76561198016255205 | 249222 | 249223.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9899 | 76561198016255205 | 262771 | 262772.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9900 | 76561197989430253 | 20762 | 20763.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9900 | 76561197989430253 | 137604 | 137605.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9901 | 76561198365118288 | 144525 | 144526.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 5434 | 5435.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 36040 | 36041.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 53395 | 53396.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 64550 | 64551.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9903 | 76561198386265483 | 44850 | 44851.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9903 | 76561198386265483 | 46043 | 46044.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9903 | 76561198386265483 | 57153 | 57154.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9903 | 76561198386265483 | 281111 | 281112.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 144749 | 144750.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 184707 | 184708.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 219609 | 219610.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 233249 | 233250.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 342378 | 342379.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 111480 | 111481.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 115609 | 115610.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 126425 | 126426.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 355475 | 355476.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 360357 | 360358.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9906 | 76561198995880877 | 19504 | 19505.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9906 | 76561198995880877 | 139368 | 139369.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9906 | 76561198995880877 | 159076 | 159077.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9906 | 76561198995880877 | 281818 | 281819.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9906 | 76561198995880877 | 353795 | 353796.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9907 | 76561198063336407 | 111446 | 111447.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9907 | 76561198063336407 | 144794 | 144795.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9907 | 76561198063336407 | 250901 | 250902.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9907 | 76561198063336407 | 303785 | 303786.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9908 | 76561198138828475 | 5346 | 5347.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9909 | 76561198355739212 | 188103 | 188104.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9910 | 76561198081484775 | 61076 | 61077.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9910 | 76561198081484775 | 137515 | 137516.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9911 | 76561198210626739 | 63820 | 63821.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9911 | 76561198210626739 | 76572 | 76573.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9911 | 76561198210626739 | 123179 | 123180.0 | **15.6** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9911 | 76561198210626739 | 272259 | 272260.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9912 | 76561198838822582 | 36560 | 36561.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9912 | 76561198838822582 | 84825 | 84826.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9913 | 76561198966340160 | 84919 | 84920.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9913 | 76561198966340160 | 92980 | 92981.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9913 | 76561198966340160 | 94649 | 94650.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9913 | 76561198966340160 | 101664 | 101665.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9914 | 76561198210626739 | 86489 | 86490.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9914 | 76561198210626739 | 132100 | 132101.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9914 | 76561198210626739 | 189060 | 189061.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9915 | 76561198995880877 | 20183 | 20184.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9915 | 76561198995880877 | 27893 | 27894.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9916 | 76561198081484775 | 12219 | 12220.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9916 | 76561198081484775 | 162520 | 162521.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9916 | 76561198081484775 | 225184 | 225185.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9918 | 76561198959824088 | 246078 | 246079.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9919 | 76561198920720017 | 10239 | 10240.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9919 | 76561198920720017 | 20459 | 20460.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9919 | 76561198920720017 | 44936 | 44937.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9919 | 76561198920720017 | 128636 | 128637.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9920 | 76561198045898864 | 28525 | 28526.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9920 | 76561198045898864 | 37105 | 37106.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9920 | 76561198045898864 | 200714 | 200715.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9920 | 76561198045898864 | 213045 | 213046.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9921 | 76561198386265483 | 108540 | 108541.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9921 | 76561198386265483 | 162346 | 162347.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9921 | 76561198386265483 | 206582 | 206583.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9923 | 76561197991272318 | 83299 | 83300.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9923 | 76561197991272318 | 101061 | 101062.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9924 | 76561198872013168 | 32371 | 32372.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9924 | 76561198872013168 | 201480 | 201481.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9924 | 76561198872013168 | 216726 | 216727.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 2853 | 2854.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 10700 | 10701.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 17495 | 17496.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 55471 | 55472.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 61341 | 61342.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 151300 | 151301.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 166824 | 166825.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9925 | 76561198386265483 | 233887 | 233888.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9926 | 76561198995880877 | 67614 | 67615.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9926 | 76561198995880877 | 185945 | 185946.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9926 | 76561198995880877 | 196303 | 196304.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9927 | 76561198081484775 | 162847 | 162848.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9929 | 76561197989744167 | 57921 | 57922.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9929 | 76561197989744167 | 61518 | 61519.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9929 | 76561197989744167 | 168770 | 168771.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9929 | 76561197989744167 | 217751 | 217752.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9930 | 76561197978835160 | 18079 | 18080.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9930 | 76561197978835160 | 48585 | 48586.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9930 | 76561197978835160 | 49810 | 49811.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9930 | 76561197978835160 | 109538 | 109539.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 39794 | 39795.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 49035 | 49036.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 49562 | 49563.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 73604 | 73605.0 | **15.6** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 223052 | 223053.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9932 | 76561198210626739 | 22889 | 22890.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9932 | 76561198210626739 | 53903 | 53904.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9932 | 76561198210626739 | 137500 | 137501.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9933 | 76561198055109028 | 43156 | 43157.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9933 | 76561198055109028 | 141887 | 141888.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9933 | 76561198055109028 | 214787 | 214788.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9935 | 76561198080114546 | 64925 | 64926.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9935 | 76561198080114546 | 89239 | 89240.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9935 | 76561198080114546 | 99504 | 99505.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9935 | 76561198080114546 | 127812 | 127813.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9935 | 76561198080114546 | 200685 | 200686.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9936 | 76561197995817501 | 55840 | 55841.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9936 | 76561197995817501 | 63670 | 63671.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9936 | 76561197995817501 | 76088 | 76089.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9936 | 76561197995817501 | 100723 | 100724.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9937 | 76561198044045107 | 35738 | 35739.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9938 | 76561198121220486 | 96173 | 96174.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9938 | 76561198121220486 | 100485 | 100486.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9939 | 76561198045898864 | 95884 | 95885.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9939 | 76561198045898864 | 169663 | 169664.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9939 | 76561198045898864 | 214785 | 214786.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 48840 | 48841.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 95436 | 95437.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 142485 | 142486.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 178794 | 178795.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 185700 | 185701.0 | **15.6** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9941 | 76561198386265483 | 186295 | 186296.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9942 | 76561198016255205 | 63509 | 63510.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9942 | 76561198016255205 | 82973 | 82974.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9942 | 76561198016255205 | 183117 | 183118.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9942 | 76561198016255205 | 224452 | 224453.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9943 | 76561198201620490 | 140925 | 140926.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9944 | 76561198377335846 | 128253 | 128254.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9944 | 76561198377335846 | 214578 | 214579.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9946 | 76561198068422762 | 34968 | 34969.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9946 | 76561198068422762 | 230318 | 230319.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9947 | 76561198350342505 | 182502 | 182503.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9948 | 76561198178737429 | 81926 | 81927.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9948 | 76561198178737429 | 99514 | 99515.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9948 | 76561198178737429 | 238736 | 238737.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9948 | 76561198178737429 | 248409 | 248410.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9949 | 76561198015308884 | 182380 | 182381.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9949 | 76561198015308884 | 214175 | 214176.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9949 | 76561198015308884 | 251187 | 251188.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9950 | 76561198396338183 | 44447 | 44448.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9950 | 76561198396338183 | 231051 | 231052.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 27362 | 27363.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 34468 | 34469.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 82190 | 82191.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 183018 | 183019.0 | **15.6** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 207559 | 207560.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 26793 | 26794.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 33768 | 33769.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 34417 | 34418.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 136432 | 136433.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 142169 | 142170.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9952 | 76561198386265483 | 143227 | 143228.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9953 | 76561198966340160 | 42366 | 42367.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9953 | 76561198966340160 | 45967 | 45968.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9953 | 76561198966340160 | 167791 | 167792.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9953 | 76561198966340160 | 200731 | 200732.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9953 | 76561198966340160 | 213139 | 213140.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9954 | 76561198995880877 | 42372 | 42373.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9954 | 76561198995880877 | 110957 | 110958.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9954 | 76561198995880877 | 130337 | 130338.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9954 | 76561198995880877 | 200729 | 200730.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9955 | 76561198210626739 | 20906 | 20907.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9955 | 76561198210626739 | 26903 | 26904.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9955 | 76561198210626739 | 175492 | 175493.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9956 | 76561198081484775 | 49544 | 49545.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9956 | 76561198081484775 | 59607 | 59608.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9956 | 76561198081484775 | 148445 | 148446.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9957 | 76561198045898864 | 85301 | 85302.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9957 | 76561198045898864 | 167714 | 167715.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9957 | 76561198045898864 | 187535 | 187536.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9958 | 76561198959824088 | 165731 | 165732.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9958 | 76561198959824088 | 192635 | 192636.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9960 | 76561198838822582 | 110257 | 110258.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9961 | 76561198920720017 | 209373 | 209374.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9962 | 76561198178737429 | 95456 | 95457.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9962 | 76561198178737429 | 256233 | 256234.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 24373 | 24374.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 86151 | 86152.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 128876 | 128877.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 135638 | 135639.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 225471 | 225472.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9964 | 76561198011732823 | 20765 | 20766.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9964 | 76561198011732823 | 135632 | 135633.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 75915 | 75916.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 121792 | 121793.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 166851 | 166852.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 176784 | 176785.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 187262 | 187263.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 187813 | 187814.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9966 | 76561198068422762 | 213628 | 213629.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9967 | 76561197989430253 | 96643 | 96644.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9967 | 76561197989430253 | 103845 | 103846.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9967 | 76561197989430253 | 130555 | 130556.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9967 | 76561197989430253 | 254136 | 254137.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9968 | 76561198377335846 | 51031 | 51032.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9968 | 76561198377335846 | 73785 | 73786.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9968 | 76561198377335846 | 85984 | 85985.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9968 | 76561198377335846 | 134535 | 134536.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9968 | 76561198377335846 | 190684 | 190685.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9969 | 76561198350342505 | 10782 | 10783.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9969 | 76561198350342505 | 34186 | 34187.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9969 | 76561198350342505 | 123064 | 123065.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9970 | 76561198015308884 | 104124 | 104125.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9970 | 76561198015308884 | 256137 | 256138.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9970 | 76561198015308884 | 256650 | 256651.0 | **15.6** | sustained_aim |
| faze-vs-pain-m1-nuke | 9971 | 76561198396338183 | 88881 | 88882.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9972 | 76561198365118288 | 122409 | 122410.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9973 | 76561198845436666 | 122181 | 122182.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9973 | 76561198845436666 | 127547 | 127548.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 34300 | 34301.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 39197 | 39198.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 99295 | 99296.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 182903 | 182904.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 183563 | 183564.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9975 | 76561198178737429 | 193286 | 193287.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9976 | 76561198021715100 | 20637 | 20638.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9976 | 76561198021715100 | 76644 | 76645.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9976 | 76561198021715100 | 80077 | 80078.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9977 | 76561197989430253 | 130796 | 130797.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9977 | 76561197989430253 | 152197 | 152198.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9978 | 76561198201620490 | 89013 | 89014.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9978 | 76561198201620490 | 162090 | 162091.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9978 | 76561198201620490 | 184545 | 184546.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9979 | 76561198920720017 | 22684 | 22685.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9979 | 76561198920720017 | 68793 | 68794.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9979 | 76561198920720017 | 69452 | 69453.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9979 | 76561198920720017 | 127610 | 127611.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9979 | 76561198920720017 | 172103 | 172104.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9980 | 76561198016255205 | 52772 | 52773.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9980 | 76561198016255205 | 194446 | 194447.0 | **15.6** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9981 | 76561198410085211 | 67431 | 67432.0 | **15.6** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9885 | 76561198838822582 | 16213 | 16215.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 108858 | 108860.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9887 | 76561198966340160 | 29978 | 29980.0 | **31.2** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 333866 | 333868.0 | **31.2** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9903 | 76561198386265483 | 178457 | 178459.0 | **31.2** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9905 | 76561198045898864 | 282770 | 282772.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9915 | 76561198995880877 | 128041 | 128043.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9916 | 76561198081484775 | 102190 | 102192.0 | **31.2** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9923 | 76561197991272318 | 151384 | 151386.0 | **31.2** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 25402 | 25404.0 | **31.2** | sustained_aim |
| spirit-vs-virtus-pro-m1-ancient | 9939 | 76561198045898864 | 22977 | 22979.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9958 | 76561198959824088 | 156008 | 156010.0 | **31.2** | sustained_aim |
| faze-vs-pain-m1-nuke | 9971 | 76561198396338183 | 100922 | 100924.0 | **31.2** | sustained_aim |
| passion-ua-vs-faze-m1-anubis | 9974 | 76561198068422762 | 172068 | 172070.0 | **31.2** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9883 | 76561198872013168 | 240948 | 240951.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9885 | 76561198838822582 | 261185 | 261188.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-ancient | 9886 | 76561198045898864 | 222737 | 222740.0 | **46.9** | sustained_aim |
| passion-ua-vs-faze-m2-nuke | 9898 | 76561198178737429 | 231684 | 231687.0 | **46.9** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 207781 | 207784.0 | **46.9** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9902 | 76561198855375325 | 272271 | 272274.0 | **46.9** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9904 | 76561198193174134 | 222784 | 222787.0 | **46.9** | sustained_aim |
| mouz-vs-spirit-m2-mirage | 9908 | 76561198138828475 | 166079 | 166082.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9913 | 76561198966340160 | 189080 | 189083.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9918 | 76561198959824088 | 139568 | 139571.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9921 | 76561198386265483 | 108023 | 108026.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m2-mirage | 9921 | 76561198386265483 | 138918 | 138921.0 | **46.9** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9923 | 76561197991272318 | 224844 | 224847.0 | **46.9** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 160327 | 160330.0 | **46.9** | sustained_aim |
| spirit-vs-vitality-m1-mirage | 9931 | 76561197973140692 | 166827 | 166830.0 | **46.9** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9947 | 76561198350342505 | 198137 | 198140.0 | **46.9** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9950 | 76561198396338183 | 82369 | 82372.0 | **46.9** | sustained_aim |
| faze-vs-pain-m2-dust2 | 9951 | 76561197989430253 | 197920 | 197923.0 | **46.9** | sustained_aim |
| spirit-vs-the-mongolz-m1-nuke | 9958 | 76561198959824088 | 148414 | 148417.0 | **46.9** | sustained_aim |
| faze-vs-pain-m1-nuke | 9963 | 76561198016255205 | 211570 | 211573.0 | **46.9** | sustained_aim |
| faze-vs-pain-m1-nuke | 9967 | 76561197989430253 | 160600 | 160603.0 | **46.9** | sustained_aim |
| faze-vs-pain-m1-nuke | 9969 | 76561198350342505 | 187739 | 187742.0 | **46.9** | sustained_aim |
| faze-vs-pain-m1-nuke | 9971 | 76561198396338183 | 63310 | 63313.0 | **46.9** | sustained_aim |
| faze-vs-pain-m1-nuke | 9971 | 76561198396338183 | 172228 | 172231.0 | **46.9** | sustained_aim |

*333 engagements recovered from the pre-fix floor.*

## 6. Random Sample (5 rows per demo for spot-check)

### spirit-vs-the-mongolz-m2-ancient.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9891 | 76561198959824088 | 147439 | 147469.0 | 147492 | 468.8 | 359.4 | sustained_aim | peek |
| 9887 | 76561198966340160 | 207097 | 207102.0 | 207134 | 78.1 | 500.0 | sustained_aim | peek |
| 9887 | 76561198966340160 | 91934 | 91940.0 | 92013 | 93.8 | 1140.6 | sustained_aim | hold |
| 9889 | 76561198362438171 | 223556 | 223562.0 | 223577 | 93.8 | 234.4 | sustained_aim | hold |
| 9882 | 76561198386265483 | 158622 | 158623.0 | 158653 | 15.6 | 468.8 | sustained_aim | peek |

### passion-ua-vs-faze-m2-nuke.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9894 | 76561198410085211 | 53721 | 53722.0 | 53779 | 15.6 | 890.6 | sustained_aim | hold |
| 9895 | 76561198920720017 | 220694 | 220705.0 | 220784 | 171.9 | 1234.4 | sustained_aim | peek |
| 9900 | 76561197989430253 | 20762 | 20763.0 | 20791 | 15.6 | 437.5 | sustained_aim | peek |
| 9892 | 76561198845436666 | 143590 | 143611.0 | 143641 | 328.1 | 468.8 | sustained_aim | peek |
| 9899 | 76561198016255205 | 185563 | 185588.0 | 185621 | 390.6 | 515.6 | sustained_aim | hold |

### mouz-vs-spirit-m2-mirage.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9911 | 76561198210626739 | 87527 | 87533.0 | 87565 | 93.8 | 500.0 | sustained_aim | peek |
| 9905 | 76561198045898864 | 52574 | 52583.0 | 52611 | 140.6 | 437.5 | sustained_aim | peek |
| 9903 | 76561198386265483 | 334618 | 334618.0 | 334656 | 0.0 | 593.8 | pre_aimed | peek |
| 9905 | 76561198045898864 | 282770 | 282772.0 | 282832 | 31.2 | 937.5 | sustained_aim | hold |
| 9903 | 76561198386265483 | 355342 | 355354.0 | 355383 | 187.5 | 453.1 | sustained_aim | peek |

### spirit-vs-the-mongolz-m2-mirage.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9913 | 76561198966340160 | 64410 | 64434.0 | 64439 | 375.0 | 78.1 | sustained_aim | hold |
| 9915 | 76561198995880877 | 255763 | 255782.0 | 255793 | 296.9 | 171.9 | sustained_aim | peek |
| 9921 | 76561198386265483 | 206582 | 206583.0 | 206585 | 15.6 | 31.2 | sustained_aim | peek |
| 9921 | 76561198386265483 | 212339 | 212354.0 | 212428 | 234.4 | 1156.2 | sustained_aim | peek |
| 9916 | 76561198081484775 | 102190 | 102192.0 | 102212 | 31.2 | 312.5 | sustained_aim | peek |

### spirit-vs-vitality-m1-mirage.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9926 | 76561198995880877 | 196303 | 196304.0 | 196330 | 15.6 | 406.2 | sustained_aim | peek |
| 9931 | 76561197973140692 | 208222 | 208237.0 | 208254 | 234.4 | 265.6 | sustained_aim | peek |
| 9931 | 76561197973140692 | 49035 | 49036.0 | 49096 | 15.6 | 937.5 | sustained_aim | peek |
| 9922 | 76561199063238565 | 186848 | 186848.0 | 186868 | 0.0 | 312.5 | pre_aimed | peek |
| 9924 | 76561198872013168 | 216726 | 216727.0 | 216758 | 15.6 | 484.4 | sustained_aim | peek |

### spirit-vs-virtus-pro-m1-ancient.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9935 | 76561198080114546 | 89239 | 89240.0 | 89263 | 15.6 | 359.4 | sustained_aim | peek |
| 9935 | 76561198080114546 | 127812 | 127813.0 | 127870 | 15.6 | 890.6 | sustained_aim | peek |
| 9937 | 76561198044045107 | 48953 | 48953.0 | 49004 | 0.0 | 796.9 | pre_aimed | peek |
| 9933 | 76561198055109028 | 164733 | 164733.0 | 164767 | 0.0 | 531.2 | pre_aimed | peek |
| 9936 | 76561197995817501 | 72439 | 72455.0 | 72472 | 250.0 | 265.6 | sustained_aim | peek |

### faze-vs-pain-m2-dust2.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9951 | 76561197989430253 | 207559 | 207560.0 | 207592 | 15.6 | 500.0 | sustained_aim | peek |
| 9946 | 76561198068422762 | 65079 | 65106.0 | 65116 | 421.9 | 156.2 | sustained_aim | hold |
| 9950 | 76561198396338183 | 145251 | 145257.0 | 145294 | 93.8 | 578.1 | sustained_aim | hold |
| 9949 | 76561198015308884 | 72202 | 72202.0 | 72227 | 0.0 | 390.6 | pre_aimed | peek |
| 9949 | 76561198015308884 | 214175 | 214176.0 | 214197 | 15.6 | 328.1 | sustained_aim | peek |

### spirit-vs-the-mongolz-m1-nuke.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9958 | 76561198959824088 | 192635 | 192636.0 | 192686 | 15.6 | 781.2 | sustained_aim | peek |
| 9955 | 76561198210626739 | 143271 | 143305.0 | 143339 | 531.2 | 531.2 | sustained_aim | peek |
| 9952 | 76561198386265483 | 82260 | 82260.0 | 82281 | 0.0 | 328.1 | pre_aimed | peek |
| 9960 | 76561198838822582 | 69827 | 69834.0 | 69883 | 109.4 | 765.6 | sustained_aim | hold |
| 9961 | 76561198920720017 | 157350 | 157355.0 | 157367 | 78.1 | 187.5 | sustained_aim | peek |

### faze-vs-pain-m1-nuke.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9969 | 76561198350342505 | 123064 | 123065.0 | 123087 | 15.6 | 343.8 | sustained_aim | peek |
| 9970 | 76561198015308884 | 256137 | 256138.0 | 256153 | 15.6 | 234.4 | sustained_aim | peek |
| 9966 | 76561198068422762 | 176784 | 176785.0 | 176828 | 15.6 | 671.9 | sustained_aim | peek |
| 9969 | 76561198350342505 | 10782 | 10783.0 | 10816 | 15.6 | 515.6 | sustained_aim | peek |
| 9971 | 76561198396338183 | 203960 | 203967.0 | 203980 | 109.4 | 203.1 | sustained_aim | peek |

### passion-ua-vs-faze-m1-anubis.dem

| match | player | T0 | T1 | T2 | rt_T0→T1 | rt_T1→T2 | t1_source | type |
|-|-|-|-|-|-|-|-|-|
| 9974 | 76561198068422762 | 76687 | 76720.0 | 76736 | 515.6 | 250.0 | sustained_aim | peek |
| 9981 | 76561198410085211 | 184453 | 184457.0 | 184506 | 62.5 | 765.6 | sustained_aim | hold |
| 9979 | 76561198920720017 | 69452 | 69453.0 | 69494 | 15.6 | 640.6 | sustained_aim | peek |
| 9980 | 76561198016255205 | 135194 | 135213.0 | 135273 | 296.9 | 937.5 | sustained_aim | peek |
| 9972 | 76561198365118288 | 148060 | 148078.0 | 148095 | 281.2 | 265.6 | sustained_aim | peek |

## 7. Pre-Fix vs Post-Fix Comparison (same 10 demos)

| Demo | pre N | pre min | pre n_at_125 | post N | post min | post n_at_125 | post n_pre_aimed |
|-|-|-|-|-|-|-|-|
| spirit-vs-the-mongolz-m2-ancient.dem | 87 | 125.0 | 24 | 89 | **0.0** | 1 | 4 |
| passion-ua-vs-faze-m2-nuke.dem | 80 | 125.0 | 25 | 86 | **0.0** | 1 | 4 |
| mouz-vs-spirit-m2-mirage.dem | 75 | 125.0 | 19 | 112 | **0.0** | 3 | 15 |
| spirit-vs-the-mongolz-m2-mirage.dem | 68 | 125.0 | 23 | 75 | **0.0** | 1 | 8 |
| spirit-vs-vitality-m1-mirage.dem | 69 | 125.0 | 26 | 74 | **0.0** | 2 | 6 |
| spirit-vs-virtus-pro-m1-ancient.dem | 65 | 125.0 | 16 | 71 | **0.0** | 0 | 6 |
| faze-vs-pain-m2-dust2.dem | 60 | 125.0 | 17 | 71 | **0.0** | 1 | 7 |
| spirit-vs-the-mongolz-m1-nuke.dem | 59 | 125.0 | 14 | 67 | **0.0** | 0 | 6 |
| faze-vs-pain-m1-nuke.dem | 64 | 125.0 | 18 | 77 | **0.0** | 1 | 9 |
| passion-ua-vs-faze-m1-anubis.dem | 56 | 125.0 | 15 | 63 | **0.0** | 0 | 6 |

---

**Files referenced:**

- `overnight_report.md` — autonomous watcher verdict (top-5 PASS + top-10 PASS)
- `rebatch_top5.log` — full pipeline log for top-5 (94 min wall)
- `rebatch_top10.log` — full pipeline log for next-5 (85 min wall)
- `analytics.db` — current post-fix DB (this report's source)
- `analytics.db.pre-staged-rebatch-2026-05-16` — pre-fix backup (Section 7 source)

If anything looks suspicious, document the specific row + diagnosis. Acceptance criteria:

- Section 1 min_ms < 125 (B-1 cleared) — currently **0.0** ✓
- Section 1 n_pre_aimed (rt=0) == n_pre_aimed (flag) — currently **71 == 71** ✓
- Section 2 per-demo min_ms < 125 every row — currently **all 0.0** ✓
- Section 4 all pre_aimed engagements have crosshair_angle_at_T0 close to 0° (spot-check ~5 random rows)
- Section 5 recovered low-rt engagements look like legitimate fast reactions (not data corruption)
- Section 7 post-fix N is comparable to pre-fix N per demo (within ±20% — different rejection profile, not catastrophic data loss)
