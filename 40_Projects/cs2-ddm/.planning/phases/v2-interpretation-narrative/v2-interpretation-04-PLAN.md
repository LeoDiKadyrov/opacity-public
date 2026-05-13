---
phase: v2-interpretation-narrative
plan: 04
type: execute
wave: 2
depends_on: [02]
files_modified:
  - report_generator.py
  - tests/test_report_generator.py
autonomous: true
requirements: [REQ-6, REQ-10]
must_haves:
  truths:
    - "generate_html_report inserts narrative block between header and interpretation_section when build_narrative_report returns text"
    - "On NarrativeBuildError → narrative_section = '' (empty), report still ships with tier table — REQ-10 fail-soft proven"
    - "On unexpected Exception (not NarrativeBuildError) → re-raise iff env DEV_FAIL_FAST=1, else log + fall back (R-9 mitigation)"
    - "Failure logged via config.get_logger (writes to ddm_analysis.log) — narrative_failures.log writes happen inside interpretation_narrative._failure_logger before NarrativeBuildError is raised; the report_generator catch only adds a high-level log line for operator visibility"
    - "generate_html_report accepts optional no_narrative: bool = False param for SC-6 v1-baseline rendering"
    - "Markdown narrative converted to HTML via existing pipeline (re-use whatever report_generator already does for markdown blocks)"
  artifacts:
    - path: "report_generator.py"
      provides: "Narrative block insertion + fail-soft + no_narrative toggle for SC-6"
      contains: "build_narrative_report"
    - path: "tests/test_report_generator.py"
      provides: "Integration tests for narrative pass-path + fallback path + no_narrative toggle"
      min_lines: 80
  key_links:
    - from: "report_generator.generate_html_report"
      to: "interpretation_narrative.build_narrative_report"
      via: "deferred import + try/except NarrativeBuildError + try/except Exception with DEV_FAIL_FAST"
      pattern: "build_narrative_report"
    - from: "report_generator.generate_html_report"
      to: "interpretation_narrative.fetch_top_moments"
      via: "called per metric × engagement_type to assemble top_moments dict"
      pattern: "fetch_top_moments"
---

<objective>
Wire the narrative block into report_generator.py (REQ-6 + REQ-10). When build_narrative_report succeeds, narrative HTML appears between the report header and the existing tier-table interpretation section. When it fails (LLM error, validator reject, missing data, missing prompt) → narrative section silently empty, tier table still ships, failure logged. Add `no_narrative: bool = False` param to generate_html_report for SC-6 side-by-side v1-baseline rendering.

Purpose: This plan is what makes v2 SHIP. Without it, build_narrative_report exists but no user ever sees the output. With it, every HTML report download includes the narrative if API + validator + cache cooperate, and silently degrades to v1 behavior otherwise. R-9 mitigation requires distinguishing expected (NarrativeBuildError) from unexpected (Exception) failures so dev bugs surface in DEV_FAIL_FAST mode.

Output:
- `report_generator.py` — insertion point + try/except + no_narrative toggle
- `tests/test_report_generator.py` — extended with integration tests covering the 4 paths (pass, NarrativeBuildError, unexpected exception, no_narrative=True)
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-SPEC.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-CONTEXT.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-PATTERNS.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-VALIDATION.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-02-SUMMARY.md
@.planning/phases/v2-interpretation-narrative/v2-interpretation-03-SUMMARY.md
@CLAUDE.md
@report_generator.py
@interpretation.py
@interpretation_narrative.py

<interfaces>
<!-- Existing contracts. -->

From `report_generator.py:595-665` — generate_html_report current shape:
```python
def generate_html_report(
    player_steamid: int, benchmark_steamid: int, benchmark_name: str,
    db_path: str = DB_PATH,
) -> bytes:
    player_steamid = int(player_steamid)
    benchmark_steamid = int(benchmark_steamid)
    today = date.today().isoformat()
    player_display = PLAYER_NAMES.get(player_steamid, str(player_steamid))

    # ── Interpretation section ─────────────────────────────────────
    interp_parts: list[str] = []
    interp_rows_by_type: dict[str, list[dict]] = {}
    for engagement_type in ["peek", "hold"]:
        rows = compute_interpretation(...)
        interp_rows_by_type[engagement_type] = rows
        # ... build card_html + table_html ...
    interp_content = "\n".join(interp_parts)
    interpretation_section = _section("Interpretation", interp_content)

    # ── Distributions + Raw + Assemble ─────────────────────────────
    ...
    html = f"""...
    <h1>Djok Reaction Report</h1>
    <div class="sub-header">{player_steamid} vs {benchmark_name} · Generated {today}</div>
    {interpretation_section}
    {distributions_section}
    {raw_section}
    """
```

