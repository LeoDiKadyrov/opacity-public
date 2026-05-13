#!/usr/bin/env python3
"""
obsidian_writer.py
Exports cs2-ddm analysis results to Obsidian Evergreen notes.

Usage (from run_analysis.py):
    from obsidian_writer import write_analysis_note
    write_analysis_note(results_df, demo_name="donk_mirage_123")
"""

from datetime import date
from pathlib import Path

VAULT_EVERGREEN = Path(r"D:\Obsidian\opacity\20_Evergreen")


def _format_metrics(df) -> str:
    lines = []
    if df is None or len(df) == 0:
        return "_No data_"

    metric_cols = [
        ("rt_t0_t1_ms", "T0→T1 (aim start)"),
        ("rt_t1_t2_ms", "T1→T2 (first hit)"),
        ("rt_t0_t2_ms", "T0→T2 (total)"),
        ("crosshair_angle_at_t0_deg", "Crosshair angle at T0"),
    ]

    available = [(col, label) for col, label in metric_cols if col in df.columns]
    if not available:
        return "_Metric columns not found in data_"

    lines.append("| Метрика | Mean | Median | Std |")
    lines.append("|-|-|-|-|")
    for col, label in available:
        series = df[col].dropna()
        if series.empty:
            continue
        lines.append(
            f"| {label} | {series.mean():.1f}ms | {series.median():.1f}ms | {series.std():.1f}ms |"
        )

    return "\n".join(lines)


def _kill_rate_section(df) -> str:
    if df is None or "kill_rate" not in df.columns:
        return ""
    kr = df["kill_rate"].dropna()
    if len(kr) == 0:
        return ""
    return f"\n**Kill Rate:** {kr.mean():.1%} mean ({len(kr)} duels)\n"


def write_analysis_note(
    df,
    demo_name: str,
    player_name: str = "",
    notes: str = "",
) -> Path:
    """
    Write analysis results as Evergreen note to Obsidian.

    Args:
        df: Analysis results DataFrame (from run_analysis.py output)
        demo_name: Demo identifier (e.g. 'donk_mirage_123')
        player_name: Optional player name for note title
        notes: Optional freeform notes to include

    Returns:
        Path to created/updated note
    """
    today = date.today().isoformat()
    slug = demo_name.lower().replace(" ", "-").replace("_", "-")
    output_file = VAULT_EVERGREEN / f"cs2-analysis-{slug}.md"

    player_str = f" — {player_name}" if player_name else ""
    sample_size = len(df) if df is not None else 0

    metrics_md = _format_metrics(df)
    kill_rate_md = _kill_rate_section(df)

    content = f"""---
type: вечнозеленая
tags: [cs2, ddm, analysis, {slug}]
updated: {today}
created: {today}
demo: {demo_name}
sample_size: {sample_size}
---

# CS2 Analysis: {demo_name}{player_str}

Один атомарный вывод: [заполни после анализа — главное, что выяснил про этот демо/игрока]

## Метрики

{metrics_md}
{kill_rate_md}
## Контекст

- Demo: `{demo_name}`
- Sample: {sample_size} моментов
- Дата: {today}

## Связанные идеи

- [[cs2-ddm dashboard]]
- [[Kill Rate vs Reaction Time]]

"""

    if notes:
        content += f"## Заметки\n\n{notes}\n"

    VAULT_EVERGREEN.mkdir(parents=True, exist_ok=True)
    output_file.write_text(content, encoding="utf-8")
    print(f"[obsidian_writer] Written: {output_file}")
    return output_file
