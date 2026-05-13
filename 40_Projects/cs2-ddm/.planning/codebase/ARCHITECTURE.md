# Architecture

_Generated: 2026-04-30_
_Focus: arch_

## Summary

Two independent analysis pipelines share a common data-parsing layer (`DDMAnalyzer.analyze_demo`) and BVH visibility engine (`T0Detector`). Pipeline 1 produces per-engagement RT metrics. Pipeline 2 produces T0-anchored kill-rate stats that include misses.

## Two-Path Pipeline

```
demo (.dem)
    |
    v
DDMAnalyzer.analyze_demo()          [ddm_analyzer.py]
    |  demoparser2: parse_ticks, parse_event
    |
    +--- PATH 1: RT Analysis (bulk_mode=True) ---
    |       auto_build_moments() → cluster player_hurt → AnalysisMoment list
    |       analyze_engagement_episode() per-moment:
    |           _resolve_t0()        BVH T0 via T0Detector.find_t0()
    |           _find_t2()           first player_hurt after T0
    |           _detect_t1()         sustained-aim detection
    |           is_1v1_duel()        third-party filter
    |           _compute_velocity()  player + enemy XY speed at T0
    |           _compute_crosshair_angle_at_t0()
    |       results_df → csv_utils.save_results()
    |           → cs2_engagement_analysis_results.csv
    |
    +--- PATH 2: Kill Rate (attempts_mode=True) ---
            find_all_duel_attempts() → DuelAttemptFinder.find_attempts()
                _cluster_fires()     weapon_fire clusters (gap=128t, max=192t)
                _process_cluster()   per cluster:
                    T0Detector.find_first_visible_enemy_in_window()
                    _check_kill()    player_death within 320t of T0
                    _count_bullets() first 5 fires after T0 vs hurt events
                    _player_velocity()
            List[DuelAttempt] → {player}_attempts.csv
            kill_rate_analysis.print_comparison_table()
```

## Key Classes

### `DDMAnalyzer` — `ddm_analyzer.py`

Top-level orchestrator. One instance per demo file.

| Method | Role |
|-|-|
| `__init__` | Opens DemoParser, parses map name, constructs T0Detector |
| `analyze_demo(bulk_mode, attempts_mode)` | Parses all events; dispatches to Path 1 and/or Path 2 |
| `auto_build_moments()` | Converts player_hurt clusters into AnalysisMoment list |
| `analyze_engagement_episode()` | Per-moment RT pipeline orchestrator |
| `find_all_duel_attempts()` | Delegates to DuelAttemptFinder for Path 2 |
| `_resolve_t0()` | BVH scan or manual tick; enforces T0_MIN_OFFSET_TICKS gate |
| `_find_t2()` | First player_hurt after T0; rejects AWP hits |
| `_detect_t1()` | Sustained angular movement toward enemy post-T0 |
| `is_1v1_duel()` | Rejects third-party damage or multi-target hits |
| `_compute_velocity()` | XY speed via consecutive position delta × tickrate |
| `_compute_crosshair_angle_at_t0()` | Angular distance from crosshair to enemy at T0 |
| `_compute_round_phase()` | Classifies T0 as early/mid/late using round_start events |

### `T0Detector` — `t0_detector.py`

BVH-based visibility engine. One instance per map; `.tri` BVH tree loaded once, reused across all episodes.

| Method | Role |
|-|-|
| `find_t0()` | Scans tick range; returns first tick any AABB corner ray clears geometry |
| `find_first_visible_enemy_in_window()` | Earliest tick + closest enemy for a cluster window (Path 2) |
| `_is_smoke_obscured()` | Sphere intersection test against active smoke volumes |
| `parse_smoke_events()` | Static; builds smoke interval DataFrame from demoparser2 events |
| `parse_flash_intervals()` | Static; builds per-player flash-blind intervals |

### `DuelAttemptFinder` — `duel_attempts.py`

Produces `DuelAttempt` records for every weapon_fire cluster (hits and misses).

| Method | Role |
|-|-|
| `find_attempts()` | Clusters fires, processes each cluster, returns accepted attempts |
| `_cluster_fires()` | Static; gap-based + max-span split of sorted fire ticks |
| `_process_cluster()` | Per-cluster: find T0, classify kill, count bullets |
| `_check_kill()` | player_death within _KILL_CONFIRM_WINDOW_TICKS of T0 |
| `_count_bullets()` | First _BULLETS_FOR_HIT_RATE fires after T0 vs hurt latency window |

