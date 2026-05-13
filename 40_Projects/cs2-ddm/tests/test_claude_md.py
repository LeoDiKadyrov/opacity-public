"""B-2 — Nyquist gate: confirm CLAUDE.md documents Phase v2 LLM coaching layer.

These tests exist so the `type="auto"` Plan 06 Task 1 CLAUDE.md edit has an
automated verifier (otherwise it would have grep-only verification per
Nyquist Rule 8a). They are intentionally tiny and string-level — the goal is
"the words exist in the canonical project doc", not full prose review.
"""

from pathlib import Path


_CLAUDE_MD = Path(__file__).resolve().parents[1] / "CLAUDE.md"


def test_anthropic_api_key_documented() -> None:
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY" in text, (
        "Phase v2 requires ANTHROPIC_API_KEY documented in CLAUDE.md"
    )


def test_interpretation_narrative_module_referenced() -> None:
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "interpretation_narrative" in text, (
        "CLAUDE.md must reference the v2 module name (interpretation_narrative)"
    )


def test_narrative_failures_log_referenced() -> None:
    text = _CLAUDE_MD.read_text(encoding="utf-8")
    assert "narrative_failures.log" in text, (
        "CLAUDE.md must reference the fail-soft diagnostic log location"
    )
