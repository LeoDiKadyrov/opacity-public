"""HTML report generator for Djok reaction analysis reports."""
from __future__ import annotations

import base64
import io
import sqlite3
from contextlib import closing
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import DB_PATH, PLAYER_NAMES
from interpretation import compute_interpretation, get_worst_metric

# ── Design tokens (per 09-UI-SPEC.md D-06) ────────────────────────────────────
_BG = "#0e0e12"
_SECONDARY = "#16161d"
_BORDER = "#2a2a35"
_TEXT = "#e0e0e8"
_MUTED = "#7a7a90"
_ACCENT = "#e8b84b"

_FONT_BODY = "Space Grotesk, Inter, system-ui, sans-serif"
_FONT_MONO = "JetBrains Mono, Consolas, monospace"

_METRIC_LABELS: dict[str, str] = {
    "crosshair_angle_at_t0_deg": "Crosshair angle at T0 (deg)",
    "rt_visible_to_aim_ms": "RT: visible → aim start (ms)",
    "rt_aim_to_hit_ms": "RT: aim start → hit (ms)",
    "rt_visible_to_hit_ms": "RT: visible → hit (ms)",
    "kill_rate": "Kill rate (%)",
    "hit_rate": "Hit rate (%)",
}

_RT_METRICS = {"rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"}

_TIER_BADGE_STYLES: dict[str, str] = {
    "Elite":       f"background:{_SECONDARY};color:#4ecdc4",
    "Good":        f"background:{_SECONDARY};color:{_TEXT}",
    "Average":     f"background:{_SECONDARY};color:{_MUTED}",
    "Work needed": f"background:#1a1408;color:{_ACCENT}",
    "n/a":         f"background:{_SECONDARY};color:{_MUTED}",
}

_RAW_DATA_COL_PRIORITY = [
    "match_id", "engagement_type", "moment_timestamp",
    "rt_visible_to_hit_ms", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms",
    "crosshair_angle_at_t0_deg", "player_velocity_at_t0_ups",
    "enemy_velocity_at_t0_ups",
]

_NUMERIC_COLS = frozenset({
    "match_id", "t0_manual_tick", "t1_aim_start_tick", "t2_first_hit_tick",
    "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
    "player_velocity_at_t0_ups", "enemy_velocity_at_t0_ups",
    "crosshair_angle_at_t0_deg", "player_steamid", "target_enemy_id",
})

# Metrics shown per engagement type — col names are internal, never user input
_CHART_METRICS: dict[str, list[str]] = {
    "peek": [
        "crosshair_angle_at_t0_deg",
        "rt_visible_to_aim_ms",
        "rt_aim_to_hit_ms",
        "rt_visible_to_hit_ms",
    ],
    "hold": [
        "crosshair_angle_at_t0_deg",
        "rt_visible_to_hit_ms",
    ],
}

# Whitelist of columns allowed in chart SQL — guards against accidental injection
_KNOWN_COLS: frozenset[str] = frozenset(
    col for cols in _CHART_METRICS.values() for col in cols
)


# ── Chart helpers ─────────────────────────────────────────────────────────────

def _fig_to_b64(fig: "plt.Figure") -> str:
    """Serialize a matplotlib figure to a base64-encoded PNG string.

    Caller is responsible for calling plt.close(fig) after use.
    """
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=96, bbox_inches="tight")
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


def _chart_for_metric(
    values: list[float],
    metric_label: str,
    engagement_type: str,
    player_mean: Optional[float],
) -> str:
    """Render a histogram for one metric and return a chart container HTML string.

    Returns an HTML div with an inline base64 PNG and caption.
    Returns empty string if values list is empty.
    """
    count = len(values)
    if count == 0:
        return ""

    fig, ax = plt.subplots(figsize=(10, 4))
    fig.patch.set_facecolor(_BG)
    ax.set_facecolor(_SECONDARY)

    ax.hist(values, bins="auto", color=_MUTED, edgecolor=_BORDER)

    if player_mean is not None:
        ax.axvline(player_mean, color=_ACCENT, linewidth=2, label="You")
        ax.legend(
            facecolor=_SECONDARY,
            labelcolor=_TEXT,
            edgecolor=_BORDER,
            framealpha=1,
        )

    ax.grid(True, color=_BORDER, alpha=0.5)
    ax.tick_params(colors=_TEXT)
    ax.xaxis.label.set_color(_TEXT)
    ax.yaxis.label.set_color(_TEXT)
    for spine in ax.spines.values():
        spine.set_edgecolor(_BORDER)

    b64 = _fig_to_b64(fig)
    plt.close(fig)

    caption = f"{metric_label} — {engagement_type} engagements (n={count})"
    return (
        f'<div style="background:{_SECONDARY};border:1px solid {_BORDER};'
        f'border-radius:4px;padding:16px;margin-bottom:16px;">'
        f'<img src="data:image/png;base64,{b64}" style="width:100%;max-width:720px;" />'
        f'<p style="color:{_MUTED};font-size:12px;font-style:italic;">{caption}</p>'
        f"</div>"
    )


