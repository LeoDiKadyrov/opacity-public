# SC-4 Empirical Run — Phase 10

**Demo:** `astralis-vs-spirit-m1-dust2-p1.dem`
**Demo path:** `temp_demos/astralis-vs-spirit-m1-dust2-p1.dem` (147 MB, verified on disk)
**Pipeline run:** 2026-05-16 (Wave 2 auto-execution)
**Command:**
```
python multi_player_analyze.py temp_demos/astralis-vs-spirit-m1-dust2-p1.dem \
    --players 76561198386265483,76561198081484775,76561198210626739,76561197987713664,76561197998926770
```
**Pre-run analytics.db backup:** `analytics.db.pre-phase-10-sc4-2026-05-16` (created 2026-05-16 prior to dust2-row cleanup + pipeline run)

## Sampling decision

The Wave 2 plan estimated 30–60 min for the full 13-pro pipeline. To keep the executor's runtime/context budget bounded while still demonstrating distribution shape, I ran on a 5-pro subset (RESEARCH Open Q6 permits this — dust2 demo is sparse per-pro regardless; even sparse data demonstrates the fix). Subset balances both teams and roles:

| SteamID64 | Player | Team | Role | Engagements written |
|-|-|-|-|-|
| 76561198386265483 | donk | Spirit | star | 2 (both pre_aimed) |
| 76561198081484775 | sh1ro | Spirit | support | 0 |
| 76561198210626739 | zweih | Spirit | fragger | 0 |
| 76561197987713664 | device | Astralis | legend | 0 |
| 76561197998926770 | HooXi | Astralis | IGL | 3 (all sustained_aim) |

Total: 5 engagements survived all gates (clean 1v1, no AWP, enemy stationary, alive at T0, not in smoke, etc.). The other 3 pros produced zero rows on this demo after all filters — expected for a single short demo.

## Pre-run cleanup

The pre-existing `analytics.db` contained 18 dust2 rows from earlier batches (pre-Phase-10 floor-clipped data, generated with `T1_GRACE_MS=120`). To isolate SC-4 to clean post-fix data:

```python
DELETE FROM engagements WHERE demo_name='astralis-vs-spirit-m1-dust2-p1.dem';
DELETE FROM duel_attempts WHERE demo_name='astralis-vs-spirit-m1-dust2-p1.dem';
```

