# Phase 7: Parallel Batch Runner + Data Accumulation — Research

**Researched:** 2026-05-05
**Domain:** Python multiprocessing, SQLite WAL concurrency, Streamlit background tasks, schema migration
**Confidence:** HIGH (все ключевые вопросы верифицированы инструментами на реальной машине)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- D-01: Demos sourced manually — no FACEIT API. `for_analysis/` drop directory.
- D-02: Batch runner сканирует `for_analysis/` в runtime.
- D-03: Batch triggered из нового "Batch Analysis" section в `app.py` — не CLI.
- D-04: `st.progress()` + live status text ("Processing demo 12/100: ...").
- D-05: Worker count — Streamlit slider. Default = 8.
- D-06: `match_id` = auto-increment от MAX(match_id)+1 в analytics.db. Empty DB → start 1.
- D-07: Новый столбец `demo_name` в обеих таблицах `engagements` и `duel_attempts`.
- D-08: `ProcessPoolExecutor` (multiprocessing, CPU-bound BVH raycasting).
- D-09: Log-and-continue. Failed demos → `batch_errors.log`.
- D-10: Новая таблица `processed_matches`: (demo_filename TEXT, player_steamid INTEGER, match_id INTEGER, processed_at TEXT). PK на (demo_filename, player_steamid).
- D-11: Skip if (demo_filename, player_steamid) exists in processed_matches.
- D-12: "Force reprocess" checkbox в Streamlit.
- D-13: Все результаты в тот же analytics.db.
- D-14: Один игрок на batch run.

### Claude's Discretion
- Механизм Streamlit polling (threading + session_state, или queue-based).
- Точная логика парсинга demo_name (strip .dem, normalize separators).
- Формат и расположение batch_errors.log.

### Deferred Ideas (OUT OF SCOPE)
- Multi-player batch в одном run.
- FACEIT API integration.
- Отдельный CLI run_batch.py.
</user_constraints>

---

## Summary

Phase 7 — технически хорошо изученная территория: ProcessPoolExecutor, SQLite WAL, Streamlit polling. Все ключевые вопросы верифицированы на реальной машине (Windows 11, Python 3.14.3, Streamlit 1.54.0, SQLite 3.50.4). Главный подводный камень: Windows `spawn` start method требует, чтобы worker-функция жила в импортируемом модуле, а не в `__main__` или лямбде — это жёсткое ограничение платформы. Второй критический факт: WAL mode уже НЕ включён в `analytics.db` (текущий `journal_mode = delete`), его нужно выставить при инициализации.

**Primary recommendation:** Создать `batch_runner.py` с worker-функцией верхнего уровня; Streamlit запускает пул через `threading.Thread` и следит за `st.session_state.batch_status` dict; WAL pragma ставить в `init_db()` при первом подключении.

---

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Demo discovery (for_analysis/ scan) | batch_runner.py | app.py | бизнес-логика сканирования отдельна от UI |
| Worker execution (DDMAnalyzer) | batch_runner.py (worker fn) | — | CPU-bound, должен быть в импортируемом модуле |
| Idempotency check (processed_matches) | db_utils.py | batch_runner.py | данные живут в SQLite, helper в db_utils |
| match_id assignment | db_utils.py | batch_runner.py | DB-level MAX(match_id)+1, нужна транзакция |
| Progress reporting | app.py (Streamlit polling) | batch_runner.py (status dict) | UI читает состояние; runner пишет в shared dict |
| Error logging | batch_runner.py | — | logging.FileHandler("batch_errors.log") |
| Schema migration (ALTER TABLE) | db_utils.init_db() | — | один раз при старте, идемпотентно |

---

## Focus Area 1: ProcessPoolExecutor + SQLite WAL — Concurrent Writes

### WAL mode: верификация

**VERIFIED (инструмент на реальной машине):**

1. `PRAGMA journal_mode=WAL` **персистируется в файл БД** — при новом подключении к уже WAL-configured DB возвращает `wal` без повторной установки pragma. [VERIFIED: sqlite3 test]
2. 8 параллельных writer-потоков с `timeout=10` и нормальными (non-EXCLUSIVE) транзакциями — **0 ошибок**, все 8 строк сохранены. [VERIFIED: threading test]
3. При `BEGIN EXCLUSIVE` + короткий timeout — воспроизводится `database is locked`. Вывод: EXCLUSIVE lock нельзя использовать в concurrent pipeline. [VERIFIED: locking test]
4. `ProcessPoolExecutor` + module-level worker function + 4 процесса → 12 строк, 0 ошибок. [VERIFIED: _test_pool_worker.py]

**Текущее состояние analytics.db:** `journal_mode = delete` (WAL не включён). [VERIFIED: PRAGMA query]

### Правильный паттерн записи из worker-процессов:

