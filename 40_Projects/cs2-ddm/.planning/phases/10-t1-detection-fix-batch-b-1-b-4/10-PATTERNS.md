# Phase 10: T1 detection fix batch (B-1 + B-4) — Pattern Map

**Mapped:** 2026-05-16
**Files analyzed:** 5 (4 modified Python files + 1 new frozen artifact)
**Analogs found:** 5 / 5 (all in-repo — single-project codebase, no cross-file analogs needed)

All five touched files have strong same-file analogs because Phase 10 is a surgical correctness fix on an existing pipeline. Every pattern below is sourced from the file being modified (or a sibling test file) so the planner can copy verbatim with line citations.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-|-|-|-|-|
| `config.py` | config | request-response (constant emit) | Same file, lines 92-105 (`T0_TO_T2_MAX_TICKS`) | exact (same constant block) |
| `ddm_analyzer.py:_detect_t1` | algorithm method | transform (returns Tuple[int, str]) | Same file, lines 328-424 (`_resolve_t0`) | exact (private method, `Optional[Tuple[int, str]]` signature, same logging tag convention) |
| `db_utils.py:_migrate_schema` | migration | batch (ALTER TABLE) | Same function, lines 84-99 (6 prior migrations) | exact (idempotent tuple-list append) |
| `tests/test_ddm_analyzer_t1.py` | test | request-response (fixture+assert) | Same file, lines 39-49 (`analyzer` fixture), 52-97 (`_manual_moment`/`_hurt`/`_make_ticks` helpers) | exact (reuse existing helpers verbatim) |
| `.planning/phases/10-.../grace_experiment_pre_fix.txt` | frozen artifact | file-I/O (write-once) | None in repo — operator captures stdout of `python grace_experiment.py` | no-analog (one-shot text dump) |

**Pipeline-write of `t1_source` field** in `analyze_engagement_episode` return dict (lines 791-813) reuses the existing dict-emit pattern verbatim — no signature change to the orchestrator method, just one new key.

## Pattern Assignments

### `config.py` (constant value change + comment rewrite)

**Analog:** Same file. Look at `T0_TO_T2_MAX_TICKS` (lines 92-105) — the only constant in `config.py` with an empirical rationale + cross-reference comment. This is the bar for Phase 10's comment quality.

**Comment style pattern** (config.py:88-105):
```python
# Round-phase thresholds (seconds into the round at T0).
_ROUND_EARLY_MAX_S: float = 40.0
_ROUND_MID_MAX_S: float = 70.0

# Minimum ticks between BVH-found T0 and search_start.
# If T0 == search_start the enemy was already visible before the lookback window
# started — the true T0 is unknown and T0→T2 will be inflated.
# 20 ticks ≈ 312ms. Engagements failing this gate are not gradeable.
T0_MIN_OFFSET_TICKS: int = 20

# Maximum ticks between T0 and T2 (first hit) for an engagement to be gradeable.
# auto_build_moments groups player_hurt events into 5s clusters; if same target
# is hit twice across separate firefights (e.g. shoot → miss → enemy retreats →
# returns → hit), T2 captures the LATE hit, inflating rt_visible_to_hit and
# rt_aim_to_hit by 4–6 seconds. 96 ticks ≈ 1.5s — empirically where mean ≈ median
# (clean distribution). Engagements with T0→T2 > this cap = cluster bleed,
# ungradeable for RT but kept in raw table.
T0_TO_T2_MAX_TICKS: int = 96
```

**Current state to replace** (config.py:122-124):
```python
# Grace period after T0 before searching for T1 (reactive aim start).
# Avoids picking up pre-aim micro-corrections as T1.
T1_GRACE_MS: int = 120
```

**Target after Phase 10** (mirror `T0_TO_T2_MAX_TICKS` documentation depth — cite the audit, name the filters that replace grace, and reference the DB evidence):

