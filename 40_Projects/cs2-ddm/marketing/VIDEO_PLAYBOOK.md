# Djok Video Playbook

Voice + structure contract for `/video-weekly` skill. Read alongside `MARKETING_PLAYBOOK.md`. This is NOT optional reference — it gates every draft the skill produces.

---

## Voice profile (distilled from 4 references)

| Slice | Reference | Take this |
|-|-|-|
| Frame | RachelR | Working professional, not founder-influencer. «Год задрот это делал, потому что меня зацепило» |
| Pace | MahoneTV | Slow, data-anchored, multi-POV breakdown. NOT TikTok-rush in long-form |
| Strategic depth | Ash's Playbook (ex-GamerLegion coach) | «Что игрок делает → что должен → почему мостик» — coaching frame, not highlight |
| Honesty + status awareness | Эрик Шопов | «Это не работает», «sample мал», «DDM отвалился». Status without posturing |
| **DROP** | Эрик (subset) | Snap judgements without data anchors. ALL claims = anchored in numbers / demos / sources |

### Anti-patterns (banned voice)
- Founder-influencer voice: «let me tell you why», «here's the secret», «we revolutionize», «10x your aim»
- Guru framing: «If you're like most players...», «We've all been there»
- Generic motivation closes: «Stay tuned», «Keep grinding», «You got this»
- Hey-guys openings: «Hey what's up everyone», «Привет, ребят, сегодня поговорим о...»
- Sub-baiting: «Like, comment, subscribe», «Smash that bell»
- Snap judgement without data: «Leetify is bad» (allowed: «Leetify Time to Damage = end-to-end. Djok splits perception/execution because [reason with number]»)

---

## Hook Intensity (HI) requirements — first 3 seconds

Every short-form video MUST have all three vectors in 0:00-0:03:

1. **Audio cue** — specific phrase OR sound trigger (NOT generic music swell). Examples:
   - «Donk видит врага за 172 миллисекунды. Ты — за [твоё число]»
   - «Я год писал инструмент, который мне самому не помог сначала»
   - Sound effect = single demo gunshot or tick metronome (NOT royalty-free «epic» drop)

2. **Visual trigger** — dynamic motion OR sharp cut in <1s. Examples:
   - Demo replay frozen at T0 frame with crosshair overlay
   - Dashboard screen-rec scrolling to a stat
   - Face-cam quick-cut with on-screen number anchor

3. **Text overlay** — key claim duplicated on screen. NOT decorative. Reader gets the hook without sound. Examples:
   - `donk: 172ms · ты: ?`
   - `год соло. вот что не работает.`
   - `Leetify Time to Damage = 1 число. Djok = 3 фазы.`

If a hook fails any vector → rewrite before filming.

---

## Hybrid G long-form template (12min)

Use for Long #1 (foundational). Then iterate based on data signals.

```
0:00-0:30  HOOK (HI required)
           - audio: hard number или vulnerable anchor
           - visual: demo T0 frame OR dashboard scroll
           - text: claim on screen
           Example: «Я год писал инструмент для CS2.
                     Не для себя. Потому что никто не смотрел на это.»

0:30-2:00  JOURNEY OPENING (RachelR frame)
           ⚠️ ВАЖНО: мотивация — научная любопытность, НЕ "я застрял L8-9". Не использую
           инструмент для своего аима. Меня зацепило что никто не делал T0→T1 разделение,
           хотя данные лежат в каждом .dem файле.

           - что зацепило: реакция всегда измерялась одним числом — T0→T2. Но это 3 разные
             фазы с разными механизмами. Никто не смотрел отдельно. Казалось очевидным что там
             есть сигнал — полез проверять.
           - кого смотрел / читал (MahoneTV разборы, Ash's coaching, Эрик про "посмотрю демку,
             пойму ошибку") — они читают демки руками, я хотел это формализовать
           - почему соло год — не "я disruptor", а "никто не делал T0→T1 split, значит самому"

           ЗАПРЕЩЕНО в JOURNEY OPENING:
           - "я застрял на L8-9"
           - "Leetify не давал ответ ПОЧЕМУ"
           - "мне самому не помог"
           - любое "я решал свою проблему" — это выдуманный нарратив

2:00-8:00  PRODUCT MECHANICS (MahoneTV pace)
           - демка как ground truth (BVH+AABB ray к 8 углам hitbox enemy)
           - почему 3 фазы: T0 (visible) → T1 (aim start) → T2 (first hit)
           - что они значат для игрока (T0→T1 = perception, T1→T2 = execution; разные drills)
           - данные: donk 172ms / 312ms / 5.2° (n=448), karrigan 203ms / 344ms / 5.8° (n=224)
           - dashboard screen-rec: report.html walkthrough на pro demo

8:00-10:00 HONEST ROADMAP (Эрик filter — без snap judgement)
           - DDM coaching метрика валидировалась RED 2026-05-12, я её дропнул (объясни ПОЧЕМУ: 1/30 STABILITY pass на pc4, binary Pc + EZ noise floor)
           - sample n=2-4 в hold engagements = не показываю Elite badges на этих
           - drills prescription = speculative right now. метрики мы измеряем хорошо, drills я ещё research
           - инструмент = ранняя альфа соло разраба

10:00-12:00 CTA (Ash coaching frame, NO sub-baiting)
            - free batch run для первых N (Cybershoke loss-leader pattern)
            - ссылка landing (https://djok... — Arystan put actual)
            - «пришли .dem, я разберу за 48h. бесплатно для первых.»
            - end: data frame на экране (donk number + ты vs его + landing URL)
```