```python
# В worker-функции (в batch_runner.py, не в app.py):
def analyze_demo_worker(args: tuple) -> dict:
    demo_path, player_steamid, match_id, db_path = args
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")  # 10s retry на SQLITE_BUSY
    conn.close()
    # ... DDMAnalyzer вызов ...
    # save_to_db открывает свой connection внутри
    return {"status": "ok", "match_id": match_id, "demo": demo_path}
```

### Где устанавливать WAL:

WAL нужно включить **один раз в init_db()** при первом создании/открытии analytics.db. Поскольку WAL персистируется в файл, повторные подключения наследуют его автоматически. Для безопасности — также ставить `PRAGMA journal_mode=WAL` в каждом worker-подключении (pragma игнорируется если уже WAL, стоимость ноль).

### SQLITE_BUSY под WAL:

WAL позволяет параллельные **читатели + один писатель** одновременно. Множество писателей сериализуются — SQLite ждёт lock. Ключевые настройки:

```python
conn = sqlite3.connect(db_path, timeout=30)      # Python-level timeout
conn.execute("PRAGMA busy_timeout=10000")        # SQLite-level retry (ms)
```

При 8 worker-процессах на демо ~2-3 мин каждый: вероятность коллизии записи низкая (каждый процесс пишет результаты один раз в конце, не в процессе). 30-секундный timeout более чем достаточен. [ASSUMED]

### Не использовать BEGIN EXCLUSIVE:

`db_utils.save_to_db()` использует `with conn:` (implicit transaction) — это корректно. Не оборачивать в `BEGIN EXCLUSIVE`. [VERIFIED: db_utils.py source]

---

## Focus Area 2: Streamlit + Background Batch Jobs

### Ключевое ограничение Streamlit:

Streamlit — однопоточный event loop. Блокирующий вызов `pool.map()` или `executor.submit()` + `wait()` заморозит UI. **Решение: запускать пул в `threading.Thread`, передавать статус через `st.session_state`.** [VERIFIED: Streamlit 1.54.0 имеет `st.rerun`, `st.empty`, `st.progress`]

### Рекомендованный паттерн (polling через st.rerun):

```python
# В app.py — Batch Analysis section

import threading
import time

# Session state keys для batch:
# batch_running: bool
# batch_status: dict  {"total": N, "done": 0, "current": "filename", "errors": []}
# batch_futures: list[Future]  — хранить в session_state нельзя (not picklable)
# batch_results: list[dict]

def _run_batch_thread(demo_paths, player_steamid, n_workers, db_path):
    """Запускается в фоновом threading.Thread. Обновляет st.session_state."""
    from batch_runner import analyze_demo_worker
    import concurrent.futures
    
    total = len(demo_paths)
    st.session_state.batch_status = {"total": total, "done": 0, "current": "", "errors": []}
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=n_workers) as pool:
        futures = {
            pool.submit(analyze_demo_worker, (path, player_steamid, mid, db_path)): path
            for mid, path in demo_paths
        }
        for future in concurrent.futures.as_completed(futures):
            path = futures[future]
            try:
                result = future.result()
                st.session_state.batch_status["done"] += 1
                st.session_state.batch_status["current"] = result.get("demo", "")
            except Exception as e:
                st.session_state.batch_status["errors"].append(f"{path}: {e}")
                st.session_state.batch_status["done"] += 1
    
    st.session_state.batch_running = False

# В UI:
if st.button("Run Batch") and not st.session_state.get("batch_running"):
    st.session_state.batch_running = True
    t = threading.Thread(target=_run_batch_thread, args=(...), daemon=True)
    t.start()

if st.session_state.get("batch_running"):
    status = st.session_state.get("batch_status", {})
    done = status.get("done", 0)
    total = status.get("total", 1)
    st.progress(done / total, text=f"Processing demo {done}/{total}: {status.get('current','')}")
    time.sleep(0.5)
    st.rerun()  # перезапускает скрипт, читает обновлённый session_state
```

### Почему threading.Thread, а не ProcessPoolExecutor напрямую из main thread:

`as_completed()` блокирует вызывающий поток. Если вызвать из main Streamlit thread — UI замирает. threading.Thread запускает blocking `as_completed` loop в стороне, а main Streamlit thread делает polling через `st.rerun()`.

### Caveat: st.session_state из background thread:

В Streamlit 1.54 запись в `st.session_state` из не-main thread работает в общем случае, **но не является официально поддержанной**. [ASSUMED — нет официальной документации по thread safety session_state в 1.54] Альтернатива: `threading.Event` или `multiprocessing.Manager().dict()` как явно thread-safe shared state. Рекомендация: использовать простой Python `dict` в `st.session_state` (примитивные типы, без сложных объектов) — на практике работает надёжно с Streamlit 1.x.

### Futures и session_state:

