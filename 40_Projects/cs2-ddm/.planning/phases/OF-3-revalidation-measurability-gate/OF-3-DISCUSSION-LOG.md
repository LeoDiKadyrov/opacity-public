# Phase OF-3: Re-validation + Metric + Measurability Gate - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-10
**Phase:** OF-3-revalidation-measurability-gate
**Areas discussed:** T1 redefinition (B-5 fix), T0 backward search, Метрика + gate-критерии, Re-batch scope + схема данных

---

## T1 redefinition (B-5 fix)

| Option | Description | Selected |
|-|-|-|
| ≤3° + sustain 2 тика | T1 = первый тик dist≤3° И держится ещё 2 тика (overshoot-защита) | (delegated) |
| ≤3° без sustain | Первый тик dist≤3°, точка | |
| ≤3° и держит до T2 | Строгий lock — риск нового censorship | |

**User's choice (verbatim):** «мне нужно, чтобы было использовано решение, которое сделает так, чтобы основная методология t0->t1->t2 заработала, поэтому выбирай то, что считаешь, что реально исправит ситуацию и оживит проект» — predicate delegated to Claude; starting default = ≤3° + sustain 2 тика, validated by distribution shape.

- Порог fixed-3° vs distance-scaled → **«Claude решает по данным»** (оба варианта на 1 демо, выбор по форме распределения)
- Прицел не дошёл до порога к хиту → **Label + NaN в БД** (`t1_source="never_landed"`)
- Старый `_detect_t1`/engagements-путь → **Новый детектор в episodes-пути, старый DEPRECATED**

---

## T0 backward search

| Option | Description | Selected |
|-|-|-|
| Visibility-run backward + cap | T0 = первый тик непрерывного рана видимости; долгая видимость = label | (leaning) |
| Фикс-окно назад | Риск нового floor-артефакта (урок B-1) | |
| Claude решает | Ресёрчер проверяет оба на данных + цене | ✓ |

**User's choice:** «Claude решает» — с hard constraint: никакого clamp на границе окна.

- No-LOS (wallbang/дым) → **Label + NULL** (`t0_source="never_visible"`)
- Perf → **Correctness first, профиль на staged**
- Coverage → **Все эпизоды включая unresolved**

---

## Метрика + gate-критерии

- Предмет gate → **Оба слоя отдельно**: Gate-A win-rate слайсы + Gate-B RT-стабильность; продукт может жить на Gate-A при RED Gate-B
- Дизайн чисел → **Ресёрчер дизайнит, user апрувит ДО запуска** (lock в PLAN, no moving goalposts)
- STOP-rule при Gate-B FAIL → **Checkpoint, решает user** (park / пивот win-rate-only / итерация). Не авто-park, не авто-пивот.
- Выборка → **donk + 2-4 про с того же корпуса** (multi-player API OF-2, без новых демо)

---

## Re-batch scope + схема данных

- Тайминги → **Колонки в duel_episodes** (idempotent `_migrate_schema`), не новая таблица
- Ребатч → **Staged N=1→5→81, ручные чекпоинты**, inspection artifact на N=5 до полного прогона
- Shape-suite → **Два уровня**: синтетика в pytest + `@requires_db` на живой БД
- Старые невалидные данные engagements → **Оставить, путь deprecated**; все claims только из duel_episodes

---

## Claude's Discretion

- T1-предикат (mandate: методология должна заработать) + режим порога (по данным)
- Алгоритм T0 backward search (в рамках no-clamp constraint)
- Батчинг parse_ticks по эпизодам, имена derived-колонок
- Gate-A aux-слайсы; staged-driver reuse vs новый скрипт

## Deferred Ideas

- Dashboard/report переключение на duel_episodes — отдельная фаза
- Landing refresh + снятие баннера — после gate verdict (CAVEAT-1)
- BVH share / visibility cache — только если staged покажет неподъёмность
- kill_rate_analysis.py cleanup — backlog