Insertion point: between `<div class="sub-header">...</div>` and `{interpretation_section}`. Use `_section("Coach Narrative", narrative_html)`.

From PATTERNS.md `report_generator.py` MODIFIED section — fail-soft pattern reference:
```python
narrative_section = ""
if not no_narrative:
    try:
        from interpretation_narrative import build_narrative_report, fetch_top_moments, NarrativeBuildError
        # build top_moments + player_context, call build_narrative_report
        narrative_md = build_narrative_report(rows_combined, top_moments, player_context)
        narrative_html = _markdown_to_html(narrative_md)
        narrative_section = _section("Coach Narrative", narrative_html)
    except NarrativeBuildError as e:
        logger = get_logger(f"report.{player_steamid}")
        logger.warning(f"Narrative build failed (fail-soft): {e}")
    except Exception as e:
        if os.environ.get("DEV_FAIL_FAST") == "1":
            raise
        logger = get_logger(f"report.{player_steamid}")
        logger.error(f"Unexpected narrative error (fail-soft): {e!r}")
```

Markdown→HTML conversion: report_generator.py currently does NOT have a markdown converter (text rendering is f-string + raw HTML strings). For v2 narrative (which IS markdown), the simplest options are:
1. Use Python's `markdown` library (`pip install markdown`) — adds a small dep
2. Use `mistune` (lighter)
3. DIY minimal: convert `## Header` → `<h3>Header</h3>` + `\n\n` paragraphs → `<p>...</p>`

**Decision: DIY minimal converter.** v2 prompt only emits 3 fixed `##` headers + plain paragraph text. No tables, no code blocks, no nested lists in narrative output. A 20-line `_markdown_to_html_minimal` keeps the dep surface flat. If output complexity grows in v2.1, swap to `markdown` library then.

