"""Phase v2-interpretation-narrative Plan 02 — interpretation_narrative.py unit tests.

Test IDs map to v2-VALIDATION.md.

Per-task RED scopes:
- Task 1: TestContentHash + TestCacheIO (data layer + cache)
- Task 2: TestGetClient + TestCallLLM + TestFailureLogger (LLM client)
- Task 3: TestRenderPromptPlaceholder + TestBuildAllowedRefs + TestBuildNarrativeReport
"""
from __future__ import annotations

import sqlite3
from contextlib import closing

import pytest

from db_utils import init_db


_DONK_SID = 76561198386265483


# ── Task 1 — _content_hash + cache I/O ───────────────────────────────────────


class TestContentHash:
    """_content_hash determinism + sensitivity properties."""

    def test_content_hash_deterministic(self):
        from interpretation_narrative import _content_hash

        rows = [{"metric": "rt_visible_to_aim_ms", "tier": "Good", "player_value": 200.0}]
        moments = {"rt_visible_to_aim_ms::peek": [{"demo_name": "a.dem", "t0_tick": 100}]}
        h1 = _content_hash(rows, moments)
        h2 = _content_hash(rows, moments)
        assert h1 == h2

    def test_content_hash_changes_on_input_change(self):
        from interpretation_narrative import _content_hash

        rows = [{"metric": "rt_visible_to_aim_ms", "tier": "Good", "player_value": 200.0}]
        moments = {"rt_visible_to_aim_ms::peek": [{"demo_name": "a.dem", "t0_tick": 100}]}
        h1 = _content_hash(rows, moments)
        rows2 = [{"metric": "rt_visible_to_aim_ms", "tier": "Elite", "player_value": 150.0}]
        h2 = _content_hash(rows2, moments)
        assert h1 != h2

    def test_content_hash_excludes_directions_field(self):
        """RESEARCH note: directions excluded so cosmetic DIRECTIONS edits don't bust cache."""
        from interpretation_narrative import _content_hash

        rows1 = [{"metric": "rt_visible_to_aim_ms", "tier": "Good", "directions": ["d1"]}]
        rows2 = [{"metric": "rt_visible_to_aim_ms", "tier": "Good", "directions": ["d2_changed"]}]
        moments = {}
        assert _content_hash(rows1, moments) == _content_hash(rows2, moments)

    def test_content_hash_returns_short_hex(self):
        from interpretation_narrative import _content_hash

        h = _content_hash([], {})
        assert isinstance(h, str)
        assert len(h) == 16
        assert all(c in "0123456789abcdef" for c in h)


