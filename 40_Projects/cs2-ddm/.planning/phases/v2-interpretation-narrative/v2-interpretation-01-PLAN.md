---
phase: v2-interpretation-narrative
plan: 01
type: execute
wave: 1
depends_on: [00]
files_modified:
  - narrative_validator.py
  - tests/test_narrative_validator.py
  - config.py
autonomous: true
requirements: [REQ-5, REQ-11]
must_haves:
  truths:
    - "validate_narrative(text, allowed_refs) → (is_valid, violations) — pure function, no I/O, no LLM"
    - "Hallucinated tick numbers caught (5+ digit bare integers OR `тик 99999` pattern not in allowed_refs[ticks])"
    - "Hallucinated demo names caught (regex `\\b[\\w\\-]+\\.dem\\b` not in allowed_refs[demos])"
    - "Hallucinated round numbers caught (`раунд[аеуыое]?\\s*N` or `round\\s*N` not in allowed_refs[rounds])"
    - "Map names + locked common-noun whitelist pass without attribution per D-06"
    - "DIRECTIONS title anchor enforced per D-14 (≥1 title from interpretation.DIRECTIONS must appear)"
    - "RU regex covers тик/тика/тике/тиком (case-insensitive) and раунд/раунда/раунде/раундом"
    - "Validator returns (False, [...]) on every adversarial fixture; (True, []) on clean fixtures"
    - "D-09: validate_narrative returns structured (is_valid: bool, violations: list[dict]) where each violation = {type, value, context_snippet} for prompt iteration logging"
    - "validate_narrative raises a Cyrillic-presence violation (type="non_russian_output") when text has zero characters in [Ѐ-ӿ] range — REQ-11 RU language gate"
  artifacts:
    - path: "narrative_validator.py"
      provides: "validate_narrative + helpers + module-level regex constants"
      exports: ["validate_narrative"]
      min_lines: 80
    - path: "tests/test_narrative_validator.py"
      provides: "Adversarial fixture-driven validator tests"
      contains: "TestValidateDemoRefs"
      min_lines: 150
    - path: "config.py"
      provides: "NARRATIVE_COMMON_NOUNS_WHITELIST frozenset constant"
      contains: "NARRATIVE_COMMON_NOUNS_WHITELIST"
  key_links:
    - from: "narrative_validator.validate_narrative"
      to: "interpretation.DIRECTIONS"
      via: "import + iterate titles for D-14 anchor check"
      pattern: "DIRECTIONS"
    - from: "narrative_validator.validate_narrative"
      to: "config.NARRATIVE_COMMON_NOUNS_WHITELIST"
      via: "import + use as allow-list"
      pattern: "NARRATIVE_COMMON_NOUNS_WHITELIST"
---

<objective>
Ship the hallucination guard. Pure function, zero I/O, zero LLM. Catches fake demo names, fake tick numbers, fake round numbers; whitelists map names + locked common nouns; enforces D-14 (narrative MUST cite ≥1 DIRECTIONS title). Drives REQ-5 + SC-2 hard gate.

Purpose: This is the trust safety net. SC-2 says 0/10 reports may contain hallucinated references — without a strict regex+set validator, the LLM will eventually invent a tick or demo and erode trust. Per RESEARCH §Validator Design, DIY regex (~80 LOC) beats OSS guardrails frameworks at this scale (no deps, fully unit-testable, deterministic).

Output:
- `narrative_validator.py` — new pure-Python module, importable as `from narrative_validator import validate_narrative`
- `tests/test_narrative_validator.py` — adversarial fixture-driven tests (uses 7 W0 recorded fixtures + hand-written edge cases)
- `config.py` — adds `NARRATIVE_COMMON_NOUNS_WHITELIST` frozenset constant
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-00-SUMMARY.md
@CLAUDE.md
@interpretation.py
@config.py

<interfaces>
<!-- Existing contracts. Use directly; do not re-explore. -->

