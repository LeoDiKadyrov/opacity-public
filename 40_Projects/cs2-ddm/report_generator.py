"""HTML report generator for Djok reaction analysis reports.

CS 1.6 aesthetic (ekmas/cs16.css palette) + EN/RU localization.
All assets inline — no external URLs (incl. fonts via data:base64).
"""
from __future__ import annotations

import base64
import io
import os
import sqlite3
from contextlib import closing
from datetime import date
from typing import Optional

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from config import DB_PATH, PLAYER_NAMES
from interpretation import compute_interpretation, get_worst_metric

# ── CS 1.6 design tokens (ekmas/cs16.css palette pinned) ──────────────────────
_BG = "#4a5942"            # olive — body bg
_SECONDARY = "#3e4637"     # darker olive — card bg
_BORDER = "#292c21"        # dark — borders / shadows
_BEVEL_LIGHT = "#8c9284"   # light grey-olive — bevel top/left
_BEVEL_DARK = "#292c21"    # = BORDER — bevel bottom/right
_TEXT = "#dedfd6"          # cream — body text
_MUTED = "#a0aa95"         # muted greyish — captions
_ACCENT = "#c4b550"        # olive-yellow — accents/links/headers
_ACCENT2 = "#958831"       # darker yellow — Work-needed tier

_FONT_BODY = "'ArialPixel', Consolas, 'Courier New', monospace"
_FONT_MONO = "'ArialPixel', Consolas, 'Courier New', monospace"

# ── Load ArialPixel font as base64 from sibling assets file ──────────────────
_FONT_B64_PATH = os.path.join(os.path.dirname(__file__), "assets", "arialpixel_b64.txt")
try:
    with open(_FONT_B64_PATH, encoding="ascii") as _f:
        _FONT_B64 = _f.read().strip()
except FileNotFoundError:
    _FONT_B64 = ""  # fallback to system monospace — no @font-face emitted


# ── Localization ──────────────────────────────────────────────────────────────
_METRIC_LABELS_EN: dict[str, str] = {
    "crosshair_angle_at_t0_deg": "Crosshair angle at T0 (deg)",
    "rt_visible_to_aim_ms": "RT: visible → aim start (ms)",
    "rt_aim_to_hit_ms": "RT: aim start → hit (ms)",
    "rt_visible_to_hit_ms": "RT: visible → hit (ms)",
    "kill_rate": "Kill rate (%)",
    "hit_rate": "Hit rate (%)",
}
_METRIC_LABELS_RU: dict[str, str] = {
    "crosshair_angle_at_t0_deg": "Угол прицела на T0 (°)",
    "rt_visible_to_aim_ms": "RT: виден → начал наводиться (мс)",
    "rt_aim_to_hit_ms": "RT: начал наводиться → попал (мс)",
    "rt_visible_to_hit_ms": "RT: виден → попал (мс)",
    "kill_rate": "Kill rate (%)",
    "hit_rate": "Hit rate (%)",
}
# Backwards-compat alias for any external caller / test referencing _METRIC_LABELS
_METRIC_LABELS = _METRIC_LABELS_EN

_TIER_LABELS: dict[str, dict[str, str]] = {
    "en": {"Elite": "Elite", "Good": "Good", "Average": "Average",
           "Work needed": "Work needed", "n/a": "n/a"},
    "ru": {"Elite": "Elite", "Good": "Хорошо", "Average": "Средне",
           "Work needed": "Нужна работа", "n/a": "n/a"},
}

