"""Phase v2-interpretation-narrative Plan 05 (Wave 3) — eval harness tests.

Covers:
  - save_rating CSV append+dedup (D-19)
  - save_side_by_side CSV append+dedup (D-20)
  - score_sc1 + score_sc6 verdict aggregations
  - score_cost SC-4 gate (B-6)
  - cost_report aggregation
  - CLI smoke for 8 subcommands
  - record-fixture argparse contract + real-API skip marker (W-7)
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
from contextlib import closing
from pathlib import Path

import pandas as pd
import pytest

from db_utils import init_db


_DONK_SID = 76561198386265483
_KARRIGAN_SID = 76561197989430253


# ── TestSaveRating ───────────────────────────────────────────────────────────


class TestSaveRating:
    def test_save_rating_appends_new_row(self, tmp_path):
        from interpretation_narrative import save_rating
        csv_path = tmp_path / "ratings.csv"
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc123", "dim": "tone", "score": 4,
            "notes": "", "rated_at": "2026-05-12T10:00:00Z",
        })
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc123", "dim": "actionability", "score": 5,
            "notes": "", "rated_at": "2026-05-12T10:01:00Z",
        })
        df = pd.read_csv(csv_path)
        assert len(df) == 2

    def test_save_rating_overwrites_same_dedup_key(self, tmp_path):
        from interpretation_narrative import save_rating
        csv_path = tmp_path / "ratings.csv"
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc123", "dim": "tone", "score": 3,
            "notes": "first", "rated_at": "2026-05-12T10:00:00Z",
        })
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc123", "dim": "tone", "score": 5,
            "notes": "revised", "rated_at": "2026-05-12T11:00:00Z",
        })
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert int(df.iloc[0]["score"]) == 5
        assert df.iloc[0]["notes"] == "revised"

    def test_save_rating_new_prompt_hash_creates_new_row(self, tmp_path):
        from interpretation_narrative import save_rating
        csv_path = tmp_path / "ratings.csv"
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "old111", "dim": "tone", "score": 3,
            "notes": "", "rated_at": "2026-05-12T10:00:00Z",
        })
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "new222", "dim": "tone", "score": 4,
            "notes": "", "rated_at": "2026-05-12T11:00:00Z",
        })
        df = pd.read_csv(csv_path)
        assert len(df) == 2  # D-18 history preserved across prompt iterations

    def test_save_rating_csv_schema_fields(self, tmp_path):
        from interpretation_narrative import save_rating
        csv_path = tmp_path / "ratings.csv"
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc", "dim": "tone", "score": 4,
            "notes": "", "rated_at": "2026-05-12T10:00:00Z",
        })
        df = pd.read_csv(csv_path)
        assert list(df.columns) == [
            "report_id", "player_steamid", "prompt_hash",
            "dim", "score", "notes", "rated_at",
        ]

    def test_save_rating_handles_unicode_notes(self, tmp_path):
        from interpretation_narrative import save_rating
        csv_path = tmp_path / "ratings.csv"
        save_rating(str(csv_path), {
            "report_id": "v2_donk", "player_steamid": _DONK_SID,
            "prompt_hash": "abc", "dim": "tone", "score": 4,
            "notes": "тон агрессивный, без хеджа", "rated_at": "2026-05-12T10:00:00Z",
        })
        df = pd.read_csv(csv_path, encoding="utf-8")
        assert df.iloc[0]["notes"] == "тон агрессивный, без хеджа"


# ── TestSaveSideBySide ───────────────────────────────────────────────────────


class TestSaveSideBySide:
    def test_save_side_by_side_appends(self, tmp_path):
        from interpretation_narrative import save_side_by_side
        csv_path = tmp_path / "sbs.csv"
        save_side_by_side(str(csv_path), {
            "pair_id": "pair_001", "player_steamid": _DONK_SID,
            "preferred_version": "v2", "v1_rating": 2, "v2_rating": 5,
            "notes": "", "rated_at": "2026-05-12T10:00:00Z",
        })
        save_side_by_side(str(csv_path), {
            "pair_id": "pair_002", "player_steamid": _KARRIGAN_SID,
            "preferred_version": "v2", "v1_rating": 3, "v2_rating": 4,
            "notes": "", "rated_at": "2026-05-12T10:05:00Z",
        })
        df = pd.read_csv(csv_path)
        assert len(df) == 2

    def test_save_side_by_side_overwrites_same_pair(self, tmp_path):
        from interpretation_narrative import save_side_by_side
        csv_path = tmp_path / "sbs.csv"
        save_side_by_side(str(csv_path), {
            "pair_id": "pair_001", "player_steamid": _DONK_SID,
            "preferred_version": "v1", "v1_rating": 4, "v2_rating": 4,
            "notes": "first", "rated_at": "2026-05-12T10:00:00Z",
        })
        save_side_by_side(str(csv_path), {
            "pair_id": "pair_001", "player_steamid": _DONK_SID,
            "preferred_version": "v2", "v1_rating": 2, "v2_rating": 5,
            "notes": "second", "rated_at": "2026-05-12T11:00:00Z",
        })
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert df.iloc[0]["preferred_version"] == "v2"
        assert df.iloc[0]["notes"] == "second"

    def test_save_side_by_side_schema(self, tmp_path):
        from interpretation_narrative import save_side_by_side
        csv_path = tmp_path / "sbs.csv"
        save_side_by_side(str(csv_path), {
            "pair_id": "pair_001", "player_steamid": _DONK_SID,
            "preferred_version": "v2", "v1_rating": 2, "v2_rating": 5,
            "notes": "", "rated_at": "2026-05-12T10:00:00Z",
        })
        df = pd.read_csv(csv_path)
        assert list(df.columns) == [
            "pair_id", "player_steamid", "preferred_version",
            "v1_rating", "v2_rating", "notes", "rated_at",
        ]


# ── TestScoreSC1 ─────────────────────────────────────────────────────────────


def _write_ratings(csv_path: Path, scores_by_dim: dict[str, float], n_reports: int = 10,
                   prompt_hash: str = "ph1") -> None:
    """Helper — write a synthetic ratings CSV with N reports × 5 dims."""
    rows = []
    dims = ["factual_accuracy", "actionability", "tone", "attribution", "hallucinations"]
    for i in range(n_reports):
        for dim in dims:
            rows.append({
                "report_id": f"v2_player_{i}",
                "player_steamid": _DONK_SID + i,
                "prompt_hash": prompt_hash,
                "dim": dim,
                "score": scores_by_dim.get(dim, 4.0),
                "notes": "",
                "rated_at": f"2026-05-12T10:0{i % 10}:00Z",
            })
    pd.DataFrame(rows).to_csv(csv_path, index=False)


class TestScoreSC1:
    def test_score_pass_when_avg_geq_4_and_per_dim_geq_3_5(self, tmp_path):
        from interpretation_narrative import score_sc1
        csv_path = tmp_path / "ratings.csv"
        _write_ratings(csv_path, {d: 4.5 for d in [
            "factual_accuracy", "actionability", "tone", "attribution", "hallucinations",
        ]})
        result = score_sc1(str(csv_path))
        assert result["pass"] is True
        assert result["avg"] == pytest.approx(4.5, rel=1e-3)
        assert all(v >= 3.5 for v in result["per_dim"].values())

    def test_score_fail_on_avg_below_4(self, tmp_path):
        from interpretation_narrative import score_sc1
        csv_path = tmp_path / "ratings.csv"
        _write_ratings(csv_path, {d: 3.5 for d in [
            "factual_accuracy", "actionability", "tone", "attribution", "hallucinations",
        ]})
        result = score_sc1(str(csv_path))
        assert result["pass"] is False
        assert any("avg" in r for r in result["fail_reasons"])

    def test_score_fail_on_per_dim_floor(self, tmp_path):
        from interpretation_narrative import score_sc1
        csv_path = tmp_path / "ratings.csv"
        _write_ratings(csv_path, {
            "factual_accuracy": 5.0, "actionability": 5.0,
            "tone": 5.0, "attribution": 5.0, "hallucinations": 3.0,
        })
        result = score_sc1(str(csv_path))
        assert result["pass"] is False
        # average is 4.6 -> avg passes; floor on hallucinations fails
        assert result["avg"] == pytest.approx(4.6, rel=1e-3)
        assert any("hallucinations" in r for r in result["fail_reasons"])

    def test_score_handles_partial_eval_set(self, tmp_path):
        from interpretation_narrative import score_sc1
        csv_path = tmp_path / "ratings.csv"
        _write_ratings(csv_path, {d: 4.5 for d in [
            "factual_accuracy", "actionability", "tone", "attribution", "hallucinations",
        ]}, n_reports=3)
        result = score_sc1(str(csv_path))
        # Score still computes; n_reports flag is exposed
        assert result["n_reports"] == 3
        assert result["pass"] is True


# ── TestScoreCost (B-6 — SC-4 gate) ──────────────────────────────────────────


def _populate_cache(db_path: str, rows: list[dict]) -> None:
    init_db(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        with conn:
            for r in rows:
                conn.execute(
                    "INSERT INTO narrative_cache "
                    "(player_steamid, engagement_type, content_hash, narrative_md, "
                    " model, tokens_in, tokens_out, cache_creation_input_tokens, "
                    " cache_read_input_tokens, generated_at, prompt_hash) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (r["sid"], r["et"], r["ch"], "md", r["model"],
                     r["in"], r["out"], r.get("cw", 0), r.get("cr", 0),
                     r["gen_at"], r.get("ph", "ph1")),
                )


class TestScoreCost:
    def test_score_cost_pass_when_under_threshold(self, tmp_path):
        """5 reports totalling ~$0.30 -> avg $0.06 -> PASS."""
        from interpretation_narrative import _cli_main
        db_path = str(tmp_path / "analytics.db")
        # sonnet-4-6 pricing: input $3/M, output $15/M.
        # 5 rows × 5000 in + 1000 out = 25k in + 5k out
        # cost = 25000*3/1M + 5000*15/1M = 0.075 + 0.075 = $0.15 total -> avg $0.03/report
        rows = [
            {"sid": _DONK_SID, "et": "peek", "ch": f"h{i}",
             "model": "claude-sonnet-4-6",
             "in": 5000, "out": 1000,
             "gen_at": f"2026-05-12T10:0{i}:00Z"}
            for i in range(5)
        ]
        _populate_cache(db_path, rows)
        rc = _cli_main(["score-cost", "--db", db_path])
        assert rc == 0

    def test_score_cost_passes_under_subscription_mode_even_at_high_tokens(self, tmp_path):
        """Path B: SC-4 gate is informational under subscription mode (PRICING-table
        cost is reported but never gates exit code). Was: FAIL (exit 2) when
        avg cost > --max-per-report. Now: PASS (exit 0) regardless of token usage.
        """
        from interpretation_narrative import _cli_main
        db_path = str(tmp_path / "analytics.db")
        rows = [
            {"sid": _DONK_SID, "et": "peek", "ch": f"h{i}",
             "model": "claude-sonnet-4-6",
             "in": 100_000, "out": 30_000,
             "gen_at": f"2026-05-12T10:0{i}:00Z"}
            for i in range(5)
        ]
        _populate_cache(db_path, rows)
        rc = _cli_main(["score-cost", "--db", db_path])
        assert rc == 0  # Path B subscription mode: always PASS

    def test_score_cost_skip_when_empty_cache(self, tmp_path):
        from interpretation_narrative import _cli_main
        db_path = str(tmp_path / "analytics.db")
        init_db(db_path)
        rc = _cli_main(["score-cost", "--db", db_path])
        assert rc == 0  # SKIP

    def test_score_cost_max_per_report_flag_is_informational_under_sub_mode(self, tmp_path):
        """Path B: --max-per-report flag is preserved for backward compat but
        never affects exit code under subscription mode (always PASS).
        """
        from interpretation_narrative import _cli_main
        db_path = str(tmp_path / "analytics.db")
        rows = [
            {"sid": _DONK_SID, "et": "peek", "ch": f"h{i}",
             "model": "claude-sonnet-4-6",
             "in": 30_000, "out": 4_000,
             "gen_at": f"2026-05-12T10:0{i}:00Z"}
            for i in range(5)
        ]
        _populate_cache(db_path, rows)
        # default 0.10 → was FAIL; Path B → PASS
        rc_default = _cli_main(["score-cost", "--db", db_path])
        assert rc_default == 0
        # raised to 0.50 → still PASS (gate informational)
        rc_raised = _cli_main([
            "score-cost", "--db", db_path, "--max-per-report", "0.50",
        ])
        assert rc_raised == 0


# ── TestScoreSideBySide ──────────────────────────────────────────────────────


def _write_sbs(csv_path: Path, pairs: list[tuple[int, int, str]]) -> None:
    rows = [
        {"pair_id": f"pair_{i:03d}", "player_steamid": _DONK_SID + i,
         "preferred_version": pref, "v1_rating": v1, "v2_rating": v2,
         "notes": "", "rated_at": "2026-05-12T10:00:00Z"}
        for i, (v1, v2, pref) in enumerate(pairs)
    ]
    pd.DataFrame(rows).to_csv(csv_path, index=False)


class TestScoreSideBySide:
    def test_side_by_side_pass(self, tmp_path):
        from interpretation_narrative import score_sc6
        csv_path = tmp_path / "sbs.csv"
        _write_sbs(csv_path, [(2, 5, "v2"), (2, 4, "v2"), (3, 5, "v2"),
                              (2, 4, "v2"), (1, 5, "v2")])
        result = score_sc6(str(csv_path))
        assert result["pass"] is True
        assert result["v1_mean"] == pytest.approx(2.0, abs=0.1)
        assert result["v2_mean"] == pytest.approx(4.6, abs=0.1)
        assert result["delta"] >= 1.0

    def test_side_by_side_fail_on_delta(self, tmp_path):
        from interpretation_narrative import score_sc6
        csv_path = tmp_path / "sbs.csv"
        _write_sbs(csv_path, [(3, 4, "v2"), (3, 4, "v2"), (3, 4, "v2"),
                              (4, 4, "v2"), (4, 4, "v2")])
        result = score_sc6(str(csv_path))
        assert result["pass"] is False
        assert any("delta" in r for r in result["fail_reasons"])

    def test_side_by_side_fail_on_v1_too_high(self, tmp_path):
        from interpretation_narrative import score_sc6
        csv_path = tmp_path / "sbs.csv"
        # v1 mean 3.5, v2 4.5 -> delta 1.0 (ok), v2 ok, but v1 > 3.0 -> fail
        _write_sbs(csv_path, [(4, 5, "v2"), (3, 4, "v2"), (4, 5, "v2"),
                              (3, 4, "v2"), (4, 5, "v2")])
        result = score_sc6(str(csv_path))
        assert result["pass"] is False
        assert any("v1_mean" in r for r in result["fail_reasons"])


# ── TestCostReport ───────────────────────────────────────────────────────────


class TestCostReport:
    def test_cost_report_sums_correctly(self, tmp_path):
        from interpretation_narrative import cost_report
        db_path = str(tmp_path / "analytics.db")
        # sonnet-4-6: 10k in + 2k out = 10000*3/1M + 2000*15/1M = 0.03 + 0.03 = $0.06
        rows = [
            {"sid": _DONK_SID, "et": "peek", "ch": "h1",
             "model": "claude-sonnet-4-6",
             "in": 10_000, "out": 2_000,
             "gen_at": "2026-05-12T10:00:00Z"},
            {"sid": _DONK_SID, "et": "hold", "ch": "h2",
             "model": "claude-sonnet-4-6",
             "in": 10_000, "out": 2_000,
             "gen_at": "2026-05-12T10:01:00Z"},
            {"sid": _KARRIGAN_SID, "et": "peek", "ch": "h3",
             "model": "claude-sonnet-4-6",
             "in": 10_000, "out": 2_000,
             "gen_at": "2026-05-12T10:02:00Z"},
        ]
        _populate_cache(db_path, rows)
        data = cost_report(db_path)
        # Expected: 3 rows × $0.06 = $0.18 total
        assert data["total_usd"] == pytest.approx(0.18, abs=0.01)
        assert data["by_model"]["claude-sonnet-4-6"]["reports"] == 3

    def test_cost_report_handles_empty_cache(self, tmp_path):
        from interpretation_narrative import cost_report
        db_path = str(tmp_path / "analytics.db")
        init_db(db_path)
        data = cost_report(db_path)
        assert data.get("total_usd", 0.0) == 0.0

    def test_cost_report_groups_by_model(self, tmp_path):
        from interpretation_narrative import cost_report
        db_path = str(tmp_path / "analytics.db")
        rows = [
            {"sid": _DONK_SID, "et": "peek", "ch": "h1",
             "model": "claude-sonnet-4-6",
             "in": 10_000, "out": 2_000,
             "gen_at": "2026-05-12T10:00:00Z"},
            {"sid": _DONK_SID, "et": "hold", "ch": "h2",
             "model": "claude-opus-4-7",
             "in": 10_000, "out": 2_000,
             "gen_at": "2026-05-12T10:01:00Z"},
        ]
        _populate_cache(db_path, rows)
        data = cost_report(db_path)
        assert "claude-sonnet-4-6" in data["by_model"]
        assert "claude-opus-4-7" in data["by_model"]


# ── TestRecordFixture (W-7 — argparse contract + real-API skip) ───────────────


class TestRecordFixture:
    def test_record_fixture_argparse_smoke(self):
        """Argparse-only smoke: --help mentions required flags. No API call."""
        result = subprocess.run(
            [sys.executable, "-m", "interpretation_narrative", "record-fixture", "--help"],
            capture_output=True, text=True,
        )
        # argparse --help exits 0 and prints to stdout
        assert result.returncode == 0
        out = result.stdout + result.stderr
        assert "--player" in out
        assert "--type" in out
        assert "--out" in out

    def test_record_fixture_integration_real_api(self, tmp_path):
        """W-7: real-API integration test — skipped by default to prevent CI leaks."""
        pytest.skip(
            "requires real ANTHROPIC_API_KEY; run manually with "
            "python -m pytest tests/test_eval_harness.py"
            "::TestRecordFixture::test_record_fixture_integration_real_api"
        )
        # Body left in place for manual operator-driven execution.
        from interpretation_narrative import _cli_main
        out_path = tmp_path / "fixture.json"
        rc = _cli_main([
            "record-fixture", "--player", str(_DONK_SID),
            "--type", "peek", "--out", str(out_path),
        ])
        assert rc == 0
        assert out_path.exists()


# ── TestCLISmoke ─────────────────────────────────────────────────────────────


class TestCLISmoke:
    def test_help_lists_all_subcommands(self):
        result = subprocess.run(
            [sys.executable, "-m", "interpretation_narrative", "--help"],
            capture_output=True, text=True,
        )
        assert result.returncode == 0
        out = result.stdout + result.stderr
        for cmd in [
            "cost-report", "eval-rate", "generate-eval-set",
            "generate-side-by-side", "score", "score-side-by-side",
            "score-cost", "rate-side-by-side", "record-fixture",
        ]:
            assert cmd in out, f"missing subcommand in --help: {cmd}"

    def test_cost_report_smoke(self, tmp_path):
        from interpretation_narrative import _cli_main
        db_path = str(tmp_path / "analytics.db")
        init_db(db_path)
        rc = _cli_main(["cost-report", "--db", db_path])
        assert rc == 0

    def test_eval_rate_smoke(self, tmp_path):
        from interpretation_narrative import _cli_main
        csv_path = tmp_path / "ratings.csv"
        rc = _cli_main([
            "eval-rate", "--csv", str(csv_path),
            "--report-id", "smoke", "--player", str(_DONK_SID),
            "--dim", "tone", "--score", "4", "--notes", "test",
            "--prompt-hash", "smoke_hash",
        ])
        assert rc == 0
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert df.iloc[0]["dim"] == "tone"
        assert int(df.iloc[0]["score"]) == 4

    def test_rate_side_by_side_smoke(self, tmp_path):
        from interpretation_narrative import _cli_main
        csv_path = tmp_path / "sbs.csv"
        rc = _cli_main([
            "rate-side-by-side", "--csv", str(csv_path),
            "--pair-id", "pair_001", "--player", str(_DONK_SID),
            "--preferred", "v2", "--v1-rating", "2", "--v2-rating", "5",
            "--notes", "smoke",
        ])
        assert rc == 0
        df = pd.read_csv(csv_path)
        assert len(df) == 1
        assert df.iloc[0]["preferred_version"] == "v2"

    def test_generate_eval_set_emit_timings_flag_recognized(self, tmp_path, monkeypatch):
        """B-A: generate-eval-set accepts --emit-timings <path> and writes JSON with p95_s."""
        from interpretation_narrative import _cli_main
        import interpretation_narrative as in_

        # Stub report_generator.generate_html_report so we don't hit the DB.
        import report_generator
        monkeypatch.setattr(
            report_generator,
            "generate_html_report",
            lambda sid, bench_sid, bench_name, db_path=None, no_narrative=False: b"<html></html>",
        )

        roster_path = tmp_path / "roster.json"
        roster_path.write_text(json.dumps({
            "players": [
                {"steamid": _DONK_SID, "tier": "top", "name": "donk"},
                {"steamid": _KARRIGAN_SID, "tier": "top", "name": "karrigan"},
            ]
        }), encoding="utf-8")
        timings_path = tmp_path / "timings.json"
        out_dir = tmp_path / "out"
        rc = _cli_main([
            "generate-eval-set",
            "--roster", str(roster_path),
            "--out-dir", str(out_dir),
            "--db", ":memory:",
            "--emit-timings", str(timings_path),
        ])
        assert rc == 0
        assert timings_path.exists()
        payload = json.loads(timings_path.read_text(encoding="utf-8"))
        assert "timings" in payload
        assert "p95_s" in payload
        assert "n_ok" in payload
        assert "n_total" in payload
        assert payload["n_total"] == 2
        # All stubbed calls succeed -> p95 is a float, n_ok == n_total
        assert payload["n_ok"] == 2
        assert isinstance(payload["p95_s"], (int, float))


# ── TestCallLLMPublicName ────────────────────────────────────────────────────


class TestCallLLMPublicName:
    """W-8: call_llm is publicly importable (not behind a leading underscore)."""

    def test_call_llm_is_public(self):
        import interpretation_narrative as inm
        assert hasattr(inm, "call_llm"), \
            "call_llm must be a public name on interpretation_narrative"
        # Should be callable
        assert callable(getattr(inm, "call_llm"))
