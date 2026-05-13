---
project: cs2-ddm
domain: gaming
status: active
created: 2026-05-07
---

# Djok — CS2 Reaction Analysis

## What This Is

Инструмент для анализа CS2 демок, который разбивает реакцию на три этапа: T0 (враг стал виден по BVH-геометрии), T1 (игрок начал наводиться), T2 (первое попадание). Продукт Djok — для B2C игроков, которые хотят понять, что именно мешает им быть ближе к уровню лучших. Второй вектор — аналитика для профессиональных команд и научные статьи.

## Core Value

Не просто метрики — конкретный инсайт: что именно менять в тренировке, чтобы быть ближе к донку.

## Current State (v1.0 SHIPPED 2026-05-07)

End-to-end Djok delivery flow operational. Игрок может загрузить демо в Streamlit, получить отчёт с tier-классификацией каждой метрики, gap vs donk, и drill-рекомендациями — затем скачать offline-safe HTML report.

330 tests pass. SQLite schema стабильна. Public deploy + FACEIT URL auto-download → Phase 10.

## Requirements

### Validated

- ✓ BVH+AABB T0 detection (первый тик видимости врага через raycast) — Phases 1–3
- ✓ T0→T1→T2 декомпозиция реакции с RT в ms — Phase 3
- ✓ Bulk pipeline: автодетекция моментов из player_hurt — Phase 4
- ✓ Velocity classification (peek ≥50 u/s vs hold) — Phase 5
- ✓ Weapon filter (AWP/knife excluded) + enemy velocity gate — Phase 5b
- ✓ Crosshair angle at T0 (degrees off-target) — Phase 5c
- ✓ Kill-rate normalization (DuelAttemptFinder — hits + misses) — Kill Rate Feature
- ✓ CSV append/dedup pipeline — Phase 1
- ✓ Streamlit dashboard (базовая визуализация) — Phase 5
- ✓ T0 offset quality gate (reject outlier и overlapping windows) — Phase 6 (v1.0)
- ✓ Scale pipeline на 100+ игр стабильно (83 demos: 26 donk + 57 karrigan) — Phase 7 (v1.0)
- ✓ Интерпретационный слой: tier + plain-English + gap vs donk — Phase 8 (v1.0)
- ✓ Actionable рекомендации: worst-metric card + drill prescription — Phase 8 + 9 (v1.0)
- ✓ Side-by-side сравнение игрока с донком — Phase 8 (median-vs-median + Elite ceilings) (v1.0)
- ✓ Djok delivery: HTML report с brand-стилем + offline-safe + Download button — Phase 9 (v1.0)

### Active (v1.1 — TBD via /gsd-new-milestone)

- [ ] Public Streamlit deploy (Railway/Render) — Phase 10 SC1 (deferred from Phase 9)
- [ ] FACEIT match URL auto-download — Phase 10 SC2 (deferred from Phase 9)
- [ ] Profile-driven hot-path optimization — Backlog 999.2 (find_visible_enemies_at_tick BVH raycast + .tri shared mesh; close D-01 instrumentation gap first)

### Out of Scope

- Анализ по оппонентам (против каких врагов хуже/лучше) — отложено до валидации B2C
- Breakdown по картам/позициям — отложено, нужно больше данных сначала
- Корреляция с биометрией (Oura ring, сон) — отложено, дальний горизонт
- Real-time анализ во время игры — технически другая архитектура
- Team analytics для про-команд — отдельный продукт/тир, после B2C

## Context

**Откуда пришло:**
Гипотеза: разбивка реакции на T0/T1/T2 даёт инсайты, которых нет в существующих инструментах (HLTV, tracker.gg, etc.). Те показывают crosshair placement, time to damage и т.д., но игрок не понимает что конкретно менять. Первая живая валидация: анализ друга vs донк показал, что raw RT почти одинаковый, но crosshair angle и точность первых пуль — пропасть. Но "эврика" так и не наступила — нет интерпретации.

**Текущее состояние:**
- 6 матчей проанализировано (match_id 1–6, ~30 моментов)
- 215 тестов, все зелёные
- Два пайплайна: RT analysis + kill rate normalization
- Python CLI + Streamlit, нет веб-интерфейса

**Djok = B2C канал:**
Лендинг и early access flow уже существуют. Djok — это этот инструмент, не что-то отдельное.

**Научная статья:**
Может быть параллельным продуктом (100 игр донка → аналитический материал) и одновременно контент для маркетинга Djok.

## Constraints

- **Tech stack**: Python 3.14 + demoparser2 + awpy — не менять без необходимости
- **T0 detection**: BVH+AABB only — FOV-cone и m_bSpotted не работают в GOTV демках
- **Данные**: Только FACEIT/GOTV .dem файлы, CS2. Valve matchmaking демки не тестировались.
- **Solo**: Арыстан работает один, без команды — скорость важнее идеальной архитектуры
- **Validating before building**: не строить следующую фичу без доказательства что предыдущая приносит пользу

## Key Decisions

| Decision | Rationale | Outcome |
|-|-|-|
| BVH+AABB для T0, не FOV-cone | m_bSpotted не работает в GOTV; FOV даёт false positive при peeks | ✓ Верно — подтверждено на 11 моментах |
| T0-anchored kill rate (DuelAttemptFinder) | Hit rate на player_hurt не учитывает misses — искажает картину | ✓ Верно — feature merged |
| Interpretation layer как следующий приоритет | Без него игрок смотрит на метрики и не знает что делать | — Pending |
| Djok = B2C канал для этого инструмента | Лендинг уже есть, не надо строить новый | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-30 after GSD initialization*