# UI strings keyed by language
_STR: dict[str, dict[str, str]] = {
    "en": {
        "report_title":         "Djok Reaction Report",
        "interpretation":       "Interpretation",
        "distributions":        "Distributions",
        "raw_data":             "Raw Data",
        "peek_engagements":     "Peek engagements",
        "hold_engagements":     "Hold engagements",
        "biggest_opportunity":  "Your biggest opportunity",
        "gap_vs":               "Gap vs",
        "three_directions":     "Three directions. Pick one you will actually do.",
        "drill_badge":          "drill",
        "drill_mark":           "·drill",
        "th_metric":            "Metric",
        "th_you":               "You",
        "th_tier":              "Tier",
        "th_gap":               "Gap",
        "th_vs":                "vs",
        "th_directions":        "Directions (pick one)",
        "no_table":             "No engagements table found.",
        "no_player_data":       "No engagement data found for player",
        "no_distributions":     "No distribution data available.",
        "all_engagements_pre":  "All analyzed engagements. Sorted by match then tick. Showing all",
        "all_engagements_suf":  "engagements.",
        "generated":            "Generated",
    },
    "ru": {
        "report_title":         "Отчёт Djok по реакции",
        "interpretation":       "Интерпретация",
        "distributions":        "Распределения",
        "raw_data":             "Raw данные",
        "peek_engagements":     "Дуэли на пике",
        "hold_engagements":     "Дуэли на холде",
        "biggest_opportunity":  "Главная зона роста",
        "gap_vs":               "Разрыв с",
        "three_directions":     "Три направления. Выбери одно которое реально будешь делать.",
        "drill_badge":          "drill",
        "drill_mark":           "·drill",
        "th_metric":            "Метрика",
        "th_you":               "Ты",
        "th_tier":              "Тир",
        "th_gap":               "Разрыв",
        "th_vs":                "vs",
        "th_directions":        "Направления (выбери одно)",
        "no_table":             "Таблица engagements не найдена.",
        "no_player_data":       "Нет данных для игрока",
        "no_distributions":     "Нет данных для распределений.",
        "all_engagements_pre":  "Все проанализированные дуэли. Сортировка по матчу и тику. Показано",
        "all_engagements_suf":  "дуэлей.",
        "generated":            "Сгенерирован",
    },
}


def _t(key: str, lang: str = "en") -> str:
    """Lookup UI string by key + language with EN fallback."""
    return _STR.get(lang, _STR["en"]).get(key, _STR["en"].get(key, key))


def _metric_label(col: str, lang: str = "en") -> str:
    table = _METRIC_LABELS_RU if lang == "ru" else _METRIC_LABELS_EN
    return table.get(col, col)


def _tier_label(tier: str, lang: str = "en") -> str:
    return _TIER_LABELS.get(lang, _TIER_LABELS["en"]).get(tier, tier)


_RT_METRICS = {"rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"}

# Tier badge inline-style: color differentiation only; bevel border in CSS class.
# Backwards-compat — module still exposes _TIER_BADGE_STYLES for any callers.
_TIER_BADGE_STYLES: dict[str, str] = {
    "Elite":       f"color:{_ACCENT}",     # bright accent yellow
    "Good":        f"color:{_TEXT}",       # cream
    "Average":     f"color:{_MUTED}",      # muted
    "Work needed": f"color:{_ACCENT2}",    # darker yellow — distinct from Elite
    "n/a":         f"color:{_MUTED}",
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
    "round_time_s",
})

# CS2 round timer counts down from 1:55 (115s gameplay after freeze_end).
# Post-plant: bomb timer adds ~40s. round_time_s in DB = seconds since
# round_freeze_end (gameplay-start anchor, see ddm_analyzer fix 2026-05-14).
_CS2_ROUND_DURATION_S = 115


