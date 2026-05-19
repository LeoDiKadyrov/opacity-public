# Brainstorm Negative Targets

Auto-injected into `src/worker/prompts/brainstorm_prompt.py` to suppress idea patterns the user has explicitly rejected or which the 2026-05-18 review of 630 ideas surfaced as recurring noise.

Update this file when:
- A new pattern of low-value ideas appears in multiple drafts
- A project goes dormant (no active development for >3 months)
- The user adds a new "do not propose" rule

The brainstorm prompt reads this file at generation time — changes take effect on the next draft.

## Hard suppression (DO NOT propose)

- **ai_interview_coach** — project dormant. PROJECT.md says "TODO: describe project goal". The 2026-05-18 review found 43 ideas targeting it with **zero** fit verdicts. Skip until the user fills in the project goal.
- **intercept** — project undefined-spec. Same dormant-project policy.
- **Warm-network DMs / outreach automation** — Maria Данина, Veronica, Open Doors leads, cohort psy_5, etc. The user controls warm communications directly. The `/redblue-audit` skill may flag gaps, but do not draft outreach.
- **Cross-project utility libraries WITHOUT a named concrete consumer** — "universal filter", "GRADE-lite", "BT-judge", "skill-bench", "benchmark-builder", "explain-like-new" patterns. Premature abstraction. Wait until ≥1 project ships a concrete need.
- **Solution-without-problem** — anti-fingerprint scrapers when collectors use APIs not UI-scraping; generative-ancestor video for `pedigree` (fake-genealogy risk); pseudoscience formulae (T.E.C. = V·(C·I)+A with no academic backing).
- **Already-shipped autorss_feed features** — anything that duplicates v1.0-v1.9 SHIPPED phases or open backlog 999.x items. Cross-check the project's `.planning/ROADMAP.md` BEFORE proposing. Common duplicates: MI(score, reaction) per backend (999.26), sigmoid-gate router (999.29), prompt α-blend (999.30), channel quality auto-tune (999.41), GA prompt race (999.46), dwell-time beacon (999.53), reader-role buffer (999.25).

## Soft de-prioritization (PROPOSE LESS)

- **autorss_feed** — the brainstorm prompt has a known 3x-over-uniform bias toward this project (15% of ideas across 20 projects; uniform would be 5%). Aim for ≤2 autorss_feed ideas per draft of 5-7. Lean into the other 19 projects where natural.
- **Djok-landing monetization** without T2 analyzer validation — revenue features (tilt detector subscriptions, replay watermarking) presume product-market fit on the underlying CS2 analyzer. Validate the analyzer first.

## Encourage (PROPOSE MORE WHERE NATURAL)

These verdict patterns scored highest in the 2026-05-18 review:

- **psyskills clinical safety + outcome tracking** — risk gates (C-SSRS), outcome scales (PHQ-9/GAD-7), case classification. Maria Данина + cohort psy_5 are real validators.
- **DBO_Faktura_KB team tooling** — 24/7 Q&A bot, golden retrieval eval, why-this-answer trace. 10-person team pain.
- **moex_tracker RU-specific differentiators** — NL screener, sector-bundle backtests, IFRS extraction. Real moat vs Pulse/BCS.
- **cs2-ddm B2C premium signals** — real-time tilt detection, role-similarity fingerprint. T2 layer ready.
- **pedigree time-critical workflows** — interview urgency queue, granny prompt-tree gap detector. Grandmother window is closing.

## How this file feeds back

`src/worker/prompts/brainstorm_prompt.py` reads this file when present. Content is injected verbatim as a `## Negative targets` block in the brainstorm prompt before idea generation. The file is treated as authoritative — if it is missing or empty, no negative-target block is added (graceful degradation, brainstorm still runs).

Source: 2026-05-18 review of 630 ideas across drafts 58-151. Update cadence: as new patterns surface, manually edit this file. Future iteration may auto-update from user's Promote/Drop/Spike decisions accumulated in `brainstorm_decisions`.