### Длина обоснование
- 12min = в зоне комфорта RU CS2 long-form audience (Юра Fad/Эрик 50min, но они уже бренды; unknown creator должен быть < 15)
- Watch-through expectation для unknown: 25-35% (vs 3-7% на 1.5h)
- НЕ 1.5h одно видео — это wrong call до audience awareness build

---

## Short-form hook formats (7 candidates)

Each format anchored к Djok data. Cycle through in 4-week phase, log which format performs per platform.

| # | Format | Hook example (RU + EN) |
|-|-|-|
| H1 | Pro-anchor compare | RU: «Donk видит врага за 172мс. Ты — за?» EN: «Donk sees enemy in 172ms. You: ?» |
| H2 | Tool-disambiguation | RU: «Leetify даёт 1 число. Я делю на 3 фазы. Вот зачем.» EN: «Leetify: 1 number. Djok: 3 phases. Here's why.» |
| H3 | Vulnerability/build-in-public | RU: «Год соло на этом. Вот что не работает.» EN: «Solo built this for a year. Here's what doesn't work.» |
| H4 | Technical-curiosity | RU: «BVH-рейкаст к 8 углам hitbox-а. Зачем такое для CS2.» EN: «BVH raycast to 8 hitbox corners. Why CS2 needs this.» |
| H5 | Case-study | RU: «Monesy сменил мышь после PGL. Я померял T0→T1 до и после.» (Monesy ready: scoped, demo corpus pending) |
| H6 | Pro-disagreement | RU: «Karrigan медленнее donk-а на 31мс. И всё равно играет в FaZe. Вот почему это OK.» |
| H7 | Honest-failure | RU: «Я померял DDM coaching метрику. RED. Объясняю почему дропнул.» |

### Hook format DON'Ts
- «You won't believe what I found...»
- «5 ways to improve your aim»
- «POV: you're stuck in L8»
- Question-rhetorical openers без immediate payoff

---

## Demo footage rules

### Allowed b-roll sources
1. **Pro demos** (donk, karrigan, sh1ro, frozen, Monesy when corpus ready) — `analytics.db` backed, real numbers, attribution shown on screen
2. **Dashboard screen-rec** — Streamlit Interpretation tab, `report.html` scroll, SQLite query результат
3. **Personal journey artifacts** — что вдохновило (MahoneTV/Ash/Эрик YouTube embeds with attribution), статьи/papers которые читал, ранние scribbles в Obsidian, git log из cs2-ddm
4. **Anonymized client demo** — future inbound WITH EXPLICIT recorded consent. Malte (2026-05-08 inbound) = NO consent received (4-day silence per `Malte Contact Closure` memory) → do NOT reuse his demo, quote, or analysis as b-roll.

