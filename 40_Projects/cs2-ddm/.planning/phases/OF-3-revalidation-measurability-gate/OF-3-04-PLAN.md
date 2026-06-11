---
phase: OF-3
plan: "04"
type: execute
wave: 4
depends_on: ["OF-3-03"]
files_modified:
  - of3_gate.py
  - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-VERDICT.md
autonomous: false
requirements: [SC-3]
user_setup: []
must_haves:
  truths:
    - "Gate thresholds (Gate-A slices + Gate-B r/N floors) presented to user and APPROVED before the gate run (D-10, no moving goalposts)"
    - "Gate-A reproduces OF-1/OF-2 win-rate separation on clean re-batched data (D-09)"
    - "Gate-B computes split-half RT reliability (Spearman-Brown r + Fisher-z CI95) on donk corpus, with cross-player diagnostic (D-09, D-12)"
    - "Gate-B FAIL -> STOP + checkpoint; user decides park / win-rate-only / iterate (D-11, no auto-pivot/auto-park)"
    - "Sole data source is duel_episodes; engagements untouched (D-16)"
  artifacts:
    - path: "of3_gate.py"
      provides: "Gate-A win-rate slices + Gate-B split-half reliability (D-09,D-10,D-12)"
      contains: "split_half_reliability"
    - path: ".planning/phases/OF-3-revalidation-measurability-gate/OF-3-VERDICT.md"
      provides: "measurability/stability verdict, SC-3 closure (CAVEAT-1)"
      contains: "Gate-A"
  key_links:
    - from: "of3_gate.py"
      to: "analytics.db duel_episodes"
      via: "SQL on timing columns; sid via _coerce_sid/bound params, never pd.read_sql"
      pattern: "duel_episodes"
    - from: "of3_gate.py Gate-B"
      to: "pandas.Series.corr + Fisher-z"
      via: "split-half on donk rt_visible_to_land_ms, Spearman-Brown corrected, CI95"
      pattern: "corr\\(|tanh|spearman"
---

<objective>
Build the CAVEAT-1 measurability/stability gate on the clean re-batched `duel_episodes` data. Two independent layers (D-09): **Gate-A** = win-rate slices (hold/counter vs initiate — expected PASS, 9.7pp≈5σ in OF-1); **Gate-B** = RT (T0→T1) split-half reliability — the real risk (prior DDM gate closed RED 1/30). The concrete PASS thresholds (researcher-designed) are presented for USER APPROVAL BEFORE the run (D-10 — no moving goalposts, the OF-2 band-miscalibration lesson). If Gate-B FAILs, STOP and let the user decide (D-11 — no auto-pivot, no auto-park). Write the verdict to `OF-3-VERDICT.md`, closing SC-3.

Purpose: This is the question OF-3 exists to answer — not "is the opponent right" (OF-2 fixed that) but "is the reaction metric measurable as a coaching signal at all." A clean opponent does NOT imply a shippable metric (CAVEAT-1). The gate is the real, final answer on djok-as-coaching-product.
Output: `of3_gate.py`, an approved-thresholds record, `OF-3-VERDICT.md`.

CHECKPOINT: `autonomous: false` — Task 1 ends at a blocking threshold-approval checkpoint (D-10); Task 3 ends at a blocking Gate-B-decision checkpoint if Gate-B FAILs (D-11).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-RESEARCH.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md
@.planning/phases/OF-3-revalidation-measurability-gate/OF-3-03-SUMMARY.md
@.planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md
@.planning/phases/OF-2-core-rebuild/OF-2-PARITY.md

<interfaces>
Gate-B split-half reliability (RESEARCH Code Examples — standard closed-form, no scipy):
  def split_half_reliability(half_a: pd.Series, half_b: pd.Series) -> dict:
      n = len(half_a); r = half_a.corr(half_b, method="pearson")
      r_full = (2*r)/(1+r)                       # Spearman-Brown
      z = 0.5*math.log((1+r)/(1-r)); se = 1/math.sqrt(n-3)
      ci_lo = math.tanh(z - 1.96*se); ci_hi = math.tanh(z + 1.96*se)
      r_full_ci = ((2*ci_lo)/(1+ci_lo), (2*ci_hi)/(1+ci_hi))
      return {"n": n, "r_half": r, "r_full_spearman_brown": r_full, "ci95_full": r_full_ci}

