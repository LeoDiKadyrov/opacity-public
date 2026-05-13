"""Interpretation layer: tier computation, drill lookup, benchmark percentiles."""
from __future__ import annotations
import sqlite3
from contextlib import closing
from typing import Optional
import pandas as pd
from config import DB_PATH, PLAYER_NAMES, T0_TO_T2_MAX_TICKS

# Tick → ms (CS2 tickrate 64). Inline to avoid coupling.
_MS_PER_TICK = 1000.0 / 64.0
_T0_T2_MAX_MS = T0_TO_T2_MAX_TICKS * _MS_PER_TICK

_METRICS_LOWER_IS_BETTER = {
    "crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms",
    "rt_aim_to_hit_ms", "rt_visible_to_hit_ms",
}

# Absolute Elite ceiling — calibrated to pro-tier (donk, best-in-world) medians +
# small buffer. If player value beats this absolute threshold, tier = Elite,
# regardless of benchmark p25. Prevents "best player not Elite" when benchmark
# = self or stronger. Does NOT replace benchmark quartiles for non-Elite tiers.
# Direction follows _METRICS_LOWER_IS_BETTER: lower_is_better metrics → Elite
# if value <= ceiling; higher_is_better → Elite if value >= ceiling.
_ABSOLUTE_ELITE_CEILING: dict[str, dict[str, float]] = {
    "peek": {
        "crosshair_angle_at_t0_deg": 5.0,
        "rt_visible_to_aim_ms":      200.0,
        "rt_aim_to_hit_ms":          320.0,
        "rt_visible_to_hit_ms":      480.0,
    },
    "hold": {
        "crosshair_angle_at_t0_deg": 5.5,
        "rt_visible_to_hit_ms":      550.0,
    },
}

_FALLBACK_THRESHOLDS: dict[str, dict[str, tuple[float, float, float]]] = {
    "peek": {
        "crosshair_angle_at_t0_deg": (3.0, 6.0, 11.0),
        "rt_visible_to_aim_ms":      (125.0, 203.0, 328.0),
        "rt_aim_to_hit_ms":          (203.0, 422.0, 1000.0),
        "rt_visible_to_hit_ms":      (375.0, 578.0, 1156.0),
        "kill_rate":                 (17.2, 24.5, 31.5),
        "hit_rate":                  (8.8, 10.9, 15.2),
    },
    "hold": {
        "crosshair_angle_at_t0_deg": (3.0, 5.0, 10.0),
        "rt_visible_to_hit_ms":      (375.0, 516.0, 812.0),
        "kill_rate":                 (1.8, 4.3, 7.3),
        "hit_rate":                  (0.7, 1.7, 3.3),
    },
}

# Direction menu per (metric, engagement_type). Each metric gets 3 directions.
# Per drill research 2026-05-12: drop drill prescriptions for perception + pre-aim
# (knowledge/context-based — no synthetic→game transfer evidence). Only T1→T2
# (motor execution) keeps an optional short-drill option among its 3 directions.
# Tier-agnostic — body wording works across Elite/Good/Average/Work needed.
Direction = dict  # {"title": str, "body": str, "is_drill": bool (optional)}

