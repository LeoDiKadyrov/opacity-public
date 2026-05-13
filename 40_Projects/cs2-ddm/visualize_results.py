import os
from typing import Optional

import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import seaborn as sns

from config import VELOCITY_PEEK_THRESHOLD_UPS

# ── Color palette ─────────────────────────────────────────────────────────────

_PALETTE = {
    "peek":  "#2ecc71",
    "hold":  "#e74c3c",
    "early": "#3498db",
    "mid":   "#f39c12",
    "late":  "#e74c3c",
}
_PEEK_DIST_COLORS = ("#3498db", "#e67e22", "#2ecc71")   # T0→T1, T1→T2, T0→T2
_HOLD_DIST_COLORS = ("#9b59b6", "#e74c3c", "#1abc9c")
_PEEK_BAR_COLORS  = ("#5dade2", "#f5b041")
_HOLD_BAR_COLORS  = ("#8e44ad", "#c0392b")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _load_df(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    numeric = [
        "t0_manual_tick", "t1_aim_start_tick", "t2_first_hit_tick",
        "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
        "player_velocity_at_t0_ups",
    ]
    for col in numeric:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _peek_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return only peek-classified rows, or all rows if engagement_type absent."""
    if "engagement_type" in df.columns:
        return df[df["engagement_type"] == "peek"].copy()
    return df.copy()


def _hold_df(df: pd.DataFrame) -> pd.DataFrame:
    """Return only hold-classified rows."""
    if "engagement_type" in df.columns:
        return df[df["engagement_type"] == "hold"].copy()
    return pd.DataFrame(columns=df.columns)


# ── Chart functions (each returns a Figure for Streamlit / saves for CLI) ─────

def plot_velocity_scatter(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Scatter: player velocity @ T0 vs T0→T2 reaction time, colored by engagement type."""
    if "player_velocity_at_t0_ups" not in df.columns:
        return None
    plot_df = df.dropna(subset=["player_velocity_at_t0_ups", "rt_visible_to_hit_ms"])
    if plot_df.empty:
        return None

    hue_col = "engagement_type" if "engagement_type" in plot_df.columns else None
    palette = {"peek": _PALETTE["peek"], "hold": _PALETTE["hold"]} if hue_col else None

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.scatterplot(
        data=plot_df,
        x="player_velocity_at_t0_ups",
        y="rt_visible_to_hit_ms",
        hue=hue_col,
        palette=palette,
        alpha=0.75,
        s=80,
        ax=ax,
    )
    ax.axvline(x=VELOCITY_PEEK_THRESHOLD_UPS, color="gray", linestyle="--", linewidth=1,
               label=f"Peek threshold ({VELOCITY_PEEK_THRESHOLD_UPS} u/s)")
    ax.set_xlabel("Player XY velocity at T0 (units/sec)")
    ax.set_ylabel("T0→T2 reaction time (ms)")
    ax.set_title("Velocity at T0 vs Reaction Time — peek vs hold classification")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(500))
    ax.set_ylim(bottom=0)
    ax.legend()
    fig.tight_layout()
    return fig


def _plot_distributions(
    engagement_df: pd.DataFrame,
    title: str,
    colors: tuple,
) -> Optional[matplotlib.figure.Figure]:
    """Shared histogram + KDE of T0→T1, T1→T2, T0→T2 for a filtered engagement set."""
    data_df = engagement_df.dropna(subset=["rt_visible_to_hit_ms"])
    if data_df.empty:
        return None

    n = len(data_df)
    fig, axes = plt.subplots(1, 3, figsize=(16, 5))
    fig.suptitle(f"{title} (n={n})", fontsize=14)

    cols = [
        ("rt_visible_to_aim_ms",  "T0→T1  Visible to Aim",  colors[0]),
        ("rt_aim_to_hit_ms",      "T1→T2  Aim to Hit",      colors[1]),
        ("rt_visible_to_hit_ms",  "T0→T2  Visible to Hit",  colors[2]),
    ]
    for ax, (col, col_title, color) in zip(axes, cols):
        data = data_df[col].dropna()
        if data.empty:
            ax.set_visible(False)
            continue
        sns.histplot(data, bins=12, kde=True, ax=ax, color=color)
        ax.axvline(data.median(), color="black", linestyle="--", linewidth=1.2,
                   label=f"median {data.median():.0f}ms")
        ax.set_title(col_title)
        ax.set_xlabel("ms")
        ax.legend(fontsize=9)

    fig.tight_layout(rect=[0, 0, 1, 0.95])
    return fig