def _generate_charts_html(
    player_steamid: int,
    benchmark_steamid: int,
    benchmark_name: str,
    db_path: str,
    interpretation_rows_by_type: Optional[dict[str, list[dict]]] = None,
) -> str:
    """Generate the full Distributions section HTML with base64 charts.

    Queries benchmark player's metric distributions and overlays player's mean.
    Uses cursor.fetchall() — never pd.read_sql — to preserve SteamID64 precision.
    """
    parts: list[str] = []

    with closing(sqlite3.connect(db_path)) as conn:
        for engagement_type, metrics in _CHART_METRICS.items():
            for col in metrics:
                assert col in _KNOWN_COLS, f"Unknown column: {col!r}"  # T-09-05 guard
                metric_label = _METRIC_LABELS.get(col, col)

                # Benchmark distribution
                cursor = conn.execute(
                    f"SELECT {col} FROM engagements"  # col from internal whitelist
                    " WHERE player_steamid = ? AND engagement_type = ?"
                    f" AND {col} IS NOT NULL",
                    (benchmark_steamid, engagement_type),
                )
                values = [row[0] for row in cursor.fetchall()]

                # Player mean from interpretation rows if available
                player_mean: Optional[float] = None
                if interpretation_rows_by_type and engagement_type in interpretation_rows_by_type:
                    for row in interpretation_rows_by_type[engagement_type]:
                        if row.get("metric") == col:
                            player_mean = row.get("player_value")
                            break

                chart_html = _chart_for_metric(values, metric_label, engagement_type, player_mean)
                parts.append(chart_html)

    return "\n".join(p for p in parts if p)


# ── CSS ───────────────────────────────────────────────────────────────────────

