# OF-3 Re-batch Inspection -- donk timing pass (D-14)
**Source:** `analytics.db` (`duel_episodes` table only -- Pitfall 5)
**Player:** donk (76561198386265483)
**Purpose:** Independent manual review artifact for the N=5 checkpoint (D-14). Every table carries `crosshair_angle_at_t0_deg` -- the physics-bounded column mandated by the B-5 post-mortem.

---

## 1. Aggregate

| Metric | Value |
|-|-|
| n_episodes (total, donk) | 3352 |
| n with t0_tick resolved | 155 |
| n with t1_tick resolved | 123 |
| t0_source = BVH+AABB | 155 (98.7%) |
| t0_source = never_visible | 2 (1.3%) |
| t1_source = lands | 123 (78.3%) |
| t1_source = never_landed | 32 (20.4%) |
| t1_source = no_t0 | 2 (1.3%) |
| rt_visible_to_land_ms min | 0.00 |
| rt_visible_to_land_ms p10 | 0.00 |
| rt_visible_to_land_ms p25 | 0.00 |
| rt_visible_to_land_ms median | 46.88 |
| rt_visible_to_land_ms mean | 144.82 |
| rt_visible_to_land_ms max | 1312.50 |
| crosshair_angle_at_t0_deg (lands) max | 125.74 |

---

## 2. Per-Demo Breakdown

| Demo | n_episodes | median rt_ms | %@tick-quantum | max crosshair_angle_at_t0_deg |
|-|-|-|-|-|
| 9z-vs-spirit-m1-overpass | 42 | 93.75 | 8.1% | 50.29 |
| 9z-vs-spirit-m2-dust2 | 43 | 93.75 | 11.4% | 42.80 |
| astralis-vs-spirit-m1-dust2-p1 | 11 | 0.00 | 11.1% | 12.20 |
| astralis-vs-spirit-m1-dust2-p2 | 24 | 187.50 | 0.0% | 125.74 |
| astralis-vs-spirit-m2-ancient | 37 | 0.00 | 25.0% | 41.59 |

---

## 3. Per-Actor (donk) -- Crosshair-Angle Distribution on Lands

- median rt_visible_to_land_ms: **46.88**
- never_landed%: **20.4%** (32 of 157 t1_source rows)

| angle_deg@T0 (on lands) | count | pct | interpretation |
|-|-|-|-|
| <=1 deg | 12 | 9.8% | already on-target -- pre-aim-class, defensible 1-tick land |
| 1-3 deg | 37 | 30.1% | borderline, defensible near-instant land |
| 3-10 deg | 57 | 46.3% | minor adjust -- multi-tick land expected |
| 10-30 deg | 8 | 6.5% | flick -- multi-tick land expected |
| 30+ deg | 9 | 7.3% | hard flick -- multi-tick land expected |

---

## 4. Full List of Resolved Rows (lands, capped at 200)

