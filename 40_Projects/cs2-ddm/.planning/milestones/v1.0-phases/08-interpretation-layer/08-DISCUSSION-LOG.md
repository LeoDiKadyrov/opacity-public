# Phase 8: Interpretation Layer — Discussion Log

**Date:** 2026-05-06
**Areas discussed:** Report location, Tier thresholds, Drill content, Benchmark player

---

## Area 1: Report Location

| Question | Options presented | Decision |
|-|-|-|
| Where does interpretation output live? | New tab / Inline below Results / Separate module | New tab in app.py |
| Top-of-page layout? | Summary card first / Full table first / You decide | Summary card first (SC2 punchline visible immediately) |
| How does user select which player? | Sidebar SteamID / Dropdown in tab | Sidebar SteamID (same as analysis config) |
| Works before full dataset? | Any data + warning / Block until N demos / You decide | Works with any data; fallback + warning when <20 demos |

**Notes:** User asked about downloadable reports — captured as deferred (Phase 9 SC3 scope).

---

## Area 2: Tier Thresholds

| Question | Options presented | Decision |
|-|-|-|
| How are tiers calculated? | Percentile from donk / Hard-coded / Hybrid | User redirected to multi-player: percentile from SELECTED benchmark |
| Tiers per benchmark player — method? | Percentile on-the-fly / Fixed per player / You decide | Percentile from selected player's distribution |
| Fallback when sample too small? | Warning + estimates / Block / You decide | Warning + hard-coded estimates |
| Per engagement_type or combined? | Separately peek/hold / Combined | Separately (SC3 alignment) |

---

## Area 3: Drill Content

| Question | Options presented | Decision |
|-|-|-|
| Form of drill recommendations? | Hard-coded text / Workshop map refs / Admin UI | Hard-coded text dict in interpretation.py |
| How many drills per cell? | One primary / 2-3 with priority | One primary drill per metric+tier |
| Which metrics get drills? | 4 from SC1 + RT components / Add hit_rate too | 5 metrics: crosshair_angle, rt_visible_to_aim, rt_aim_to_hit, kill_rate, hit_rate |

**Notes:** User asked about metric ↔ outcome correlation — captured as deferred (new analytical capability).

---

## Area 4: Benchmark Player

| Question | Options presented | Decision |
|-|-|-|
| Where does dropdown live? | In Interpretation tab / In sidebar | In Interpretation tab |
| Minimum N for reliable tiers? | 20 demos / 10 demos | 20 demos; below = "(small sample)" label |
| How to display players? | SteamID + count / PLAYER_NAMES dict | PLAYER_NAMES dict in config.py |

---

## Deferred Ideas

| Idea | Reason deferred |
|-|-|
| Downloadable reports (PDF/HTML) | Phase 9 SC3 |
| Metric ↔ engagement outcome correlation | New capability — future phase |
| FACEIT-level cohort comparison | Requires FACEIT API — Phase 9+ |
| Weapon type split in interpretation | Phase 8 scope full; consider Phase 9 |
| round_phase breakdown | Insufficient signal at current scale |

---

## Claude's Discretion Items

- Exact percentile breakpoints (quartile vs quintile split)
- `interpretation.py` internal structure
- Specific drill text per metric+tier
- Hard-coded fallback threshold values per metric
