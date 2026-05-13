---
type: lead_magnet_outline
product: ЦР Insider PDF
tags: [revenue, content, lead-magnet, C-cat]
created: 2026-05-09
target_launch: 2026-05-22 (week 2 end)
target_revenue: $25-50 × 4-8 sales = $100-400 first 2 weeks
sales_channel: gumroad / boosty / direct (TG-канал + LinkedIn pinned)
nda_constraint: НИКАКИХ имён банков, конкретных сделок, тех. деталей ЦР
---

# ЦР Insider PDF — outline

## Concept

Не "что такое ЦР" (это есть в Wiki/CB-papers). Не "учебник по технологии" (NDA не позволит).

**Содержание:** **мета-наблюдения** Implementation Manager-а — что происходит на стыке банка и ЦБ при подключении. Реакция банков, паттерны провалов коммуникации, кто въехал, кто нет, что повторяется в 70+ имплементациях.

Аналог: "What I learned implementing X across 70+ banks" — не "X works like this," а "here's what implementing X teaches you about institutional behavior."

**Buyer persona:**
- Fintech-product manager / тех-директор / consulting analyst
- Хочет понять что ему ждать когда его банк начнёт ЦР
- Готов платить $25-50 за 30-страничную выжимку 12 месяцев чужого опыта
- НЕ конкурент Faktura/ЦФТ — клиентский сегмент

## Title options

1. **"ЦР: 70 банков, один паттерн. Что выяснилось при имплементации Цифрового рубля"** (data-anchor)
2. **"Implementation Manager Цифрового рубля: 12 месяцев, 70+ банков, без NDA"**
3. **"Цифровой рубль не для рассказов. Insider-наблюдения о том, как банки реагируют на новую инфраструктуру"**

Recommended: #1 — числа first, no marketing tone.

## Length & format

- 30-40 страниц A4 (~12000-15000 слов)
- PDF + EPUB
- Cover простой типографичный, не дизайн
- Цена $25 launch / $35 standard / $50 если будут просить enterprise license

## Structure (10 sections + appendix)

### Front matter
- Title page
- About author (1 page) — кто я, не зачем покупать
- Disclaimer NDA (1 page) — explicit что НЕ будет

### 1. Setup: что такое ЦР для банка (3 pages)
- Не учебник. **Угол:** что банк должен поменять operationally чтобы поддержать ЦР.
- 3 категории требований: технические, процессные, regulatory.
- "Что банки думают перед тем как начать" vs "что они узнают за 2 месяца."

### 2. 3 типа реакций банков на анонс подключения (4 pages)
- **Тип A — рапид.** "Сделаем за квартал, выкатываем." Реальность: 6 месяцев минимум, всегда.
- **Тип B — отрицание.** "Это не критично, делаем когда дойдёт очередь." Через 3 месяца паника.
- **Тип C — паралич.** "Мы не понимаем, давайте подождём что сделают другие."
- Распределение по 70+ банкам: ~20% / ~50% / ~30%.

### 3. HR-вопрос как индикатор зрелости (2 pages — переработка LinkedIn пост #1 идеи)
- 3 типа HR-вопросов = красный флаг
- 2 типа = банк въехал
- Что это говорит про organizational maturity

### 4. Где банки теряют 80% времени имплементации (5 pages — переработка LinkedIn пост #2)
- 3 категории monkey-work которые повторяются у всех 70+
- Что не повторяется и где нужен мозг
- Гипотеза почему отрасль не автоматизирует
- Конкретные паттерны без имён

### 5. Communication breakdowns (4 pages)
- 5 точек где общение ЦБ ↔ банк ↔ интегратор ломается
- Как это видно по симптомам в чатах/звонках
- Что обычно стоит за паттерном (это не "плохие люди" — структурное)

### 6. Кто принимает решения внутри банка (3 pages)
- Карта стейкхолдеров (CRO, CIO, retail product, ops, compliance)
- У каждого свой агенда
- Кто блокирует, кто ускоряет, кто фигурирует в звонках но не имеет голоса

