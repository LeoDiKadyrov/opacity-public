---
phase: OF-2
plan: 03
type: execute
wave: 3
depends_on: [OF-2-02]
milestone: outcome-first
autonomous: false   # checkpoint: user reviews parity inspection artifact before SC-2 sign-off
files_modified:
  - OF-2-PARITY.md   # NEW — parity verdict (in this phase dir)
  - of2_parity_inspection.md  # NEW — human-readable inspection artifact (repo root)
requirements: [R-8]
branch: outcome-first

must_haves:
  truths:
    - "Production outcome_first path ran on donk's 81 spirit demos and wrote duel_episodes rows"
    - "Parity vs outcome_first_spike_results.json computed with explicit tolerances (±5% episodes, win-rate 40–70%, initiator sep ≥5pp, dust2 spot-check 17/16)"
    - "Multi-player smoke: one demo, ALL players reconstructed in one call"
    - "Physics-bounded inspection artifact produced for manual review (won≈kills, lost≈deaths per demo)"
  artifacts:
    - path: ".planning/phases/OF-2-core-rebuild/OF-2-PARITY.md"
      provides: "R-8 parity verdict — PASS/FAIL per tolerance"
      contains: "win_rate_resolved_pct"
    - path: "of2_parity_inspection.md"
      provides: "Manual-review inspection tables with physics-bounded columns"
      contains: "won"
---

<objective>
Prove the production path reproduces the spike's validated numbers (R-8), prove multi-player works on a real demo, and hand the user an independent inspection artifact. This is the SC-2 evidence gate — NOT the OF-3 measurability gate (CAVEAT-1 still stands; no marketing claims from this data).
</objective>

<threat_model>
No new attack surface — read-only analysis run + report files.
</threat_model>

<context>
@.planning/phases/OF-2-core-rebuild/OF-2-CONTEXT.md
@.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md  (baseline numbers)
@outcome_first_spike_results.json  (4168 episodes baseline)

<tolerances>
- n_episodes: 4168 ± 5% → [3960, 4376] (gun-only filter REDUCES episodes vs spike — expect ≤ 4168; if production > spike, investigate, that direction is wrong)
- win_rate_resolved_pct: 40–70% band (spike: 56.7%)
- initiator separation: ≥ 5pp (spike: 9.7pp — holder 51.9% vs initiator 61.6%)
- dust2 spot-check spirit-vs-vitality-m3-dust2: won=17, lost=16 EXACT (gunfire kills/deaths; if gun-only filter shifts this, document the delta and verify against HLTV scoreboard 17/16)
- demos used: 81 (5 of 86 have no donk events)
</tolerances>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Multi-player smoke — 1 demo, all players</name>
  <files>(no source changes — run only)</files>
  <read_first>
    - outcome_first.py (CLI args from OF-2-01)
  </read_first>
  <action>
    Pick demo `D:\Obsidian\opacity\40_Projects\for_analysis\spirit\spirit-vs-vitality-m3-dust2.dem` (the spot-check demo). Run via temp DB:
    `py -X utf8 outcome_first.py --demos <single-demo-dir-or-file> --db of2_smoke.db` (no --player → all players mode via discover_player_sids).
    Env: PYTHONUTF8=1, PYTHONIOENCODING=utf-8.
    Assert via SQL on of2_smoke.db:
    - `SELECT COUNT(DISTINCT player_steamid) FROM duel_episodes` == 10 (full roster)
    - donk rows present: `SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=76561198386265483` > 0
    - per-player won≈kills sanity for 2-3 players vs known scoreboard.
    Use cursor.fetchall() (NEVER pd.read_sql on sid columns). Delete of2_smoke.db after recording numbers in OF-2-PARITY.md draft.
  </action>
  <verify>
    <automated>SQL count check: 10 distinct players, donk episodes > 0</automated>
  </verify>
  <acceptance_criteria>
    - 10 distinct player_steamid values, all 17-digit (no float-corrupted ids — check `LENGTH(CAST(player_steamid AS TEXT))==17` for all rows)
    - donk won/lost on this demo recorded for Task 2 cross-check
  </acceptance_criteria>
  <commit>(no commit — run artifacts recorded in Task 3 report)</commit>
</task>

