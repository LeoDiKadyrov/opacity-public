# OF-1 VERDICT — Outcome-First Validation Spike

**Date:** 2026-06-05
**Player:** donk (76561198386265483)
**Corpus:** `D:\Obsidian\opacity\40_Projects\for_analysis\spirit\` — 86 demos on disk, 81 used (5 had no donk events), 0 parse failures
**Artifact:** `outcome_first_spike_results.json` (4168 episodes + summary + gates)
**Script:** `outcome_first_spike.py` (standalone; no production module imported or edited — tripwire held, `git status` clean on ddm_analyzer.py / duel_attempts.py / t0_detector.py / config.py)

---

## Gate results

### GATE-1 — Opponent-truth rate: **PASS**

| | new (outcome-first) | old (geometry-first) |
|-|-|-|
| opponent anchored on real event | **100.0%** | 5.9% nominal-hit rate |

By construction: every episode starts from a `player_hurt`/`player_death` where donk is attacker or victim; the opponent is the other steamid **on the event**. BVH never selects the opponent. The 94% contamination class is structurally impossible here.

### GATE-2 — Win-rate plausibility: **PASS**

| | new | old |
|-|-|-|
| resolved win-rate | **56.7%** (N=2518: 1428 won / 1090 lost; 1650 unresolved) | 92.7% survival-proxy |

56.7% sits inside the 40–70% PASS band. Cross-check against physics-bounded reality: won=1428 ≈ donk's actual kill volume (81 maps × ~18 kills), lost=1090 ≈ his death volume; implied K/D = 1.31 — consistent with donk's known tournament K/D. Single-demo spot-check (spirit-vs-vitality-m3-dust2): won=17 = exactly his 17 kills, lost=16 = exactly his 16 deaths.

### GATE-3 — Interpretable slice: **PASS**

| slice (win-rate among resolved) | win% | N |
|-|-|-|
| opponent initiated (donk holds/counters) | 51.9% | 1267 |
| donk initiated (peeks first) | 61.6% | 1251 |

**Separation = 9.7 pp** (~5σ at these N; per-bucket SE ≈ 1.4 pp). Old slices showed zero separation. The direction is interpretable and matches donk's known profile as an aggressive entry: he wins MORE when he initiates. Aux slice is even stronger and sanity-consistent: landing the first hit → 84.6% win (N=1353) vs conceding it → 24.3% (N=1165).

---

## VERDICT: **GO** — all three gates PASS. OF-2 may be planned.

## What OF-2 must do (one paragraph, NOT started this session)

Make outcome-first the production duel path: episodes anchored on `player_hurt`/`player_death` (the spike's `collect_exchanges` + `group_episodes` logic, productionized), deprecate the geometry-first opponent guess (`DuelAttemptFinder._process_cluster` → `find_first_visible_enemy_in_window` as opponent *selector*), keep `t0_detector.find_t0(known_enemy)` strictly for backward reaction search on the KNOWN opponent. TDD per project convention (Wave-0 RED tests first), new schema columns for ground-truth opponent + outcome + initiator, and the `_coerce_sid` string-path steamid coercion everywhere (see Found-bug below).

## Caveats carried forward (mandatory)

- **CAVEAT-1 stands.** Opponent-identity fix ≠ methodology validity. DDM closed RED 2026-05-12 (1/30 stability). OF-3 MUST re-run a measurability/stability gate before any coaching/marketing claim. A clean opponent does not imply a shippable metric.
- **Unresolved = 40%** (1650/4168). Exchanges with no death inside the episode window: utility chip damage, disengages, traded-by-teammate. v1 applies no weapon filter — `player_hurt` includes HE/molotov chip. OF-2 should add a weapon/context filter and decide the unresolved bucket's semantics; the gate metrics above are computed on resolved episodes only and are robust to this.
- **Initiator is fire-based, lookback 128 ticks**, falls back to first hit. weapon_fire has no target → some attribution noise. Slice survives it at 5σ; OF-2 can refine with visibility/positioning.

## Found bug worth keeping (spike side-product)

Run 1 produced garbage (win-rate 30.8%, won=487, median hits 0.0) because `pd.to_numeric` on `attacker_steamid` columns containing `None` (world damage) silently produces float64 → 17-digit SteamID precision loss → all donk-as-attacker rows dropped. Fixed via string-path coercion; self-check now uses real 17-digit ids + a None row. Any OF-2 code touching steamid columns must use the string path. Same disease class as the known `pd.read_sql` gotcha.

## Stop-rule honored

This was the single allowed validation loop (CAVEAT-2). Gate decided on the first valid run after one in-session bug fix — no "one more capture" spiral. OF-2 is authorized for PLANNING only; it was not started in this session.
