---
type: meta
updated: 2026-06-07
auto_generated: true
---
# Project Graph

Auto-generated from PROJECT.md ledgers in `Claude_experiments/`. 22 projects across 8 domains.

## ? (4 projects)

- • **Claude_experiments** — Персональная система второго мозга для Арыстана Кадырова. Автоматически компилирует источники знаний (Obsidian заметки, рабочие KB, Telegram канал, YouGile чаты) в Evergreen-заметки и ежедневный брифинг через Claude API. После v2.0 — pipeline self-aware (health, cost), cross-project linked (ledgers, memory router) и outbound-capable (drafts → gated autonomous). Запускается по расписанию в 7:00 GMT+5 + ручные вызовы.
- • **china-ebat** — TODO: what
- • **bagdan_jitsu** — A BJJ training-log system for individual practitioners: a Telegram bot turns unstructured ru/en training notes into a normalized sequence model (positions, stimuli, actions), and a web canvas (React + React Flow + elkjs) lets the user view and fully edit those sequences by mouse. Pet project of Leo + Богдан (repo owner: https://github.com/theBodyan/bjj, local clone at `bjj/`).
- • **paralich** — A short first-person indie horror prototype about sleep paralysis. You wake in the night unable to move — only your gaze can shift. Apparitions visit the room. The horror is built from atmosphere and the tension of *where to look*, not from chasing or combat. Web-based (three.js), PS1/low-poly aesthetic, ~3-5 minute single episode. This is a prototype to prove the core feel, not a finished game.

_Cross-pollinate candidates within `?`:_ Claude_experiments, china-ebat, bagdan_jitsu, paralich

## ai (3 projects)

- ▶ **ai_interview_coach** — TODO: describe project goal — why it exists, not what code does.
- ▶ **health-agent-plugin** — Claude Code plugin providing health analytics skills. Users run skills like `/analyze`, `/plan-panel`, `/add-result` against their personal health data. Skills compare lab results and training data to 5 longevity protocols: Blueprint, Medicine 3.0, AHA Life's Essential 8, Sinclair, WHO.
- ▶ **intercept** — <h1 align="center">Interceptor</h1>

_Cross-pollinate candidates within `ai`:_ ai_interview_coach, health-agent-plugin, intercept

## content (2 projects)

- ▶ **arystan_health** — Personal health analytics system for Arystан Kadyrov (DOB 30.01.2002, male, 23 y/o). Converts raw medical documents into structured Markdown and JSON, then compares results against the Blueprint longevity protocol in `protocols/blueprint_summary.md`.
- ▶ **psyskills** — Claude Code plugin for psychotherapists. Provides four structured skills for clinical work: `/psy:conceptualize` (BASIC ID multi-modal case formulation from session transcript), `/psy:goals` (six-criteria goal-setting), `/psy:strategy` (4-step session strategy planning), `/psy:supervise` (4-axis supervision assessment scored /40). Each client lives in `clients/<name>.md` with structured frontmatter; templates and references organize the framework knowledge base.
  
  GitHub-installable via `claude plugin install`. Designed for solo practitioners and supervision-heavy training programs.

_Cross-pollinate candidates within `content`:_ arystan_health, psyskills

## finance (1 projects)

- ▶ **moex_tracker** — MOEX financial dashboard + personal finance planning tools. Collects annual IFRS financials from smart-lab.ru, price history and OFZ yields from MOEX ISS public API, runs dividend bounce backtests across 20 Russian blue-chip tickers. Personal finance layer: IIS-A tax refund calculator, savings trajectory tracker, portfolio allocator (RUB LQDT/OFZ + USD S&P500 via Freedom Finance Kazakhstan), live CBR/Yahoo Finance/CoinGecko rates.
  
  FastAPI web UI on port 8001, cross-linked with autorss_feed digest (port 8000). Pipeline runs daily via Windows Task Scheduler at 08:00. GitHub: LeoDiKadyrov/moex-tracker.

## gaming (4 projects)

- ▶ **pongayer** — You are assisting in the development of **Dialogue Pong** — a multiplayer web-based game that transforms classic Pong into a platform for anonymous dialogue between strangers.
- ▶ **wtp-plugin** — What-To-Play MCP server. 7 tools (Steam library, local scanner, HLTB, OpenCritic, reviews) → персональные рекомендации игр. State в `gaming_profile.json`.
- ▶ **djok-landing** — Single-page landing for Djok — CS2 reaction analysis service. EN/RU bilingual, dark terminal aesthetic. Deployed on Cloudflare Workers. Part of the cs2-ddm project (analyzer lives at 40_Projects/cs2-ddm).
- ▶ **cs2-ddm** — Инструмент для анализа CS2 демок, который разбивает реакцию на три этапа: T0 (враг стал виден по BVH-геометрии), T1 (игрок начал наводиться), T2 (первое попадание). Продукт Djok — для B2C игроков, которые хотят понять, что именно мешает им быть ближе к уровню лучших. Второй вектор — аналитика для профессиональных команд и научные статьи.

_Cross-pollinate candidates within `gaming`:_ pongayer, wtp-plugin, djok-landing, cs2-ddm

## personal (2 projects)

- ▶ **arystan-context** — Public context API for Arystan Kadyrov. Machine-readable JSON files (status, projects, goals) generated daily from Obsidian vault + second_brain pipeline. Designed for external AI agents (friends, collaborators) to query what Arystan is working on, where help is needed, and how to collaborate. No NDA data. Open-source on GitHub.
- ▶ **pedigree** — Genealogical research project. Builds Kadyrov family tree 7+ generations deep via grandmother interviews (Whisper transcription pipeline), DNA testing (MyHeritage autosomal × 4 + FTDNA Big Y), ЗАГС archives, and oral history. Goal: GEDCOM → web visualization → printed book. Paternal-male Kazakh line bootstrapped. Phase 1 active (interviews + DNA ordered).

_Cross-pollinate candidates within `personal`:_ arystan-context, pedigree

## productivity (3 projects)

- ▶ **autorss_feed** — Personal AI curator pipeline. Pulls posts from Telegram channels, Reddit subreddits, YouTube channels, and IMAP email accounts, scores each for relevance using Claude (batch) or Ollama (qwen2.5:7b), groups curated content by category and topic, and renders a daily Markdown digest with project-aware "Связь:" connections.
  
  Three-agent architecture (Collector → Curator → Editor) communicating exclusively via SQLite. FastAPI web UI renders digests as HTML. Auto-runs twice daily (07:00 + 19:00 GMT+5) via Windows Task Scheduler. Multi-account IMAP support (3 active accounts: Gmail main, Gmail secondary, mail.ru). Topic tagging across 30 allow-listed tags. v1.1 shipped 2026-05-08.
  
  Drives Arystan's morning information consumption — replaces manual scrolling through 40+ Telegram channels and 3 inboxes with a single curated digest tied to active projects.
- ▶ **korzina_weekly** — Node.js-проект, автоматизирующий заказ продуктов через приватный API `api.korzinavdom.kz`. Workflow: вытащить историю прошлого заказа → согласовать корзину с пользователем → отправить инкрементальные `PUT`-запросы в `/client/basket/items`.
- ▶ **second_brain** — Pipeline собирает контекст из YouGile + Telegram + Obsidian → `daily-briefing.md`. User-facing guide: `USAGE.md`.

_Cross-pollinate candidates within `productivity`:_ autorss_feed, korzina_weekly, second_brain

## work (3 projects)

- ▶ **DBO_Faktura_KB** — RAG knowledge base assistant for the ДБО Faktura.ru implementation manager. Indexes technical documentation (Fxgate transport gateway, SBM online gateway, АРМ administration interfaces, УЦ certificate authority) into a Chroma vector store and answers technical integration questions via Claude. Module-filtered search (`fxgate`, `sbm`, `arm`, etc.) keeps retrieval focused. When no high-confidence match is found, logs the gap to a backlog so docs can be expanded.
  
  Scope is strictly technical: API integration, configuration, request/response formats, system connectivity between ДБО and bank АБС. Not for finance, regulation, or business-logic questions.
- ▶ **Digital_ruble** — Implementation Manager assistant for Russia's Цифровой Рубль (Digital Ruble / CBDC) rollout across 70+ Russian banks via Faktura.ru. Bridges the CR Platform (ПлЦР), Faktura.ru's ДБО layer, and each bank's АБС. Glossary covers Fxgate (offline transport), SBM (online gateway), СЦР (CR account), ФП (financial intermediary), ПЦ (processing), КО/КК (treatment/control contours), ССС (modern systems vendor).
  
  Scope is strictly technical: API integration, DB configuration, request/response formats, system connectivity. Output language Russian unless asked. Active national-scale rollout — Arystan leads a team of 10.
- ▶ **Olga_reich** — This is a business strategy document repository, not a software project. It contains planning materials for **"Юрист и бизнес"** (Lawyer & Business) — a Russian-language online community and educational platform for legal professionals.

_Cross-pollinate candidates within `work`:_ DBO_Faktura_KB, Digital_ruble, Olga_reich

## All projects (alphabetical)

- `Claude_experiments` (?, ?)
- `DBO_Faktura_KB` (work, active)
- `Digital_ruble` (work, active)
- `Olga_reich` (work, active)
- `ai_interview_coach` (ai, active)
- `arystan-context` (personal, active)
- `arystan_health` (content, active)
- `autorss_feed` (productivity, active)
- `bagdan_jitsu` (?, ?)
- `china-ebat` (?, ?)
- `cs2-ddm` (gaming, active)
- `djok-landing` (gaming, active)
- `health-agent-plugin` (ai, active)
- `intercept` (ai, active)
- `korzina_weekly` (productivity, active)
- `moex_tracker` (finance, active)
- `paralich` (?, ?)
- `pedigree` (personal, active)
- `pongayer` (gaming, active)
- `psyskills` (content, active)
- `second_brain` (productivity, active)
- `wtp-plugin` (gaming, active)
