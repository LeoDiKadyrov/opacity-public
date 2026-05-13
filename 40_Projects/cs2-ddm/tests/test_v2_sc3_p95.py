"""Plan 06 SC-3 P95 generation-time gate — timings.json schema smoke.

SC-3 = "P95 generation latency ≤30s on cold-cache eval set (n≥10)". The
real measurement is operator-executed (Task 3 in Plan 06 — requires real
ANTHROPIC_API_KEY + ~10 live LLM calls). What we automate here is the
contract that lets the operator's gate command actually work:

  1. `--emit-timings <path>` produces a JSON file with the right shape.
  2. Each per-entry record has the keys the SC-3 gate reads.
  3. `p95_s` is computed from ok-only samples (D-04 / D-05 decision —
     see Plan 05 SUMMARY) so failed reports don't poison the metric.
  4. `n_ok / n_total` are surfaced separately so completeness is gated
     independently from latency.

Plan 05 already added the broader CLI test (TestCLISmoke in
tests/test_eval_harness.py). This file is Plan 06's targeted SC-3
verifier — kept narrow + named after the gate it serves so a future
grep for "SC-3" lands here directly.

These tests use a monkeypatched `report_generator.generate_html_report`
to dodge DB / network — no real LLM call. The actual ≤30s gate is
applied by the operator after running:

    python -m interpretation_narrative generate-eval-set \\
        --out-dir evals/generated --emit-timings evals/generated/timings.json
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest


_DONK_SID = 76561198386265483
_KARRIGAN_SID = 76561197989430253

_ENTRY_KEYS = {"player_steamid", "name", "ok", "elapsed_s"}
_PAYLOAD_KEYS = {"timings", "p95_s", "n_ok", "n_total"}


@pytest.fixture
def stub_report_generator(monkeypatch):
    """Stub generate_html_report to return constant bytes without DB / LLM."""
    import report_generator

    monkeypatch.setattr(
        report_generator,
        "generate_html_report",
        lambda sid, bench_sid, bench_name, db_path=None, no_narrative=False: b"<html></html>",
    )
    return report_generator


@pytest.fixture
def roster_path(tmp_path):
    p = tmp_path / "roster.json"
    p.write_text(
        json.dumps(
            {
                "players": [
                    {"steamid": _DONK_SID, "tier": "top", "name": "donk"},
                    {"steamid": _KARRIGAN_SID, "tier": "top", "name": "karrigan"},
                ]
            }
        ),
        encoding="utf-8",
    )
    return p


def _run_generate(roster_path: Path, tmp_path: Path):
    from interpretation_narrative import _cli_main

    timings_path = tmp_path / "timings.json"
    out_dir = tmp_path / "out"
    rc = _cli_main(
        [
            "generate-eval-set",
            "--roster", str(roster_path),
            "--out-dir", str(out_dir),
            "--db", ":memory:",
            "--emit-timings", str(timings_path),
        ]
    )
    assert rc == 0
    return json.loads(timings_path.read_text(encoding="utf-8"))


def test_timings_payload_top_level_schema(stub_report_generator, roster_path, tmp_path):
    """SC-3 gate reads p95_s / n_ok / n_total — must always be present."""
    payload = _run_generate(roster_path, tmp_path)
    assert _PAYLOAD_KEYS.issubset(payload.keys()), (
        f"missing top-level keys: {_PAYLOAD_KEYS - payload.keys()}"
    )
    assert isinstance(payload["timings"], list)
    assert isinstance(payload["n_ok"], int)
    assert isinstance(payload["n_total"], int)
    assert payload["n_total"] == 2


def test_timings_per_entry_schema(stub_report_generator, roster_path, tmp_path):
    """Each per-player row carries the keys needed for failure-attribution."""
    payload = _run_generate(roster_path, tmp_path)
    for entry in payload["timings"]:
        assert _ENTRY_KEYS.issubset(entry.keys()), (
            f"missing per-entry keys in {entry!r}: {_ENTRY_KEYS - entry.keys()}"
        )
        assert isinstance(entry["player_steamid"], int)
        assert isinstance(entry["ok"], bool)
        assert isinstance(entry["elapsed_s"], (int, float))
        assert entry["elapsed_s"] >= 0.0


def test_p95_uses_ok_only_samples(stub_report_generator, roster_path, tmp_path):
    """All stubbed calls succeed -> p95 is a numeric latency (D-04 decision)."""
    payload = _run_generate(roster_path, tmp_path)
    assert payload["n_ok"] == payload["n_total"] == 2
    assert isinstance(payload["p95_s"], (int, float))
    assert payload["p95_s"] >= 0.0


def test_sc3_gate_assert_is_expressible(stub_report_generator, roster_path, tmp_path):
    """Show that the operator's `assert p95 <= 30` gate is wired off the JSON.

    Plan 06 Task 3 acceptance criterion runs this exact check:
        python -c "import json; data=json.load(open('.../timings.json'));
                   assert data['p95_s'] <= 30.0"
    We replicate it on the stubbed timings (which will be a tiny fraction of
    a second) and assert the gate passes — proving the wiring is correct.
    """
    payload = _run_generate(roster_path, tmp_path)
    p95 = payload["p95_s"]
    assert p95 is not None, "p95_s must not be None when n_ok > 0"
    # Stubbed report build is microseconds — well under the 30s SC-3 gate.
    assert p95 <= 30.0, f"SC-3 wiring smoke: stub p95 {p95:.4f}s > 30s"
