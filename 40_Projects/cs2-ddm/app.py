"""
CS2 DDM Reaction Analyzer — Streamlit GUI

Run with:  streamlit run app.py
"""

import shutil
import threading
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")   # non-interactive backend required for Streamlit

import pandas as pd
import streamlit as st

from ddm_analyzer import DDMAnalyzer
from csv_utils import save_results
import visualize_results as viz
from config import DEFAULT_BATCH_WORKERS, DB_PATH, BATCH_INPUT_DIR, PLAYER_NAMES
from batch_runner import BatchRunner
from interpretation import compute_interpretation, get_benchmark_players, get_worst_metric
import report_generator

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="CS2 DDM Reaction Analyzer",
    page_icon="🎯",
    layout="wide",
)

# ── Constants ─────────────────────────────────────────────────────────────────
TEMP_DIR    = Path("temp_demos")
RESULTS_CSV = "cs2_engagement_analysis_results.csv"

# ── Session state ─────────────────────────────────────────────────────────────
if "results_df"   not in st.session_state:
    st.session_state.results_df   = pd.DataFrame()
if "attempts_df"  not in st.session_state:
    st.session_state.attempts_df  = pd.DataFrame()
if "demo_paths"   not in st.session_state:
    st.session_state.demo_paths   = {}   # {filename: abs_path_str}
if "show_plots"   not in st.session_state:
    st.session_state.show_plots   = False
if "last_steamid" not in st.session_state:
    st.session_state.last_steamid = ""
if "last_tickrate" not in st.session_state:
    st.session_state.last_tickrate = 64

# Batch Analysis session state (Phase 7)
if "batch_running" not in st.session_state:
    st.session_state.batch_running = False

# Module-level shared dict for thread → main-thread communication.
# st.session_state is not writable from background threads (missing ScriptRunContext).
# _batch_state is a cached singleton module — import always returns the same object,
# so _BATCH_SHARED and _BATCH_LOCK survive Streamlit reruns (exec-based, not reimport).
import _batch_state as _bs
_BATCH_SHARED: dict = _bs.shared
_BATCH_LOCK = _bs.lock

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configuration")

    steamid_input = st.text_input(
        "Player SteamID64",
        placeholder="76561198...",
        help="17-digit Steam ID of the player to analyze.",
        key="steamid_input",
    )
    tickrate = st.selectbox("Demo tickrate", [64, 128], index=0)

    st.divider()
    enemy_vel_threshold = st.slider(
        "Enemy velocity threshold (u/s)",
        min_value=50, max_value=300, value=120, step=10,
        help="Reject engagements where the enemy was moving faster than this at T0 "
             "(counter-peek / mutual-peek filter).",
    )
    player_vel_threshold = st.slider(
        "Player peek threshold (u/s)",
        min_value=10, max_value=150, value=50, step=5,
        help="Player XY speed at T0 above which the engagement is classified as 'peek'.",
    )

    reanalyze_clicked = st.button(
        "🔄 Re-analyze with new thresholds",
        use_container_width=True,
        disabled=not st.session_state.demo_paths or not st.session_state.last_steamid,
    )

    st.divider()
    if st.button("🗑️ Clear All", use_container_width=True):
        if TEMP_DIR.exists():
            shutil.rmtree(TEMP_DIR)
        st.session_state.results_df = pd.DataFrame()
        st.session_state.demo_paths = {}
        st.session_state.show_plots = False
        st.rerun()

# ── Title ─────────────────────────────────────────────────────────────────────
st.title("🎯 CS2 DDM Reaction Analyzer")
st.caption(
    "Upload CS2 demo files (.dem), run BVH-based reaction time analysis, "
    "and visualize results. Runs fully locally — no internet required after setup."
)

# ── Section 1: Upload ─────────────────────────────────────────────────────────
st.header("1. Upload Demos")

uploaded_files = st.file_uploader(
    "Drop .dem files here or click to browse",
    type=["dem"],
    accept_multiple_files=True,
)

TEMP_DIR.mkdir(exist_ok=True)

