"""Phase v2-interpretation-narrative Wave 0 guard — verify autouse fixture
blocks real Anthropic client calls. Defends against accidental live-API leaks
in CI / dev (T-LLM-01 from VALIDATION.md).
"""
import pytest


def test_real_anthropic_client_raises():
    """v2-W0-conftest-no-real-api — direct Anthropic() call must boom."""
    import anthropic
    with pytest.raises(RuntimeError, match="Real Anthropic client requested"):
        anthropic.Anthropic(api_key="fake-key-not-used")


def test_fixture_does_not_break_other_tests():
    """Sanity: importing other modules works under the autouse fixture."""
    import db_utils
    assert hasattr(db_utils, "save_to_db")
    assert hasattr(db_utils, "init_db")