def _css() -> str:
    return f"""<style>
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{
    background: {_BG};
    color: {_TEXT};
    font-family: {_FONT_BODY};
    font-size: 14px;
    line-height: 1.5;
    padding: 32px 24px 64px;
    max-width: 1100px;
    margin: 0 auto;
}}
h1 {{
    font-size: 28px;
    font-weight: 700;
    color: {_TEXT};
    margin-bottom: 4px;
}}
.sub-header {{
    font-size: 14px;
    color: {_MUTED};
    margin-bottom: 48px;
    font-family: {_FONT_MONO};
}}
.section {{
    margin-bottom: 48px;
}}
.section-header {{
    font-size: 20px;
    font-weight: 600;
    color: {_TEXT};
    margin-bottom: 24px;
    padding-bottom: 8px;
    border-bottom: 1px solid {_BORDER};
}}
.sub-section-header {{
    font-size: 16px;
    font-weight: 600;
    color: {_TEXT};
    margin: 24px 0 16px;
}}
/* Worst metric card */
.worst-card {{
    border: 1px solid {_ACCENT};
    background: {_SECONDARY};
    border-radius: 4px;
    padding: 16px;
    margin-bottom: 24px;
}}
.worst-card-label {{
    font-size: 12px;
    font-weight: 500;
    color: {_ACCENT};
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 4px;
}}
.worst-card-metric {{
    font-size: 28px;
    font-weight: 700;
    color: {_TEXT};
    line-height: 1.1;
    margin-bottom: 8px;
}}
.worst-card-gap {{
    font-size: 14px;
    color: {_MUTED};
    margin-bottom: 8px;
}}
.worst-card-gap .mono {{ font-family: {_FONT_MONO}; }}
.worst-card-drill {{
    font-size: 14px;
    color: {_TEXT};
    margin-top: 8px;
}}
.menu-intro {{
    font-size: 13px;
    color: {_MUTED};
    margin: 12px 0 6px;
    font-style: italic;
}}
.direction-list {{
    list-style: none;
    padding: 0;
    margin: 0;
}}
.direction-list li {{
    padding: 8px 0 8px 0;
    border-bottom: 1px solid {_BORDER};
    display: flex;
    gap: 10px;
}}
.direction-list li:last-child {{ border-bottom: none; }}
.direction-list .dir-title {{
    color: {_ACCENT};
    font-weight: 600;
    flex: 0 0 140px;
    font-family: {_FONT_MONO};
    font-size: 12px;
}}
.direction-list .dir-body {{
    color: {_TEXT};
    flex: 1;
    font-size: 13px;
}}
.direction-list .dir-drill-badge {{
    display: inline-block;
    background: #1a1408;
    color: {_ACCENT};
    font-size: 10px;
    padding: 1px 6px;
    margin-right: 6px;
    border-radius: 2px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}
.tier-table td.col-direction {{ width: 29%; }}
.tier-table .table-directions {{
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 12px;
}}
.tier-table .table-directions li {{
    padding: 2px 0;
    color: {_MUTED};
}}
.tier-table .table-directions li .t-title {{
    color: {_ACCENT};
    font-weight: 600;
    font-family: {_FONT_MONO};
    margin-right: 6px;
}}
.tier-table .table-directions .t-drill-mark {{
    color: {_ACCENT};
    font-size: 10px;
    margin-left: 4px;
}}
/* Tier table */
.tier-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 32px;
}}
.tier-table th {{
    background: {_BG};
    color: {_MUTED};
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    padding: 8px;
    text-align: left;
}}
.tier-table th:nth-child(2),
.tier-table th:nth-child(3),
.tier-table th:nth-child(4),
.tier-table th:nth-child(5) {{ text-align: right; }}
.tier-table td {{
    padding: 10px 8px;
    border-bottom: 1px solid {_BORDER};
    font-size: 14px;
    vertical-align: middle;
}}
.tier-table tr.odd td {{ background: {_SECONDARY}; }}
.tier-table tr.even td {{ background: {_BG}; }}
.tier-table td.mono {{ font-family: {_FONT_MONO}; text-align: right; }}
.tier-table td.col-metric {{ width: 25%; }}
.tier-table td.col-you {{ width: 10%; }}
.tier-table td.col-tier {{ width: 12%; }}
.tier-table td.col-gap {{ width: 12%; }}
.tier-table td.col-bm {{ width: 12%; }}
.tier-badge {{
    font-size: 12px;
    padding: 4px 8px;
    border-radius: 3px;
    display: inline-block;
    white-space: nowrap;
}}
.caveat-row td {{
    color: {_MUTED};
    font-size: 12px;
    padding: 4px 8px;
    font-style: italic;
}}
/* Charts placeholder */
#charts-section {{
    min-height: 40px;
    background: {_SECONDARY};
    border: 1px solid {_BORDER};
    border-radius: 4px;
    padding: 16px;
    color: {_MUTED};
    font-size: 13px;
}}
/* Raw data table */
.raw-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    overflow-x: auto;
    display: block;
}}
.raw-table th {{
    background: {_BG};
    color: {_MUTED};
    font-size: 12px;
    font-weight: 500;
    text-transform: uppercase;
    padding: 8px;
    text-align: left;
    white-space: nowrap;
}}
.raw-table td {{
    padding: 8px;
    border-bottom: 1px solid {_BORDER};
    white-space: nowrap;
}}
.raw-table tr.odd td {{ background: {_SECONDARY}; }}
.raw-table tr.even td {{ background: {_BG}; }}
.raw-table td.mono {{ font-family: {_FONT_MONO}; }}
.table-caption {{
    font-size: 12px;
    color: {_MUTED};
    margin-bottom: 8px;
}}
</style>"""


# ── Component helpers ─────────────────────────────────────────────────────────

def _tier_badge(tier: str) -> str:
    style = _TIER_BADGE_STYLES.get(tier, _TIER_BADGE_STYLES["n/a"])
    return f'<span class="tier-badge" style="{style}">{tier}</span>'


