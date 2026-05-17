# Phase 10: T1 detection fix batch (B-1 + B-4) — Research

**Researched:** 2026-05-16
**Domain:** measurement-layer correctness (reaction-time detection); single-file algorithmic fix with paired test rewrite + 1-demo empirical validation
**Confidence:** HIGH

## Summary

Phase 10 ships a measurement-layer correctness fix to `_detect_t1` in `ddm_analyzer.py`, eliminating two coexisting distortions of the `rt_visible_to_aim_ms` (T0→T1) metric: B-1 (hard 125 ms floor from a redundant grace gate) and B-4 (silent NaN censorship of the best pre-aimed engagements). The two bugs are inverse-direction artifacts on the same column — B-1 chops the left tail to a tick-quantum cliff, B-4 deletes the truest near-zero cases — and ship together because fixing only one yields a still-broken distribution (REVIEW.md line 124 explicit).

The code surface is narrow and verifiable: 1 constant in `config.py`, ~15 lines in `_detect_t1` (lines 512-583), 1 test rewrite + 1 new test, optional 1-column DB migration. No upstream/downstream code touches the bug site — `_detect_t1` is invoked once at `ddm_analyzer.py:739` and its return value flows into `rt_t0_t1`/`t1_aim_start_tick` only. The semantic filter chain (`sig_change` + `moving_towards` + `sustained`) survives intact per REVIEW recommendation; grace was the structural fourth predicate creating the floor, not a load-bearing safety net.

**Primary recommendation:** Apply BOTH fixes in a single PR (REVIEW.md mandates this). Use Variant **B-1a + B-4c** (see Architecture Patterns): set `T1_GRACE_MS=0` for minimum churn, add a `pre_aimed` early-return branch keyed on `curr_dist ≤ T1_NOT_AIMED_THRESHOLD` at T0+0 sustained over `T1_SUSTAINED_AIM_TICKS=2` ticks (mirrors existing sustained logic), and add a `t1_source TEXT DEFAULT NULL` column via idempotent ALTER TABLE so the pre-aim branch is externally visible for downstream charts and SC-4 distribution checks. Reject Variant B-4a (return T1=T0 without persistence flag) — it makes the censorship-fix invisible in the DB and risks recurrence detection failing silently in future audits.

## Architectural Responsibility Map

Single-tier project (Python pipeline, no client/server split). Mapping is by module ownership rather than network tier.

| Capability | Primary Module | Secondary Module | Rationale |
|-|-|-|-|
| Grace-floor removal | `config.py` (T1_GRACE_MS) | `ddm_analyzer.py:517-518` (consumer) | Constant defines the artifact; consumer must remain correct under value=0 |
| Pre-aimed branch | `ddm_analyzer.py:_detect_t1` | — | Algorithm decision; no other consumer of pre-aim state |
| Schema flag (`t1_source`) | `db_utils.py:_migrate_schema` | `ddm_analyzer.py:analyze_engagement_episode` (writer) | Migration idempotent; writer emits new column verbatim |
| Test rewrite | `tests/test_ddm_analyzer_t1.py` | `tests/conftest.py` (none needed) | Test asserts current buggy behavior — must be rewritten, not patched |
| SC-4 empirical validation | `grace_experiment.py` (existing) | `analytics.db` query | Already produces 3-variant comparison; production run with fix must match `grace=0` row |
| Downstream re-derivation | `interpretation.py` (`_FALLBACK_THRESHOLDS`, `_ABSOLUTE_ELITE_CEILING`) | — | OUT OF SCOPE — deferred to Phase A item 7 after full re-batch |

## Standard Stack

### Core (no new dependencies — fix is constant + algorithm + schema-migration only)

| Library | Version | Purpose | Why Standard |
|-|-|-|-|
| pandas | already in requirements.txt | DataFrame ops in `_detect_t1` | unchanged |
| sqlite3 | stdlib | `db_utils.py` ALTER TABLE | unchanged |
| pytest | already configured | test rewrite + new test | unchanged — 367 baseline tests pass |

**Installation:** no new packages. `[VERIFIED: requirements.txt present at repo root, pytest baseline 367 pass per REVIEW.md line 5]`

### No `npm view` / `pip index versions` checks needed — phase introduces no new dependencies.

## Architecture Patterns

### System data flow

`config.T1_GRACE_MS` → `ddm_analyzer._detect_t1` → `rt_t0_t1` int math → `analyze_engagement_episode` returns dict → `db_utils.save_to_db` writes `engagements` table → downstream `interpretation.py` reads via `cursor.fetchall()` → `report_generator.py` renders HTML.

Phase 10 touches only the first two arrows (config → algorithm) and optionally extends arrow 3 (one new column).

### Recommended project structure

No new files. Edits are localized to:

```
cs2-ddm/
├── config.py             # T1_GRACE_MS = 0 (one-line value change + comment rewrite)
├── ddm_analyzer.py       # _detect_t1: remove grace, add pre-aimed branch, emit t1_source
├── db_utils.py           # _migrate_schema: ALTER TABLE engagements ADD t1_source TEXT
├── tests/
│   └── test_ddm_analyzer_t1.py  # rewrite test_t1_grace_period_excludes_early_ticks
│                                # rewrite test_t1_not_found_already_aimed_at_enemy
│                                # NEW test_t1_pre_aimed_returns_t0
│                                # NEW test_t1_source_emitted_correctly
└── grace_experiment.py   # untouched — used as post-fix SC-5 cross-check
```

### Pattern 1: B-1 fix — remove the floor without removing the semantics

