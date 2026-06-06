"""
Shared constants, data model, and logging factory for the DDM reaction pipeline.
"""

# ─────────────────────────────────────────────────────────────────────────────
# Persistence paths
# ─────────────────────────────────────────────────────────────────────────────

import logging
import os
from dataclasses import dataclass
from typing import Optional

DB_PATH: str = "analytics.db"

# ─────────────────────────────────────────────────────────────────────────────
# Engagement classification thresholds
# ─────────────────────────────────────────────────────────────────────────────

# Player XY speed at T0 (units/sec) above which the engagement is classified
# as a "peek" (player was moving to expose themselves).
# CS2 crouch-walk ≈ 78 u/s, walk ≈ 130 u/s, run ≈ 250 u/s.
# Stationary holds are typically < 10 u/s. 50 u/s is a conservative threshold.
VELOCITY_PEEK_THRESHOLD_UPS: float = 50.0

# Enemy XY speed at T0 (units/sec) ABOVE which the engagement is rejected.
# If the enemy is also moving fast at T0, this is a counter-peek or mutual-peek
# scenario — not the "player peeks a holding enemy" case we want to study.
# CS2 players rarely hold perfectly still — counter-strafing and shift-walking
# produce ~80–100 u/s. 120 u/s filters only clearly active movers.
ENEMY_VELOCITY_HOLD_THRESHOLD_UPS: float = 120.0

# Weapon names that are melee/knife weapons (as reported by demoparser2).
# Hits from these are excluded before clustering so knife rounds are ignored.
KNIFE_WEAPON_NAMES: frozenset = frozenset([
    "knife", "knife_t", "weapon_knife", "weapon_knife_t",
    "bayonet", "m9_bayonet", "flip", "gut", "karambit",
    "falchion", "huntsman", "bowie", "butterfly", "shadow_dagger",
    "stiletto", "ursus", "navaja", "talon", "skeleton",
])

# AWP hits are excluded from clustering and from episode analysis.
# AWP reaction mechanics (scoping, slow movement, one-shot kill) are
# fundamentally different from rifles/pistols and must be studied separately.
AWP_WEAPON_NAMES: frozenset = frozenset([
    "awp", "weapon_awp",
    "ssg08", "weapon_ssg08",    # Scout
    "scar20", "weapon_scar20",  # SCAR-20 (CT auto-sniper)
    "g3sg1", "weapon_g3sg1",    # G3SG1 (T auto-sniper)
])

# OF-2: weapon categories excluded from gun-only episode anchoring.
# Utility damage (HE/molotov/inferno tick-damage/flash/smoke) does NOT start
# a duel episode. "inferno" = demoparser2 weapon string for molotov burn ticks.
UTILITY_WEAPON_NAMES: frozenset = frozenset([
    "hegrenade", "weapon_hegrenade",
    "molotov", "weapon_molotov",
    "incgrenade", "weapon_incgrenade",
    "inferno",
    "flashbang", "weapon_flashbang",
    "smokegrenade", "weapon_smokegrenade",
])

# OF-2: lookback window (ticks) for weapon_fire initiator attribution
# in outcome_first.py. 128 ticks = 2s @ 64 Hz. Matches OF-1 spike semantics.
_INITIATOR_LOOKBACK_TICKS: int = 128

# Duel attempt clustering: new cluster when fire event gap exceeds this value.
# 128 ticks ≈ 2 seconds at 64 Hz. Clusters separate distinct engagements.
# Previously 320 (5s) — oversized clusters merged multiple enemies into a single
# attempt, breaking T0 target identity and kill attribution semantics.
_FIRE_CLUSTER_GAP_TICKS: int = 128

# Hard cap on cluster duration. In sustained firefights the inter-fire gap stays
# below _FIRE_CLUSTER_GAP_TICKS indefinitely, letting a cluster span 30+ seconds
# and merge multiple distinct engagements. Force-split when cluster[0]→t exceeds
# this span regardless of individual gaps. 192 ticks ≈ 3s at 64 Hz.
_FIRE_CLUSTER_MAX_SPAN_TICKS: int = 192

# Time window after fire_cluster_tick to search for player_hurt event.
# 192 ticks ≈ 3 seconds at 64 Hz. Covers typical hit confirmation latency.
_HIT_WINDOW_TICKS: int = 192