class TestCacheIO:
    """_cache_get / _cache_put roundtrip via narrative_cache table."""

    def test_cache_get_returns_none_when_missing(self, tmp_path):
        from interpretation_narrative import _cache_get

        db = str(tmp_path / "c.db")
        init_db(db)
        result = _cache_get(db, _DONK_SID, "peek", "deadbeef00000000")
        assert result is None

    def test_cache_put_then_get_roundtrip(self, tmp_path):
        from interpretation_narrative import _cache_get, _cache_put

        db = str(tmp_path / "c.db")
        init_db(db)
        usage = {
            "input_tokens": 4400, "output_tokens": 700,
            "cache_creation_input_tokens": 600, "cache_read_input_tokens": 0,
            "model": "claude-sonnet-4-6",
        }
        _cache_put(
            db, _DONK_SID, "peek", "abc123",
            "## sample narrative", "claude-sonnet-4-6", usage,
        )
        out = _cache_get(db, _DONK_SID, "peek", "abc123")
        assert out == "## sample narrative"

    def test_cache_put_overwrites_on_pk_collision(self, tmp_path):
        from interpretation_narrative import _cache_get, _cache_put

        db = str(tmp_path / "c.db")
        init_db(db)
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        _cache_put(db, _DONK_SID, "peek", "k1", "v1", "claude-sonnet-4-6", usage)
        _cache_put(db, _DONK_SID, "peek", "k1", "v2", "claude-sonnet-4-6", usage)

        with closing(sqlite3.connect(db)) as conn:
            cnt = conn.execute(
                "SELECT COUNT(*) FROM narrative_cache "
                "WHERE player_steamid=? AND engagement_type=? AND content_hash=?",
                (_DONK_SID, "peek", "k1"),
            ).fetchone()[0]
        assert cnt == 1
        assert _cache_get(db, _DONK_SID, "peek", "k1") == "v2"

    def test_cache_steamid64_no_truncation(self, tmp_path):
        """SteamID64 (17-digit) survives put → get without precision loss (R-8)."""
        from interpretation_narrative import _cache_get, _cache_put

        db = str(tmp_path / "c.db")
        init_db(db)
        usage = {"input_tokens": 1, "output_tokens": 1,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        _cache_put(db, _DONK_SID, "peek", "h_big", "narr", "m", usage)
        with closing(sqlite3.connect(db)) as conn:
            cursor = conn.execute(
                "SELECT player_steamid FROM narrative_cache WHERE content_hash=?",
                ("h_big",),
            )
            (raw_sid,) = cursor.fetchone()
        assert raw_sid == _DONK_SID
        assert _cache_get(db, _DONK_SID, "peek", "h_big") == "narr"

    def test_cache_get_treats_prompt_hash_mismatch_as_miss(self, tmp_path):
        """D-18: when prompt template changes, cached entries become invalid."""
        from interpretation_narrative import _cache_get, _cache_put

        db = str(tmp_path / "c.db")
        init_db(db)
        usage = {"input_tokens": 0, "output_tokens": 0,
                 "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
        _cache_put(
            db, _DONK_SID, "peek", "ck", "text", "m", usage, prompt_hash="phash_v1",
        )
        assert _cache_get(db, _DONK_SID, "peek", "ck", prompt_hash="phash_v1") == "text"
        assert _cache_get(db, _DONK_SID, "peek", "ck", prompt_hash="phash_v2") is None


# ── Task 2 — _get_client + call_llm + _failure_logger ────────────────────────


class TestGetClient:
    """_get_client — Path B: returns binary path string (no real client object).

    Path B (2026-05-12): replaced anthropic SDK singleton with `claude` CLI
    binary path. Singleton + API-key-env gate no longer apply. Test reduces
    to verifying the function returns the expected binary identifier.
    """

    def test_get_client_returns_claude_binary(self):
        from interpretation_narrative import _get_client
        assert _get_client() == "claude"


class TestCallLLM:
    """call_llm — Path B: subprocess `claude -p --output-format json`.

    Tests use `make_fake_claude_cli` factory which monkeypatches
    `subprocess.run` to return a CompletedProcess whose stdout is the
    JSON shape `claude -p` emits. Recorded SDK fixtures are translated
    via `_fixture_to_cli_payload` in conftest.
    """

    def test_call_llm_returns_text_and_usage(self, make_fake_claude_cli):
        import interpretation_narrative as inv
        make_fake_claude_cli("ok_donk_peek")

        text, usage = inv.call_llm("system block", "user block")
        assert text.startswith("## Что у тебя получается")
        assert usage["output_tokens"] == 700
        assert usage["model"] == "claude-sonnet-4-6"
        # Path B: subscription_mode flag distinguishes CLI usage from SDK
        assert usage["subscription_mode"] is True

    def test_call_llm_refusal_raises(self, make_fake_claude_cli):
        import interpretation_narrative as inv
        make_fake_claude_cli("refusal")
        with pytest.raises(inv.NarrativeBuildError, match="(?i)refusal"):
            inv.call_llm("s", "u")

    def test_call_llm_max_tokens_returns_text_without_raising(
        self, make_fake_claude_cli
    ):
        """max_tokens is a soft warning; downstream validator catches truncation."""
        import interpretation_narrative as inv
        make_fake_claude_cli("truncated_max_tokens")
        text, usage = inv.call_llm("s", "u")
        assert text  # non-empty
        assert usage["output_tokens"] >= 0

    def test_call_llm_api_error_raises(self, make_fake_claude_cli):
        """is_error: true / api_error_status set → NarrativeBuildError."""
        import interpretation_narrative as inv
        # Build a custom payload directly (no recorded fixture has is_error=True yet)
        import subprocess as sp
        import json as _j

        class _ErrProc:
            def __init__(self):
                err_payload = {
                    "type": "result", "subtype": "error",
                    "is_error": True, "api_error_status": 401,
                    "result": "", "stop_reason": "end_turn",
                    "usage": {}, "modelUsage": {},
                }
                self._pending = []
                self._closed = False
                self.stdin = self._Stdin(self, err_payload)
                self.stdout = self._Stdout(self)
                self.stderr = sp.PIPE  # unused

            class _Stdin:
                def __init__(self, parent, payload):
                    self._parent = parent
                    self._payload = payload
                    self.closed = False
                def write(self, data):
                    self._parent._pending.append(_j.dumps(self._payload) + "\n")
                    return len(data)
                def flush(self): pass
                def close(self): self.closed = True

            class _Stdout:
                def __init__(self, parent): self._parent = parent
                def readline(self):
                    if self._parent._pending:
                        return self._parent._pending.pop(0)
                    return ""

            def poll(self): return None
            def terminate(self): self._closed = True
            def kill(self): self._closed = True
            def wait(self, timeout=None): return 0

        import pytest as _pt

        def _popen(cmd, *args, **kwargs):
            return _ErrProc()

        # Patch Popen and reset singleton
        import subprocess as _sp_mod
        _orig_popen = _sp_mod.Popen
        _sp_mod.Popen = _popen
        try:
            inv._close_persistent_client()
            with _pt.raises(inv.NarrativeBuildError, match="(?i)api error|401"):
                inv.call_llm("s", "u")
        finally:
            _sp_mod.Popen = _orig_popen
            inv._close_persistent_client()

    def test_call_llm_persistent_session_shares_across_calls(self, make_fake_claude_cli):
        """Path B persistence: 2 consecutive call_llm with same system prompt
        spawn ONE subprocess (singleton), pipe 2 user messages."""
        import interpretation_narrative as inv

        # Two fixture payloads queued for two turns in same session
        make_fake_claude_cli("ok_donk_peek", "clean_paraphrase")
        text1, _ = inv.call_llm("static system", "user A")
        text2, _ = inv.call_llm("static system", "user B")
        assert text1
        assert text2
        # Both should have come from the SAME persistent process (singleton stayed alive)
        assert inv._PERSISTENT_CLIENT is not None
        assert inv._PERSISTENT_CLIENT["proc"].poll() is None

    def test_call_llm_system_prompt_change_respawns(self, make_fake_claude_cli):
        """Different system prompt hash → respawn (cache invalidation)."""
        import interpretation_narrative as inv

        make_fake_claude_cli("ok_donk_peek")
        inv.call_llm("system A", "user 1")
        first_proc = inv._PERSISTENT_CLIENT["proc"]

        make_fake_claude_cli("clean_paraphrase")  # reinstall factory + clear singleton
        inv.call_llm("system B (different)", "user 2")
        second_proc = inv._PERSISTENT_CLIENT["proc"]
        assert first_proc is not second_proc


class TestFailureLogger:
    """_failure_logger — file handler, no propagation."""

    def test_failure_logger_writes_to_file(self, tmp_path, monkeypatch):
        import interpretation_narrative as inv
        import logging

        # Reset cached logger so the new file handler lands in tmp cwd
        existing = logging.getLogger("narrative_failures")
        for h in list(existing.handlers):
            existing.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        monkeypatch.chdir(tmp_path)
        logger = inv._failure_logger()
        logger.warning("test entry from unit test")
        for h in logger.handlers:
            h.flush()

        log_path = tmp_path / "narrative_failures.log"
        assert log_path.exists()
        contents = log_path.read_text(encoding="utf-8")
        assert "test entry from unit test" in contents

    def test_failure_logger_no_propagation(self, tmp_path, monkeypatch, caplog):
        import interpretation_narrative as inv
        import logging

        existing = logging.getLogger("narrative_failures")
        for h in list(existing.handlers):
            existing.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        monkeypatch.chdir(tmp_path)
        logger = inv._failure_logger()
        with caplog.at_level(logging.WARNING, logger="narrative_failures"):
            logger.warning("isolated entry")
        # propagate=False — root logger should have no records from this logger
        root_records = [r for r in caplog.records if r.name == "root"]
        assert root_records == []


# ── Task 3 — _render_prompt + _build_allowed_refs + build_narrative_report ──


class TestRenderPrompt:
    """Plan v2-03 task 2 — _render_prompt now REQUIRES the prompt template to
    exist and contain the {{DYNAMIC_USER_BLOCK}} marker. W1's silent
    STATIC_PLACEHOLDER fallback is removed; both failure modes raise
    NarrativeBuildError so the orchestrator's fail-soft path catches them and
    falls back to tier-table-only behavior (REQ-10)."""

    def test_render_prompt_loads_real_template_when_file_exists(
        self, monkeypatch, tmp_path
    ):
        import interpretation_narrative as inv

        prompt_file = tmp_path / "real_prompt.md"
        prompt_file.write_text(
            "STUB_REAL_TEMPLATE_CONTENT\n{{DYNAMIC_USER_BLOCK}}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(inv, "_PROMPT_PATH", str(prompt_file))

        static, dynamic = inv._render_prompt(
            rows=[], top_moments={}, player_context={"player_steamid": _DONK_SID},
        )
        assert "STUB_REAL_TEMPLATE_CONTENT" in static
        # The W1 placeholder must NOT appear when a real template exists.
        assert "STATIC_PLACEHOLDER" not in static
        assert dynamic and dynamic.strip().startswith("{")

    def test_render_prompt_raises_when_template_missing(
        self, monkeypatch, tmp_path
    ):
        """W1 fall-back to STATIC_PLACEHOLDER is removed in W2 plan 03."""
        import interpretation_narrative as inv

        monkeypatch.setattr(inv, "_PROMPT_PATH", str(tmp_path / "no_such_file.md"))
        with pytest.raises(inv.NarrativeBuildError, match="(?i)prompt template"):
            inv._render_prompt(
                rows=[],
                top_moments={},
                player_context={"player_steamid": _DONK_SID},
            )

    def test_render_prompt_raises_when_marker_missing(
        self, monkeypatch, tmp_path
    ):
        import interpretation_narrative as inv

        prompt_file = tmp_path / "no_marker.md"
        prompt_file.write_text("Template without the marker.\n", encoding="utf-8")
        monkeypatch.setattr(inv, "_PROMPT_PATH", str(prompt_file))

        with pytest.raises(inv.NarrativeBuildError, match="DYNAMIC_USER_BLOCK"):
            inv._render_prompt(
                rows=[],
                top_moments={},
                player_context={"player_steamid": _DONK_SID},
            )

    def test_render_prompt_partitions_at_marker(self, monkeypatch, tmp_path):
        import interpretation_narrative as inv

        prompt_file = tmp_path / "p.md"
        prompt_file.write_text("BEFORE\n{{DYNAMIC_USER_BLOCK}}\nAFTER", encoding="utf-8")
        monkeypatch.setattr(inv, "_PROMPT_PATH", str(prompt_file))

        static, dynamic = inv._render_prompt(
            rows=[], top_moments={}, player_context={"player_steamid": _DONK_SID},
        )
        assert static == "BEFORE\n"
        assert "AFTER" not in dynamic


class TestBuildAllowedRefs:
    def test_build_allowed_refs_collects_demos_ticks_rounds_maps(self):
        from interpretation_narrative import _build_allowed_refs

        top_moments = {
            "rt_visible_to_aim_ms::peek": [
                {"demo_name": "a.dem", "t0_tick": 100, "round_number": 1, "map_name": "de_mirage"},
                {"demo_name": "b.dem", "t0_tick": 200, "round_number": 2, "map_name": "de_inferno"},
            ],
            "rt_aim_to_hit_ms::peek": [
                {"demo_name": "a.dem", "t0_tick": 300, "round_number": 1, "map_name": "de_mirage"},
            ],
        }
        refs = _build_allowed_refs(top_moments, "donk")
        assert refs["demos"] == {"a.dem", "b.dem"}
        assert refs["ticks"] == {100, 200, 300}
        assert refs["rounds"] == {1, 2}
        assert refs["maps"] == {"de_mirage", "de_inferno"}
        assert refs["nickname"] == "donk"

    def test_build_allowed_refs_excludes_null_round_number_and_map(self):
        from interpretation_narrative import _build_allowed_refs

        top_moments = {
            "x::peek": [
                {"demo_name": "a.dem", "t0_tick": 1, "round_number": None, "map_name": None},
                {"demo_name": "b.dem", "t0_tick": 2, "round_number": 5, "map_name": "de_dust2"},
            ]
        }
        refs = _build_allowed_refs(top_moments, "x")
        assert refs["rounds"] == {5}
        assert refs["maps"] == {"de_dust2"}


class TestBuildNarrativeReport:
    """build_narrative_report orchestrator — cache → render → call_llm → validate → cache_put."""

    def _player_ctx(self):
        return {
            "player_steamid": _DONK_SID,
            "engagement_type": "peek",
            "player_name": "donk",
        }

    def _top_moments_minimal(self):
        # Demos/ticks/rounds chosen to MATCH ok_donk_peek.json fixture content:
        # text mentions "spirit-vs-faze.dem", "раунд 14", "тик 12345"
        return {
            "rt_visible_to_aim_ms::peek": [
                {"demo_name": "spirit-vs-faze.dem", "t0_tick": 12345,
                 "map_name": "de_mirage", "round_number": 14,
                 "round_phase": "mid", "round_time_s": 30.0,
                 "player_value": 312.0, "benchmark_p50": 200.0,
                 "gap_vs_benchmark": 112.0},
            ],
        }

    def test_build_narrative_returns_text_on_clean_path(
        self, make_fake_claude_cli, mock_validator_pass, tmp_path
    ):
        import interpretation_narrative as inv

        db_path = str(tmp_path / "c.db")
        init_db(db_path)

        make_fake_claude_cli("ok_donk_peek")

        out = inv.build_narrative_report(
            rows=[{"metric": "rt_visible_to_aim_ms", "tier": "Average"}],
            top_moments=self._top_moments_minimal(),
            player_context=self._player_ctx(),
            db_path=db_path,
        )
        assert out.startswith("## Что у тебя получается")

    def test_build_narrative_caches_on_first_call(
        self, make_fake_claude_cli, mock_validator_pass, tmp_path
    ):
        """narrative_cache: second build_narrative_report on same content_hash
        must NOT consume a second fixture turn (only 1 LLM call total)."""
        import interpretation_narrative as inv

        db_path = str(tmp_path / "c.db")
        init_db(db_path)

        # Install ONLY 1 fixture turn. If build_narrative_report tries to call
        # call_llm twice, the second turn has no payload → would hang.
        make_fake_claude_cli("ok_donk_peek")

        rows = [{"metric": "rt_visible_to_aim_ms", "tier": "Average"}]
        moments = self._top_moments_minimal()
        ctx = self._player_ctx()

        text1 = inv.build_narrative_report(rows, moments, ctx, db_path=db_path)
        text2 = inv.build_narrative_report(rows, moments, ctx, db_path=db_path)
        assert text1 == text2
        # Confirm the underlying fake process only received ONE user message.
        proc = inv._PERSISTENT_CLIENT["proc"]
        user_msgs = [w for w in proc._writes if '"type": "user"' in w]
        assert len(user_msgs) == 1, f"expected 1 LLM call, got {len(user_msgs)}"

    def test_build_narrative_raises_on_validator_fail(
        self, make_fake_claude_cli, mock_validator_fail, tmp_path
    ):
        import interpretation_narrative as inv

        db_path = str(tmp_path / "c.db")
        init_db(db_path)

        # Use hallucinated_tick fixture — mocked validator rejects
        make_fake_claude_cli("hallucinated_tick")

        with pytest.raises(inv.NarrativeBuildError, match="(?i)validator|halluc"):
            inv.build_narrative_report(
                rows=[],
                top_moments=self._top_moments_minimal(),
                player_context=self._player_ctx(),
                db_path=db_path,
            )

    def test_build_narrative_raises_on_llm_error(
        self, monkeypatch, mock_validator_pass, tmp_path
    ):
        import interpretation_narrative as inv

        db_path = str(tmp_path / "c.db")
        init_db(db_path)

        def _boom(*a, **kw):
            raise inv.NarrativeBuildError("synthetic API outage")

        monkeypatch.setattr(inv, "call_llm", _boom)
        with pytest.raises(inv.NarrativeBuildError, match="synthetic"):
            inv.build_narrative_report(
                rows=[], top_moments=self._top_moments_minimal(),
                player_context=self._player_ctx(), db_path=db_path,
            )

    def test_build_narrative_logs_failure_to_log(
        self, monkeypatch, make_fake_claude_cli, mock_validator_fail, tmp_path
    ):
        """REQ-10 + D-07: validator fail writes NARRATIVE_FAIL line to narrative_failures.log."""
        import interpretation_narrative as inv
        import logging
        from pathlib import Path

        # Reset failure logger so the file handler lands in tmp_path
        existing = logging.getLogger("narrative_failures")
        for h in list(existing.handlers):
            existing.removeHandler(h)
            try:
                h.close()
            except Exception:
                pass

        # Resolve prompt template to ABSOLUTE path BEFORE chdir so plan v2-03's
        # _render_prompt loader can still find it after chdir(tmp_path). Without
        # this, _render_prompt raises NarrativeBuildError("Prompt template
        # missing") and we never reach the validator-fail code path under test.
        abs_prompt_path = str(Path(inv._PROMPT_PATH).resolve())
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(inv, "_PROMPT_PATH", abs_prompt_path)

        db_path = str(tmp_path / "c.db")
        init_db(db_path)
        make_fake_claude_cli("hallucinated_tick")

        with pytest.raises(inv.NarrativeBuildError):
            inv.build_narrative_report(
                rows=[], top_moments=self._top_moments_minimal(),
                player_context=self._player_ctx(), db_path=db_path,
            )

        for h in logging.getLogger("narrative_failures").handlers:
            h.flush()

        log_path = tmp_path / "narrative_failures.log"
        assert log_path.exists()
        contents = log_path.read_text(encoding="utf-8")
        assert "NARRATIVE_FAIL" in contents
        assert "kind=validator" in contents

    def test_build_narrative_falls_back_to_player_short_id_when_nickname_unknown(
        self, monkeypatch, make_fake_claude_cli, mock_validator_pass, tmp_path
    ):
        """player_name=None AND not in PLAYER_NAMES → nickname becomes player_<last4>."""
        import interpretation_narrative as inv

        db_path = str(tmp_path / "c.db")
        init_db(db_path)
        make_fake_claude_cli("ok_donk_peek")

        captured = {}
        original = inv._build_allowed_refs

        def _spy(top_moments, player_name):
            captured["nickname"] = player_name
            return original(top_moments, player_name)

        monkeypatch.setattr(inv, "_build_allowed_refs", _spy)

        unknown_sid = 76561198000001234  # not in PLAYER_NAMES
        ctx = {
            "player_steamid": unknown_sid,
            "engagement_type": "peek",
            "player_name": None,
        }
        inv.build_narrative_report(
            rows=[], top_moments=self._top_moments_minimal(),
            player_context=ctx, db_path=db_path,
        )
        assert captured["nickname"] == f"player_{str(unknown_sid)[-4:]}"
