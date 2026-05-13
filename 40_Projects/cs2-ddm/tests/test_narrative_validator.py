"""Phase v2 narrative validator tests. Task IDs map to v2-VALIDATION.md.

Adversarial corpus drives REQ-5 (hallucination guard) + REQ-11 (RU language gate).

Per D-06: numeric refs (tick, round) — strict exact match.
Per D-08: allowed_refs has keys {"ticks", "rounds", "demos", "maps"}.
Per D-09: violations = list[dict] with {type, value, context_snippet}.
Per D-14: text MUST cite >=1 DIRECTIONS title.

Note: W0 plan 00 was scheduled to ship `tests/fixtures/anthropic_recorded/*.json`
recorded fixtures. Those are not present in this worktree base; the seven
adversarial scenarios from RESEARCH §Testing Strategy are inlined below as
literal text payloads to keep this plan self-contained (deviation Rule 3 —
blocking dependency on missing artifact, replaced with equivalent inline data).
"""

import pytest

from narrative_validator import validate_narrative


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────


def _allowed(
    *,
    ticks: set | None = None,
    rounds: set | None = None,
    demos: set | None = None,
    maps: set | None = None,
) -> dict:
    """Build canonical allowed_refs dict per D-08 with sensible defaults."""
    return {
        "ticks": ticks or set(),
        "rounds": rounds or set(),
        "demos": demos or set(),
        "maps": maps or set(),
    }


# Single-shot text snippets that include a DIRECTIONS title anchor + Cyrillic
# so non-target violation passes don't trip on D-14 / REQ-11 noise.
_ANCHOR_TAIL_RU = " Demo review поможет."


# ─────────────────────────────────────────────────────────────────────────────
# Pass 1 — demo filename detection (REQ-5)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateDemoRefs:
    """Pass 1 — demo filename detection."""

    def test_demo_in_allowed_passes(self):  # v2-01-D-1
        text = "Посмотри demo spirit-vs-faze.dem." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(
            text, _allowed(demos={"spirit-vs-faze.dem"})
        )
        assert ok is True, viols
        assert viols == []

    def test_demo_not_in_allowed_fails(self):  # v2-01-D-2
        text = "Посмотри fakedemo123.dem." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed(demos={"real.dem"}))
        assert ok is False
        assert any(
            v["type"] == "demo" and v["value"] == "fakedemo123.dem"
            for v in viols
        )

    def test_demo_case_insensitive_match(self):  # v2-01-D-3
        text = "Посмотри Spirit-VS-Faze.DEM." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(
            text, _allowed(demos={"spirit-vs-faze.dem"})
        )
        assert ok is True, viols

    def test_no_demo_mention_no_violation(self):  # v2-01-D-4
        text = "Тренируйся регулярно." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "demo" for v in viols)


# ─────────────────────────────────────────────────────────────────────────────
# Pass 2 — numeric tick refs (REQ-5)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateTicks:
    """Pass 2 — anchored + bare digit tick detection (strict per D-06)."""

    def test_anchored_tick_pattern_caught(self):  # v2-01-T-1
        text = "На тик 99999 ты опоздал." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "tick" and v["value"] == 99999 for v in viols
        )

    def test_anchored_tick_in_allowed_passes(self):  # v2-01-T-2
        text = "На тик 12345 ты вовремя." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed(ticks={12345}))
        assert ok is True, viols
        assert not any(v["type"] == "tick" for v in viols)

    def test_bare_5digit_caught_as_tick(self):  # v2-01-T-3
        text = "Около 99999 момент важный." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "tick" and v["value"] == 99999 for v in viols
        )

    def test_2digit_score_not_flagged(self):  # v2-01-T-4
        text = "Счёт 16-12 в твою пользу." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "tick" for v in viols)

    def test_decimal_not_flagged(self):  # v2-01-T-5
        text = "Hit-rate 12.345 процентов." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "tick" for v in viols), viols

    def test_thousands_separator_not_flagged(self):  # v2-01-T-6
        text = "Зарегистрировано 12,345 единиц." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "tick" for v in viols), viols

    def test_ru_suffix_variants_caught_via_bare_5digit(self):  # v2-01-T-7
        # The bare 5+ digit fallback MUST catch the integer regardless of
        # any RU suffix attached to "тик".
        for variant in ("тике 99999", "тиком 99999", "тика 99999"):
            text = f"На {variant} опоздал." + _ANCHOR_TAIL_RU
            ok, viols = validate_narrative(text, _allowed())
            assert ok is False, variant
            assert any(
                v["type"] == "tick" and v["value"] == 99999 for v in viols
            ), variant

    def test_anchored_4digit_tick_caught(self):  # v2-01-T-8
        # truncated_max_tokens fixture variant: tick 1234 (4 digits) — caught
        # by anchored tick regex (RESEARCH \d{4,} for keyword variant).
        text = "На тик 1234 опоздал." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "tick" and v["value"] == 1234 for v in viols
        )

    def test_anchored_tick_no_double_count(self):  # v2-01-T-9
        # тик 99999 should yield exactly ONE tick violation, not two
        # (anchored pass + bare pass both match same offset).
        text = "На тик 99999 опоздал." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        tick_viols = [v for v in viols if v["type"] == "tick"]
        assert len(tick_viols) == 1, tick_viols