def _directions_full_html(directions: list[dict]) -> str:
    """Render menu of directions for the worst-metric card (full title + body)."""
    if not directions:
        return ""
    items = []
    for d in directions:
        title = d.get("title", "")
        body = d.get("body", "")
        is_drill = d.get("is_drill", False)
        badge = '<span class="dir-drill-badge">drill</span>' if is_drill else ""
        items.append(
            f'<li><span class="dir-title">{title}</span>'
            f'<span class="dir-body">{badge}{body}</span></li>'
        )
    return (
        '<p class="menu-intro">Three directions. Pick one you will actually do.</p>'
        f'<ul class="direction-list">{"".join(items)}</ul>'
    )


def _directions_compact_html(directions: list[dict]) -> str:
    """Compact direction list for tier-table cell."""
    if not directions:
        return ""
    items = []
    for d in directions:
        title = d.get("title", "")
        body = d.get("body", "")
        mark = '<span class="t-drill-mark">·drill</span>' if d.get("is_drill", False) else ""
        items.append(f'<li><span class="t-title">{title}{mark}</span>{body}</li>')
    return f'<ul class="table-directions">{"".join(items)}</ul>'


def _worst_metric_card_html(worst: Optional[dict], benchmark_name: str) -> str:
    """Render worst metric card or empty string if not applicable."""
    if worst is None:
        return ""
    tier = worst.get("tier")
    if tier in (None, "n/a"):
        return ""
    label = worst.get("label", worst.get("metric", ""))
    gap = worst.get("gap")
    directions = worst.get("directions") or []
    gap_str = f"{gap:+.1f}" if gap is not None else "N/A"
    return f"""<div class="worst-card">
  <div class="worst-card-label">Your biggest opportunity</div>
  <div class="worst-card-metric">{label} {_tier_badge(tier)}</div>
  <div class="worst-card-gap">Gap vs {benchmark_name}: <span class="mono">{gap_str}</span></div>
  {_directions_full_html(directions)}
</div>"""


def _tier_table_html(rows: list[dict], benchmark_name: str) -> str:
    """Render interpretation tier table for a set of metric rows."""
    header = f"""<table class="tier-table">
<thead>
<tr>
  <th class="col-metric">Metric</th>
  <th class="col-you">You</th>
  <th class="col-tier">Tier</th>
  <th class="col-gap">Gap</th>
  <th class="col-bm">vs {benchmark_name}</th>
  <th class="col-direction">Directions (pick one)</th>
</tr>
</thead>
<tbody>"""
    body_rows = []
    row_idx = 0
    for row in rows:
        metric = row.get("metric", "")
        label = row.get("label", metric)
        pval = row.get("player_value")
        tier = row.get("tier", "n/a")
        gap = row.get("gap")
        bm_p50 = row.get("benchmark_p50")
        directions = row.get("directions") or []
        caveat = row.get("caveat")

        pval_str = f"{pval:.1f}" if pval is not None else "—"
        gap_str = f"{gap:+.1f}" if gap is not None else "—"
        bm_str = f"{bm_p50:.1f}" if bm_p50 is not None else "—"

        if tier == "n/a" or not directions:
            direction_cell = f'<span style="color:{_MUTED}">{row.get("drill", "—")}</span>'
        else:
            direction_cell = _directions_compact_html(directions)

        parity = "odd" if row_idx % 2 == 0 else "even"
        body_rows.append(
            f'<tr class="{parity}">'
            f'<td class="col-metric">{label}</td>'
            f'<td class="col-you mono">{pval_str}</td>'
            f'<td class="col-tier">{_tier_badge(tier)}</td>'
            f'<td class="col-gap mono">{gap_str}</td>'
            f'<td class="col-bm mono">{bm_str}</td>'
            f'<td class="col-direction">{direction_cell}</td>'
            f'</tr>'
        )
        row_idx += 1

        if caveat and metric in _RT_METRICS:
            body_rows.append(
                f'<tr class="caveat-row">'
                f'<td colspan="6">{caveat}</td>'
                f'</tr>'
            )

    footer = "</tbody></table>"
    return header + "\n".join(body_rows) + footer