**What:** Set `T1_GRACE_MS = 0` in `config.py`. Rewrite the comment to point to the audit (REVIEW-2026-05-16 line 26-61, Phase A item 1) and the semantic filter chain that replaces it. Leave the `grace_ticks` calculation line intact in `_detect_t1` so structural symmetry is preserved (`int(0/15.625) = 0` → no math behavior change), but the resulting `aim_search_start = t0_tick + 0` removes the cliff.

**When to use:** This phase. `[CITED: REVIEW-2026-05-16.md line 51 — "REMOVE the grace gate entirely (T1_GRACE_MS = 0). Keep semantic chain intact."]`

**Example (config.py:122-124):**
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

**Why this over Variant b (remove the line entirely):** Keeping `grace_ticks = int(T1_GRACE_MS / (1000 / self.tickrate))` line means future re-experimentation (e.g. raising `T1_SUSTAINED_AIM_TICKS` to 3 then re-introducing a small grace if regression appears) doesn't require an algorithm edit, just a constant flip. The line is dead but defensive. REVIEW.md line 51: "If a regression appears in T1 noise, raise `T1_SUSTAINED_AIM_TICKS` to 3 or tighten `T1_MIN_ANGLE_CHANGE` — both semantic, neither creates a structural cliff." — keeping the grace plumbing is consistent with that stance.

### Pattern 2: B-4 fix — pre-aimed early return with persisted source flag

**What:** Before the main consecutive-tick loop in `_detect_t1`, check if the player's crosshair is already within `T1_NOT_AIMED_THRESHOLD = 1.0°` of the enemy at T0 AND remains within that threshold for `T1_SUSTAINED_AIM_TICKS = 2` consecutive ticks. If so, return `T1 = T0` (or `T0 + 1`, see Open Questions Q1). Persist branch decision via new `t1_source` column.

**When to use:** This phase, paired with B-1 fix per REVIEW.md line 124 ("must be fixed together").

**Algorithm sketch (drop-in for `_detect_t1` immediately after `aim_search_start` calculation, ~line 519):**

```python
# B-4 fix (2026-05-16): pre-aimed branch. If player crosshair was already
# on target at T0 (within T1_NOT_AIMED_THRESHOLD) and stayed there for
# T1_SUSTAINED_AIM_TICKS, perception+motion-planning was complete before
# visibility — set T1=T0, rt_visible_to_aim_ms=0. Else fall through to
# sustained-aim loop. Source: REVIEW-2026-05-16.md B-4 + feedback_pre_aim_
# censorship_inverse_survivorship.md.
pre_aim_window = all_ticks_df[
    (all_ticks_df["steamid"] == self.player_steamid)
    & (all_ticks_df["tick"] >= t0_tick)
    & (all_ticks_df["tick"] < t0_tick + T1_SUSTAINED_AIM_TICKS + 1)
].sort_values("tick")
if len(pre_aim_window) >= T1_SUSTAINED_AIM_TICKS:
    on_target_all = True
    for _, r in pre_aim_window.head(T1_SUSTAINED_AIM_TICKS + 1).iterrows():
        e_row = all_ticks_df[
            (all_ticks_df["tick"] == int(r["tick"]))
            & (all_ticks_df["steamid"] == int(target_enemy_id))
        ]
        if e_row.empty:
            on_target_all = False; break
        e = e_row.iloc[0]
        des_p, des_y = self.get_desired_angles(
            r["X"], r["Y"], r["Z"], e["X"], e["Y"], e["Z"],
        )
        dist = math.hypot(
            self.angular_diff(r["yaw"], des_y),
            self.angular_diff(r["pitch"], des_p),
        )
        if dist > T1_NOT_AIMED_THRESHOLD:
            on_target_all = False; break
    if on_target_all:
        self.logger.info(f"{tag} T1={t0_tick} (pre_aimed)")
        return t0_tick, "pre_aimed"
```

Change `_detect_t1` return signature from `int` → `Tuple[int, str]` where second element is `"sustained_aim"` (line 580), `"pre_aimed"` (new branch above), or `"none"` (line 583 — empty/timeout). Caller in `analyze_engagement_episode` (line 739) destructures and stores both. Existing tests on T1 value continue to work; new tests assert source.

### Pattern 3: t1_source schema migration

**What:** One-line addition to `db_utils._migrate_schema` `_eng_migrations` list:

```python
("t1_source", "TEXT DEFAULT NULL"),
```

**When to use:** Same PR as B-4. Existing rows get `NULL` (interpreted as "legacy — sustained_aim by old algorithm"). Post-fix rows get one of three discrete labels. SC-4 distribution check filters on `t1_source = 'pre_aimed'` to verify left tail is present.

**Why over deferring the column (Variant B-4a):**

1. Without a flag, future audits cannot distinguish a pre_aimed (T0→T1=0) from a noise-capture artifact. The flag IS the audit trail.
2. ALTER TABLE ADD COLUMN with DEFAULT NULL is established at `db_utils.py:97-99` — pattern is idempotent and trivially compatible with existing rows. Cost: 0 backfill, 1 LoC. `[VERIFIED: db_utils.py:97-99]`
3. Per `feedback_pre_aim_censorship_inverse_survivorship.md` line 28: "Add a per-engagement source/tier column when the detection logic has branches. T1 should carry t1_source ∈ {sustained_aim, pre_aimed} so the chart can split, pool, or visualize separately. This makes the censorship visible if it ever recurs." `[CITED]`

### Anti-Patterns to Avoid

