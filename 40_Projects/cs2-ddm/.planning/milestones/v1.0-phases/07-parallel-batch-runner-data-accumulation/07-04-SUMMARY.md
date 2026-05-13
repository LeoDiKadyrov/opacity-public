---
phase: 07-parallel-batch-runner-data-accumulation
plan: "04"
subsystem: app.py
tags: [streamlit, batch-runner, ui, threading]
dependency_graph:
  requires: ["07-02", "07-03"]
  provides: ["batch-analysis-ui"]
  affects: ["app.py"]
tech_stack:
  added: []
  patterns: ["threading.Thread + st.rerun() polling", "session_state batch coordination"]
key_files:
  modified: ["app.py"]
decisions:
  - "BATCH_INPUT_DIR set to ../../for_analysis (relative from app.py location)"
  - "SteamID sourced from sidebar input (shared across sections)"
  - "_BATCH_SHARED thread-safe dict for progress state"
  - "BatchRunner imported at module level to avoid PicklingError in ProcessPoolExecutor"
metrics:
  duration: "~2h (including checkpoint fixes)"
  completed: "2026-05-05"
  tasks_completed: 1
  files_modified: 1
---

# Phase 7 Plan 04: Streamlit Batch Analysis UI Summary

Streamlit Batch Analysis section added to app.py — users select subfolder, configure workers, launch batch processing via threading.Thread with live st.progress() polling.

## What Was Built

- New "Batch Analysis" section (Section 5) in app.py
- Subfolder selectbox scanning for_analysis/ directory
- Worker count slider (1–16, default=DEFAULT_BATCH_WORKERS=8)
- SteamID sourced from sidebar (shared with existing sections)
- Run Batch button → threading.Thread(_run_batch_thread) — non-blocking
- st.progress() + status text "Processing demo N/Total: filename"
- Force reprocess checkbox passed to BatchRunner.run(force_reprocess=True)
- Post-run summary: OK/Failed counts + error list

## Key Fixes Applied During Checkpoint

| Fix | Detail |
|-|-|
| BATCH_INPUT_DIR | Changed from hardcoded path to `../../for_analysis` relative to app.py |
| Subfolder selectbox | Added UI to select subfolder within for_analysis/ |
| SteamID from sidebar | Removed duplicate SteamID input; reads from existing sidebar field |
| _BATCH_SHARED dict | Thread-safe shared dict for progress state (replaces unsafe globals) |
| BatchRunner module-level import | Moved `from batch_runner import BatchRunner` to top-level to avoid PicklingError in ProcessPoolExecutor workers |
| Schema migrations | Added missing columns: round_time_s, round_phase, map_name, crosshair_angle_at_t0_deg |

## Validation Results

- 26/26 demos processed successfully (0 failures)
- 214 engagements written to analytics.db
- 2321 duel attempts written to analytics.db
- Median RT 453ms — matches reference dataset exactly
- UI remained non-blocking throughout batch run
- Force reprocess checkbox correctly triggers reprocessing

## Deviations from Plan

**1. [Rule 3 - Blocking] BATCH_INPUT_DIR path fix**
- Found during: Task 1 (checkpoint verification)
- Issue: Hardcoded absolute path failed on user's machine configuration
- Fix: Changed to relative path `../../for_analysis`
- Files modified: app.py

**2. [Rule 2 - Missing functionality] Thread-safe progress dict**
- Found during: Task 1
- Issue: Shared mutable state between threading.Thread and main thread was not protected
- Fix: Replaced with `_BATCH_SHARED` dict (dict operations are GIL-protected in CPython)

**3. [Rule 3 - Blocking] PicklingError fix**
- Found during: Checkpoint verification
- Issue: BatchRunner imported inside function caused PicklingError when ProcessPoolExecutor pickled workers
- Fix: Moved import to module level

**4. [Rule 1 - Bug] Schema migration columns**
- Found during: Checkpoint verification
- Issue: Four columns missing from analytics.db schema causing INSERT failures
- Fix: Added round_time_s, round_phase, map_name, crosshair_angle_at_t0_deg to _migrate_schema

## Self-Check: PASSED

- app.py modified and committed
- Batch Analysis section verified via human checkpoint (26/26 demos, 214 engagements, 2321 duel attempts, median RT 453ms)
