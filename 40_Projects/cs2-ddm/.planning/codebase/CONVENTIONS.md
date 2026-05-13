# Coding Conventions

_Generated: 2026-04-30_
_Focus: quality_

## Summary

Project enforces strict Python typing, dataclass-based state, and named constants throughout. All code is auto-formatted by black + ruff on every edit via Claude Code hooks.

## Type Hints

- All public functions annotated: `Tuple`, `List`, `Dict`, `Optional` from `typing`
- `from __future__ import annotations` used in `duel_attempts.py` for forward refs
- Return types always declared — no bare `def f():`

## Naming Conventions

| Category | Pattern | Example |
|-|-|-|
| Public constants | `UPPER_SNAKE` | `VELOCITY_PEEK_THRESHOLD_UPS` |
| Internal constants | `_UPPER_SNAKE` | `_FIRE_CLUSTER_GAP_TICKS` |
| Classes | `PascalCase` | `DuelAttemptFinder`, `T0Detector` |
| Methods/functions | `snake_case` | `find_first_visible_enemy_in_window` |
| Dataclass fields | `snake_case` | `t0_tick`, `was_killed`, `engagement_type` |

## Dataclasses

`@dataclass` used for all structured state — never plain dicts or tuples for multi-field results:
- `AnalysisMoment` (ddm_analyzer.py) — input spec for RT analysis
- `DuelAttempt` (duel_attempts.py) — output of one T0-anchored attempt
- Fields with defaults (`= ""`, `= 0`) at the end per dataclass ordering rules

## Constants

All magic numbers live in `config.py`. No inline literals in logic files:
```python
# config.py
VELOCITY_PEEK_THRESHOLD_UPS = 50
_FIRE_CLUSTER_GAP_TICKS = 128
_ATTEMPT_WINDOW_BEFORE_TICKS = ...
```

## Imports

- stdlib imports first, then third-party, then local — no mixing
- Named imports from config (not `import config`): `from config import X, Y`

## Formatting Tools

- `black` — auto-format on every file save (Claude Code hook)
- `ruff` — linting + import sort on every file save

## Comments

Sparse by design. Comments only for non-obvious constraints or workarounds:
```python
_HIT_LATENCY_TICKS = 4  # tolerance between fire and registered hurt (~60ms)
```
No docstrings on straightforward methods — name conveys intent.

## Error Handling

- `Optional[X]` return + `None` for "not found" — no exceptions for normal control flow
- NaN tick handling explicit: `pd.isna()` checks before tick arithmetic (critical in duel_attempts.py:106,249)
- Logging via `logging.getLogger(__name__)` — never print() in library code