- **Don't redefine the semantic filters.** Keep `T1_MIN_ANGLE_CHANGE`, `T1_NOT_AIMED_THRESHOLD`, `T1_MOVING_TOWARDS_TOLERANCE`, `T1_SUSTAINED_AIM_TICKS` values UNCHANGED. REVIEW.md flags W-3 (T1_MOVING_TOWARDS_TOLERANCE below quantization noise) and W-4 (T1_NOT_AIMED_THRESHOLD triple-stacking) as deferred to Phase B. Touching them in Phase 10 enlarges scope and breaks the "minimum viable fix" framing.
- **Don't add a `T1_MIN_RT_MS` lower bound** as semantic replacement for grace. That would just be the same floor under a different name. REVIEW.md is explicit: "If a regression appears, raise sustained_aim_ticks OR tighten min_angle_change — both semantic, neither creates a structural cliff." Trust the existing three-filter chain. `[CITED: REVIEW-2026-05-16.md line 51]`
- **Don't try to fix B-2 or B-3 in this phase.** Both are separate-pipeline bugs (`DuelAttemptFinder` path, not `_detect_t1`). They're Phase A items 3 + 4 with their own plans. Each touches different code paths (`duel_attempts.py`, `t0_detector.py:find_first_visible_enemy_in_window`).
- **Don't re-derive `_FALLBACK_THRESHOLDS` / `_ABSOLUTE_ELITE_CEILING` in this phase.** Those need clean re-batched data (Phase A item 6 = ~20h overnight). REVIEW.md line 58-60 + ROADMAP.md "Out of scope" list both confirm deferral. Note them in scope as "Phase A item 7 follow-up".
- **Don't write a `tests/test_distribution_shape.py` regression suite in this phase.** It's Phase A item 5 with its own spec (REVIEW.md lines 303-349). Out of scope per ROADMAP.md.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|-|-|-|-|
| Schema migration | Drop-and-recreate engagements table | Existing `db_utils._migrate_schema` ALTER TABLE pattern lines 84-99 | Idempotent, preserves existing rows, project-standard |
| Distribution-shape check (full suite) | New per-tick floor detector | DEFER to Phase A item 5 — REVIEW.md spec ready | Out of scope; one-off SQL queries suffice for SC-4 |
| Re-batch trigger | New CLI or script | DEFER to Phase A item 6 — operator gate, separate phase | Re-batch is ~20h overnight, gated on this phase landing |
| Pre-aim detection from scratch | Anything bigger than the 15-line block above | Use existing `get_desired_angles` + `angular_diff` helpers (ddm_analyzer.py:105-122) | Already battle-tested across 367 passing tests; copying the math from the sustained-aim loop is the safe path |

**Key insight:** Phase 10 is a **minimum-viable-correctness fix**. Every adjacent improvement (W-3 / W-4 / threshold re-derivation / distribution-shape suite / re-batch) has its own planning slot in REVIEW.md's roadmap. The temptation to "while I'm here" is the failure mode that turned earlier phases into multi-day scope explosions. Stay narrow.

## Runtime State Inventory

**Applicable** — this phase changes a constant (`T1_GRACE_MS = 120 → 0`) and adds a DB column (`t1_source`). Need to confirm what existing state references the old behavior.

| Category | Items Found | Action Required |
|-|-|-|
| Stored data | `analytics.db` contains 4104 engagement rows (verified 2026-05-16 query). 1225 / 4104 rows (≈29.8%) have `rt_visible_to_aim_ms` BETWEEN 124.5 AND 125.5 — these are floor-clipped. 827 / 4104 rows have `rt_visible_to_aim_ms IS NULL` — some are legitimate (T1 detection failed) but a subset are B-4 censored pre-aims. | NO data migration in Phase 10. Re-batch (Phase A item 6, separate phase) regenerates the values from raw demos. Existing rows keep `t1_source = NULL`, interpretable as "legacy". |
| Live service config | None — no n8n / Datadog / dashboards reading `T1_GRACE_MS` directly. The grace value is internal-pipeline only. Streamlit app reads `engagements` table via `cursor.fetchall()`. | None. |
| OS-registered state | None — no Task Scheduler tasks, no pm2 processes, no systemd units reference T1 constants. Batch runner is invoked manually. | None. |
| Secrets/env vars | None — `T1_GRACE_MS` is a config-module constant, not an env var. `ANTHROPIC_API_KEY` (orthogonal — narrative layer was discarded per `project_v2_discard_data_fixes_shipped_2026_05_14.md`). | None. |
| Build artifacts / installed packages | None — pure Python project, no compiled artifacts. `grace_experiment.py` already reloads the `ddm_analyzer` module via `importlib.reload` (line 49) so its in-memory variant test will pick up new constants on next run without rebuild. | None. |

**The canonical question answered:** After every file change is applied, the `analytics.db` rows generated BEFORE this PR are still floor-clipped. They need re-batching (Phase A item 6) to surface clean numbers. Phase 10's SC-4 validates on 1 demo by running pipeline ON THE FIXED CODE against that demo — it does NOT mutate existing rows.

## Common Pitfalls

### Pitfall 1: Test fixture `GRACE_TICKS` reference

**What goes wrong:** `tests/test_ddm_analyzer_t1.py:29` defines `GRACE_TICKS = int(T1_GRACE_MS / (1000 / TICKRATE))`. With `T1_GRACE_MS=0`, this becomes `GRACE_TICKS = 0`. Then `test_t1_grace_period_excludes_early_ticks` (line 291-305) computes `before_grace = T0 + GRACE_TICKS - 2 = T0 - 2` — which is BEFORE T0, breaking the test's premise.

