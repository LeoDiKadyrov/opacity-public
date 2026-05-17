# CS2-DDM Methodology + Codebase Review Brief

**For:** Fresh session, Claude Opus 4.7 with max thinking.
**Goal:** Deep audit of detection methodology + all modules for systemic bugs.
**Triggered by:** 2026-05-16 discovery of `T1_GRACE_MS=120` floor bug clipping 25-43% of T0→T1 metric. Owner concerned other similar bugs lurk undetected.

---

## How to start this session

1. Read `CLAUDE.md` in repo root for tech stack + directory layout
2. Read `memory/MEMORY.md` (index) — load entries dated 2026-05-12 onward for full bug-history context
3. Especially load:
   - `memory/project_t1_grace_floor_bug_2026_05_16.md` (the trigger bug)
   - `memory/feedback_redundant_grace_filter_creates_floor_artifact_2026_05_16.md` (anti-pattern)
   - `memory/feedback_data_layer_bugs_donk_groundtruth_2026_05_14.md` (3 prior bugs from manual cross-check)
   - `memory/project_v2_discard_data_fixes_shipped_2026_05_14.md` (Bug A/B/C fix history)
4. Run pytest baseline to confirm clean starting state: `python -m pytest -p no:cov 2>&1 | tail -5`

---

## Project context (1 paragraph)

CS2 demo analysis tool. Takes a `.dem` file, identifies every duel attempt, computes **reaction time decomposition**: T0 = enemy becomes visible, T1 = player starts aiming, T2 = first registered hit. Metrics: `rt_visible_to_aim_ms` (T0→T1, perception/biology), `rt_aim_to_hit_ms` (T1→T2, mechanics), `crosshair_angle_at_t0_deg` (pre-aim quality). Visibility computed via BVH+AABB raycasting against enemy hitbox (line of sight from eye to 8 AABB corners). Tickrate 64, ms per tick = 15.625ms. Output: `engagements` table in `analytics.db` (SQLite, dual-write with CSV). Used to build per-player reports against pro benchmarks (Spirit + FaZe rosters). Public product: Djok ($5 early access, manual delivery).

---

## Module map (files to audit)

| File | Lines | Critical? | What it does |
|-|-|-|-|
| `t0_detector.py` | ~400 | YES | BVH+AABB visibility, smoke suppression, find_first_visible_enemy_in_window |
| `ddm_analyzer.py` | ~850 | YES | DDMAnalyzer pipeline orchestrator, _detect_t1 (BUG SOURCE), CSV/DB write |
| `duel_attempts.py` | ~250 | YES | DuelAttemptFinder — cluster fire ticks, derive T0 window, kill detection |
| `kill_rate_analysis.py` | medium | YES | Kill rate metric pipeline (built on duel_attempts) |
| `config.py` | ~200 | HIGH | All thresholds + window constants. **Audit every constant for redundancy + floor risk.** |
| `db_utils.py` | medium | medium | SQLite dual-write, schema management |
| `csv_utils.py` | small | medium | CSV append/dedup, match_id integrity |
| `batch_runner.py` | medium | low | ProcessPoolExecutor parallel demo processing |
| `multi_player_analyze.py` | small | low | Wrapper running pipeline for all 10 players in demo |
| `interpretation.py` | medium | low | Per-player tier/benchmark interpretation |
| `report_generator.py` | medium | low | HTML report builder with base64 charts |
| `visualize_results.py` | medium | low | matplotlib chart generation |
| `app.py` | medium | low | Streamlit dashboard |

---

## Known bugs (current + history)

### CURRENT — `T1_GRACE_MS` floor (just discovered 2026-05-16)
- **Location:** `config.py:124` (`T1_GRACE_MS = 120`) + `ddm_analyzer.py:517-518` in `_detect_t1`
- **Symptom:** 25-43% of every pro's peek engagements pinned at exactly 125ms (8 ticks × 15.625ms)
- **Cause:** Grace period is redundant with `moving_towards + sustained` filters already preventing micro-corrections at lines 562-564 + 578
- **Status:** Under-experiment as of brief-creation — testing `grace=30` vs `grace=0` on 1 demo
- **Impact:** All landing claims about donk 172ms / m0NESY 203ms reaction times suspect

### DEFERRED — Bug B peek/hold strafe-hold mis-classification (2026-05-14)
- **Symptom:** `engagement_type` derived from velocity threshold (`config._PLAYER_VELOCITY_THRESHOLD`). Strafing-hold scenarios (player holding angle while strafe-shooting, ups~165) get tagged `peek` even though angle was held
- **Files:** `ddm_analyzer.py:_classify_engagement` (line ~585)
- **Status:** TODO in code, no fix yet

### FIXED but useful context — Bug A phantom T0 through smoke (2026-05-14)
- **Was:** BVH didn't gate visibility on smoke geometry — T0 fired through dissipating smoke
- **Fix:** Smoke geometry check added (`_is_smoke_obscured` in `t0_detector.py:320`)
- **Pattern:** geometry-only visibility check missed environmental occluders. Could similar miss exist for molotov flame, world geometry edge cases, or other smoke states?

### FIXED but useful context — Bug C phantom engagement after death (2026-05-14)
- **Was:** T0Detector didn't gate on `is_alive`. Fabricated engagements for spectator/corpse view
- **Fix:** alive check added
- **Pattern:** failed to gate on player state. Are there other player-state gates missed?