```python
# T1 reactive aim search starts at T0 (grace removed 2026-05-16 — see
# .planning/REVIEW-2026-05-16.md B-1). Three semantic filters prevent
# pre-aim micro-corrections from registering as T1:
#   1. T1_MIN_ANGLE_CHANGE (0.08°) — filters jitter
#   2. moving_towards predicate — filters non-reactive corrections
#   3. T1_SUSTAINED_AIM_TICKS=2 — filters single-tick noise spikes
# Adding a structural grace on top creates a hard 8-tick (125ms) floor on
# the metric. 1145 engagements pinned at exactly that value pre-fix.
T1_GRACE_MS: int = 0
```

**Why keep the constant (instead of removing it):** RESEARCH.md Pattern 1 — keeps `grace_ticks = int(0/15.625) = 0` plumbing intact so future re-experimentation (raising `T1_SUSTAINED_AIM_TICKS` to 3 then trying small grace) doesn't require an algorithm edit.

**Note on adjacent T1 constants** (config.py:126-137): Phase 10 does NOT touch `T1_SUSTAINED_AIM_TICKS`, `T1_MIN_ANGLE_CHANGE`, `T1_NOT_AIMED_THRESHOLD`, or `T1_MOVING_TOWARDS_TOLERANCE`. RESEARCH.md "Anti-Patterns to Avoid" is explicit: those are Phase B (W-3, W-4).

---

### `ddm_analyzer.py:_detect_t1` (algorithm change + signature change to `Tuple[int, str]`)

**Analog:** Same file, `_resolve_t0` at lines 328-424. This method returns `Optional[Tuple[int, str]]` — exactly the signature shape the planner needs. The planner can copy the destructuring pattern at the caller (line 671) verbatim.

**Existing analog signature** (ddm_analyzer.py:328-334):
```python
def _resolve_t0(
    self, moment_info: AnalysisMoment, all_ticks_df: pd.DataFrame,
    all_player_hurt_events_df: pd.DataFrame,
    smoke_events: Optional[pd.DataFrame], tag: str,
    ticks_by_sid: Optional[Dict[int, pd.DataFrame]] = None,
) -> Optional[Tuple[int, str]]:
    """Resolve T0 from manual tick or BVH auto-detection. Returns (t0_tick, source) or None."""
```

**Existing analog return-tuple pattern** (ddm_analyzer.py:405-424 — multiple return paths, all returning the tuple shape consistently):
```python
if auto_t0 is not None:
    t0_tick = auto_t0
    t0_source = method
    self.logger.info(f"{tag} Auto T0={t0_tick}, source={t0_source}")
    offset = t0_tick - search_start
    if offset < T0_MIN_OFFSET_TICKS:
        self.logger.warning(
            f"{tag} REJECTED — T0 at search_start boundary "
            f"(offset={offset} ticks < {T0_MIN_OFFSET_TICKS})"
        )
        return None
else:
    self.logger.warning(f"{tag} REJECTED — BVH: {method}")
    return None

if t0_tick is None:
    self.logger.warning(f"{tag} REJECTED — no T0 available (manual not set, auto disabled).")
    return None

return (t0_tick, t0_source)
```

**Existing analog destructuring at caller** (ddm_analyzer.py:665-671):
```python
result = self._resolve_t0(
    moment_info, all_ticks_df, all_player_hurt_events_df, smoke_events, tag,
    ticks_by_sid=ticks_by_sid,
)
if result is None:
    return None
t0_tick, t0_source = result
```

**Current `_detect_t1` signature to change** (ddm_analyzer.py:512-516):
```python
def _detect_t1(
    self, t0_tick: int, t2_tick: int, target_enemy_id: str,
    all_ticks_df: pd.DataFrame, tag: str,
) -> int:
    """Search for sustained aim toward target. Returns t1_tick or -1."""
```