def plot_peek_distributions(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Histogram + KDE of T0→T1, T1→T2, T0→T2 for peek engagements only."""
    return _plot_distributions(
        _peek_df(df),
        "Reaction Time Distributions — Peek Engagements Only",
        _PEEK_DIST_COLORS,
    )


def plot_peek_vs_hold_boxplot(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Side-by-side boxplot of T0→T2 for peek vs hold."""
    if "engagement_type" not in df.columns:
        return None
    plot_df = df.dropna(subset=["rt_visible_to_hit_ms"])
    if plot_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(8, 6))
    sns.boxplot(
        data=plot_df,
        x="engagement_type",
        y="rt_visible_to_hit_ms",
        hue="engagement_type",
        order=["peek", "hold"],
        palette={"peek": _PALETTE["peek"], "hold": _PALETTE["hold"]},
        legend=False,
        ax=ax,
    )
    counts = plot_df.groupby("engagement_type").size().to_dict()
    labels = [f"{t}\n(n={counts.get(t, 0)})" for t in ["peek", "hold"]]
    ax.set_xticks([0, 1])
    ax.set_xticklabels(labels)
    ax.set_ylabel("T0→T2 reaction time (ms)")
    ax.set_title("Peek vs Hold — T0→T2 distribution")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(500))
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