### FIXED but useful context — `round_time_s` off-by-20s (2026-05-14)
- **Was:** Used `round_start` event which fires at freeze-phase begin (includes 20s buy)
- **Fix:** Now uses `round_freeze_end`
- **Pattern:** event-name semantics misunderstood. Are there other event mistreatments?

---

## Anti-patterns to hunt across codebase

These are the recurring failure modes from project history. Search each file for instances:

### 1. **Redundant filter stacking** (just learned)
- Look for: cases where 2+ filters claim to prevent the same failure mode
- Example: `T1_GRACE_MS` stacked on top of `moving_towards + sustained`
- Where else? Suspicious files: `t0_detector.py` (visibility filters), `duel_attempts.py` (window + cluster filters)

### 2. **Integer-tick floor artifacts**
- Look for: `int(some_ms / tick_ms)` or `// tick_ms` patterns that quantize time into ticks
- Distribution shape check: aggregate stats may hide pinning at exact tick multiples. ALWAYS verify min/p10 don't cluster on a single value
- SQL smell test: `SELECT COUNT(*) FROM engagements WHERE rt_x_y_ms = <suspicious_multiple_of_15.625>`

### 3. **SteamID64 precision loss**
- **Known:** `pd.read_sql` truncates float64 SteamIDs silently
- Pattern: use `cursor.fetchall()` + manual dict, NEVER `pd.read_sql` for SteamID columns
- Audit: any pandas reads of SteamID columns

### 4. **Broken upstream flags** (`m_bSpotted`, `m_bSpottedByMask`)
- Per CLAUDE.md: never populated in CS2 GOTV demos
- Audit: any reference to these flags in code

### 5. **Engagement-type derived from single proxy**
- `engagement_type` from velocity alone misses strafing-hold (Bug B)
- Pattern: any classification using single threshold without semantic check

### 6. **Event-name semantics**
- `round_start` ≠ round action begin (includes freeze)
- Audit: every demoparser event reference (`round_start`, `round_end`, `round_freeze_end`, `player_hurt`, `weapon_fire`, etc.) — verify what they ACTUALLY fire on

### 7. **Cluster/window arithmetic with cascading constants**
- `_ATTEMPT_WINDOW_BEFORE_TICKS=16` + `_ATTEMPT_WINDOW_AFTER_TICKS=32` + `_HIT_LATENCY_TICKS` — check for off-by-one + window-edge bugs

### 8. **NaN handling**
- demoparser2 0.41.2 NaN tick crash was fixed but pattern (NaN propagation through tick arithmetic) may recur
- Audit: every `int(<tick>)` cast on demo-derived value

---

## Specific files of highest concern (priority order)

1. **`ddm_analyzer.py:_detect_t1` (lines 512-583)** — the bug source. Audit all filter logic + thresholds. Recommend: derive minimum reaction time empirically OR remove grace.
2. **`ddm_analyzer.py:_classify_engagement`** — Bug B lives here, audit + propose fix
3. **`t0_detector.py:find_first_visible_enemy_in_window` (line 291)** — tick-by-tick scan, check window boundary handling
4. **`t0_detector.py:_is_smoke_obscured` (line 320)** — geometric occlusion, check edge cases (smoke entering/leaving, molotov interaction)
5. **`duel_attempts.py:DuelAttemptFinder`** — cluster derivation, window arithmetic
6. **`config.py` (all constants)** — every threshold deserves justification. Audit for: (a) is it tested? (b) what's the sensitivity analysis? (c) is it stacked redundantly with another filter?
7. **`db_utils.py`** — schema integrity, check NULL handling around NaN fields

---

## Test coverage status

- 322 tests passing as of 2026-05-15
- See `tests/` directory for module-level coverage
- Specifically check:
  - `test_t0_detector_first_visible_window.py` — does it test the 8-tick floor case? (probably not — that's the bug)
  - `test_ddm_analyzer_t1.py` — does it test `_detect_t1` for known reaction-time floor behaviour?
- **High-value missing test class:** distribution-shape regression tests. Should fail if aggregate output is pinning on tick-quantum values.

---

## Method requested

1. **Module-by-module audit** in priority order above
2. **Anti-pattern hunt across all files** — grep for each of the 8 anti-patterns
3. **Distribution-shape spec** — propose a regression test suite that catches floor/ceiling artifacts in metric distributions
4. **Constant justification table** — for every threshold in `config.py`, document: rationale, redundancy check, sensitivity. Flag any without justification.
5. **Output format:** structured findings file like `REVIEW-2026-05-16.md` with sections per file + severity (BLOCKER / WARN / INFO) per finding.

---

## Output expectations

Single self-contained markdown file. Format reference: `.planning/phases/v2-interpretation-narrative/REVIEW-2026-05-14.md` (from prior code-review cycle). Severity classification + remediation guidance per finding.

After review, owner will triage findings → fix → re-batch → ship corrections publicly (community-trust angle, per `project_t1_grace_floor_bug_2026_05_16.md`).

---

## Background context user wants reviewer to know

- This is a solo project (year of dev).
- Public product positioning: trust-through-specificity. Bugs that survive to production damage that positioning more than they damage technical correctness.
- Code quality bar: production-grade for measurement layer (T0/T1/T2/visibility), pragmatic for reporting/UI layer.
- Owner has manual-demo audit habit and welcomes findings — this is not adversarial review.
- Reddit user `shimszy` flagged the T1 floor critique indirectly. Public fix-and-credit is the planned response.