RESEARCH-PROPOSED thresholds (D-10 — PRESENT FOR USER APPROVAL, NOT pre-locked):
  Gate-A (expected PASS): win_rate_resolved in [40,70]% AND hold/counter-vs-initiate separation >= 5pp
    (OF-1 saw 56.7% win-rate, 9.7pp; OF-2 saw 10.4pp — re-derive on clean timing data).
  Gate-B PRIMARY (per-player split-half on donk's own corpus, HIGH N):
    split donk resolved (won+lost) lands-rows by ODD/EVEN parity of a STABLE key (demo_name hash,
    NOT match_id — match_id ordering unreliable per RESEARCH Open Q3). Group by per-demo mean
    rt_visible_to_land_ms -> N≈40/41 per half. Spearman-Brown r_full with Fisher-z CI95.
    PROPOSED PASS: r_full >= 0.5 AND CI95 lower bound > 0 ("reliably non-zero, not noise").
    Fallback grouping if per-demo N too noisy: per-round (decided at run from the N=5 feasibility note).
  Gate-B SECONDARY (cross-player, D-12, diagnostic NOT pass/fail): median rt per player
    (donk + 2-4 pros from the SAME on-disk corpus) with bootstrap CI95. Feeds VERDICT narrative.

Cross-player pros: pick 2-4 from the same spirit/ demos (opponents already in duel_episodes — free,
no new demos). Filter to sids with >= 50 resolved lands-rows for a stable median.

donk sid: 76561198386265483. Source table: duel_episodes ONLY (D-16).
SteamID: _coerce_sid / bound params; never pd.read_sql on sid columns.
</interfaces>
</context>

<tasks>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 1: Present Gate-A + Gate-B thresholds for approval BEFORE the run (D-10)</name>
  <decision>
    Lock the concrete PASS/FAIL thresholds for Gate-A and Gate-B before any gate computation runs. This is D-10: numbers are locked with a user checkpoint BEFORE the run — no moving goalposts after seeing results (the OF-2 ±5% band-miscalibration lesson).
  </decision>
  <context>
    The researcher derived these from first principles (no external CS2 reliability benchmark exists). They are PROPOSALS, not pre-locked. The prior DDM stability gate closed RED 1/30 cross-player — Gate-B is the real risk. The recommendation reframes Gate-B as a HIGH-N per-player split-half on donk's own corpus (the question we can answer with statistical power), with cross-player as a secondary diagnostic. Present the full rationale (RESEARCH Open Question 1) before the user decides.
  </context>
  <options>
    <option id="proposed">
      <name>Researcher-proposed (recommended)</name>
      <pros>Gate-A: win_rate in [40,70]% AND separation >= 5pp (matches OF-1/OF-2 evidence). Gate-B PRIMARY: per-player split-half on donk, per-demo means (N≈40/41), Spearman-Brown r_full >= 0.5 AND CI95 lower bound > 0. Gate-B SECONDARY: cross-player medians (donk + 2-4 pros), bootstrap CI95, diagnostic only. Answers "is the RT metric internally reliable for a well-sampled player" with real statistical power; avoids re-deriving the small-N failure that closed the prior gate.</pros>
      <cons>r >= 0.5 is a moderate bar derived from "CI95 lower bound > 0", not an industry benchmark. Per-demo N≈40 gives wide CI; the meaningful gate is the LOWER bound > 0, not the point estimate.</cons>
    </option>
    <option id="cross-player-primary">
      <name>Cross-player as PRIMARY (mirrors prior DDM gate)</name>
      <pros>Directly answers the marketing-relevant question "does donk react faster than X". Same framing as the prior gate (apples-to-apples with the 1/30 RED).</pros>
      <cons>Inherits the SAME small-N problem (N=3-5 players) that closed the prior gate RED — likely re-derives the same failure with a different label. Not enough players in the on-disk corpus for statistical power.</cons>
    </option>
    <option id="custom">
      <name>User-specified thresholds</name>
      <pros>User sets the exact r, N floor, grouping unit, separation pp directly.</pros>
      <cons>Must still be locked here, before the run.</cons>
    </option>
  </options>
  <resume-signal>Type "approved: proposed" (or "approved: cross-player-primary", or specify custom r/N/separation values). Executor writes the locked thresholds verbatim into of3_gate.py and OF-3-VERDICT.md's "Thresholds (locked pre-run)" section before computing anything.</resume-signal>
</task>

<task type="auto">
  <name>Task 2: Implement of3_gate.py (Gate-A + Gate-B) with locked thresholds</name>
  <files>of3_gate.py</files>
  <read_first>
    - outcome_first_spike.py (OF-1 slice logic — locate via Glob if not in tree; the win-rate / initiator-separation slice definitions to reproduce on clean data)
    - .planning/phases/OF-1-outcome-first-validation-spike/OF-1-VERDICT.md (the OF-1 numbers Gate-A must reproduce: 56.7% win-rate, 9.7pp separation)
    - .planning/phases/OF-2-core-rebuild/OF-2-PARITY.md (OF-2 baseline: won=1428/lost=1090, 10.4pp; band-miscalibration lesson)
    - outcome_first.py (lines 52-61: _coerce_sid — import for sid handling)
    - monesy_rebatch.py (argparse --phase pattern to mirror as --gate {A,B})
    - .planning/phases/OF-3-revalidation-measurability-gate/OF-3-PATTERNS.md (of3_gate.py analog, lines 317-337)
  </read_first>
  <action>
Create `of3_gate.py`. CLI: `--gate {A|B|both}`, `--db <path>` (default analytics.db), `--out OF-3-VERDICT.md`. Query `duel_episodes` EXCLUSIVELY (D-16), `sqlite3` + `cursor.fetchall()`, `_coerce_sid` for sids, never pd.read_sql on sid columns.

**Hardcode the LOCKED thresholds from Task 1 approval at the top of the file** as named constants with a comment `# LOCKED pre-run per D-10 user approval YYYY-MM-DD` — these must NOT be tunable after seeing results.

**Gate-A (win-rate slices):**
- Compute donk win_rate_resolved = won / (won + lost) on lands-resolved episodes; assert in the locked band (default [40,70]%).
- Compute the initiator/hold-vs-counter separation (reproduce OF-1/OF-2 slice: win-rate for episodes where donk initiated vs held/countered); assert separation >= locked pp (default 5).
- PASS/FAIL per the locked thresholds; record actual numbers.

**Gate-B (split-half RT reliability):**
- PRIMARY (per-player on donk, per locked grouping): take donk resolved lands-rows (`t1_source='lands'`, both t0/t1 non-NULL), compute `rt_visible_to_land_ms`. Split by ODD/EVEN parity of `hash(demo_name)` (stable key, NOT match_id — RESEARCH Open Q3). Group by per-demo mean rt within each half, align halves on the shared grouping unit, call `split_half_reliability(half_a, half_b)`. PASS per locked r_full + CI95-lower-bound rule.
- SECONDARY (cross-player diagnostic, D-12): for donk + 2-4 pros (sids with >= 50 resolved lands-rows in duel_episodes), compute median rt + bootstrap CI95 (resample episodes with replacement, ~1000 iters, percentile CI). Report only — NOT pass/fail.
- Include the `split_half_reliability` function verbatim from the interface block (pandas.corr + Fisher-z, no scipy).

**Output:** write/append `OF-3-VERDICT.md` with: locked thresholds (echoed), Gate-A actual + verdict, Gate-B PRIMARY actual (r_full, CI95, N) + verdict, Gate-B SECONDARY per-player table, and an overall narrative. Model markdown structure on OF-1-VERDICT.md / OF-2-PARITY.md.

Per-player median rt < 100ms => surface a "physiology floor — investigate" warning in the verdict (CONTEXT specifics), not an auto-fail.
  </action>
  <verify>
    <automated>py of3_gate.py --gate A --db analytics.db --out OF-3-VERDICT.md 2>&1 | Select-String "Gate-A|win_rate|PASS|FAIL"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -n "split_half_reliability" of3_gate.py` returns the function (Spearman-Brown + Fisher-z)
    - `grep -n "LOCKED" of3_gate.py` shows the thresholds carry the pre-run-locked comment (D-10)
    - `grep -c "engagements" of3_gate.py` returns 0 (duel_episodes only, D-16); `grep -n "duel_episodes" of3_gate.py` returns matches
    - `grep -n "pd.read_sql" of3_gate.py` returns NOTHING
    - `grep -n "scipy" of3_gate.py` returns NOTHING (pandas.corr per Standard Stack)
    - `grep -n "hash(demo_name)\|demo_name" of3_gate.py` confirms split key is demo_name-based, not match_id (RESEARCH Open Q3)
    - `py of3_gate.py --gate A --db analytics.db` runs and prints Gate-A win_rate + PASS/FAIL
    - `py of3_gate.py --gate B --db analytics.db` runs and prints Gate-B PRIMARY r_full + CI95 + N, plus the cross-player diagnostic table
  </acceptance_criteria>
  <done>of3_gate.py computes Gate-A (win-rate slices) + Gate-B (split-half reliability + cross-player diagnostic) with locked thresholds, duel_episodes only, no scipy/pd.read_sql; verdict numbers written.</done>
</task>

<task type="checkpoint:decision" gate="blocking">
  <name>Task 3: Write OF-3-VERDICT.md; if Gate-B FAILs, STOP for user decision (D-11)</name>
  <what-built>
    Executor runs `py of3_gate.py --gate both --db analytics.db --out OF-3-VERDICT.md`, producing the full measurability/stability verdict: locked thresholds (echoed), Gate-A verdict (expected PASS), Gate-B PRIMARY verdict (r_full + CI95 + N), Gate-B SECONDARY cross-player diagnostic, and the overall SC-3 closure narrative. The verdict cites donk's real clean-data numbers vs the OF-1 baseline.
  </what-built>
  <how-to-verify>
    1. Open `OF-3-VERDICT.md`. Confirm the locked thresholds match what was approved in Task 1 (no drift — D-10).
    2. Gate-A: confirm win_rate in band and separation >= threshold (expected PASS — reproduces OF-1/OF-2).
    3. Gate-B PRIMARY: read r_full + CI95 lower bound + N. PASS = r_full >= locked threshold AND CI95 lower bound > 0.
    4. **If Gate-B PASS:** the metric is measurable — methodology revived. CAVEAT-1 lifted for the RT metric; OF-3/SC-3 closes GREEN. (Marketing/landing refresh is a SEPARATE downstream phase — still gated, but the data answer is in.)
    5. **If Gate-B FAIL (D-11 — STOP, no auto-pivot/auto-park):** the RT metric is NOT a reliable coaching signal even with a clean opponent. This is a legitimate, final-class answer. Product can still ship on Gate-A (win-rate-only) per D-09. The user decides among: (a) park djok permanently, (b) pivot to win-rate-only product (drop the RT claim), (c) one more methodology iteration (e.g. different grouping unit / threshold / predicate). Do NOT auto-select.
    6. Sanity: any per-player median rt < 100ms must be flagged "investigate" in the verdict, not silently accepted.
  </how-to-verify>
  <resume-signal>If Gate-B PASS: type "approved: close OF-3 GREEN". If Gate-B FAIL: type your D-11 decision — "park", "pivot: win-rate-only", or "iterate: <what to change>".</resume-signal>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|-|-|
| analytics.db → gate script | Local read-only stats; no write to game data |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-|-|-|-|-|
| T-OF3-08 | Information disclosure | SteamID in gate SQL/groupby | mitigate | _coerce_sid + bound params; never pd.read_sql on sid columns (precision rule) |
| T-OF3-09 | Tampering | post-hoc threshold tuning ("moving goalposts") | mitigate | Thresholds LOCKED in Task 1 checkpoint, hardcoded with pre-run-locked comment before any computation (D-10) |

No network/auth/crypto surface. Pure statistical read of local DB. ASVS L1 V2/V3/V4/V6 N/A.
</threat_model>

<verification>
- Thresholds locked via Task 1 checkpoint BEFORE the run (D-10)
- Gate-A reproduces OF-1/OF-2 win-rate separation on clean data (D-09)
- Gate-B split-half reliability computed (r_full + CI95 + N), cross-player diagnostic reported (D-09/D-12)
- Gate-B FAIL => STOP checkpoint, user decides (D-11)
- OF-3-VERDICT.md written, SC-3 closed (CAVEAT-1)
</verification>

<success_criteria>
- of3_gate.py: Gate-A win-rate slices + Gate-B split-half reliability, duel_episodes only (D-16), no scipy/pd.read_sql
- Thresholds presented + approved before run (D-10), hardcoded with locked comment
- Gate-B FAIL routed to STOP + user decision (D-11), no auto-pivot/auto-park
- OF-3-VERDICT.md cites clean-data numbers vs OF-1 baseline; SC-3 measurability verdict written
</success_criteria>

<output>
After completion, create `.planning/phases/OF-3-revalidation-measurability-gate/OF-3-04-SUMMARY.md`
</output>
