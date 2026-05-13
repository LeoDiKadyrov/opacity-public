# `/marketing-weekly` Skill — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill that generates a full weekly marketing output for Djok — community opportunities, platform-specific post drafts, CTA variants — with a self-improving loop via `marketing/log.md`.

**Architecture:** A markdown skill file (`.claude/skills/marketing-weekly.md`) instructs Claude to read prior engagement history, dispatch 3 parallel research/audit/SEO agents, and synthesize results into `marketing/WEEKLY.md`. State accumulates in `marketing/log.md` — the user fills engagement notes after each publish cycle, making the next run's audit agent smarter.

**Tech Stack:** Claude Code skill (markdown), no external dependencies. WebSearch/WebFetch used by research agent (Claude Code built-in tools).

---

## File Map

| Action | Path | Responsibility |
|-|-|-|
| Create | `marketing/log.md` | Persistent engagement memory — append-only |
| Create | `marketing/WEEKLY.md` | Generated output — overwritten each run |
| Create | `.claude/skills/marketing-weekly.md` | Skill definition — the full implementation |

---

## Task 1: Initialize `marketing/` directory + log schema

**Files:**
- Create: `marketing/log.md`

- [ ] **Step 1: Create `marketing/log.md` with empty first entry**

Create `marketing/log.md` with this exact content:

```markdown
# Djok Marketing Log

Append one entry per week after publishing. Fill engagement notes manually.

---

## Template (copy for each new week)

### YYYY-MM-DD

#### Posted

- [Platform] Title or description
  Engagement: [upvotes / likes / replies / DMs]
  What worked: [specific observation — hook format, data angle, framing]
  What flopped: [specific observation]

#### Notes

- Best hook format this week: [pattern]
- Audience responded to: [observation]
- Avoid next time: [anti-pattern]

---
```

- [ ] **Step 2: Commit**

```bash
git add marketing/log.md
git commit -m "feat(marketing): add marketing/ directory + log.md schema"
```

Expected: 1 file committed, `marketing/log.md` in repo.

---

## Task 2: Write the skill file

**Files:**
- Create: `.claude/skills/marketing-weekly.md`

- [ ] **Step 1: Create `.claude/skills/` directory if missing**

Check that `.claude/` exists (it does — settings.json lives there). Create `.claude/skills/` if absent.

- [ ] **Step 2: Create `.claude/skills/marketing-weekly.md`**

Create the file with this exact content:

````markdown
# /marketing-weekly — Djok Weekly Marketing Pipeline

Run the full weekly marketing pipeline for Djok. Takes ~3-5 minutes.

## What this produces

- `marketing/WEEKLY.md` — ready-to-use post drafts per channel + CTA A/B variants
- Updated log entry template appended to `marketing/log.md`

---

## Step 1: Load engagement memory

Check if `marketing/log.md` exists.

If it exists: read the full file. Extract:
- Hook formats that had high engagement (upvotes/likes mentioned)
- Framing or angles that flopped
- Explicit "avoid" rules the user noted
- Note how many weeks of data are present

If missing or empty: set audit_available = false. Proceed — audit section will be empty.

---

## Step 2: Dispatch 3 agents in parallel

Use the Agent tool to run all 3 simultaneously. Launch all 3 before waiting for any result.

### Agent 1 — Research

Prompt:
```
You are a community research agent for Djok — a CS2 reaction time analysis tool targeting FACEIT level 8-10 players. These players are skeptical of marketing copy. They respond to hard data (milliseconds, tick counts, geometric detection methods).

Search the following for content from the past 7 days:

1. Reddit r/GlobalOffensive — search: "reaction time", "aim analysis", "pro player", "donk CS2"
2. Twitter/X — search: "CS2 reaction", "FACEIT aim", "pro aim comparison", "donk stats"
3. Any competitor mentions: Leetify, Aim Lab, tracker.gg CS2 features

For each platform, identify 1-2 threads where Djok data adds genuine value:
- Users asking about reaction time or aim metrics
- Pro player performance analysis threads
- Discussions where real BVH-measured data (T0→T1 in ms) would be credible and interesting

Output per opportunity:
- Platform + URL (or title if no URL available)
- Thread summary (1 sentence)
- Engagement angle: specifically how Djok data (T0→T1 median, crosshair angle, kill rate) adds value
- Suggested entry point (reply, post, comment)

Produce 3-5 total opportunities. Quality over quantity.
```

