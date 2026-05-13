# Reddit r/GlobalOffensive draft — m0NESY SUPERSTRIKE natural experiment

**Status:** DRAFT — not posted as of 2026-05-13. User to review.

**Title options:**
- A: I measured m0NESY's reaction time before/after the SUPERSTRIKE switch. The data is weird.
- B: 21 demos, 2 tournaments: did m0NESY's mouse switch help his reaction time?

---

Lots of debate about whether the Logitech PRO X2 SUPERSTRIKE's 30ms click latency drop actually matters. I had a way to test it without theorycrafting: m0NESY switched mice between IEM Rio and PGL Astana. Same player, same surface, ~6 weeks apart. Natural experiment.

I parsed 21 demos (11 IEM Rio + 10 PGL Astana) and split his reaction into two phases per duel:

- **T0→T1**: enemy becomes visible → m0NESY starts moving crosshair toward enemy. Pure perception/reaction.
- **T1→T2**: starts moving crosshair → first registered hit. Mechanical aim + click.

A click-latency improvement should propagate to T1→T2 (faster click → faster registered hit), NOT T0→T1 (your eyes don't get faster from a better mouse).

**Results** (median, m0NESY only, peek scenarios including moving enemies up to 300 u/s):

| | IEM Rio (before, N=73) | PGL Astana (after, N=38) | Δ |
|-|-|-|-|
| T0→T1 (reaction) | 203 ms | 203 ms | 0 |
| T1→T2 (mechanic) | 344 ms | 211 ms | **−133 ms** |
| T0→T2 (total) | 547 ms | 398 ms | −149 ms |

Reaction phase didn't move. Mechanic phase dropped 133ms.

**Caveats — read these:**
- 133ms is way bigger than the 30ms click latency improvement alone. Most of the drop = 6 weeks of practice + roster context. Can't isolate the mouse.
- Astana mean T1→T2 is 397ms vs median 211ms — long outlier tail (likely re-aim scenarios). Median is the honest number.
- N=38 Astana is below the ≥30 stationary-only threshold I'd want for a confident point estimate.
- With stricter filter (only stationary enemies, ≤120 u/s) N drops to 15 and the signal flips. Threshold choice matters here.

**Method:** BVH + AABB ray casting against enemy hitbox for T0 (the `m_bSpotted` flag is broken in CS2 GOTV — don't trust it). Viewangle delta for T1. `player_hurt` event for T2. 64-tick demos, ~15.6ms granularity.

**Honest takeaway:** I can't prove SUPERSTRIKE caused the drop. What I can say is the drop is in the phase where hardware would propagate. T0→T1 staying at 203ms is the structurally interesting part — rules out "feels snappier → plays better" placebo bleeding into reaction.

Built this for Djok [LINK]. DM if you want your own split.

---

## Edit decisions for user

1. **Title A or B?** A has more news-hook punch, B is more methodology-honest.
2. **CTA line?** Keep / soften ("If anyone's building something similar, would love to compare notes") / drop entirely.
3. **Djok URL** — fill in.
4. **Adapt to RU for Telegram cohort?** Drop "[FILL IN]" placeholders from `marketing/WEEKLY.md`.

## Data provenance

- Wide-vel CSV: `D:\Obsidian\opacity\40_Projects\cs2-ddm\monesy_wide_vel.csv` (139 rows, group column)
- Standard-vel: `analytics.db` engagements table, filtered by player_steamid=76561198074762801 + demo_name LIKE pattern
- Monesy SteamID: 76561198074762801 (verified via `reference_player_steam_ids.md`)
- Demos: `D:\Obsidian\opacity\40_Projects\for_analysis\monesy-pgl-astana\` (10) + `monesy-pre-pgl-astana(iem-rio)\` (11)