`concurrent.futures.Future` объекты **не хранить в session_state** — они не сериализуемы и их жизненный цикл привязан к executor. Хранить только примитивный dict с прогрессом.

---

## Focus Area 3: Worker Function Design

### Windows spawn — критическое ограничение: [VERIFIED: тест с __main__]

На Windows `multiprocessing.get_start_method() == 'spawn'`. Дочерние процессы **импортируют** модуль-parent через стандартный import, не через fork. Это означает:

- **Worker-функция ОБЯЗАНА быть в импортируемом модуле** (не в `lambda`, не в методе класса, не в теле `if __name__ == '__main__':`).
- Функция, определённая в `python -c` или в `app.py`-теле вне функции — не пикклируется.
- **Правильно:** создать `batch_runner.py`, определить `analyze_demo_worker()` как top-level функцию.

### DDMAnalyzer НЕ picklable: [VERIFIED: DemoParser class not picklable]

`demoparser2.DemoParser` — Rust extension, не picklable. `DDMAnalyzer.__init__` принимает `demo_path` и сразу создаёт `self.parser = DemoParser(demo_path)`. Передавать экземпляр DDMAnalyzer между процессами нельзя.

**Правильный паттерн worker-функции:**

```python
# batch_runner.py — top-level function, NOT inside class or app.py body
from typing import Tuple, Any
import logging

def analyze_demo_worker(args: Tuple) -> dict:
    """
    Callable для ProcessPoolExecutor. Принимает plain args (picklable).
    DDMAnalyzer создаётся ВНУТРИ worker-процесса.
    """
    demo_path, player_steamid, match_id, db_path, tickrate = args
    
    # Импорты внутри функции для надёжности при spawn
    from ddm_analyzer import DDMAnalyzer
    from kill_rate_analysis import save_attempts
    import db_utils
    import dataclasses
    
    try:
        analyzer = DDMAnalyzer(
            demo_path=demo_path,
            player_steamid=player_steamid,
            match_id=match_id,
            tickrate=tickrate,
        )
        results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)
        
        # save_to_db вызывается внутри analyze_demo() для engagements
        # duel_attempts — сохраняем отдельно:
        if attempts:
            save_attempts("batch", attempts, match_id=match_id)
        
        return {
            "status": "ok",
            "match_id": match_id,
            "demo": demo_path,
            "engagements": len(results_df),
            "attempts": len(attempts),
        }
    except Exception as e:
        import traceback
        return {
            "status": "error",
            "match_id": match_id,
            "demo": demo_path,
            "error": str(e),
            "traceback": traceback.format_exc(),
        }
```

### run_analysis.py как шаблон:

`run_analysis.py::main()` — прямой шаблон для worker body. Ключевые отличия batch worker:
1. Нет `save_results()` в CSV (batch пишет только в SQLite, или пишет в оба — на усмотрение)
2. `match_id` передаётся извне (pre-assigned), не генерируется
3. Ошибки возвращаются как dict, не print + continue
4. `obsidian_writer` не вызывается в batch mode

---

## Focus Area 4: match_id Assignment Under Parallelism

### Проблема race condition:

Если 8 workers стартуют одновременно и каждый делает `SELECT MAX(match_id)+1` — все получат одинаковый результат и присвоят себе match_id=8 (если в БД было 7). Это нарушает уникальность match_id. [VERIFIED: логически]

### Решение: pre-assign match_ids до запуска pool (рекомендовано):

```python
def assign_match_ids(demos_to_process: list[str], db_path: str) -> list[tuple[int, str]]:
    """Секвенциально назначить match_ids до запуска workers."""
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    
    row = conn.execute("SELECT MAX(match_id) FROM engagements").fetchone()
    current_max = int(row[0]) if row[0] is not None else 0
    
    assignments = []
    for i, demo_path in enumerate(demos_to_process):
        assignments.append((current_max + 1 + i, demo_path))
    conn.close()
    return assignments
```

Затем передавать `(match_id, demo_path)` парами в pool. Каждый worker знает свой match_id заранее. Никаких DB-обращений для ID assignment внутри workers.

### Почему не DB-level locking:

`BEGIN EXCLUSIVE` + `SELECT MAX + INSERT` внутри каждого worker — создаёт сериализацию всех 8 workers на каждую попытку записи. Сложнее и медленнее pre-assign. [ASSUMED: проще и безопаснее]

### match_id из processed_matches vs engagements:

`MAX(match_id)` нужно брать из engagements (или из MAX по обеим таблицам). Таблица `processed_matches` хранит match_id для обратной связи но не является авторитетным источником — исторические данные могут быть только в engagements. Рекомендация: `MAX(COALESCE((SELECT MAX(match_id) FROM engagements), 0), COALESCE((SELECT MAX(match_id) FROM duel_attempts), 0))`.

---