**Target signature after Phase 10** (planner: mirror `_resolve_t0`):
```python
def _detect_t1(
    self, t0_tick: int, t2_tick: int, target_enemy_id: str,
    all_ticks_df: pd.DataFrame, tag: str,
) -> Tuple[int, str]:
    """Search for T1 (sustained aim start). Returns (t1_tick, t1_source).

    Returns (-1, "none") on no-detection. Source ∈ {"sustained_aim", "pre_aimed", "none"}.
    Pre-aim branch (B-4 fix, 2026-05-16): when player crosshair is already
    within T1_NOT_AIMED_THRESHOLD of enemy at T0 sustained for
    T1_SUSTAINED_AIM_TICKS ticks → return (t0_tick, "pre_aimed").
    """
```

**Existing core algorithm pattern (lines 530-580 — preserve verbatim):**
```python
consecutive = 0
potential_t1 = -1
for i in range(len(player_aim_ticks) - 1):
    curr = player_aim_ticks.iloc[i]
    nxt = player_aim_ticks.iloc[i + 1]

    enemy_at_tick = all_ticks_df[
        (all_ticks_df["tick"] == curr["tick"])
        & (all_ticks_df["steamid"] == int(target_enemy_id))
    ]
    if enemy_at_tick.empty:
        consecutive = 0
        continue

    e = enemy_at_tick.iloc[0]
    des_p, des_y = self.get_desired_angles(
        curr["X"], curr["Y"], curr["Z"],
        e["X"], e["Y"], e["Z"],
    )

    d_yaw   = abs(self.angular_diff(curr["yaw"], nxt["yaw"]))
    d_pitch = abs(self.angular_diff(curr["pitch"], nxt["pitch"]))
    sig_change = d_yaw > T1_MIN_ANGLE_CHANGE or d_pitch > T1_MIN_ANGLE_CHANGE

    curr_dist = math.hypot(
        self.angular_diff(curr["yaw"], des_y),
        self.angular_diff(curr["pitch"], des_p),
    )
    nxt_dist = math.hypot(
        self.angular_diff(nxt["yaw"], des_y),
        self.angular_diff(nxt["pitch"], des_p),
    )
    moving_towards = nxt_dist < (curr_dist - T1_MOVING_TOWARDS_TOLERANCE)

    if sig_change and moving_towards and curr_dist > T1_NOT_AIMED_THRESHOLD:
        if consecutive == 0:
            potential_t1 = int(nxt["tick"])
        consecutive += 1
    else:
        consecutive = 0
        potential_t1 = -1

    if self.debug_prints:
        self.logger.debug(
            f"  Tick {int(curr['tick'])}: dYaw={d_yaw:.4f} dPitch={d_pitch:.4f} "
            f"sig={sig_change} towards={moving_towards} dist={curr_dist:.2f}"
        )

    if consecutive >= T1_SUSTAINED_AIM_TICKS:
        self.logger.info(f"{tag} T1={potential_t1} (after {consecutive} aim ticks)")
        return potential_t1  # → CHANGE to: return potential_t1, "sustained_aim"
```

**Existing sentinel returns to update** (ddm_analyzer.py:527-528, 582-583):
```python
if len(player_aim_ticks) < 2:
    self.logger.warning(f"{tag} T1 not found — no sustained aiming detected.")
    return -1                # → CHANGE to: return -1, "none"

# ...

self.logger.warning(f"{tag} T1 not found — no sustained aiming detected.")
return -1                    # → CHANGE to: return -1, "none"
```

**Imports to reuse** (ddm_analyzer.py:1-42 — already imports `math`, `Tuple`, all T1 constants). The pre-aim branch needs zero new imports.

**Pre-aim block insertion point** — directly after `aim_search_start = t0_tick + grace_ticks` (line 518), before the `player_aim_ticks` DataFrame slice. The pre-aim block reuses the existing `get_desired_angles` (lines 105-117) and `angular_diff` (lines 119-122) helpers — both are static methods on the same class.