**Why it happens:** Test was written when grace was a real semantic; after fix it's a dead concept and the test must be rewritten, not patched.

**How to avoid:** Plan must explicitly rewrite (not patch) `test_t1_grace_period_excludes_early_ticks`. New test name + new assertion. Suggested name: `test_t1_no_grace_early_aim_passes_through` — sets up qualifying aim ticks at T0+1, T0+2, T0+3 and asserts `t1_aim_start_tick == T0+2` (first qualifying nxt-tick).

**Warning signs:** If the test still references `GRACE_TICKS`, the rewrite was incomplete.

### Pitfall 2: `test_t1_not_found_already_aimed_at_enemy` two-test interaction

**What goes wrong:** Tests line 241-249 asserts `T1=NaN` when curr_dist ≤ 1.0°. Under B-4 fix, this case must now return `T1=T0` (or `T0+something_small`) and emit `t1_source="pre_aimed"`. Test's intent ("already aimed at enemy") is correct; assertion is now inverted.

**Why it happens:** B-4 specifically reverses the meaning of "already aimed". Before: censored (NaN). After: pre-aim success (T1=T0).

**How to avoid:** Rewrite same test. New assertion: `assert int(result["t1_aim_start_tick"]) == T0` AND `assert result["t1_source"] == "pre_aimed"` AND `assert result["rt_visible_to_aim_ms"] == 0.0`. Suggested name: `test_t1_pre_aimed_returns_t0_with_source_flag`.

**Warning signs:** Test fails with "expected NaN got 1000" — that's the green signal the fix worked, but the assertion needs updating.

### Pitfall 3: `_detect_t1` return type change

**What goes wrong:** Signature changes from `→ int` to `→ Tuple[int, str]`. Caller at `ddm_analyzer.py:739` (`t1_tick = self._detect_t1(...)`) and downstream consumers must destructure.

**Why it happens:** Adding `t1_source` requires the algorithm to return both pieces, or the caller must compute source separately. Returning both from `_detect_t1` is cleaner.

**How to avoid:** Plan must explicitly enumerate:
1. Update `_detect_t1` signature.
2. Update line 739: `t1_tick, t1_source = self._detect_t1(...)`.
3. Update sentinel returns (lines 528, 582-583): return `(-1, "none")` instead of `-1`.
4. Add `"t1_source": t1_source` to the return dict at line 791-813.
5. Update `db_utils._migrate_schema` to add column.
6. Existing tests don't read `t1_source` so most pass unchanged.

**Warning signs:** `TypeError: cannot unpack non-iterable int object` at test runtime.

### Pitfall 4: pytest invocation gotcha

**What goes wrong:** Plain `python -m pytest` fails on this repo because `pytest.ini` has `--cov` but `pytest-cov` may not be installed.

**Why it happens:** Project convention is `python -m pytest --override-ini="addopts=--strict-markers"` per CLAUDE.md.

**How to avoid:** Plan's verification step must specify the correct invocation. CLAUDE.md lines 8-9: `python -m pytest --override-ini="addopts=--strict-markers"`.

**Warning signs:** "ERROR: usage: pytest [...] --cov requires pytest-cov".

### Pitfall 5: Grace experiment script reload semantics

**What goes wrong:** `grace_experiment.py:46-49` patches `_cfg.T1_GRACE_MS` then `importlib.reload(sys.modules["ddm_analyzer"])`. If we modify the import line in `ddm_analyzer.py` (e.g., import `T1_NOT_AIMED_THRESHOLD` is already line 34, but pre-aim branch references additional names), `importlib.reload` MUST be after the monkey-patch — which it is.

**Why it happens:** Module-level imports cache constant values. Reload picks up the new value. If new dependencies are added to `ddm_analyzer.py`'s import block, the reload remains safe.

**How to avoid:** No action needed in plan. `grace_experiment.py` is correct as-is; its `grace=0` row post-fix should match production behavior on the SAME demo (SC-5 check). One caveat: the SC-5 cross-check should run `grace_experiment.py` BEFORE applying the production constant change (else baseline grace=120 row becomes unreproducible). Plan must sequence: (1) run `grace_experiment.py` once for record; (2) apply fix; (3) re-run pipeline on same demo; (4) compare DB rows for that demo against grace_experiment's grace=0 row.

**Warning signs:** Production min/median doesn't match grace=0 row of pre-fix experiment.

### Pitfall 6: `check-phase6` skill compliance

**What goes wrong:** Skill is mandatory before committing changes to `ddm_analyzer.py` (per CLAUDE.md "Skills" section and `.claude/skills/check-phase6/SKILL.md`). Skipping it is a project-rule violation.

**Why it happens:** Easy to forget when scope feels narrow.

**How to avoid:** Plan includes an explicit gate task: "Invoke `/check-phase6` skill; confirm 3 edge cases (T0>T2 flash, overlapping windows, T0 at search_start) are not regressed by `_detect_t1` changes." All 3 cases are upstream of `_detect_t1` (T0 already resolved before `_detect_t1` is called per `analyze_engagement_episode:665-695`), so the answer should be "not affected" — but the skill must be invoked.

**Warning signs:** Commit landing without `/check-phase6` runlog entry in the plan's task log.

## Code Examples

### Verified algorithm pattern from `_detect_t1` (lines 530-580)

