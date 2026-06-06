# OF-1-00 SUMMARY — Outcome-First Validation Spike

**Executed:** 2026-06-05, inline (gsd-sdk CLI absent per plan's execution_context)
**Result:** **GO** — all 3 gates PASS. See `OF-1-VERDICT.md`.

## What was built

- `outcome_first_spike.py` — standalone outcome-first duel reconstructor (repo root, uncommitted at time of writing):
  - `collect_exchanges()` — all `player_hurt`/`player_death` where P is attacker or victim; opponent = other steamid on the event (ground truth, never BVH).
  - `group_episodes()` — same-opponent events grouped into episodes, gap > 320 ticks (mirrored `_KILL_CONFIRM_WINDOW_TICKS`) or opponent change starts new episode.
  - Outcome from death ordering: won (E died first) / lost (P died first) / unresolved.
  - Initiator from `weapon_fire` 128-tick lookback, fallback first-hit attacker.
  - `--self-check` (synthetic 3-episode case with real 17-digit sids + None row), `--gate` (re-print gates from json), full-run CLI.
- `outcome_first_spike_results.json` — 4168 episodes, summary, gates (repo root).
- No production module touched (tripwire held).

## Gate numbers (donk, 81 demos)

| Gate | New | Old baseline | Verdict |
|-|-|-|-|
| GATE-1 opponent-truth | 100% | 5.9% | PASS |
| GATE-2 resolved win-rate | 56.7% (N=2518) | 92.7% proxy | PASS (40–70% band) |
| GATE-3 holder vs initiator | 51.9% vs 61.6% = 9.7pp (~5σ) | no separation | PASS |

Cross-checks: won=1428 ≈ donk kill volume, implied K/D 1.31; single-demo exact match (17/16 vs kills/deaths).

## Deviations from plan

1. **Corpus narrowed to spirit/** (86 demos) instead of full `for_analysis` root (225): non-spirit demos contain no donk events (verified — first 27 all skipped), full root risked the 10-min background timeout for zero information gain. 81 used = exactly the roadmap's "donk's 81 demos".
2. **In-session bug fix (run 1 invalid):** `pd.to_numeric` on steamid columns with `None` → float64 → 17-digit precision loss → donk-as-attacker rows all dropped (run 1: win-rate 30.8%, won=487). Fixed `_coerce_sid` to string-path coercion; self-check hardened. Run 2 = the valid run. Documented in VERDICT + memory (`feedback-to-numeric-none-corrupts-steamids-2026-06-05`).
3. **Reaction timing (find_t0 backward search) not added** — plan marked it OPTIONAL for v1; GATE-3 passed on initiator slice without it.

## Next

- OF-2 (core rebuild) is AUTHORIZED FOR PLANNING — not started this session per CAVEAT-2.
- CAVEAT-1 unchanged: OF-3 measurability/stability gate mandatory before any claim.