**Math helper invocation pattern** (matches existing usage at lines 545-561):
```python
des_p, des_y = self.get_desired_angles(
    r["X"], r["Y"], r["Z"],
    e["X"], e["Y"], e["Z"],
)
dist = math.hypot(
    self.angular_diff(r["yaw"], des_y),
    self.angular_diff(r["pitch"], des_p),
)
```

**Logging tag convention** (matches existing T1 detection logs at lines 527, 579, 582):
```python
self.logger.info(f"{tag} T1={t0_tick} (pre_aimed)")  # success branch
self.logger.warning(f"{tag} T1 not found — ...")     # failure branch
```

---

### `db_utils.py:_migrate_schema` (ALTER TABLE addition — 1 line)

**Analog:** Same function. The pattern is fully idempotent and has 6 prior identical applications (lines 85-96).

**Existing migration pattern** (db_utils.py:84-99):
```python
cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
_eng_migrations = [
    ("demo_name", "TEXT DEFAULT NULL"),
    ("player_steamid", "INTEGER DEFAULT NULL"),
    ("map_name", "TEXT DEFAULT NULL"),
    ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
    ("round_time_s", "REAL DEFAULT NULL"),
    ("round_phase", "TEXT DEFAULT NULL"),
    # Phase v2-interpretation-narrative D-01: per-engagement attribution.
    # Backfilled for existing rows via scripts/backfill_round_number.py
    # (operator-run gate, NOT CI). 1-indexed; NULL for warmup engagements.
    ("round_number", "INTEGER DEFAULT NULL"),
]
for col, col_def in _eng_migrations:
    if col not in cols:
        conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
```

**Phase 10 addition** (mirror the comment depth of the `round_number` entry — cite the REVIEW and explain the {sustained_aim, pre_aimed, none} domain):

```python
_eng_migrations = [
    ("demo_name", "TEXT DEFAULT NULL"),
    ("player_steamid", "INTEGER DEFAULT NULL"),
    ("map_name", "TEXT DEFAULT NULL"),
    ("crosshair_angle_at_t0_deg", "REAL DEFAULT NULL"),
    ("round_time_s", "REAL DEFAULT NULL"),
    ("round_phase", "TEXT DEFAULT NULL"),
    ("round_number", "INTEGER DEFAULT NULL"),
    # Phase 10 (2026-05-16, REVIEW B-4): per-engagement T1-detection branch.
    # Values ∈ {"sustained_aim", "pre_aimed", "none"} for new rows.
    # NULL on legacy (pre-Phase-10) rows — interpret as "sustained_aim under
    # old grace=120 algorithm". Distinguishes pre-aim engagements (rt_t0_t1=0)
    # from sustained-aim engagements so chart can split or pool.
    ("t1_source", "TEXT DEFAULT NULL"),
]
```

**Why idempotent ALTER TABLE pattern is safe:** The `if col not in cols` guard handles re-running `init_db()` after the fix. Existing rows get `NULL` (interpreted as legacy). No backfill needed in Phase 10 — re-batch (Phase A item 6) regenerates from raw demos with the new branch labels.

---

### `tests/test_ddm_analyzer_t1.py` (rewrite 2 tests + add 3 new)

**Analog:** Same file. The existing helpers (`_make_ticks`, `_manual_moment`, `_hurt`, `_aim_rows_*`) are reusable verbatim for both rewrites and new tests. The planner copies the helper invocation pattern from existing tests.

**Existing helpers to reuse without modification** (test_ddm_analyzer_t1.py:39-97):

`analyzer` fixture (lines 39-49):
```python
@pytest.fixture
def analyzer():
    with patch("ddm_analyzer.DemoParser"):
        a = DDMAnalyzer(
            demo_path="fake.dem",
            player_steamid=PLAYER_ID,
            match_id="t1_test",
            debug_prints=False,
        )
    a.t0_detector = None
    return a
```