if uploaded_files:
    for f in uploaded_files:
        if f.name not in st.session_state.demo_paths:
            try:
                dest = TEMP_DIR / f.name
                data = f.read()
                if not data:
                    st.warning(f"⚠ `{f.name}` — file was empty on upload, try again.")
                    continue
                dest.write_bytes(data)
                st.session_state.demo_paths[f.name] = str(dest)
            except Exception as e:
                st.error(f"Failed to save `{f.name}`: {e}")

if st.session_state.demo_paths:
    st.success(f"{len(st.session_state.demo_paths)} demo(s) ready to analyze")
    for name in st.session_state.demo_paths:
        st.write(f"  ✓ `{name}`")

# ── Section 2: Analyze ────────────────────────────────────────────────────────
st.header("2. Analyze")

no_demos   = not st.session_state.demo_paths
no_steamid = not st.session_state.get("steamid_input", "").strip()

if no_demos or no_steamid:
    st.info(
        ("❌ No demos uploaded — use the uploader above.   " if no_demos else "✅ Demo(s) ready.   ")
        + ("❌ SteamID64 missing — enter it in the sidebar." if no_steamid else "✅ SteamID entered.")
    )

col_run, col_plots = st.columns(2)
with col_run:
    analyze_clicked = st.button(
        "▶ Run Analysis",
        use_container_width=True,
        type="primary",
        disabled=no_demos or no_steamid,
    )
with col_plots:
    plots_clicked = st.button(
        "📊 Show Plots",
        use_container_width=True,
        disabled=st.session_state.results_df.empty,
    )

if plots_clicked:
    st.session_state.show_plots = True

def _run_analysis(player_steamid: int, tickrate: int, demos: list,
                   enemy_vel: float, player_vel: float):
    """Shared analysis loop used by both Analyze and Re-analyze buttons."""
    all_results = []
    progress_bar = st.progress(0, text="Starting…")

    for i, (filename, demo_path) in enumerate(demos):
        progress_bar.progress(i / len(demos), text=f"Analyzing {filename}…")
        with st.spinner(f"Processing `{filename}`…"):
            try:
                match_label = Path(demo_path).stem
                analyzer = DDMAnalyzer(
                    demo_path, player_steamid,
                    match_id=match_label, tickrate=tickrate, debug_prints=False,
                    enemy_velocity_threshold=enemy_vel,
                    player_velocity_threshold=player_vel,
                )
                results_df, _ = analyzer.analyze_demo(bulk_mode=True)
                if not results_df.empty:
                    save_results(results_df, RESULTS_CSV, analyzer.match_id)
                    all_results.append(results_df)
                label = f"✓ `{filename}` — **{len(results_df)}** engagement(s)"
                if not results_df.empty:
                    st.success(label)
                else:
                    st.warning(f"⚠ `{filename}` — no valid engagements found")
            except Exception as e:
                import traceback
                st.error(f"✗ `{filename}` — {e}")
                st.code(traceback.format_exc())

    progress_bar.progress(1.0, text="Done!")
    # OF-2: geometry attempts removed; attempts_df always empty (kept for session_state compat)
    return all_results, pd.DataFrame()


if reanalyze_clicked:
    st.session_state.results_df = pd.DataFrame()
    st.session_state.show_plots = False
    try:
        player_steamid = int(st.session_state.last_steamid)
    except ValueError:
        st.error("Stored SteamID is invalid — please use Run Analysis first.")
        st.stop()
    all_results, attempts_df = _run_analysis(
        player_steamid, st.session_state.last_tickrate,
        list(st.session_state.demo_paths.items()),
        enemy_vel_threshold, player_vel_threshold,
    )
    if all_results:
        st.session_state.results_df = pd.concat(all_results, ignore_index=True)
        st.session_state.attempts_df = attempts_df
        st.rerun()

if analyze_clicked:
    sid_str = st.session_state.get("steamid_input", "").strip()
    try:
        player_steamid = int(sid_str)
    except ValueError:
        st.error("Invalid SteamID64 — must be a plain 17-digit number.")
        st.stop()

    st.session_state.last_steamid  = sid_str
    st.session_state.last_tickrate = tickrate

    all_results, attempts_df = _run_analysis(
        player_steamid, tickrate, list(st.session_state.demo_paths.items()),
        enemy_vel_threshold, player_vel_threshold,
    )

    if all_results:
        st.session_state.results_df = pd.concat(all_results, ignore_index=True)
        st.session_state.attempts_df = attempts_df
        st.session_state.show_plots = False
        st.rerun()

