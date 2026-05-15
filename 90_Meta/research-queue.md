---
type: meta
tags: [research, queue, evergreen-worker]
created: 2026-05-12
---

# Research Queue

Кормит `evergreen_research_worker.ps1` (DAILY 10:00). Worker берёт первый unchecked item, websearches, пишет note в `20_Evergreen/`, отмечает done.

**Добавлять topic'ы:** `- [ ] {описание темы}`. Конкретные topic'ы > общие. Worker лучше работает на narrow questions, не на «прочитай всё про X».

## Active queue

- [x] Lazarus modes concept graph — как Александр Ярцев в MentalTech Lab его моделирует, как соотносится с Психодемия модулем
- [x] Faktura DBO knowledge base patterns — какие типы вопросов от банков повторяются в 70+ имплементациях, как chromaDB структурировать
- [ ] Nippard fatigue management — научный consensus по recovery markers для 5×/week split, что мерить помимо subjective RPE
- [ ] Cs2-ddm scientific framing — какие peer-reviewed работы по reaction time analytics в esports существуют, что заявка про T0→T1 split добавляет к literature
- [ ] Boyd Varty tracking method — что из core principles переносимо на product/career exploration без metaphor inflation
- [ ] КПТ vs ППК evidence base — где они конвергируют, где расходятся, что Психодемия cohort должен понимать о различиях
- [ ] Solo founder $200/mo MRR patterns — кейс-стади who actually achieved this in 30 days, без paid traffic
- [ ] ИИС-А налоговый вычет 2026 — actual rules, limits, что меняется этим годом

## Completed (worker marks)

_Worker move completed items here — auto._

## Notes

- Worker default tone: RU, density-first, anti-AI scan applied
- Average note length ~500-700 слов
- Worker НЕ создаёт сразу 5 notes — one per day, чтобы quality stay reasonable
- Если хочешь priority — поставь topic первым в queue