### Agent 2 — Audit

Only run if audit_available = true.

Prompt:
```
You are a marketing audit agent for Djok, a CS2 reaction time analysis tool.

Read the file `marketing/log.md`.

Analyze the engagement history:
- Which posts had the highest engagement numbers?
- What hook formats appear in the high-engagement entries? (e.g., "number in headline", "comparison to donk", "specific tick count")
- What angles or framings appear in the flopped entries?
- What explicit "avoid" rules did the user note?

Produce 3-5 concrete rules as:
  DO: [specific pattern] — evidence: [which post, what result]
  AVOID: [specific pattern] — evidence: [which post, what result]

If fewer than 2 weeks of data exist, note this and produce fewer rules with lower confidence.
```

If audit_available = false, skip Agent 2. Substitute this note in WEEKLY.md Audit section:
```
_First run — no engagement history yet. Fill log.md after this week's posts to enable pattern learning._
```

### Agent 3 — SEO + Conversion

Prompt:
```
You are a conversion optimization agent for the Djok landing page.

Read `landing/index.html` and `landing/data.js`.

Audience context: FACEIT level 8-10 CS2 players. They distrust vague marketing claims. They respond to:
- Exact numbers (milliseconds, percentages, sample sizes)
- Technical credibility signals (BVH raycast, 83 demos analyzed)
- Honest framing ("manual analysis, 48h delivery" not "AI-powered instant")

Analyze:
1. Find the primary CTA button text (exact quote from HTML)
2. Is the hero headline numbers-first or claim-first?
3. What CS2-specific search terms is the page NOT targeting that FACEIT L8-10 players might search?
   Consider: "CS2 reaction time test", "FACEIT aim analysis", "compare aim to pro", "CS2 demo analysis"

Output:
- Current CTA: [exact text from HTML]
- Hero headline: [exact text from HTML]
- Variant A: CTA leading with specificity ("See your T0→T1 vs donk →")
- Variant B: CTA leading with comparison angle ("Compare your reaction to pro →")  
- Variant C: CTA leading with diagnosis ("Find your weakest phase →")
- Keyword gaps: 3-5 terms with 1-sentence rationale each
```

---

## Step 3: Synthesize into WEEKLY.md

Wait for all agent results. Write `marketing/WEEKLY.md` with this structure:

```markdown
# Djok Marketing Week: [CURRENT DATE]

_Generated by /marketing-weekly. Review, edit, then publish manually._

---

## Audit Patterns Applied

[Paste Agent 2 output here, or the "first run" note]

---

## Opportunities

[For each of Agent 1's 3-5 opportunities:]
### [N]. [Platform] — [Thread title/description]
**Angle:** [engagement angle from Agent 1]
**Entry point:** [reply/post/comment]
**URL/location:** [from Agent 1]

---

## Post Drafts

### Reddit — r/GlobalOffensive

[Write a data-first EN post. Open with a hard number. No marketing tone. Technical audience.
If audit patterns exist, apply DO rules to this draft.
Reference the opportunity thread from Agent 1 if relevant.]

---

### Twitter/X

[Write a hook line + hard stat. 280 chars for hook, then 3-4 tweet thread optional.
Image prompt: describe a monochrome terminal-style data visual (no design tool needed — just describe it for manual creation).
Apply audit DO rules if available.]

---

### Telegram (RU)

[Write in Russian. Technical tone. Monospace numbers. FACEIT L8-10 audience.
2-3 paragraphs. Data-first. No exclamation marks.
Apply audit DO rules if available.]

---

### Discord

[Short message (3-5 sentences max). Fits in a chat reply, not a post.
EN. Direct. Can reference an open opportunity thread from Agent 1.]

---

## Landing Page

**Current CTA:** [from Agent 3]
**Current hero headline:** [from Agent 3]

**Variant A:** [from Agent 3]
**Variant B:** [from Agent 3]
**Variant C:** [from Agent 3]

**Keyword gaps:**
[from Agent 3 — 3-5 terms with rationale]

---

## Log Entry Template

Copy this into `marketing/log.md` after publishing:

\`\`\`
## [CURRENT DATE]

### Posted

- [Reddit] [thread title or "original post"]
  Engagement: 
  What worked: 
  What flopped: 

- [Twitter] [hook line]
  Engagement: 
  What worked: 
  What flopped: 

- [Telegram] [topic]
  Engagement: 
  What worked: 
  What flopped: 

- [Discord] [server/channel]
  Engagement: 
  What worked: 
  What flopped: 

### Notes

- Best hook format this week: 
- Audience responded to: 
- Avoid next time: 
\`\`\`
```