### 7. Регуляторное окно (3 pages)
- Чем regulator (ЦБ) реально отличается от обычного клиента
- Какие требования двигаются после deployment-а
- Как банки справляются с тем что spec эволюционирует во время имплементации

### 8. Что повторяется во всех 70+ (4 pages — flagship глава)
- 7 universal паттернов
- Каждый с примером без имён
- Каждый с **as-if советом**: "если ты CTO в банке который начинает — вот на что смотри"

### 9. Что НЕ повторяется (2 pages)
- Где разнообразие реальное
- В чём команды-чемпионы отличаются от middle-pack
- Что не масштабируется как best practice

### 10. Что я бы сделал иначе если бы запускал банк-внедрение (3 pages)
- 5 принципов из 12 месяцев observation
- Не "best practices" — **opinions** с указанием что они opinion

### Appendix A — глоссарий (2 pages)
- 20-30 терминов которые используются в книге
- Без отсылок к non-public документам

### Appendix B — что почитать (1 page)
- Public CB-papers, BIS-research, академические работы
- НЕ внутренние Faktura/ЦФТ материалы

## Voice constraints

- Tool, formal-grounded (LinkedIn voice mode)
- Brutal honesty про industry — yes
- Self-deprecation — modest, не overblown
- Никаких "I'm a 25-year-old who somehow ended up here" историй
- Numbers anchor everywhere (70+, 80%, 12 месяцев, etc)
- Никаких призывов к действию typа "запишись на консультацию!" — пусть текст работает

## NDA-safe checklist (для каждой главы)

- [ ] Нет названий банков
- [ ] Нет конкретных дат сделок
- [ ] Нет внутренних product names ЦФТ/Faktura
- [ ] Нет цифр объёмов транзакций
- [ ] Все паттерны сформулированы как "this is observable across N participants" а не "this is what X did"
- [ ] Нет цитат из не-публичных встреч
- [ ] Disclaimer о том что content — observations + opinions, не consulting advice

## Distribution

| Channel | When | Format |
|-|-|-|
| LinkedIn pinned | day of launch | "Вот PDF про implementation 70+ банков. Ссылка." |
| Telegram канал | day of launch | "выкатил pdf — что я вынес из 12 месяцев импл-я. Ссылка." |
| LinkedIn DM (Tier 2 outreach contacts) | day +1 | "если откликаешься на наблюдения — вот развёрнутая версия в pdf" |
| TG fintech чаты | day +3 | sample chunk + link |
| X в EN | day +7 | "I implemented digital ruble across 70+ banks for 12 months. Wrote a PDF." (EN summary, не translation) |

## Pricing tiers

| Tier | Price | What |
|-|-|-|
| Standard | $25 | 30-page PDF, EPUB |
| Plus | $50 | + 1-hour 1-on-1 call (limit 5 в первый месяц) |
| Enterprise | $200 | + 4-hour deep workshop с командой (limit 1 в первый месяц) |

## Post-launch tracking

| Метрика | Target Week 2 | Target Week 4 |
|-|-|-|
| Page views | 200+ | 500+ |
| Sales Standard | 4 | 10 |
| Sales Plus | 1 | 2 |
| Inbound DM | 3 | 8 |
| New LinkedIn followers | 30 | 80 |

If <2 sales by 5/30 — pricing wrong или distribution wrong, не contents.

## Risks

- **NDA escalation.** Если кто-то из ЦФТ/банк увидит и интерпретирует как утечку — нужна exit strategy. Mitigation: каждая глава анонимизирована до уровня "publicly observable patterns from N>5 instances."
- **Faktura HR/legal questions.** Не запрашивать разрешение — это не их конкуренция. Но иметь готовый ответ: "Personal observations + publicly available info, no internal data, no client names."
- **Низкий conversion.** Тогда $200 трек проваливается, opt 1 (consulting) становится primary.