Then `db_utils.init_db('analytics.db')` was invoked manually to apply the `t1_source` ALTER TABLE migration (the migration is gated on `init_db()` and `multi_player_analyze.py` does not call it — see Deviation #1 below). After migration, 4913 legacy rows have `t1_source IS NULL`; 5 new dust2 rows have non-NULL values.

## Per-row inspection

| player_steamid | t0 | t1 | t2 | rt_t0_t1 (ms) | t1_source | type |
|-|-|-|-|-|-|-|
| 76561197998926770 (HooXi) | 17867 | 17868 | 17886 | 15.6 | sustained_aim | peek |
| 76561197998926770 (HooXi) | 24522 | 24587 | 24591 | 1015.6 | sustained_aim | peek |
| 76561197998926770 (HooXi) | 40915 | 40919 | 40926 | 62.5 | sustained_aim | peek |
| 76561198386265483 (donk) | 15789 | 15789 | 15839 | 0.0 | pre_aimed | peek |
| 76561198386265483 (donk) | 22069 | 22069 | 22100 | 0.0 | pre_aimed | peek |

Notable: the 15.6 ms HooXi engagement would have been **floor-clipped to ≥125 ms** under the pre-fix `T1_GRACE_MS=120` code; it is now correctly recovered at one-tick resolution (15.625 ms). The two donk engagements at `rt=0.0` ms are **B-4 fix recoveries** — under pre-fix code these would have been censored to NaN and dropped from the distribution (the "inverse survivorship" pattern documented in `feedback_pre_aim_censorship_inverse_survivorship.md`).

## SQL Query

```sql
SELECT MIN(rt_visible_to_aim_ms) AS min_ms,
       MAX(rt_visible_to_aim_ms) AS max_ms,
       COUNT(*) AS n_total,
       SUM(CASE WHEN rt_visible_to_aim_ms BETWEEN 124.5 AND 125.5 THEN 1 ELSE 0 END) AS n_at_125ms,
       SUM(CASE WHEN rt_visible_to_aim_ms = 0 THEN 1 ELSE 0 END) AS n_pre_aimed,
       SUM(CASE WHEN t1_source = 'pre_aimed' THEN 1 ELSE 0 END) AS n_with_flag
FROM engagements
WHERE demo_name = 'astralis-vs-spirit-m1-dust2-p1.dem'
  AND rt_visible_to_aim_ms IS NOT NULL;
```

## Result

| metric | value |
|-|-|
| min_ms | 0.0 |
| max_ms | 1015.625 |
| n_total | 5 |
| n_at_125ms | 0 |
| n_pre_aimed | 2 |
| n_with_flag | 2 |

## Acceptance check

- [x] `min_ms < 125.0` — actual: 0.0 → **PASS** (the 125 ms floor is GONE; pre-aim recovery floors the distribution at 0)
- [x] `n_at_125ms / n_total < 0.10` — actual ratio: 0.0% → **PASS** (no value pinning at the prior 8-tick floor)
- [x] `n_pre_aimed == n_with_flag` — match: YES (2 == 2) → **PASS** (every `rt=0` row carries `t1_source='pre_aimed'`; flag column emits correctly)

## Small-sample caveat

`n_total = 5` is below the 30-row threshold the plan suggests for statistically robust pinning analysis. However:

1. The plan explicitly anticipates this: "even sparse data should show `%@125ms = 0.0%` if grace removal worked" (RESEARCH Open Q6).
2. The frozen baseline `grace_experiment_pre_fix.txt` showed `grace=120` produced 42.9 % pinning on the same demo (14 rows, 13 pros) → the floor signal is EXTREMELY load-bearing; even with 5 rows, zero pinning is non-trivial evidence the fix landed.
3. The flag-column sanity check (`n_pre_aimed == n_with_flag`) is sample-size-independent — both counts being 2 confirms emission correctness.
4. SC-5 grace_experiment parity diff (Task 3 below) covers the 13-pro distribution comparison statistically.

The dust2 demo at 5 surviving rows after all gates is consistent with the grace_experiment's 14 rows across 13 pros (≈ 1.08 rows/pro/demo); a 5-pro subset produces 5.4 expected rows.

## Verdict

**SC-4 PASS.**

All three acceptance checks pass. The 125 ms floor is eliminated, no tick-quantum pinning at the prior boundary, the `t1_source` flag column emits correctly on every pre-aim row.

**Operator sign-off:** Claude (gsd-executor, Wave 2 auto-execution) @ 2026-05-16

---

## Deviation #1 — Schema migration not auto-applied by `save_to_db`

**Trigger:** First pipeline run wrote 5 CSV rows successfully but the engagements DB write failed with `Warning: could not write to 'analytics.db' table 'engagements': table engagements has no column named t1_source`. Subsequent SC-4 query returned 0 rows.

**Root cause:** `db_utils.save_to_db()` does NOT call `init_db()` before writing. The `t1_source` ALTER TABLE lives in `_migrate_schema`, which only runs from `init_db()`. Of the project's pipeline entry points:
- `batch_runner.py:234` — calls `init_db()` once at startup → migration applies
- `multi_player_analyze.py` — does NOT call `init_db()` → migration never fires
- `run_analysis.py` — invokes `ddm_analyzer.analyze_demo()` which calls `save_to_db` directly → no migration

This is a pre-existing latent issue surfaced by Phase 10's first schema change. Existing batches all went through `batch_runner.py` (which calls init_db), so the gap wasn't visible until now.

**Fix (this run):** Invoked `db_utils.init_db('analytics.db')` once manually after the first failed run, then re-ran the pipeline. Migration applied; second run wrote rows correctly.

**Out-of-scope deferred to Phase A:** The architectural fix is to either (a) call `init_db()` inside `save_to_db()` before any write, or (b) audit all pipeline entry points and ensure they call `init_db()` at startup. Tracked as a Phase A follow-up — does NOT block Phase 10 shipment because the operator can manually invoke `init_db()` before Phase A item 6 (full corpus re-batch) which uses `batch_runner.py` and gets the migration for free.

**Risk:** Low. Phase A item 6 (full re-batch ~20h) uses `batch_runner.py` which auto-migrates. Operators using `multi_player_analyze.py` on a fresh DB without prior batch_runner invocation hit silent DB-write failure. A defensive `init_db()` call at the top of `multi_player_analyze.py` would close the gap permanently.
