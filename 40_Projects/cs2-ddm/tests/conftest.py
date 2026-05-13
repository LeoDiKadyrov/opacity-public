"""
Shared fixtures and configuration for the DDM test suite.

Phase 9.1 (Wave 0) extension: ``fake_parser`` fixture exposes a mock that
supports BOTH the legacy singular ``parse_event(name)`` shape used by the
existing 322 tests AND the batched ``parse_events(list[name])`` shape that
production code migrates to in plan 09.1-02 (Pitfall #3 mitigation).

Usage in tests:

    def test_something(fake_parser):
        # legacy singular (returns DataFrame directly):
        fake_parser.parse_event.return_value = pd.DataFrame(...)

        # new batched (returns list[(name, DataFrame)]):
        fake_parser.parse_events.return_value = [
            ("player_hurt",  hurt_df),
            ("player_death", death_df),
            ("weapon_fire",  fire_df),
            ("round_start",  rs_df),
        ]

        # or override with a spy callable:
        fake_parser.parse_events = lambda events: [(n, pd.DataFrame()) for n in events]

Production code uses ``parse_events([list])`` per RESEARCH.md §Pattern 2 — the
return shape is a list-of-tuples, NOT a dict, and order is non-deterministic
(Pitfall #2). Tests should mirror the list-of-tuples shape and let the code
under test build its own ``dict(by_name)``.
"""

from unittest.mock import MagicMock

import pandas as pd
import pytest


@pytest.fixture
def fake_parser():
    """A demoparser2.DemoParser stand-in supporting both event-API shapes.

    The default ``parse_events`` behavior returns ``[(name, empty_df)]`` for
    every requested event name so that tests not focused on event content
    don't have to hand-stub the full 4-event tuple list. Tests that DO care
    about event content override via ``return_value`` or by reassigning the
    attribute to a spy callable.
    """
    parser = MagicMock(name="fake_parser")

    # Legacy singular API — kept for backward compat with existing 322 tests.
    parser.parse_event.return_value = pd.DataFrame()

    # Batched API (demoparser2 0.41.2). Default = empty DataFrame per event,
    # preserving the list-of-tuples shape from RESEARCH.md §Pattern 2.
    def _default_parse_events(event_names, *args, **kwargs):
        return [(name, pd.DataFrame()) for name in event_names]

    parser.parse_events.side_effect = _default_parse_events

    # Common ancillary calls used by ddm_analyzer / t0_detector.
    parser.parse_ticks.return_value = pd.DataFrame()
    parser.parse_header.return_value = {"map_name": "de_test"}

    return parser


# ─────────────────────────────────────────────────────────────────────────────
# Phase v2-interpretation-narrative Wave 0 — block real Anthropic API calls.
# Per RESEARCH §Testing Strategy lines 624-634. Every test runs under this
# fixture; tests that need a fake LLM client install their own monkeypatch
# override (later monkeypatch wins per pytest semantics).
# ─────────────────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _no_real_anthropic(monkeypatch):
    """Block real Anthropic client + claude CLI subprocess in tests (autouse, fail-loud).

    Path B (2026-05-12): primary block target shifted from `anthropic.Anthropic`
    to `subprocess.run` of the `claude` binary. Anthropic SDK block kept for
    legacy code paths that still try the SDK directly.
    """
    # Legacy: block direct Anthropic SDK instantiation (in case any old code path remains).
    try:
        import anthropic  # noqa: F401

        def _boom(*args, **kwargs):
            raise RuntimeError(
                "Real Anthropic client requested in test — add monkeypatch."
            )
        monkeypatch.setattr("anthropic.Anthropic", _boom)
    except ImportError:
        pass

    # Path B: block real `claude -p` subprocess (both .run and .Popen variants).
    # Persistent stream-json mode uses Popen; one-shot mode used run. Tests
    # that need a fake install their own monkeypatch via `make_fake_claude_cli`.
    import subprocess as _sp
    _orig_run = _sp.run
    _orig_popen = _sp.Popen

    def _is_claude_cli(cmd):
        return (
            isinstance(cmd, (list, tuple))
            and len(cmd) > 0
            and isinstance(cmd[0], str)
            and cmd[0].endswith("claude")
        )

    def _guard_run(cmd, *args, **kwargs):
        if _is_claude_cli(cmd):
            raise RuntimeError(
                "Real `claude -p` subprocess (run) requested in test — add "
                "monkeypatch or use make_fake_claude_cli fixture."
            )
        return _orig_run(cmd, *args, **kwargs)

    def _guard_popen(cmd, *args, **kwargs):
        if _is_claude_cli(cmd):
            raise RuntimeError(
                "Real `claude -p` subprocess (Popen) requested in test — add "
                "monkeypatch or use make_fake_claude_cli fixture."
            )
        return _orig_popen(cmd, *args, **kwargs)

    monkeypatch.setattr(_sp, "run", _guard_run)
    monkeypatch.setattr(_sp, "Popen", _guard_popen)

    # Also reset persistent client singleton so cross-test state doesn't leak.
    try:
        import interpretation_narrative as _inv_mod
        _inv_mod._close_persistent_client()
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────────────────────
# Phase v2-interpretation-narrative Plan 02 Task 2 — FakeAnthropic + factory
# fixture for tests that need a stand-in Anthropic client. Tests opt-in by
# requesting ``make_fake_anthropic``; the autouse ``_no_real_anthropic`` block
# above stays active otherwise.
# Pattern per RESEARCH §Testing Strategy lines 522-635 + PATTERNS.md.
#
# Path B (2026-05-12): added FakeClaudeCli + make_fake_claude_cli factory so
# tests using the `claude -p` subprocess path can monkeypatch subprocess.run
# from a recorded fixture. The legacy FakeAnthropic + make_fake_anthropic
# fixtures remain for back-compat with already-written tests but are unused
# by the new call_llm path.
# ─────────────────────────────────────────────────────────────────────────────


