---
phase: OF-2
plan: 02
type: execute
wave: 2
depends_on: [OF-2-01]
milestone: outcome-first
autonomous: true
files_modified:
  - duel_attempts.py                              # delete DuelAttemptFinder class; keep DuelAttempt dataclass
  - t0_detector.py                                # delete find_first_visible_enemy_in_window (the opponent selector)
  - ddm_analyzer.py                               # delete find_all_duel_attempts + attempts_mode path
  - batch_runner.py                               # worker: episodes write replaces duel_attempts write
  - multi_player_analyze.py                       # drop attempts_mode; wire reconstruct_all_players
  - app.py                                        # drop attempts_mode
  - kill_rate_analysis.py                         # deprecation note; drop attempts_mode call path
  - tests/test_duel_attempts.py                   # delete L142-359 (DuelAttemptFinder section)
  - tests/test_t0_detector_first_visible_window.py  # DELETE file
  - tests/test_ddm_analyzer_core.py               # delete find_all_duel_attempts + attempts_mode tests
requirements: [R-7]
branch: outcome-first

must_haves:
  truths:
    - "Geometry opponent-selector is GONE: no production code calls find_first_visible_enemy_in_window or DuelAttemptFinder"
    - "DuelAttempt dataclass survives (kill_rate_analysis.py + test_db_utils.py + test_kill_rate_analysis.py import it)"
    - "t0_detector.find_t0 and find_visible_enemies_at_tick survive untouched (OF-3 needs them)"
    - "batch_runner worker writes duel_episodes for the processed player"
    - "Full suite GREEN after deletions"
  artifacts:
    - path: "batch_runner.py"
      provides: "Episode write in worker"
      contains: "reconstruct_all_players"
---

<objective>
Delete the geometry-first opponent guess from production (USER DECISION: удалить селектор + его тесты, не deprecate) and wire outcome-first episodes into every pipeline that previously produced geometry attempts. After this plan, the only duel data the pipelines produce is ground-truth duel_episodes.
</objective>

<threat_model>
No new attack surface — net code deletion. Risk class is regression, not security: mitigated by full-suite gate + grep acceptance criteria below.
</threat_model>

<context>
@.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md
@.planning/phases/OF-2-core-rebuild/OF-2-RESEARCH.md  (§1 Consumer Map — but see CORRECTION below)
@.planning/phases/OF-1-outcome-first-validation-spike/OF-1-CONTEXT.md  (§1 Killer 1 — что именно умирает и почему)

<consumer_map_correction>
RESEARCH.md missed the `attempts_mode` cascade. FULL verified caller list (grep 2026-06-05):
- app.py:191                — `analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)`
- batch_runner.py:105       — same call + duel_attempts write at L120-126
- multi_player_analyze.py:116 — same call
- kill_rate_analysis.py:78  — same call
- ddm_analyzer.py:18 (import), :225-258 (find_all_duel_attempts), :922 (attempts_mode param), :1157-1158 (attempts_mode branch)
- tests/test_ddm_analyzer_core.py:855-867 (find_all_duel_attempts test), :1119-1121 (attempts_mode test with fake_find_all)
Every one of these is touched in this plan.
</consumer_map_correction>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Gut duel_attempts.py + delete t0_detector selector</name>
  <files>duel_attempts.py, t0_detector.py</files>
  <read_first>
    - duel_attempts.py (полностью — L26-51 dataclass KEEP, L53-297 class DELETE)
    - t0_detector.py L280-330 (find_first_visible_enemy_in_window boundaries; verify find_t0 and find_visible_enemies_at_tick are separate methods)
  </read_first>
  <action>
    duel_attempts.py:
    - KEEP: module imports needed by the dataclass, `DuelAttempt` dataclass (L26-51) verbatim.
    - DELETE: `_HIT_LATENCY_TICKS` constant (L23), entire `DuelAttemptFinder` class (L53-297: __init__, find_attempts, _cluster_fires, _process_cluster, _check_kill, _count_bullets, _hurt_victims_in_window, _player_velocity).
    - DELETE now-unused imports: math, time, logging (if nothing else uses them), config imports VELOCITY_PEEK_THRESHOLD_UPS, KNIFE_WEAPON_NAMES, AWP_WEAPON_NAMES, _FIRE_CLUSTER_GAP_TICKS, _FIRE_CLUSTER_MAX_SPAN_TICKS, _ATTEMPT_WINDOW_BEFORE_TICKS, _ATTEMPT_WINDOW_AFTER_TICKS, _KILL_CONFIRM_WINDOW_TICKS, _BULLETS_FOR_HIT_RATE (verify each is unused after deletion before removing — ruff will flag).
    - ADD module docstring note: "DuelAttemptFinder (geometry-first opponent selection) was removed in OF-2 — opponent identity now comes from ground-truth events via outcome_first.py. The DuelAttempt dataclass remains for legacy CSV/db row typing (kill_rate_analysis)."

    t0_detector.py:
    - DELETE method `find_first_visible_enemy_in_window` (L291-~330) — it IS the opponent selector (its only caller `_process_cluster` dies above).
    - DO NOT touch: `find_t0`, `find_visible_enemies_at_tick`, `is_visible`, smoke/flash parsing — all KEPT for OF-3 backward reaction search.
    - Note: /check-phase6 skill applies to t0_detector.py edits — review its 3 edge cases before commit.
  </action>
  <verify>
    <automated>py -c "from duel_attempts import DuelAttempt" exits 0</automated>
    <automated>py -c "from duel_attempts import DuelAttemptFinder" FAILS (ImportError)</automated>
    <automated>grep -c "find_first_visible_enemy_in_window" t0_detector.py returns 0</automated>
    <automated>grep -c "def find_t0" t0_detector.py returns 1</automated>
  </verify>
  <acceptance_criteria>
    - `grep -rn "DuelAttemptFinder" --include="*.py" .` → hits ONLY in outcome_first_spike.py docstring (historical) and tests pending Task 3; 0 hits in duel_attempts.py/ddm_analyzer.py after Task 2
    - DuelAttempt dataclass intact with all 13 fields
  </acceptance_criteria>
  <commit>refactor(OF-2): delete geometry opponent-selector (DuelAttemptFinder + find_first_visible_enemy_in_window)</commit>