```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py:530-580 (verified 2026-05-16)
consecutive = 0
potential_t1 = -1
for i in range(len(player_aim_ticks) - 1):
    curr = player_aim_ticks.iloc[i]
    nxt = player_aim_ticks.iloc[i + 1]
    # ... enemy lookup, des_p/des_y, d_yaw/d_pitch ...
    sig_change = d_yaw > T1_MIN_ANGLE_CHANGE or d_pitch > T1_MIN_ANGLE_CHANGE
    curr_dist = math.hypot(self.angular_diff(curr["yaw"], des_y), ...)
    nxt_dist = math.hypot(self.angular_diff(nxt["yaw"], des_y), ...)
    moving_towards = nxt_dist < (curr_dist - T1_MOVING_TOWARDS_TOLERANCE)
    if sig_change and moving_towards and curr_dist > T1_NOT_AIMED_THRESHOLD:
        if consecutive == 0:
            potential_t1 = int(nxt["tick"])
        consecutive += 1
    else:
        consecutive = 0
        potential_t1 = -1
    if consecutive >= T1_SUSTAINED_AIM_TICKS:
        return potential_t1
```

The pre-aim branch (B-4 fix) inverts the curr_dist predicate and looks at the leading edge of the same player_aim_ticks frame. See Pattern 2 above for the drop-in block.

### Verified ALTER TABLE pattern from `db_utils._migrate_schema` (lines 84-99)

```python
# Source: D:\Obsidian\opacity\40_Projects\cs2-ddm\db_utils.py:84-99 (verified 2026-05-16)
cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
_eng_migrations = [
    ("demo_name", "TEXT DEFAULT NULL"),
    ("player_steamid", "INTEGER DEFAULT NULL"),
    # ... existing migrations ...
    ("round_number", "INTEGER DEFAULT NULL"),
    # NEW for Phase 10:
    ("t1_source", "TEXT DEFAULT NULL"),
]
for col, col_def in _eng_migrations:
    if col not in cols:
        conn.execute(f"ALTER TABLE engagements ADD COLUMN {col} {col_def}")
```

Pattern is fully idempotent — re-running `init_db` after the fix is safe.

### Verified test fixture pattern from `tests/test_ddm_analyzer_t1.py` (lines 39-49, 72-97)

The existing `_make_ticks` helper builds tick frames with player + enemy rows at controlled positions. Pre-aim test reuses this with `_aim_rows_already_aimed` (line 121-129) — those rows now produce a pre-aim hit instead of NaN. Test rewrite is mechanical.

### SC-4 single-demo SQL query

```sql
-- Run AFTER applying fix + re-analyzing 1 reference demo:
SELECT
  MIN(rt_visible_to_aim_ms) AS min_ms,
  MAX(rt_visible_to_aim_ms) AS max_ms,
  COUNT(*) AS n_total,
  SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END) AS n_at_125ms,
  SUM(CASE WHEN rt_visible_to_aim_ms = 0 THEN 1 ELSE 0 END) AS n_pre_aimed,
  SUM(CASE WHEN t1_source = 'pre_aimed' THEN 1 ELSE 0 END) AS n_with_flag
FROM engagements
WHERE demo_name = 'spirit-vs-the-mongolz-m2-ancient.dem'
  AND rt_visible_to_aim_ms IS NOT NULL;
```

Acceptance per ROADMAP SC-4: `min_ms < 125`, `n_at_125ms / n_total < 0.10` (no value pinning >10% of N at any tick-quantum), `n_pre_aimed == n_with_flag` (sanity check on flag emission).

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|-|-|-|-|
| Stack 4 filters incl. structural grace | Trust 3 semantic filters (`sig_change` + `moving_towards` + `sustained`) | This phase (2026-05-16) | Removes 125ms floor; restores left tail of distribution |
| Single return path from `_detect_t1` (sustained_aim only, NaN for pre-aim) | Two return paths (sustained_aim or pre_aimed), persisted via `t1_source` flag | This phase | Pre-aim engagements no longer silently dropped; flag makes branch auditable |
| Implicit "moving toward target" success criterion | Explicit "already at target" pre-emption check | This phase | Inverse survivorship bias removed |

**Deprecated/outdated:**
- `T1_GRACE_MS = 120` (config.py:124, value pre-fix): rationale comment ("Avoids picking up pre-aim micro-corrections as T1") was structurally redundant with the existing three semantic filters — `feedback_redundant_grace_filter_creates_floor_artifact_2026_05_16.md` documents the methodology principle.
- Test `test_t1_grace_period_excludes_early_ticks`: asserted the buggy behavior. Rewrite, don't patch.
- Test `test_t1_not_found_already_aimed_at_enemy`: asserted the censorship. Rewrite to assert pre-aim success.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|-|-|-|-|
| A1 | Pre-aim sustained check uses `T1_SUSTAINED_AIM_TICKS = 2` (same constant as sustained-aim loop). | Pattern 2 | If a different constant is appropriate (e.g., 1 tick = "instant" pre-aim), B-4 either over-rejects (requires too much stability) or over-accepts (registers brief glances as pre-aim). Cheap to flip; default mirrors existing semantics. |
| A2 | Pre-aim branch sets `T1 = T0` (not `T0 + 1` or `T0 + sustained_count`). | Pattern 2 | If physiological interpretation is "perception complete at first visible tick", T0+1 is more correct (T0 itself is the visibility-onset tick, not the post-perception tick). Plan should make this explicit; REVIEW.md uses both phrasings ("T1=T0" line 120, "rt_visible_to_aim_ms=0" line 120) so the convention is T0. |
| A3 | Reference demo for SC-4 is `spirit-vs-the-mongolz-m2-ancient.dem` (highest engagement count in current DB at 99 rows, 87 with rt_visible_to_aim_ms NOT NULL, 24 at 125ms = 27.6% pinning — strong floor signal). Alternative: `astralis-vs-spirit-m1-dust2-p1.dem` (the demo `grace_experiment.py` already uses), but that produces only ~14 rows per pro after filters, possibly too sparse for SC-4's pinning threshold. | Open Q6 | If chosen demo has too few engagements, SC-4 distribution check is statistically noisy. Plan should permit operator override but recommend the ancient demo as default. |
| A4 | `_detect_t1` is invoked only from `analyze_engagement_episode:739` (verified by grep — no other callers). | Pitfall 3 | If a second caller exists in the duel_attempts pipeline, signature change breaks it. Grep confirms `_detect_t1` is private and called exactly once. |
| A5 | Floor-clipped existing analytics.db rows (1225 / 4104 at 125ms = 29.8%) match the per-player distribution evidence in `project_t1_grace_floor_bug_2026_05_16.md` (25-43% per pro). Numbers are within range — consistent. | Runtime State Inventory | None — corroborates the bug evidence. |

