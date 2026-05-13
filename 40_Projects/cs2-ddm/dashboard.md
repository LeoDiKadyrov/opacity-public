---
type: дашборд_проекта
status: в работе
goal: Djok — CS2 DDM Reaction Analyzer
tags: [cs2, djok, dashboard]
created: 2026-05-04
---

# Djok — Project Dashboard

## Цель
Инструмент анализа реакции CS2 игроков по demo файлам. Интерпретационный слой — главный приоритет.

## Текущий статус

| Фаза | Статус | Дата |
|-|-|-|
| Phase 1–5 | Done | — |
| Phase 6 (quality gates) | Done | 2026-05-02 |
| Phase 7 (batch runner + 100 demos) | Next | — |

Tests: **256 passing**

## Ключевые выводы (из анализа)

```dataview
LIST
FROM "20_Evergreen"
WHERE contains(tags, "cs2") AND contains(tags, "analysis")
SORT file.mtime DESC
LIMIT 10
```

## Задачи YouGile

```dataview
TABLE synced
FROM "40_Projects/cs2-ddm"
WHERE type = "задачи"
```

## Последние сессии

```dataview
LIST
FROM "00_Inbox"
WHERE contains(tags, "cs2-ddm") OR contains(tags, "session")
SORT file.mtime DESC
LIMIT 5
```

## Ссылки
- Pricing: $5/batch (expires 2026-07-03)
