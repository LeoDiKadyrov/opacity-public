---
phase: v2-interpretation-narrative
plan: 03
type: execute
wave: 2
depends_on: [01, 02]
files_modified:
  - prompts/coaching_v2.md
  - interpretation_narrative.py
  - tests/test_interpretation_narrative.py
  - config.py
autonomous: true
requirements: [REQ-4, REQ-1, REQ-11]
must_haves:
  truths:
    - "prompts/coaching_v2.md exists, contains the 3 D-13 section headers (## Что у тебя получается / ## Где теряешь время / ## Action этой недели)"
    - "Prompt template contains anti-hallucination instruction (REQ-4): explicit 'do not invent demo events, ticks, rounds, maps' wording"
    - "Prompt template contains tone calibration (D-10): brutally honest, address by nickname, no flattery"
    - "Prompt template contains length cap (D-12): hard cap 600 words wording"
    - "Prompt template contains DIRECTIONS reference policy (D-14): must cite at least one direction title"
    - "Prompt template uses {{DYNAMIC_USER_BLOCK}} placeholder for dynamic split (cacheable static portion before, dynamic after)"
    - "Prompt template language = Russian (REQ-11) for instructions + section headers; English allowed in code comments only"
    - "D-11: output language Russian (locked via REQ-11) — prompt template + eval rubric + tone calibration all in RU; eval set rated in RU"
    - "_render_prompt loads prompts/coaching_v2.md and produces non-placeholder system + user blocks"
    - "PLAYER_NAMES expanded to ≥10 REAL nickname entries (D-15 roster + benchmark donk/karrigan) — NO `player_<last4>` placeholders, hard-block via RosterResolutionError per B-1+B-4 revision"
  artifacts:
    - path: "prompts/coaching_v2.md"
      provides: "Versioned RU prompt template — system block + dynamic placeholder"
      contains: "Что у тебя получается"
      min_lines: 50
    - path: "interpretation_narrative.py"
      provides: "_render_prompt now actually loads prompt file (W2 replaces W1's placeholder)"
      contains: "{{DYNAMIC_USER_BLOCK}}"
    - path: "config.py"
      provides: "PLAYER_NAMES expanded to ≥10 entries from D-15 roster"
      min_lines: 0
  key_links:
    - from: "interpretation_narrative._render_prompt"
      to: "prompts/coaching_v2.md"
      via: "open(_PROMPT_PATH).read() + partition on {{DYNAMIC_USER_BLOCK}}"
      pattern: "DYNAMIC_USER_BLOCK"
    - from: "prompts/coaching_v2.md"
      to: "narrative_validator (D-14 anchor enforcement)"
      via: "prompt instructs LLM to cite ≥1 DIRECTIONS title — validator enforces"
      pattern: "Demo review|Map study|Aim_botz"
---

<objective>
Ship the prompt template (REQ-4) — the actual instructions the LLM follows. Convert W1's _render_prompt placeholder into a real loader. Expand PLAYER_NAMES to cover D-15 eval roster (R-1 mitigation). This plan turns W1's machinery into a coaching agent.