# ── Section 3: Results table ──────────────────────────────────────────────────
if not st.session_state.results_df.empty:
    st.header("3. Results")
    df = st.session_state.results_df

    peek_n = int((df["engagement_type"] == "peek").sum()) if "engagement_type" in df.columns else 0
    hold_n = int((df["engagement_type"] == "hold").sum()) if "engagement_type" in df.columns else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Total engagements", len(df))
    m2.metric("Peek", peek_n)
    m3.metric("Hold", hold_n)

    # Kill rate summary
    att = st.session_state.attempts_df
    if not att.empty:
        st.subheader("Kill Rate + First-Burst Accuracy")
        agg = (
            att.groupby("engagement_type")
            .agg(
                Attempts=("was_killed", "size"),
                Kills=("was_killed", "sum"),
                Bullets_Fired=("bullets_fired", "sum"),
                Bullets_Hit=("bullets_hit", "sum"),
            )
            .reset_index()
        )
        agg["Kill Rate"] = (100 * agg["Kills"] / agg["Attempts"]).round(1).astype(str) + "%"
        agg["Hit Rate"] = (
            100 * agg["Bullets_Hit"] / agg["Bullets_Fired"].replace(0, pd.NA)
        ).round(1).astype(str) + "%"
        st.dataframe(
            agg[["engagement_type", "Attempts", "Kills", "Kill Rate",
                 "Bullets_Fired", "Bullets_Hit", "Hit Rate"]]
        )

        # Engaged duels: clusters where player damaged at least one enemy.
        # Filters out phantom attempts (sprays into stone/smoke/air where BVH
        # picked up a distant visible enemy but the player never hit anyone).
        st.markdown("**Engaged duels** — clusters where player hit at least one enemy")
        if "hurt_victims_in_window" in att.columns:
            engaged = att[att["hurt_victims_in_window"].fillna("") != ""]
        else:
            engaged = att[att["bullets_hit"] > 0]

        if engaged.empty:
            st.info("No engaged duels recorded.")
        else:
            eagg = (
                engaged.groupby("engagement_type")
                .agg(
                    Attempts=("was_killed", "size"),
                    Kills=("was_killed", "sum"),
                    Bullets_Fired=("bullets_fired", "sum"),
                    Bullets_Hit=("bullets_hit", "sum"),
                )
                .reset_index()
            )
            eagg["Kill Rate"] = (100 * eagg["Kills"] / eagg["Attempts"]).round(1).astype(str) + "%"
            eagg["Hit Rate"] = (
                100 * eagg["Bullets_Hit"] / eagg["Bullets_Fired"].replace(0, pd.NA)
            ).round(1).astype(str) + "%"
            st.dataframe(
                eagg[["engagement_type", "Attempts", "Kills", "Kill Rate",
                      "Bullets_Fired", "Bullets_Hit", "Hit Rate"]]
            )
            st.caption(
                f"Engaged: {len(engaged)}/{len(att)} "
                f"({100*len(engaged)/len(att):.1f}% of attempts). "
                f"Phantoms (no damage): {len(att) - len(engaged)}."
            )

        with st.expander(f"Raw duel attempts ({len(att)} rows) — diagnostic"):
            st.dataframe(att, width="stretch", height=300)
            st.download_button(
                label="Download attempts CSV",
                data=att.to_csv(index=False).encode("utf-8"),
                file_name="duel_attempts_raw.csv",
                mime="text/csv",
            )

    display_cols = [
        "match_id", "map_name", "moment_timestamp", "engagement_type",
        "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
        "player_velocity_at_t0_ups", "enemy_velocity_at_t0_ups", "crosshair_angle_at_t0_deg",
    ]
    display_df = df[[c for c in display_cols if c in df.columns]]

    def _highlight_type(val):
        if val == "peek":
            return "background-color: #d5f5e3; color: #1a5c35"
        if val == "hold":
            return "background-color: #fdebd0; color: #784212"
        return ""

    styled = (
        display_df.style.map(_highlight_type, subset=["engagement_type"])
        if "engagement_type" in display_df.columns
        else display_df.style
    )
    st.dataframe(styled, width="stretch", height=380)

