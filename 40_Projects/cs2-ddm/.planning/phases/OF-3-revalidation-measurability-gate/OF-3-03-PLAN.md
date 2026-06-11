---
phase: OF-3
plan: "03"
type: execute
wave: 3
depends_on: ["OF-3-02"]
files_modified:
  - of3_rebatch.py
  - generate_of3_inspection.py
  - resume_of3_rebatch.ps1
autonomous: false
requirements: [SC-3]
user_setup: []
must_haves:
  truths:
    - "donk corpus re-batched through outcome-first timing, staged N=1->5->81 (D-14)"
    - "N=5 inspection artifact reviewed by user BEFORE the full 81-demo run (D-14, autonomous:false)"
    - "Every inspection table carries >=1 physics-bounded column (crosshair_angle_at_t0_deg) (B-5 post-mortem rule, D-14)"
    - "Distribution-shape @requires_db tier runs after each stage; doubt => STOP (D-14, D-15)"
    - "b5_smoking_gun query class returns 0 impossible rows on fresh duel_episodes data (acceptance smell-test)"
  artifacts:
    - path: "of3_rebatch.py"
      provides: "staged N=1->5->81 driver, skip-existing, pause/resume, UTF-8 env (D-14)"
      contains: "T0_BACKWARD_SEARCH_CAP_TICKS"
    - path: "generate_of3_inspection.py"
      provides: "7-section inspection artifact generator, duel_episodes only, physics-bounded columns (D-14, Pitfall 5)"
      contains: "crosshair_angle_at_t0_deg"
  key_links:
    - from: "of3_rebatch.py"
      to: "outcome_first.reconstruct_all_players"
      via: "per-demo subprocess/inline call with UTF-8 env; skip-existing via duel_episodes.t0_source presence"
      pattern: "reconstruct_all_players|t0_source"
    - from: "generate_of3_inspection.py"
      to: "analytics.db duel_episodes"
      via: "sqlite cursor.fetchall(), never pd.read_sql on sid"
      pattern: "duel_episodes"
---

<objective>
Re-batch donk's 81-demo corpus through the OF-3 outcome-first timing pass, STAGED N=1 -> 5 -> 81 with manual checkpoints (D-14). Run the `@requires_db` distribution-shape tier after each stage (D-15). Generate a 7-section inspection artifact at N=5, reviewed by the user BEFORE the full run — every table carrying at least one physics-bounded column (`crosshair_angle_at_t0_deg`), per the B-5 post-mortem lesson. The acceptance smell-test: the `b5_smoking_gun.md` query class must return 0 impossible rows on fresh data.

Purpose: Produce a clean, trustworthy `duel_episodes` timing dataset that the measurability gate (OF-3-04) consumes. Staging + doubt-threshold + physics-bounded inspection is the hard-won ops discipline that catches tick-quantum bugs cheaply before a 81-demo regret.
Output: `of3_rebatch.py`, `generate_of3_inspection.py`, resume wrapper, populated `duel_episodes` timing columns for 81 donk demos, an `of3_inspection.md` artifact, green `@requires_db` tier.

CHECKPOINT: `autonomous: false` — Task 3 (N=5 inspection review) and Task 4 (N=81 go-ahead) are blocking human checkpoints per D-14.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-02-SUMMARY.md
@b5_smoking_gun.md

<interfaces>
Re-batch driver entry (reuse OF-2 production path):
  outcome_first.reconstruct_all_players(demo_path, player_sids, match_ids_by_sid, db_path) -> Dict[int,int]
  outcome_first.discover_player_sids(hurt_df) -> List[int]  (for "all players in demo" or filter to donk)
  db_utils.get_next_match_id / save_to_db already handle match_id assignment

donk steamid: 76561198386265483 (per CLAUDE.md interpretation_narrative example)
donk corpus: D:\Obsidian\opacity\40_Projects\for_analysis\spirit\  (81 demos with donk events, verified OF-1/OF-2)