# ─── T0-anchored duel attempt detection ──────────────────────────────────────
# Window around a weapon_fire cluster in which BVH scans for T0 (first visibility).
# W_before covers peek attempts where the player starts firing BEFORE the enemy
# becomes geometrically visible (spray into angle / anticipation).
# W_after covers late-emerge scenarios where enemy crosses LOS mid-cluster.
_ATTEMPT_WINDOW_BEFORE_TICKS: int = 16   # 250ms — antecedent fire
_ATTEMPT_WINDOW_AFTER_TICKS:  int = 32   # 500ms — late emerge

# Window after T0 in which a player_death (attacker=self, victim=T0 target)
# counts as a kill confirmation.
_KILL_CONFIRM_WINDOW_TICKS: int = 320    # 5s — covers long fights

# Number of weapon_fire events after T0 used to compute bullet-level hit rate
# (bullets_hit / bullets_fired). Represents the first-burst accuracy.
_BULLETS_FOR_HIT_RATE: int = 5

# Within a 320-tick cluster, start a new sub-cluster when the victim changes
# AND the gap between consecutive hits exceeds this value (~1 second at 64 Hz).
_SUB_CLUSTER_GAP_TICKS: int = 64

# Round-phase thresholds (seconds into the round at T0).
_ROUND_EARLY_MAX_S: float = 40.0
_ROUND_MID_MAX_S: float = 70.0

# Minimum ticks between BVH-found T0 and search_start.
# If T0 == search_start the enemy was already visible before the lookback window
# started — the true T0 is unknown and T0→T2 will be inflated.
# 20 ticks ≈ 312ms. Engagements failing this gate are not gradeable.
T0_MIN_OFFSET_TICKS: int = 20

# Maximum ticks between T0 and T2 (first hit) for an engagement to be gradeable.
# auto_build_moments groups player_hurt events into 5s clusters; if same target
# is hit twice across separate firefights (e.g. shoot → miss → enemy retreats →
# returns → hit), T2 captures the LATE hit, inflating rt_visible_to_hit and
# rt_aim_to_hit by 4–6 seconds. 96 ticks ≈ 1.5s — empirically where mean ≈ median
# (clean distribution). Engagements with T0→T2 > this cap = cluster bleed,
# ungradeable for RT but kept in raw table.
T0_TO_T2_MAX_TICKS: int = 96

# Phase 9.1 — selective parse_ticks windowing (D-02 fallback flag).
# When True, parse_ticks is called with a `ticks=` union of windows around
# each player_hurt anchor instead of materializing the full demo. Set to
# False to revert to full-demo parse without a git revert.
# Window math (tickrate 64, ms_per_tick = 15.625):
#   384 ticks ≈ 6s before each hurt — covers approach + visibility lookback.
#   192 ticks ≈ 3s after each hurt — covers analysis window + grace.
PARSE_TICKS_SELECTIVE: bool = True
_SELECTIVE_WINDOW_BEFORE_TICKS: int = 384  # ~6s before each player_hurt anchor
_SELECTIVE_WINDOW_AFTER_TICKS: int = 192   # ~3s after — covers analysis window + grace

# ─────────────────────────────────────────────────────────────────────────────
# T1 detection parameters
# ─────────────────────────────────────────────────────────────────────────────

# T1 reactive aim search starts at T0 (grace removed 2026-05-16 — see
# .planning/REVIEW-2026-05-16.md B-1). Three semantic filters prevent
# pre-aim micro-corrections from registering as T1:
#   1. T1_MIN_ANGLE_CHANGE (0.08°) — filters jitter
#   2. moving_towards predicate — filters non-reactive corrections
#   3. T1_SUSTAINED_AIM_TICKS=2 — filters single-tick noise spikes
# Adding a structural grace on top creates a hard 8-tick (125ms) floor on
# the metric. 1145 engagements pinned at exactly that value pre-fix.
# Phase 10 also adds a pre-aimed branch (see ddm_analyzer._detect_t1) that
# returns T1=T0 when the player is already on target at T0 (B-4).
T1_GRACE_MS: int = 0

# Minimum number of consecutive ticks showing aim movement toward the enemy
# before the start of that sequence is accepted as T1.
T1_SUSTAINED_AIM_TICKS: int = 2

# Minimum angular change per tick (degrees) to count as active aim movement.
T1_MIN_ANGLE_CHANGE: float = 0.08

# Maximum angular deviation from enemy direction to remain "on target".
T1_NOT_AIMED_THRESHOLD: float = 1.0