---

## Step 4: Report to user

Tell the user:

- "WEEKLY.md written to `marketing/WEEKLY.md`"
- Number of opportunities found
- Whether audit patterns were applied (N rules from N weeks of data) or skipped (first run)
- "Next steps: review WEEKLY.md → edit drafts → publish → fill the log entry template in WEEKLY.md → paste into marketing/log.md"
````

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/marketing-weekly.md
git commit -m "feat(marketing): add /marketing-weekly skill"
```

Expected: skill file committed.

---

## Task 3: Smoke test

**Goal:** Verify skill runs end-to-end and produces correct output structure.

- [ ] **Step 1: Run the skill**

In Claude Code, type:
```
/marketing-weekly
```

- [ ] **Step 2: Verify `marketing/WEEKLY.md` was created**

Check file exists and contains all 6 sections:
- Audit Patterns Applied
- Opportunities (3-5 entries)
- Post Drafts (4 platform drafts)
- Landing Page (3 CTA variants + keyword gaps)
- Log Entry Template

- [ ] **Step 3: Verify `marketing/log.md` was NOT overwritten**

Log.md should still contain only the schema template from Task 1 (skill does not write to log.md — user fills it manually after publishing).

- [ ] **Step 4: Check audit section**

On first run (empty log.md), audit section should read:
```
_First run — no engagement history yet. Fill log.md after this week's posts to enable pattern learning._
```

- [ ] **Step 5: Commit WEEKLY.md to .gitignore**

`marketing/WEEKLY.md` is generated output — should not be tracked. Add to `.gitignore`:

```
marketing/WEEKLY.md
```

```bash
git add .gitignore
git commit -m "chore: ignore generated marketing/WEEKLY.md"
```

---

## Self-Review

### Spec coverage check

| Spec requirement | Task |
|-|-|
| 3 parallel agents (Research, Audit, SEO) | Task 2 Step 2 |
| marketing/log.md schema | Task 1 |
| marketing/WEEKLY.md format (all 6 sections) | Task 2 Step 2 |
| Audit skips gracefully on first run | Task 2 Step 2 (audit_available flag) |
| Self-improving loop via log.md | Task 2 Step 2 + Task 3 Step 3 |
| Smoke test verifies structure | Task 3 |
| WEEKLY.md excluded from git | Task 3 Step 5 |

All spec requirements covered. No gaps found.

### Placeholder scan

No TBD, TODO, or vague instructions present. Agent prompts contain full text. Output format is fully specified with exact section headers.

### Type consistency

No code types — skill file uses consistent section names throughout:
- `marketing/log.md` (not `log.md` or `marketing-log.md`)
- `marketing/WEEKLY.md` (not `weekly.md` or `WEEKLY.md`)
- `audit_available` flag named consistently in Step 2 condition and Agent 2 skip note