# ─────────────────────────────────────────────────────────────────────────────
# Pass 3 — round numbers (REQ-5)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateRounds:
    """Pass 3 — round number detection (RU + EN morphology)."""

    def test_round_anchor_caught(self):  # v2-01-R-1
        text = "В раунд 99 ты упустил темп." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "round" and v["value"] == 99 for v in viols
        )

    def test_round_in_allowed_passes(self):  # v2-01-R-2
        text = "В раунд 14 решение верное." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed(rounds={14}))
        assert ok is True, viols
        assert not any(v["type"] == "round" for v in viols)

    def test_round_ru_suffix_variants(self):  # v2-01-R-3
        for variant in ("раунде 99", "раунда 99", "раундом 99"):
            text = f"В {variant} ошибка." + _ANCHOR_TAIL_RU
            ok, viols = validate_narrative(text, _allowed())
            assert ok is False, variant
            assert any(
                v["type"] == "round" and v["value"] == 99 for v in viols
            ), variant

    def test_english_round_caught(self):  # v2-01-R-4
        text = "In round 99 you mispositioned." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "round" and v["value"] == 99 for v in viols
        )

    def test_three_digit_round_not_caught(self):  # v2-01-R-5
        # Acceptable design choice: \d{1,2} — real CS2 rounds 1-30.
        text = "В раунд 100 тренировки." + _ANCHOR_TAIL_RU
        _, viols = validate_narrative(text, _allowed())
        # round regex anchors on \d{1,2}, so 100 NOT flagged as round.
        # The bare 5+ digit regex also won't match (3 digits).
        # Acceptable — design accepts this miss to avoid false positives.
        assert not any(v["type"] == "round" for v in viols)


# ─────────────────────────────────────────────────────────────────────────────
# Pass 4 — D-06 map whitelist (no validation, soft pass)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateMaps:
    """D-06 — map names allowed without attribution; never raise violations."""

    def test_known_map_passes_without_attribution(self):  # v2-01-M-1
        text = "На Mirage отлично работаешь." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(
            text, _allowed(maps={"de_mirage"})
        )
        assert ok is True, viols
        assert not any(v["type"] == "map" for v in viols)

    def test_known_map_de_prefix_passes(self):  # v2-01-M-2
        text = "На de_mirage защита надёжная." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(
            text, _allowed(maps={"de_mirage"})
        )
        assert ok is True, viols
        assert not any(v["type"] == "map" for v in viols)

    def test_unknown_map_does_not_fail(self):  # v2-01-M-3
        # D-06: maps are SOFT (whitelisted, not validated). Unknown map ok.
        text = "На Cache был эксперимент." + _ANCHOR_TAIL_RU
        ok, viols = validate_narrative(text, _allowed())
        assert ok is True, viols
        assert not any(v["type"] == "map" for v in viols)


# ─────────────────────────────────────────────────────────────────────────────
# Pass 5 — DIRECTIONS title anchor (D-14)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateDirectionAnchor:
    """D-14 — narrative MUST cite >=1 DIRECTIONS title verbatim."""

    def test_no_direction_title_fails(self):  # v2-01-A-1
        text = "Тренируйся регулярно и анализируй ошибки."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(v["type"] == "no_direction_anchor" for v in viols)

    def test_one_direction_title_passes(self):  # v2-01-A-2
        text = "Demo review поможет тебе разобрать ошибки."
        ok, viols = validate_narrative(text, _allowed())
        # No tick/round/demo refs + Cyrillic + DIRECTIONS title → all pass.
        assert ok is True, viols
        assert not any(v["type"] == "no_direction_anchor" for v in viols)

    def test_case_insensitive_anchor(self):  # v2-01-A-3
        text = "demo REVIEW поможет тебе."
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "no_direction_anchor" for v in viols), viols

    def test_partial_match_does_not_count(self):  # v2-01-A-4
        # "Demo" alone (without "review") should NOT satisfy anchor — substring
        # match must be the full title.
        text = "Demo поможет тебе разобрать ошибки."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(v["type"] == "no_direction_anchor" for v in viols)