| demo | round/tick | t0_tick | t1_tick | t2 (first_event_tick) | rt_visible_to_land_ms | crosshair_angle_at_t0_deg | t1_source |
|-|-|-|-|-|-|-|-|
| 9z-vs-spirit-m1-overpass | 9609 | 9587 | 9596 | 9609 | 140.62 | 6.55 | lands |
| 9z-vs-spirit-m1-overpass | 10274 | 10254 | 10261 | 10274 | 109.38 | 7.81 | lands |
| 9z-vs-spirit-m1-overpass | 10320 | 10302 | - | 10320 | - | 5.85 | never_landed |
| 9z-vs-spirit-m1-overpass | 10369 | 10316 | 10324 | 10369 | 125.00 | 6.29 | lands |
| 9z-vs-spirit-m1-overpass | 14502 | 14477 | 14477 | 14502 | 0.00 | 1.90 | lands |
| 9z-vs-spirit-m1-overpass | 14980 | 14946 | 14977 | 14980 | 484.38 | 50.29 | lands |
| 9z-vs-spirit-m1-overpass | 22576 | 22564 | 22564 | 22576 | 0.00 | 0.59 | lands |
| 9z-vs-spirit-m1-overpass | 22788 | 22740 | 22740 | 22788 | 0.00 | 2.21 | lands |
| 9z-vs-spirit-m1-overpass | 22894 | 22866 | 22893 | 22894 | 421.88 | 3.03 | lands |
| 9z-vs-spirit-m1-overpass | 23103 | 23090 | 23090 | 23103 | 0.00 | 1.23 | lands |
| 9z-vs-spirit-m1-overpass | 37252 | 37224 | 37239 | 37252 | 234.38 | 5.84 | lands |
| 9z-vs-spirit-m1-overpass | 37818 | 37793 | 37796 | 37818 | 46.88 | 3.56 | lands |
| 9z-vs-spirit-m1-overpass | 37936 | 37905 | 37905 | 37936 | 0.00 | 1.45 | lands |
| 9z-vs-spirit-m1-overpass | 38072 | 38032 | 38059 | 38072 | 421.88 | 8.99 | lands |
| 9z-vs-spirit-m1-overpass | 48747 | 48728 | 48734 | 48747 | 93.75 | 7.00 | lands |
| 9z-vs-spirit-m1-overpass | 49399 | 49378 | 49378 | 49399 | 0.00 | 1.25 | lands |
| 9z-vs-spirit-m1-overpass | 49585 | 49566 | 49583 | 49585 | 265.62 | 5.23 | lands |
| 9z-vs-spirit-m1-overpass | 56155 | 56116 | 56116 | 56155 | 0.00 | 2.93 | lands |
| 9z-vs-spirit-m1-overpass | 65116 | 65096 | 65096 | 65116 | 0.00 | 2.51 | lands |
| 9z-vs-spirit-m1-overpass | 65232 | 65212 | 65218 | 65232 | 93.75 | 5.21 | lands |
| 9z-vs-spirit-m1-overpass | 75466 | 75435 | 75449 | 75466 | 218.75 | 3.00 | lands |
| 9z-vs-spirit-m1-overpass | 75782 | 75762 | 75778 | 75782 | 250.00 | 6.45 | lands |
| 9z-vs-spirit-m1-overpass | 75820 | 75792 | - | 75820 | - | 14.81 | never_landed |
| 9z-vs-spirit-m1-overpass | 75821 | 75791 | - | 75821 | - | 14.67 | never_landed |
| 9z-vs-spirit-m1-overpass | 80257 | 80233 | 80233 | 80257 | 0.00 | 1.20 | lands |
| 9z-vs-spirit-m1-overpass | 80646 | 80624 | 80636 | 80646 | 187.50 | 3.14 | lands |
| 9z-vs-spirit-m1-overpass | 80827 | 80795 | 80797 | 80827 | 31.25 | 6.86 | lands |
| 9z-vs-spirit-m1-overpass | 81067 | 81040 | 81056 | 81067 | 250.00 | 33.41 | lands |
| 9z-vs-spirit-m1-overpass | 83722 | 83698 | 83718 | 83722 | 312.50 | 4.76 | lands |
| 9z-vs-spirit-m1-overpass | 83780 | 83692 | - | 83780 | - | 5.23 | never_landed |
| 9z-vs-spirit-m1-overpass | 115130 | 115116 | 115123 | 115130 | 109.38 | 5.76 | lands |
| 9z-vs-spirit-m1-overpass | 115260 | 115207 | 115207 | 115260 | 0.00 | 1.95 | lands |
| 9z-vs-spirit-m1-overpass | 125921 | 125901 | 125914 | 125921 | 203.12 | 6.93 | lands |
| 9z-vs-spirit-m1-overpass | 126064 | 126046 | 126060 | 126064 | 218.75 | 8.67 | lands |
| 9z-vs-spirit-m1-overpass | 126064 | 126037 | 126037 | 126064 | 0.00 | 1.18 | lands |
| 9z-vs-spirit-m1-overpass | 126083 | 126046 | 126060 | 126083 | 218.75 | 8.67 | lands |
| 9z-vs-spirit-m1-overpass | 133115 | 133105 | 133105 | 133115 | 0.00 | 2.66 | lands |
| 9z-vs-spirit-m1-overpass | 142835 | 142819 | - | 142835 | - | 5.72 | never_landed |
| 9z-vs-spirit-m1-overpass | 152499 | 152462 | 152488 | 152499 | 406.25 | 25.41 | lands |
| 9z-vs-spirit-m1-overpass | 155808 | 155780 | 155780 | 155808 | 0.00 | 2.04 | lands |
| 9z-vs-spirit-m1-overpass | 156181 | 156170 | 156176 | 156181 | 93.75 | 4.39 | lands |
| 9z-vs-spirit-m1-overpass | 156191 | 156169 | 156173 | 156191 | 62.50 | 4.01 | lands |
| 9z-vs-spirit-m2-dust2 | 8885 | 8867 | 8880 | 8885 | 203.12 | 8.23 | lands |
| 9z-vs-spirit-m2-dust2 | 8903 | 8862 | 8880 | 8903 | 281.25 | 14.77 | lands |
| 9z-vs-spirit-m2-dust2 | 9080 | 9052 | 9052 | 9080 | 0.00 | 2.57 | lands |
| 9z-vs-spirit-m2-dust2 | 9307 | 9279 | 9307 | 9307 | 437.50 | 16.09 | lands |
| 9z-vs-spirit-m2-dust2 | 9410 | 9387 | 9404 | 9410 | 265.62 | 6.77 | lands |
| 9z-vs-spirit-m2-dust2 | 15419 | 15257 | 15302 | 15419 | 703.12 | 32.56 | lands |
| 9z-vs-spirit-m2-dust2 | 16306 | 16272 | - | 16306 | - | 107.11 | never_landed |
| 9z-vs-spirit-m2-dust2 | 16367 | 16352 | - | 16367 | - | 6.77 | never_landed |
| 9z-vs-spirit-m2-dust2 | 22176 | 22164 | 22164 | 22176 | 0.00 | 1.10 | lands |
| 9z-vs-spirit-m2-dust2 | 22567 | 22539 | 22539 | 22567 | 0.00 | 0.45 | lands |
| 9z-vs-spirit-m2-dust2 | 27856 | - | - | 27856 | - | - | no_t0 |
| 9z-vs-spirit-m2-dust2 | 43445 | 43445 | 43445 | 43445 | 0.00 | 0.53 | lands |
| 9z-vs-spirit-m2-dust2 | 49576 | 49550 | - | 49576 | - | 15.46 | never_landed |
| 9z-vs-spirit-m2-dust2 | 58668 | 58646 | 58647 | 58668 | 15.62 | 3.05 | lands |
| 9z-vs-spirit-m2-dust2 | 58812 | 58786 | 58786 | 58812 | 0.00 | 1.73 | lands |
| 9z-vs-spirit-m2-dust2 | 59063 | - | - | 59063 | - | - | no_t0 |
| 9z-vs-spirit-m2-dust2 | 65582 | 65560 | 65560 | 65582 | 0.00 | 2.91 | lands |
| 9z-vs-spirit-m2-dust2 | 77009 | 76985 | 77007 | 77009 | 343.75 | 11.80 | lands |
| 9z-vs-spirit-m2-dust2 | 86357 | 86322 | - | 86357 | - | 14.91 | never_landed |
| 9z-vs-spirit-m2-dust2 | 86925 | 86883 | 86905 | 86925 | 343.75 | 6.24 | lands |
| 9z-vs-spirit-m2-dust2 | 87784 | 87756 | 87759 | 87784 | 46.88 | 3.81 | lands |
| 9z-vs-spirit-m2-dust2 | 87952 | 87921 | 87921 | 87952 | 0.00 | 0.49 | lands |
| 9z-vs-spirit-m2-dust2 | 89454 | 89434 | 89434 | 89454 | 0.00 | 1.42 | lands |
| 9z-vs-spirit-m2-dust2 | 94505 | 94492 | 94494 | 94505 | 31.25 | 4.60 | lands |
| 9z-vs-spirit-m2-dust2 | 94517 | 94503 | 94516 | 94517 | 203.12 | 7.76 | lands |
| 9z-vs-spirit-m2-dust2 | 94521 | 94467 | - | 94521 | - | 165.41 | never_landed |
| 9z-vs-spirit-m2-dust2 | 94524 | 94503 | 94516 | 94524 | 203.12 | 7.76 | lands |
| 9z-vs-spirit-m2-dust2 | 94824 | 94803 | 94808 | 94824 | 78.12 | 38.14 | lands |
| 9z-vs-spirit-m2-dust2 | 104454 | 104407 | 104441 | 104454 | 531.25 | 42.80 | lands |
| 9z-vs-spirit-m2-dust2 | 126153 | 126132 | 126133 | 126153 | 15.62 | 3.06 | lands |
| 9z-vs-spirit-m2-dust2 | 126212 | 126188 | 126193 | 126212 | 78.12 | 5.28 | lands |
| 9z-vs-spirit-m2-dust2 | 126406 | 126332 | 126395 | 126406 | 984.38 | 24.61 | lands |
| 9z-vs-spirit-m2-dust2 | 126596 | 126561 | 126584 | 126596 | 359.38 | 9.60 | lands |
| 9z-vs-spirit-m2-dust2 | 130274 | 130259 | 130267 | 130274 | 125.00 | 8.73 | lands |
| 9z-vs-spirit-m2-dust2 | 130373 | 130352 | 130369 | 130373 | 265.62 | 8.75 | lands |
| 9z-vs-spirit-m2-dust2 | 130404 | 130370 | 130391 | 130404 | 328.12 | 7.81 | lands |
| 9z-vs-spirit-m2-dust2 | 132003 | 131983 | 131983 | 132003 | 0.00 | 2.82 | lands |
| 9z-vs-spirit-m2-dust2 | 139158 | 139136 | 139136 | 139158 | 0.00 | 1.08 | lands |
| 9z-vs-spirit-m2-dust2 | 145296 | 145270 | 145270 | 145296 | 0.00 | 1.43 | lands |
| 9z-vs-spirit-m2-dust2 | 149198 | 149169 | 149175 | 149198 | 93.75 | 8.42 | lands |
| 9z-vs-spirit-m2-dust2 | 149329 | 149316 | 149322 | 149329 | 93.75 | 5.54 | lands |
| 9z-vs-spirit-m2-dust2 | 160943 | 160921 | - | 160943 | - | 100.17 | never_landed |
| 9z-vs-spirit-m2-dust2 | 170677 | 170588 | 170646 | 170677 | 906.25 | 17.90 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 2668 | 2642 | 2649 | 2668 | 109.38 | 9.26 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 3972 | 3581 | 3581 | 3972 | 0.00 | 0.99 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 10261 | 10237 | - | 10261 | - | 10.97 | never_landed |
| astralis-vs-spirit-m1-dust2-p1 | 13109 | 13072 | 13072 | 13109 | 0.00 | 0.35 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 15839 | 15835 | 15835 | 15839 | 0.00 | 0.42 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 16498 | 16477 | 16477 | 16498 | 0.00 | 1.44 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 22100 | 22069 | 22069 | 22100 | 0.00 | 0.99 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 24375 | 24309 | 24322 | 24375 | 203.12 | 6.84 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 24485 | 24454 | 24456 | 24485 | 31.25 | 3.09 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 32795 | 32782 | 32795 | 32795 | 203.12 | 12.20 | lands |
| astralis-vs-spirit-m1-dust2-p1 | 40933 | 40910 | - | 40933 | - | 86.19 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 6271 | 6096 | - | 6271 | - | 150.68 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 6280 | 6265 | - | 6280 | - | 12.63 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 10353 | 10334 | 10341 | 10353 | 109.38 | 3.22 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 10411 | 10381 | - | 10411 | - | 31.05 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 23050 | 23018 | 23048 | 23050 | 468.75 | 33.95 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 23311 | 23311 | - | 23311 | - | 48.68 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 30520 | 30520 | 30520 | 30520 | 0.00 | 0.83 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 39889 | 39866 | 39883 | 39889 | 265.62 | 6.29 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 51162 | 51106 | 51139 | 51162 | 515.62 | 33.30 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 51347 | 51303 | 51303 | 51347 | 0.00 | 1.24 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 52410 | 52396 | 52396 | 52410 | 0.00 | 0.13 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 53516 | 53396 | 53480 | 53516 | 1312.50 | 125.74 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 53655 | 53621 | - | 53655 | - | 68.19 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 72327 | 72321 | - | 72327 | - | 36.44 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 72333 | 72323 | - | 72333 | - | 20.83 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 72383 | 72321 | - | 72383 | - | 36.44 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 72383 | 72323 | 72343 | 72383 | 312.50 | 20.83 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 72402 | 72321 | - | 72402 | - | 36.44 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 83357 | 83334 | 83356 | 83357 | 343.75 | 5.52 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 90515 | 90324 | 90346 | 90515 | 343.75 | 3.29 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 106478 | 106457 | - | 106478 | - | 8.19 | never_landed |
| astralis-vs-spirit-m1-dust2-p2 | 114598 | 114579 | 114579 | 114598 | 0.00 | 2.71 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 114668 | 114638 | 114643 | 114668 | 78.12 | 6.03 | lands |
| astralis-vs-spirit-m1-dust2-p2 | 119622 | 119594 | 119599 | 119622 | 78.12 | 5.19 | lands |
| astralis-vs-spirit-m2-ancient | 5742 | 5715 | 5728 | 5742 | 203.12 | 8.72 | lands |
| astralis-vs-spirit-m2-ancient | 6618 | 6596 | 6596 | 6618 | 0.00 | 1.85 | lands |
| astralis-vs-spirit-m2-ancient | 7572 | 7532 | - | 7572 | - | 179.62 | never_landed |
| astralis-vs-spirit-m2-ancient | 10510 | 10489 | - | 10510 | - | 18.31 | never_landed |
| astralis-vs-spirit-m2-ancient | 10514 | 10474 | 10475 | 10514 | 15.62 | 3.05 | lands |
| astralis-vs-spirit-m2-ancient | 10517 | 10489 | - | 10517 | - | 18.31 | never_landed |
| astralis-vs-spirit-m2-ancient | 10520 | 10474 | 10475 | 10520 | 15.62 | 3.05 | lands |
| astralis-vs-spirit-m2-ancient | 10536 | 10489 | - | 10536 | - | 18.31 | never_landed |
| astralis-vs-spirit-m2-ancient | 14568 | 14510 | 14529 | 14568 | 296.88 | 6.77 | lands |
| astralis-vs-spirit-m2-ancient | 17701 | 17682 | 17682 | 17701 | 0.00 | 2.25 | lands |
| astralis-vs-spirit-m2-ancient | 25329 | 25306 | 25309 | 25329 | 46.88 | 4.05 | lands |
| astralis-vs-spirit-m2-ancient | 25342 | 25314 | 25314 | 25342 | 0.00 | 1.57 | lands |
| astralis-vs-spirit-m2-ancient | 33540 | 33495 | 33495 | 33540 | 0.00 | 0.77 | lands |
| astralis-vs-spirit-m2-ancient | 33578 | 33557 | - | 33578 | - | 9.88 | never_landed |
| astralis-vs-spirit-m2-ancient | 36584 | 36481 | 36481 | 36584 | 0.00 | 2.89 | lands |
| astralis-vs-spirit-m2-ancient | 43281 | 43275 | - | 43281 | - | 0.52 | never_landed |
| astralis-vs-spirit-m2-ancient | 43375 | 43355 | 43362 | 43375 | 109.38 | 4.99 | lands |
| astralis-vs-spirit-m2-ancient | 56105 | 56084 | 56084 | 56105 | 0.00 | 2.44 | lands |
| astralis-vs-spirit-m2-ancient | 62476 | 62451 | 62451 | 62476 | 0.00 | 2.29 | lands |
| astralis-vs-spirit-m2-ancient | 62526 | 62499 | 62500 | 62526 | 15.62 | 3.04 | lands |
| astralis-vs-spirit-m2-ancient | 65780 | 65517 | - | 65780 | - | 17.27 | never_landed |
| astralis-vs-spirit-m2-ancient | 71204 | 71181 | 71184 | 71204 | 46.88 | 3.76 | lands |
| astralis-vs-spirit-m2-ancient | 79665 | 79648 | - | 79665 | - | 58.25 | never_landed |
| astralis-vs-spirit-m2-ancient | 79794 | 79703 | 79704 | 79794 | 15.62 | 4.65 | lands |
| astralis-vs-spirit-m2-ancient | 87673 | 87651 | 87653 | 87673 | 31.25 | 3.29 | lands |
| astralis-vs-spirit-m2-ancient | 87935 | 87801 | 87801 | 87935 | 0.00 | 1.77 | lands |
| astralis-vs-spirit-m2-ancient | 107130 | 107108 | 107115 | 107130 | 109.38 | 6.41 | lands |
| astralis-vs-spirit-m2-ancient | 111519 | 111493 | 111493 | 111519 | 0.00 | 2.38 | lands |
| astralis-vs-spirit-m2-ancient | 117841 | 117819 | 117819 | 117841 | 0.00 | 2.57 | lands |
| astralis-vs-spirit-m2-ancient | 117872 | 117862 | - | 117872 | - | 7.65 | never_landed |
| astralis-vs-spirit-m2-ancient | 118658 | 118637 | 118637 | 118658 | 0.00 | 0.75 | lands |
| astralis-vs-spirit-m2-ancient | 122606 | 122585 | 122585 | 122606 | 0.00 | 2.79 | lands |
| astralis-vs-spirit-m2-ancient | 128374 | 128359 | 128359 | 128374 | 0.00 | 2.76 | lands |
| astralis-vs-spirit-m2-ancient | 131193 | 131171 | 131171 | 131193 | 0.00 | 2.44 | lands |
| astralis-vs-spirit-m2-ancient | 143502 | 143387 | 143387 | 143502 | 0.00 | 1.93 | lands |
| astralis-vs-spirit-m2-ancient | 145438 | 145402 | 145402 | 145438 | 0.00 | 2.77 | lands |
| astralis-vs-spirit-m2-ancient | 151525 | 151477 | 151515 | 151525 | 593.75 | 41.59 | lands |