Purpose: Without a real prompt, build_narrative_report returns nonsense (it's still wired correctly via W1, but the LLM has no coaching instructions). This plan ships the actual prompt content per D-10 (tone) + D-12 (length) + D-13 (structure) + D-14 (anchor) + REQ-4 (anti-hallucination). The prompt is what makes Djok an actual coach instead of a templated tier-table dump.

Output:
- `prompts/coaching_v2.md` — RU prompt template, ~80 lines, versioned
- `interpretation_narrative.py` — `_render_prompt` upgraded to load real template (replaces W1 placeholder)
- `config.py` — PLAYER_NAMES expanded to ≥10 entries (D-15 roster: donk, karrigan, frozen, twistzz, jcobbb, sh1ro, plus 4 more from D-15 mid + bottom tiers)
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
@.planning/phases/v2-interpretation-narrative/v2-interpretation-01-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-02-SUMMARY.md
@CLAUDE.md
@interpretation.py
@config.py
@interpretation_narrative.py

<interfaces>
<!-- Existing contracts. -->

From W2 plan 02 — `interpretation_narrative._render_prompt` (placeholder version):
```python
def _render_prompt(rows, top_moments, player_context) -> tuple[str, str]:
    try:
        with open(_PROMPT_PATH, encoding="utf-8") as f:
            template = f.read()
    except FileNotFoundError:
        template = "STATIC_PLACEHOLDER\n{{DYNAMIC_USER_BLOCK}}"
    if "{{DYNAMIC_USER_BLOCK}}" in template:
        static, _, _ = template.partition("{{DYNAMIC_USER_BLOCK}}")
    else:
        static = template
    dynamic = json.dumps({...}, ensure_ascii=False, indent=2, default=str)
    return static, dynamic
```

This plan's job: ship `prompts/coaching_v2.md` that contains a real `{{DYNAMIC_USER_BLOCK}}` placeholder so the partition split works. Once the file exists, `_render_prompt` automatically uses it (no code change needed in build_narrative_report flow). Plan 03 may also tighten `_render_prompt` to fail loudly if template is missing — see Task 2 below.

From `interpretation.DIRECTIONS` (interpretation.py:61) — list of direction titles to surface in prompt:
- "Map study", "Demo review", "In-game prefire" (crosshair_angle peek)
- "Default angle audit", "Demo review", "Head-level discipline" (crosshair_angle hold)
- "Demo review", "Higher-tier pugs", "Deathmatch focus" (rt_visible_to_aim_ms peek)
- "Deathmatch volume", "Aim_botz before pug", "Optional drill: KovaaK's" (rt_aim_to_hit_ms peek)
- "Demo review", "Route by bottleneck", "Full-loop DM" (rt_visible_to_hit_ms peek)
- "Default angle commit", "Demo review", "Trigger discipline" (rt_visible_to_hit_ms hold)

The prompt instructs LLM to cite at least one of these by title verbatim (D-14 + validator enforcement).

D-15 player roster (CONTEXT.md):
- 3 top: donk (76561198386265483), karrigan (76561197989430253), frozen (TBD steamid)
- 4 mid: twistzz (TBD), jcobbb (TBD), sh1ro (76561198081484775), 1 random Spirit ≥100 trials (TBD from analytics.db)
- 3 bottom: 3 lowest-trial players that pass min-trials gate (TBD from analytics.db)

Memory note (reference_player_steam_ids): sh1ro=76561198081484775, karrigan=76561197989430253, donk=76561198386265483. Other Spirit/Faze/Astralis/G2/NaVi IDs in `reference_player_steam_ids.md` (operator may need to query analytics.db for missing IDs).
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Write prompts/coaching_v2.md (RU prompt template per D-10/D-12/D-13/D-14/REQ-4)</name>
  <files>prompts/coaching_v2.md</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md (D-10 tone, D-12 length, D-13 structure, D-14 anchor)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §Anthropic SDK Integration §Prompt caching lines 263-303 (static vs dynamic split)
    - interpretation.py lines 61-100 (DIRECTIONS dict — list ALL titles to mention in prompt as "directions menu")
    - .planning/PROJECT.md (project voice / vision)
  </read_first>
  <action>
    Write `prompts/coaching_v2.md` with the following structure. Content is RU per REQ-11; markdown structure preserved for downstream rendering. Place `{{DYNAMIC_USER_BLOCK}}` placeholder at the END of static portion, before any dynamic content. The file IS the static system block + a marker for where dynamic content goes when _render_prompt partitions it.

    Template:

    ```markdown
    # Djok Coach Prompt v2

    Ты — тренер по CS2, разбираешь reaction time данные игрока.

    ## Tone (брутально честный, без flattery)

    - Обращайся к игроку по нику. Никаких "good job", "great work", "потенциал есть".
    - Если данные показывают слабость — называй прямо. "Твой T1→T2 = 380мс, Average tier. У донка 312мс. Разница не во врождённой aim speed — это миф. Разница в pre-aim discipline и trigger commitment."
    - Не хеджируй ("возможно", "можно попробовать"). Прямые actionable observations.
    - Educate while diagnosing. Объясняй ПОЧЕМУ метрика плохая, не только ЧТО.
    - Без motivational platitudes. Без "продолжай работать".

    ## Output structure (СТРОГО эти 3 секции, в этом порядке)

    ```
    ## Что у тебя получается
    [На основе best-N moments — 1 best per metric, 6 metrics × 1 = до 6 моментов. Назови 1-2 СИЛЬНЫЕ стороны, привязав к конкретным моментам из top_moments если data позволяет: демо, раунд, тик. Если хороших моментов нет — короткая секция "пока сильных сторон в данных не видно".]

    ## Где теряешь время
    [На основе worst-N moments — 2 worst per metric. Главный bottleneck — T0→T1 (perception) или T1→T2 (motor). Назови 2-3 КОНКРЕТНЫЕ слабости, ОБЯЗАТЕЛЬНО привязав к моментам из top_moments: демо filename, round_number, tick. Объясни механизм (pre-aim, trigger discipline, perception lag).]

    ## Action этой недели
    [1-2 конкретных шага. ОБЯЗАТЕЛЬНО процитируй название минимум одного direction из меню ниже verbatim. Не паравфразируй — точное название.]
    ```

    ## Length

    Hard cap: 600 слов. Target: 500 слов ± 100. Не превышай 600 слов ни при каких условиях.

    ## Anti-hallucination — STRICT RULES

    Ты можешь упоминать ТОЛЬКО:
    - Демо-файлы, ник, тики, раунды, карты — которые УЖЕ присутствуют в `top_moments` секции input. Никаких выдуманных филмов.
    - Числовые значения метрик — точно из tier_rows input. Никаких округлений если не дано округлённое.
    - Названия directions — verbatim из меню ниже.

    Если ты упомянешь демо-файл, тик, раунд или карту, которой нет в input — narrative будет отброшен валидатором, и игрок получит fallback к статической tier table. Это снижает trust в продукте. **Не выдумывай.**

    Если данных мало (<20 engagements), скажи это явно: "На таком объёме данных уверенно сказать нельзя, но тренд показывает X."

    ## DIRECTIONS menu (процитируй минимум один title verbatim в "Action этой недели")

    **Crosshair angle (peek):** Map study | Demo review | In-game prefire
    **Crosshair angle (hold):** Default angle audit | Demo review | Head-level discipline
    **T0→T1 perception (peek):** Demo review | Higher-tier pugs | Deathmatch focus
    **T1→T2 motor (peek):** Deathmatch volume | Aim_botz before pug | Optional drill: KovaaK's
    **T0→T2 composite (peek):** Demo review | Route by bottleneck | Full-loop DM
    **T0→T2 composite (hold):** Default angle commit | Demo review | Trigger discipline

    ## Common nouns (можно использовать без attribution)

    peek, hold, aim, crosshair, pre-aim, deathmatch, DM, VOD — нейтральная терминология, не считается hallucination.

    Названия карт (de_mirage, Mirage, de_inferno, etc.) — если карта присутствует в `top_moments`, используй; если нет — не упоминай конкретные карты.

    ---

    {{DYNAMIC_USER_BLOCK}}
    ```

    Implementation notes:
    - The `{{DYNAMIC_USER_BLOCK}}` is the partition marker that `_render_prompt` uses to split static (cacheable) from dynamic (per-call). Everything ABOVE it goes into the cached system block; everything below (which is empty in the file but populated at runtime with the JSON dynamic payload from `_render_prompt`) is the user message.
    - Word count of the static portion: aim for ≤500 words to keep cache cheap. The actual prose above is ~350 words RU + structure markers.
    - Section headers MUST be exactly `## Что у тебя получается`, `## Где теряешь время`, `## Action этой недели` per D-13 (the validator does not enforce these — but the eval rubric will rate "structure" dim and a misnamed section drops the score).
    - DIRECTIONS menu lists EXACTLY the titles from `interpretation.DIRECTIONS` — keep in sync if interpretation.DIRECTIONS evolves (note this in summary so future maintainers know to update).
  </action>
  <verify>
    <automated>python -c "from pathlib import Path; t = Path('prompts/coaching_v2.md').read_text(encoding='utf-8'); assert '{{DYNAMIC_USER_BLOCK}}' in t; assert '## Что у тебя получается' in t; assert '## Где теряешь время' in t; assert '## Action этой недели' in t; assert 'Demo review' in t; assert '600 слов' in t; assert 'не выдумывай' in t.lower() or 'Не выдумывай' in t; print('OK')"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f prompts/coaching_v2.md` succeeds
    - `grep -c "Что у тебя получается" prompts/coaching_v2.md` ≥ 2 (header + structure description reference)
    - `grep -c "Где теряешь время" prompts/coaching_v2.md` ≥ 2
    - `grep -c "Action этой недели" prompts/coaching_v2.md` ≥ 2
    - `grep -c "Demo review" prompts/coaching_v2.md` ≥ 1 (DIRECTIONS menu reference)
    - `grep -c "{{DYNAMIC_USER_BLOCK}}" prompts/coaching_v2.md` == 1 (single partition marker)
    - `grep -i -c "не выдумывай\|hallucination\|don't invent" prompts/coaching_v2.md` ≥ 1 (anti-hallucination instruction)
    - `grep -c "600 слов\|600 words" prompts/coaching_v2.md` ≥ 1 (length cap)
    - `wc -l prompts/coaching_v2.md` returns ≥ 50
    - Prompt is RU (visual inspection — primary instruction language)
  </acceptance_criteria>
  <done>
    Prompt template shipped. _render_prompt now loads real content. The next build_narrative_report call will send actual coaching instructions to Anthropic instead of the W1 "STATIC_PLACEHOLDER" stub.
  </done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: Tighten _render_prompt + expand PLAYER_NAMES (D-15 roster + R-1 mitigation)</name>
  <files>interpretation_narrative.py, config.py, tests/test_interpretation_narrative.py, tests/test_config.py</files>
  <read_first>
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-RESEARCH.md §R-1 PLAYER_NAMES coverage gap (line 867)
    - .planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md D-15 (player roster spec)
    - config.py current PLAYER_NAMES (line 172) — only 2 entries (donk, karrigan)
    - interpretation_narrative.py _render_prompt (W2 plan 02 implementation)
    - tests/test_interpretation_narrative.py (existing test patterns from W2)
    - Memory file `reference_player_steam_ids.md` (Spirit/Faze player IDs lookup)
  </read_first>
  <behavior>
    RED tests:
    - `test_render_prompt_loads_real_template_when_file_exists(tmp_path, monkeypatch)` — write a stub file with `{{DYNAMIC_USER_BLOCK}}` to tmp_path; monkeypatch `interpretation_narrative._PROMPT_PATH`; call `_render_prompt(...)`; assert returned static block contains stub content NOT the W1 placeholder string
    - `test_render_prompt_partitions_at_marker(tmp_path, monkeypatch)` — stub template = "BEFORE\n{{DYNAMIC_USER_BLOCK}}\nAFTER"; assert static="BEFORE\n", dynamic JSON does NOT contain "AFTER" (AFTER is dropped per partition logic)
    - `test_render_prompt_warns_when_template_missing(monkeypatch, caplog)` — set _PROMPT_PATH to nonexistent file; assert raises NarrativeBuildError matching /prompt template/ OR logs a warning + uses placeholder. **Decision: prefer raising NarrativeBuildError** — fail-soft semantics already covered upstream; W2-shipped placeholder was a temporary unit-test affordance that should now be removed.

    Then RED tests for PLAYER_NAMES expansion:
    - `test_player_names_has_at_least_ten_entries` — `from config import PLAYER_NAMES; assert len(PLAYER_NAMES) >= 10`
    - `test_player_names_includes_donk_and_karrigan` — preserved
    - `test_player_names_includes_d15_top_tier` — `assert 76561198386265483 in PLAYER_NAMES; assert 76561197989430253 in PLAYER_NAMES; assert 76561198081484775 in PLAYER_NAMES` (donk, karrigan, sh1ro per memory `reference_player_steam_ids`)
    - `test_player_names_keys_are_int_not_str` — guard against accidental string SteamIDs

    GREEN:
    1. Update `interpretation_narrative._render_prompt`:
    ```python
    def _render_prompt(rows, top_moments, player_context) -> tuple[str, str]:
        try:
            with open(_PROMPT_PATH, encoding="utf-8") as f:
                template = f.read()
        except FileNotFoundError as e:
            raise NarrativeBuildError(
                f"Prompt template not found at {_PROMPT_PATH}. Run plan v2-03 first."
            ) from e
        if "{{DYNAMIC_USER_BLOCK}}" not in template:
            raise NarrativeBuildError(
                f"Prompt template at {_PROMPT_PATH} missing {{DYNAMIC_USER_BLOCK}} marker"
            )
        static, _, _ = template.partition("{{DYNAMIC_USER_BLOCK}}")
        dynamic = json.dumps({
            "player": player_context,
            "tier_rows": rows,
            "top_moments": top_moments,
        }, ensure_ascii=False, indent=2, default=str)
        return static, dynamic
    ```

    2. Expand `config.PLAYER_NAMES` to at least 10 entries. Use known SteamIDs from memory + analytics.db (operator may query DB for unknown IDs):
    ```python
    PLAYER_NAMES: dict[int, str] = {
        # Spirit roster
        76561198386265483: "donk",
        76561198081484775: "sh1ro",
        # 3 more Spirit (zontix, magixx, tn1r — operator: query analytics.db SELECT DISTINCT player_steamid for confirmed IDs)
        # ... TBD numeric IDs from analytics.db ...
        # Faze roster
        76561197989430253: "karrigan",
        # Other Faze (twistzz, jacob, broky, frozen)
        # ... TBD ...
        # Bottom-tier players from D-15 (3 lowest-trial players that pass min-trials gate)
        # ... TBD ...
    }
    ```

    Since exact additional SteamIDs depend on analytics.db state, the executor MUST:
    - Query the DB to find candidate SteamIDs: `SELECT player_steamid, COUNT(*) FROM engagements GROUP BY player_steamid ORDER BY COUNT(*) DESC LIMIT 30;`
    - Map known IDs from `reference_player_steam_ids.md` memory
    - Pick 8 additional entries (10 total) with REAL nicknames resolved per the HARD BLOCK below — placeholder fallbacks are forbidden by D-10 + D-15
    - Document chosen mapping in plan SUMMARY

    **HARD BLOCK per D-10 + D-15 (B-1 + B-4 revision, no placeholders allowed):**

    The executor MUST resolve REAL nicknames for ALL 10 D-15 roster players. Placeholder strings like `player_<last4>` are FORBIDDEN — D-10 says "address player by nickname" and D-15 specifies a real-player roster.

    Resolution path:
    1. Confirmed from memory `reference_player_steam_ids.md`: donk=76561198386265483, karrigan=76561197989430253, sh1ro=76561198081484775. Use these directly.
    2. The executor SHOULD attempt to look up the remaining 7 nicknames from one of:
       - `reference_player_steam_ids.md` memory file (full Spirit/Faze/Astralis/G2/NaVi roster mapping documented there per MEMORY.md index)
       - HLTV.org / liquipedia.net player-page lookup by SteamID
       - Manual cross-reference if the user has shared a roster doc
    3. If, after a reasonable lookup attempt, the executor cannot resolve all 10 nicknames AND/OR cannot assemble a 10-real-player D-15 roster from the current `analytics.db`:
       - Raise a `RosterResolutionError` (define inline in the script if not already in `interpretation_narrative.py`) with a message listing exactly which SteamIDs were unresolvable and which roster slots could not be filled.
       - STOP execution. Do NOT commit a partial PLAYER_NAMES dict. Do NOT use any placeholder fallback.
       - Surface the error so the operator can supply nicknames or expand the demo corpus before proceeding to Plan 05.

    R-1 mitigation language in RESEARCH about `player_<short_steamid>` placeholders is HEREBY OVERRIDDEN by this revision: that fallback was acceptable as a research-phase suggestion but is rejected at planning-phase per locked decisions D-10 + D-15.
  </behavior>
  <action>
    1. Write RED tests in `tests/test_interpretation_narrative.py` (TestRenderPrompt class) + `tests/test_config.py` (PLAYER_NAMES expansion tests). Commit (`test(v2-03): RED _render_prompt tightening + PLAYER_NAMES expansion`).
    2. Update `interpretation_narrative._render_prompt` to raise NarrativeBuildError on missing template / missing marker.
    3. Query the DB for candidate SteamIDs:
       ```bash
       python -c "import sqlite3; c = sqlite3.connect('analytics.db'); print(c.execute('SELECT player_steamid, COUNT(*) FROM engagements GROUP BY player_steamid ORDER BY COUNT(*) DESC LIMIT 30').fetchall())"
       ```
    4. Cross-reference with `reference_player_steam_ids` memory file (HAS the full Spirit/Faze/Astralis/G2/NaVi mapping per MEMORY.md index). Confirmed seed entries:
       - 76561198386265483 → "donk"
       - 76561197989430253 → "karrigan"
       - 76561198081484775 → "sh1ro"
       Resolve 7 MORE real nicknames from the memory file + DB top-trial steamid list — combine the two: pick the 7 highest-trial-count SteamIDs that have a confirmed nickname in `reference_player_steam_ids.md`. If a top-trial SteamID is not in the memory file, look it up on HLTV/liquipedia by SteamID. **NO `player_<last4>` placeholders permitted** — see HARD BLOCK section above. If 7 confirmed-real nicknames cannot be assembled, raise `RosterResolutionError` and stop.
    5. Commit GREEN (`feat(v2-03): _render_prompt enforces template presence + PLAYER_NAMES ≥10 entries`).
    6. Verify all tests pass.
  </action>
  <verify>
    <automated>python -m pytest tests/test_interpretation_narrative.py::TestRenderPrompt tests/test_config.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `python -c "from config import PLAYER_NAMES; assert len(PLAYER_NAMES) >= 10; assert 76561198386265483 in PLAYER_NAMES; assert 76561197989430253 in PLAYER_NAMES; assert 76561198081484775 in PLAYER_NAMES; print(len(PLAYER_NAMES))"` prints `10` or higher
    - `python -c "from config import PLAYER_NAMES; assert all(isinstance(k, int) for k in PLAYER_NAMES); print('OK')"` prints "OK"
    - `grep -c "raise NarrativeBuildError" interpretation_narrative.py` ≥ 6 (W2's raise sites + 2 new in _render_prompt)
    - `grep -c "DYNAMIC_USER_BLOCK" interpretation_narrative.py` ≥ 2 (check for marker + partition use)
    - `python -c "import interpretation_narrative as inv; from pathlib import Path; assert Path(inv._PROMPT_PATH).exists()"` exits 0 (prompt file ships in plan 03 task 1, this task verifies it's resolvable from default _PROMPT_PATH)
    - `python -m pytest tests/test_interpretation_narrative.py -p no:cov` ALL PASS (W2 tests + new TestRenderPrompt tests, ≥4 new)
    - `python -m pytest tests/test_config.py -p no:cov` ALL PASS (≥4 PLAYER_NAMES tests new)
    - `python -m pytest -p no:cov` full suite green
  </acceptance_criteria>
  <done>
    _render_prompt now loads the real RU prompt template; build_narrative_report sends actual coaching instructions to Anthropic. PLAYER_NAMES has ≥10 entries — eval roster D-15 in W3 can address all 10 players by display name. R-1 mitigation done.
  </done>
</task>

</tasks>

<verification>
- `python -m pytest -p no:cov` full suite green
- `python -c "import interpretation_narrative as inv; s, d = inv._render_prompt([], {}, {'player_steamid': 76561198386265483, 'engagement_type': 'peek', 'player_name': 'donk', 'n_total_engagements': 100}); assert 'Что у тебя получается' in s; assert 'Demo review' in s; print('OK')"` prints "OK"
- `python -c "from config import PLAYER_NAMES; print(len(PLAYER_NAMES), 'players')"` prints number ≥ 10
</verification>

<success_criteria>
- prompts/coaching_v2.md committed; loads cleanly via _render_prompt
- _render_prompt raises NarrativeBuildError on missing file (no silent placeholder fallback)
- PLAYER_NAMES ≥10 entries — D-15 roster nicks resolvable
- DIRECTIONS menu in prompt mirrors interpretation.DIRECTIONS titles verbatim (D-14 + validator anchor enforceable)
- Static prompt block ~350-500 words RU; cacheable
- Ready for W3 to wire report_generator integration
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-03-SUMMARY.md` documenting:
- prompts/coaching_v2.md final word count + key sections
- PLAYER_NAMES final entries (full list of SteamID → name)
- Confirmation that all 10 PLAYER_NAMES entries are REAL nicknames (no placeholders); if RosterResolutionError raised, document which IDs were unresolvable and operator path forward
- Any DIRECTIONS title that didn't fit cleanly in prompt menu (synced with interpretation.DIRECTIONS as of W3 ship)
- _render_prompt now raises (not silently placeholder-falls-back) — confirm fail-soft path in build_narrative_report still catches via NarrativeBuildError
</output>