## Focus Area 5: Schema Migration (demo_name + player_steamid)

### Текущее состояние analytics.db: [VERIFIED: PRAGMA table_info]

```
Таблицы: ['engagements']
Столбцы engagements: match_id, moment_timestamp, description, t0_source, 
    t0_manual_tick, t1_aim_start_tick, t2_first_hit_tick, rt_visible_to_aim_ms, 
    rt_aim_to_hit_ms, rt_visible_to_hit_ms, target_enemy_id, 
    player_velocity_at_t0_ups, enemy_velocity_at_t0_ups, engagement_type
Отсутствуют: demo_name, player_steamid (оба нужны для Phase 7)
Таблица duel_attempts: НЕ СУЩЕСТВУЕТ
Journal mode: delete (WAL не включён — критично)
Существующих строк: 3
```

### Миграция через ALTER TABLE ADD COLUMN: [VERIFIED: тест на копии analytics.db]

```python
def _migrate_schema(conn: sqlite3.Connection) -> None:
    """Idempotent schema migration — добавляет колонки если отсутствуют."""
    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    
    # engagements — добавить demo_name, player_steamid если нет
    if "engagements" in existing_tables:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
        if "demo_name" not in cols:
            conn.execute("ALTER TABLE engagements ADD COLUMN demo_name TEXT DEFAULT NULL")
        if "player_steamid" not in cols:
            conn.execute("ALTER TABLE engagements ADD COLUMN player_steamid INTEGER DEFAULT NULL")
    
    # duel_attempts — создать если не существует (Phase 6 могла не создать)
    if "duel_attempts" not in existing_tables:
        conn.execute("""
            CREATE TABLE duel_attempts (
                match_id TEXT,
                demo_name TEXT,
                player_steamid INTEGER,
                -- остальные колонки из DuelAttempt dataclass
                PRIMARY KEY (match_id, t0_tick, enemy_steamid)
            )
        """)
    else:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(duel_attempts)").fetchall()}
        if "demo_name" not in cols:
            conn.execute("ALTER TABLE duel_attempts ADD COLUMN demo_name TEXT DEFAULT NULL")
    
    # processed_matches — создать если не существует
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_matches (
            demo_filename TEXT NOT NULL,
            player_steamid INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (demo_filename, player_steamid)
        )
    """)
    conn.commit()
```

### Где вызывать миграцию:

В `db_utils.init_db(db_path)` — функция которой сейчас нет, нужно создать. Вызывать при старте app.py и в batch_runner.py. Идемпотентна — безопасно вызывать несколько раз.

### Старые строки в engagements (3 строки):

После ALTER TABLE ADD COLUMN значения `demo_name` и `player_steamid` будут NULL для старых строк. Это ожидаемо и не ломает существующие queries (NULL-safe). Обновлять ретроактивно не нужно. [ASSUMED: 3 строки — тестовые данные, не критично]

---

## Focus Area 6: Windows-Specific Concerns

### `if __name__ == '__main__':` guard и Streamlit: [VERIFIED: тест]

Streamlit запускает `app.py` как import (не как `__main__`), но ProcessPoolExecutor на Windows spawn требует, чтобы worker-функция была в importable module. **Решение полностью исключает проблему:** worker-функция живёт в `batch_runner.py` — отдельном модуле с чистым namespace. Streamlit импортирует `batch_runner`, дочерние процессы импортируют `batch_runner` — всё работает без `if __name__` guard.

Тест подтвердил: `_test_pool_worker.py` (module с `if __name__ == '__main__':`) работает корректно, `python -c` с inline-функцией — нет. [VERIFIED]

### spawn overhead на Windows:

Каждый spawn-процесс перезапускает Python интерпретатор и заново импортирует все модули (ddm_analyzer, demoparser2, awpy, numpy, pandas). Оценка overhead: ~3-5 секунд на процесс при cold start (awpy + demoparser2 + numpy тяжёлые). При demo ~2 мин анализа — overhead ~3-5% от времени. При 8 workers и 100 демо с ~20 proc-restarts (100/8 ≈ 13 батчей × pool overhead) — некритично. [ASSUMED: оценка; awpy import time не замерялась]

### Initializer функция для тёплого старта:

ProcessPoolExecutor поддерживает `initializer` parameter:

```python
def _worker_init():
    """Импорты один раз при старте worker-процесса."""
    import ddm_analyzer  # noqa — кэшируется в sys.modules
    import awpy          # noqa

ProcessPoolExecutor(max_workers=8, initializer=_worker_init)
```

Экономит повторный import при повторном `submit()` в тот же worker. Полезно если pool держится живым между батчами.

### awpy/demoparser2 в child processes:

demoparser2 — Rust pyo3 extension. Не picklable как объект, но импортируется нормально в spawn. DDMAnalyzer создаётся внутри worker → всё ок. [VERIFIED: DemoParser not picklable as object, but module imports fine]