DIRECTIONS: dict[tuple[str, str], list[Direction]] = {
    # crosshair_angle — pre-aim discipline, knowledge-based. Direction-only.
    ("crosshair_angle_at_t0_deg", "peek"): [
        {"title": "Map study", "body": "Pick 3 default crosshair positions per site; memorize from pro VODs of your role."},
        {"title": "Demo review", "body": "Review your last 5 deaths. Mark where crosshair was off the pre-aim angle."},
        {"title": "In-game prefire", "body": "Workshop prefire map 10 min before pug — train_aim_csgo2 or aim_botz prefire mode."},
    ],
    ("crosshair_angle_at_t0_deg", "hold"): [
        {"title": "Default angle audit", "body": "Pick one default hold angle per site; commit to it, don't drift mid-round."},
        {"title": "Demo review", "body": "Watch your holds; mark where crosshair dropped below neck level before peek."},
        {"title": "Head-level discipline", "body": "Solo queue practice — never drop crosshair below neck on a hold."},
    ],

    # T0→T1 perception latency — peek only. Direction-only (perceptual transfer weak per research Q2).
    ("rt_visible_to_aim_ms", "peek"): [
        {"title": "Demo review", "body": "Watch your last 3 demos; find moments where enemy was visible ≥100ms before you reacted."},
        {"title": "Higher-tier pugs", "body": "Queue against higher-FACEIT-tier opponents; faster visual search than scrims."},
        {"title": "Deathmatch focus", "body": "FFA DM 20 min — first-shot reaction priority, ignore kill count."},
    ],

    # T1→T2 motor execution — peek only. HYBRID: 1 optional drill among 3 (motor specificity per research Q3).
    ("rt_aim_to_hit_ms", "peek"): [
        {"title": "Deathmatch volume", "body": "30 min DM daily — pure aim work. Focus on first-shot accuracy, not raw kill count."},
        {"title": "Aim_botz before pug", "body": "10 min head-level flicks. 50 taps per session before you queue."},
        {"title": "Optional drill: KovaaK's", "body": "Reactive Tracking scenario ≤15 min/day. Stop if hand/wrist strain.", "is_drill": True},
    ],

    # T0→T2 composite — bottleneck info routes user to T0→T1 or T1→T2 menu.
    ("rt_visible_to_hit_ms", "peek"): [
        {"title": "Demo review", "body": "Identify your slowest peek moments. Categorize each as perception delay or motor delay."},
        {"title": "Route by bottleneck", "body": "If T0→T1 is worst, see perception menu above. If T1→T2 is worst, see motor menu."},
        {"title": "Full-loop DM", "body": "DM peek-only mode: pre-aim → peek → shoot. No spray, no repositioning."},
    ],
    ("rt_visible_to_hit_ms", "hold"): [
        {"title": "Default angle commit", "body": "Pick one hold position per site. Commit, don't reposition mid-round."},
        {"title": "Demo review", "body": "Watch your holds; identify hesitation when peek appears."},
        {"title": "Trigger discipline", "body": "Practice firing on first movement; don't wait for full peek to clear."},
    ],

    # kill_rate — outcome metric. Direction-only.
    ("kill_rate", "peek"): [
        {"title": "Peek selection audit", "body": "Review your peeks last 3 demos. Only peek when crosshair is pre-placed."},
        {"title": "VOD per map", "body": "Watch 1 pro your role on the map you queue most. Adopt one new peek angle."},
        {"title": "Demo notes", "body": "Track 'peek outcome' per round — killed / traded / whiffed. Identify pattern."},
    ],
    ("kill_rate", "hold"): [
        {"title": "Default hold audit", "body": "Pick 2 default hold spots per site. Resets and repositioning cost kills."},
        {"title": "VOD per site", "body": "Watch 1 pro per site. Copy one new hold angle per session."},
        {"title": "Patience drill", "body": "Solo queue — hold crosshair 20s silent before peek. Build still-discipline."},
    ],

    # hit_rate — accuracy outcome. Direction-only.
    ("hit_rate", "peek"): [
        {"title": "Single-tap DM", "body": "DM with single-tap only — no spray. AK or M4. 15 min daily."},
        {"title": "Spray review", "body": "Demo review for spray-downs; identify moments you should have one-tapped."},
        {"title": "Aim_botz static", "body": "Static head target, 50 taps per session. Track hit% per session."},
    ],
    ("hit_rate", "hold"): [
        {"title": "Counter-strafe drill", "body": "Stop fully before shooting on hold; counter-strafe before every tap."},
        {"title": "Single-tap discipline", "body": "Hold + tap only, never spray. DM 15 min daily AK or M4."},
        {"title": "Demo review", "body": "Watch your holds; mark where you sprayed instead of tapping."},
    ],
}

DEFAULT_DIRECTIONS: list[Direction] = [
    {"title": "Demo review", "body": "Watch your recent demos focused on this metric; identify the pattern first."},
    {"title": "VOD pro player", "body": "Find a pro your role; copy one habit related to this metric."},
    {"title": "Solo queue audit", "body": "Track this metric across next 5 solo queues; commit one fix per game."},
]

# Backward-compat: legacy DRILLS export — first direction's title:body string.
# Tests reference DRILLS by import; report_generator may read row['drill'].
DRILLS: dict[tuple[str, str, str], str] = {
    (metric, tier, etype): f"{directions[0]['title']}: {directions[0]['body']}"
    for (metric, etype), directions in DIRECTIONS.items()
    for tier in ("Elite", "Good", "Average", "Work needed")
}