</task>

<task type="auto">
  <name>Task 2: ddm_analyzer.py + 4 callers — remove attempts_mode path, wire episodes</name>
  <files>ddm_analyzer.py, batch_runner.py, multi_player_analyze.py, app.py, kill_rate_analysis.py</files>
  <read_first>
    - ddm_analyzer.py L15-25 (imports), L225-258 (find_all_duel_attempts), L915-930 (analyze_demo signature), L1150-1165 (attempts_mode branch + return)
    - batch_runner.py L74-151 (worker), L120-126 (duel_attempts write block)
    - multi_player_analyze.py L100-130 (call site + comment L114)
    - app.py L180-200 (call site + что делается с attempts ниже)
    - kill_rate_analysis.py L70-90 (call site)
  </read_first>
  <action>
    ddm_analyzer.py:
    - L18 REPLACE: `from duel_attempts import DuelAttempt, DuelAttemptFinder` WITH: (delete line entirely if DuelAttempt unused elsewhere in file after edits; keep `from duel_attempts import DuelAttempt` if the return type hint still referenced — after deleting find_all_duel_attempts it should be unused → delete).
    - DELETE method `find_all_duel_attempts` (L225-258).
    - analyze_demo: REMOVE param `attempts_mode: bool = False` (L922); REMOVE the `if attempts_mode:` branch (L1157-1158); KEEP the `(results_df, attempts)` tuple return shape with `attempts = []` hardcoded just before return, with comment `# OF-2: geometry attempts removed; tuple shape kept for caller compatibility. Episodes live in outcome_first.reconstruct_all_players.`

    batch_runner.py (worker, L105-126):
    - L105 REPLACE: `results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)` WITH: `results_df, _ = analyzer.analyze_demo(bulk_mode=True)`
    - REPLACE the duel_attempts write block (L120-126, `n_attempts = 0` through `_db.save_to_db(att_df, db_path, "duel_attempts", match_id)`) WITH:
      ```python
      # OF-2: ground-truth duel episodes (outcome-first) replace geometry attempts
      from outcome_first import reconstruct_all_players
      ep_counts = reconstruct_all_players(
          demo_path,
          player_sids=[player_steamid],
          match_ids_by_sid={player_steamid: match_id},
          db_path=db_path,
      )
      n_attempts = ep_counts.get(player_steamid, 0)
      ```
      (n_attempts key in the result dict now counts episodes; rename dict key "attempts" → keep as-is for UI compatibility, add comment.)

    multi_player_analyze.py (`analyze_one`, L97-131; `match_id` in scope from L99):
    - EDIT M.1 — L114-116 REPLACE:
      ```python
          # attempts_mode=True so duel_attempts gets populated for the
          # kill_rate / hit_rate metrics in the report.
          results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)
      ```
      WITH:
      ```python
          results_df, _ = analyzer.analyze_demo(bulk_mode=True)
      ```
    - EDIT M.2 — L124-130 REPLACE:
      ```python
      if attempts:
          att_df = pd.DataFrame([dataclasses.asdict(a) for a in attempts])
          att_df["demo_name"] = demo_name
          try:
              _db.save_to_db(att_df, str(DB_PATH), "duel_attempts", match_id)
          except Exception as e:
              print(f"    WARN: duel_attempts save failed: {e}")
      ```
      WITH:
      ```python
      # OF-2: ground-truth duel episodes replace geometry attempts
      from outcome_first import reconstruct_all_players
      reconstruct_all_players(
          demo_path,
          player_sids=[player_sid],
          match_ids_by_sid={player_sid: match_id},
          db_path=str(DB_PATH),
      )
      ```
      (`dataclasses` import becomes unused after M.2 — remove if ruff flags it.)

    app.py:
    - L191 REPLACE: `results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)` WITH: `results_df, _ = analyzer.analyze_demo(bulk_mode=True)`
    - Read what app.py does with `attempts` below L191; delete/neutralize that block (likely a duel_attempts save or display) and add the same reconstruct_all_players wiring if a DB write existed.

    kill_rate_analysis.py:
    - L78 REPLACE: `_, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)` WITH: `_, attempts = analyzer.analyze_demo(bulk_mode=True)  # OF-2: always [] — geometry attempts removed`
    - ADD module docstring warning: "DEPRECATED PIPELINE (OF-2): kill-rate from geometry attempts was built on the removed opponent-selector. Hit/miss semantics move to duel_episodes (n_hits_p_on_e) in OF-3. Module kept for DuelAttempt typing + historical CSV reads only."

    MANDATORY mock sweep (memory lesson — signature change misses monkeypatches):
    `grep -rn "patch.object.*analyze_demo\|analyze_demo.*return_value\|patch.object.*find_all_duel_attempts\|find_all_duel_attempts.*return_value\|attempts_mode" tests/` — fix/delete every hit (Task 3 covers the known ones; this grep catches strays).
  </action>
  <verify>
    <automated>grep -rn "attempts_mode" --include="*.py" . returns 0 hits</automated>
    <automated>py -c "import ddm_analyzer, batch_runner, multi_player_analyze, kill_rate_analysis" exits 0</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "find_all_duel_attempts" ddm_analyzer.py` == 0
    - `grep -c "reconstruct_all_players" batch_runner.py` >= 1
    - `grep -c "reconstruct_all_players" multi_player_analyze.py` >= 1
    - `grep -rn "attempts_mode" --include="*.py" .` == 0 hits
  </acceptance_criteria>
  <commit>refactor(OF-2): attempts_mode removed; episodes wired into batch/multi-player/app pipelines</commit>
</task>

<task type="auto">
  <name>Task 3: Test cleanup — delete selector tests, keep survivors</name>
  <files>tests/test_duel_attempts.py, tests/test_t0_detector_first_visible_window.py, tests/test_ddm_analyzer_core.py</files>
  <read_first>
    - tests/test_duel_attempts.py L1-141 (survivors: dataclass tests L14-49, find_visible_enemies tests L51-80) и L142-359 (deletions)
    - tests/test_ddm_analyzer_core.py L850-875, L1110-1125 (attempts tests)
    - tests/test_batch_runner.py (полностью — worker contract tests могут пинить attempts write)
  </read_first>
  <action>
    - tests/test_t0_detector_first_visible_window.py: DELETE the whole file (`git rm`).
    - tests/test_duel_attempts.py: DELETE L142-359 (from `from duel_attempts import DuelAttemptFinder` through the end of the DuelAttemptFinder test section, including TestPlayerSteamid class at L349+). KEEP L1-141 (DuelAttempt dataclass tests + find_visible_enemies_at_tick tests).
    - tests/test_ddm_analyzer_core.py: DELETE `test_find_all_duel_attempts_returns_list` (L855-867) and the attempts_mode test at L1119-1121 (read its full function body first — delete the whole function, not just 3 lines).
    - tests/test_batch_runner.py: read for assertions on `"duel_attempts"` save or `attempts` result key from the worker; update expectations to episode wiring (mock `outcome_first.reconstruct_all_players` → `{sid: N}`).
    - Final sweep: `grep -rn "DuelAttemptFinder\|find_first_visible_enemy_in_window\|find_all_duel_attempts" tests/` must return 0 hits.
  </action>
  <verify>
    <automated>py -m pytest -p no:cov exits 0 (full suite GREEN after deletions)</automated>
    <automated>grep -rn "DuelAttemptFinder|find_first_visible_enemy_in_window|find_all_duel_attempts" tests/ -E returns 0 hits</automated>
  </verify>
  <acceptance_criteria>
    - tests/test_t0_detector_first_visible_window.py отсутствует на диске
    - tests/test_duel_attempts.py содержит `class TestDuelAttempt` / dataclass tests, 0 упоминаний DuelAttemptFinder
    - Full suite GREEN
  </acceptance_criteria>
  <commit>test(OF-2): delete geometry-selector test suite; survivors intact</commit>
</task>

</tasks>

<verification>
- `py -m pytest -p no:cov` exits 0
- `grep -rn "DuelAttemptFinder\|find_first_visible_enemy_in_window\|attempts_mode" --include="*.py" .` → hits only in outcome_first_spike.py docstring (historical reference, allowed) and .planning/ docs
- `py -c "from duel_attempts import DuelAttempt"` exits 0 (kill_rate_analysis + test_db_utils contract intact)
- black + ruff clean on touched files (hook enforces)
</verification>