Skip-existing predicate (per demo): a demo is "done" for donk when its duel_episodes rows for donk's sid have t0_source IS NOT NULL (timing computed). Re-batch must DELETE-then-reinsert per demo (force_reprocess) because OF-2 already wrote 3352 timing-less rows.

Subprocess UTF-8 (mandatory, Windows cp1252 gotcha):
  _UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}

Tick-quantum multiples (ms): 15.625, 31.25, 46.875, 62.5
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: of3_rebatch.py staged driver + resume wrapper</name>
  <files>of3_rebatch.py, resume_of3_rebatch.ps1</files>
  <read_first>
    - monesy_rebatch.py (full: 2-phase staged pattern, extract_roster, skip-existing monesy_done/all_done, delete_*_rows, log/report_append, subprocess env)
    - resume_rebatch.ps1 (existing PowerShell pause/resume wrapper to mirror, if present; else full_corpus_rebatch resume scripts)
    - outcome_first.py (reconstruct_all_players + discover_player_sids signatures)
    - db_utils.py (get_next_match_id, DB_PATH)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (of3_rebatch.py analog section, lines 256-289)
  </read_first>
  <action>
Create `of3_rebatch.py` adapting `monesy_rebatch.py`:
1. Top: `_UTF8_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}`. Pass `env=_UTF8_ENV` to every subprocess call (or run inline — inline is acceptable per OF-2 deviation note where CLI --demos rejected single files; if running inline, still set the env vars at process start).
2. CLI: `--stage {1|5|81}` (mirrors monesy `--phase`), `--db <path>` (default analytics.db), `--corpus D:\Obsidian\opacity\40_Projects\for_analysis\spirit`.
3. Discover the donk demo list from the corpus dir (the 81 .dem files). For `--stage 1` process the FIRST demo; `--stage 5` process the first 5; `--stage 81` process all. Deterministic ordering (sorted by filename) so N=1 ⊂ N=5 ⊂ N=81.
4. **Skip-existing** (`of3_done(demo_name, db) -> bool`): a demo is done when `SELECT COUNT(*) FROM duel_episodes WHERE demo_name=? AND player_steamid=<donk> AND t0_source IS NOT NULL` > 0. Skip done demos (resume-safe).
5. **Force-reprocess** (`delete_donk_timing_rows(demo_name, db)`): since OF-2 wrote timing-less donk rows, DELETE this demo's donk rows before re-running so reconstruct_all_players reinserts WITH timing (avoid duplicate match_ids: delete by demo_name+player_steamid, then call reconstruct which assigns a fresh match_id via get_next_match_id). Use `cursor.execute` + commit; never pd.read_sql for the sid filter (pass donk sid as a bound int param).
6. For each non-done demo: parse via `_parse_demo_events`, get donk sid (filter discover_player_sids to donk, or just `[DONK_SID]`), assign match_id via get_next_match_id, call `reconstruct_all_players(demo_path, [DONK_SID], {DONK_SID: match_id}, db)`.
7. `log()` + `report_append()` to `of3_rebatch_report.md` (per memory: every phase writes to report before proceeding; exception block writes traceback).
8. After each stage completes, print the distribution-shape SQL summary (pinning %, min/p10 rt, never_landed%, never_visible%, b5-class count) so the operator sees doubt-triggers immediately.