From `interpretation.py:61` — DIRECTIONS dict:
```python
DIRECTIONS: dict[tuple[str, str], list[Direction]] = {
    ("crosshair_angle_at_t0_deg", "peek"): [
        {"title": "Map study", "body": "..."},
        {"title": "Demo review", "body": "..."},
        {"title": "In-game prefire", "body": "..."},
    ],
    ("rt_visible_to_aim_ms", "peek"): [
        {"title": "Demo review", "body": "..."},
        {"title": "Higher-tier pugs", "body": "..."},
        {"title": "Deathmatch focus", "body": "..."},
    ],
    ("rt_aim_to_hit_ms", "peek"): [
        {"title": "Deathmatch volume", "body": "..."},
        {"title": "Aim_botz before pug", "body": "..."},
        {"title": "Optional drill: KovaaK's", "body": "...", "is_drill": True},
    ],
    # ... 6 metrics × {peek, hold} entries
}
```

Each direction has a `title` field. Build set of all titles via:
```python
from interpretation import DIRECTIONS
ALL_DIRECTION_TITLES = {d["title"] for ds in DIRECTIONS.values() for d in ds}
```

Validator signature contract (from SPEC REQ-5 + RESEARCH §Validator Design):
```python
def validate_narrative(
    text: str,
    allowed_refs: dict[str, set],  # {"ticks": {int,...}, "rounds": {int,...}, "demos": {str,...}, "maps": {str,...}}
) -> tuple[bool, list[dict]]:
    """Returns (is_valid, violations). Each violation = {type, value, context_snippet}."""
```

Config constant to add (from PATTERNS.md `config.py` MODIFIED section):
```python
# In config.py, add this section:
NARRATIVE_COMMON_NOUNS_WHITELIST: frozenset[str] = frozenset({
    "peek", "hold", "aim", "crosshair", "pre-aim",
    "deathmatch", "DM", "VOD",
})
```