def assign_tier(
    value: float,
    p25: float,
    p50: float,
    p75: float,
    lower_is_better: bool,
    absolute_elite: Optional[float] = None,
) -> str:
    """Tier from benchmark quartiles, with optional absolute Elite ceiling.

    If absolute_elite is provided and value beats it (≤ for lower_is_better,
    ≥ for higher_is_better), returns Elite immediately — independent of
    benchmark distribution. Used so a best-in-world player evaluated against
    himself (or a stronger benchmark) still scores Elite at his typical pace.
    """
    if lower_is_better:
        if absolute_elite is not None and value <= absolute_elite:
            return "Elite"
        if value <= p25:
            return "Elite"
        elif value <= p50:
            return "Good"
        elif value <= p75:
            return "Average"
        else:
            return "Work needed"
    else:
        if absolute_elite is not None and value >= absolute_elite:
            return "Elite"
        if value >= p75:
            return "Elite"
        elif value >= p50:
            return "Good"
        elif value >= p25:
            return "Average"
        else:
            return "Work needed"


def get_benchmark_players(db_path: str = DB_PATH) -> list[dict]:
    """Return list of {steamid, display_name, demo_count, small_sample} for all players in analytics.db."""
    with closing(sqlite3.connect(db_path)) as conn:
        # Use cursor directly — pd.read_sql casts large int64 steamids to float64,
        # which loses precision on 17-digit SteamID64 values.
        cursor = conn.execute(
            "SELECT player_steamid, COUNT(DISTINCT demo_name) as demo_count "
            "FROM engagements WHERE player_steamid IS NOT NULL GROUP BY player_steamid"
        )
        rows_raw = cursor.fetchall()
    result = []
    for row_raw in rows_raw:
        sid = int(row_raw[0])
        demo_count = int(row_raw[1])
        small_sample = demo_count < 20
        display = PLAYER_NAMES.get(sid, str(sid))
        if small_sample:
            display += " (small sample)"
        result.append({"steamid": sid, "display_name": display, "demo_count": demo_count, "small_sample": small_sample})
    return result


def _get_percentiles(
    conn: sqlite3.Connection,
    benchmark_steamid: int,
    engagement_type: str,
) -> Optional[dict[str, tuple[float, float, float]]]:
    """Return per-metric (p25, p50, p75) from benchmark player. Returns None if demo_count < 20."""
    demo_df = pd.read_sql(
        "SELECT COUNT(DISTINCT demo_name) as n FROM engagements WHERE player_steamid = ? AND engagement_type = ?",
        conn, params=(int(benchmark_steamid), engagement_type)
    )
    if demo_df["n"].iloc[0] < 20:
        return None  # triggers fallback

    # RT + crosshair percentiles from engagements
    eng_df = pd.read_sql(
        "SELECT crosshair_angle_at_t0_deg, rt_visible_to_aim_ms, rt_aim_to_hit_ms, rt_visible_to_hit_ms "
        "FROM engagements WHERE player_steamid = ? AND engagement_type = ?",
        conn, params=(int(benchmark_steamid), engagement_type)
    )
    result: dict[str, tuple[float, float, float]] = {}
    for col in ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"]:
        if col not in eng_df.columns:
            continue
        s = eng_df[col].dropna()
        if len(s) < 5:
            continue
        result[col] = (float(s.quantile(0.25)), float(s.quantile(0.50)), float(s.quantile(0.75)))

    # kill_rate + hit_rate from duel_attempts — per-demo rate distribution
    da_df = pd.read_sql(
        "SELECT demo_name, SUM(was_killed) as kills, COUNT(*) as attempts, "
        "SUM(bullets_hit) as bhit, SUM(bullets_fired) as bfired "
        "FROM duel_attempts WHERE player_steamid = ? AND engagement_type = ? GROUP BY demo_name",
        conn, params=(int(benchmark_steamid), engagement_type)
    )
    if len(da_df) >= 5:
        kr = (da_df["kills"] / da_df["attempts"].replace(0, float("nan")) * 100).dropna()
        if len(kr) >= 5:
            result["kill_rate"] = (float(kr.quantile(0.25)), float(kr.quantile(0.50)), float(kr.quantile(0.75)))
        hr = (da_df["bhit"] / da_df["bfired"].replace(0, float("nan")) * 100).dropna()
        if len(hr) >= 5:
            result["hit_rate"] = (float(hr.quantile(0.25)), float(hr.quantile(0.50)), float(hr.quantile(0.75)))

    return result