# Minimum approach delta (degrees) to count as "moving towards" enemy.
T1_MOVING_TOWARDS_TOLERANCE: float = 0.01


# ─────────────────────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AnalysisMoment:
    timestamp: str                                    # "MM:SS" label
    manual_t0_tick_enemy_first_visible: Optional[int] # None → use auto-detection
    description: str = ""
    analysis_window_seconds_after_t0: int = 5
    target_enemy_steamid_if_known: Optional[int] = None

    # Phase 2 — auto T0
    use_auto_t0: bool = False
    # Tick to start scanning for the enemy in auto mode (set to ~T0 - a few seconds)
    auto_t0_search_start_tick: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# Logging
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# Batch runner
# ─────────────────────────────────────────────────────────────────────────────

# Default number of parallel worker processes for batch demo analysis.
# Matches i7-11800H physical core count (8 cores / 16 logical).
# Each worker loads awpy + demoparser2 + numpy (~300 MB RAM per process).
# ─────────────────────────────────────────────────────────────────────────────
# Player display names (Phase 8 interpretation layer)
# ─────────────────────────────────────────────────────────────────────────────

# D-15 eval roster (Plan v2-03 task 2). Real nicknames only — placeholder
# strings forbidden per D-10 + D-15 + B-1+B-4 hard block. SteamIDs verified
# 2026-05-12 via profilerr.net + memory `reference_player_steam_ids.md`
# (Spirit 86 demos + FaZe astralis-vs-faze 57 demos).
PLAYER_NAMES: dict[int, str] = {
    # ─ D-15 top tier (3 players) ────────────────────────────────────────────
    76561198386265483: "donk",        # Spirit, top trial count in main DB (1232)
    76561197989430253: "karrigan",    # FaZe, top trials FaZe-side (363)
    76561198068422762: "frozen",      # FaZe (memory: reference_player_steam_ids)
    # ─ D-15 mid tier (4 players) ────────────────────────────────────────────
    76561198016255205: "twistzz",     # FaZe (memory)
    76561198178737429: "jcobbb",      # FaZe HLTV id 22383, verified 2026-05-12
    76561198081484775: "sh1ro",       # Spirit (249 trials in main DB)
    76561198872013168: "tN1R",        # Spirit ≥100 trials (426); D-15 random Spirit slot
    # ─ D-15 bottom tier (3 players, lowest-trial passing min-trials gate) ───
    76561198005107817: "Staehr",      # Astralis (31 trials in main DB)
    76561198120557348: "jabbi",       # Astralis (memory; awaits backfill)
    76561197998926770: "HooXi",       # Astralis (memory; awaits backfill)
}

# ─────────────────────────────────────────────────────────────────────────────
# Phase v2 — LLM narrative coaching layer (Plans 01 + 02; resolved merge)
# ─────────────────────────────────────────────────────────────────────────────

# LLM provider abstraction (REQ-3). Currently Anthropic-only; future-proof env hook.
LLM_PROVIDER: str = os.environ.get("LLM_PROVIDER", "anthropic")

# Default model — claude-sonnet-4-6 per L-2 (quality/cost balance, $3/$15 MTok).
# Override via env LLM_MODEL=claude-opus-4-7 for ~5× cost / higher quality.
LLM_MODEL: str = os.environ.get("LLM_MODEL", "claude-sonnet-4-6")

# Locked common-noun whitelist — D-06 hybrid validator allows these without
# attribution. Keep tight: every token here is a free-pass to the LLM.
NARRATIVE_COMMON_NOUNS_WHITELIST: frozenset[str] = frozenset({
    "peek", "hold", "aim", "crosshair", "pre-aim",
    "deathmatch", "DM", "VOD",
})

DEFAULT_BATCH_WORKERS: int = 8

# Directory scanned by the batch runner for .dem input files.
BATCH_INPUT_DIR: str = "../for_analysis"

# Log file for batch worker errors (tracebacks from failed demos).
BATCH_ERRORS_LOG: str = "batch_errors.log"


def get_logger(match_id: int | str, debug: bool = False) -> logging.Logger:
    import sys
    name = f"DDM.{match_id}"
    logger = logging.getLogger(name)
    if not logger.handlers:
        fh = logging.FileHandler("ddm_analysis.log", encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(name)s] %(levelname)s: %(message)s"
        ))
        logger.addHandler(fh)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(logging.Formatter("[%(name)s] %(message)s"))
        logger.addHandler(sh)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False
    return logger