# ── Section 4: Plots ──────────────────────────────────────────────────────────
if st.session_state.show_plots and not st.session_state.results_df.empty:
    st.header("4. Visualizations")
    df = st.session_state.results_df

    col_a, col_b = st.columns(2)
    with col_a:
        fig = viz.plot_peek_distributions(df)
        if fig:
            st.pyplot(fig)
        else:
            st.info("Not enough peek data for distribution plot.")
    with col_b:
        fig = viz.plot_hold_distributions(df)
        if fig:
            st.pyplot(fig)
        else:
            st.info("No hold engagement data for distribution plot.")

    col_c, col_d = st.columns(2)
    with col_c:
        fig = viz.plot_peek_vs_hold_boxplot(df)
        if fig:
            st.pyplot(fig)
        else:
            st.info("Not enough data for peek vs hold boxplot.")
    with col_d:
        fig = viz.plot_round_phase_distribution(df)
        if fig:
            st.pyplot(fig)
        else:
            st.info("No round phase data yet — re-run analysis to populate.")

    fig = viz.plot_velocity_scatter(df)
    if fig:
        st.pyplot(fig)

    fig = viz.plot_summary_boxplots(df)
    if fig:
        st.pyplot(fig)

    # ── Crosshair angle section ────────────────────────────────────────────────
    if "crosshair_angle_at_t0_deg" in df.columns and df["crosshair_angle_at_t0_deg"].notna().any():
        st.subheader("Crosshair Angle at T0")

        col_e, col_f = st.columns(2)
        with col_e:
            fig = viz.plot_crosshair_angle_distribution(df)
            if fig:
                st.pyplot(fig)
        with col_f:
            fig = viz.plot_crosshair_angle_by_match(df)
            if fig:
                st.pyplot(fig)

        fig = viz.plot_crosshair_angle_vs_t0t1(df)
        if fig:
            st.pyplot(fig)

        fig = viz.plot_crosshair_angle_buckets(df)
        if fig:
            st.pyplot(fig)

    if "match_id" in df.columns:
        for mid in df["match_id"].unique():
            peek_fig = viz.plot_stacked_bars(df, mid)
            hold_fig = viz.plot_hold_stacked_bars(df, mid)
            if peek_fig or hold_fig:
                st.subheader(f"Match {mid} — Stacked Bars")
                if peek_fig and hold_fig:
                    c1, c2 = st.columns(2)
                    with c1:
                        st.pyplot(peek_fig)
                    with c2:
                        st.pyplot(hold_fig)
                elif peek_fig:
                    st.pyplot(peek_fig)
                else:
                    st.pyplot(hold_fig)

# ── Batch Analysis ────────────────────────────────────────────────────────────
st.header("Batch Analysis")
st.caption(
    "Process all .dem files in a `for_analysis/` subfolder in parallel. "
    "Uses the Player SteamID64 from Configuration above."
)

_FOR_ANALYSIS_DIR = Path(BATCH_INPUT_DIR)
_FOR_ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)

# Detect subfolders (player/team collections) within for_analysis/
_subfolders = sorted(
    [d.name for d in _FOR_ANALYSIS_DIR.iterdir() if d.is_dir()],
)
_folder_options = ["(root — flat .dem files)"] + _subfolders

selected_folder = st.selectbox(
    "Demo folder",
    options=_folder_options,
    index=0,
    help="Select a subfolder to process. Each subfolder typically contains one player's or team's demos.",
)

if selected_folder == "(root — flat .dem files)":
    _scan_dir = _FOR_ANALYSIS_DIR
