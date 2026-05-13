# Design: `/marketing-weekly` skill for Djok

**Date:** 2026-05-07  
**Product:** Djok (CS2 reaction time analysis, FACEIT L8-10)  
**Stage:** Pre-launch — zero traffic, zero leads

---

## Problem

No automated marketing pipeline exists. Content needs to be created, distributed, and improved based on engagement — but the audience (FACEIT L8-10) is skeptical and technical, requiring data-first copy rather than generic marketing.

## Goal

A single Claude Code skill (`/marketing-weekly`) that generates a full weekly marketing output: community opportunities, platform-specific post drafts, and landing page CTA variants — with a self-improving loop via `marketing/log.md`.

---

## Architecture

### Orchestrator: `/marketing-weekly`

Reads `marketing/log.md` (if exists), then spawns 3 agents in parallel:

| Agent | Input | Output |
|-|-|-|
| Research | WebSearch: Reddit/Twitter (7-day window), terms: "CS2 reaction time", "FACEIT aim analysis", "donk stats" | 3–5 opportunity threads + competitive mentions summary |
| Audit | `marketing/log.md` | 3–5 engagement patterns from past posts (skipped on first run if log empty) |
| SEO + Conversion | `landing/index.html`, `landing/data.js` | 1–2 CTA A/B variants + keyword gap suggestions |

Orchestrator synthesizes results → writes `marketing/WEEKLY.md` → presents log entry template to user.

### No auto-publish

User is always the final gate: Claude generates → user edits → user publishes manually → user fills engagement notes in log entry → next run uses those notes.

---

## File Schemas

### `marketing/log.md`

Append-only. One entry per week. User fills engagement notes after posting.

```markdown
## YYYY-MM-DD

### Posted
- [Platform] Title/description
  Engagement: [upvotes/likes/replies]
  What worked: [specific observation]
  What flopped: [specific observation]

### Notes
- Best performing hook format: [pattern]
- Audience responds to: [observation]
- Avoid: [anti-pattern]
```

### `marketing/WEEKLY.md`

Generated output. Overwritten each run.

```markdown
# Marketing Week: YYYY-MM-DD

## Opportunities
[3–5 threads with engagement angle per thread]

## Drafts

### Reddit (r/GlobalOffensive)
[EN post, data-first, no marketing tone]

### Twitter/X
[hook line + 1 hard number + image prompt description]

### Telegram (RU)
[RU text, technical tone, monospace numbers]

### Discord
[short message, not a post — fits in a chat reply]

## Landing A/B Proposals
Current CTA: [current text]
Variant A: [proposal]
Variant B: [proposal]

## Log entry template
[pre-filled template for user to paste into log.md after posting]
```

---

## Self-Improving Loop

| Log.md state | Audit agent behavior |
|-|-|
| Empty / missing | Skips pattern extraction; research + SEO agents still run |
| 1–2 entries | Surfaces basic patterns ("number in headline worked") |
| 4+ entries | Specific rules ("83 demos framing = credibility signal; avoid 'improve aim' framing") |

Over time, audit agent output feeds directly into draft tone and hook selection.

---

## Target Channels

All 4 confirmed by user:

| Channel | Language | Format | Audience fit |
|-|-|-|-|
| Reddit r/GlobalOffensive | EN | Long-form analysis post | High — loves data deep dives |
| Twitter/X | EN | Hook + stat thread | Medium — viral potential via quote-RT |
| Discord (FACEIT/regional) | EN/RU | Short community message | High — direct access to L8-10 |
| Telegram (RU/KZ) | RU | Data thread | Highest — closest to user's network |

---

## Constraints

- WebSearch + WebFetch permissions required for research agent
- `marketing/` directory created on first run if missing
- No cron — skill-driven only (user triggers manually)
- No external API keys required (uses Claude's built-in web access)
- Skill file location: `.claude/skills/marketing-weekly.md`

---

## Out of Scope

- Auto-posting to any platform
- Analytics API integrations (GA, Twitter API)
- Email marketing / newsletter
- Paid ads management
