---
phase: v2-interpretation-narrative
plan: 01
subsystem: narrative-validation
tags: [validator, hallucination-guard, REQ-5, REQ-11, D-06, D-09, D-14, W-3]
dependency-graph:
  requires:
    - interpretation.DIRECTIONS (preferred) OR fallback hardcoded title set
    - config.NARRATIVE_COMMON_NOUNS_WHITELIST (shipped this plan)
  provides:
    - narrative_validator.validate_narrative (pure function, importable)
    - config.LLM_PROVIDER, config.LLM_MODEL (env-overridable defaults)
    - config.NARRATIVE_COMMON_NOUNS_WHITELIST (frozenset of 8 D-06 tokens)
  affects:
    - W2 interpretation_narrative.build_narrative_report (consumes validator)
    - W3 eval-rate harness (validator gates SC-2 hallucination check)
tech-stack:
  added:
    - re (stdlib regex — anchored tick / bare-5-digit / round / demo / Cyrillic)
  patterns:
    - hybrid-validator (strict numeric + whitelist nouns per D-06)
    - import-with-fallback (graceful degradation when DIRECTIONS upstream missing)
key-files:
  created:
    - narrative_validator.py (202 LOC)
    - tests/test_narrative_validator.py (404 LOC, 37 tests across 8 TestClasses)
  modified:
    - config.py (+19 LOC: import os, LLM_PROVIDER, LLM_MODEL, NARRATIVE_COMMON_NOUNS_WHITELIST)
    - tests/test_config.py (+48 LOC: TestPhaseV2NarrativeConstants, 4 tests)
decisions:
  - DIRECTIONS title fallback set hardcoded (interpretation.DIRECTIONS not in worktree base)
  - _TICK_RE extended with [ауеыёиом]* RU suffix tolerance beyond RESEARCH baseline
  - Anchored-tick offset tracking (seen_tick_offsets set) prevents bare-pass double-count
  - Map names + common-nouns passively allowed (no validation = whitelist per D-06)
  - W0 recorded fixtures inlined as literal payloads (worktree base lacks tests/fixtures/)
metrics:
  duration: ~25 minutes
  completed: 2026-05-12
  tasks: 2
  commits: 4
  tests-added: 41 (4 config + 37 validator)
  tests-total: 367 passed (1 pre-existing fail in test_interpretation_live_db, out of scope)
---

# Phase v2-interpretation-narrative Plan 01: narrative_validator Summary

Hallucination guard for LLM coaching narratives. Pure function, zero I/O, zero LLM. Catches fake demo names + tick numbers + round numbers, enforces D-14 DIRECTIONS title anchor + REQ-11 RU language gate. Drives SC-2 hard gate (0/10 reports may contain hallucinated refs).

## Validator Signature

```python
def validate_narrative(
    text: str,
    allowed_refs: dict[str, set],   # {"ticks", "rounds", "demos", "maps"}
) -> tuple[bool, list[dict]]:
    """Returns (is_valid, violations).
    Each violation = {type, value, context_snippet}.
    """
```

`is_valid` is `True` iff `violations == []`. Violation types emitted:
- `demo` — fabricated `*.dem` filename not in `allowed_refs["demos"]`
- `tick` — anchored or bare 5+ digit integer not in `allowed_refs["ticks"]`
- `round` — `раунд[морф] N` or `round N` not in `allowed_refs["rounds"]`
- `no_direction_anchor` — narrative cites zero DIRECTIONS titles (D-14)
- `non_russian_output` — text contains zero Cyrillic chars (REQ-11 / W-3)

## Regex Patterns Shipped

| Pattern | Regex | Notes |
|-|-|-|
| `_TICK_RE` | `(?:тик[ауеыёиом]*\|tick)\s*(\d{4,})` IGNORECASE | RU suffix tolerance beyond RESEARCH baseline; 4+ digits when keyword anchored |
| `_TICK_BARE_RE` | `(?<![\d.,])\d{5,}(?![\d.,])` | 5+ digit fallback; lookarounds block decimals/thousands |
| `_ROUND_RE` | `(?:раунд[аеуыоё]?[ом]?\|round)\s*(\d{1,2})\b` IGNORECASE | 1-2 digit cap (real CS2 rounds 1-30) |
| `_DEMO_RE` | `\b[\w\-]+\.dem\b` IGNORECASE | Slug + `.dem` extension |

`_TICK_RE` was extended from RESEARCH baseline to tolerate Russian morphology suffixes (`тика`, `тике`, `тиком`). The bare-5-digit fallback (`_TICK_BARE_RE`) catches the integer regardless of suffix, but anchored coverage gives clearer violation context. Anchored-tick `start(1)` offsets tracked in a set so the bare pass does not emit a duplicate violation for the same integer.

## Test Count Delta

