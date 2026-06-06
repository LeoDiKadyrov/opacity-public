# Phase OF-1 — Context: Death Diagnosis + Outcome-First Design + Code Map

This is the knowledge a fresh session needs to execute `OF-1-00-PLAN.md`. Read it fully before writing code.

---

## 1. Death diagnosis (why geometry-first failed) — with exact code refs

The CS2 demo provides **ground truth only for events**, each carrying explicit attacker+victim steamids:
- `player_hurt` (attacker_steamid, user_steamid=victim, tick, dmg, weapon)
- `player_death` (attacker_steamid, user_steamid=victim, tick)
- `weapon_fire` (player tick stream)
- `parse_ticks` props: X/Y/Z, pitch, yaw, steamid, is_alive, team_num, duck_amount, velocity.

It does NOT provide: *who you were dueling*, *when you perceived them*, *whether you were holding*. djok needs those for its product, so it **fabricates** them from proxies — then joins real outcomes onto the fabrication.

### Killer 1 — opponent is a geometric guess (the 94%)
`duel_attempts.py`:
- `find_attempts()` (L87) takes ALL the player's `weapon_fire` ticks; `_cluster_fires()` (L152) groups them into temporal clusters — **purely by time gaps, never by what was shot**. Spray-into-wall, prefire, smoke-tap, real kill → all become "duels".
- `_process_cluster()` (L167) builds a window around the cluster and calls `t0_detector.find_first_visible_enemy_in_window()` (L180).
- `t0_detector.py:291` `find_first_visible_enemy_in_window()` scans tick-by-tick; at the FIRST tick any enemy is BVH-visible, returns it; ties broken by smallest crosshair angle: `enemy_sid, angle = min(visible, key=lambda x: x[1])` (L314).
- **There is zero link between the weapon_fire and the chosen enemy.** Closest-visible ≠ who you shot.
- The code confesses it: `DuelAttempt` comment L44–48 — `hurt_victims_in_window` exists "to detect target misidentification where BVH-selected enemy_steamid differs from who player was really shooting at."
- Outcomes are then computed against the WRONG enemy: `_check_kill()` (L219, `user_steamid == enemy_sid`) and `_count_bullets()` (L248, `user_steamid == enemy_sid`). Wrong enemy → was_killed=False / bullets_hit=0 even when the real duel was won. **Empirically: only 5.9% of donk's hold rows have a hit on the nominal enemy.**

### Killer 2 — engagement_type is a proxy
`duel_attempts.py:192` `engagement = "peek" if player_velocity >= VELOCITY_PEEK_THRESHOLD_UPS else "hold"`. "hold" = merely "slow at T0" (reloading, walking, mid-spray) — not tactically holding. Slicing on it = proxy on top of fiction.

### Killer 3 — reaction time (T0-T1-T2) is a motion proxy
`ddm_analyzer.py:512` `_detect_t1()`. L621: `moving_towards = nxt_dist < (curr_dist - T1_MOVING_TOWARDS_TOLERANCE)`. T1 fires when crosshair angular distance to enemy decreases. "Moving toward" ≠ "reacting". `config.py:145 T1_MOVING_TOWARDS_TOLERANCE = 0.01°` is BELOW demo angular quantization (~0.022°) → fires on noise. With `T1_GRACE_MS=0` (config.py:132) T1 collapses to T0+1 tick (the 15.6ms pin, bug B-5).

### Why 370/370 tests stayed green
`.planning/codebase/TESTING.md:8`: "No integration tests against real .dem files — all tests use mocked/synthetic data." Tests validate the *math of the proxy*, never that the proxy corresponds to truth. The disease is invisible to the suite.

---

## 2. Outcome-first design (the inversion)

Anchor on ground-truth events; use geometry/kinematics ONLY to fill timing for a KNOWN pair.

1. **Collect real exchanges for player P.** From `player_hurt` + `player_death`, take every event where `attacker==P` OR `victim==P`. Each event names the real opponent E (the other steamid) — **ground truth, no guess**.
2. **Group into duel episodes.** Cluster these events by opponent E and time proximity (consecutive events vs the same E within ~`_KILL_CONFIRM_WINDOW_TICKS`≈320 / a tunable gap) into one duel. One episode = P-vs-E exchange.
3. **Outcome is ground truth.** From `player_death` within the episode: E died first → P WON; P died first → P LOST; neither → UNRESOLVED (exclude or bucket separately).
4. **Reaction timing, searched BACKWARD on the KNOWN enemy.** Now call `t0_detector.find_t0(all_ticks, P, enemy_steamid=E, search_start, search_end)` — BVH is *correct* here: it answers "when did P first see the KNOWN E", not "who is E". From first-visibility, find aim onset toward E (reuse `_detect_t1` logic conceptually, but on the real pair). v1 spike MAY defer reaction timing and just prove opponent+outcome+slice; reaction is refinement.
5. **peek/hold, now on real duels.** Initiator = who entered whose view / who moved first. Counter-peek/hold-success = P holding (static pre-contact) and E initiates → did P win (E died first)? Keep velocity proxy for v1 but it now rides on REAL duels.

**The 94% contamination cannot occur** because the opponent is never selected by geometry — it is read from the event that defines the exchange.

---

## 3. Ground-truth available for the spike

Re-parse ONLY (cheap, per-demo):
- `parse_events(["player_hurt", "player_death", "weapon_fire"])` → opponent + outcome + fire stream.
- `parse_ticks([...])` for the narrow reaction window only (optional in v1).

donk steamid = `76561198386265483`. Demos: `D:\Obsidian\opacity\40_Projects\for_analysis\` (mostly `spirit/`), 81 confirmed on disk for donk.

---

## 4. Reuse map (do NOT rebuild these)

| Need | Use | Note |
|-|-|-|
| Parse events | `DDMAnalyzer` parse path / direct `demoparser2.DemoParser(path).parse_events([...])` | parser core is solid |
| First-visible KNOWN enemy | `t0_detector.find_t0(...)` | correct given a KNOWN enemy |
| Demo→steamid mapping | `reference_player_steam_ids.md`, `reference_demo_corpus_locations.md` | in cs2-ddm memory |
| Reference scripts | `counter_peek_v1.py`, `counter_peek_v2_enrich.py` | uncommitted starting points |

## 5. Gotchas (this machine)

- Python launcher `py`, NOT `python`. Set `PYTHONUTF8=1` + `PYTHONIOENCODING=utf-8`; `sys.stdout.reconfigure(encoding="utf-8")` in scripts (cp1252 kills on `→` etc.).
- SteamID64 precision: coerce to `int64`, never float (pandas precision loss).
- `_KILL_CONFIRM_WINDOW_TICKS` = 320 ticks ≈ 5s @ 64-tick — reuse as the duel-episode grouping window.
- **TRIPWIRE:** do NOT touch / fix / re-run the T0-T1-T2 reaction methodology or the geometry-first `DuelAttemptFinder` opponent selection. The spike is a NEW standalone script. Production code stays untouched until OF-2 (post-gate).
- Spike is exploratory — minimal correctness check only; do not over-engineer (project has an explicit over-engineering-rejection rule).