Create `resume_of3_rebatch.ps1` mirroring the existing resume_rebatch.ps1: detached `Start-Process py of3_rebatch.py --stage 81`, cmdline-match pause/kill helper. Skip-existing makes resume idempotent.
  </action>
  <verify>
    <automated>py of3_rebatch.py --stage 1 --db analytics.db.of3_smoke 2>&1 | Select-String "stage 1|done|t0_source"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "_UTF8_ENV" of3_rebatch.py` returns the UTF-8 env dict definition
    - `grep -n "t0_source IS NOT NULL\|t0_source is not null" of3_rebatch.py` confirms the skip-existing predicate
    - `grep -n "stage" of3_rebatch.py` shows the --stage {1,5,81} CLI arg
    - `grep -n "reconstruct_all_players" of3_rebatch.py` shows the production-path call
    - `grep -n "pd.read_sql" of3_rebatch.py` returns NOTHING (sid filters use bound params + fetchall)
    - `py of3_rebatch.py --stage 1 --db analytics.db.of3_smoke` runs to completion on 1 demo and writes timing rows (verify: `t0_source IS NOT NULL` count > 0 for that demo in the smoke DB)
    - `resume_of3_rebatch.ps1` exists with a detached Start-Process invocation
  </acceptance_criteria>
  <done>of3_rebatch.py runs staged with skip-existing + UTF-8 env + force-reprocess; resume wrapper present; N=1 smoke writes timing rows.</done>
</task>

<task type="auto">
  <name>Task 2: generate_of3_inspection.py — 7-section, physics-bounded, duel_episodes only</name>
  <files>generate_of3_inspection.py</files>
  <read_first>
    - generate_top10_inspection.py (full: 7-section structure, pct/fmt_num helpers, sqlite read pattern)
    - of2_parity_inspection.md (the 7-section format + acceptance checklist this must follow)
    - b5_smoking_gun.md (the exact impossible-row query class to reproduce as an anomaly bucket)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (generate_of3_inspection.py analog, lines 293-313; Pitfall 5 — duel_episodes only, NEW script)
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md (Pitfall 5 column-collision note)
  </read_first>
  <action>
Create `generate_of3_inspection.py` (NEW — do NOT extend generate_top10_inspection.py, which assumes `engagements`; Pitfall 5). Query `duel_episodes` EXCLUSIVELY via `sqlite3` + `cursor.fetchall()` (never pd.read_sql on sid columns). Produce `of3_inspection.md` with the 7 sections from `of2_parity_inspection.md`, EACH table carrying `crosshair_angle_at_t0_deg` (the physics-bounded column — this is the non-negotiable B-5 post-mortem rule, feedback_inspection_without_physics_sanity_columns_misses_bugs_2026_05_19):

1. **Aggregate:** n_episodes, n with t0/t1 resolved, t0_source breakdown (BVH+AABB / long_visible / never_visible %), t1_source breakdown (lands / never_landed / no_t0 %), rt_visible_to_land_ms min/p10/p25/median/mean/max.
2. **Per-unit (per-demo):** for each of the N demos: n_episodes, median rt, %@tick-quantum pinning, max crosshair_angle_at_t0_deg.
3. **Per-actor (donk):** median rt, never_landed%, and the crosshair_angle_at_t0_deg distribution buckets (<=1 / 1-3 / 3-10 / 10-30 / 30+) mirroring b5_smoking_gun's table — on lands rows.
4. **Full list of resolved rows** (or a capped sample if huge): demo, round/tick, t0_tick, t1_tick, t2(first_event_tick), rt_visible_to_land_ms, crosshair_angle_at_t0_deg, t1_source.
5. **Anomaly buckets:** (a) b5-class impossible rows: `t1_tick = t0_tick + 1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD` — THIS COUNT MUST BE 0; (b) negative rt; (c) per-player median rt < 100ms (physiology floor flag); (d) tick-quantum clusters >10%.
6. **Random sample** (~20 rows) with all timing + physics columns for manual spot-check.
7. **Pre-vs-post:** compare to OF-2 baseline (won=1428/lost=1090 episode counts must be UNCHANGED — timing pass adds columns, never drops episodes; D-08). Distribution of rt is NEW (no pre baseline).

End with an explicit **acceptance checklist** (model on of2_parity_inspection.md): [ ] 0 b5-class impossible rows, [ ] pinning <10% at every tick-quantum, [ ] never_landed% plausible (2-50%), [ ] no per-player median rt <100ms unexplained, [ ] episode counts unchanged vs OF-2.

CLI: `py generate_of3_inspection.py --db <path> --out of3_inspection.md`.
  </action>
  <verify>
    <automated>py generate_of3_inspection.py --db analytics.db.of3_smoke --out of3_inspection_smoke.md 2>&1; Test-Path of3_inspection_smoke.md</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "crosshair_angle_at_t0_deg" generate_of3_inspection.py` appears in MULTIPLE table-building sections (physics-bounded column in every table)
    - `grep -n "duel_episodes" generate_of3_inspection.py` returns matches; `grep -c "engagements" generate_of3_inspection.py` returns 0 (Pitfall 5 — never queries the deprecated table)
    - `grep -n "pd.read_sql" generate_of3_inspection.py` returns NOTHING
    - `grep -n "2 \* TARGET_REACHED_THRESHOLD\|2\*TARGET_REACHED_THRESHOLD\|> 6" generate_of3_inspection.py` shows the b5-class impossible-row query
    - `grep -n "acceptance" generate_of3_inspection.py` (case-insensitive) shows the checklist is emitted
    - Running on the N=1 smoke DB produces `of3_inspection_smoke.md` with all 7 section headers present
  </acceptance_criteria>
  <done>generate_of3_inspection.py emits the 7-section artifact from duel_episodes only, physics-bounded columns in every table, b5-class anomaly bucket + acceptance checklist.</done>