`_manual_moment()` (lines 52-59):
```python
def _manual_moment(t0=T0, window_sec=5):
    return AnalysisMoment(
        timestamp="0:15",
        manual_t0_tick_enemy_first_visible=t0,
        description="t1_test",
        analysis_window_seconds_after_t0=window_sec,
        use_auto_t0=False,
    )
```

`_hurt()` (lines 62-69):
```python
def _hurt(t2=T2):
    """One clean hit by player on enemy at T2."""
    return pd.DataFrame({
        "tick":             [t2],
        "attacker_steamid": [str(PLAYER_ID)],
        "user_steamid":     [str(ENEMY_ID)],
        "weapon":           ["ak47"],
    })
```

`_make_ticks()` (lines 72-97) — full signature reused; new tests pass different `player_aim_rows`.

**Existing `_aim_rows_already_aimed()` helper** (lines 121-129) — already returns the exact data shape Phase 10's pre-aim test needs:
```python
def _aim_rows_already_aimed():
    """
    Player already looking at enemy (dist < T1_NOT_AIMED_THRESHOLD=1.0°).
    Even with movement, the 'curr_dist > threshold' check fails → T1 not found.
    """
    base = T0 + 10
    return [(base,   0.5, 0.3),   # dist = hypot(0.5,0.3) ≈ 0.58 < 1.0
            (base+1, 0.3, 0.2),
            (base+2, 0.1, 0.1)]
```

Phase 10 reuses this helper unchanged — its semantic was "censored to NaN" pre-fix; post-fix it becomes "pre-aim T1=T0". The docstring on the helper should be updated to reflect the new semantics, but no aim rows change.

**Existing assertion pattern for "T1 found"** (lines 158-167) — Phase 10 mirrors this exactly for the new pre-aim positive test:
```python
def test_t1_found_returns_tick(self, analyzer):
    """Sustained aim toward enemy → T1 tick is detected and returned."""
    ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert not math.isnan(result["t1_aim_start_tick"])
    assert int(result["t1_aim_start_tick"]) == T0 + 11
```

**Existing rt_visible_to_aim_ms assertion pattern** (lines 168-176):
```python
def test_t1_found_rt_visible_to_aim_ms(self, analyzer):
    """RT(T0→T1) = (T1 - T0) × ms_per_tick."""
    ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    expected_ms = (T0 + 11 - T0) * (1000.0 / TICKRATE)
    assert abs(result["rt_visible_to_aim_ms"] - expected_ms) < 0.1
```

**Test 1: REWRITE `test_t1_not_found_already_aimed_at_enemy`** (currently lines 241-249) → assert pre-aim success with `t1_source='pre_aimed'`:

```python
# Rewrite — new name + new assertions, helper unchanged
def test_t1_pre_aimed_returns_t0_with_source_flag(self, analyzer):
    """B-4 fix: player already aimed at enemy at T0 → T1=T0, source='pre_aimed'."""
    ticks = _make_ticks(player_aim_rows=_aim_rows_already_aimed())
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert int(result["t1_aim_start_tick"]) == T0
    assert result["t1_source"] == "pre_aimed"
    assert result["rt_visible_to_aim_ms"] == 0.0
```

**Test 2: REWRITE `test_t1_grace_period_excludes_early_ticks`** (currently lines 291-305) — `GRACE_TICKS = 0` post-fix, so the test's `before_grace = T0 + 0 - 2 = T0 - 2` is before T0 entirely. Replace with a test asserting grace-removed pass-through:

```python
# Rewrite — qualifying aim ticks just after T0 now feed sustained-aim loop
def test_t1_no_grace_early_aim_passes_through(self, analyzer):
    """B-1 fix: T1_GRACE_MS=0 → aim ticks at T0+1, T0+2, T0+3 feed sustained-aim loop."""
    # 3 ticks immediately after T0 with same dist-decrease shape as _aim_rows_t1_found
    aim_rows = [
        (T0 + 1, 30.0, 5.0),
        (T0 + 2, 20.0, 3.0),
        (T0 + 3, 12.0, 1.5),
    ]
    ticks = _make_ticks(player_aim_rows=aim_rows)
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert not math.isnan(result["t1_aim_start_tick"])
    assert int(result["t1_aim_start_tick"]) == T0 + 2  # nxt of first qualifying pair
    assert result["t1_source"] == "sustained_aim"
```

