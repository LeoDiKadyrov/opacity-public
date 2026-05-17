# SC-5 Grace Experiment Parity Diff — Phase 10

**Pre-fix baseline:** `grace_experiment_pre_fix.txt` (Plan 00 Task 1, captured 2026-05-16 pre-Plan-01)
**Post-fix rerun:** `grace_experiment_post_fix.txt` (this task, captured 2026-05-16 post-Plan-01 production code)
**Demo:** `temp_demos/astralis-vs-spirit-m1-dust2-p1.dem` (147 MB)
**Pros:** 13 (donk, tN1R, sh1ro, zweih, zont1x, magixx, chopper, Staehr, HooXi, jabbi, device, ryu, cadiaN)

## Pre-fix grace=0 row (from `grace_experiment_pre_fix.txt:1885`)

```
grace=0        |   14 |    16 |    16 |    62 |   203 |     0.0% |    64.3%
```

## Post-fix grace=0 row (from `grace_experiment_post_fix.txt:1885`)

```
grace=0        |   16 |     0 |    16 |    62 |   203 |     0.0% |    68.8%
```

## grace=0 row comparison

| Metric | Pre-fix | Post-fix | Delta | Within tolerance? |
|-|-|-|-|-|
| N | 14 | 16 | +2 | N/A (sample count) — expected rise from pre-aim recoveries |
| min | 16 | 0 | -16 ms | YES (post ≤ pre expected — pre-aim 0 ms cluster restored by B-4) |
| p25 | 16 | 16 | 0 | YES (identical) |
| med | 62 | 62 | 0 | YES (identical) |
| p75 | 203 | 203 | 0 | YES (identical) |
| **%@125ms** | **0.0%** | **0.0%** | **0.0pp** | **YES — CRITICAL: within ±2 pp** |
| %<180ms | 64.3% | 68.8% | +4.5pp | YES (post ≥ pre expected — pre-aim cluster adds new sub-180 mass) |

## Full 3-variant COMPARISON TABLE diff

Pre-fix (production code = `T1_GRACE_MS=120`, no pre-aim branch):

|variant|N|min|p25|med|p75|%@125ms|%<180ms|
|-|-|-|-|-|-|-|-|
|grace=120|14|125|125|164|250|42.9%|50.0%|
|grace=30|14|31|31|62|203|0.0%|64.3%|
|grace=0|14|16|16|62|203|0.0%|64.3%|

Post-fix (production code = `T1_GRACE_MS=0`, pre-aim branch active):

|variant|N|min|p25|med|p75|%@125ms|%<180ms|
|-|-|-|-|-|-|-|-|
|grace=120|16|0|125|133|250|37.5%|56.2%|
|grace=30|16|0|31|62|203|0.0%|68.8%|
|grace=0|16|0|16|62|203|0.0%|68.8%|

## Notes on directional expected divergence

The pre-fix `grace=0` row used the in-memory monkey-patch on `_detect_t1` body that had NO pre-aim branch — it merely simulated what removing the floor would look like. The post-fix `grace=0` row uses the new code path which includes BOTH grace removal (B-1) AND pre-aim branch (B-4).

Therefore:

- **post-fix `min` drops from 16 ms to 0 ms** because pre-aim cases (which pre-fix code censored to NaN per the `feedback_pre_aim_censorship_inverse_survivorship.md` pattern) are now restored as `rt=0` rows. This is the **B-4 fix**, not a parity violation.
- **post-fix `N` rises from 14 to 16** (+2 engagements). Those two new rows are the pre-aim cluster recoveries — engagements that were silently dropped from the `peek` distribution under pre-fix code.
- **post-fix `%<180ms` rises from 64.3% to 68.8%** (+4.5 pp). The 2 new rows at `rt=0` are in the sub-180 mass.
- **post-fix `p25`, `med`, `p75` are IDENTICAL** to pre-fix (16, 62, 203 ms). The middle of the distribution did not shift — only the left tail extended to 0 ms via 2 new sample points.
- **post-fix `%@125ms` stays at 0.0%** (the **CRITICAL** check) — both pre-fix and post-fix grace=0 produce zero engagements pinned at the 8-tick floor. Triangulation between in-memory experiment and live production confirms the fix landed correctly.

### Secondary signal — `grace=120` variant comparison

The `grace=120` row of the post-fix experiment is informative even though it does NOT correspond to production code anymore:

|metric|pre-fix grace=120|post-fix grace=120|interpretation|
|-|-|-|-|
|N|14|16|+2 from new pre-aim cluster|
|min|125|0|new pre-aim rows are flag-tagged BEFORE any grace gate fires|
|%@125ms|42.9%|37.5%|2 new rows at 0 ms dilute the floor pinning ratio|
|%<180ms|50.0%|56.2%|new 0 ms cluster shifts mass into sub-180|

This confirms the pre-aim branch (B-4) fires correctly INDEPENDENT of the grace-floor monkey-patch (B-1). Both fixes are orthogonal at the algorithm level: pre-aim is a separate early-return BEFORE the sustained-aim search window even starts. Even at `T1_GRACE_MS=120`, the pre-aim branch still recovers 2 zero-ms rows that pre-fix code censored.

## Verdict

**SC-5 PASS.**

The load-bearing `%@125ms` parity metric is `0.0% → 0.0%` (delta = 0.0 pp). Required tolerance was ±2 pp; achieved exact equality. All directional consistency expectations met:

- post-fix `min` (0) ≤ pre-fix `min` (16) ✓
- post-fix `%<180ms` (68.8) ≥ pre-fix `%<180ms` (64.3) ✓
- post-fix `N` (16) ≥ pre-fix `N` (14) ✓ (2 new pre-aim recoveries)
- post-fix middle quartiles (p25/med/p75) unchanged ✓

The triangulation between Path A (pre-fix in-memory monkey-patch simulation of `T1_GRACE_MS=0`) and Path B (post-fix production code with `T1_GRACE_MS=0`) agrees exactly on the load-bearing parity check. The Plan 01 fix landed correctly and produces the predicted distribution on real demo data.

**Operator sign-off:** Claude (gsd-executor, Wave 2 auto-execution) @ 2026-05-16