def _format_round_time(seconds) -> str:
    """Format gameplay-elapsed seconds as in-game countdown timer (M:SS).

    >115s = post-plant; show as "+Ns post" since we lack the plant_tick to
    recover an exact bomb-timer reading.
    """
    if seconds is None:
        return "—"
    try:
        s = float(seconds)
    except (TypeError, ValueError):
        return "—"
    if s < 0:
        return f"{s:.1f}s"
    if s <= _CS2_ROUND_DURATION_S:
        remaining = _CS2_ROUND_DURATION_S - s
        m = int(remaining // 60)
        ss = int(remaining % 60)
        return f"{m}:{ss:02d}"
    return f"+{int(s - _CS2_ROUND_DURATION_S)}s post"

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
    lang: str = "en",
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
                metric_label = _metric_label(col, lang)

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
    # @font-face only emitted if base64 successfully loaded — otherwise system mono fallback
    font_face = (
        f"@font-face {{ font-family:'ArialPixel'; font-style:normal; font-weight:400;"
        f" src: url(data:font/ttf;base64,{_FONT_B64}) format('truetype'); font-display:swap; }}"
        if _FONT_B64 else ""
    )
    return f"""<style>
{font_face}
* {{ box-sizing: border-box; margin: 0; padding: 0; font-family: {_FONT_BODY}; }}
body {{
    background: {_BG};
    color: {_TEXT};
    font-family: {_FONT_BODY};
    font-size: 15px;
    line-height: 1.5;
    padding: 32px 24px 64px;
    max-width: 1100px;
    margin: 0 auto;
}}
h1 {{
    font-size: 28px;
    font-weight: 400;
    color: {_ACCENT};
    text-transform: uppercase;
    margin-bottom: 4px;
    letter-spacing: 0;
}}
.sub-header {{
    font-size: 14px;
    color: {_MUTED};
    margin-bottom: 48px;
}}
.section {{ margin-bottom: 48px; }}
.section-header {{
    font-size: 20px;
    font-weight: 400;
    color: {_ACCENT};
    text-transform: uppercase;
    margin-bottom: 24px;
    padding-bottom: 8px;
    border-bottom: 1px solid {_BORDER};
}}
.sub-section-header {{
    font-size: 16px;
    font-weight: 400;
    color: {_ACCENT};
    text-transform: uppercase;
    margin: 24px 0 16px;
}}
/* CS 1.6 bevel — 4-side border, no radius */
.worst-card {{
    background: {_SECONDARY};
    border-top: 2px solid {_BEVEL_LIGHT};
    border-left: 2px solid {_BEVEL_LIGHT};
    border-right: 2px solid {_BEVEL_DARK};
    border-bottom: 2px solid {_BEVEL_DARK};
    border-radius: 0;
    padding: 16px 18px;
    margin-bottom: 24px;
}}
.worst-card-label {{
    font-size: 13px;
    color: {_ACCENT};
    text-transform: uppercase;
    letter-spacing: 0.05em;
    margin-bottom: 6px;
}}
.worst-card-metric {{
    font-size: 26px;
    font-weight: 400;
    color: {_TEXT};
    line-height: 1.1;
    margin-bottom: 8px;
}}
.worst-card-gap {{
    font-size: 14px;
    color: {_MUTED};
    margin-bottom: 8px;
}}
.worst-card-gap .mono {{ color: {_ACCENT}; }}
.worst-card-drill {{
    font-size: 14px;
    color: {_TEXT};
    margin-top: 8px;
}}
.menu-intro {{
    font-size: 14px;
    color: {_MUTED};
    margin: 12px 0 6px;
}}
.direction-list {{
    list-style: none;
    padding: 0;
    margin: 0;
}}
.direction-list li {{
    padding: 8px 0;
    border-bottom: 1px solid {_BORDER};
    display: flex;
    gap: 10px;
}}
.direction-list li:last-child {{ border-bottom: none; }}
.direction-list .dir-title {{
    color: {_ACCENT};
    font-weight: 400;
    flex: 0 0 150px;
    font-size: 13px;
    text-transform: uppercase;
}}
.direction-list .dir-body {{
    color: {_TEXT};
    flex: 1;
    font-size: 14px;
}}
.direction-list .dir-drill-badge {{
    display: inline-block;
    background: {_BORDER};
    color: {_ACCENT};
    font-size: 11px;
    padding: 1px 6px;
    margin-right: 6px;
    border-radius: 0;
    text-transform: uppercase;
}}
.tier-table td.col-direction {{ width: 29%; }}
.tier-table .table-directions {{
    list-style: none;
    padding: 0;
    margin: 0;
    font-size: 13px;
}}
.tier-table .table-directions li {{
    padding: 2px 0;
    color: {_MUTED};
}}
.tier-table .table-directions li .t-title {{
    color: {_ACCENT};
    font-weight: 400;
    margin-right: 6px;
    text-transform: uppercase;
}}
.tier-table .table-directions .t-drill-mark {{
    color: {_ACCENT};
    font-size: 11px;
    margin-left: 4px;
}}
/* Tier table — CS console panel */
.tier-table {{
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 32px;
    background: {_SECONDARY};
    border-top: 2px solid {_BEVEL_LIGHT};
    border-left: 2px solid {_BEVEL_LIGHT};
    border-right: 2px solid {_BEVEL_DARK};
    border-bottom: 2px solid {_BEVEL_DARK};
}}
.tier-table th {{
    background: {_BORDER};
    color: {_ACCENT};
    font-size: 13px;
    font-weight: 400;
    text-transform: uppercase;
    padding: 8px;
    text-align: left;
    letter-spacing: 0.03em;
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
    color: {_TEXT};
}}
.tier-table tr.odd td {{ background: {_SECONDARY}; }}
.tier-table tr.even td {{ background: {_BG}; }}
.tier-table td.mono {{ text-align: right; color: {_ACCENT}; }}
.tier-table td.col-metric {{ width: 25%; color: {_TEXT}; }}
.tier-table td.col-you {{ width: 10%; }}
.tier-table td.col-tier {{ width: 12%; }}
.tier-table td.col-gap {{ width: 12%; }}
.tier-table td.col-bm {{ width: 12%; }}
.tier-badge {{
    font-size: 12px;
    padding: 3px 8px;
    border-radius: 0;
    display: inline-block;
    white-space: nowrap;
    background: {_SECONDARY};
    border-top: 1px solid {_BEVEL_LIGHT};
    border-left: 1px solid {_BEVEL_LIGHT};
    border-right: 1px solid {_BEVEL_DARK};
    border-bottom: 1px solid {_BEVEL_DARK};
    text-transform: uppercase;
    letter-spacing: 0.03em;
}}
.caveat-row td {{
    color: {_MUTED};
    font-size: 12px;
    padding: 4px 8px;
    background: {_SECONDARY};
}}
/* Charts placeholder */
#charts-section {{
    min-height: 40px;
    background: {_SECONDARY};
    border-top: 2px solid {_BEVEL_LIGHT};
    border-left: 2px solid {_BEVEL_LIGHT};
    border-right: 2px solid {_BEVEL_DARK};
    border-bottom: 2px solid {_BEVEL_DARK};
    border-radius: 0;
    padding: 16px;
    color: {_MUTED};
    font-size: 14px;
}}
/* Raw data table */
.raw-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
    overflow-x: auto;
    display: block;
    background: {_SECONDARY};
    border-top: 2px solid {_BEVEL_LIGHT};
    border-left: 2px solid {_BEVEL_LIGHT};
    border-right: 2px solid {_BEVEL_DARK};
    border-bottom: 2px solid {_BEVEL_DARK};
}}
.raw-table th {{
    background: {_BORDER};
    color: {_ACCENT};
    font-size: 12px;
    font-weight: 400;
    text-transform: uppercase;
    padding: 8px;
    text-align: left;
    white-space: nowrap;
}}
.raw-table td {{
    padding: 8px;
    border-bottom: 1px solid {_BORDER};
    white-space: nowrap;
    color: {_TEXT};
}}
.raw-table tr.odd td {{ background: {_SECONDARY}; }}
.raw-table tr.even td {{ background: {_BG}; }}
.raw-table td.mono {{ color: {_ACCENT}; }}
.table-caption {{
    font-size: 13px;
    color: {_MUTED};
    margin-bottom: 8px;
}}
</style>"""


# ── Component helpers ─────────────────────────────────────────────────────────

def _tier_badge(tier: str, lang: str = "en") -> str:
    style = _TIER_BADGE_STYLES.get(tier, _TIER_BADGE_STYLES["n/a"])
    return f'<span class="tier-badge" style="{style}">{_tier_label(tier, lang)}</span>'


def _directions_full_html(directions: list[dict], lang: str = "en") -> str:
    """Render menu of directions for the worst-metric card (full title + body)."""
    if not directions:
        return ""
    items = []
    for d in directions:
        title = d.get("title", "")
        body = d.get("body", "")
        is_drill = d.get("is_drill", False)
        badge = f'<span class="dir-drill-badge">{_t("drill_badge", lang)}</span>' if is_drill else ""
        items.append(
            f'<li><span class="dir-title">{title}</span>'
            f'<span class="dir-body">{badge}{body}</span></li>'
        )
    return (
        f'<p class="menu-intro">{_t("three_directions", lang)}</p>'
        f'<ul class="direction-list">{"".join(items)}</ul>'
    )


def _directions_compact_html(directions: list[dict], lang: str = "en") -> str:
    """Compact direction list for tier-table cell."""
    if not directions:
        return ""
    items = []
    for d in directions:
        title = d.get("title", "")
        body = d.get("body", "")
        mark = f'<span class="t-drill-mark">{_t("drill_mark", lang)}</span>' if d.get("is_drill", False) else ""
        items.append(f'<li><span class="t-title">{title}{mark}</span>{body}</li>')
    return f'<ul class="table-directions">{"".join(items)}</ul>'


def _worst_metric_card_html(worst: Optional[dict], benchmark_name: str, lang: str = "en") -> str:
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
  <div class="worst-card-label">{_t("biggest_opportunity", lang)}</div>
  <div class="worst-card-metric">{label} {_tier_badge(tier, lang)}</div>
  <div class="worst-card-gap">{_t("gap_vs", lang)} {benchmark_name}: <span class="mono">{gap_str}</span></div>
  {_directions_full_html(directions, lang)}
</div>"""


def _tier_table_html(rows: list[dict], benchmark_name: str, lang: str = "en") -> str:
    """Render interpretation tier table for a set of metric rows."""
    header = f"""<table class="tier-table">
<thead>
<tr>
  <th class="col-metric">{_t("th_metric", lang)}</th>
  <th class="col-you">{_t("th_you", lang)}</th>
  <th class="col-tier">{_t("th_tier", lang)}</th>
  <th class="col-gap">{_t("th_gap", lang)}</th>
  <th class="col-bm">{_t("th_vs", lang)} {benchmark_name}</th>
  <th class="col-direction">{_t("th_directions", lang)}</th>
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
            direction_cell = _directions_compact_html(directions, lang)

        parity = "odd" if row_idx % 2 == 0 else "even"
        body_rows.append(
            f'<tr class="{parity}">'
            f'<td class="col-metric">{label}</td>'
            f'<td class="col-you mono">{pval_str}</td>'
            f'<td class="col-tier">{_tier_badge(tier, lang)}</td>'
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


def _raw_data_html(db_path: str, player_steamid: int, lang: str = "en") -> str:
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
            return f"<p style='color:{_MUTED}'>{_t('no_table', lang)}</p>"

    if not db_rows:
        return f"<p style='color:{_MUTED}'>{_t('no_player_data', lang)} {player_steamid}.</p>"

    # Determine column order
    priority = [c for c in _RAW_DATA_COL_PRIORITY if c in col_names]
    remaining = [c for c in col_names if c not in _RAW_DATA_COL_PRIORITY]
    ordered_cols = priority + remaining
    col_idx = {c: col_names.index(c) for c in ordered_cols if c in col_names}

    n = len(db_rows)
    caption = (
        f'<p class="table-caption">{_t("all_engagements_pre", lang)} '
        f'{n} {_t("all_engagements_suf", lang)}</p>'
    )

    header_cells = "".join(f"<th>{c}</th>" for c in ordered_cols)
    header = f"<thead><tr>{header_cells}</tr></thead>"

    body_rows = []
    for i, db_row in enumerate(db_rows):
        parity = "odd" if i % 2 == 0 else "even"
        cells = []
        for c in ordered_cols:
            idx = col_idx.get(c)
            val = db_row[idx] if idx is not None else ""
            if c == "round_time_s":
                val_str = _format_round_time(val)
            else:
                val_str = str(val) if val is not None else "—"
            mono_class = " mono" if c in _NUMERIC_COLS else ""
            cells.append(f'<td class="{mono_class.strip()}">{val_str}</td>')
        body_rows.append(f'<tr class="{parity}">{"".join(cells)}</tr>')

    table = f'<table class="raw-table">{header}<tbody>{"".join(body_rows)}</tbody></table>'
    return caption + table


def _section(header: str, content: str) -> str:
    """Wrap content in a section div with a header (header pre-localized by caller)."""
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
    lang: str = "en",
) -> bytes:
    """Generate a self-contained HTML report for a player vs benchmark.

    Args:
        lang: "en" (default) or "ru" — controls user-facing UI strings.
              All CS jargon kept in original form per
              reference_cs_ru_jargon_convention (DM, KovaaK's, T0/T1/T2 etc).

    Returns UTF-8 encoded bytes of a complete HTML document.
    No external URLs are included — all CSS + font are inline.
    """
    player_steamid = int(player_steamid)
    benchmark_steamid = int(benchmark_steamid)
    today = date.today().isoformat()
    if lang not in ("en", "ru"):
        lang = "en"
    player_display = PLAYER_NAMES.get(player_steamid, str(player_steamid))

    # ── Interpretation section ─────────────────────────────────────────────────
    interp_parts: list[str] = []
    interp_rows_by_type: dict[str, list[dict]] = {}
    for engagement_type in ["peek", "hold"]:
        sub_key = "peek_engagements" if engagement_type == "peek" else "hold_engagements"
        sub_label = _t(sub_key, lang)
        rows = compute_interpretation(
            db_path=db_path,
            player_steamid=player_steamid,
            benchmark_steamid=benchmark_steamid,
            engagement_type=engagement_type,
        )
        interp_rows_by_type[engagement_type] = rows
        worst = get_worst_metric(rows)
        card_html = _worst_metric_card_html(worst, benchmark_name, lang)
        table_html = _tier_table_html(rows, benchmark_name, lang)
        interp_parts.append(
            f'<h3 class="sub-section-header">{sub_label}</h3>'
            + card_html
            + table_html
        )

    interp_content = "\n".join(interp_parts)
    interpretation_section = _section(_t("interpretation", lang), interp_content)

    # ── Distributions section ──────────────────────────────────────────────────
    charts_html = _generate_charts_html(
        player_steamid=player_steamid,
        benchmark_steamid=benchmark_steamid,
        benchmark_name=benchmark_name,
        db_path=db_path,
        interpretation_rows_by_type=interp_rows_by_type,
        lang=lang,
    )
    distributions_section = _section(
        _t("distributions", lang),
        charts_html or f"<p style='color:{_MUTED}'>{_t('no_distributions', lang)}</p>",
    )

    # ── Raw data section ───────────────────────────────────────────────────────
    raw_html = _raw_data_html(db_path, player_steamid, lang)
    raw_section = _section(_t("raw_data", lang), raw_html)

    # ── Assemble ───────────────────────────────────────────────────────────────
    html = f"""<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Djok Report — {player_steamid}</title>
{_css()}
</head>
<body>
<h1>{_t("report_title", lang)}</h1>
<div class="sub-header">{player_steamid} vs {benchmark_name} · {_t("generated", lang)} {today}</div>
{interpretation_section}
{distributions_section}
{raw_section}
</body>
</html>"""

    return html.encode("utf-8")