**Test 3: NEW `test_t1_source_field_present_for_sustained_aim`** — verify the existing happy path emits the new field correctly. Mirror `test_t1_found_returns_tick` (lines 158-167) and add the source assertion:

```python
def test_t1_source_field_present_for_sustained_aim(self, analyzer):
    """T1 found via sustained-aim loop → t1_source='sustained_aim' in result dict."""
    ticks = _make_ticks(player_aim_rows=_aim_rows_t1_found())
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert result["t1_source"] == "sustained_aim"
```

**Test 4: NEW `test_t1_pre_aim_falls_through_when_enemy_missing_at_t0`** — fallback path. Mirror the existing `test_t1_not_found_enemy_data_missing_resets_consecutive` (lines 259-287) which already builds a tick DataFrame with enemy rows omitted at specific ticks. The Phase 10 test omits enemy row at T0 specifically:

```python
def test_t1_pre_aim_falls_through_when_enemy_missing_at_t0(self, analyzer):
    """Pre-aim check can't evaluate without enemy at T0 → falls through to sustained-aim loop."""
    base = T0 + 10
    player_rows = _aim_rows_t1_found()  # qualifying sustained-aim sequence
    # Build ticks manually: omit enemy row at T0 specifically (player still present)
    rows = []
    rows.append({"steamid": PLAYER_ID, "tick": T0,   "X": 0.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    rows.append({"steamid": PLAYER_ID, "tick": T0+1, "X": 1.0, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    # Enemy at T0+1 only (NOT at T0 — pre-aim check should fail and fall through)
    rows.append({"steamid": ENEMY_ID,  "tick": T0+1, "X": ENEMY_X, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    for tick, yaw, pitch in player_rows:
        rows.append({"steamid": PLAYER_ID, "tick": tick, "X": 0.0, "Y": 0.0, "Z": 0.0, "yaw": yaw, "pitch": pitch})
        rows.append({"steamid": ENEMY_ID,  "tick": tick, "X": ENEMY_X, "Y": 0.0, "Z": 0.0, "yaw": 0.0, "pitch": 0.0})
    ticks = pd.DataFrame(rows)

    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert int(result["t1_aim_start_tick"]) == T0 + 11  # sustained-aim loop hit
    assert result["t1_source"] == "sustained_aim"
```

**Test 5: NEW `test_t1_source_none_when_t1_not_found`** — sentinel return covers the empty-window branch. Mirror `test_t1_not_found_single_tick_in_window` (lines 210-218):

```python
def test_t1_source_none_when_t1_not_found(self, analyzer):
    """T1 detection fails → t1_source='none' in result dict."""
    ticks = _make_ticks()  # no aim rows → no qualifying pairs
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert math.isnan(result["t1_aim_start_tick"])
    assert result["t1_source"] == "none"
```

**Lines to delete in test header** (test_ddm_analyzer_t1.py:28-29) — `GRACE_TICKS` constant becomes 0 and stops being referenced after rewrites:
```python
# At tickrate=64: 1 tick = 15.625ms. Grace period = int(120/15.625) = 7 ticks.
GRACE_TICKS = int(T1_GRACE_MS / (1000 / TICKRATE))
```
After Phase 10, no test references `GRACE_TICKS` (the only reference was in `test_t1_grace_period_excludes_early_ticks`, which is rewritten). Plan should explicitly remove the constant + its comment.

**Imports already in place** (test_ddm_analyzer_t1.py:22):
```python
from config import AnalysisMoment, T1_GRACE_MS, T1_SUSTAINED_AIM_TICKS, T1_MIN_ANGLE_CHANGE
```
After grace removal, `T1_GRACE_MS` can stay imported (used in rewritten docstrings as documentation) or be dropped — planner's call. Other imports remain.

