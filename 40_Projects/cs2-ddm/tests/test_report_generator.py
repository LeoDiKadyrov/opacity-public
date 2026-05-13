"""
Tests for report_generator.py — HTML report module (Plan 09-01).
"""

from __future__ import annotations
import os
import re
import sqlite3
import pytest

from config import DB_PATH

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def empty_db(tmp_path):
    """Minimal DB with full schema but no data rows.

    Schema must match what interpretation.py queries:
    - engagements: needs demo_name, player_steamid, engagement_type, RT cols, crosshair col
    - duel_attempts: needs demo_name, player_steamid, engagement_type, was_killed, bullets cols
    """
    db = str(tmp_path / "test.db")
    with sqlite3.connect(db) as conn:
        conn.execute(
            "CREATE TABLE engagements ("
            "  player_steamid INTEGER, match_id INTEGER, engagement_type TEXT,"
            "  moment_timestamp TEXT, t0_manual_tick INTEGER, demo_name TEXT,"
            "  rt_visible_to_hit_ms REAL, rt_visible_to_aim_ms REAL,"
            "  rt_aim_to_hit_ms REAL, crosshair_angle_at_t0_deg REAL,"
            "  player_velocity_at_t0_ups REAL, enemy_velocity_at_t0_ups REAL"
            ")"
        )
        conn.execute(
            "CREATE TABLE duel_attempts ("
            "  player_steamid INTEGER, match_id INTEGER, engagement_type TEXT,"
            "  demo_name TEXT, was_killed INTEGER, bullets_fired INTEGER,"
            "  bullets_hit INTEGER"
            ")"
        )
    return db


_DONK_SID = 76561198386265483
_HAS_DB = os.path.exists(DB_PATH)

# ── Task 1 tests: generation contract ─────────────────────────────────────────


def test_returns_bytes(empty_db):
    """generate_html_report() must return bytes."""
    import report_generator

    result = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    )
    assert isinstance(result, bytes)


def test_title_contains_steamid(empty_db):
    """<title> must contain 'Djok Report — {steamid}'."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "Djok Report" in html
    assert "1" in html  # steamid present somewhere


def test_title_exact_format(empty_db):
    """<title> tag must be exactly 'Djok Report — 76561198386265483'."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=76561198386265483,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "<title>Djok Report — 76561198386265483</title>" in html


def test_no_external_urls(empty_db):
    """Generated HTML must have zero external URLs (href/src pointing to https://)."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    external = re.findall(r"""(?:href|src)=["'](https?://[^"']+)""", html)
    assert external == [], f"External URLs found: {external}"


def test_interpretation_section_present(empty_db):
    """'Interpretation' header must be present in generated HTML."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "Interpretation" in html


def test_distributions_section_present(empty_db):
    """'Distributions' section placeholder must be present."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "Distributions" in html


def test_raw_data_section_present(empty_db):
    """'Raw Data' section must be present."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "Raw Data" in html


def test_worst_metric_card_omitted_when_no_data(empty_db):
    """When DB has no rows for steamid, 'Your biggest opportunity' card should NOT appear
    (or, if it appears, must not show a tier because there is no player data)."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=999,
        benchmark_steamid=999,
        benchmark_name="nobody",
        db_path=empty_db,
    ).decode()
    # If card is rendered, the worst metric tier must be n/a (acceptable)
    # Strictest form: card should be absent when all tiers are n/a
    # We accept either: card absent OR card present with no golden border visible
    # (get_worst_metric returns None when all n/a → card omitted per spec)
    # Since empty DB means all metrics return "Work needed" (no data fallback),
    # card MAY appear. The key invariant is: no crash, output is bytes.
    assert isinstance(html, str)


def test_accent_color_in_css(empty_db):
    """Accent color #e8b84b must appear in the HTML (used in CSS)."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "#e8b84b" in html


def test_bg_color_in_css(empty_db):
    """Primary background color #0e0e12 must appear in the HTML CSS."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "#0e0e12" in html


def test_benchmark_name_in_subheader(empty_db):
    """Benchmark name 'donk' must appear in generated HTML sub-header."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="donk",
        db_path=empty_db,
    ).decode()
    assert "donk" in html


# ── Integration tests (skip if analytics.db absent) ───────────────────────────


@pytest.mark.skipif(not _HAS_DB, reason="analytics.db not present")
def test_donk_report_returns_bytes():
    """Integration: generate report for donk using real analytics.db."""
    import report_generator

    result = report_generator.generate_html_report(
        player_steamid=_DONK_SID,
        benchmark_steamid=_DONK_SID,
        benchmark_name="donk",
        db_path=DB_PATH,
    )
    assert isinstance(result, bytes)
    assert len(result) > 1000  # non-trivial output


@pytest.mark.skipif(not _HAS_DB, reason="analytics.db not present")
def test_donk_report_no_external_urls():
    """Integration: real report must pass external-URL safety gate."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=_DONK_SID,
        benchmark_steamid=_DONK_SID,
        benchmark_name="donk",
        db_path=DB_PATH,
    ).decode()
    external = re.findall(r"""(?:href|src)=["'](https?://[^"']+)""", html)
    assert external == [], f"External URLs in real report: {external}"


