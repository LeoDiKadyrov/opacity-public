"""Phase v2-interpretation-narrative Wave 0 — assert all 7 recorded Anthropic
fixtures parse and carry the minimum schema downstream waves rely on.

Per VALIDATION.md row v2-W0-fixtures (REQ-3,5).
"""
import json
from pathlib import Path

import pytest

FIXTURES_DIR = Path(__file__).parent / "anthropic_recorded"
EXPECTED_FIXTURES = [
    "ok_donk_peek",
    "hallucinated_tick",
    "hallucinated_demo",
    "no_direction_anchor",
    "refusal",
    "truncated_max_tokens",
    "clean_paraphrase",
]


@pytest.mark.parametrize("name", EXPECTED_FIXTURES)
def test_fixture_loads_and_has_required_keys(name):
    """Every fixture parses + has {text, usage, model, stop_reason, captured_at}."""
    path = FIXTURES_DIR / f"{name}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {"text", "usage", "model", "stop_reason", "captured_at"} <= set(data.keys())
    assert isinstance(data["text"], str) and len(data["text"]) > 0
    assert {"input_tokens", "output_tokens"} <= set(data["usage"].keys())


def test_all_seven_fixtures_present():
    """Sanity: directory contains exactly the expected 7 fixtures."""
    present = sorted(p.stem for p in FIXTURES_DIR.glob("*.json"))
    assert sorted(EXPECTED_FIXTURES) == present


def test_refusal_fixture_has_refusal_stop_reason():
    """REQ-10 fail-soft trigger relies on stop_reason='refusal' surfacing."""
    data = json.loads((FIXTURES_DIR / "refusal.json").read_text(encoding="utf-8"))
    assert data["stop_reason"] == "refusal"


def test_truncated_fixture_has_max_tokens_stop_reason():
    """R-6: validator must catch tick mid-sentence in max_tokens responses."""
    data = json.loads(
        (FIXTURES_DIR / "truncated_max_tokens.json").read_text(encoding="utf-8")
    )
    assert data["stop_reason"] == "max_tokens"