---

### `analyze_engagement_episode` return dict (`t1_source` field addition)

**Analog:** Same method, same return dict at lines 791-813 — 15 fields already present, one new field added.

**Existing return dict pattern** (ddm_analyzer.py:791-813):
```python
return {
    "match_id": self.match_id,
    "player_steamid": self.player_steamid,  # D-05: Path 1 schema
    "map_name": self.map_name,
    "moment_timestamp": moment_info.timestamp,
    "description": moment_info.description,
    "t0_source": t0_source,
    "t0_manual_tick": int(t0_tick),
    "t1_aim_start_tick": int(t1_tick) if t1_tick != -1 else np.nan,
    "t2_first_hit_tick": int(t2_tick),
    "rt_visible_to_aim_ms": rt_t0_t1,
    "rt_aim_to_hit_ms": rt_t1_t2,
    "rt_visible_to_hit_ms": rt_t0_t2,
    "target_enemy_id": str(target_enemy_id),
    "player_velocity_at_t0_ups": round(player_vel, 1) if not math.isnan(player_vel) else np.nan,
    "enemy_velocity_at_t0_ups": round(enemy_vel, 1) if not math.isnan(enemy_vel) else np.nan,
    "engagement_type": engagement_type,
    "crosshair_angle_at_t0_deg": crosshair_angle,
    "round_time_s": round_time_s,
    "round_phase": round_phase,
    # D-01: 1-indexed round_number for narrative attribution (Phase v2).
    "round_number": round_number,
}
```

**Caller-site change required** (ddm_analyzer.py:739):
```python
t1_tick = self._detect_t1(t0_tick, t2_tick, target_enemy_id, all_ticks_df, tag)
# → CHANGE to:
t1_tick, t1_source = self._detect_t1(t0_tick, t2_tick, target_enemy_id, all_ticks_df, tag)
```

**Insertion of new field** — append after `round_number` to match the `t0_source` placement convention (close to its `t1_aim_start_tick`/`t2_first_hit_tick` siblings would be aesthetically tighter, but minimum-diff favors append):

```python
return {
    # ... existing 15 fields unchanged ...
    "round_number": round_number,
    # Phase 10 (B-4 fix, 2026-05-16): T1 detection branch label.
    # ∈ {"sustained_aim", "pre_aimed", "none"}. NULL on legacy rows.
    "t1_source": t1_source,
}
```

**Why append (not slot near `t1_aim_start_tick`):** matches existing precedent — `round_number` was added in Phase v2 as a trailing field (lines 811-812) rather than re-shuffling earlier columns. Keeps git diff narrow and avoids touching the visually-adjacent `t1_aim_start_tick` line which would imply a logic change there.

**Note on `t0_source` slot** (line 797): existing precedent for source-flag fields. `t1_source` mirrors this exactly (string label, default NULL for legacy rows, three discrete domain values).

---

### `.planning/phases/10-.../grace_experiment_pre_fix.txt` (frozen artifact)

**Analog:** None in repo. This is a one-shot operator capture of `python grace_experiment.py` stdout before the fix lands. The artifact preserves the pre-fix 3-variant comparison (grace=120 baseline, grace=30, grace=0) for SC-5 diff against post-fix production.

**Capture pattern** (executed by operator before applying Phase 10 fixes):
```bash
python grace_experiment.py > .planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_pre_fix.txt 2>&1
```

**File format:** Plain text stdout dump. No structured schema. Used purely for human diff inspection (SC-5 acceptance: production T0→T1 distribution on the SAME demo matches the `grace=0` row of this captured baseline).