import json as _json  # noqa: E402
import subprocess as _subprocess_mod  # noqa: E402
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402


class _FakeMessage:
    def __init__(self, text, usage, stop_reason="end_turn", model="claude-sonnet-4-6"):
        self.content = [SimpleNamespace(text=text, type="text")]
        self.usage = SimpleNamespace(**usage)
        self.stop_reason = stop_reason
        self.stop_details = None
        self.model = model


class _FakeMessages:
    def __init__(self, response):
        self._response = response

    def create(self, **kwargs):
        return self._response


class FakeAnthropic:
    def __init__(self, response):
        self.messages = _FakeMessages(response)


def load_recorded_fixture(name: str) -> dict:
    """Load tests/fixtures/anthropic_recorded/<name>.json."""
    p = Path(__file__).parent / "fixtures" / "anthropic_recorded" / f"{name}.json"
    return _json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture
def make_fake_anthropic():
    """Factory — returns FakeAnthropic configured from a recorded fixture by name.

    Legacy fixture for SDK-era tests. Path B replacement is `make_fake_claude_cli`.
    """
    def _make(fixture_name: str) -> FakeAnthropic:
        data = load_recorded_fixture(fixture_name)
        return FakeAnthropic(_FakeMessage(
            text=data["text"],
            usage=data["usage"],
            stop_reason=data["stop_reason"],
            model=data["model"],
        ))
    return _make


def _fixture_to_cli_payload(data: dict) -> dict:
    """Translate recorded `tests/fixtures/anthropic_recorded/*.json` (SDK shape)
    to the `claude -p --output-format json` CLI shape so existing fixtures
    drive the Path-B mock without rewriting fixture files.
    """
    is_refusal = data.get("stop_reason") == "refusal"
    usage = data.get("usage") or {}
    model = data.get("model") or "claude-sonnet-4-6"
    return {
        "type": "result",
        "subtype": "success" if not is_refusal else "refusal",
        "is_error": False,
        "api_error_status": None,
        "duration_ms": 100,
        "duration_api_ms": 50,
        "result": data.get("text", ""),
        "stop_reason": data.get("stop_reason", "end_turn"),
        "stop_details": data.get("stop_details"),
        "session_id": "test-fixture",
        "total_cost_usd": 0.0,
        "usage": {
            "input_tokens": usage.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens", 0),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens", 0),
        },
        "modelUsage": {model: {}},
    }


