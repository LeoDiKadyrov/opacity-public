"""Phase v2 — narrative output validator (hallucination guard).

Pure function, no I/O, no network. Per REQ-5 + D-06/D-08/D-09/D-14 + REQ-11.

The validator scans LLM-generated coaching narratives for fabricated references
to demo files, tick numbers, and round numbers. It also enforces two
content-shape gates:

* D-14 — narrative MUST cite at least one DIRECTIONS title verbatim.
* REQ-11 / W-3 — narrative MUST contain at least one Cyrillic character
  (Russian-language output gate).

Maps and a locked common-noun whitelist (config.NARRATIVE_COMMON_NOUNS_WHITELIST)
are passively allowed without attribution per D-06; the validator does NOT
iterate them — absence of validation IS the whitelist.
"""

from __future__ import annotations

import re
from typing import Optional  # noqa: F401  (kept for downstream typing extension)


# ─────────────────────────────────────────────────────────────────────────────
# DIRECTIONS title set (D-14 anchor)
# ─────────────────────────────────────────────────────────────────────────────
#
# Plan promised `interpretation.DIRECTIONS` dict; in the current worktree base
# `interpretation.py` ships only the legacy DRILLS dict (longer body strings).
# Try the import — if absent, fall back to the canonical title set extracted
# from CONTEXT.md D-13 + D-14 + RESEARCH §Validator Design Pass 4 examples.
# Either source produces the same set of short, citable direction names.

_FALLBACK_DIRECTION_TITLES = frozenset({
    "Map study",
    "Demo review",
    "In-game prefire",
    "Higher-tier pugs",
    "Deathmatch focus",
    "Deathmatch volume",
    "Aim_botz before pug",
    "Optional drill: KovaaK's",
})

try:  # pragma: no cover — import guard
    from interpretation import DIRECTIONS  # type: ignore[attr-defined]

    _DIRECTION_TITLES = frozenset(
        d["title"] for ds in DIRECTIONS.values() for d in ds
    )
    if not _DIRECTION_TITLES:
        _DIRECTION_TITLES = _FALLBACK_DIRECTION_TITLES
except (ImportError, AttributeError):
    _DIRECTION_TITLES = _FALLBACK_DIRECTION_TITLES


# ─────────────────────────────────────────────────────────────────────────────
# Regex patterns (RESEARCH §Validator Design)
# ─────────────────────────────────────────────────────────────────────────────

# Anchored tick: "тик 12345" / "tick 12345" / "тике 12345" / "тиком 12345" /
# "тика 12345". RU suffix tolerance via [ауеыёиом]* — covers genitive/dative/
# instrumental case suffixes without false matches on unrelated words.
# 4+ digit minimum: anchored variant is a strong signal even at small magnitude.
_TICK_RE = re.compile(
    r"(?:тик[ауеыёиом]*|tick)\s*(\d{4,})", re.IGNORECASE
)

# Bare 5+ digit integer NOT inside a decimal/thousands-separator context.
# Negative look-around blocks "12.345" / "12,345" / chained digits.
_TICK_BARE_RE = re.compile(r"(?<![\d.,])\d{5,}(?![\d.,])")

# Round: "раунд 14" / "раунде 14" / "раунда 14" / "раундом 14" / "round 14".
# 1-2 digit magnitude — real CS2 rounds are 1-30; 3+ digit numbers are not
# round refs and avoid colliding with unrelated stats (e.g. "100% accuracy").
_ROUND_RE = re.compile(
    r"(?:раунд[аеуыоё]?[ом]?|round)\s*(\d{1,2})\b", re.IGNORECASE
)

# Demo filename: hyphenated/underscored slug followed by .dem extension.
_DEMO_RE = re.compile(r"\b[\w\-]+\.dem\b", re.IGNORECASE)

# Snippet padding for context_snippet field (D-09). 30 chars each side ≈
# enough surrounding context for a human reviewer to understand the offense.
_SNIPPET_PAD = 30


