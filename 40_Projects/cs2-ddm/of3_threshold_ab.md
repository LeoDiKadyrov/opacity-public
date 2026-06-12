# OF-3-02 D-02 Threshold A/B Comparison

Demo: `spirit-vs-the-mongolz-m2-ancient.dem` (donk, 76561198386265483)

| Metric | Fixed 3.0deg | Distance-scaled |
|-|-|-|
| n episodes | 80 | 80 |
| n resolved (t1_source=lands) | 62 | 57 |
| %@tick-quantum pinning | 3.2% | 10.5% |
| min rt_visible_to_land_ms | 0.0 | 0.0 |
| p10 rt_visible_to_land_ms | 0.0 | 31.25 |
| never_landed% | 21.2% | 27.5% |
| n b5-class impossible rows | 0 | 0 |

## Decision rule (locked, D-02)
KEEP fixed 3.0 UNLESS fixed produces >10% pinning OR >10 impossible rows that distance-scaling resolves.
