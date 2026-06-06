---
phase: OF-1
plan: 00
type: spike
wave: 0
depends_on: []
milestone: outcome-first
autonomous: true
files_modified:
  - outcome_first_spike.py          # NEW standalone script
  - OF-1-VERDICT.md                  # NEW gate decision (in this phase dir)
production_code_touched: false      # TRIPWIRE: no edits to ddm_analyzer.py / duel_attempts.py / t0_detector.py / config.py
requirements: [SC-1]

must_haves:
  truths:
    - "Opponent identity for every reconstructed duel comes from a real player_hurt/player_death event (attacker==donk OR victim==donk), NEVER from BVH selection"
    - "Outcome (won/lost/unresolved) comes from player_death ordering within the duel episode"
    - "Spike runs on donk's on-disk demos and writes a results artifact + a VERDICT.md with PASS/FAIL on the 3 gate conditions"
    - "No production module is edited"
  artifacts:
    - path: "outcome_first_spike.py"
      provides: "Standalone outcome-first duel reconstructor for one player"
      contains: "attacker"
    - path: "OF-1-VERDICT.md"
      provides: "STOP/GO gate decision vs old 5.9% / 92.7% baseline"
---

<objective>
Prove or kill outcome-first. Build a standalone reconstructor that anchors each duel on a ground-truth player_hurt/player_death event (real opponent, real outcome), run it on donk's 81 on-disk demos, and decide STOP or GO via three gate conditions. No production code is touched — this is the deferred-tar-pit stop-rule expressed as a cheap spike.

Output: outcome_first_spike.py (+ a results json/print), and OF-1-VERDICT.md with the PASS/FAIL decision and donk's real numbers vs the old baseline.
</objective>

<execution_context>
gsd-sdk CLI is NOT installed on this machine. Execute this plan INLINE — read it directly, do the tasks, update STATE.md + write SUMMARY by hand. Do not invoke /gsd-* skills.
</execution_context>

<context>
@.planning/milestones/outcome-first-ROADMAP.md
@.planning/phases/OF-1-outcome-first-validation-spike/OF-1-CONTEXT.md
@duel_attempts.py
@t0_detector.py
@counter_peek_v2_enrich.py
@CLAUDE.md

<interfaces>
demoparser2: DemoParser(path).parse_events(["player_hurt","player_death","weapon_fire"]) -> List[(name, DataFrame)]
  player_hurt / player_death columns include: tick, attacker_steamid, user_steamid (victim)
t0_detector (reuse, do not edit): find_t0(all_ticks_df, player_steamid, enemy_steamid, search_start_tick, search_end_tick, ...) -> (tick|None, source)
donk_steamid = 76561198386265483
demos: D:\Obsidian\opacity\40_Projects\for_analysis\  (mostly spirit/)
_KILL_CONFIRM_WINDOW_TICKS = 320  (≈5s @ 64-tick) — reuse as duel-episode grouping gap
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Build outcome_first_spike.py — opponent + outcome from ground-truth events</name>
  <files>outcome_first_spike.py</files>
  <read_first>
    - OF-1-CONTEXT.md §2 (outcome-first design) + §5 (gotchas)
    - counter_peek_v2_enrich.py (player_death re-parse pattern, demo→path mapping, win logic to improve on)
    - reference_demo_corpus_locations.md + reference_player_steam_ids.md (cs2-ddm memory) for donk's demo file list
  </read_first>
  <behavior>
    - For a given player P (default donk) and a list of demo paths:
    - Parse player_hurt + player_death per demo.
    - Build the set of REAL exchanges: every hurt/death where attacker==P OR victim==P. The opponent E = the other steamid on that event (ground truth).
    - Group consecutive same-opponent events into duel EPISODES: new episode when gap to prior P-vs-E event > _KILL_CONFIRM_WINDOW_TICKS (320) or opponent changes.
    - Per episode record: demo, opponent E, first_event_tick, last_event_tick, outcome ∈ {won (E died first), lost (P died first), unresolved (neither died)}, p_was_attacker_first (who landed first hit), n_hits_P_on_E, n_hits_E_on_P.
    - Set PYTHONUTF8/IOENCODING + stdout.reconfigure. Coerce steamids to int64.
  </behavior>
  <action>
    Write outcome_first_spike.py as a standalone CLI. Core function reconstruct_duels(player_steamid, demo_paths) -> pandas.DataFrame of episodes with the columns above. Opponent and outcome MUST derive only from player_hurt/player_death — assert/comment this. Keep a tiny inline self-check (e.g. on a synthetic 2-event sequence) so logic is sanity-checked without real demos. Do NOT import or call DuelAttemptFinder or _detect_t1. Reaction-timing (find_t0 backward search) is OPTIONAL in v1 — only add if Task 3 needs it for a slice; opponent+outcome+initiator is the priority.
  </action>
  <verify>
    <automated>py -X utf8 outcome_first_spike.py --self-check</automated>
  </verify>
  <acceptance_criteria>
    - outcome_first_spike.py exists; `py outcome_first_spike.py --help` exits 0
    - grep for "attacker" and "user_steamid" present (opponent derived from events)
    - grep confirms NO import of duel_attempts / DuelAttemptFinder
    - --self-check passes on the synthetic case
  </acceptance_criteria>
  <done>Standalone reconstructor builds episodes with ground-truth opponent + outcome; self-check green; no production import.</done>