# ─────────────────────────────────────────────────────────────────────────────
# Pass 6 — RU language gate (REQ-11 / W-3)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateRussianLanguage:
    """REQ-11 — narrative MUST contain >=1 Cyrillic char (W-3)."""

    def test_pure_english_text_fails_with_non_russian_output_violation(self):  # v2-01-L-1
        text = "Donk had elite reaction time. Demo review will help."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(v["type"] == "non_russian_output" for v in viols)

    def test_text_with_at_least_one_cyrillic_char_passes_language_gate(self):  # v2-01-L-2
        text = "Donk: Demo review поможет."
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "non_russian_output" for v in viols), viols

    def test_pure_cyrillic_text_passes_language_gate(self):  # v2-01-L-3
        text = "Что у тебя получается. Demo review."
        _, viols = validate_narrative(text, _allowed())
        assert not any(v["type"] == "non_russian_output" for v in viols), viols


# ─────────────────────────────────────────────────────────────────────────────
# D-09 — structured violation shape
# ─────────────────────────────────────────────────────────────────────────────


class TestViolationShape:
    """D-09 — every violation must carry {type, value, context_snippet}."""

    def test_violation_has_required_keys(self):  # v2-01-S-1
        text = "На тик 99999 опоздал. fakedemo.dem смотри."
        _, viols = validate_narrative(text, _allowed())
        assert len(viols) >= 1
        for v in viols:
            assert "type" in v
            assert "value" in v
            assert "context_snippet" in v
            assert isinstance(v["type"], str)
            assert isinstance(v["context_snippet"], str)

    def test_context_snippet_includes_offending_token(self):  # v2-01-S-2
        text = "Длинный префикс перед fakedemo123.dem и после suffix."
        _, viols = validate_narrative(text, _allowed())
        demo_viols = [v for v in viols if v["type"] == "demo"]
        assert demo_viols
        assert "fakedemo123.dem" in demo_viols[0]["context_snippet"].lower()


# ─────────────────────────────────────────────────────────────────────────────
# Recorded-fixture parity (W0 adversarial corpus, inlined per Rule 3 deviation)
# ─────────────────────────────────────────────────────────────────────────────


class TestValidateRecordedFixtures:
    """Mirrors the seven W0 fixture scenarios (RESEARCH §Testing Strategy)."""

    def test_ok_donk_peek_fixture_passes(self):  # v2-01-F-1
        text = (
            "## Что у тебя получается\n"
            "На spirit-vs-faze.dem ты в раунд 14 показал себя.\n"
            "## Где теряешь время\n"
            "Demo review даст ответы."
        )
        ok, viols = validate_narrative(
            text,
            _allowed(
                ticks={12345}, rounds={14}, demos={"spirit-vs-faze.dem"}
            ),
        )
        assert ok is True, viols

    def test_hallucinated_tick_fixture_fails(self):  # v2-01-F-2
        text = (
            "На тик 99999999 ты опоздал. Demo review нужен."
        )
        ok, viols = validate_narrative(
            text, _allowed(ticks={12345})
        )
        assert ok is False
        assert any(
            v["type"] == "tick" and v["value"] == 99999999 for v in viols
        )

    def test_hallucinated_demo_fixture_fails(self):  # v2-01-F-3
        text = "Посмотри fakedemo123.dem. Demo review поможет."
        ok, viols = validate_narrative(
            text, _allowed(demos={"spirit-vs-faze.dem"})
        )
        assert ok is False
        assert any(
            v["type"] == "demo" and v["value"] == "fakedemo123.dem"
            for v in viols
        )

    def test_no_direction_anchor_fixture_fails(self):  # v2-01-F-4
        text = "Тренируйся регулярно и будет лучше."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(v["type"] == "no_direction_anchor" for v in viols)

    def test_clean_paraphrase_fixture_passes(self):  # v2-01-F-5
        # No explicit refs; cites Demo review anchor + Cyrillic + whitelisted Mirage.
        text = "На Mirage Demo review даст разбор твоих ошибок."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is True, viols

    def test_truncated_max_tokens_fixture_fails(self):  # v2-01-F-6
        # Truncated narrative with anchored tick 1234 (4 digits, anchored regex).
        text = "На тик 1234 опоздал. Demo review нуж"
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        assert any(
            v["type"] == "tick" and v["value"] == 1234 for v in viols
        )

    def test_refusal_fixture_validator_outcome(self):  # v2-01-F-7
        # Refusal text — typically empty or "I cannot help with that".
        # Validator runs anyway; would fail on no_direction_anchor + non_russian_output.
        text = "I cannot generate that."
        ok, viols = validate_narrative(text, _allowed())
        assert ok is False
        types = {v["type"] for v in viols}
        assert "no_direction_anchor" in types
        assert "non_russian_output" in types