### for_analysis/ директория:

`for_analysis/` **НЕ существует** на текущем диске. [VERIFIED: os.listdir] Нужно создать при первом запуске или в Wave 0.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Concurrent write safety | Custom file locks | SQLite WAL mode | атомарные транзакции встроены |
| Batch job futures | Custom thread pool | `ProcessPoolExecutor` | стандарт, production-ready |
| Progress polling | WebSocket/SSE | `st.rerun()` + sleep loop | Streamlit идиоматично |
| Worker status sharing | `multiprocessing.Queue` | plain dict в `st.session_state` | достаточно для 1 batch run |
| match_id uniqueness | DB-level lock + SELECT | pre-assign в main thread | проще, без deadlock risk |
| Schema idempotency | DROP + recreate | ALTER TABLE ADD COLUMN IF | данные сохраняются |

---

## Common Pitfalls

### Pitfall 1: Worker function defined in app.py body
**What goes wrong:** `AttributeError: module '__main__' has no attribute 'worker_fn'` в Windows spawn — pool workers не могут найти функцию.
**Why it happens:** spawn перезапускает интерпретатор и импортирует модуль. Streamlit запускает app.py иначе чем `__main__`, функция не доступна в глобальном namespace дочернего процесса.
**How to avoid:** Все worker-функции в `batch_runner.py`. Импортировать: `from batch_runner import analyze_demo_worker`.
**Warning signs:** Immediate `BrokenProcessPool` при первом `pool.submit()`.

### Pitfall 2: WAL mode не включён (текущее состояние)
**What goes wrong:** `database is locked` при конкурентных writes без WAL.
**Why it happens:** analytics.db создан без WAL pragma. Default mode = DELETE (journal).
**How to avoid:** `init_db()` выставляет `PRAGMA journal_mode=WAL` при первом открытии. Персистируется автоматически.
**Warning signs:** Ошибки при > 1 worker даже с коротким демо.

### Pitfall 3: race condition в match_id assignment
**What goes wrong:** Несколько workers получают одинаковый match_id → дублирование + нарушение idempotency DELETE.
**Why it happens:** `SELECT MAX(match_id)+1` выполняется конкурентно до того, как первый worker успел записать.
**How to avoid:** Pre-assign все match_ids в main thread до запуска pool.
**Warning signs:** `analytics.db` содержит дублирующиеся match_ids после batch run.

### Pitfall 4: Блокировка Streamlit main thread
**What goes wrong:** UI замерзает на время batch (100 демо × 2 мин = 200+ мин).
**Why it happens:** `pool.map()` или `wait(futures)` вызваны из main Streamlit thread.
**How to avoid:** Весь pool execution — в `threading.Thread(daemon=True)`. Main thread делает `time.sleep(0.5) + st.rerun()` polling.
**Warning signs:** Браузер показывает spinner, ни прогресс ни кнопки не реагируют.

### Pitfall 5: Streamlit reruns при каждом rerun очищают локальные переменные
**What goes wrong:** Thread reference, futures list теряются при `st.rerun()`.
**Why it happens:** `st.rerun()` перезапускает скрипт с нуля — локальные переменные уничтожаются.
**How to avoid:** Хранить только примитивный status dict в `st.session_state`. Thread запущен daemon=True — продолжает работать независимо от rerun. Futures не хранить вообще (результаты пишутся в БД worker-ом).

### Pitfall 6: for_analysis/ не существует
**What goes wrong:** `FileNotFoundError` при сканировании директории.
**Why it happens:** Директория была задумана как drop location, но не создана на текущей машине.
**How to avoid:** `Path("for_analysis").mkdir(exist_ok=True)` в начале Batch Analysis section и/или в Wave 0.

### Pitfall 7: duel_attempts таблица отсутствует в analytics.db
**What goes wrong:** `save_to_db(df, db, "duel_attempts", match_id)` упадёт с `ValueError: Unknown table 'duel_attempts'` — или если добавить в allowed tables, то с SQLite ошибкой "no such table".
**Why it happens:** Phase 6 добавила engagements, но duel_attempts в analytics.db не создана (только в CSV). [VERIFIED: analytics.db содержит только engagements]
**How to avoid:** `init_db()` создаёт duel_attempts через `CREATE TABLE IF NOT EXISTS`.

---

## Code Examples

### init_db() — полный шаблон

