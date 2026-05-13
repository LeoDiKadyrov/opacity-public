---
type: входящее
tags: [inbox, session, cs2-ddm, marketing]
created: 2026-05-12
project: cs2-ddm
status: draft
---

# Session: 2026-05-12 — cs2-ddm

## Что сделано
- Стратегическое обсуждение маркетинговых углов: Malte (dormant), Monesy + смена мышки (strong)
- Определён news hook: Monesy mouse switch = органический reach (люди уже обсуждают)
- Спланирован естественный эксперимент: демо до PGL Astana vs демо с PGL Astana
- Defined метрики для case study: T0→T1, T1→T2, crosshair_angle, n per group, spread
- Выбран контент план: Reddit r/GO пост + RU Telegram сообщества (this week)

## Ключевые решения
- **Malte skip** — 4 дня без ответа = закрытие, не пауза. Нет consent на quote.
- **Monesy selection** — смена мышки типичная дискуссия в CS, но твой differentiator: метрики before/after (никто не мерит так)
- **Natural experiment setup** — две группы демо (pre-tournament vs tournament) позволяет isolate gear effect от tournament variance
- **Batch pipeline reuse** — используем существующий `bench/multi_player_batch_loop.py` для обеих групп, фильтруем results по monesy SteamID after

## Открытые вопросы
- Где найти monesy SteamID (csgostats.gg или Steam профиль)?
- Демки по обеим периодам в какой директории лежат? (for_analysis/monesy_pre_astana/ vs for_analysis/monesy_astana/)
- Есть ли video clip из турнира для Reddit поста (влияет на engagement)?
- RU Telegram сообщества — какие именно target (CS сообщества или broader gaming)?