### Forbidden b-roll
- **Arystan-as-player gameplay** — это НЕ brand frame. Ты coach/analyst, не pro-aspirant.
- Aim trainer footage (Kovaak's, Aim Lab) — wrong frame, мы про real demo not synthetic test
- Other people's content without source label / consent
- AI-generated voiceover (HeyGen, Synthesia, ElevenLabs cloned) — anti-pattern для CS2 trust building. Эрик-rule: face wins faceless.
- AI avatars on screen
- Stock b-roll without label (`stock: pexels` overlay OK if used)

---

## Channel matrix

### Short-form (cycle 6/week × 4 weeks)
| Platform | Format constraints | Captions | Cadence first cycle |
|-|-|-|-|
| YouTube Shorts | 60s max, vertical 9:16 | Submagic burned-in | 2/week |
| TikTok | 60-90s, vertical 9:16 | Submagic | 2/week |
| Instagram Reels | 60-90s, vertical 9:16 | Submagic | 2/week (cross-post) |
| X (Twitter) video | 2:20 max, square or 9:16 OK | Optional native | 1/week (best-performing cut) |
| Reddit r/GO clip | 60-120s, embed in comment OR self-post | Optional | 1/week (data-rich format only) |
| RU TG community chats | 30-60s, vertical OK | RU burned-in | 1/week (NEVER `kdrvarystanos`) |

### Long-form
| Platform | Format | Cadence |
|-|-|-|
| YouTube main channel | 10-15min horizontal 16:9 | 1/2 weeks first cycle (2-3 per 4-week phase) |
| RU YT секция | same upload, RU description + tags | same |
| TG embed | YT link in community chats post-publish | per long |

---

## Gates 6-9 (encoded in `/video-weekly` Step 3.5)

These extend Gates 1-5 from `/marketing-weekly`. Drafts failing any gate get rewritten in-context before file write.

### Gate 6 — Hook Intensity (HI) check
Every short-form draft AND long-form 0:00-0:03 must have:
- ✅ Audio cue specified (verbatim phrase OR sound trigger)
- ✅ Visual trigger specified (dynamic motion / sharp cut <1s)
- ✅ Text overlay specified (claim text + on-screen duration)

If any vector missing → REWRITE hook before draft ships.

### Gate 7 — Emotional Resonance (ER) check
Draft must have at least ONE of:
- Vulnerability anchor («не работало», «дропнул», «не знал»)
- Status-aware honesty («sample мал», «соло», «ранняя альфа»)
- Coaching empathy («ты застрял на L8, не потому что aim, а потому что perception lag — вот доказательство»)

Generic emotional manipulation («imagine if», «picture this») = FAIL.

### Gate 8 — Script Clarity (SC) check
- Reading level ≈ 8th grade RU/EN (no jargon walls)
- BUT technical terms (BVH, AABB, T0→T1, peek/hold engagement) allowed if defined inline on first use
- Sentence length: avg ≤ 18 words. NO multi-clause comma-trains.
- Numbers always with unit (ms, °, n=)

### Gate 9 — Novelty check
- Compare к marketing/log.md video section (Agent V1 history)
- If draft hook pattern + topic combo appeared in last 4 weeks → FAIL → choose different combo
- First-cycle pass: all 6 short-form drafts must use DIFFERENT hook format (H1-H7)

---

## Personal-journey frame (RachelR style)

Long #1 specifically uses this — but applicable to vulnerability shorts (H3).

### Frame rules
- **Working professional, not founder-pitching**. «Я год писал это» NOT «I'm building the future of esports analytics»
- **Show artifacts**: что читал (MahoneTV embed snippet), что копал (git log), что не работало (DDM dropped commit)
- **Status delta admission**: куда хочу прийти (≠ Faktura long-term, ≠ generic SaaS founder) и где сейчас (соло, ранняя альфа, 1 inbound client). Это Эрик-pattern «моя команда худший проект» applied honestly.
- **NO ego footage**: ни моих gameplay highlights, ни моих стримов, ни моих speaking gigs

### Inspirations to NAME on-screen (with attribution)
- MahoneTV — глубокие разборы, многоплановые POV
- Ash's Playbook — coach frame, «что игрок должен делать»
- Эрик Шоков / OFFSTAGE — community-builder honest model
- RachelR — обыденность необыденно, working-professional aesthetic

Attribution = on-screen text + spoken mention. NEVER recycle their footage without consent/fair-use justification.

---

## Loss-leader CTA pattern (Cybershoke-derived)

Эрик раздал 2500 годовых premium subs → 90% retention. Apply to Djok early-access:

- **First N inbound**: free batch run on 10-20 demos («for being first», loyalty build + n grows without $5 friction)
- **Consent ask**: anonymous / initial-only quote consent for landing testimonial section
- **No bait-and-switch**: state up-front it's free for first N, not «limited time offer»

Validated 2026-05-08 with Malte (1 free batch delivered, no paid conversion, no consent for testimonial reuse). Reuse pattern in CTAs but do NOT cite Malte by initial or anonymized handle until explicit consent recorded.

---

## When to update this playbook

After every 4-week video cycle, review `marketing/log.md` video section. If a hook format from H1-H7 fails 4+ times across platforms → mark `DEPRECATED` here. If new format emerges from data → add as H8+.

Voice profile / banned anti-patterns updated only with explicit user direction. Don't drift.