---

## 5. Anomaly Buckets

### (a) b5-class impossible rows: t1=t0+1 AND angle > 2*TARGET_REACHED_THRESHOLD (6.0 deg)

**Count: 0** (MUST be 0)


### (b) negative rt_visible_to_land_ms

**Count: 0**


### (c) per-demo median rt_visible_to_land_ms < 100ms (physiology floor flag)

| demo | median_rt_ms | n |
|-|-|-|
| 9z-vs-spirit-m1-overpass | 93.75 | 37 |
| 9z-vs-spirit-m2-dust2 | 93.75 | 35 |
| astralis-vs-spirit-m1-dust2-p1 | 0.00 | 9 |
| astralis-vs-spirit-m2-ancient | 0.00 | 28 |

### (d) tick-quantum clusters >10% (aggregate)

| quantum_ms | count | pct |
|-|-|-|
| 15.625 | 6 | 4.9% |
| 31.25 | 4 | 3.3% |
| 46.875 | 4 | 3.3% |
| 62.5 | 1 | 0.8% |

---

## 6. Random Sample (~20 rows, manual spot-check)

| demo | first_event_tick | t0_tick | t0_source | t1_tick | t1_source | rt_visible_to_land_ms | rt_visible_to_hit_ms | crosshair_angle_at_t0_deg |
|-|-|-|-|-|-|-|-|-|
| 9z-vs-spirit-m2-dust2 | 77009 | 76985 | BVH+AABB | 77007 | lands | 343.75 | 375.00 | 11.80 |
| 9z-vs-spirit-m1-overpass | 10274 | 10254 | BVH+AABB | 10261 | lands | 109.38 | 312.50 | 7.81 |
| astralis-vs-spirit-m2-ancient | 56105 | 56084 | BVH+AABB | 56084 | lands | 0.00 | 328.12 | 2.44 |
| 9z-vs-spirit-m2-dust2 | 58668 | 58646 | BVH+AABB | 58647 | lands | 15.62 | 343.75 | 3.05 |
| astralis-vs-spirit-m2-ancient | 87935 | 87801 | BVH+AABB | 87801 | lands | 0.00 | 2093.75 | 1.77 |
| 9z-vs-spirit-m1-overpass | 155808 | 155780 | BVH+AABB | 155780 | lands | 0.00 | 437.50 | 2.04 |
| 9z-vs-spirit-m2-dust2 | 49576 | 49550 | BVH+AABB | - | never_landed | - | 406.25 | 15.46 |
| astralis-vs-spirit-m2-ancient | 43375 | 43355 | BVH+AABB | 43362 | lands | 109.38 | 312.50 | 4.99 |
| astralis-vs-spirit-m2-ancient | 62526 | 62499 | BVH+AABB | 62500 | lands | 15.62 | 421.88 | 3.04 |
| astralis-vs-spirit-m1-dust2-p1 | 40933 | 40910 | BVH+AABB | - | never_landed | - | 359.38 | 86.19 |
| 9z-vs-spirit-m2-dust2 | 149198 | 149169 | BVH+AABB | 149175 | lands | 93.75 | 453.12 | 8.42 |
| 9z-vs-spirit-m2-dust2 | 94521 | 94467 | BVH+AABB | - | never_landed | - | 843.75 | 165.41 |
| 9z-vs-spirit-m1-overpass | 115260 | 115207 | BVH+AABB | 115207 | lands | 0.00 | 828.12 | 1.95 |
| 9z-vs-spirit-m2-dust2 | 130404 | 130370 | BVH+AABB | 130391 | lands | 328.12 | 531.25 | 7.81 |
| 9z-vs-spirit-m2-dust2 | 149329 | 149316 | BVH+AABB | 149322 | lands | 93.75 | 203.12 | 5.54 |
| 9z-vs-spirit-m1-overpass | 56155 | 56116 | BVH+AABB | 56116 | lands | 0.00 | 609.38 | 2.93 |
| 9z-vs-spirit-m2-dust2 | 132003 | 131983 | BVH+AABB | 131983 | lands | 0.00 | 312.50 | 2.82 |
| 9z-vs-spirit-m1-overpass | 9609 | 9587 | BVH+AABB | 9596 | lands | 140.62 | 343.75 | 6.55 |
| astralis-vs-spirit-m2-ancient | 14568 | 14510 | BVH+AABB | 14529 | lands | 296.88 | 906.25 | 6.77 |
| astralis-vs-spirit-m1-dust2-p2 | 106478 | 106457 | BVH+AABB | - | never_landed | - | 328.12 | 8.19 |

---

## 7. Pre-vs-Post (episode counts vs OF-2 baseline, D-08)

| Metric | OF-2 baseline | Current (this stage) | Delta |
|-|-|-|-|
| won | 1428 | 1428 | 0 |
| lost | 1090 | 1090 | 0 |

Timing pass adds columns, never drops episodes (D-08). For a partial stage (N=1 or N=5), won/lost will be a SUBSET of the OF-2 baseline -- deltas are negative until N=81 completes, where deltas MUST be 0.

*Distribution of rt_visible_to_land_ms is NEW (no OF-2 baseline to compare).*

---

## Acceptance Checklist

- [ ] Section 5(a): 0 b5-class impossible rows
- [ ] Section 5(d): pinning <10% at every tick-quantum
- [ ] Section 1/3: never_landed% is plausible (2-50%)
- [ ] Section 5(c): no per-player median rt <100ms unexplained
- [ ] Section 7: episode counts unchanged vs OF-2 (only true at N=81; for N=1/N=5 confirm no episodes were DROPPED for the processed demos)