```python
# db_utils.py — добавить функцию init_db()
import sqlite3
from contextlib import closing
from typing import Optional

def init_db(db_path: str) -> None:
    """Initialize analytics.db: WAL mode + schema migration.
    
    Idempotent — safe to call multiple times.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        # WAL mode: persists to DB file — subsequent connections inherit it
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=10000")
        
        with conn:
            _migrate_schema(conn)


def _migrate_schema(conn: sqlite3.Connection) -> None:
    existing_tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    
    # engagements: add demo_name and player_steamid if missing
    if "engagements" in existing_tables:
        cols = {c[1] for c in conn.execute("PRAGMA table_info(engagements)").fetchall()}
        if "demo_name" not in cols:
            conn.execute("ALTER TABLE engagements ADD COLUMN demo_name TEXT DEFAULT NULL")
        if "player_steamid" not in cols:
            conn.execute("ALTER TABLE engagements ADD COLUMN player_steamid INTEGER DEFAULT NULL")
    
    # duel_attempts: create if missing
    conn.execute("""
        CREATE TABLE IF NOT EXISTS duel_attempts (
            match_id TEXT,
            map_name TEXT,
            demo_name TEXT,
            player_steamid INTEGER,
            t0_tick INTEGER,
            enemy_steamid INTEGER,
            was_killed INTEGER,
            bullets_fired INTEGER,
            bullets_hit INTEGER,
            engagement_type TEXT,
            player_velocity_ups REAL,
            crosshair_angle_deg REAL,
            hurt_victims_in_window TEXT
        )
    """)
    
    # processed_matches: idempotency table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS processed_matches (
            demo_filename TEXT NOT NULL,
            player_steamid INTEGER NOT NULL,
            match_id INTEGER NOT NULL,
            processed_at TEXT NOT NULL,
            PRIMARY KEY (demo_filename, player_steamid)
        )
    """)
```

### is_processed() и mark_processed()

```python
def is_processed(db_path: str, demo_filename: str, player_steamid: int) -> bool:
    with closing(sqlite3.connect(db_path)) as conn:
        row = conn.execute(
            "SELECT 1 FROM processed_matches WHERE demo_filename=? AND player_steamid=?",
            (demo_filename, player_steamid)
        ).fetchone()
        return row is not None


def mark_processed(db_path: str, demo_filename: str, player_steamid: int, match_id: int) -> None:
    from datetime import datetime, timezone
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            conn.execute(
                """INSERT OR REPLACE INTO processed_matches
                   (demo_filename, player_steamid, match_id, processed_at)
                   VALUES (?, ?, ?, ?)""",
                (demo_filename, player_steamid, match_id,
                 datetime.now(timezone.utc).isoformat())
            )


def get_next_match_id(db_path: str, n: int) -> int:
    """Return the first of n consecutive match_ids available for assignment."""
    with closing(sqlite3.connect(db_path)) as conn:
        r1 = conn.execute("SELECT MAX(CAST(match_id AS INTEGER)) FROM engagements").fetchone()[0]
        r2 = conn.execute("SELECT MAX(CAST(match_id AS INTEGER)) FROM duel_attempts").fetchone()[0] \
             if _table_exists(conn, "duel_attempts") else None
        current_max = max(r1 or 0, r2 or 0)
        return current_max + 1
```

### batch_runner.py — скелет

```python
# batch_runner.py
from __future__ import annotations
import logging
import os
from pathlib import Path
from typing import Tuple, Any

logger = logging.getLogger("BatchRunner")


def analyze_demo_worker(args: Tuple[str, int, int, str, int]) -> dict:
    """
    Top-level worker function for ProcessPoolExecutor.
    All args are plain picklable types.
    
    Returns dict with keys: status, match_id, demo, engagements, attempts, error
    """
    demo_path, player_steamid, match_id, db_path, tickrate = args
    
    # Imports inside function — ensures clean namespace in spawn processes
    from ddm_analyzer import DDMAnalyzer
    import db_utils
    import dataclasses
    import sqlite3
    
    # Set WAL on worker's first DB touch
    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=10000")
    conn.close()
    
    demo_name = Path(demo_path).stem
    
    try:
        analyzer = DDMAnalyzer(
            demo_path=demo_path,
            player_steamid=player_steamid,
            match_id=match_id,
            tickrate=tickrate,
        )
        results_df, attempts = analyzer.analyze_demo(bulk_mode=True, attempts_mode=True)
        
        # Inject demo_name into results before save
        if not results_df.empty:
            results_df["demo_name"] = demo_name
        
        # analyze_demo calls save_to_db(engagements) internally — already saved
        # Save duel_attempts separately
        if attempts:
            import pandas as pd
            att_df = pd.DataFrame([dataclasses.asdict(a) for a in attempts])
            att_df["demo_name"] = demo_name
            db_utils.save_to_db(att_df, db_path, "duel_attempts", match_id)
        
        db_utils.mark_processed(db_path, os.path.basename(demo_path), player_steamid, match_id)
        
        return {
            "status": "ok",
            "match_id": match_id,
            "demo": demo_name,
            "engagements": len(results_df),
            "attempts": len(attempts),
        }
    except Exception as exc:
        import traceback
        return {
            "status": "error",
            "match_id": match_id,
            "demo": demo_name,
            "error": str(exc),
            "traceback": traceback.format_exc(),
        }
```