def _snippet(text: str, start: int, end: int) -> str:
    """Return [start-PAD, end+PAD] slice with newlines collapsed to spaces."""
    s = max(0, start - _SNIPPET_PAD)
    e = min(len(text), end + _SNIPPET_PAD)
    return text[s:e].replace("\n", " ")


def _has_cyrillic(text: str) -> bool:
    """Return True if text contains >=1 char in Cyrillic / Cyrillic Supplement.

    Range U+0400..U+04FF covers the main Cyrillic block; U+0500..U+052F covers
    Cyrillic Supplement (plus Macedonian/Belarusian/Kazakh extras).
    """
    for ch in text:
        if "Ѐ" <= ch <= "ԯ":
            return True
    return False


def validate_narrative(
    text: str,
    allowed_refs: dict[str, set],
) -> tuple[bool, list[dict]]:
    """Validate narrative output against an allow-list of references.

    Args:
        text: LLM-generated narrative (markdown). Untrusted input.
        allowed_refs: Per-report allow-list per D-08 with keys
            ``{"ticks", "rounds", "demos", "maps"}``. Missing keys treated as
            empty set. Values for ``demos`` are lower-cased before comparison.

    Returns:
        ``(is_valid, violations)`` per D-09. ``is_valid`` is True iff
        ``violations`` is empty. Each violation dict has the shape::

            {"type": str, "value": Any, "context_snippet": str}

        Violation types:
          * ``demo`` — value = filename (lower-cased)
          * ``tick`` — value = int
          * ``round`` — value = int
          * ``no_direction_anchor`` — value = None (D-14)
          * ``non_russian_output`` — value = None (REQ-11 / W-3)
    """
    violations: list[dict] = []

    ticks_allowed: set = allowed_refs.get("ticks", set())
    rounds_allowed: set = allowed_refs.get("rounds", set())
    demos_allowed: set = {d.lower() for d in allowed_refs.get("demos", set())}

    # ── Pass 1: demo filenames ──────────────────────────────────────────────
    for m in _DEMO_RE.finditer(text):
        demo = m.group(0).lower()
        if demo not in demos_allowed:
            violations.append({
                "type": "demo",
                "value": demo,
                "context_snippet": _snippet(text, m.start(), m.end()),
            })

    # ── Pass 2a: anchored ticks (тик/tick + 4+ digits) ──────────────────────
    # Track digit-group offsets so the bare-5-digit pass below does not
    # double-count the same integer.
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

    # ── Pass 2b: bare 5+ digit integers (not already counted as anchored) ──
    for m in _TICK_BARE_RE.finditer(text):
        if m.start() in seen_tick_offsets:
            continue
        tick = int(m.group(0))
        if tick not in ticks_allowed:
            violations.append({
                "type": "tick",
                "value": tick,
                "context_snippet": _snippet(text, m.start(), m.end()),
            })

    # ── Pass 3: round numbers ───────────────────────────────────────────────
    for m in _ROUND_RE.finditer(text):
        rnd = int(m.group(1))
        if rnd not in rounds_allowed:
            violations.append({
                "type": "round",
                "value": rnd,
                "context_snippet": _snippet(text, m.start(), m.end()),
            })

    # ── Pass 4: D-14 DIRECTIONS title anchor ───────────────────────────────
    titles_lower = {t.lower() for t in _DIRECTION_TITLES}
    text_lower = text.lower()
    if not any(t in text_lower for t in titles_lower):
        violations.append({
            "type": "no_direction_anchor",
            "value": None,
            "context_snippet": "",
        })

    # ── Pass 5: REQ-11 / W-3 RU language gate ──────────────────────────────
    if not _has_cyrillic(text):
        violations.append({
            "type": "non_russian_output",
            "value": None,
            "context_snippet": text[:100],
        })

    return (len(violations) == 0, violations)