**Sequencing concern** (RESEARCH.md Pitfall 5): The capture MUST happen BEFORE the constant change in `config.py`. After the fix, `grace_experiment.py` still runs all 3 variants correctly (it monkey-patches the constant in-memory via `importlib.reload`), so post-fix re-runs reproduce all 3 distributions — but the pre-fix baseline serves as the trusted comparison point for "did the production fix match what the experiment predicted".

**No source-code analog needed** — `grace_experiment.py` already exists at the repo root (lines 1-80 read earlier). Phase 10 does not touch it. The artifact is a passive output capture, not a new script.

---

## Shared Patterns

### Logging tag convention
**Source:** `ddm_analyzer.py:328+` (every `_resolve_t0`, `_find_t2`, `_detect_t1`, `_compute_round_phase` method uses the same `tag` parameter and `self.logger.info(f"{tag} ...")` pattern)
**Apply to:** All new logging in pre-aim branch + sentinel returns

Existing pattern (ddm_analyzer.py:579, 582, 528):
```python
self.logger.info(f"{tag} T1={potential_t1} (after {consecutive} aim ticks)")
self.logger.warning(f"{tag} T1 not found — no sustained aiming detected.")
```

Phase 10 pre-aim branch follows verbatim:
```python
self.logger.info(f"{tag} T1={t0_tick} (pre_aimed)")
```

### Typing import convention
**Source:** `ddm_analyzer.py:15`
**Apply to:** Updated `_detect_t1` signature

```python
from typing import Tuple, List, Dict, Optional
```
`Tuple[int, str]` is already importable. No new typing imports needed.

### Idempotent migration pattern
**Source:** `db_utils.py:84-99`
**Apply to:** `t1_source` column addition

The `cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}` + `if col not in cols` guard handles re-running `init_db()` after the fix. No backfill, no destructive operations — the project standard for schema evolution.

### Test fixture invocation convention
**Source:** `tests/test_ddm_analyzer_t1.py:158-167` (template invocation used by every existing T1 test)
**Apply to:** All new and rewritten tests

```python
def test_NAME(self, analyzer):
    """DOCSTRING."""
    ticks = _make_ticks(player_aim_rows=AIM_ROWS_HELPER())
    result = analyzer.analyze_engagement_episode(
        _manual_moment(), ticks, pd.DataFrame(), _hurt()
    )
    assert result is not None
    assert ASSERTION
```

Empty `pd.DataFrame()` second arg = no fire events (irrelevant to T1 path); `_hurt()` third arg = T2 anchor at tick 1080 (within T0_TO_T2_MAX_TICKS gate).

### Source-flag field naming convention
**Source:** `ddm_analyzer.py:797` (`t0_source`)
**Apply to:** New `t1_source` field

Existing T0 follows `{t0_tick, t0_source, t0_manual_tick}` shape. Phase 10's T1 fields follow `{t1_aim_start_tick, t1_source}` — same pattern. Three discrete string values for the source flag, matching `t0_source` ∈ {"manual", "bvh_anchor_hit", ...}.

## No Analog Found

Files with no close match in the codebase:

| File | Role | Data Flow | Reason |
|-|-|-|-|
| `.planning/phases/10-.../grace_experiment_pre_fix.txt` | frozen artifact | file-I/O (write-once) | One-shot operator stdout capture — no code analog. Format is plain text dump; no schema. Operator-side acquisition only, not part of CI or pipeline. |

The single no-analog case is non-Python and non-source — it's a pre-fix evidence capture for SC-5 acceptance diffing. No pattern needed.

## Metadata

**Analog search scope:**
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\config.py` (236 lines, 1 read)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\db_utils.py` (198 lines, 1 read)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py` (lines 1-130, 300-499, 500-829 read non-overlapping; ~830 lines total)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\tests\test_ddm_analyzer_t1.py` (336 lines, 1 read)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\grace_experiment.py` (lines 1-80, 1 read)

**Files scanned:** 5 in-repo source files (all directly touched by Phase 10, no cross-file analogs needed)
**Pattern extraction date:** 2026-05-16