**If this table is empty:** N/A — 5 assumptions noted. Cheap to flip A1 and A2 in planner discussion; A3 is operator preference; A4 and A5 are documented as verified.

## Open Questions

1. **Pre-aim branch: T1 = T0 or T0+1?**
   - What we know: REVIEW.md line 120 says "set T1 = T0, rt_visible_to_aim_ms = 0" — explicit.
   - What's unclear: T0 is the first tick the enemy is geometrically visible. Setting T1=T0 means rt_visible_to_aim_ms=0 exactly, no quantization. Setting T1=T0+1 means rt=15.625ms (one tick), interpretable as "the first tick the player COULD have reacted, they were already aimed". Either is defensible; REVIEW.md prefers T0.
   - Recommendation: Follow REVIEW.md literally — T1=T0, rt=0. If downstream histograms show too many exact-zero values, Phase B can revisit. Document the choice in `_detect_t1` docstring.

2. **Should pre-aim require enemy availability at T0?**
   - What we know: Sustained-aim loop skips ticks where enemy row missing (lines 540-542). Pre-aim block in Pattern 2 above does the same (`if e_row.empty: ... break`).
   - What's unclear: If enemy is missing at exactly T0, fallback behavior is "abort pre-aim check, fall through to sustained-aim loop". This is the safe default.
   - Recommendation: Pattern 2 already handles correctly. Add a unit test (`test_t1_pre_aim_falls_through_when_enemy_missing_at_t0`).

3. **Should `t1_source` use NULL or `'sustained_aim'` for legacy rows post-migration?**
   - What we know: ALTER TABLE pattern sets DEFAULT NULL. Existing rows stay NULL.
   - What's unclear: Reports/dashboards may want a non-NULL legacy label. SQL `COALESCE(t1_source, 'legacy')` works downstream — no need to backfill.
   - Recommendation: Keep DEFAULT NULL; downstream uses COALESCE. NO retroactive UPDATE.

4. **Is the `moving_towards` filter still load-bearing if `T1_MOVING_TOWARDS_TOLERANCE=0.01°` is at noise floor (W-3)?**
   - What we know: `feedback_below_noise_floor_filter_degeneracy.md` confirms 0.01° is degenerate. Effective predicate strength is "any non-zero inward step", which `sig_change > 0.08°` already enforces stricter.
   - What's unclear: Removing `moving_towards` (W-3 Variant a) is a Phase B item. In Phase 10, the filter stays as-is.
   - Recommendation: DO NOT touch in Phase 10. Note for Phase B follow-up.

5. **Are there other tests that lean on the buggy behavior beyond the 2 named ones?**
   - What we know: `grep -r T1_GRACE` finds only 1 test file. `grep -r GRACE_TICKS` finds only 1 test file (the same file). `grep -r T1_NOT_AIMED_THRESHOLD` finds only `_detect_t1` and 1 test docstring mention.
   - What's unclear: Indirect dependencies — e.g., a downstream interpretation test that hard-codes 125ms p25. Quick scan of `tests/test_interpretation.py`: not loaded — would need spot check.
   - Recommendation: Plan should include `grep` audit task as gate: "grep `tests/` for 125, 0.125, 'grace', 'pre_aim'; document any non-T1 test that hard-codes the floor value". 367 baseline tests must remain green (= 368+ post-add).

6. **Which reference demo for SC-4?**
   - What we know: A3 in Assumptions Log — `spirit-vs-the-mongolz-m2-ancient.dem` has 99 rows / 87 valid (27.6% floor pinning, strong signal); `astralis-vs-spirit-m1-dust2-p1.dem` is what `grace_experiment.py` uses by default but is sparser per-player.
   - What's unclear: Whether the dust2 demo is still in `temp_demos/` (verified yes) AND whether the ancient demo is in `temp_demos/` or `for_analysis/` (NOT verified — `for_analysis/` was empty per init check; `temp_demos/` had only the dust2 demo). The ancient demo may need to be obtained or substituted.
   - Recommendation: Plan defaults to dust2 (already on disk), uses ancient if/when available. SC-4 acceptance criteria scale to N — at N≥80 the "no value pinning >10% of N" is statistically meaningful; at N=14 (one pro × dust2) it's noisier but `grace_experiment.py` already showed grace=0 produces `%@125ms = 0.0%` so even sparse demo demonstrates the fix.

