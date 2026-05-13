"""
EZ-Diffusion Pc Validation Spike (2026-05-08)

See `.planning/spikes/ez-pc-validation/SPEC.md` for the hypothesis and method.

Validates whether any Pc definition yields stable, discriminant, non-redundant DDM
parameters (v, a, t_er) on existing analytics.db engagement data.

Outputs `bench/EZ_PC_RESULTS.md` with GREEN/YELLOW/RED verdict per Pc candidate.
"""

from __future__ import annotations

import math
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

import numpy as np

# Use repo-relative paths so the script runs from the repo root.
REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "analytics.db"
RESULTS_PATH = REPO_ROOT / "bench" / "EZ_PC_RESULTS.md"

# EZ-Diffusion scale parameter (Wagenmakers 2007 convention)
S = 0.1

# Phase 6 ungradeable gate: drop engagements with rt_visible_to_hit_ms > 1500ms
RT_CAP_MS = 1500.0

# Bootstrap configuration
BOOTSTRAP_N = 1000
RNG_SEED = 20260508

# Players known to have sufficient sample sizes (peek only per data audit 2026-05-08)
DONK_SID = 76561198386265483
KARRIGAN_SID = 76561197989430253


# ---------------------------------------------------------------------------
# EZ-Diffusion closed-form math (Wagenmakers, van der Maas & Grasman 2007)
# ---------------------------------------------------------------------------

@dataclass
class EZParams:
    v: float
    a: float
    t_er: float
    n: int
    pc: float
    mrt_s: float
    vrt_s: float


def ez_diffusion(rt_correct_s: np.ndarray, pc: float, n_total: int) -> EZParams | None:
    """Closed-form EZ-Diffusion fit.

    rt_correct_s: RTs of correct trials in seconds (motor + decision time)
    pc: proportion correct in (0, 1) — values at {0, 1} are edge-corrected
    n_total: total trial count (for edge correction)

    Returns None if fit is degenerate (insufficient data, Pc at exact 0.5, etc).
    """
    if rt_correct_s.size < 2 or n_total < 5:
        return None

    # Edge correction (Stafford 2009 form): Pc==0 or Pc==1 makes logit blow up.
    if pc <= 0:
        pc = 1.0 / (2.0 * n_total)
    elif pc >= 1:
        pc = 1.0 - 1.0 / (2.0 * n_total)

    # Pc at exact 0.5 makes drift undefined in the closed form.
    if abs(pc - 0.5) < 1e-6:
        return None

    mrt = float(np.mean(rt_correct_s))
    vrt = float(np.var(rt_correct_s, ddof=1))
    if vrt <= 0:
        return None

    # Wagenmakers 2007 Eqns 4–7
    L = math.log(pc / (1.0 - pc))
    x = L * (L * pc * pc - L * pc + pc - 0.5) / vrt
    v_mag = (abs(x)) ** 0.25
    if v_mag < 1e-9:
        return None
    v = math.copysign(S * v_mag, pc - 0.5)

    a = (S * S) * L / v
    y = -v * a / (S * S)

    # Mean decision time (Eqn 9)
    mdt = (a / (2.0 * v)) * ((1.0 - math.exp(y)) / (1.0 + math.exp(y)))
    t_er = mrt - mdt

    return EZParams(
        v=float(v),
        a=float(a),
        t_er=float(t_er),
        n=n_total,
        pc=pc,
        mrt_s=mrt,
        vrt_s=vrt,
    )


# ---------------------------------------------------------------------------
# Data extraction
# ---------------------------------------------------------------------------

@dataclass
class Trial:
    rt_ms: float
    crosshair_deg: float | None
    bullets_hit: int | None        # from duel_attempts join (None if no match)
    was_killed: int | None         # from duel_attempts join (None if no match)