Minimal converter:
```python
import re

def _markdown_to_html_minimal(md: str) -> str:
    """Convert v2 narrative markdown → HTML. Only handles `## Header` + paragraphs.
    Output is wrapped in <div class="narrative">. Safe for v2 prompt output shape."""
    out = []
    for block in re.split(r"\n{2,}", md.strip()):
        block = block.strip()
        if not block:
            continue
        if block.startswith("## "):
            out.append(f'<h3 class="narrative-header">{block[3:].strip()}</h3>')
        else:
            # treat as paragraph; preserve <br> on single newlines within
            paragraph = block.replace("\n", "<br>")
            out.append(f'<p class="narrative-paragraph">{paragraph}</p>')
    return f'<div class="narrative">\n' + "\n".join(out) + "\n</div>"
```

From `interpretation_narrative` (W2):
```python
def fetch_top_moments(db_path, player_steamid, metric, engagement_type, benchmark_p50, n_worst=2, n_best=1) -> list[dict]: ...
def build_narrative_report(rows, top_moments, player_context, db_path=DB_PATH) -> str: ...
class NarrativeBuildError(Exception): ...
```

Building top_moments per metric × engagement_type:
```python
top_moments = {}
metrics_to_attribute = ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"]
for engagement_type in ["peek", "hold"]:
    for metric in metrics_to_attribute:
        # benchmark_p50 lookup from interp_rows_by_type[engagement_type] for this metric
        try:
            row = next(r for r in interp_rows_by_type[engagement_type] if r["metric"] == metric)
            benchmark_p50 = row.get("benchmark_p50")
        except StopIteration:
            continue
        if benchmark_p50 is None:
            continue
        moments = fetch_top_moments(db_path, player_steamid, metric, engagement_type, benchmark_p50)
        if moments:
            top_moments[f"{metric}::{engagement_type}"] = moments
```

Player context:
```python
player_context = {
    "player_steamid": player_steamid,
    "player_name": PLAYER_NAMES.get(player_steamid, f"player_{str(player_steamid)[-4:]}"),
    "engagement_type": "combined",  # narrative covers both peek + hold
    "n_total_engagements": sum(len(rows) for rows in interp_rows_by_type.values()),
}
```

Combined rows for build_narrative_report `rows` arg:
```python
rows_combined = []
for et in ["peek", "hold"]:
    for r in interp_rows_by_type[et]:
        rows_combined.append({**r, "engagement_type": et})
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: report_generator narrative integration + fail-soft + no_narrative toggle</name>
  <files>report_generator.py, tests/test_report_generator.py</files>
  <read_first>
    - report_generator.py full file (focus 595-665 for assembly site)
    - tests/test_report_generator.py current tests (W1 patterns; no narrative tests yet)
    - interpretation_narrative.py (verify build_narrative_report + NarrativeBuildError surface from W2)
    - interpretation.py compute_interpretation return shape (rows have 'metric', 'benchmark_p50' keys)
  </read_first>
  <behavior>
    RED tests in `tests/test_report_generator.py` (additional to existing tests):

    **TestNarrativeIntegration:**
    - `test_narrative_section_present_when_build_succeeds(monkeypatch, populated_db_for_report, make_fake_anthropic)` — monkeypatch `interpretation_narrative._get_client` to clean fixture; call `generate_html_report(...)`; decode bytes; assert `"Coach Narrative"` substring in HTML; assert `"narrative-header"` class present in HTML; assert `"## Что у тебя получается"` NOT in HTML (markdown converted, not raw); assert "Что у тебя получается" IS in HTML (header text inside `<h3>`).
    - `test_narrative_appears_before_interpretation_section(monkeypatch, populated_db_for_report, make_fake_anthropic)` — find positions of "Coach Narrative" and "Interpretation" headers in returned HTML; assert narrative position < interpretation position
    - `test_narrative_falls_back_silently_on_NarrativeBuildError(monkeypatch, populated_db_for_report)` — monkeypatch `interpretation_narrative.build_narrative_report` to raise NarrativeBuildError; call `generate_html_report(...)`; assert returns bytes (no raise); assert `"Coach Narrative"` NOT in HTML; assert `"Interpretation"` IS in HTML (tier table preserved)
    - `test_narrative_logs_failure_on_NarrativeBuildError(monkeypatch, populated_db_for_report, caplog)` — same as above; assert log message at WARNING level matching /Narrative build failed/ in caplog OR in narrative_failures.log
    - `test_unexpected_exception_swallowed_when_dev_fail_fast_unset(monkeypatch, populated_db_for_report)` — monkeypatch `interpretation_narrative.build_narrative_report` to raise `RuntimeError("oops")`; ensure DEV_FAIL_FAST not set; assert `generate_html_report(...)` returns bytes (does NOT raise); assert log at ERROR level
    - `test_unexpected_exception_reraises_when_dev_fail_fast_set(monkeypatch, populated_db_for_report)` — monkeypatch as above; `monkeypatch.setenv("DEV_FAIL_FAST", "1")`; assert `generate_html_report(...)` raises RuntimeError matching /oops/
    - `test_no_narrative_toggle_skips_narrative_path(monkeypatch, populated_db_for_report, make_fake_anthropic)` — call `generate_html_report(..., no_narrative=True)`; assert `"Coach Narrative"` NOT in HTML even though narrative would have succeeded; assert build_narrative_report NOT called (use a counting wrapper monkeypatch)

    `populated_db_for_report` fixture: extend the existing `mock_db` from `test_interpretation.py` patterns to also include `round_number`, `map_name`, `t0_manual_tick`, and benchmark rows so `compute_interpretation` returns sensible benchmarks. Or stub via monkeypatch: monkeypatch `compute_interpretation` to return canned tier-table rows with benchmark_p50, and monkeypatch `fetch_top_moments` to return canned 3-element lists. Either approach works; the second is faster + isolates report_generator from DB schema details.

    GREEN edit to `report_generator.py:generate_html_report`:
    ```python
    # Add to imports section at top
    import os  # if not already imported

    # Add helper at module level (near _section)
    def _markdown_to_html_minimal(md: str) -> str:
        """Convert v2 narrative markdown → HTML. Handles ## Header + paragraphs only.
        Safe for v2 prompt output shape (3 fixed sections + plain text)."""
        import re
        out = []
        for block in re.split(r"\n{2,}", md.strip()):
            block = block.strip()
            if not block:
                continue
            if block.startswith("## "):
                out.append(f'<h3 class="narrative-header">{block[3:].strip()}</h3>')
            else:
                paragraph = block.replace("\n", "<br>")
                out.append(f'<p class="narrative-paragraph">{paragraph}</p>')
        return '<div class="narrative">\n' + "\n".join(out) + "\n</div>"

    # Modify generate_html_report signature
    def generate_html_report(
        player_steamid: int, benchmark_steamid: int, benchmark_name: str,
        db_path: str = DB_PATH,
        no_narrative: bool = False,  # NEW — SC-6 v1-baseline toggle
    ) -> bytes:
        player_steamid = int(player_steamid)
        benchmark_steamid = int(benchmark_steamid)
        today = date.today().isoformat()
        player_display = PLAYER_NAMES.get(player_steamid, str(player_steamid))

        # ── Interpretation section (existing) ─────────────────────────
        interp_parts: list[str] = []
        interp_rows_by_type: dict[str, list[dict]] = {}
        for engagement_type in ["peek", "hold"]:
            sub_label = "Peek engagements" if engagement_type == "peek" else "Hold engagements"
            rows = compute_interpretation(
                db_path=db_path, player_steamid=player_steamid,
                benchmark_steamid=benchmark_steamid, engagement_type=engagement_type,
            )
            interp_rows_by_type[engagement_type] = rows
            worst = get_worst_metric(rows)
            card_html = _worst_metric_card_html(worst, benchmark_name)
            table_html = _tier_table_html(rows, benchmark_name)
            interp_parts.append(
                f'<h3 class="sub-section-header">{sub_label}</h3>'
                + card_html + table_html
            )
        interp_content = "\n".join(interp_parts)
        interpretation_section = _section("Interpretation", interp_content)

        # ── Narrative section (v2 — fail-soft) ────────────────────────
        narrative_section = ""
        if not no_narrative:
            try:
                from interpretation_narrative import (
                    build_narrative_report, fetch_top_moments, NarrativeBuildError,
                )
                # Build top_moments dict keyed "{metric}::{engagement_type}"
                metrics_attribute = [
                    "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
                    "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
                ]
                top_moments: dict[str, list[dict]] = {}
                for et in ["peek", "hold"]:
                    for metric in metrics_attribute:
                        bench_row = next(
                            (r for r in interp_rows_by_type[et] if r.get("metric") == metric),
                            None,
                        )
                        if bench_row is None or bench_row.get("benchmark_p50") is None:
                            continue
                        moments = fetch_top_moments(
                            db_path, player_steamid, metric, et,
                            benchmark_p50=float(bench_row["benchmark_p50"]),
                        )
                        if moments:
                            top_moments[f"{metric}::{et}"] = moments
                rows_combined = []
                for et in ["peek", "hold"]:
                    for r in interp_rows_by_type[et]:
                        rows_combined.append({**r, "engagement_type": et})
                player_context = {
                    "player_steamid": player_steamid,
                    "player_name": PLAYER_NAMES.get(
                        player_steamid, f"player_{str(player_steamid)[-4:]}"
                    ),
                    "engagement_type": "combined",
                    "n_total_engagements": sum(len(rs) for rs in interp_rows_by_type.values()),
                }
                narrative_md = build_narrative_report(
                    rows_combined, top_moments, player_context, db_path=db_path,
                )
                narrative_html = _markdown_to_html_minimal(narrative_md)
                narrative_section = _section("Coach Narrative", narrative_html)
            except NarrativeBuildError as e:
                # Expected fail-soft path — log and continue with tier table only.
                from config import get_logger  # logger factory
                logger = get_logger(f"report.{player_steamid}")
                logger.warning(f"Narrative build failed (fail-soft): {e}")
            except Exception as e:
                # R-9: do NOT silently swallow unexpected exceptions in dev.
                if os.environ.get("DEV_FAIL_FAST") == "1":
                    raise
                from config import get_logger
                logger = get_logger(f"report.{player_steamid}")
                logger.error(f"Unexpected narrative error (fail-soft): {e!r}")

        # ── Distributions section (existing) ──────────────────────────
        ...

        # ── Assemble ───────────────────────────────────────────────────
        html = f"""<!DOCTYPE html>
        ...
        <h1>Djok Reaction Report</h1>
        <div class="sub-header">{player_steamid} vs {benchmark_name} · Generated {today}</div>
        {narrative_section}
        {interpretation_section}
        {distributions_section}
        {raw_section}
        ..."""
        return html.encode("utf-8")
    ```

    Note about CSS for narrative classes: existing _css() function in report_generator generates CSS string. Add minimal narrative styling rules so the section is visually distinct:
    ```css
    .narrative { padding: 1rem; background: #1a1a25; border-left: 3px solid #6a8caf; margin-bottom: 1.5rem; }
    .narrative-header { color: #c4d4e8; margin-top: 1rem; }
    .narrative-paragraph { color: #d4d4e0; line-height: 1.6; }
    ```
    Add these into whatever _css() returns. If executor finds _css is a static f-string, append the rules; if dynamic, hook in.
  </behavior>
  <action>
    1. Write RED tests in `tests/test_report_generator.py` (TestNarrativeIntegration class). Commit (`test(v2-04): RED report_generator narrative integration`).
    2. Edit `report_generator.py` per the GREEN block above:
       - Add `import os` if not present
       - Add `_markdown_to_html_minimal` helper near `_section`
       - Modify `generate_html_report` signature to add `no_narrative: bool = False`
       - Insert narrative section block between Interpretation section build and Assemble
       - Add `{narrative_section}` to assembled HTML between sub-header div and `{interpretation_section}`
       - Add narrative CSS rules to `_css()` output
    3. Verify RED tests now pass.
    4. Hook will black + ruff + pytest. If pytest reveals existing tests broke (e.g., a test that did exact-string-match on the assembled HTML and now finds `narrative_section=""` whitespace), update those tests to use substring assertions.
  </action>
  <verify>
    <automated>python -m pytest tests/test_report_generator.py -p no:cov -x</automated>
  </verify>
  <acceptance_criteria>
    - `grep -c "build_narrative_report" report_generator.py` ≥ 1
    - `grep -c "fetch_top_moments" report_generator.py` ≥ 1
    - `grep -c "NarrativeBuildError" report_generator.py` ≥ 1
    - `grep -c "no_narrative" report_generator.py` ≥ 2 (param + use)
    - `grep -c "DEV_FAIL_FAST" report_generator.py` ≥ 1
    - `grep -c "_markdown_to_html_minimal" report_generator.py` ≥ 2 (def + use)
    - `grep -c "narrative-header\|narrative-paragraph\|class=\"narrative\"" report_generator.py` ≥ 3 (CSS classes referenced from converter + CSS)
    - `python -c "import report_generator; import inspect; sig = inspect.signature(report_generator.generate_html_report); assert 'no_narrative' in sig.parameters; print('OK')"` prints "OK"
    - `python -m pytest tests/test_report_generator.py -p no:cov` ALL PASS (existing + ≥7 new TestNarrativeIntegration tests)
    - `python -m pytest -p no:cov` full suite green
    - W-2: `python -c "from config import get_logger; print(get_logger.__qualname__)"` exits 0 + prints `get_logger` (smoke check that the logger factory imported by report_generator narrative-section block resolves)
  </acceptance_criteria>
  <done>
    Narrative block ships in HTML reports. Fail-soft proven: NarrativeBuildError → empty narrative section + tier table preserved + log entry. Unexpected exceptions log silently in production but re-raise under DEV_FAIL_FAST. SC-6 v1-baseline rendering possible via `no_narrative=True`. _markdown_to_html_minimal handles v2 prompt output shape (3 ## headers + paragraphs).
  </done>
</task>

</tasks>

<verification>
- `python -m pytest tests/test_report_generator.py -p no:cov` PASS
- `python -m pytest -p no:cov` full suite green
- Visual smoke (manual, optional): `python -c "from report_generator import generate_html_report; html = generate_html_report(76561198386265483, 76561198386265483, 'donk').decode(); print('Coach Narrative' in html, 'Interpretation' in html, len(html))"` — first bool depends on whether real ANTHROPIC_API_KEY is set + analytics.db has data; second bool should be True; len should be > 1000.
</verification>

<success_criteria>
- Narrative block inserted between header and interpretation section
- Fail-soft: NarrativeBuildError → tier table only, no exception bubbled to caller
- DEV_FAIL_FAST=1 re-raises unexpected exceptions for dev debugging
- no_narrative=True toggle for SC-6 v1-baseline reports
- Markdown→HTML minimal converter handles v2 prompt shape
- All existing 322+ tests still pass + ≥7 new integration tests
</success_criteria>

<output>
After completion, create `.planning/phases/v2-interpretation-narrative/v2-interpretation-04-SUMMARY.md` documenting:
- Final generate_html_report signature (with no_narrative param)
- Whether _markdown_to_html_minimal needed extension beyond ## header + paragraphs (e.g., bold/italic)
- CSS additions to _css()
- Test count delta
- Behavior with real API key set vs unset (smoke test result if executor ran one)
</output>
