---
date: '2026-05-14'
source: https://www.biorxiv.org/content/10.64898/2026.05.09.723964v1?rss=1
tags:
- digest-reaction
---

## Из дайджеста

--- <!-- item-id:6383 --> <!-- post-id:6383 -->

---

## Idea 1: Connectome-similarity scorer для curator team-fit
Скрипт `src/curator/team_fit_scorer.py`: статья описывает FC similarity ↔ shared role. Маппить на autorss curator: посты со схожим embedding-профилем = "та же роль" → бустить precision на underrepresented категориях. Cosine-sim curated_post embeddings vs profile_hash centroid, threshold ≥0.75.

## Idea 2: Role-position taxonomy для sources.txt
Volleyball court position → category role. Расширить `config/sources.txt` 5-м полем `role` (analyst/scout/setter/finisher) поверх `category`. Editor группирует по role, не только category. Fix Goodhart 'other' bloat — role-based routing вместо single-axis category.

## Idea 3: Cross-source FC graph
`scripts/build_source_connectome.py`: корреляции по co-curation patterns (какие источники часто curated в одном digest). NetworkX adjacency matrix → vis.js рендер на `/sources/graph`. Аналог resting-state FC между источниками. Detect dead/duplicate sources через low-connectivity cluster.

## Idea 4: Naturalistic vs resting-state mode для editor
Paper различает task-active vs resting FC. Editor `--mode active` (game-time, hot topics, last 4h) vs `--mode resting` (baseline weekly digest, slow-burn topics). Разные prompts, разные thresholds. CRON: active 07:00/19:00, resting Sunday 11:00.

## Idea 5: Team-membership classifier для draft автоматизации
Draft `chain_state` = "team" assignment. Drafts с похожим source_url-profile группировать в один meta-draft. `src/agents/draft_clusterer.py`: simhash + jaccard на frontmatter tags, threshold 0.6 → merge promotes. Reduce draft fatigue (27→~10 за неделю).

## Idea 6: Coordination metric для multi-collector pipeline
Telegram/Reddit/ArXiv/Email/YouTube — 5 "players". Метрика `pipeline_synergy.py`: какой % curated postов цитирует друг друга через 24h window. Низкая synergy → collectors работают изолированно (waste). Логировать в `cost_snapshots.synergy_score`.

## Idea 7: bioRxiv Neuroscience auto-pull в research section
Уже есть BiorxivCollector. Добавить `neuroscience` subcat в `config/sources.txt`: `neuroscience | research | bioRxiv Neuroscience | biorxiv`. Эта статья — пример того, что подходит под research stage.

## Top-3 with rationale

1. **Idea 3: Cross-source FC graph** — direct port методики (FC matrix → role inference). Решает реальную проблему: discover_telegram_dialogs auto-add 150 sources, многие dead. Visualization + dead-source culling за 1 скрипт.
2. **Idea 5: Draft clustering** — атакует open issue (draft fatigue, 27 pending). Simhash уже в репо (`src/llm/simhash.py`). Низкий риск, высокий ROI.
3. **Idea 4: active/resting editor modes** — paper-faithful split. Решает Goodhart 'other' bloat через temporal disambiguation, не category proliferation.

## Immediate Next Step

```bash
# Quick win: дамп co-curation matrix для будущей FC graph
.venv/Scripts/python.exe -c "
import sqlite3
db = sqlite3.connect('curator.db')
rows = db.execute('''
  SELECT d.id AS digest_id, s.target, s.display_name, s.category
  FROM digest_items di
  JOIN raw_posts rp ON di.item_id = rp.id
  JOIN sources s ON rp.source_id = s.id
  JOIN digests d ON di.digest_id = d.id
  WHERE d.created_at > datetime('now', '-30 days')
  ORDER BY d.id, s.target
''').fetchall()
from collections import defaultdict
co = defaultdict(int)
by_digest = defaultdict(set)
for did, tgt, _, _ in rows:
    by_digest[did].add(tgt)
for srcs in by_digest.values():
    srcs = sorted(srcs)
    for i, a in enumerate(srcs):
        for b in srcs[i+1:]:
            co[(a,b)] += 1
top = sorted(co.items(), key=lambda x: -x[1])[:20]
for (a,b), n in top: print(f'{n:3d}  {a} <-> {b}')
"
```

Output → seed для `scripts/build_source_connectome.py`. Если top-pairs показывают clusters — Idea 3 viable. Если flat distribution — collectors isolated, Idea 6 priority.
