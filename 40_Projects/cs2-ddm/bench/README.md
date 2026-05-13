# Phase 9.1 — Demo Analysis Benchmark Harness

Cold-cache walltime benchmark for full-demo analysis. SC5 gate: post-change
mean walltime must be ≥ 3× faster than the pre-change baseline.

## Methodology (CONTEXT.md D-01)

- Up to 10 `.dem` files from `for_analysis/`, preferring distinct maps for
  `.tri` BVH load variance.
- One fresh subprocess per demo so the BVH cache is genuinely cold every run.
- Each subprocess runs `DDMAnalyzer.analyze_demo(profile=True, bulk_mode=True)`
  and emits JSON with `walltime_s`, per-step `step_seconds`, and `n_moments`.
- The parent harness aggregates per-demo records into a single JSON file.

## Usage

Capture pre-change baseline (run before any plan 09.1-01..04 commit):

```
python bench/run_bench.py --output bench/baseline.json
```

Capture post-change run (after all 4 perf changes shipped):

```
python bench/run_bench.py --output bench/post_change.json
```

Compare and check the SC5 ≥3× gate:

```
python bench/run_bench.py --compare bench/baseline.json bench/post_change.json
```

Exit code: `0` = PASS (mean speedup ≥ 3×), `2` = FAIL.

## Notes

- `psutil` is optional — `analyze_demo(profile=True)` already gates RSS
  measurement on `_PSUTIL_AVAILABLE`. Bench results don't require it.
- If `for_analysis/` has fewer than 10 demos the harness runs with whatever
  is on disk; the 09.1-00 SUMMARY records the actual count used.
- Per-demo timeout defaults to 600s (`--timeout`).