_METRIC_LABELS: dict[str, str] = {
    "crosshair_angle_at_t0_deg": "Crosshair angle at T0 (deg)",
    "rt_visible_to_aim_ms": "RT: visible → aim start (ms)",
    "rt_aim_to_hit_ms": "RT: aim start → hit (ms)",
    "rt_visible_to_hit_ms": "RT: visible → hit (ms)",
    "kill_rate": "Kill rate (%)",
    "hit_rate": "Hit rate (%)",
}

_TIER_ORDER: dict[str, int] = {"Work needed": 3, "Average": 2, "Good": 1, "Elite": 0}

_RT_CAVEAT = "Measured on hits only — survivorship bias applies"


def compute_interpretation(
    db_path: str,
    player_steamid: int,
    benchmark_steamid: int,
    engagement_type: str,
) -> list[dict]:
    """Return one dict per metric with tier, drill, caveat, and bottleneck info."""
    player_steamid = int(player_steamid)
    benchmark_steamid = int(benchmark_steamid)

    with closing(sqlite3.connect(db_path)) as conn:
        # Get benchmark percentiles (None = fallback)
        percentiles = _get_percentiles(conn, benchmark_steamid, engagement_type)
        small_sample = percentiles is None
        if small_sample:
            thresholds = _FALLBACK_THRESHOLDS.get(engagement_type, _FALLBACK_THRESHOLDS["peek"])
        else:
            thresholds = percentiles

        # Player engagement values (raw — filter applied after)
        eng_df_raw = pd.read_sql(
            "SELECT crosshair_angle_at_t0_deg, rt_visible_to_aim_ms, rt_aim_to_hit_ms, rt_visible_to_hit_ms "
            "FROM engagements WHERE player_steamid = ? AND engagement_type = ?",
            conn, params=(player_steamid, engagement_type)
        )

        # Player duel_attempts values
        da_df = pd.read_sql(
            "SELECT demo_name, SUM(was_killed) as kills, COUNT(*) as attempts, "
            "SUM(bullets_hit) as bhit, SUM(bullets_fired) as bfired "
            "FROM duel_attempts WHERE player_steamid = ? AND engagement_type = ? GROUP BY demo_name",
            conn, params=(player_steamid, engagement_type)
        )

    # Cluster-bleed gate (Bug 2): drop rows where rt_visible_to_hit_ms exceeds
    # T0_TO_T2_MAX_TICKS — these are not "slow reactions" but T2 captured from
    # a separate firefight on the same target. Future runs cap at source in
    # ddm_analyzer; this filter cleans existing DB rows from before the fix.
    rt_col = "rt_visible_to_hit_ms"
    if rt_col in eng_df_raw.columns:
        ungradeable_mask = eng_df_raw[rt_col].notna() & (eng_df_raw[rt_col] > _T0_T2_MAX_MS)
        n_ungradeable = int(ungradeable_mask.sum())
        eng_df = eng_df_raw[~ungradeable_mask].copy()
    else:
        n_ungradeable = 0
        eng_df = eng_df_raw

    # Compute player median values — benchmark uses p50, so player must too.
    # RT distributions are right-skewed; mean drags far above median due to long-tail
    # outliers from auto_build_moments cluster bleed. Median = robust comparison.
    player_values: dict[str, Optional[float]] = {}
    for col in ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms"]:
        if col in eng_df.columns and not eng_df[col].dropna().empty:
            player_values[col] = float(eng_df[col].dropna().median())
        else:
            player_values[col] = None

    if len(da_df) > 0:
        total_attempts = da_df["attempts"].sum()
        total_kills = da_df["kills"].sum()
        total_fired = da_df["bfired"].sum()
        total_hit = da_df["bhit"].sum()
        player_values["kill_rate"] = float(total_kills / total_attempts * 100) if total_attempts > 0 else None
        player_values["hit_rate"] = float(total_hit / total_fired * 100) if total_fired > 0 else None
    else:
        player_values["kill_rate"] = None
        player_values["hit_rate"] = None

    # Determine RT bottleneck for rt_visible_to_hit_ms
    abs_ceiling = _ABSOLUTE_ELITE_CEILING.get(engagement_type, {})
    t0t1_tier = None
    t1t2_tier = None
    if "rt_visible_to_aim_ms" in thresholds and player_values.get("rt_visible_to_aim_ms") is not None:
        p25, p50, p75 = thresholds["rt_visible_to_aim_ms"]
        t0t1_tier = assign_tier(
            player_values["rt_visible_to_aim_ms"], p25, p50, p75, lower_is_better=True,
            absolute_elite=abs_ceiling.get("rt_visible_to_aim_ms"),
        )
    if "rt_aim_to_hit_ms" in thresholds and player_values.get("rt_aim_to_hit_ms") is not None:
        p25, p50, p75 = thresholds["rt_aim_to_hit_ms"]
        t1t2_tier = assign_tier(
            player_values["rt_aim_to_hit_ms"], p25, p50, p75, lower_is_better=True,
            absolute_elite=abs_ceiling.get("rt_aim_to_hit_ms"),
        )

    bottleneck: Optional[str] = None
    if t0t1_tier is not None and t1t2_tier is not None:
        if _TIER_ORDER[t0t1_tier] > _TIER_ORDER[t1t2_tier]:
            bottleneck = "T0→T1"
        elif _TIER_ORDER[t1t2_tier] > _TIER_ORDER[t0t1_tier]:
            bottleneck = "T1→T2"

    # Determine which metrics to include for this engagement_type
    if engagement_type == "hold":
        metrics_to_include = ["crosshair_angle_at_t0_deg", "rt_visible_to_hit_ms", "kill_rate", "hit_rate"]
    else:
        metrics_to_include = ["crosshair_angle_at_t0_deg", "rt_visible_to_aim_ms", "rt_aim_to_hit_ms", "rt_visible_to_hit_ms", "kill_rate", "hit_rate"]

    rows = []
    for metric in metrics_to_include:
        lower_is_better = metric in _METRICS_LOWER_IS_BETTER
        pval = player_values.get(metric)

        # hold engagement: skip T0→T1 and T1→T2 with n/a
        if engagement_type == "hold" and metric in ("rt_visible_to_aim_ms", "rt_aim_to_hit_ms"):
            rows.append({
                "metric": metric,
                "label": _METRIC_LABELS.get(metric, metric),
                "player_value": None,
                "tier": "n/a",
                "benchmark_p50": None,
                "gap": None,
                "drill": "n/a (n<20 hold moments with valid T1)",
                "directions": [],
                "caveat": None,
                "small_sample": small_sample,
                "bottleneck_component": None,
            })
            continue

        if metric in thresholds:
            p25, p50, p75 = thresholds[metric]
            benchmark_p50 = p50
        else:
            # metric not in thresholds for this engagement type — skip
            continue

        if pval is not None:
            tier = assign_tier(
                pval, p25, p50, p75, lower_is_better=lower_is_better,
                absolute_elite=abs_ceiling.get(metric),
            )
        else:
            # No data for player — default to Work needed so user sees something
            tier = "Work needed"

        gap = (pval - benchmark_p50) if pval is not None else None

        directions = DIRECTIONS.get((metric, engagement_type), DEFAULT_DIRECTIONS)
        # Legacy drill string for backward compat (tests + report_generator fallback).
        drill = f"{directions[0]['title']}: {directions[0]['body']}"
        caveat = _RT_CAVEAT if metric.startswith("rt_") else None

        row: dict = {
            "metric": metric,
            "label": _METRIC_LABELS.get(metric, metric),
            "player_value": pval,
            "tier": tier,
            "benchmark_p50": benchmark_p50,
            "gap": gap,
            "drill": drill,
            "directions": directions,
            "caveat": caveat,
            "small_sample": small_sample,
            "bottleneck_component": bottleneck if metric == "rt_visible_to_hit_ms" else None,
        }
        rows.append(row)

    return rows


def get_worst_metric(rows: list[dict]) -> Optional[dict]:
    """Return the row with the worst tier. Skip rows where tier is 'n/a'. Return None if all are n/a."""
    candidates = [r for r in rows if r.get("tier") not in ("n/a", None)]
    if not candidates:
        return None
    return max(candidates, key=lambda r: _TIER_ORDER.get(r["tier"], -1))