def fetch_trials(player_sid: int, engagement_type: str = "peek") -> list[Trial]:
    """Pull engagements joined to duel_attempts (best-effort tick-proximity match)."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    rows = cur.execute(
        """
        SELECT
            e.rt_visible_to_hit_ms,
            e.crosshair_angle_at_t0_deg,
            d.bullets_hit,
            d.was_killed
        FROM engagements e
        LEFT JOIN duel_attempts d
          ON e.player_steamid = d.player_steamid
         AND e.match_id = d.match_id
         AND ABS(d.t0_tick - COALESCE(e.t0_manual_tick, 0)) <= 10
        WHERE e.player_steamid = ?
          AND e.engagement_type = ?
          AND e.rt_visible_to_hit_ms IS NOT NULL
          AND e.rt_visible_to_hit_ms <= ?
        """,
        (player_sid, engagement_type, RT_CAP_MS),
    ).fetchall()
    conn.close()
    return [
        Trial(
            rt_ms=float(r[0]),
            crosshair_deg=float(r[1]) if r[1] is not None else None,
            bullets_hit=int(r[2]) if r[2] is not None else None,
            was_killed=int(r[3]) if r[3] is not None else None,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Pc definitions
# ---------------------------------------------------------------------------

def pc1_first_shot_hit(t: Trial) -> bool | None:
    if t.bullets_hit is None:
        return None
    return t.bullets_hit > 0


def pc2_won_duel(t: Trial) -> bool | None:
    if t.was_killed is None:
        return None
    return t.was_killed == 1


def pc3_factory(threshold_deg: float) -> Callable[[Trial], bool | None]:
    def _pc(t: Trial) -> bool | None:
        if t.crosshair_deg is None:
            return None
        return t.crosshair_deg < threshold_deg

    _pc.__name__ = f"pc3_crosshair_lt_{threshold_deg:g}"
    return _pc


PC_CANDIDATES: dict[str, Callable[[Trial], bool | None]] = {
    "pc1_first_shot_hit": pc1_first_shot_hit,
    "pc2_won_duel": pc2_won_duel,
    "pc3a_crosshair_lt_3deg": pc3_factory(3.0),
    "pc3b_crosshair_lt_5deg": pc3_factory(5.0),
    "pc3c_crosshair_lt_8deg": pc3_factory(8.0),
    # pc4 (engagement_started) skipped — trivially Pc=1.0, degenerate.
}


# ---------------------------------------------------------------------------
# Fit + bootstrap stability
# ---------------------------------------------------------------------------

def fit_pc(trials: list[Trial], pc_fn: Callable[[Trial], bool | None]) -> EZParams | None:
    """Apply Pc fn to trials, drop unclassifiable, fit EZ."""
    classified = [(t.rt_ms, pc_fn(t)) for t in trials]
    classified = [(rt, c) for rt, c in classified if c is not None]
    if len(classified) < 30:
        return None
    rts_correct_s = np.array([rt / 1000.0 for rt, c in classified if c], dtype=float)
    pc = sum(1 for _, c in classified if c) / len(classified)
    return ez_diffusion(rts_correct_s, pc, n_total=len(classified))


def bootstrap_ci(
    trials: list[Trial],
    pc_fn: Callable[[Trial], bool | None],
    n_iter: int = BOOTSTRAP_N,
) -> dict[str, dict[str, float]] | None:
    """Bootstrap CI95 for v, a, t_er. Returns None if base fit fails."""
    base = fit_pc(trials, pc_fn)
    if base is None:
        return None

    rng = np.random.default_rng(RNG_SEED)
    n = len(trials)
    samples: dict[str, list[float]] = {"v": [], "a": [], "t_er": []}
    failures = 0
    for _ in range(n_iter):
        idx = rng.integers(0, n, size=n)
        resampled = [trials[int(i)] for i in idx]
        fit = fit_pc(resampled, pc_fn)
        if fit is None:
            failures += 1
            continue
        samples["v"].append(fit.v)
        samples["a"].append(fit.a)
        samples["t_er"].append(fit.t_er)

    if not samples["v"]:
        return None

    out: dict[str, dict[str, float]] = {}
    for key, point_val in [("v", base.v), ("a", base.a), ("t_er", base.t_er)]:
        arr = np.array(samples[key])
        lo = float(np.percentile(arr, 2.5))
        hi = float(np.percentile(arr, 97.5))
        width = hi - lo
        ratio = abs(width / point_val) if abs(point_val) > 1e-9 else float("inf")
        out[key] = {
            "point": float(point_val),
            "ci_lo": lo,
            "ci_hi": hi,
            "ci_width": float(width),
            "ratio_width_over_point": float(ratio),
        }
    out["_meta"] = {"n_iter": n_iter, "n_failed": failures, "n_total": n}  # type: ignore
    return out


# ---------------------------------------------------------------------------
# Synthetic recovery (random-walk DDM simulator)
# ---------------------------------------------------------------------------

def simulate_ddm(
    v_true: float,
    a_true: float,
    t_er_true: float,
    n_trials: int,
    dt: float = 0.001,
    max_t: float = 5.0,
    seed: int = RNG_SEED,
) -> tuple[np.ndarray, np.ndarray]:
    """2-AFC random-walk diffusion. Returns (rt_seconds, correct_bool)."""
    rng = np.random.default_rng(seed)
    rts = np.zeros(n_trials)
    correct = np.zeros(n_trials, dtype=bool)
    half_a = a_true / 2.0
    sqrt_dt = math.sqrt(dt)
    for i in range(n_trials):
        x = 0.0
        t = 0.0
        while -half_a < x < half_a and t < max_t:
            x += v_true * dt + S * rng.standard_normal() * sqrt_dt
            t += dt
        rts[i] = t + t_er_true
        correct[i] = x >= half_a
    return rts, correct


def recovery_test(n_trials: int = 100, n_runs: int = 30) -> dict:
    """Generate synthetic trials with known params, recover via EZ, report bias."""
    truths = [
        (0.18, 0.12, 0.30),  # easy task, careful threshold
        (0.30, 0.15, 0.25),  # high drift, high threshold
        (0.10, 0.10, 0.40),  # low drift, hair trigger
    ]
    out = {"n_trials": n_trials, "n_runs": n_runs, "results": []}
    for v_t, a_t, t_t in truths:
        recoveries = []
        for run in range(n_runs):
            rts, correct = simulate_ddm(v_t, a_t, t_t, n_trials, seed=RNG_SEED + run)
            pc = float(np.mean(correct))
            rts_correct = rts[correct]
            if rts_correct.size < 2:
                continue
            fit = ez_diffusion(rts_correct, pc, n_total=n_trials)
            if fit is None:
                continue
            recoveries.append((fit.v, fit.a, fit.t_er))
        if not recoveries:
            out["results"].append({
                "true": {"v": v_t, "a": a_t, "t_er": t_t},
                "recovered": None,
                "n_successful_runs": 0,
            })
            continue
        arr = np.array(recoveries)
        means = arr.mean(axis=0)
        biases_pct = [(means[i] - t) / t * 100.0 for i, t in enumerate([v_t, a_t, t_t])]
        out["results"].append({
            "true": {"v": v_t, "a": a_t, "t_er": t_t},
            "recovered_mean": {"v": float(means[0]), "a": float(means[1]), "t_er": float(means[2])},
            "bias_pct": {"v": biases_pct[0], "a": biases_pct[1], "t_er": biases_pct[2]},
            "n_successful_runs": len(recoveries),
        })
    return out


# ---------------------------------------------------------------------------
# Validity verdict
# ---------------------------------------------------------------------------

def classify_pc(
    boot_donk: dict | None,
    boot_karrigan: dict | None,
    convergent_corr: float | None,
) -> tuple[str, list[str]]:
    """Apply pass/fail rules from SPEC. Returns (verdict, reasons)."""
    reasons = []
    pass_count = 0
    n_checks = 0

    # Stability (combined across both players)
    n_checks += 1
    if boot_donk and boot_karrigan:
        ratios = []
        for boot in (boot_donk, boot_karrigan):
            for key in ("v", "a", "t_er"):
                ratios.append(boot[key]["ratio_width_over_point"])
        max_ratio = max(ratios)
        if max_ratio <= 0.30:
            pass_count += 1
            reasons.append(f"STABILITY PASS (max CI95 width / point = {max_ratio:.2f})")
        else:
            reasons.append(f"STABILITY FAIL (max CI95 width / point = {max_ratio:.2f}, need <=0.30)")
    else:
        reasons.append("STABILITY UNAVAILABLE (one or both fits failed)")

    # Discriminant (donk vs karrigan separation)
    n_checks += 1
    if boot_donk and boot_karrigan:
        # Cohen's d proxy: (point_donk - point_karrigan) / pooled CI half-width
        d_separations = []
        for key in ("v", "a", "t_er"):
            diff = abs(boot_donk[key]["point"] - boot_karrigan[key]["point"])
            half_donk = boot_donk[key]["ci_width"] / 2.0
            half_karrigan = boot_karrigan[key]["ci_width"] / 2.0
            pooled = math.sqrt(half_donk ** 2 + half_karrigan ** 2)
            d = diff / pooled if pooled > 1e-9 else 0.0
            d_separations.append((key, d))
        max_d = max(d for _, d in d_separations)
        if max_d > 1.0:  # clear separation by bootstrap CI
            pass_count += 1
            reasons.append(
                "DISCRIMINANT PASS ("
                + ", ".join(f"{k}: d={d:.2f}" for k, d in d_separations)
                + ")"
            )
        else:
            reasons.append(
                "DISCRIMINANT FAIL — donk vs karrigan ("
                + ", ".join(f"{k}: d={d:.2f}" for k, d in d_separations)
                + ")"
            )
    else:
        reasons.append("DISCRIMINANT UNAVAILABLE")

    # Convergent (corr v vs hit_rate). With only 2 players we cannot compute a
    # population correlation — this check degrades to a qualitative comparison.
    n_checks += 1
    if convergent_corr is None:
        reasons.append(
            "CONVERGENT DEGRADED — only 2 players in DB peek (>=50 trials), "
            "population corr undefined. Treat as N/A."
        )
    else:
        if 0.30 <= convergent_corr <= 0.75:
            pass_count += 1
            reasons.append(f"CONVERGENT PASS (corr={convergent_corr:.2f})")
        elif convergent_corr > 0.85:
            reasons.append(f"CONVERGENT FAIL — REDUNDANT with hit_rate (corr={convergent_corr:.2f})")
        else:
            reasons.append(f"CONVERGENT FAIL — {convergent_corr:.2f}")

    # Recovery is per-run, applied to all Pc together — we report it once at top
    # level, not per Pc.

    if pass_count >= 2:
        verdict = "GREEN"
    elif pass_count == 1:
        verdict = "YELLOW"
    else:
        verdict = "RED"
    return verdict, reasons


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"[ez-pc-spike] DB: {DB_PATH}", flush=True)
    if not DB_PATH.exists():
        print(f"[ez-pc-spike] ERROR: {DB_PATH} not found", file=sys.stderr)
        sys.exit(1)

    donk_trials = fetch_trials(DONK_SID, "peek")
    karrigan_trials = fetch_trials(KARRIGAN_SID, "peek")
    print(
        f"[ez-pc-spike] donk peek n={len(donk_trials)}, karrigan peek n={len(karrigan_trials)}",
        flush=True,
    )

    pc_results: dict[str, dict] = {}
    for pc_name, pc_fn in PC_CANDIDATES.items():
        print(f"[ez-pc-spike] Pc = {pc_name}", flush=True)
        donk_fit = fit_pc(donk_trials, pc_fn)
        karrigan_fit = fit_pc(karrigan_trials, pc_fn)

        donk_boot = bootstrap_ci(donk_trials, pc_fn) if donk_fit else None
        karrigan_boot = bootstrap_ci(karrigan_trials, pc_fn) if karrigan_fit else None

        verdict, reasons = classify_pc(donk_boot, karrigan_boot, convergent_corr=None)

        pc_results[pc_name] = {
            "donk_fit": donk_fit,
            "karrigan_fit": karrigan_fit,
            "donk_boot": donk_boot,
            "karrigan_boot": karrigan_boot,
            "verdict": verdict,
            "reasons": reasons,
        }
        print(f"[ez-pc-spike]   verdict: {verdict}", flush=True)

    print("[ez-pc-spike] running synthetic recovery...", flush=True)
    recovery = recovery_test(n_trials=100, n_runs=30)

    write_results_md(donk_trials, karrigan_trials, pc_results, recovery)
    print(f"[ez-pc-spike] wrote {RESULTS_PATH}", flush=True)


def fmt_param(boot: dict | None, key: str) -> str:
    if boot is None:
        return "—"
    p = boot[key]
    return f"{p['point']:.4f} [{p['ci_lo']:.4f}, {p['ci_hi']:.4f}] (w/p={p['ratio_width_over_point']:.2f})"


def write_results_md(
    donk_trials: list[Trial],
    karrigan_trials: list[Trial],
    pc_results: dict[str, dict],
    recovery: dict,
) -> None:
    lines: list[str] = []
    lines.append("# EZ-Diffusion Pc Validation — Results")
    lines.append("")
    lines.append("**Spike spec:** `.planning/spikes/ez-pc-validation/SPEC.md`")
    lines.append("**Generated:** 2026-05-08 (run via `python bench/ez_pc_validation.py`)")
    lines.append("")
    lines.append("## Data summary")
    lines.append("")
    lines.append("| Player | engagement_type | N (rt<=1500ms) |")
    lines.append("|-|-|-|")
    lines.append(f"| donk | peek | {len(donk_trials)} |")
    lines.append(f"| karrigan | peek | {len(karrigan_trials)} |")
    lines.append("")
    lines.append(
        "**Constraint vs SPEC:** SPEC asked for >=3 players. analytics.db has only 2 players "
        "with >=50 engagements (rt<=1500ms gate applied), peek only. hold engagement_type "
        "has zero rows in `engagements` with valid RT. Discriminant test degraded to pairwise; "
        "convergent (population corr v vs hit_rate) reported as DEGRADED."
    )
    lines.append("")

    lines.append("## Synthetic recovery (sanity check on EZ math)")
    lines.append("")
    lines.append(
        f"N trials per run: {recovery['n_trials']}, runs per condition: {recovery['n_runs']}"
    )
    lines.append("")
    lines.append("| true v | true a | true t_er | recovered v | recovered a | recovered t_er | v bias % | a bias % | t_er bias % | n runs |")
    lines.append("|-|-|-|-|-|-|-|-|-|-|")
    for r in recovery["results"]:
        if r.get("recovered_mean") is None:
            lines.append(
                f"| {r['true']['v']:.2f} | {r['true']['a']:.2f} | {r['true']['t_er']:.2f} "
                f"| FAIL | FAIL | FAIL | — | — | — | 0 |"
            )
        else:
            lines.append(
                f"| {r['true']['v']:.2f} | {r['true']['a']:.2f} | {r['true']['t_er']:.2f} "
                f"| {r['recovered_mean']['v']:.3f} | {r['recovered_mean']['a']:.3f} | {r['recovered_mean']['t_er']:.3f} "
                f"| {r['bias_pct']['v']:+.1f} | {r['bias_pct']['a']:+.1f} | {r['bias_pct']['t_er']:+.1f} "
                f"| {r['n_successful_runs']} |"
            )
    lines.append("")
    bias_threshold = 15.0
    all_within = all(
        r.get("recovered_mean") is not None
        and all(abs(r.get("bias_pct", {}).get(k, 999)) <= bias_threshold for k in ("v", "a", "t_er"))
        for r in recovery["results"]
    )
    lines.append(
        f"**Recovery verdict:** {'PASS' if all_within else 'FAIL'} "
        f"(SPEC requires |bias| <= {bias_threshold:.0f}% on all 3 params at N=100)"
    )
    lines.append("")

    lines.append("## Per-Pc results")
    lines.append("")
    for pc_name, res in pc_results.items():
        lines.append(f"### {pc_name}")
        lines.append("")
        donk_boot = res["donk_boot"]
        kar_boot = res["karrigan_boot"]
        donk_fit = res["donk_fit"]
        kar_fit = res["karrigan_fit"]
        lines.append("| Player | Pc | N | v (CI95) | a (CI95) | t_er (CI95) |")
        lines.append("|-|-|-|-|-|-|")
        donk_pc = f"{donk_fit.pc:.3f}" if donk_fit else "—"
        donk_n = donk_fit.n if donk_fit else 0
        kar_pc = f"{kar_fit.pc:.3f}" if kar_fit else "—"
        kar_n = kar_fit.n if kar_fit else 0
        lines.append(
            f"| donk | {donk_pc} | {donk_n} | "
            f"{fmt_param(donk_boot, 'v')} | {fmt_param(donk_boot, 'a')} | {fmt_param(donk_boot, 't_er')} |"
        )
        lines.append(
            f"| karrigan | {kar_pc} | {kar_n} | "
            f"{fmt_param(kar_boot, 'v')} | {fmt_param(kar_boot, 'a')} | {fmt_param(kar_boot, 't_er')} |"
        )
        lines.append("")
        lines.append(f"**Verdict: {res['verdict']}**")
        lines.append("")
        for reason in res["reasons"]:
            lines.append(f"- {reason}")
        lines.append("")

    lines.append("## Summary verdict matrix")
    lines.append("")
    lines.append("| Pc | Verdict |")
    lines.append("|-|-|")
    for pc_name, res in pc_results.items():
        lines.append(f"| {pc_name} | **{res['verdict']}** |")
    lines.append("")

    greens = [n for n, r in pc_results.items() if r["verdict"] == "GREEN"]
    yellows = [n for n, r in pc_results.items() if r["verdict"] == "YELLOW"]
    reds = [n for n, r in pc_results.items() if r["verdict"] == "RED"]

    lines.append("## Recommendation")
    lines.append("")
    if greens:
        lines.append(f"**At least one Pc passed: {', '.join(greens)}.**")
        lines.append("")
        lines.append(
            "Route: `/gsd-spec-phase` for Phase 10 (Longitudinal DDM lens). "
            "Pc choice locked to highest-passing candidate. Acknowledge constraint: "
            "validation done on peek + 2 players only; revisit when more players reach >=50 trials."
        )
    elif yellows:
        lines.append(f"**No Pc fully passed; YELLOW: {', '.join(yellows)}.**")
        lines.append("")
        lines.append(
            "Route options: (1) hybrid Pc spike-2 combining best two YELLOW signals, "
            "(2) narrow Phase 10 scope to peek-only with explicit experimental disclaimer, "
            "(3) defer until DB scale increases (stability check may pass with more players)."
        )
    else:
        lines.append("**All Pc REJECTED.**")
        lines.append("")
        lines.append(
            "Route: archive idea as note. DDM (EZ-Diffusion) is not a viable feature for cs2-ddm "
            "given current data shape. Seeds B + C also become inactive (their prerequisite is GREEN spike)."
        )
    lines.append("")
    lines.append("## Caveats / known gaps")
    lines.append("")
    lines.append(
        "- **Convergent check degraded** (only 2 players). Cannot compute population corr "
        "v vs hit_rate. Verdict relies on stability + discriminant only — 2/3 checks instead of 3/3."
    )
    lines.append(
        "- **Hold engagement_type unsupported** at current data scale. Findings apply to peek only."
    )
    lines.append(
        "- **pc1/pc2 lose ~20% of engagements** to the `engagements` <-> `duel_attempts` "
        "tick-proximity join (405/502 matched for donk peek). Pc=NaN trials silently dropped."
    )
    lines.append(
        "- **EZ scale param S=0.1** is the Wagenmakers 2007 convention. Different choice would "
        "rescale `v` and `a` proportionally; ratios and verdicts unchanged."
    )

    RESULTS_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