<task type="auto">
  <name>Task 2: donk 81-demo parity run vs spike baseline</name>
  <files>(run only; writes to analytics.db duel_episodes)</files>
  <read_first>
    - outcome_first_spike_results.json (summary block — baseline numbers)
    - .planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md (gate bands)
  </read_first>
  <action>
    Run production path on the full donk corpus:
    `py -X utf8 outcome_first.py --demos "D:\Obsidian\opacity\40_Projects\for_analysis\spirit" --player 76561198386265483 --db analytics.db --compare-baseline outcome_first_spike_results.json`
    Expected wall time: minutes (events-only parse; spike did 86 demos in one session). If > 30 min, switch to detached PowerShell watcher pattern.
    Record: n_episodes, won, lost, unresolved, win_rate_resolved_pct, initiator slice (holder win% vs initiator win%, separation pp), per-demo dust2 spot-check.
    Compare against <tolerances>. ANY tolerance miss → STOP (doubt threshold), investigate before proceeding to Task 3 — do not rationalize a miss as "close enough".
  </action>
  <verify>
    <automated>SQL: SELECT COUNT(*) FROM duel_episodes WHERE player_steamid=76561198386265483 — in [3960, 4376] band (or documented-and-investigated if outside)</automated>
  </verify>
  <acceptance_criteria>
    - All 5 tolerance checks evaluated with explicit PASS/FAIL each
    - Numbers recorded verbatim for Task 3
  </acceptance_criteria>
  <commit>(no commit — data run)</commit>
</task>

<task type="auto">
  <name>Task 3: Inspection artifact + parity verdict</name>
  <files>of2_parity_inspection.md, .planning/phases/OF-2-core-rebuild/OF-2-PARITY.md</files>
  <read_first>
    - top10_inspection.md (формат-референс: 7 секций; ADD physics-bounded column per memory lesson — b5 smoking gun)
  </read_first>
  <action>
    of2_parity_inspection.md (human review, repo root) — sections:
    1. Aggregate: spike vs production side-by-side (n_episodes/won/lost/unresolved/win-rate/initiator slice) + delta %.
    2. Per-demo table (81 rows): demo, episodes, won, lost, unresolved, win_pct — EVERY row carries physics-bounded columns won≈kills / lost≈deaths expectation (флаг рядом, если won > 40 на одной карте = физически невозможно).
    3. Multi-player smoke results (Task 1): 10 players, per-player episodes/won/lost.
    4. Anomaly buckets: demos with win_pct outside 30–80%, episodes==0, unresolved > 60%.
    5. Random sample: 15 random episodes (demo, opponent sid, ticks, outcome, initiator, anchor_weapon) for manual demo-scrub verification.
    6. Gun-only filter effect: spike-minus-production episode count delta, top-10 demos by delta.
    7. Acceptance checklist (explicit checkboxes user ticks).

    OF-2-PARITY.md (phase dir) — verdict:
    - 5 tolerance checks, each PASS/FAIL with numbers
    - Multi-player smoke PASS/FAIL
    - Overall R-8: PASS/FAIL
    - Reminder block: CAVEAT-1 — это НЕ measurability gate; маркетинговые claims заблокированы до OF-3.

    Then STOP — checkpoint. User reviews of2_parity_inspection.md manually before SC-2 sign-off (trust-but-verify pattern).
  </action>
  <verify>
    <automated>test -f of2_parity_inspection.md && test -f .planning/phases/OF-2-core-rebuild/OF-2-PARITY.md</automated>
    <manual>User ticks acceptance checklist in of2_parity_inspection.md</manual>
  </verify>
  <acceptance_criteria>
    - of2_parity_inspection.md has all 7 sections; section 2 contains physics-bounded flag column
    - OF-2-PARITY.md contains explicit PASS/FAIL on all 5 tolerances + overall R-8 verdict
    - CAVEAT-1 reminder present in OF-2-PARITY.md
  </acceptance_criteria>
  <commit>docs(OF-2): R-8 parity verdict + inspection artifact</commit>
</task>

</tasks>

<verification>
- OF-2-PARITY.md exists with explicit R-8 PASS/FAIL
- duel_episodes contains donk's 81-demo reconstruction
- User has reviewed inspection artifact (checkpoint — phase not complete until then)
</verification>