### `AnalysisMoment` — `config.py` (dataclass)

Input record for Path 1.

```python
@dataclass
class AnalysisMoment:
    timestamp: str
    manual_t0_tick_enemy_first_visible: Optional[int]
    description: str = ""
    analysis_window_seconds_after_t0: int = 5
    target_enemy_steamid_if_known: Optional[int] = None
    use_auto_t0: bool = False
    auto_t0_search_start_tick: Optional[int] = None
```

### `DuelAttempt` — `duel_attempts.py` (dataclass)

Output record for Path 2.

```python
@dataclass
class DuelAttempt:
    match_id: str
    map_name: str
    t0_tick: int
    enemy_steamid: int
    was_killed: bool
    bullets_fired: int
    bullets_hit: int
    engagement_type: str           # "peek" | "hold"
    player_velocity_ups: float
    crosshair_angle_deg: float
    hurt_victims_in_window: str    # comma-separated steamids (diagnostic)
    fires_in_cluster: int
```

## CSV Schemas

### Path 1: `cs2_engagement_analysis_results.csv`

Managed by `csv_utils.save_results()` — replace-or-append per `match_id`. Schema must stay stable.

| Column | Notes |
|-|-|
| `match_id` | Unique per demo |
| `t0_manual_tick` | Resolved T0 tick; sort key in visualize_results.py |
| `t0_source` | "BVH+AABB" or "manual" |
| `t1_aim_start_tick` | -1 → NaN when no sustained aim found |
| `t2_first_hit_tick` | First player_hurt tick after T0 |
| `rt_visible_to_aim_ms` | (T1-T0) × ms_per_tick |
| `rt_aim_to_hit_ms` | (T2-T1) × ms_per_tick |
| `rt_visible_to_hit_ms` | (T2-T0) × ms_per_tick |
| `player_velocity_at_t0_ups` | XY speed in Source engine units/sec |
| `enemy_velocity_at_t0_ups` | Same for target enemy |
| `engagement_type` | "peek" (≥50 u/s) or "hold" |
| `crosshair_angle_at_t0_deg` | Angular distance crosshair→enemy at T0 |
| `round_phase` | "early" (<40s), "mid" (<70s), "late" |

### Path 2: `{player}_attempts.csv`

Columns match `DuelAttempt` dataclass fields. Written by `kill_rate_analysis.save_attempts()`.

| Column | Notes |
|-|-|
| `was_killed` | player_death confirmed within 320 ticks of T0 |
| `bullets_fired` | First 5 fire events at/after T0 |
| `bullets_hit` | Of those, registered a hurt within 4 ticks |
| `hurt_victims_in_window` | All hurt targets in cluster window (diagnostic) |

## Architectural Constraints

- **BVH-only T0**: `m_bSpotted`/`m_bSpottedByMask` never populated in CS2 GOTV demos. FOV-only always fails for peek scenarios. BVH+AABB is the only correct method.
- **Tickrate fixed at 64**: `ms_per_tick = 15.625ms`. No dynamic detection.
- **T0 boundary gate**: T0 within 20 ticks of `search_start` rejected — enemy was already visible before lookback window.
- **AWP exclusion**: AWP, Scout, auto-snipers rejected at `auto_build_moments()` and `_find_t2()`.
- **Enemy velocity gate** (`ENEMY_VELOCITY_HOLD_THRESHOLD_UPS = 120 u/s`): Episode rejected if enemy moving at T0.
- **Velocity is derived**: demoparser2 doesn't expose `vel_x`/`vel_y`. Velocity = `sqrt(dx²+dy²) × tickrate` from consecutive X/Y position rows.
- **Single-threaded**: Tick-by-tick BVH scan in `find_t0()` is primary runtime cost.

## Anti-Patterns

**FOV cone for T0**: Enemy behind wall still inside cone → false-positive T0 50-200ms early. Use `T0Detector.find_t0()`.

**Reading `m_bSpotted`**: Always zero in CS2 GOTV demos. Use BVH only.

**Video timestamps for tick numbers in late rounds**: Drifts by hundreds of ticks. Anchor to `player_hurt` event ticks from demoparser2.

**Combining Path 1 and Path 2 data**: Path 1 applies strict 1v1 quality filters; Path 2 includes all attempts. Populations are not comparable.