def plot_summary_boxplots(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Comparison boxplots per match (peek engagements only)."""
    peek = _peek_df(df).dropna(subset=["rt_visible_to_aim_ms", "rt_aim_to_hit_ms"])
    if peek.empty:
        return None

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 8))
    fig.suptitle("Reaction Metrics Across Matches (Peek Only)", fontsize=16)

    sns.boxplot(x="match_id", y="rt_visible_to_aim_ms", data=peek, ax=ax1)
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    ax1.set_title("Perception & Decision Time (T0→T1)")
    ax1.set_xlabel("")
    ax1.set_ylabel("ms")
    ax1.yaxis.set_major_locator(ticker.MultipleLocator(500))
    ax1.set_ylim(bottom=0)

    sns.boxplot(x="match_id", y="rt_aim_to_hit_ms", data=peek, ax=ax2)
    ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    ax2.set_title("Aiming & Execution Time (T1→T2)")
    ax2.set_xlabel("")
    ax2.set_ylabel("ms")
    ax2.yaxis.set_major_locator(ticker.MultipleLocator(500))
    ax2.set_ylim(bottom=0)

    fig.tight_layout(rect=[0, 0.05, 1, 0.95])
    return fig


def _bar_labels(df: pd.DataFrame) -> pd.Series:
    """Combine moment_timestamp with round_phase if available, e.g. '2:51, early'."""
    if "round_phase" in df.columns:
        return df.apply(
            lambda r: f"{r['moment_timestamp']}, {r['round_phase']}"
            if pd.notna(r.get("round_phase")) else str(r["moment_timestamp"]),
            axis=1,
        )
    return df["moment_timestamp"].astype(str)


def _plot_stacked_bars_impl(
    engagement_df: pd.DataFrame,
    match_id,
    bar_colors: tuple,
    title: str,
) -> Optional[matplotlib.figure.Figure]:
    """Shared stacked-bar implementation for a filtered engagement set."""
    if engagement_df.empty:
        return None

    labels = _bar_labels(engagement_df)
    has_angle = (
        "crosshair_angle_at_t0_deg" in engagement_df.columns
        and engagement_df["crosshair_angle_at_t0_deg"].notna().any()
    )

    fig, ax = plt.subplots(figsize=(15, 8))
    ax.bar(labels, engagement_df["rt_visible_to_aim_ms"].fillna(0),
           label="T0→T1 (Visible→Aim)", color=bar_colors[0])
    ax.bar(labels, engagement_df["rt_aim_to_hit_ms"].fillna(0),
           bottom=engagement_df["rt_visible_to_aim_ms"].fillna(0),
           label="T1→T2 (Aim→Hit)", color=bar_colors[1])
    ax.tick_params(axis="x", rotation=45)
    ax.set_ylabel("ms")
    ax.set_title(title)

    if has_angle:
        angle_vals = engagement_df["crosshair_angle_at_t0_deg"].values
        ax2 = ax.twinx()
        x_pos = range(len(labels))
        ax2.scatter(x_pos, angle_vals, color="#e74c3c", marker="D",
                    s=70, zorder=5, label="Crosshair angle (°)")
        ax2.set_ylabel("Crosshair angle at T0 (°)", color="#e74c3c")
        ax2.tick_params(axis="y", labelcolor="#e74c3c")
        max_angle = np.nanmax(angle_vals)
        ax2.set_ylim(0, max(90.0, float(max_angle) * 1.25))
        lines1, labels1 = ax.get_legend_handles_labels()
        lines2, labels2 = ax2.get_legend_handles_labels()
        ax.legend(lines1 + lines2, labels1 + labels2, loc="upper left")
    else:
        ax.legend()

    fig.tight_layout()
    return fig


def _sort_by_tick(df: pd.DataFrame) -> pd.DataFrame:
    for col in ("t0_manual_tick", "t1_aim_start_tick", "t2_first_hit_tick", "moment_timestamp"):
        if col in df.columns:
            return df.sort_values(col)
    return df


def plot_stacked_bars(df: pd.DataFrame, match_id) -> Optional[matplotlib.figure.Figure]:
    """Per-engagement stacked bar for a single match (peek only)."""
    peek = _sort_by_tick(_peek_df(df[df["match_id"] == match_id].copy()))
    return _plot_stacked_bars_impl(
        peek, match_id, _PEEK_BAR_COLORS,
        f"Reaction Components — Match {match_id} (Peek Engagements)",
    )


def plot_hold_distributions(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Histogram + KDE of T0→T1, T1→T2, T0→T2 for hold engagements only."""
    return _plot_distributions(
        _hold_df(df),
        "Reaction Time Distributions — Hold Engagements Only",
        _HOLD_DIST_COLORS,
    )


def plot_hold_stacked_bars(df: pd.DataFrame, match_id) -> Optional[matplotlib.figure.Figure]:
    """Per-engagement stacked bar for a single match (hold only)."""
    hold = _sort_by_tick(_hold_df(df[df["match_id"] == match_id].copy()))
    return _plot_stacked_bars_impl(
        hold, match_id, _HOLD_BAR_COLORS,
        f"Reaction Components — Match {match_id} (Hold Engagements)",
    )


def plot_round_phase_distribution(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Grouped boxplot of T0→T2 by round phase (early / mid / late)."""
    if "round_phase" not in df.columns:
        return None
    plot_df = df.dropna(subset=["rt_visible_to_hit_ms", "round_phase"])
    plot_df = plot_df[plot_df["round_phase"].isin(["early", "mid", "late"])]
    if plot_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(9, 6))
    sns.boxplot(
        data=plot_df,
        x="round_phase",
        y="rt_visible_to_hit_ms",
        hue="round_phase",
        order=["early", "mid", "late"],
        palette={"early": _PALETTE["early"], "mid": _PALETTE["mid"], "late": _PALETTE["late"]},
        legend=False,
        ax=ax,
    )
    counts = plot_df.groupby("round_phase").size().to_dict()
    labels = [f"{p}\n(n={counts.get(p, 0)})" for p in ["early", "mid", "late"]]
    ax.set_xticks([0, 1, 2])
    ax.set_xticklabels(labels)
    ax.set_ylabel("T0→T2 reaction time (ms)")
    ax.set_title("T0→T2 by Round Phase — All Engagements")
    ax.yaxis.set_major_locator(ticker.MultipleLocator(500))
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ── Crosshair angle charts ────────────────────────────────────────────────────

_ANGLE_COLOR = "#e74c3c"
_ANGLE_BUCKET_COLORS = ("#3498db", "#2ecc71", "#f39c12", "#e74c3c")


def plot_crosshair_angle_distribution(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Histogram + KDE of crosshair angle at T0 — peek engagements only."""
    col = "crosshair_angle_at_t0_deg"
    peek = _peek_df(df)
    if col not in peek.columns:
        return None
    data = peek[col].dropna()
    if len(data) < 3:
        return None

    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(data, bins=20, kde=True, ax=ax, color=_ANGLE_COLOR, alpha=0.7)
    med = data.median()
    p75 = data.quantile(0.75)
    ax.axvline(med, color="black", linestyle="--", linewidth=1.5, label=f"Median {med:.1f}°")
    ax.axvline(p75, color="gray",  linestyle=":",  linewidth=1.2, label=f"p75 {p75:.1f}°")
    ax.set_xlabel("Crosshair angle at T0 (°)")
    ax.set_title(f"Crosshair Placement at T0 — Peek Engagements (n={len(data)})")
    ax.legend()
    fig.tight_layout()
    return fig


def plot_crosshair_angle_vs_t0t1(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Scatter: crosshair angle at T0 vs T0→T1 — the core diagnostic chart."""
    col_x, col_y = "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms"
    peek = _peek_df(df)
    if col_x not in peek.columns or col_y not in peek.columns:
        return None
    plot_df = peek.dropna(subset=[col_x, col_y])
    if len(plot_df) < 5:
        return None

    hue_col = "match_id" if ("match_id" in plot_df.columns and plot_df["match_id"].nunique() > 1) else None

    fig, ax = plt.subplots(figsize=(10, 6))
    sns.scatterplot(data=plot_df, x=col_x, y=col_y, hue=hue_col, alpha=0.7, s=80, ax=ax)
    try:
        z = np.polyfit(plot_df[col_x].astype(float), plot_df[col_y].astype(float), 1)
        xs = np.linspace(float(plot_df[col_x].min()), float(plot_df[col_x].max()), 100)
        ax.plot(xs, np.poly1d(z)(xs), color="black", linestyle="--", linewidth=1.5, label="Trend")
    except np.linalg.LinAlgError:
        pass
    ax.set_xlabel("Crosshair angle at T0 (°)")
    ax.set_ylabel("T0→T1 (ms) — Perception + Decision Time")
    ax.set_title("Crosshair Angle vs Perception Time — Peek Engagements")
    ax.set_ylim(bottom=0)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_crosshair_angle_buckets(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Bar chart: median T0→T1 and T0→T2 by crosshair angle bucket."""
    col = "crosshair_angle_at_t0_deg"
    peek = _peek_df(df)
    if col not in peek.columns:
        return None
    plot_df = peek.dropna(subset=[col, "rt_visible_to_aim_ms", "rt_visible_to_hit_ms"]).copy()
    if plot_df.empty:
        return None

    bins   = [0, 5, 15, 30, 360]
    labels = ["0–5°", "5–15°", "15–30°", "30°+"]
    plot_df["angle_bucket"] = pd.cut(
        plot_df[col], bins=bins, labels=labels, right=True, include_lowest=True
    )
    plot_df = plot_df.dropna(subset=["angle_bucket"])

    summary = (
        plot_df.groupby("angle_bucket", observed=True)
        .agg(t0t1=("rt_visible_to_aim_ms", "median"),
             t0t2=("rt_visible_to_hit_ms", "median"),
             n=("rt_visible_to_aim_ms", "count"))
        .reset_index()
    )
    if summary.empty:
        return None

    fig, ax = plt.subplots(figsize=(10, 6))
    x = np.arange(len(summary))
    w = 0.35
    ax.bar(x - w / 2, summary["t0t1"], w, label="T0→T1 (perception)", color=_PEEK_DIST_COLORS[0])
    ax.bar(x + w / 2, summary["t0t2"], w, label="T0→T2 (total RT)",   color=_PEEK_DIST_COLORS[2])
    ax.set_xticks(x)
    ax.set_xticklabels(
        [f"{b}\n(n={n})" for b, n in zip(summary["angle_bucket"], summary["n"])]
    )
    ax.set_ylabel("ms (median)")
    ax.set_title("Reaction Time by Crosshair Angle Bucket — Peek Engagements")
    ax.set_ylim(bottom=0)
    ax.legend()
    fig.tight_layout()
    return fig


def plot_crosshair_angle_by_match(df: pd.DataFrame) -> Optional[matplotlib.figure.Figure]:
    """Boxplot of crosshair angle at T0 per match — peek engagements only."""
    col = "crosshair_angle_at_t0_deg"
    peek = _peek_df(df)
    if col not in peek.columns or "match_id" not in peek.columns:
        return None
    plot_df = peek.dropna(subset=[col])
    if plot_df.empty:
        return None

    fig, ax = plt.subplots(figsize=(12, 6))
    sns.boxplot(data=plot_df, x="match_id", y=col, ax=ax, color=_ANGLE_COLOR)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=45, ha="right", fontsize=8)
    ax.set_ylabel("Crosshair angle at T0 (°)")
    ax.set_title("Crosshair Placement per Match — Peek Engagements")
    ax.set_ylim(bottom=0)
    fig.tight_layout()
    return fig


# ── CLI entry point ────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("csv", nargs="?", default="cs2_engagement_analysis_results.csv")
    parser.add_argument("--output-dir", default="analysis_plots")
    args = parser.parse_args()
    csv_path = args.csv
    output_dir = args.output_dir

    try:
        df = _load_df(csv_path)
    except FileNotFoundError:
        print(f"Error: '{csv_path}' not found.")
        return

    os.makedirs(output_dir, exist_ok=True)
    print(f"Loaded {len(df)} rows. Plots -> '{output_dir}/'")

    if "engagement_type" in df.columns:
        print(f"  engagement_type: {df['engagement_type'].value_counts().to_dict()}")

    def _save(fig, name):
        if fig is None:
            return
        path = os.path.join(output_dir, name)
        fig.savefig(path)
        plt.close(fig)
        print(f"  Saved {path}")

    _save(plot_velocity_scatter(df),                 "velocity_scatter.png")
    _save(plot_peek_distributions(df),               "peek_distributions.png")
    _save(plot_hold_distributions(df),               "hold_distributions.png")
    _save(plot_peek_vs_hold_boxplot(df),             "peek_vs_hold_boxplot.png")
    _save(plot_summary_boxplots(df),                 "summary_boxplots.png")
    _save(plot_round_phase_distribution(df),         "round_phase_distribution.png")
    _save(plot_crosshair_angle_distribution(df),     "crosshair_angle_distribution.png")
    _save(plot_crosshair_angle_vs_t0t1(df),          "crosshair_angle_vs_t0t1.png")
    _save(plot_crosshair_angle_buckets(df),          "crosshair_angle_buckets.png")
    _save(plot_crosshair_angle_by_match(df),         "crosshair_angle_by_match.png")

    for match_id in df["match_id"].unique():
        _save(plot_stacked_bars(df, match_id),      f"stacked_bar_{match_id}.png")
        _save(plot_hold_stacked_bars(df, match_id), f"hold_stacked_bar_{match_id}.png")

    print("\nAll plots generated.")


if __name__ == "__main__":
    main()