def _raw_data_html(db_path: str, player_steamid: int) -> str:
    """Query engagements for player and render as HTML table.

    Uses cursor.fetchall() — never pd.read_sql — to preserve SteamID64 precision.
    """
    with closing(sqlite3.connect(db_path)) as conn:
        try:
            cursor = conn.execute(
                "SELECT * FROM engagements WHERE player_steamid = ?"
                " ORDER BY match_id, t0_manual_tick",
                (player_steamid,)
            )
            col_names = [d[0] for d in cursor.description]
            db_rows = cursor.fetchall()
        except sqlite3.OperationalError:
            return "<p style='color:#7a7a90'>No engagements table found.</p>"

    if not db_rows:
        return f"<p style='color:{_MUTED}'>No engagement data found for player {player_steamid}.</p>"

    # Determine column order
    priority = [c for c in _RAW_DATA_COL_PRIORITY if c in col_names]
    remaining = [c for c in col_names if c not in _RAW_DATA_COL_PRIORITY]
    ordered_cols = priority + remaining
    col_idx = {c: col_names.index(c) for c in ordered_cols if c in col_names}

    n = len(db_rows)
    caption = f'<p class="table-caption">All analyzed engagements. Sorted by match then tick. Showing all {n} engagements.</p>'

    header_cells = "".join(f"<th>{c}</th>" for c in ordered_cols)
    header = f"<thead><tr>{header_cells}</tr></thead>"

    body_rows = []
    for i, db_row in enumerate(db_rows):
        parity = "odd" if i % 2 == 0 else "even"
        cells = []
        for c in ordered_cols:
            idx = col_idx.get(c)
            val = db_row[idx] if idx is not None else ""
            val_str = str(val) if val is not None else "—"
            mono_class = " mono" if c in _NUMERIC_COLS else ""
            cells.append(f'<td class="{mono_class.strip()}">{val_str}</td>')
        body_rows.append(f'<tr class="{parity}">{"".join(cells)}</tr>')

    table = f'<table class="raw-table">{header}<tbody>{"".join(body_rows)}</tbody></table>'
    return caption + table


def _section(header: str, content: str) -> str:
    """Wrap content in a section div with a header."""
    return f"""<div class="section">
<h2 class="section-header">{header}</h2>
{content}
</div>"""


# ── Main entry point ──────────────────────────────────────────────────────────

def generate_html_report(
    player_steamid: int,
    benchmark_steamid: int,
    benchmark_name: str,
    db_path: str = DB_PATH,
) -> bytes:
    """Generate a self-contained HTML report for a player vs benchmark.

    Returns UTF-8 encoded bytes of a complete HTML document.
    No external URLs are included — all CSS is inline, no CDN, no Google Fonts.
    """
    player_steamid = int(player_steamid)
    benchmark_steamid = int(benchmark_steamid)
    today = date.today().isoformat()
    player_display = PLAYER_NAMES.get(player_steamid, str(player_steamid))

    # ── Interpretation section ─────────────────────────────────────────────────
    interp_parts: list[str] = []
    interp_rows_by_type: dict[str, list[dict]] = {}
    for engagement_type in ["peek", "hold"]:
        sub_label = "Peek engagements" if engagement_type == "peek" else "Hold engagements"
        rows = compute_interpretation(
            db_path=db_path,
            player_steamid=player_steamid,
            benchmark_steamid=benchmark_steamid,
            engagement_type=engagement_type,
        )
        interp_rows_by_type[engagement_type] = rows
        worst = get_worst_metric(rows)
        card_html = _worst_metric_card_html(worst, benchmark_name)
        table_html = _tier_table_html(rows, benchmark_name)
        interp_parts.append(
            f'<h3 class="sub-section-header">{sub_label}</h3>'
            + card_html
            + table_html
        )

    interp_content = "\n".join(interp_parts)
    interpretation_section = _section("Interpretation", interp_content)

    # ── Distributions section ──────────────────────────────────────────────────
    charts_html = _generate_charts_html(
        player_steamid=player_steamid,
        benchmark_steamid=benchmark_steamid,
        benchmark_name=benchmark_name,
        db_path=db_path,
        interpretation_rows_by_type=interp_rows_by_type,
    )
    distributions_section = _section("Distributions", charts_html or "<p style='color:#7a7a90'>No distribution data available.</p>")

    # ── Raw data section ───────────────────────────────────────────────────────
    raw_html = _raw_data_html(db_path, player_steamid)
    raw_section = _section("Raw Data", raw_html)

    # ── Assemble ───────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Djok Report — {player_steamid}</title>
{_css()}
</head>
<body>
<h1>Djok Reaction Report</h1>
<div class="sub-header">{player_steamid} vs {benchmark_name} · Generated {today}</div>
{interpretation_section}
{distributions_section}
{raw_section}
</body>
</html>"""

    return html.encode("utf-8")