class _FakeClaudeProcess:
    """Stub Popen-like for persistent stream-json mode (Path B).

    Records writes; reads emit the configured JSON event sequence per turn.
    Tests that need to inject a specific recorded fixture per turn use
    `make_fake_claude_cli` to install a Popen factory.
    """
    def __init__(self, turn_payloads: list[dict]):
        self._turn_payloads = list(turn_payloads)
        self._pending_lines: list[str] = []
        self._writes: list[str] = []
        self._closed = False
        # File-like stdin/stdout proxies.
        self.stdin = self._StdinProxy(self)
        self.stdout = self._StdoutProxy(self)
        self.stderr = self._StderrProxy()

    class _StdinProxy:
        def __init__(self, parent): self._parent = parent
        @property
        def closed(self): return self._parent._closed
        def write(self, data):
            self._parent._writes.append(data)
            # On each user message, queue next turn's events for readout.
            try:
                _parsed = _json.loads(data.rstrip("\n"))
            except Exception:
                _parsed = None
            if _parsed and _parsed.get("type") == "user" and self._parent._turn_payloads:
                payload = self._parent._turn_payloads.pop(0)
                # Emit a synthetic assistant + result event pair.
                assistant_evt = {
                    "type": "assistant",
                    "message": {
                        "model": payload.get("modelUsage", {"claude-sonnet-4-6": {}}),
                        "content": [{"type": "text", "text": payload.get("result", "")}],
                    },
                }
                self._parent._pending_lines.append(_json.dumps(assistant_evt) + "\n")
                self._parent._pending_lines.append(_json.dumps(payload) + "\n")
            return len(data)
        def flush(self): pass
        def close(self): self._parent._closed = True

    class _StdoutProxy:
        def __init__(self, parent): self._parent = parent
        def readline(self):
            if self._parent._pending_lines:
                return self._parent._pending_lines.pop(0)
            # EOF when no more pending lines and process closed
            return "" if self._parent._closed else "\n"

    class _StderrProxy:
        def read(self): return ""

    def poll(self): return None if not self._closed else 0
    def terminate(self): self._closed = True
    def kill(self): self._closed = True
    def wait(self, timeout=None): self._closed = True; return 0


@pytest.fixture
def make_fake_claude_cli(monkeypatch):
    """Factory — monkeypatches subprocess.Popen so persistent stream-json mode
    sees a stub process that emits recorded fixture payloads per turn.

    Usage:
        def test_x(make_fake_claude_cli):
            make_fake_claude_cli("ok_donk_peek")
            text, usage = call_llm("sys", "user")
    """
    installed = {"proc": None, "payloads": []}

    def _install(*fixture_names, returncode: int = 0, stderr: str = ""):
        if not fixture_names:
            raise ValueError("make_fake_claude_cli requires ≥1 fixture name")
        payloads = []
        for fixture_name in fixture_names:
            data = load_recorded_fixture(fixture_name)
            payloads.append(_fixture_to_cli_payload(data))
        installed["payloads"].extend(payloads)

        def _popen_factory(cmd, *args, **kwargs):
            proc = _FakeClaudeProcess(installed["payloads"])
            installed["proc"] = proc
            return proc

        monkeypatch.setattr("subprocess.Popen", _popen_factory)
        # Reset singleton so next call_llm spawns the fake.
        try:
            import interpretation_narrative as _inv_mod
            _inv_mod._close_persistent_client()
        except Exception:
            pass
        return payloads[0] if len(payloads) == 1 else payloads

    return _install


# ─────────────────────────────────────────────────────────────────────────────
# Phase v2 Plan 02 Task 3 — narrative_validator mock fixtures.
# Plan 01 ships the real validator in a parallel wave. Tests for plan 02's
# orchestrator use these to inject pass/fail behavior without depending on
# plan 01's commit landing first.
# ─────────────────────────────────────────────────────────────────────────────

import sys as _sys  # noqa: E402
import types as _types  # noqa: E402


def _install_validator_stub(monkeypatch, validate_impl):
    """Insert a stub `narrative_validator` module into sys.modules so that
    `from narrative_validator import validate_narrative` resolves without
    requiring plan 01's real module to exist.
    """
    mod = _types.ModuleType("narrative_validator")
    mod.validate_narrative = validate_impl  # type: ignore[attr-defined]
    monkeypatch.setitem(_sys.modules, "narrative_validator", mod)
    return mod


@pytest.fixture
def mock_validator_pass(monkeypatch):
    """validate_narrative always returns (True, [])."""
    def _ok(text, allowed_refs):
        return (True, [])
    return _install_validator_stub(monkeypatch, _ok)


@pytest.fixture
def mock_validator_fail(monkeypatch):
    """validate_narrative always returns (False, [violation])."""
    def _fail(text, allowed_refs):
        return (False, [{"type": "tick", "value": 99999999, "context_snippet": "тике 99999999"}])
    return _install_validator_stub(monkeypatch, _fail)