</task>

<task type="auto">
  <name>Task 2: Run on donk's 81 demos — produce results artifact</name>
  <files>outcome_first_spike.py (run only)</files>
  <read_first>
    - OF-1-CONTEXT.md §3 (corpus location)
  </read_first>
  <action>
    Enumerate donk's demos under D:\Obsidian\opacity\40_Projects\for_analysis\ (recurse; spirit/ etc.). Run reconstruct_duels(donk, demos). Write results to outcome_first_spike_results.json (or .csv): all episodes + a summary block. Print summary to stdout: total episodes, won/lost/unresolved counts, overall win-rate among resolved, median hits-P-on-E. If some demos fail to parse, skip + log count (do not fabricate).
  </action>
  <verify>
    <automated>py -X utf8 outcome_first_spike.py --player 76561198386265483 --demos "D:\Obsidian\opacity\40_Projects\for_analysis" --out outcome_first_spike_results.json</automated>
  </verify>
  <acceptance_criteria>
    - outcome_first_spike_results.json exists, non-empty, with N_episodes > 0 and a summary block
    - stdout prints total episodes + won/lost/unresolved + resolved win-rate
  </acceptance_criteria>
  <done>Real results produced for donk across available demos.</done>
</task>

<task type="auto">
  <name>Task 3: Compute the 3 gate metrics + one counter-peek/hold slice</name>
  <files>outcome_first_spike.py (extend) </files>
  <read_first>
    - OF-1-CONTEXT.md §2 step 5 (peek/hold on real duels) + ROADMAP gate definition
  </read_first>
  <behavior>
    - GATE-1 opponent-truth rate: fraction of episodes whose opponent came from a real event (by construction ≈100%; report it explicitly and contrast with the old 5.9% nominal-hit rate).
    - GATE-2 win-rate plausibility: resolved win-rate; PASS band roughly 40–70%.
    - GATE-3 interpretable slice: split duels where donk did NOT initiate (opponent landed/fired first = donk is the holder/counter-peeker) vs donk initiated; report win-rate per bucket. A real separation = signal. (If reaction-timing was added, also slice by pre-aim readiness.)
  </behavior>
  <action>
    Add a --gate mode that prints the three gate metrics with the old baseline beside each (old opponent-truth 5.9%, old survival-proxy win 92.7%, old slices: no separation). Compute the holder-vs-initiator slice from who-landed/fired-first within each episode.
  </action>
  <verify>
    <automated>py -X utf8 outcome_first_spike.py --gate --out outcome_first_spike_results.json</automated>
  </verify>
  <acceptance_criteria>
    - stdout prints GATE-1, GATE-2, GATE-3 each with new value vs old baseline
    - holder-vs-initiator win-rates printed with N per bucket
  </acceptance_criteria>
  <done>Three gate metrics + holder/initiator slice computed on real data.</done>
</task>

<task type="manual">
  <name>Task 4: GATE DECISION — write OF-1-VERDICT.md</name>
  <files>.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md</files>
  <action>
    Judge against the gate honestly. Write OF-1-VERDICT.md:
    - The three gate numbers (new vs old baseline) and PASS/FAIL on each.
    - Overall verdict: GO (all three pass → OF-2 may be planned) or STOP (any fail → park djok permanently per CAVEAT-2, no further loops).
    - If GO: one paragraph on what OF-2 must do (make outcome-first the production path, TDD, deprecate geometry-first opponent guess) — but DO NOT start OF-2 in this session.
    - If STOP: state plainly that djok-as-coaching is dead even with correct opponent identity, and why (e.g. unresolved-rate too high, or holder/initiator slice still flat → metric not informative). Connect to CAVEAT-1 (DDM RED 1/30) if relevant.
    - Stop-rule reminder: this was the single allowed validation loop. No "one more capture" spiral.
  </action>
  <acceptance_criteria>
    - OF-1-VERDICT.md exists with explicit PASS/FAIL per gate condition and a single GO/STOP decision
    - Decision is justified by the real numbers, not vibes
  </acceptance_criteria>
  <done>Gate decided and written; downstream (OF-2) authorized or milestone closed.</done>
</task>

</tasks>

<verification>
- outcome_first_spike.py runs end-to-end (self-check + real run + gate) with `py -X utf8`
- No production module (ddm_analyzer.py, duel_attempts.py, t0_detector.py, config.py) modified — `git status` shows only new files
- OF-1-VERDICT.md contains the GO/STOP decision with donk's numbers vs old 5.9% / 92.7% baseline
</verification>

<success_criteria>
A fresh session can run this spike, see whether outcome-first yields real duels with a plausible, interpretable metric, and get a defensible GO/STOP — without touching production code and without entering the rebuild prematurely.
</success_criteria>

<output>
After completion, write .planning/phases/OF-1-outcome-first-validation-spike/OF-1-00-SUMMARY.md (what was built, the gate numbers, the decision) and update .planning/STATE.md (milestone outcome-first, Phase OF-1 result).
</output>
