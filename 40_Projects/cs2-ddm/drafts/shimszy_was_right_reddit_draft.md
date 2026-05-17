# Draft: «shimszy was right» Reddit post

**Target sub:** r/GlobalOffensive (primary), maybe cross r/cs2  
**Status:** DRAFT — DO NOT SHIP UNTIL grace fix verified + re-batched + numbers re-confirmed  
**Hook:** community-caught bug acknowledgment pattern

---

## Title options (pick one)

1. **A reddit user caught a bug in my reaction time tool — here's what I found**  
2. **shimszy was right: 133ms reaction delta was data quality, not biology**  
3. **My CS2 reaction tool had a 125ms floor artifact. Here's the fix and corrected numbers.**

**Recommended: #3** — concrete number in title = scan-readable, methodology-focused = matches r/GO substance audience.

---

## Body (English, post body — strip em-dashes, period/comma instead)

Last week I posted about m0NESY's mouse switch and claimed a 133ms drop in his mechanical aim phase. User `shimszy` commented:

> «133 ms is complete insanity. There's probably a data quality issue because that is closer to the gap between a nova and a pro than something possible with a hardware change.»

He was right.

When I went to validate the methodology before scaling, I queried the distribution shape across all 16 pros in my dataset. Found this:

```
player       N     min   p25   median   %@exactly_125ms
donk         294   125   125   156      43.5%
karrigan     189   125   125   <pending>33.3%
twistzz      177   125   125   <pending>24.9%
sh1ro        128   125   125   <pending>25.8%
... (all 16 pros pinned at 125ms minimum)
```

125ms = exactly 8 ticks at 64-tickrate (8 × 15.625ms). Across 1145 engagements, every "fast reaction" measurement landed on the same value. Not biology — a deterministic floor artifact.

**Root cause:** my T1 detector had a 120ms grace period added on top of two existing filters that already prevented micro-corrections from counting as aim start. Redundant safety filter created a structural cliff. <FIXED_GRACE_VALUE>ms is the fix (drops floor to <NEW_FLOOR>ms; aggregate medians shift down by ~<MEDIAN_SHIFT>ms).

**What changes:**
- T0→T1 (reaction phase) numbers shift downward. Real biology is faster than I reported.
- T1→T2 (mechanical phase) — unaffected by this bug.
- Crosshair-angle metric — unaffected.
- The m0NESY 133ms delta claim is still under-investigation with the corrected pipeline. New numbers when re-batch completes.

**What this means for the original m0NESY post:**
- The «203ms reaction unchanged Rio→Astana» claim was likely both values clipping at floor. Real delta probably exists but smaller magnitude.
- The «133ms mechanical drop» was real-direction but inflated by mismatch in N between samples (73 Rio vs 38 Astana, outlier tail dominating Astana mean).

**Methodology page** documents the bug + fix + audit log: <LANDING_URL>/methodology.html

**What I'm doing next:**
1. Apply fix
2. Re-batch top corpus
3. Update landing numbers
4. Re-run m0NESY analysis
5. Post corrected comparison

Thanks shimszy. This is exactly the critique that mattered — would have shipped to 10x more users with bad anchor numbers.

---

## First OP comment (post immediately, contains link)

For anyone curious about the tool itself or wanting their own demo split:

→ <LANDING_URL>/?utm_source=reddit&utm_campaign=shimszy_fix&utm_medium=organic

Year of solo dev. Free preview via DM, $5 for full report. Methodology page above documents what works + what doesn't.

---

## Image to attach (chart)

**Recommended:** distribution histogram showing the 125ms pinning. Bar chart, x = T0→T1 ms bins, y = count. Highlight 125ms spike vs natural distribution.

Alternative: before/after distribution comparison (current grace=120 vs fixed) once fix shipped.

---

## Pre-flight checklist before posting

- [ ] Grace fix committed + tested on 5+ demos
- [ ] Top corpus re-batched with fix
- [ ] m0NESY demos re-batched
- [ ] New numbers verified to NOT pin at any new tick floor (distribution shape check)
- [ ] Methodology page live on landing with shimszy credit
- [ ] Landing page anchor numbers (172ms donk, etc.) updated to corrected values
- [ ] Chart generated (distribution histogram)
- [ ] UTM link tested (lands on / with utm params passed through)
- [ ] Em-dashes removed from post body (anti-AI-slop signal)
- [ ] Pre-empted caveats included (per [[feedback_reddit_pre_empted_caveats_neutralize_critics_2026_05_16]])

---

## Tone guardrails

- DO acknowledge shimszy by username, link his comment
- DO be specific about what was wrong + what is fixed
- DO state new numbers without hedging once verified
- DON'T over-apologize / self-flagellate (one ackn line is enough)
- DON'T frame as «I'm so dumb» — frame as «community caught what I missed»
- DON'T leave bug unsourced — quote shimszy verbatim, link comment
- DON'T ship until all checklist items green

---

## Russian version (TG, after EN ships)

[Translate after EN published. Use CS-RU jargon convention per [[reference_cs_ru_jargon_convention_2026_05_15]]. Keep T0/T1/T2/peek as EN. Translate everything else.]