7. **`grace_experiment.py` baseline state preservation.**
   - What we know: `grace_experiment.py` runs all 3 variants (grace=120, 30, 0) in one process via in-memory monkey-patch. Self-contained.
   - What's unclear: After the fix lands, `grace=120` row of the experiment is no longer a "baseline" because production code no longer uses 120. The experiment still works (monkey-patches override the constant), so post-fix runs reproduce all 3 distributions.
   - Recommendation: Save current pre-fix experiment output to `.planning/phases/10-t1-detection-fix-batch-b-1-b-4/grace_experiment_pre_fix.txt` as a frozen artifact for "diff against this" comparison.

## Environment Availability

Skip — phase has no external runtime dependencies. All edits are to existing Python files. `python`, `sqlite3`, `pytest`, `pandas` already verified by the 367 passing baseline.

## Validation Architecture

(Workflow.nyquist_validation = true per .planning/config.json.)

### Test Framework
| Property | Value |
|-|-|
| Framework | pytest (configured in pytest.ini with --cov; override via --override-ini="addopts=--strict-markers" per CLAUDE.md) |
| Config file | `pytest.ini` (root) |
| Quick run command | `python -m pytest tests/test_ddm_analyzer_t1.py --override-ini="addopts=--strict-markers" -x` |
| Full suite command | `python -m pytest --override-ini="addopts=--strict-markers"` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|-|-|-|-|-|
| SC-1 | T1_GRACE_MS removed; grace-period test rewritten | unit | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_no_grace_early_aim_passes_through --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (test rewrite) |
| SC-2 | Pre-aimed branch returns T1=T0 with t1_source='pre_aimed' | unit | `python -m pytest tests/test_ddm_analyzer_t1.py::TestT1Detection::test_t1_pre_aimed_returns_t0 --override-ini="addopts=--strict-markers" -x` | ❌ Wave 0 (new test) |
| SC-3 | All 367+ existing tests remain green | full suite | `python -m pytest --override-ini="addopts=--strict-markers"` | ✅ baseline confirmed |
| SC-4 | Single-demo re-analysis shows distribution unflattened | manual + SQL | `python run_analysis.py` on reference demo + SC-4 SQL query above | ✅ (run_analysis.py exists; SQL is hand-run) |
| SC-5 | grace_experiment.py production = grace=0 variant | manual | `python grace_experiment.py` post-fix, compare to pre-fix saved baseline | ✅ (script exists) |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_ddm_analyzer_t1.py --override-ini="addopts=--strict-markers" -x` (~5s)
- **Per wave merge:** `python -m pytest --override-ini="addopts=--strict-markers"` (full 367+ tests, ~30s)
- **Phase gate:** Full suite green + SC-4 SQL query passes + SC-5 grace_experiment diff matches before `/gsd-verify-work`

### Wave 0 Gaps
- [ ] Rewrite `tests/test_ddm_analyzer_t1.py::test_t1_grace_period_excludes_early_ticks` — currently asserts buggy behavior; must assert grace-removed pass-through (covers SC-1)
- [ ] Rewrite `tests/test_ddm_analyzer_t1.py::test_t1_not_found_already_aimed_at_enemy` — currently asserts NaN censorship; must assert pre-aim T1=T0 + `t1_source='pre_aimed'` (covers SC-2 + B-4)
- [ ] Add `tests/test_ddm_analyzer_t1.py::test_t1_pre_aimed_returns_t0` — explicit pre-aim positive case
- [ ] Add `tests/test_ddm_analyzer_t1.py::test_t1_source_field_present_for_sustained_aim` — emits `t1_source='sustained_aim'` for non-pre-aim path
- [ ] Add `tests/test_ddm_analyzer_t1.py::test_t1_pre_aim_falls_through_when_enemy_missing_at_t0` — fallback to sustained-aim loop when pre-aim check can't be evaluated

*Test framework infrastructure already exists; only test additions/rewrites needed.*

## Security Domain

Skip — phase has no auth, no input validation, no crypto, no network surface. Pure internal-pipeline logic + offline DB migration.

ASVS categories not applicable: V2 / V3 / V4 / V6 (no authentication, sessions, access control, or cryptography). V5 (input validation): the only "input" is demo file data, already validated upstream by demoparser2 schema and unchanged by this phase. V11 (data protection): no PII change; engagement metrics are non-personal except for SteamID which is public per CS2 demo format.

## Project Constraints (from CLAUDE.md)

| # | Constraint | Source | Phase 10 Compliance |
|-|-|-|-|
| C1 | `pip install -r requirements.txt` — no new deps. | CLAUDE.md "Quick Start" | ✅ Phase 10 adds zero dependencies. |
| C2 | Test invocation: `python -m pytest --override-ini="addopts=--strict-markers"`. | CLAUDE.md "Quick Start" | ✅ Validation Architecture uses correct flag. |
| C3 | Hook autorun: any Edit/Write on `*.py` triggers black + ruff + pytest. | CLAUDE.md "Claude Code Automations" | ✅ Edits to config.py, ddm_analyzer.py, db_utils.py, test file all trigger hook — no extra action needed. |
| C4 | `/check-phase6` skill is **required** before any commit to `t0_detector.py` or `ddm_analyzer.py`. | CLAUDE.md "Skills" + .claude/skills/check-phase6/SKILL.md | ✅ Plan must include explicit `/check-phase6` invocation as a gate before committing _detect_t1 edits. The 3 edge cases (T0>T2 flash, overlapping windows, T0 at search_start) are all UPSTREAM of `_detect_t1` and not affected — but the skill must still be invoked per project rule. |
| C5 | `cs2_engagement_analysis_results.csv` and `.env` are write-blocked. | CLAUDE.md "Claude Code Automations" | ✅ Phase 10 writes only to analytics.db, config.py, ddm_analyzer.py, db_utils.py, tests/. None of these are blocked. |
| C6 | Named constants in `config.py` — no magic numbers in logic files. | CLAUDE.md "Code Style" | ✅ Fix changes value of an existing named constant (`T1_GRACE_MS`); does not introduce magic numbers. |
| C7 | Strict typing hints (Tuple, List, Dict, Optional). | CLAUDE.md "Code Style" | ✅ `_detect_t1` return type changes to `Tuple[int, str]`; plan signature update must follow project's existing strict-hint convention. |
| C8 | `@dataclass` for state management. | CLAUDE.md "Code Style" | N/A — no new state classes introduced by this phase. |
| C9 | Tickrate=64, ms_per_tick=15.625, formula `ticks × (1000 / tickrate)`. | CLAUDE.md "Tech Stack & Core Rules" | ✅ Unchanged. SC-4 query uses tick-quantum value 125ms = 8 × 15.625 ms as the floor signature. |
| C10 | Isolation Rule: "Never combine data across unrelated categories unless explicitly requested." | CLAUDE.md "Tech Stack & Core Rules" | ✅ Phase 10 modifies ONE column on ONE table; does not cross-pollinate engagements with duel_attempts. |

## Sources

### Primary (HIGH confidence)
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\.planning\REVIEW-2026-05-16.md` — full audit, BLOCKER B-1 + B-4 + filter chain analysis + recommended fix paths
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\.planning\CODE_REVIEW_BRIEF_2026_05_16.md` — methodology context and audit framing
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\.planning\ROADMAP.md` (Phase 10 entry, lines 65-101) — scope, SC-1 through SC-5, in/out boundary
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\config.py` (lines 122-137) — current T1 constants with verified line numbers
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\ddm_analyzer.py` (lines 512-583) — verified bug site
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\db_utils.py` (lines 74-99) — verified ALTER TABLE migration pattern
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\tests\test_ddm_analyzer_t1.py` (lines 241-249, 291-305, full 336 lines) — verified test surface area
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\grace_experiment.py` (lines 43-71) — verified validation tooling and reload semantics
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\analytics.db` — verified distribution evidence via SQL probe: 4104 total rows, 1225 (29.8%) at 125ms exact floor, 827 NULL
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\CLAUDE.md` — project constraints C1-C10
- `D:\Obsidian\opacity\40_Projects\cs2-ddm\.claude\skills\check-phase6\SKILL.md` — mandatory skill checklist

### Secondary (memory files — HIGH confidence; project-authored)
- `C:\Users\Leo\.claude\projects\D--Obsidian-opacity-40-Projects-cs2-ddm\memory\project_t1_grace_floor_bug_2026_05_16.md` — DB evidence, discovery sequence, experiment results, REVIEW outcome
- `C:\Users\Leo\.claude\projects\D--Obsidian-opacity-40-Projects-cs2-ddm\memory\feedback_redundant_grace_filter_creates_floor_artifact_2026_05_16.md` — methodology principle this phase corrects
- `C:\Users\Leo\.claude\projects\D--Obsidian-opacity-40-Projects-cs2-ddm\memory\feedback_pre_aim_censorship_inverse_survivorship.md` — B-4 pattern rationale, source-flag prescription
- `C:\Users\Leo\.claude\projects\D--Obsidian-opacity-40-Projects-cs2-ddm\memory\feedback_below_noise_floor_filter_degeneracy.md` — W-3 (deferred); informs Phase B follow-up scope

### Tertiary (verified, no external sources needed)
None — phase scope is entirely internal-codebase + project-authored docs. No external libraries documented or upgraded.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new deps; existing libs verified by 367 passing tests
- Architecture: HIGH — bug site verified by direct file read; algorithm change is 15 LoC; signature change has only 1 caller
- Pitfalls: HIGH — Pitfalls 1-6 each grounded in verified file content (line numbers / grep)
- Pre-aim algorithm specifics: MEDIUM-HIGH — Pattern 2 sketch is plausible drop-in, but A1 + A2 in Assumptions Log are decisions the planner/operator will lock; sketch is illustrative not prescriptive
- SC-4 reference demo choice: MEDIUM — `astralis-vs-spirit-m1-dust2-p1.dem` is on disk and used by grace_experiment.py, but A3 flags possible substitution

**Research date:** 2026-05-16
**Valid until:** 30 days (no fast-moving external dependencies; project-internal scope stable)

## Phase Requirements

None — Phase 10 was added as an ad-hoc fix-batch phase post-audit. No REQ-N IDs in REQUIREMENTS.md (file does not exist; project does not maintain top-level requirements register). Scope is defined by ROADMAP.md "Phase 10" section + REVIEW-2026-05-16.md BLOCKER B-1 + B-4. SC-1 through SC-5 in ROADMAP.md serve as the acceptance contract.

| ID | Description | Research Support |
|-|-|-|
| SC-1 | T1_GRACE_MS=0 shipped; grace-period test rewritten | Pattern 1 + Common Pitfalls 1 + Wave 0 Gaps item 1 |
| SC-2 | Pre-aimed branch shipped; test_t1_pre_aimed_returns_t0 green | Pattern 2 + Common Pitfalls 2 + Wave 0 Gaps items 2-3 |
| SC-3 | All 367+ existing tests pass | Validation Architecture full suite + Pitfall 3 (signature change handling) |
| SC-4 | Single-demo distribution unflattened (min<125ms, no >10% pinning) | Code Examples SQL query + Open Question 6 (demo choice) |
| SC-5 | grace_experiment.py production = grace=0 variant | Pitfall 5 (reload semantics) + Open Question 7 (baseline preservation) |