| TestClass | Tests | Coverage |
|-|-|-|
| TestPhaseV2NarrativeConstants (test_config.py) | 4 | NARRATIVE_COMMON_NOUNS_WHITELIST + LLM_PROVIDER + LLM_MODEL invariants |
| TestValidateDemoRefs | 4 | Demo filename Pass 1 |
| TestValidateTicks | 9 | Anchored, bare, decimal/thousands false-positives, RU suffix variants, no-double-count |
| TestValidateRounds | 5 | RU + EN morphology, 3-digit acceptance design |
| TestValidateMaps | 3 | D-06 soft pass (no validation) |
| TestValidateDirectionAnchor | 4 | D-14 case-insensitive substring match |
| TestValidateRussianLanguage | 3 | REQ-11 / W-3 Cyrillic gate |
| TestViolationShape | 2 | D-09 dict shape + snippet content |
| TestValidateRecordedFixtures | 7 | All 7 W0 adversarial scenarios (inlined per Rule 3 deviation) |
| **Total new tests** | **41** | — |

Full suite: 367 passed, 3 skipped, 1 pre-existing failure (`tests/test_interpretation.py::test_integration_live_db` — worktree's analytics.db lacks `player_steamid` column from a Phase 6+ migration not yet applied; unrelated to this plan, out of scope per Scope Boundary).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking dependency] interpretation.DIRECTIONS not present in worktree base**
- **Found during:** Task 2 RED writeup (validator GREEN spec imports `from interpretation import DIRECTIONS`)
- **Issue:** Worktree base (`8f1049f`) ships only the legacy `DRILLS` dict in `interpretation.py`. `DIRECTIONS` was scheduled to land later in v2 (CONTEXT references `interpretation.py:61`) but is not yet committed.
- **Fix:** `narrative_validator.py` wraps the import in `try/except (ImportError, AttributeError)` and falls back to a hardcoded title set extracted from CONTEXT D-13/D-14 + RESEARCH §Validator Design Pass 4 examples. Either source produces the same set of citable direction names.
- **Files modified:** `narrative_validator.py` (new, lines 26-58)
- **Commit:** `3fcda2a`

**2. [Rule 3 - Blocking dependency] tests/fixtures/anthropic_recorded/*.json missing**
- **Found during:** Task 2 RED writeup (plan promises `TestValidateRecordedFixtures` parametrised over 7 W0 fixtures)
- **Issue:** Worktree base lacks `tests/fixtures/` directory; W0 plan that ships those JSON fixtures is not yet merged into this branch.
- **Fix:** All 7 adversarial scenarios from RESEARCH §Testing Strategy inlined as literal text payloads inside `TestValidateRecordedFixtures` methods. Same coverage, no JSON load needed.
- **Files modified:** `tests/test_narrative_validator.py` lines 305-393
- **Commit:** `dda2791`

### CLAUDE.md compliance

- Strict typing hints: `dict[str, set]`, `tuple[bool, list[dict]]`, `set[int]`, `frozenset[str]`. No untyped public surface.
- Named constants in `config.py` — `LLM_PROVIDER`, `LLM_MODEL`, `NARRATIVE_COMMON_NOUNS_WHITELIST` shipped per "no magic numbers" rule.
- RU-only language rule respected — narrative validator enforces REQ-11 Cyrillic gate as a hard violation.

## Authentication Gates

None. Validator is pure offline code; no API keys, no network, no external services touched.

## Known Stubs

None. Validator is a complete, committable implementation per its plan scope. The 5-pass scan + violation emission is fully wired and exercised by the 37 unit tests.

## Per-Task Commits

| Task | Type | Commit | Description |
|-|-|-|-|
| 1 | RED | `efad10c` | test(v2-01): RED v2 narrative constants in config |
| 1 | GREEN | `9789d89` | feat(v2-01): add NARRATIVE_COMMON_NOUNS_WHITELIST + LLM defaults to config |
| 2 | RED | `dda2791` | test(v2-01): RED narrative_validator adversarial corpus |
| 2 | GREEN | `3fcda2a` | feat(v2-01): narrative_validator hallucination guard |

## Acceptance Criteria

- [x] `narrative_validator.py` exists, exports `validate_narrative`
- [x] All 7 recorded-fixture scenarios behave per spec (clean pass / hallucinated fail)
- [x] D-14 DIRECTIONS title anchor enforced
- [x] D-09 structured violations `{type, value, context_snippet}`
- [x] Numeric refs (tick, round) strict; demos strict (filename); maps + common-nouns lax (D-06)
- [x] REQ-11 / W-3 Cyrillic-presence Pass 5 raises `non_russian_output`
- [x] Validator pure function (no I/O, no LLM, no DB)
- [x] Available for import by W2 `interpretation_narrative.build_narrative_report`
- [x] Full suite green (no regressions caused by this plan)

## Self-Check: PASSED

- [x] `narrative_validator.py` exists at worktree root
- [x] `tests/test_narrative_validator.py` exists with 37 tests
- [x] `config.py` carries NARRATIVE_COMMON_NOUNS_WHITELIST + LLM_PROVIDER + LLM_MODEL
- [x] All 4 commits present in `git log`: efad10c, 9789d89, dda2791, 3fcda2a
- [x] `python -m pytest tests/test_narrative_validator.py tests/test_config.py -p no:cov` → 60 passed
- [x] Smoke imports: `from narrative_validator import validate_narrative` + `from config import NARRATIVE_COMMON_NOUNS_WHITELIST` succeed