Recorded fixtures from W0 (tests/fixtures/anthropic_recorded/) provide the adversarial corpus:
- `ok_donk_peek` — must PASS validator (has `spirit-vs-faze.dem` in allowed_refs)
- `hallucinated_tick` — must FAIL (tick 99999999 not in allowed_refs)
- `hallucinated_demo` — must FAIL (fakedemo123.dem)
- `no_direction_anchor` — must FAIL (no DIRECTIONS title)
- `truncated_max_tokens` — must FAIL (tick 1234 truncated, not in allowed)
- `clean_paraphrase` — must PASS (no explicit refs at all, cites "Demo review" anchor + uses whitelisted "Mirage")
- `refusal` — N/A (text body has no refs but also no DIRECTIONS title; the refusal itself triggers fail-soft upstream BEFORE validator runs — but if validator does run, would FAIL on no_direction_anchor)
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Add NARRATIVE_COMMON_NOUNS_WHITELIST constant to config.py</name>
  <files>config.py, tests/test_config.py</files>
  <read_first>
    - config.py lines 155-202 (current PLAYER_NAMES section + logging — append new section after PLAYER_NAMES)
    - tests/test_config.py (existing test patterns)
  </read_first>
  <behavior>
    - Test 1 (RED first): `test_narrative_common_nouns_whitelist_present` — `from config import NARRATIVE_COMMON_NOUNS_WHITELIST; assert isinstance(NARRATIVE_COMMON_NOUNS_WHITELIST, frozenset); assert {"peek", "hold", "aim", "crosshair", "pre-aim", "deathmatch", "DM", "VOD"} <= NARRATIVE_COMMON_NOUNS_WHITELIST`
    - Test 2: `test_narrative_common_nouns_whitelist_immutable` — `with pytest.raises(AttributeError): NARRATIVE_COMMON_NOUNS_WHITELIST.add("foo")`
  </behavior>
  <action>
    Add this section to `config.py` after the `PLAYER_NAMES` block (around line 175), BEFORE `DEFAULT_BATCH_WORKERS`:
    ```python
    # ─────────────────────────────────────────────────────────────────────────────
    # Phase v2 — LLM narrative coaching layer
    # ─────────────────────────────────────────────────────────────────────────────

    # LLM provider abstraction (REQ-3). Currently Anthropic-only; future-proof env hook.
    LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "anthropic")

    # Default model — claude-sonnet-4-6 per L-2 (quality/cost balance, $3/$15 MTok).
    # Override via env LLM_MODEL=claude-opus-4-7 for ~5× cost / higher quality.
    LLM_MODEL: str = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

    # Locked common-noun whitelist — D-06 hybrid validator allows these without
    # attribution. Keep tight: every token here is a free-pass to the LLM.
    NARRATIVE_COMMON_NOUNS_WHITELIST: frozenset[str] = frozenset({
        "peek", "hold", "aim", "crosshair", "pre-aim",
        "deathmatch", "DM", "VOD",
    })
    ```

    Verify `import os` is present at top of `config.py`. If absent, add it near the existing `import logging` line. PATTERNS.md notes: "import os already implicit via Python stdlib but currently missing at top of config.py — add explicit import os near import logging line 9".

    Add tests to `tests/test_config.py`. Tests are tiny — a single concern: constants exist + are frozen.
  </action>
  <verify>
    <automated>python -m pytest tests/test_config.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "NARRATIVE_COMMON_NOUNS_WHITELIST" config.py` ≥ 1
    - `grep -c "LLM_PROVIDER" config.py` ≥ 1
    - `grep -c "LLM_MODEL" config.py` ≥ 1
    - `grep -E "^import os" config.py` returns at least 1 match
    - `python -c "from config import NARRATIVE_COMMON_NOUNS_WHITELIST, LLM_PROVIDER, LLM_MODEL; assert isinstance(NARRATIVE_COMMON_NOUNS_WHITELIST, frozenset); print('OK')"` prints "OK"
    - Both new tests in tests/test_config.py PASS
    - Full suite still green (no regressions)
  </acceptance_criteria>
  <done>
    Three config constants shipped: LLM_PROVIDER (env-defaulted to "anthropic"), LLM_MODEL (env-defaulted to "claude-sonnet-4-6"), NARRATIVE_COMMON_NOUNS_WHITELIST (frozenset of 8 tokens). Available for import by validator + future LLM client.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: narrative_validator.py — pure-function hallucination guard with adversarial test corpus</name>
  <files>narrative_validator.py, tests/test_narrative_validator.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Validator Design lines 343-444
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md D-06, D-08, D-09, D-14
    - interpretation.py lines 1-100 (DIRECTIONS dict structure — do NOT modify)
    - tests/test_csv_utils.py (TestClass-grouped pattern reference)
    - tests/fixtures/anthropic_recorded/*.json (W0 fixtures — adversarial corpus)
    - tests/conftest.py (verify autouse fixture from W0 is in place)
  </read_first>
  <behavior>
    All RED tests in `tests/test_narrative_validator.py` written and committed BEFORE implementation:

    **TestValidateDemoRefs** (REQ-5 demo names):
    - `test_demo_in_allowed_passes` — text "review demo spirit-vs-faze.dem", allowed_refs has it → (True, [])
    - `test_demo_not_in_allowed_fails` — text "review fakedemo123.dem", allowed_refs={...} → (False, [{type:"demo", value:"fakedemo123.dem", ...}])
    - `test_demo_case_insensitive_match` — text "Spirit-VS-Faze.DEM", allowed has lowercase variant → (True, [])
    - `test_no_demo_mention_no_violation` — text contains zero `.dem` filenames → (True, [...]) but no demo violation entry

    **TestValidateTicks** (REQ-5 numeric refs strict):
    - `test_anchored_tick_pattern_caught` — "тик 99999" not in allowed → violation type "tick" value 99999
    - `test_anchored_tick_in_allowed_passes` — "тик 12345" with 12345 in allowed → no tick violation
    - `test_bare_5digit_caught_as_tick` — "около 99999 момент" with 99999 not in allowed → violation
    - `test_2digit_score_not_flagged` — "счёт 16-12" → no tick violation (regex requires 5+ digits, won't match 2-digit)
    - `test_decimal_not_flagged` — "процент 12.345" → no violation (negative lookahead for `.` per RESEARCH `(?<![\d.,])\d{5,}(?![\d.,])`)
    - `test_thousands_separator_not_flagged` — "12,345 единиц" → no violation
    - `test_ru_suffix_variants_caught` — text "тике 99999", "тиком 99999", "тика 99999" — at least the bare-5-digit pattern catches the integer

    **TestValidateRounds** (REQ-5 round refs):
    - `test_round_anchor_caught` — "раунд 99" with 99 not in allowed → violation type "round" value 99
    - `test_round_in_allowed_passes` — "раунд 14" with 14 in allowed → no violation
    - `test_round_ru_suffix_variants` — "раунде 99", "раунда 99", "раундом 99" — all caught by `раунд[аеуыое]?\s*\d{1,2}\b` regex
    - `test_english_round_caught` — "round 99" → violation
    - `test_two_digit_max` — "раунд 100" — outside `\d{1,2}` so NOT caught (acceptable: real rounds are 1-30 in CS2)

    **TestValidateMaps** (D-06 whitelist):
    - `test_known_map_passes_without_attribution` — text "на Mirage отлично", allowed_refs["maps"] = {"de_mirage"} → no violation (strip de_ prefix variant)
    - `test_known_map_de_prefix_passes` — text "на de_mirage" → no violation
    - `test_unknown_map_does_NOT_fail` — D-06: maps are SOFT (whitelisted, not validated). Even unknown map name → no violation. (Per RESEARCH "Maps allowed without attribution per D-06")

    **TestValidateDirectionAnchor** (D-14):
    - `test_no_direction_title_fails` — text contains zero DIRECTIONS titles → (False, [{type: "no_direction_anchor", ...}])
    - `test_one_direction_title_passes` — text contains "Demo review" → no `no_direction_anchor` violation
    - `test_case_insensitive_anchor` — text "demo REVIEW поможет" → passes
    - `test_partial_match_does_not_count` — "Demo" alone (without "review") → fails anchor (substring match must be the full title)

    **TestValidateCommonNouns** (D-06 + D-08):
    - `test_whitelisted_common_noun_passes` — text has "peek", "VOD", "DM" → no violation for these
    - `test_player_nickname_passes` — text addresses player (per D-10) — soft check, not a violation either way

    **TestValidateRussianLanguage** (REQ-11 RU language gate — W-3):
    - `test_pure_english_text_fails_with_non_russian_output_violation` — text = "Donk had elite reaction time. Demo review will help." with valid allowed_refs; assert (False, [...]) with violation type == "non_russian_output"
    - `test_text_with_at_least_one_cyrillic_char_passes_language_gate` — text = "Donk: Demo review поможет" (1 Cyrillic word); assert no "non_russian_output" violation
    - `test_pure_cyrillic_text_passes_language_gate` — text = "Что у тебя получается. Demo review." (mostly Cyrillic); assert no "non_russian_output" violation

    **TestValidateRecordedFixtures** (uses W0 fixtures + builds allowed_refs):
    - `test_ok_donk_peek_fixture_passes` — load fixture; build allowed_refs with `spirit-vs-faze.dem`, ticks={12345}, rounds={14}, maps=set() → (True, [])
    - `test_hallucinated_tick_fixture_fails` — fixture text mentions tick 99999999, allowed has only {12345} → (False, [{type:"tick", value:99999999, ...}])
    - `test_hallucinated_demo_fixture_fails` — text mentions fakedemo123.dem → (False, [{type:"demo", value:"fakedemo123.dem", ...}])
    - `test_no_direction_anchor_fixture_fails` — text has no DIRECTIONS title → (False, [{type:"no_direction_anchor", ...}])
    - `test_clean_paraphrase_fixture_passes` — text has no explicit refs, cites "Demo review" → (True, [])
    - `test_truncated_max_tokens_fixture_fails` — text mentions tick 1234 (4 digits — NOT caught by 5+ bare-digit regex). Adjust: also check `_TICK_RE` anchored "тике 1234" — with `\d{4,}` if we relax minimum digit count for ANCHORED tick, this catches. **Decision**: Keep RESEARCH's `\d{4,}` for `_TICK_RE` anchored variant (тик/tick keyword present is strong signal even at 4 digits). Re-confirm regex in implementation matches RESEARCH §Validator Design line 382.

    GREEN implementation in `narrative_validator.py`:
    ```python
    """Phase v2 — narrative output validator (hallucination guard).

    Pure function, no I/O, no network. Per REQ-5 + D-06/D-08/D-09/D-14.
    """
    from __future__ import annotations
    import re
    from typing import Optional

    from interpretation import DIRECTIONS
    from config import NARRATIVE_COMMON_NOUNS_WHITELIST

    # Regex patterns per RESEARCH §Validator Design (verified against RU adversarial corpus)
    _TICK_RE = re.compile(r"(?:тик|tick)[ауеыё]?\s*(\d{4,})", re.IGNORECASE)
    _TICK_BARE_RE = re.compile(r"(?<![\d.,])\d{5,}(?![\d.,])")  # 5+ digits, not part of decimal/thousands
    _ROUND_RE = re.compile(r"(?:раунд[аеуыое]?|round)\s*(\d{1,2})\b", re.IGNORECASE)
    _DEMO_RE = re.compile(r"\b[\w\-]+\.dem\b", re.IGNORECASE)

    _SNIPPET_PAD = 30  # chars on each side of match for context

    def _snippet(text: str, start: int, end: int) -> str:
        s = max(0, start - _SNIPPET_PAD)
        e = min(len(text), end + _SNIPPET_PAD)
        return text[s:e].replace("\n", " ")

    def validate_narrative(
        text: str,
        allowed_refs: dict[str, set],
    ) -> tuple[bool, list[dict]]:
        """Returns (is_valid, violations). violations = list of dict
        {type: str, value: any, context_snippet: str}.

        Per D-06: numeric refs (tick, round) — strict exact match.
        Per D-08: allowed_refs has keys {"ticks", "rounds", "demos", "maps"}.
        Per D-14: text MUST cite ≥1 DIRECTIONS title or returns no_direction_anchor violation.
        Maps + locked whitelist nouns pass without attribution.
        """
        violations: list[dict] = []
        ticks_allowed = allowed_refs.get("ticks", set())
        rounds_allowed = allowed_refs.get("rounds", set())
        demos_allowed = {d.lower() for d in allowed_refs.get("demos", set())}

        # Pass 1: demo names
        for m in _DEMO_RE.finditer(text):
            demo = m.group(0).lower()
            if demo not in demos_allowed:
                violations.append({
                    "type": "demo",
                    "value": demo,
                    "context_snippet": _snippet(text, m.start(), m.end()),
                })

        # Pass 2a: anchored ticks (тик/tick + 4+ digits)
        seen_tick_offsets: set[int] = set()
        for m in _TICK_RE.finditer(text):
            tick = int(m.group(1))
            seen_tick_offsets.add(m.start(1))
            if tick not in ticks_allowed:
                violations.append({
                    "type": "tick",
                    "value": tick,
                    "context_snippet": _snippet(text, m.start(), m.end()),
                })

        # Pass 2b: bare 5+ digit integers (not already caught as anchored)
        for m in _TICK_BARE_RE.finditer(text):
            if m.start() in seen_tick_offsets:
                continue  # already counted via anchored pass
            tick = int(m.group(0))
            if tick not in ticks_allowed:
                violations.append({
                    "type": "tick",
                    "value": tick,
                    "context_snippet": _snippet(text, m.start(), m.end()),
                })

        # Pass 3: round numbers
        for m in _ROUND_RE.finditer(text):
            rnd = int(m.group(1))
            if rnd not in rounds_allowed:
                violations.append({
                    "type": "round",
                    "value": rnd,
                    "context_snippet": _snippet(text, m.start(), m.end()),
                })

        # Pass 4: D-14 DIRECTIONS title anchor (≥1 title must appear)
        titles_lower = {d["title"].lower() for ds in DIRECTIONS.values() for d in ds}
        text_lower = text.lower()
        if not any(t in text_lower for t in titles_lower):
            violations.append({
                "type": "no_direction_anchor",
                "value": None,
                "context_snippet": "",
            })

        # Pass 5: REQ-11 RU language gate (W-3) — narrative MUST contain ≥1 Cyrillic char
        # Range U+0400..U+04FF covers Cyrillic block; U+0500..U+052F covers Cyrillic Supplement.
        if not any("Ѐ" <= ch <= "ԯ" for ch in text):
            violations.append({
                "type": "non_russian_output",
                "value": None,
                "context_snippet": text[:100],
            })

        # Note: maps + common nouns whitelist — passively allowed, no validation needed.
        # NARRATIVE_COMMON_NOUNS_WHITELIST imported for downstream allowed_refs builders;
        # validator itself does not iterate it (whitelist = absence of validation).

        return (len(violations) == 0, violations)
    ```

    Note the `_TICK_RE` regex uses `[ауеыё]?` to cover RU suffixes (тика/тике/тиком). Per RESEARCH the regex is `(?:тик|tick)\s*(\d{4,})` — but the test `test_ru_suffix_variants_caught` requires suffix tolerance, so extend slightly. If executor finds the broader pattern over-matches, fall back to the RESEARCH form and rely on `_TICK_BARE_RE` for the 5+ digit variants (current adversarial fixtures use 99999 = 5 digits, so bare-digit regex catches them anyway).
  </behavior>
  <action>
    1. Write `tests/test_narrative_validator.py` with all TestClasses listed in <behavior>. Commit RED first (`test(v2-01): RED narrative_validator adversarial corpus`).
    2. Write `narrative_validator.py` per the GREEN implementation. Commit GREEN (`feat(v2-01): narrative_validator hallucination guard`).
    3. Verify all 30+ tests in `tests/test_narrative_validator.py` PASS, including the 7-fixture parametrized roundtrip.
    4. Hook auto-runs black + ruff + pytest. If ruff complains about unused `Optional` import or `NARRATIVE_COMMON_NOUNS_WHITELIST` import (it's imported but only used as documentation in current code), either: (a) actually use it in validator (e.g., add a passive `_ = NARRATIVE_COMMON_NOUNS_WHITELIST` reference for downstream import discoverability), or (b) remove the import and document the constant lives in config.py for downstream use (preferred — keep validator pure). Pick (b).
  </action>
  <verify>
    <automated>python -m pytest tests/test_narrative_validator.py -p no:cov -v</automated>
  </verify>
  <acceptance_criteria>
    - `test -f narrative_validator.py` succeeds
    - `python -c "from narrative_validator import validate_narrative; ok, v = validate_narrative('Demo review для тренировки', {'ticks':set(),'rounds':set(),'demos':set(),'maps':set()}); print(ok, len(v))"` prints `True 0` (clean text with DIRECTIONS title cited)
    - `python -c "from narrative_validator import validate_narrative; ok, v = validate_narrative('тик 99999 показал', {'ticks':set(),'rounds':set(),'demos':set(),'maps':set()}); print(ok, [x['type'] for x in v])"` prints something like `False ['tick', 'no_direction_anchor']`
    - `grep -c "validate_narrative" narrative_validator.py` ≥ 1 (definition)
    - `grep -c "no_direction_anchor" narrative_validator.py` ≥ 1
    - `grep -c "_DEMO_RE" narrative_validator.py` ≥ 2 (compile + use)
    - `python -m pytest tests/test_narrative_validator.py -p no:cov` ALL PASS (≥25 tests including all 7 recorded-fixture cases)
    - `python -m pytest -p no:cov` full suite green
  </acceptance_criteria>
  <done>
    `validate_narrative` shipped. All 7 W0 recorded fixtures behave per spec: clean fixtures pass, hallucinated fixtures fail with correct violation types. SC-2 (0/10 reports with hallucinated refs) is now ENFORCEABLE during W3 eval. D-14 anchor enforced. Numeric refs strict, common nouns lax per D-06.
  </done>
</task>

</tasks>

<verification>
- `python -m pytest tests/test_narrative_validator.py tests/test_config.py -p no:cov` PASS
- `python -m pytest -p no:cov` full suite green (W0 + W1.01 ≥350 tests)
- `python -c "from narrative_validator import validate_narrative; from config import NARRATIVE_COMMON_NOUNS_WHITELIST; print(len(NARRATIVE_COMMON_NOUNS_WHITELIST))"` prints `8`
- Hallucinated-tick fixture round-trips through validator and produces ≥1 violation
- Clean fixture round-trips and produces zero violations
</verification>

<success_criteria>
- `narrative_validator.py` exists, exports `validate_narrative`, all adversarial tests green
- DIRECTIONS title anchor (D-14) enforced
- Numeric refs (tick, round) strict; demos strict (filename match); maps + common-nouns lax (D-06)
- Validator is pure function (no I/O, no LLM, no DB) — fully unit-testable
- Available for import by `interpretation_narrative.build_narrative_report` in W2
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-01-SUMMARY.md` documenting:
- validate_narrative signature + return shape
- Regex patterns shipped (with any deviation from RESEARCH if executor found edge cases)
- Test count delta (~30 new tests)
- Whether `_TICK_RE` was extended for RU suffixes or stayed at RESEARCH baseline
- Any adversarial fixtures that surfaced bugs in regex (note for downstream)
</output>