else:
    # H-01: validate resolved path stays under _FOR_ANALYSIS_DIR (prevents symlink traversal)
    _scan_dir = (_FOR_ANALYSIS_DIR / selected_folder).resolve()
    if not _scan_dir.is_relative_to(_FOR_ANALYSIS_DIR.resolve()):
        st.error("Invalid folder selection.")
        st.stop()

dem_files = sorted(_scan_dir.glob("*.dem"))

if dem_files:
    st.success(f"{len(dem_files)} demo(s) in `{_scan_dir.name}/`")
    with st.expander("Demo files"):
        for _p in dem_files:
            st.write(f"  `{_p.name}`")
else:
    st.info(f"No .dem files in `{_scan_dir}` — drop files there and refresh.")

# Batch controls — SteamID reused from sidebar Configuration
_batch_sid_str = st.session_state.get("steamid_input", "").strip()
batch_steamid_valid = False
batch_player_steamid = 0
if _batch_sid_str:
    try:
        batch_player_steamid = int(_batch_sid_str)
        batch_steamid_valid = True
        st.info(f"Using SteamID64 from Configuration: `{batch_player_steamid}`")
    except ValueError:
        st.error("SteamID64 in Configuration is invalid — enter a plain 17-digit number there.")
else:
    st.warning("Enter Player SteamID64 in the Configuration panel (sidebar) first.")

n_workers = st.slider(
    "Worker processes",
    min_value=1,
    max_value=16,
    value=DEFAULT_BATCH_WORKERS,
    step=1,
    help=f"Parallel worker processes. Default={DEFAULT_BATCH_WORKERS} (matches i7-11800H physical cores).",
)

force_reprocess = st.checkbox(
    "Force reprocess (ignore processed_matches)",
    value=False,
    help="Re-run analysis even for demos already in the database.",
)

batch_clicked = st.button(
    "▶ Run Batch",
    use_container_width=True,
    type="primary",
    disabled=(
        not dem_files
        or not batch_steamid_valid
        or bool(st.session_state.get("batch_running"))
    ),
)


def _run_batch_thread(
    demo_paths: list,
    player_steamid: int,
    n_workers: int,
    db_path: str,
    force: bool,
) -> None:
    """Background thread: writes progress to _BATCH_SHARED (not st.session_state).

    st.session_state is not accessible from background threads (missing ScriptRunContext).
    The main thread polls _BATCH_SHARED and calls st.rerun() to update the UI.
    """
    total = len(demo_paths)
    _BATCH_SHARED.update({"running": True, "total": total, "done": 0, "current": "", "errors": [], "results": []})

    def _progress(done: int, total: int, current: str) -> None:
        _BATCH_SHARED["done"] = done
        _BATCH_SHARED["current"] = current

    try:
        runner = BatchRunner(db_path=db_path, n_workers=n_workers)
        results = runner.run(
            demo_paths,
            player_steamid=player_steamid,
            tickrate=64,
            force_reprocess=force,
            progress_callback=_progress,
        )
        errors = [
            f"{r.get('demo', '?')}: {r.get('error', 'unknown')}"
            for r in results if r.get("status") == "error"
        ]
        # H-02: write results then flip running=False atomically
        with _BATCH_LOCK:
            _BATCH_SHARED["errors"].extend(errors)
            _BATCH_SHARED["results"] = results
            _BATCH_SHARED["running"] = False
    except Exception as exc:
        import traceback
        with _BATCH_LOCK:
            _BATCH_SHARED["errors"].append(
                f"BatchRunner crashed: {exc}\n{traceback.format_exc()}"
            )
            _BATCH_SHARED["running"] = False


if batch_clicked and batch_steamid_valid and dem_files:
    st.session_state.batch_running = True
    _BATCH_SHARED.update({"running": True, "total": len(dem_files), "done": 0, "current": "", "errors": [], "results": []})
    _t = threading.Thread(
        target=_run_batch_thread,
        args=(list(dem_files), batch_player_steamid, n_workers, DB_PATH, force_reprocess),
        daemon=True,
    )
    _t.start()

