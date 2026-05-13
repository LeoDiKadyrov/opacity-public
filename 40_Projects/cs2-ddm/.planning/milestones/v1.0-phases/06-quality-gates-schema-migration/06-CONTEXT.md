# Phase 6: Quality Gates + Schema Migration — Context

**Gathered:** 2026-04-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Корректность данных и player-keyed хранилище. Phase 6 исправляет три оставшихся quality gate дефекта, добавляет player_steamid в обе схемы, вводит SQLite как dual-write рядом с CSV (CSV остаётся нетронутым для Streamlit), и добавляет dedup в DuelAttemptFinder. Выход: trustworthy moments в queryable формате, готово для Phase 7 batch runner.

</domain>

<decisions>
## Implementation Decisions

### SQLite Storage
- **D-01:** SQLite добавляется как **dual-write** рядом с CSV. CSV остаётся основным — `app.py` и `visualize_results.py` не трогаем в этой фазе.
- **D-02:** Два файла (или одна БД с двумя таблицами): `analytics.db` с таблицами `engagements` (Path 1) и `duel_attempts` (Path 2). Схемы разные — не смешивать.
- **D-03:** Idempotency: **replace by match_id** — то же поведение что и csv_utils. При повторном запуске старые строки match_id удаляются, новые вставляются. Обеспечивает паритет между CSV и SQLite.

### player_steamid
- **D-04:** `DDMAnalyzer.__init__(player_steamid: int)` — явный параметр (не auto-detect из демки). Streamlit уже спрашивает steamid у пользователя — передаём дальше в класс.
- **D-05:** player_steamid пишется в **обе** схемы: Path 1 (`cs2_engagement_analysis_results.csv` + `engagements` таблица) и Path 2 (`*_attempts.csv` + `duel_attempts` таблица). `DuelAttemptFinder` получает steamid через DDMAnalyzer.

### DuelAttemptFinder Dedup
- **D-06:** `kill_rate_analysis.save_attempts()` получает append+dedup by match_id — аналогично csv_utils для Path 1. Если match_id уже есть в CSV, старые строки этого match_id удаляются и записываются новые.

### Overlapping Window Gate
- **D-07:** `DDMAnalyzer.analyze_demo()` ведёт `last_accepted_t2_tick` state. Момент отвергается если `first_hit_tick < last_accepted_t2_tick + 300`. При принятии момента — обновляем `last_accepted_t2_tick`.
- **D-08:** Отвергнутый момент логируется как `logger.warning("Overlapping window rejected: ...")` — видно без --debug флага.

### Teammate Quality Gate
- **D-09:** Новый gate в `analyze_engagement_episode()`: reject если в окне [T0..T2] зафиксирован `player_hurt` по `target_enemy` от тиммейта (teammate = та же команда что и player). Фильтрует "phantom kills" где команда помогла убить.

### T0 Boundary Gate (уже реализовано)
- **D-10:** `T0_MIN_OFFSET_TICKS = 20` уже реализован в `ddm_analyzer.py:372`. Edge case 3 (T0 = search_start) уже исправлен. В Phase 6 не трогаем.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Схемы данных
- `.planning/codebase/ARCHITECTURE.md` — CSV schemas для Path 1 и Path 2, key classes, метод csv_utils
- `csv_utils.py` — существующая append+dedup логика по match_id (D-06 должна её повторить для Path 2)
- `config.py` — T0_MIN_OFFSET_TICKS, константы, AnalysisMoment dataclass

### Quality Gate реализация
- `.planning/codebase/CONCERNS.md` — три edge cases (edge case 2 = overlapping window = D-07, edge case 3 = T0_MIN_OFFSET_TICKS = D-10 уже готово)
- `ddm_analyzer.py` — `_resolve_t0()` (строка 372, T0_MIN_OFFSET_TICKS gate), `is_1v1_duel()`, `analyze_engagement_episode()`

### Kill rate pipeline
- `duel_attempts.py` — DuelAttemptFinder, DuelAttempt dataclass
- `kill_rate_analysis.py` — save_attempts() которому нужен dedup (D-06), PLAYERS dict

### Phase контекст
- `.planning/ROADMAP.md` — Phase 6 success criteria (4 пункта)
- `.planning/research/PITFALLS.md` — pitfall 3: schema migration before data accumulation; pitfall 5: parallelizing before quality gates

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `csv_utils.save_results()` — append+dedup by match_id pattern. D-06 (DuelAttemptFinder dedup) должна копировать эту логику, не изобретать заново.
- `ddm_analyzer.py:_resolve_t0()` — уже содержит T0_MIN_OFFSET_TICKS gate (line 372). Overlapping window gate (D-07) добавляется в `analyze_engagement_episode()` на один уровень выше.
- `ddm_analyzer.py:is_1v1_duel()` — фильтрует чужой урон по игроку. Teammate gate (D-09) — отдельный check, добавляется рядом.

### Established Patterns
- State management в DDMAnalyzer: уже хранит `self.analysis_moments`, `self.results`. Добавить `self.last_accepted_t2_tick: Optional[int] = None` — паттерн уже есть.
- logger.warning уже используется во всём коде для rejection — D-08 следует тому же паттерну.
- dataclass с явными полями (AnalysisMoment, DuelAttempt) — player_steamid добавляется как Optional[int] поле.

### Integration Points
- `app.py` использует CSV напрямую → **не трогаем** в Phase 6. SQLite пишется параллельно через новый модуль `db_utils.py` или расширение csv_utils.
- `run_analysis.py` и `kill_rate_analysis.py` создают DDMAnalyzer — нужно добавить player_steamid arg в оба entry points.
- Streamlit app уже принимает player_steamid от пользователя → пробрасываем в DDMAnalyzer без изменения UX.

</code_context>

<specifics>
## Specific Ideas

- **Валидация из реального анализа:** Abdra vs донк показал RT ≠ разделитель; crosshair angle + kill rate — главные сигналы. Качество данных Phase 6 критично для последующей интерпретации (Phase 8).
- **teammate_in_window** идентифицирован из анализа как "phantom kill" проблема — добавляем как D-09.
- **weapon_type split** (AWP vs rifle vs pistol) и **round_phase breakdown** — упомянуты как улучшения аналитики, но относятся к Phase 8 (interpretation layer).

</specifics>

<deferred>
## Deferred Ideas

- **weapon_type split в аналитике** (AWP/rifle/pistol отдельно) — Phase 8 (interpretation layer). AWP/sniper уже фильтруется Phase 5b.
- **round_phase analysis** — колонка `round_phase` уже есть в схеме; breakdown по фазам раунда → Phase 8.
- **Replace CSV with SQLite entirely** — отложено, app.py и visualize_results.py не обновляем до Phase 9 (B2C delivery).
- **Per-round kill rate** — текущий match-level aggregate достаточен; round-phase breakdown → Phase 8.

</deferred>

---

*Phase: 6 — Quality Gates + Schema Migration*
*Context gathered: 2026-04-30*
