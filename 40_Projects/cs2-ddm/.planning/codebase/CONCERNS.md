# Codebase Concerns

**Analysis Date:** 2026-04-30

## Summary

Post-merge state: kill-rate-normalization is in main. Core risks are NaN crash regression in duel_attempts.py, duplicated velocity logic, hardcoded paths, and three unresolved edge cases deferred to Phase 6.

## Known Edge Cases (Phase 6 to fix)

1. **T0 > T2 — flash suppression delays BVH**: Hit occurs during flash → BVH finds T0 after flash ends → T0 > hit_tick → "no hit in window" rejection. **Current behavior correct.** No fix needed.

2. **Overlapping search windows — duplicate enemy**: Two engagements < 300 ticks apart → second moment's auto-discovery picks first engagement's enemy. Fix: minimum gap check — reject if `first_hit_tick < prev_accepted_T2 + 300`.

3. **T0 = search_start outlier inflation**: BVH finds T0 = search_start → enemy was visible before lookback window → inflates RT (seen: 4688ms). Fix: reject if `t0_tick < search_start + 20`.

## Tech Debt

- **Hardcoded demo paths** in `kill_rate_analysis.py` (`PLAYERS` dict, `_DEMO_BASE`). No CLI arg for paths — must edit source to add a player.
- **Duplicated velocity logic**: `_player_velocity()` exists in both `ddm_analyzer.py` and `duel_attempts.py`. Should be in `config.py` or a shared util.
- **BVH mesh loaded per-instance**: `T0Detector.__init__` loads `.tri` file every time. No caching across multiple demo analyses for same map.
- **`cluster_gap_ticks` changed 320→128** (Phase 5b fix) but `auto_build_moments()` still defaults `cluster_gap_ticks=320` — inconsistency between DDMAnalyzer and DuelAttemptFinder defaults.

## Missing Features / TODO

- **Phase 6**: T0 offset quality gate — fixes edge cases 2 and 3 above.
- **`hurt_victims_in_window`** field populated but not surfaced in dashboard or CSV output — diagnostic only.
- **No dedup in DuelAttemptFinder**: if same match processed twice, duplicate attempts accumulate in `*_attempts.csv`.
- **No per-round kill rate**: current kill rate is match-level aggregate; round-phase breakdown not implemented.
- **Player registry in kill_rate_analysis.py**: hardcoded, not config-driven. Adding a player requires code edit.

## Fragile Areas

- **NaN tick crash** (`duel_attempts.py:106, 249`): demoparser2 0.41.2 returns NaN for some ticks. Fixed with `pd.isna()` checks. High regression risk if demoparser2 is upgraded again without re-testing these lines.
- **Silent `.tri` file failure**: if mesh file missing for a map, `VisibilityChecker` may raise or return wrong results — no explicit guard.
- **Flash interval parsing**: relies on `player_blind` events in demo data. If Valve changes event schema, flash suppression silently breaks.
- **`parse_header()['map_name']`**: assumes key exists. No fallback if demo header is malformed.

## Performance Risks

- **O(N) BVH scan per tick**: `find_t0()` iterates tick-by-tick calling `is_visible()`. For 8-second windows at 64 tick = 512 BVH calls × 8 corners = 4096 ray-triangle tests per engagement.
- **Repeated DataFrame filter**: `_player_velocity()` filters `all_ticks_df` on every call. Pre-slicing (already done in `find_first_visible_enemy_in_window`) should be applied consistently.
- **No parallelism in bulk pipeline**: `analyze_demo()` processes moments sequentially. Multiple demos analyzed sequentially in `kill_rate_analysis.py`.

## Dependency Risks

- **demoparser2**: upgraded 0.41.1→0.41.2 for CS2 patch 14155. Each CS2 update may require another upgrade. Breaking changes possible.
- **awpy 2.0.2**: installed with `--ignore-requires-python` (Python 3.14 not officially supported). May break on awpy or Python updates.