</task>

<task type="checkpoint:human-verify" gate="blocking">
  <name>Task 3: Run staged N=1 -> 5, review N=5 inspection artifact (D-14 checkpoint)</name>
  <what-built>
    Executor runs `py of3_rebatch.py --stage 5 --db analytics.db` (the real DB), then `py generate_of3_inspection.py --db analytics.db --out of3_inspection.md`, then the live tier `py -m pytest tests/test_distribution_shape.py -m requires_db --override-ini="addopts=--strict-markers" -x`. The N=1 distribution-shape summary is checked FIRST (doubt = STOP before expanding to N=5); if N=1 is clean, expand to N=5 and regenerate the artifact.
  </what-built>
  <how-to-verify>
    1. Open `of3_inspection.md`. Walk the acceptance checklist at the bottom.
    2. CRITICAL physics-bounded checks (the B-5 post-mortem rule): Section 5 anomaly bucket (a) "b5-class impossible rows" MUST be 0. If >0, STOP — the T1 detector still has the B-5 class bug; do not expand to N=81.
    3. Confirm no tick-quantum cluster exceeds 10% (Section 2/5). Confirm never_landed% is plausible (2-50%). Confirm no per-player median rt < 100ms without explanation (physiology floor).
    4. Confirm `@requires_db` tier is GREEN (all distribution-shape live checks pass).
    5. Doubt trigger (per D-14): any mode/median divergence, any impossible row, any >10% pinning => STOP and investigate, do NOT advance to N=81.
  </how-to-verify>
  <resume-signal>Type "approved: expand to N=81" to proceed to the full run, or describe the distribution-shape concern (STOP) for investigation.</resume-signal>
</task>

<task type="auto">
  <name>Task 4: Full N=81 re-batch + final live-tier verification</name>
  <files>of3_rebatch.py</files>
  <read_first>
    - of3_rebatch.py (the driver built in Task 1 — confirm skip-existing means N=5 demos are skipped, only the remaining ~76 run)
    - of3_rebatch_report.md (in-progress report, if mid-run)
  </read_first>
  <action>