# Progress polling — H-02: read under lock to avoid torn reads
if st.session_state.get("batch_running"):
    with _BATCH_LOCK:
        _done = _BATCH_SHARED.get("done", 0)
        _total = max(_BATCH_SHARED.get("total", 1), 1)
        _current = _BATCH_SHARED.get("current", "")
        _still_running = _BATCH_SHARED.get("running", False)
    st.progress(
        _done / _total,
        text=f"Processing demo {_done}/{_total}: {_current}",
    )
    if _still_running:
        time.sleep(0.5)
        st.rerun()
    else:
        st.session_state.batch_running = False
        st.rerun()

# Results summary after completion
if not st.session_state.get("batch_running") and _BATCH_SHARED.get("results"):
    _results = _BATCH_SHARED["results"]
    _ok_count = sum(1 for r in _results if r.get("status") == "ok")
    _err_count = sum(1 for r in _results if r.get("status") == "error")
    _total_eng = sum(r.get("engagements", 0) for r in _results)
    _total_att = sum(r.get("attempts", 0) for r in _results)

    st.success(
        f"Batch complete: {_ok_count}/{len(_results)} demos OK — "
        f"{_total_eng} engagements, {_total_att} duel attempts written to analytics.db"
    )

    _errors = _BATCH_SHARED.get("errors", [])
    if _errors:
        st.warning(f"{_err_count} demo(s) failed:")
        for _err in _errors:
            st.code(_err)

    with st.expander("Full results"):
        _res_df = pd.DataFrame(_results)
        if not _res_df.empty:
            _cols = [c for c in ["demo", "status", "engagements", "attempts"] if c in _res_df.columns]
            st.dataframe(_res_df[_cols])

# ── Interpretation ────────────────────────────────────────────────────────────
st.header("Interpretation")

_interp_sid_str = st.session_state.get("steamid_input", "").strip()
if not _interp_sid_str:
    st.info("Enter SteamID64 in the sidebar (Configuration section) to see your interpretation report.")