---

## Runtime State Inventory

> Фаза — не rename/refactor, но содержит schema migration существующей БД.

| Category | Items Found | Action Required |
|----------|-------------|-----------------|
| Stored data | analytics.db: 3 строки в engagements, без demo_name/player_steamid, journal_mode=delete | ALTER TABLE ADD COLUMN × 2; PRAGMA journal_mode=WAL в init_db() |
| Live service config | Нет — Streamlit локальный, никаких внешних сервисов | None |
| OS-registered state | Нет Task Scheduler / pm2 / systemd для этого проекта | None |
| Secrets/env vars | Нет — demo paths хардкожены или из for_analysis/ директории | None |
| Build artifacts | for_analysis/ директория не существует | Создать mkdir в Wave 0 |

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|-------------|-----------|---------|----------|
| Python 3.14 | everything | ✓ | 3.14.3 | — |
| sqlite3 | analytics.db | ✓ | 3.50.4 | — |
| streamlit | app.py UI | ✓ | 1.54.0 | — |
| concurrent.futures | ProcessPoolExecutor | ✓ | stdlib | — |
| threading | background thread | ✓ | stdlib | — |
| multiprocessing (spawn) | Windows process start | ✓ | spawn | — |
| for_analysis/ dir | demo discovery | ✗ | — | создать mkdir |

**Missing dependencies with no fallback:** None (только for_analysis/ требует создания)

**Missing dependencies with fallback:** for_analysis/ — создать в Wave 0 задачей.

---

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x (текущий проект) |
| Config file | setup.cfg / pytest.ini (existing) |
| Quick run command | `python -m pytest tests/test_db_utils.py tests/test_batch_runner.py -x --no-header -q` |
| Full suite command | `python -m pytest --override-ini="addopts=--strict-markers"` |

### Phase Requirements → Test Map