ONLY after Task 3 approval ("approved: expand to N=81"):
1. Run the full re-batch: `py of3_rebatch.py --stage 81 --db analytics.db` (or via `resume_of3_rebatch.ps1` for a long detached run with pause/resume). Skip-existing means the 5 already-done demos are skipped; ~76 remain. For a >10h run, use the detached PowerShell wrapper (memory: bash run_in_background caps at 10min).
2. On completion, regenerate the full artifact: `py generate_of3_inspection.py --db analytics.db --out of3_inspection.md`.
3. Run the live tier on the full dataset: `py -m pytest tests/test_distribution_shape.py -m requires_db --override-ini="addopts=--strict-markers" -x`.
4. Run the acceptance smell-test query directly (b5_smoking_gun class on the full data): assert 0 rows where `t1_tick = t0_tick + 1 AND crosshair_angle_at_t0_deg > 2*TARGET_REACHED_THRESHOLD`.
5. Confirm episode counts vs OF-2 baseline are UNCHANGED (won=1428/lost=1090 for donk — timing adds columns, never drops rows, D-08).
6. Write the final numbers to `of3_rebatch_report.md`.

If any doubt-trigger fires on the full data (impossible rows > 0, >10% pinning, implausible medians), STOP and surface to the user — do NOT proceed to OF-3-04 gate on suspect data.
  </action>
  <verify>
    <automated>py -m pytest tests/test_distribution_shape.py -m requires_db --override-ini="addopts=--strict-markers" -x</automated>
  </verify>
  <acceptance_criteria>
    - `@requires_db` tier GREEN on the full 81-demo dataset (pinning <10%, min rt >= 0, 0 b5-class impossible rows)
    - `SELECT COUNT(DISTINCT demo_name) FROM duel_episodes WHERE player_steamid=<donk> AND t0_source IS NOT NULL` == 81
    - `SELECT COUNT(*) FROM duel_episodes WHERE t1_tick = t0_tick + 1 AND crosshair_angle_at_t0_deg > 2*3.0` == 0 (b5 smell-test)
    - donk won=1428 / lost=1090 episode counts unchanged vs OF-2 (D-08, no rows dropped)
    - of3_inspection.md regenerated on full data; acceptance checklist all ticked
  </acceptance_criteria>
  <done>81 donk demos carry timing columns; live distribution-shape tier GREEN; b5 smell-test returns 0; episode counts unchanged; final report written.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|-|-|
| demo file → parser | Untrusted .dem; unchanged |
| re-batch subprocess → analytics.db | Local write; DELETE+reinsert per demo |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-|-|-|-|-|
| T-OF3-05 | Tampering | DELETE-then-reinsert in re-batch | mitigate | Delete scoped by demo_name + bound donk sid param; skip-existing prevents double-processing; match_id assigned fresh via get_next_match_id (no collision) |
| T-OF3-06 | Repudiation | partial re-batch state on crash | mitigate | DB IS the state (skip-existing); report file + traceback on exception; resume wrapper idempotent |
| T-OF3-07 | Information disclosure | SteamID in inspection/driver SQL | mitigate | cursor.fetchall() + bound int params; never pd.read_sql on sid columns |

No network/auth/crypto surface. ASVS L1 V2/V3/V4/V6 N/A.
</threat_model>

<verification>
- N=1 distribution-shape summary clean before N=5 (doubt=STOP)
- N=5 inspection artifact reviewed by user, 0 b5-class impossible rows (blocking checkpoint, D-14)
- N=81 live `@requires_db` tier GREEN; b5 smell-test 0 rows; episode counts unchanged
</verification>

<success_criteria>
- Staged N=1->5->81 re-batch with skip-existing + UTF-8 env + force-reprocess (D-14)
- N=5 inspection artifact reviewed by user before full run; physics-bounded column in every table (D-14)
- @requires_db distribution-shape tier GREEN after each stage (D-15)
- b5_smoking_gun query class returns 0 on fresh data (acceptance smell-test)
- 81 donk demos carry timing; episode counts unchanged vs OF-2 (D-08)
</success_criteria>

<output>
After completion, create `.planning/phases/OF-3-revalidation-measurability-gate/OF-3-03-SUMMARY.md`
</output>