else:
    try:
        _interp_player_sid = int(_interp_sid_str)
    except ValueError:
        st.error("SteamID64 in Configuration is invalid — enter a plain 17-digit number.")
        _interp_player_sid = None

    if _interp_player_sid is not None:
        # Benchmark selector (D-10) — populated from analytics.db
        _benchmark_players = get_benchmark_players(DB_PATH)
        if not _benchmark_players:
            st.warning("No benchmark data in analytics.db. Run batch analysis first.")
        else:
            _bm_options = [p["display_name"] for p in _benchmark_players]
            _bm_default_idx = 0  # first available, NOT hardcoded donk (D-10)
            _bm_selection = st.selectbox(
                "Benchmark player",
                options=_bm_options,
                index=_bm_default_idx,
                key="interp_benchmark_select",
                help="Tier thresholds computed from this player's distribution in analytics.db.",
            )
            _bm_entry = _benchmark_players[_bm_options.index(_bm_selection)]
            _bm_sid = _bm_entry["steamid"]

            if _bm_entry["small_sample"]:
                st.warning(
                    f"**{_bm_selection}** has fewer than 20 demos. "
                    "Tiers are computed from hard-coded fallback thresholds — less reliable."
                )

            # Free vs Paid view toggle — operator switches to "Full Report"
            # only after Boosty/ko-fi payment confirmation. Default "Free Preview"
            # = tier card only (worst metric + per-metric tier list).
            _view_mode = st.radio(
                "View mode",
                options=["Free Preview", "Full Report ($5 paid)"],
                index=0,
                horizontal=True,
                key="interp_view_mode",
                help="Free Preview shows tier card only. Full Report shows detailed comparison + downloadable HTML — operator-only after payment confirmation.",
            )
            _is_paid_view = _view_mode.startswith("Full")

            # Peek / Hold tabs (D-06 — never conflated)
            _interp_tab_peek, _interp_tab_hold = st.tabs(["Peek", "Hold"])

            for _et, _tab in [("peek", _interp_tab_peek), ("hold", _interp_tab_hold)]:
                with _tab:
                    _rows = compute_interpretation(
                        DB_PATH,
                        player_steamid=_interp_player_sid,
                        benchmark_steamid=_bm_sid,
                        engagement_type=_et,
                    )

                    # Summary card — worst metric + drill at top (D-02 / SC1 / SC2)
                    _worst = get_worst_metric(_rows)
                    if _worst and _worst.get("tier") not in ("n/a", None):
                        st.info(
                            f"**Your biggest opportunity ({_et}):** "
                            f"`{_worst.get('label', _worst['metric'])}` is rated **{_worst['tier']}**. "
                            f"Drill: {_worst['drill']}"
                        )

                    if _is_paid_view:
                        # Full table — paid path
                        _h1, _h2, _h3, _h4, _h5 = st.columns([2, 1, 1, 1, 3])
                        _h1.markdown("**Metric**")
                        _h2.markdown("**You**")
                        _h3.markdown("**Tier**")
                        _h4.markdown(f"**vs {_bm_selection.split(' (')[0]}**")
                        _h5.markdown("**Drill**")
                        st.divider()

                        _RT_METRICS = {"rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"}
                        for _row in _rows:
                            _label = _row.get("label", _row["metric"])
                            _pval = _row.get("player_value")
                            _pval_str = f"{_pval:.1f}" if _pval is not None else "—"
                            _bm_p50 = _row.get("benchmark_p50")
                            _bm_str = f"{_bm_p50:.1f}" if _bm_p50 is not None else "—"
                            _gap = _row.get("gap")
                            _gap_str = f"{_gap:+.1f}" if _gap is not None else "—"
                            _tier = _row.get("tier", "—")
                            _drill = _row.get("drill", "—")

                            _bc = _row.get("bottleneck_component")
                            _drill_display = _drill
                            if _bc:
                                _drill_display = f"[{_bc} bottleneck] {_drill}"

                            col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 3])
                            col1.markdown(f"**{_label}**")
                            col2.markdown(_pval_str)
                            col3.markdown(f"*{_tier}*")
                            col4.markdown(f"vs {_bm_str} ({_gap_str})")
                            col5.markdown(_drill_display)

                            if _row["metric"] in _RT_METRICS and _pval is not None:
                                st.caption("Measured on hits only — survivorship bias applies.")
                    else:
                        # Free preview — tier-only list, no values, no drills, no benchmarks
                        _h1, _h2 = st.columns([3, 1])
                        _h1.markdown("**Metric**")
                        _h2.markdown("**Tier**")
                        st.divider()

                        for _row in _rows:
                            _label = _row.get("label", _row["metric"])
                            _tier = _row.get("tier", "—")
                            col1, col2 = st.columns([3, 1])
                            col1.markdown(f"**{_label}**")
                            col2.markdown(f"*{_tier}*")

            # ── View-mode-dependent footer ────────────────────────────────────
            if _is_paid_view:
                # Download HTML Report (D-08) — paid path only
                try:
                    _html_bytes = report_generator.generate_html_report(
                        player_steamid=_interp_player_sid,
                        benchmark_steamid=_bm_sid,
                        benchmark_name=_bm_selection.split(" (")[0],
                        db_path=DB_PATH,
                    )
                    st.download_button(
                        label="Download Report",
                        data=_html_bytes,
                        file_name=f"djok_report_{_interp_player_sid}.html",
                        mime="text/html",
                        help="Self-contained HTML file — open in any browser, no install required.",
                    )
                except Exception:
                    st.error(
                        "Report generation failed. Check that analytics.db contains data for this player."
                    )
            else:
                # Free preview — payment instructions instead of download button
                st.markdown(
                    """
                    ---
                    ### Want the full breakdown?

                    Free preview shows your tier per metric. The **Full Report** ($5)
                    includes:

                    - Per-metric values vs benchmark with gap
                    - Per-metric drill prescriptions
                    - Survivorship-bias caveats inline
                    - Downloadable offline HTML report

                    **Pay $5 → get the full report:**

                    1. Pay via [Boosty](https://boosty.to/leodikadyrov)
                       (RU cards) or [ko-fi](https://ko-fi.com/leodikadyrov)
                       (international)
                    2. Send payment screenshot + your demo SteamID to
                       [@puchar](https://t.me/puchar) on Telegram
                    3. Full HTML report delivered within 48h
                    """
                )