| Req | Behavior | Test Type | Command | Exists? |
|-----|----------|-----------|---------|---------|
| SC1 | batch processes all demos в for_analysis/ без manual intervention | unit+integration | `pytest tests/test_batch_runner.py::test_scan_for_analysis` | ❌ Wave 0 |
| SC2 | re-run produces no duplicate rows | unit | `pytest tests/test_db_utils.py::test_processed_matches_idempotency` | ❌ Wave 0 |
| SC2 | is_processed() returns True after mark_processed() | unit | `pytest tests/test_db_utils.py::test_is_processed` | ❌ Wave 0 |
| SC3 | runtime < 60 min для 100 демо | manual smoke | тайминг реального batch run | manual |
| D-07 | demo_name column в engagements после batch write | unit | `pytest tests/test_db_utils.py::test_demo_name_in_schema` | ❌ Wave 0 |
| D-10 | processed_matches table создаётся в init_db() | unit | `pytest tests/test_db_utils.py::test_init_db_creates_processed_matches` | ❌ Wave 0 |
| WAL | concurrent writes без SQLITE_BUSY | unit | `pytest tests/test_db_utils.py::test_wal_concurrent_writes` | ❌ Wave 0 |
| migration | ALTER TABLE idempotent на существующей БД | unit | `pytest tests/test_db_utils.py::test_migrate_schema_idempotent` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_db_utils.py -x -q`
- **Per wave merge:** `python -m pytest --override-ini="addopts=--strict-markers"`
- **Phase gate:** 256 + новые тесты green перед `/gsd-verify-work`

### Wave 0 Gaps
- [ ] `tests/test_db_utils.py` — добавить тесты для init_db, is_processed, mark_processed, migrate_schema, processed_matches idempotency
- [ ] `tests/test_batch_runner.py` — создать: test_scan_for_analysis, test_worker_function_picklable, test_pre_assign_match_ids, test_analyze_demo_worker_error_handling
- [ ] `for_analysis/` — создать директорию (Wave 0 task)
- [ ] `batch_runner.py` — создать модуль (Wave 1 первый task)

---

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | SQLITE_BUSY при 8 workers маловероятен (каждый пишет один раз в конце демо) | Focus Area 1 | Если демо короткие и workers пишут часто — нужно увеличить busy_timeout |
| A2 | spawn overhead ~3-5 сек на worker process | Focus Area 6 | Если awpy import медленнее — рассмотреть initializer для тёплого пула |
| A3 | 3 строки в engagements — тестовые данные, не критично обновлять retroactively | Focus Area 5 | Если это production данные — нужно UPDATE для заполнения demo_name/player_steamid |
| A4 | st.session_state write из background thread надёжен в Streamlit 1.54 | Focus Area 2 | Если thread-unsafe — использовать threading.Event + local dict как fallback |

---

## Open Questions (RESOLVED)

1. **demo_name injection в analyze_demo()**
   - What we know: `analyze_demo()` вызывает `db_utils.save_to_db(results_df, ...)` внутри — но `results_df` в этот момент ещё не содержит `demo_name`.
   - What's unclear: нужно ли изменять DDMAnalyzer чтобы он сам добавлял `demo_name`, или worker инжектирует после возврата (но данные уже записаны в БД)?
   - Recommendation: Добавить `self.demo_name` в DDMAnalyzer `__init__` (= `Path(demo_path).stem`) и включить в results dict в `analyze_demo()`. Это чище чем post-injection. Alternatively — добавить UPDATE после save_to_db в worker, но это two-phase write.
   - RESOLVED: Plan 07-03 добавляет `demo_name: str = ""` параметр в `DDMAnalyzer.__init__()` и threading через `results_df`. Worker в Plan 07-02 передаёт `Path(demo_path).stem` как `demo_name`.

2. **duel_attempts таблица — точная схема**
   - What we know: `DuelAttempt` dataclass существует в `duel_attempts.py`, save через `kill_rate_analysis.save_attempts()`.
   - What's unclear: точные имена колонок dataclass (нужно прочитать duel_attempts.py).
   - Recommendation: Плановщик должен прочитать `duel_attempts.py` и вывести CREATE TABLE schema из dataclass полей.
   - RESOLVED: Plan 07-01 Task 1 выводит схему из DuelAttempt dataclass полей (match_id, map_name, demo_name, player_steamid, t0_tick, enemy_steamid, was_killed, bullets_fired, bullets_hit, engagement_type, player_velocity_ups, crosshair_angle_deg, hurt_victims_in_window, fires_in_cluster).

3. **Force reprocess (D-12) — scope очистки**
   - What we know: "удалить processed_matches запись и все строки для match_id".
   - What's unclear: match_id может быть неизвестен при force reprocess (нужен lookup по demo_filename в processed_matches).
   - Recommendation: `DELETE FROM engagements WHERE match_id = (SELECT match_id FROM processed_matches WHERE demo_filename=? AND player_steamid=?)`, затем delete processed_matches row.
   - RESOLVED: Plan 07-01 Task 3 добавляет `force_reprocess_demo(db_path, demo_filename, player_steamid)` в `db_utils.py` — делает lookup match_id, затем DELETE из engagements, duel_attempts и processed_matches. Plan 07-02 вызывает её в `filter_unprocessed(force=True)` перед возвратом списка.

---

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | локальный инструмент, нет auth |
| V3 Session Management | no | no user sessions |
| V4 Access Control | no | single-user local tool |
| V5 Input Validation | yes | SteamID64 — integer parse; demo_path — Path validation, не URL |
| V6 Cryptography | no | нет шифрования |

### Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection via demo_filename | Tampering | Parameterized queries — уже используются в db_utils.py |
| Path traversal via demo_filename | Tampering | `Path(demo_path).stem` для demo_name; `for_analysis/` whitelist для paths |
| Malformed SteamID | Tampering | `int(steamid_input)` с ValueError catch — уже в app.py |

---

## Sources

### Primary (HIGH confidence)
- `[VERIFIED: sqlite3 test на machine]` — WAL persistence, concurrent write safety, busy_timeout behavior
- `[VERIFIED: multiprocessing test на machine]` — spawn start method, module-level function requirement, ProcessPoolExecutor + WAL
- `[VERIFIED: PRAGMA table_info(engagements)]` — текущая схема analytics.db
- `[VERIFIED: db_utils.py source]` — существующие паттерны save_to_db, implicit transaction
- `[VERIFIED: ddm_analyzer.py, run_analysis.py source]` — DDMAnalyzer constructor, analyze_demo() API

### Secondary (MEDIUM confidence)
- `[VERIFIED: streamlit.__version__]` — Streamlit 1.54.0 имеет st.rerun, st.progress, st.empty
- `[CITED: Python docs concurrent.futures]` — ProcessPoolExecutor, spawn behavior, as_completed

### Tertiary (LOW confidence)
- `[ASSUMED]` — spawn import overhead estimate (~3-5 sec); не замерялся
- `[ASSUMED]` — st.session_state thread-safety в 1.54; не верифицировано официальной документацией

---

## Metadata

**Confidence breakdown:**
- SQLite WAL concurrency: HIGH — верифицировано инструментами
- ProcessPoolExecutor Windows spawn: HIGH — верифицировано тестами
- Streamlit polling pattern: MEDIUM — API верифицировано, thread-safety assumed
- Schema migration: HIGH — тест на реальной копии analytics.db
- match_id pre-assign: HIGH — логически верифицировано, стандартный паттерн

**Research date:** 2026-05-05
**Valid until:** 2026-06-05 (стабильный стек, изменения маловероятны)
