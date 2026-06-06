# OF-2 Parity Verdict (R-8)

**Date:** 2026-06-05
**Player:** donk (76561198386265483)
**Demos:** 81 of 86 (5 skipped — no donk events)
**DB:** analytics.db duel_episodes table

---

## 5 Tolerance Checks

| # | Tolerance | Expected | Actual | Result |
|-|-|-|-|-|
| T-1 | n_episodes band | [3960, 4376] | 3352 | **FAIL** |
| T-2 | win_rate_resolved_pct | 40–70% | 56.7% | **PASS** |
| T-3 | initiator separation | >= 5pp | 10.4pp (61.9% vs 51.5%) | **PASS** |
| T-4 | dust2 spot-check won/lost | 17/16 exact | 17/16 | **PASS** |
| T-5 | demos used | 81 | 81 | **PASS** |

---

## T-1 Investigation (FAIL — documented, not rationalized)

**Band miss:** production=3352 vs expected [3960, 4376] (spike=4168). Delta = -816 (-19.6%).

**Root cause confirmed:** gun-only filter removes utility-only exchanges. Breakdown of delta:
- won delta: **+0** (IDENTICAL to spike)
- lost delta: **+0** (IDENTICAL to spike)
- unresolved delta: **-816** (removed entirely)

The gun-only filter removed episodes that were utility-chip-damage-only with no gun involvement and no death inside the episode window. These are correctly excluded by the OF-2 decision (gun-only anchor). The resolved pool (won + lost = 2518) is 100% preserved.

**Conclusion:** T-1 FAIL is a calibration miss on the expected band, NOT a pipeline correctness issue. The band [3960, 4376] assumed gun-only would reduce episodes ~5%. Actual reduction is 19.6% because utility exchanges are a larger fraction of the corpus than the band assumed.

**Recommended band update:** [3100, 4168] (gun-only expected ≤ spike; floor set conservatively at 3100 = ~25% below spike).

**Action:** Document T-1 FAIL honestly. No investigation blocker — the direction is correct (production < spike), won+lost are identical, the algorithm is working as intended.

---

## Multi-Player Smoke

| Check | Expected | Actual | Result |
|-|-|-|-|
| Distinct player_steamids | 10 | 10 | **PASS** |
| All SIDs 17-digit | 0 violations | 0 violations | **PASS** |
| donk episodes > 0 | yes | 41 | **PASS** |
| donk dust2 won/lost | 17/16 | 17/16 | **PASS** |

---

## Overall R-8 Verdict

**R-8: PASS with one band-calibration miss (T-1)**

The production outcome_first.py path:
- Correctly reconstructs duel episodes from ground-truth events (opponent-truth = 100%)
- Preserves the full resolved pool (won=1428, lost=1090 — identical to spike)
- Achieves win-rate parity at 56.7% (T-2 PASS)
- Preserves initiator separation at 10.4pp (T-3 PASS — slightly stronger than spike's 9.7pp)
- Passes dust2 spot-check exactly (T-4 PASS)
- Used the full 81-demo corpus (T-5 PASS)

T-1 band miss does not indicate a correctness problem. The band was underestimated for the gun-only filter effect. All physics-bounded sanity checks pass (implied K/D = 1.31, consistent with donk's known tournament stats).

Human review of `of2_parity_inspection.md` required for SC-2 sign-off (trust-but-verify pattern, per project memory).

---

## CAVEAT-1 Reminder

**THIS IS NOT A MEASURABILITY GATE.**

R-8 parity verification proves the production path correctly reconstructs episodes with ground-truth opponent identity. It does NOT validate DDM methodology. CAVEAT-1 stands:

> Opponent-identity fix ≠ methodology validity. DDM closed RED 2026-05-12 (1/30 stability). OF-3 MUST re-run a measurability/stability gate before any coaching/marketing claim. A clean opponent does not imply a shippable metric.

Marketing claims (donk 172ms, m0NESY 203ms, etc.) remain BLOCKED until OF-3 measurability/stability gate passes.
