# Eval Harness — Phase v2 Narrative Coaching Layer

This directory holds the evaluation harness that gates SC-1 (narrative quality), SC-4
(cost per report), and SC-6 (side-by-side delta vs v1). All ship/no-ship calls
for the v2 narrative layer route through these CSVs.

---

## 5 Rating Dimensions (D-17, 1-5 scale)

All five dimensions are weighted equally for the SC-1 ≥4.0 average gate. Each
dimension also has a per-dim floor of ≥3.5 (no single dim drags the average).

| Dim | What you are scoring | 1 (worst) | 3 (neutral) | 5 (best) |
|-|-|-|-|-|
| `factual_accuracy` | Are tier/percentile claims true vs the data shown in the report? | Multiple wrong tiers / wrong numbers | One minor slip; main claim correct | Every number and tier matches the tier table |
| `actionability` | Could a player actually act on this in their next session? | Vague platitudes ("just aim better") | One usable observation, no drill | Specific drill or VOD-watch instruction tied to a named weakness |
| `tone` | Does it match "brutally honest coach, no flattery, no hedging" (D-10)? | Sycophantic or hedge-everything | Mixed — some direct, some softened | Direct verdict, no "great job" filler, addresses player by name |
| `attribution` | When the narrative references a specific round/tick/demo, is the reference real and in `allowed_refs`? | Made-up rounds or ticks | Mostly correct refs, one fuzzy | Every numeric ref maps to a real top-moment row |
| `hallucinations` | **INVERSE — 5 = none, 1 = many.** Did the narrative invent players, maps, drills, or data points not present in inputs? | Several hallucinations | One marginal fabrication | Zero hallucinations; nothing said that isn't in the prompt context |

> **Watch out for `hallucinations`:** it is the only inverse dim. A score of 5 means
> "no hallucinations detected" — not "many hallucinations". This is to keep the
> ≥4.0 / ≥3.5 gate logic uniform (higher = better) across all five dims.

---

## SC-1 Hard Gate

The narrative ships only when:

- average score across all 5 dims × all 10 reports ≥ **4.0**
- AND each dim's own average ≥ **3.5** (per-dim floor)

If either gate fails, iterate `prompts/coaching_v2.md` and re-rate per D-18.

---

## SC-6 Side-by-Side Gate

Five players are rated head-to-head, v1 (tier table only, `no_narrative=True`)
vs v2 (tier table + narrative, `no_narrative=False`). For each pair the user
records both ratings on a 1-5 `would_pay_for_this` scale plus a `preferred_version`
(`v1` / `v2` / `neither`).

Ship gate:

- **v2 mean ≥ 4.0**
- **v1 mean ≤ 3.0**
- **delta (v2 − v1) ≥ 1.0**

All three must hold. If v1 is already at 3.5, narrative might be good but it
isn't differentiating the product, so ship is still blocked.

---

## Solo-Rater Limitation (D-16)

The v2 eval is single-rater (the user / project owner). No inter-rater
reliability check is performed. This is a known limitation:

- Quality gates reflect ONE person's calibration, not a panel.
- Drift over a long rating session is uncontrolled — rate in small batches
  with breaks if possible, and re-rate suspect rows.
- Re-rate the full set on every prompt change (D-18) so all scores share the
  same prompt context, not a mix of old and new outputs.

If/when a second rater becomes available, re-run the harness independently
and compare per-dim means. A delta >1.0 on any dim is a sign the rubric needs
sharpening before the next iteration.

---

## D-18 Re-Rate Workflow on Prompt Change

When `prompts/coaching_v2.md` changes (any byte), its `prompt_hash` changes,
and prior ratings tied to the old hash are stale. The harness handles this
by storing `prompt_hash` per row and only aggregating the latest hash in `score`.

Workflow:

1. Edit `prompts/coaching_v2.md`.
2. Re-run `python -m interpretation_narrative generate-eval-set` — overwrites
   the 10 HTMLs in `evals/generated/`.
3. Re-rate all 10 reports × 5 dims = 50 rows. The new rows carry the new
   `prompt_hash`; old rows remain in the CSV as an audit trail (D-19 dedup
   does NOT collapse across `prompt_hash`).
4. Re-run `python -m interpretation_narrative score`. The script picks the
   latest `prompt_hash` only.

---

## CSV Schemas (D-19, D-20)

**`evals/interpretation_v2_ratings.csv` (D-19):**

```
report_id, player_steamid, prompt_hash, dim, score, notes, rated_at
```

- Dedup key: `(report_id, prompt_hash, dim)` — re-rating the same dim on the same
  prompt overwrites. A new `prompt_hash` creates a new row (iteration history kept).
- `score` is `1..5` integer.
- `rated_at` is ISO-8601 UTC.

**`evals/v2_side_by_side.csv` (D-20):**

```
pair_id, player_steamid, preferred_version, v1_rating, v2_rating, notes, rated_at
```

- Dedup key: `(pair_id, player_steamid)` — re-rating a pair overwrites.
- `preferred_version` ∈ `{v1, v2, neither}`.
- `v1_rating`, `v2_rating` are `1..5` integers on the `would_pay_for_this` scale.

---

## 5-Step Workflow

```bash
# 1. Generate the 10 reports under evals/generated/v2_<name>.html
python -m interpretation_narrative generate-eval-set \
  --roster evals/v2_eval_player_roster.json \
  --out-dir evals/generated \
  --db analytics.db

# 2. Open each HTML, rate per dim. One CLI invocation per (report, dim) row.
python -m interpretation_narrative eval-rate \
  --report-id v2_donk \
  --player 76561198386265483 \
  --dim factual_accuracy \
  --score 4 \
  --notes "Spirit map identification correct, T0 wording sharp"

# 3. After all 10 × 5 = 50 rows entered, check the verdict
python -m interpretation_narrative score \
  --csv evals/interpretation_v2_ratings.csv

# 4. If FAIL, iterate prompt, re-generate, re-rate (D-18 full re-rate)

# 5. Run the side-by-side cycle for SC-6
python -m interpretation_narrative generate-side-by-side \
  --pairs 5 --out-dir evals/generated
python -m interpretation_narrative rate-side-by-side \
  --pair-id pair_001 --player 76561198386265483 \
  --preferred v2 --v1-rating 2 --v2-rating 5 --notes "..."
python -m interpretation_narrative score-side-by-side \
  --csv evals/v2_side_by_side.csv
```

---

## Cost Monitoring (REQ-9 / SC-4)

After each batch of LLM calls (whether eval generation or production reports),
check spend:

```bash
python -m interpretation_narrative cost-report --db analytics.db
```

The hard SC-4 gate is `avg_per_report ≤ $0.10`. Verified by:

```bash
python -m interpretation_narrative score-cost --db analytics.db
```

This exits 0 on PASS (avg ≤ threshold), 2 on FAIL. Use it as a pre-ship gate
in addition to SC-1 + SC-6.

The `cost-report` output also includes a 7-day rolling window so you can spot
sudden cost regressions (prompt growth, cache miss spike, model upgrade slip).