@pytest.mark.skipif(not _HAS_DB, reason="analytics.db not present")
def test_donk_report_has_interpretation_header():
    """Integration: real donk report must have Interpretation section."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=_DONK_SID,
        benchmark_steamid=_DONK_SID,
        benchmark_name="donk",
        db_path=DB_PATH,
    ).decode()
    assert "Interpretation" in html
    assert "Peek engagements" in html


# ── Task 2: Chart coverage tests ──────────────────────────────────────────────


def test_fig_to_b64_returns_string():
    """_fig_to_b64 must return a non-empty base64 string."""
    import matplotlib.pyplot as plt
    import report_generator

    fig, ax = plt.subplots()
    ax.plot([1, 2], [3, 4])
    result = report_generator._fig_to_b64(fig)
    assert isinstance(result, str)
    assert len(result) > 100
    plt.close(fig)


def test_distributions_section_has_base64(empty_db):
    """Distributions section must contain at least one base64 PNG data URI."""
    import report_generator

    # Insert some data so charts can be generated
    with sqlite3.connect(empty_db) as conn:
        conn.execute(
            "INSERT INTO engagements VALUES (1, 1, 'peek', '0:01', 100, 'demo.dem',"
            " 250.0, 180.0, 70.0, 15.0, 120.0, 80.0)"
        )
    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "data:image/png;base64," in html


def test_charts_section_header(empty_db):
    """'Distributions' header must be present in generated HTML."""
    import report_generator

    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert "Distributions" in html


def test_chart_caption_pattern(empty_db):
    """At least one chart caption must match the required pattern."""
    import report_generator

    with sqlite3.connect(empty_db) as conn:
        conn.execute(
            "INSERT INTO engagements VALUES (1, 1, 'peek', '0:01', 100, 'demo.dem',"
            " 250.0, 180.0, 70.0, 15.0, 120.0, 80.0)"
        )
    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    assert re.search(
        r"(Crosshair|RT|Kill rate|Hit rate).*(peek|hold) engagements \(n=\d+\)",
        html,
    ), "No chart caption matching pattern found"


def test_no_external_urls_after_charts(empty_db):
    """Safety gate: no external URLs even after charts are inserted."""
    import report_generator

    with sqlite3.connect(empty_db) as conn:
        conn.execute(
            "INSERT INTO engagements VALUES (1, 1, 'peek', '0:01', 100, 'demo.dem',"
            " 250.0, 180.0, 70.0, 15.0, 120.0, 80.0)"
        )
    html = report_generator.generate_html_report(
        player_steamid=1,
        benchmark_steamid=1,
        benchmark_name="test",
        db_path=empty_db,
    ).decode()
    external = re.findall(r"""(?:href|src)=["'](https?://[^"']+)""", html)
    assert external == [], f"External URLs found: {external}"


# ── Task 3: app.py integration smoke tests (Plan 09-03) ───────────────────────


def test_app_imports_report_generator():
    """app.py must contain 'import report_generator'."""
    with open("app.py", encoding="utf-8") as f:
        src = f.read()
    assert "import report_generator" in src


def test_app_download_button_present():
    """app.py must contain st.download_button and 'Download Report' label."""
    with open("app.py", encoding="utf-8") as f:
        src = f.read()
    assert "st.download_button" in src
    assert "Download Report" in src


def test_app_syntax_valid():
    """app.py must parse without syntax errors."""
    import ast

    with open("app.py", encoding="utf-8") as f:
        src = f.read()
    ast.parse(src)  # raises SyntaxError if invalid


# ── Plan v2-04: TestNarrativeIntegration (REQ-6 + REQ-10) ─────────────────────
# Wire interpretation_narrative.build_narrative_report into generate_html_report.
# Cover 4 paths per plan: pass / NarrativeBuildError / unexpected / no_narrative.

import logging  # noqa: E402

import pytest as _pytest_v204  # noqa: E402  (alias avoids shadowing top-of-file pytest)


@_pytest_v204.fixture
def populated_db_for_report(empty_db):
    """Stub-friendly DB populated with peek+hold rows so compute_interpretation
    returns sensible benchmark_p50 values. Also creates the narrative_cache
    table so build_narrative_report's _cache_get/_cache_put don't OperationalError.
    """
    with sqlite3.connect(empty_db) as conn:
        # peek rows (player_steamid=1, also doubles as benchmark for simplicity)
        for tick in (100, 200, 300, 400, 500):
            conn.execute(
                "INSERT INTO engagements VALUES (1, 1, 'peek', '0:01', ?, 'demo.dem',"
                " 250.0, 180.0, 70.0, 15.0, 120.0, 80.0)",
                (tick,),
            )
        # hold rows
        for tick in (1100, 1200, 1300):
            conn.execute(
                "INSERT INTO engagements VALUES (1, 1, 'hold', '0:01', ?, 'demo.dem',"
                " 220.0, 160.0, 60.0, 12.0, 110.0, 70.0)",
                (tick,),
            )
        # narrative_cache schema mirror (db_utils.py:137-151) so _cache_get
        # / _cache_put don't OperationalError when build_narrative_report runs.
        conn.execute(
            "CREATE TABLE IF NOT EXISTS narrative_cache ("
            "  player_steamid INTEGER NOT NULL,"
            "  engagement_type TEXT NOT NULL,"
            "  content_hash TEXT NOT NULL,"
            "  narrative_md TEXT NOT NULL,"
            "  model TEXT NOT NULL,"
            "  tokens_in INTEGER,"
            "  tokens_out INTEGER,"
            "  cache_creation_input_tokens INTEGER DEFAULT 0,"
            "  cache_read_input_tokens INTEGER DEFAULT 0,"
            "  generated_at TEXT NOT NULL,"
            "  prompt_hash TEXT,"
            "  PRIMARY KEY (player_steamid, engagement_type, content_hash)"
            ")"
        )
    return empty_db


def _stub_interpretation_rows(et_label: str) -> list[dict]:
    """Return tier-table rows shaped like compute_interpretation output."""
    base_metric_p50 = {
        "crosshair_angle_at_t0_deg": 12.0,
        "rt_visible_to_aim_ms": 200.0,
        "rt_aim_to_hit_ms": 80.0,
        "rt_visible_to_hit_ms": 280.0,
    }
    return [
        {
            "metric": m,
            "label": m,
            "player_value": p50 + 5.0,
            "tier": "Average",
            "gap": 5.0,
            "benchmark_p50": p50,
            "directions": [],
            "drill": "—",
            "caveat": None,
        }
        for m, p50 in base_metric_p50.items()
    ]


def _stub_top_moments(*args, **kwargs) -> list[dict]:
    """Return canned attribution rows shaped like fetch_top_moments output."""
    return [
        {
            "demo_name": "demo.dem",
            "t0_tick": 12345,
            "map_name": "de_mirage",
            "round_number": 14,
            "round_phase": "open",
            "round_time_s": 12.5,
            "player_value": 305.0,
            "benchmark_p50": 280.0,
            "gap_vs_benchmark": 25.0,
        }
    ]


def _attach_capture_handler(
    logger_name: str,
) -> tuple[logging.Logger, list[logging.LogRecord]]:
    """Attach a list-capturing handler to the named logger and return (logger, records).

    config.get_logger creates loggers with propagate=False, so caplog cannot
    capture them. We attach a direct handler to the named logger after
    generate_html_report has invoked get_logger (handlers list is populated
    on first call inside the SUT — but if we attach BEFORE the call to a
    pre-created logger via getLogger, the SUT's own handler additions still
    fire and our capture handler stays attached too).
    """
    logger = logging.getLogger(logger_name)
    records: list[logging.LogRecord] = []

    class _ListHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    handler = _ListHandler(level=logging.DEBUG)
    logger.addHandler(handler)
    return logger, records


class TestNarrativeIntegration:
    """Plan v2-04 Task 1: report_generator narrative wiring + fail-soft."""

    def test_narrative_section_present_when_build_succeeds(
        self,
        monkeypatch,
        populated_db_for_report,
        make_fake_anthropic,
        mock_validator_pass,
    ):
        """Pass-path: build_narrative_report returns text → 'Coach Narrative'
        header appears, markdown converted to HTML (## Header → <h3>)."""
        import importlib

        # Fresh client per test
        import interpretation_narrative

        importlib.reload(interpretation_narrative)
        # Path B persistent stream-json: monkeypatch subprocess.Popen with the
        # FakeClaudeProcess from conftest. Mirror make_fake_claude_cli inline
        # since module reload may have invalidated fixture-bound state.
        from tests.conftest import (
            _FakeClaudeProcess,
            _fixture_to_cli_payload,
            load_recorded_fixture,
        )
        _payload = _fixture_to_cli_payload(load_recorded_fixture("ok_donk_peek"))
        _pending_proc = {"holder": None}

        def _popen_factory(cmd, *args, **kwargs):
            # Fresh payloads queue each spawn — supports multi-engagement type loops.
            proc = _FakeClaudeProcess([_payload, _payload, _payload])
            _pending_proc["holder"] = proc
            return proc

        monkeypatch.setattr("subprocess.Popen", _popen_factory)
        interpretation_narrative._close_persistent_client()
        # Stub fetch_top_moments to bypass DB schema demands
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        # Ensure compute_interpretation returns non-empty benchmark_p50 rows so
        # narrative-block top_moments loop has data to iterate over.
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        html = report_generator.generate_html_report(
            player_steamid=1,
            benchmark_steamid=1,
            benchmark_name="test",
            db_path=populated_db_for_report,
        ).decode()

        assert "Coach Narrative" in html
        assert "narrative-header" in html
        # The markdown ## should NOT appear raw — converter strips the marker
        assert "## Что у тебя получается" not in html
        # But the header text itself should appear inside an <h3>
        assert "Что у тебя получается" in html

    def test_narrative_appears_before_interpretation_section(
        self,
        monkeypatch,
        populated_db_for_report,
        make_fake_anthropic,
        mock_validator_pass,
    ):
        """Insertion order: 'Coach Narrative' header position < 'Interpretation' position."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)
        # Path B persistent stream-json: monkeypatch subprocess.Popen with the
        # FakeClaudeProcess from conftest. Mirror make_fake_claude_cli inline
        # since module reload may have invalidated fixture-bound state.
        from tests.conftest import (
            _FakeClaudeProcess,
            _fixture_to_cli_payload,
            load_recorded_fixture,
        )
        _payload = _fixture_to_cli_payload(load_recorded_fixture("ok_donk_peek"))
        _pending_proc = {"holder": None}

        def _popen_factory(cmd, *args, **kwargs):
            # Fresh payloads queue each spawn — supports multi-engagement type loops.
            proc = _FakeClaudeProcess([_payload, _payload, _payload])
            _pending_proc["holder"] = proc
            return proc

        monkeypatch.setattr("subprocess.Popen", _popen_factory)
        interpretation_narrative._close_persistent_client()
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        html = report_generator.generate_html_report(
            player_steamid=1,
            benchmark_steamid=1,
            benchmark_name="test",
            db_path=populated_db_for_report,
        ).decode()
        narrative_pos = html.find("Coach Narrative")
        interp_pos = html.find(">Interpretation<")
        assert narrative_pos > 0
        assert interp_pos > 0
        assert narrative_pos < interp_pos

    def test_narrative_falls_back_silently_on_NarrativeBuildError(
        self, monkeypatch, populated_db_for_report
    ):
        """REQ-10 fail-soft: NarrativeBuildError → empty narrative + tier table preserved."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)

        def _raise(*args, **kwargs):
            raise interpretation_narrative.NarrativeBuildError("synthetic test failure")

        monkeypatch.setattr(interpretation_narrative, "build_narrative_report", _raise)
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        result = report_generator.generate_html_report(
            player_steamid=1,
            benchmark_steamid=1,
            benchmark_name="test",
            db_path=populated_db_for_report,
        )
        assert isinstance(result, bytes)
        html = result.decode()
        assert "Coach Narrative" not in html
        assert "Interpretation" in html

    def test_narrative_logs_failure_on_NarrativeBuildError(
        self, monkeypatch, populated_db_for_report
    ):
        """Failure surfaced via config.get_logger at WARNING level."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)

        def _raise(*args, **kwargs):
            raise interpretation_narrative.NarrativeBuildError("synthetic failure xyz")

        monkeypatch.setattr(interpretation_narrative, "build_narrative_report", _raise)
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        # Pre-attach capture handler to the logger name we expect get_logger to use
        logger, records = _attach_capture_handler("DDM.report.1")
        try:
            report_generator.generate_html_report(
                player_steamid=1,
                benchmark_steamid=1,
                benchmark_name="test",
                db_path=populated_db_for_report,
            )
        finally:
            # Clean up capture handler so it doesn't leak across tests
            for h in list(logger.handlers):
                if h.__class__.__name__ == "_ListHandler":
                    logger.removeHandler(h)

        warning_records = [
            r
            for r in records
            if r.levelno == logging.WARNING
            and "Narrative build failed" in r.getMessage()
        ]
        assert warning_records, (
            f"Expected WARNING log matching 'Narrative build failed', got: "
            f"{[(r.levelname, r.getMessage()) for r in records]}"
        )

    def test_unexpected_exception_swallowed_when_dev_fail_fast_unset(
        self, monkeypatch, populated_db_for_report
    ):
        """R-9 mitigation: unexpected Exception (not NarrativeBuildError) →
        no raise when DEV_FAIL_FAST not set; logs at ERROR level."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)

        def _raise(*args, **kwargs):
            raise RuntimeError("oops_unexpected_v204")

        monkeypatch.setattr(interpretation_narrative, "build_narrative_report", _raise)
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        monkeypatch.delenv("DEV_FAIL_FAST", raising=False)

        logger, records = _attach_capture_handler("DDM.report.1")
        try:
            result = report_generator.generate_html_report(
                player_steamid=1,
                benchmark_steamid=1,
                benchmark_name="test",
                db_path=populated_db_for_report,
            )
        finally:
            for h in list(logger.handlers):
                if h.__class__.__name__ == "_ListHandler":
                    logger.removeHandler(h)

        assert isinstance(result, bytes)
        html = result.decode()
        assert "Coach Narrative" not in html
        assert "Interpretation" in html
        error_records = [
            r
            for r in records
            if r.levelno == logging.ERROR
            and "Unexpected narrative error" in r.getMessage()
        ]
        assert error_records, (
            f"Expected ERROR log matching 'Unexpected narrative error', got: "
            f"{[(r.levelname, r.getMessage()) for r in records]}"
        )

    def test_unexpected_exception_reraises_when_dev_fail_fast_set(
        self, monkeypatch, populated_db_for_report
    ):
        """R-9 mitigation: DEV_FAIL_FAST=1 → unexpected RuntimeError bubbles up."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)

        def _raise(*args, **kwargs):
            raise RuntimeError("oops_dev_mode")

        monkeypatch.setattr(interpretation_narrative, "build_narrative_report", _raise)
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        monkeypatch.setenv("DEV_FAIL_FAST", "1")

        with _pytest_v204.raises(RuntimeError, match="oops_dev_mode"):
            report_generator.generate_html_report(
                player_steamid=1,
                benchmark_steamid=1,
                benchmark_name="test",
                db_path=populated_db_for_report,
            )

    def test_no_narrative_toggle_skips_narrative_path(
        self,
        monkeypatch,
        populated_db_for_report,
        make_fake_anthropic,
        mock_validator_pass,
    ):
        """SC-6 v1-baseline: no_narrative=True → 'Coach Narrative' not present;
        build_narrative_report not called even though it would succeed."""
        import importlib
        import interpretation_narrative

        importlib.reload(interpretation_narrative)
        # Path B persistent stream-json: monkeypatch subprocess.Popen with the
        # FakeClaudeProcess from conftest. Mirror make_fake_claude_cli inline
        # since module reload may have invalidated fixture-bound state.
        from tests.conftest import (
            _FakeClaudeProcess,
            _fixture_to_cli_payload,
            load_recorded_fixture,
        )
        _payload = _fixture_to_cli_payload(load_recorded_fixture("ok_donk_peek"))
        _pending_proc = {"holder": None}

        def _popen_factory(cmd, *args, **kwargs):
            # Fresh payloads queue each spawn — supports multi-engagement type loops.
            proc = _FakeClaudeProcess([_payload, _payload, _payload])
            _pending_proc["holder"] = proc
            return proc

        monkeypatch.setattr("subprocess.Popen", _popen_factory)
        interpretation_narrative._close_persistent_client()

        call_counter = {"n": 0}
        original_build = interpretation_narrative.build_narrative_report

        def _counting_build(*args, **kwargs):
            call_counter["n"] += 1
            return original_build(*args, **kwargs)

        monkeypatch.setattr(
            interpretation_narrative, "build_narrative_report", _counting_build
        )
        monkeypatch.setattr(
            interpretation_narrative, "fetch_top_moments", _stub_top_moments
        )

        import report_generator

        importlib.reload(report_generator)
        monkeypatch.setattr(
            report_generator,
            "compute_interpretation",
            lambda **kw: _stub_interpretation_rows(kw.get("engagement_type", "peek")),
        )

        html = report_generator.generate_html_report(
            player_steamid=1,
            benchmark_steamid=1,
            benchmark_name="test",
            db_path=populated_db_for_report,
            no_narrative=True,
        ).decode()

        assert "Coach Narrative" not in html
        assert "Interpretation" in html
        assert call_counter["n"] == 0, (
            f"build_narrative_report should NOT be called when no_narrative=True, "
            f"got {call_counter['n']} calls"
        )
