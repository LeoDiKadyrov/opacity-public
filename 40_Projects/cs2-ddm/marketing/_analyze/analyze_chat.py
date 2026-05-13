"""
Analyze parsed messages.jsonl → community insights for Djok positioning/marketing.

Outputs marketing/_analyze/REPORT.md with:
- Volume, sender distribution, temporal patterns
- Topic buckets with sample fragments per bucket
- CS2-specific lexicon counts
- Pain/question signals
- Voice samples (long-form posts > 200 chars)
- Competitor mentions (Leetify, Aim Lab, prefire, Faceit, csstats, etc.)
"""

from __future__ import annotations

import json
import random
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean, median

random.seed(42)

import sys

ROOT = Path(r"D:/Obsidian/opacity/40_Projects/cs2-ddm/marketing/_analyze")
# CLI: python analyze_chat.py [<input_jsonl>] [<output_md>]
JSONL = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "messages.jsonl"
REPORT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "REPORT.md"

# topic regex buckets — case-insensitive, word-boundary friendly for cyrillic
BUCKETS: dict[str, list[str]] = {
    "aim_skill": [
        r"\baim\b", r"\bаим\b", r"прицел", r"флик", r"трекинг", r"\bспрей\w*", r"recoil",
        r"мут[еи]?н?", r"тапани", r"\bхедшот\w*", r"\bхс\b", r"\bкбж\b", r"\bкилл\w+",
        r"crosshair", r"стрел[ьея][бт]", r"\bснап\w*", r"\bпасте\w*",
    ],
    "reaction": [
        r"реакц", r"\brt\b", r"\bping\b", r"\bпинг\b", r"рефлекс", r"отреаг", r"задержк",
        r"\bms\b", r"\bмс\b", r"\bтикрейт\w*", r"\btickrate", r"\b64.?тик", r"128.?тик",
    ],
    "faceit_competitive": [
        r"\bfaceit\b", r"фейсит", r"\bпремьер\w*", r"\bпремьерка\b", r"\bлвл\b",
        r"\bесеа\b", r"\besea\b", r"\bмм\b", r"valve.?мм", r"\bпремир\w*",
        r"матчмейк", r"\bмаст[еи]р\w*", r"\bглоб\w*",
    ],
    "competitor_tools": [
        r"leetify", r"летифай", r"\baim ?lab\b", r"\bаим ?лаб\w*", r"kovaaks?", r"\bковакс?",
        r"prefire", r"префаер", r"csstats", r"tracker\.?gg", r"3dmark", r"\bбенч\w*",
        r"yprac",
    ],
    "hardware": [
        r"монитор", r"\bгц\b", r"\bhz\b", r"\b240\b", r"\bdpi\b", r"\bдпи\b", r"\bsens\w*",
        r"сенс[аеи]", r"\bмыш\w*", r"\bклав\w*", r"мхзшнн", r"коврик", r"полин[га]",
    ],
    "settings_cfg": [
        r"\bcfg\b", r"\bкфг\w*", r"\bcl_\w+", r"\bfps_max\b", r"\bfps\b", r"\bфпс\b",
        r"видеонастр", r"конфиг", r"setting", r"вьюмодел",
    ],
    "cheats": [
        r"\bчит\w+", r"читак", r"\bvac\b", r"вак\b", r"\bбан\w*", r"банов", r"софт",
        r"оверволч", r"факирш",
    ],
    "drill_practice": [
        r"тренир", r"разогр", r"прогр[её]в", r"\bдм\b", r"\bdm\b", r"deathmatch", r"\bdz\b",
        r"surf", r"\baim_botz\b", r"awp_lego", r"\bретей[кх]\w*", r"\bдедран\w*",
        r"workshop", r"\bворкшоп\w*",
    ],
    "coaching_review": [
        r"разбор", r"\bгайд\w*", r"тренер", r"коуч", r"обучен", r"\banalize\w*",
        r"\bобз[оы]р\w*",
    ],
    "pain_question": [
        r"помог[иуяе]", r"\bпочему\b", r"\bкак\b.{0,40}\?", r"не могу", r"не понима",
        r"\bтильт\w*", r"\bбомб\w*", r"\bфейл\w*", r"кд", r"стресс",
    ],
    "pro_players": [
        r"\bdonk\b", r"донк", r"s1mple", r"симпл", r"zywoo", r"зивоо", r"niko",
        r"karrigan", r"монеси", r"m0NESY", r"freezzz", r"frozen", r"броки", r"twistzz",
        r"shox", r"ax1le", r"sh1ro", r"forze", r"spirit", r"navi", r"vitality",
    ],
    "buy_pay": [
        r"\bкупи\w*", r"\bпрод[аеио]", r"\bцена\b", r"\bстоит\b", r"\bдорог\w+",
        r"\bдешев\w+", r"\bподписк\w*", r"\bоплат\w+", r"\bтриал\b",
    ],
}

# слова которые указывают на "помощь / диагностика проблемы"
HELP_TRIGGERS = re.compile(
    r"(помог[иуяе]|почему я|не пойму|не понимаю|кто.{0,15}объясн|объясни|подскаж|посове|стрим.{0,30}\?|ты как считаешь)",
    re.IGNORECASE,
)


def load() -> list[dict]:
    rows = []
    with open(JSONL, encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def parse_ts(s: str | None):
    if not s:
        return None
    try:
        return datetime.strptime(s, "%d.%m.%Y %H:%M:%S")
    except Exception:
        return None


def main() -> None:
    rows = load()
    n = len(rows)

    # parse timestamps
    for r in rows:
        r["dt"] = parse_ts(r.get("ts"))

    valid = [r for r in rows if r["dt"]]
    valid.sort(key=lambda r: r["dt"])
    period_start = valid[0]["dt"] if valid else None
    period_end = valid[-1]["dt"] if valid else None

    # senders
    sender_counts = Counter(r["sender"] or "<unknown>" for r in rows)

    # length
    lens = [len(r["text"]) for r in rows]

    # bucket compile
    bucket_re = {k: [re.compile(p, re.IGNORECASE) for p in pats] for k, pats in BUCKETS.items()}

    bucket_hits: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        t = r["text"]
        for bucket, regs in bucket_re.items():
            for rg in regs:
                if rg.search(t):
                    bucket_hits[bucket].append(r)
                    break

    # bucket per-pattern fine-grained counts
    pattern_counts: dict[str, Counter] = {}
    for bucket, pats in BUCKETS.items():
        c = Counter()
        for p in pats:
            rg = re.compile(p, re.IGNORECASE)
            cnt = sum(1 for r in rows if rg.search(r["text"]))
            if cnt:
                c[p] = cnt
        pattern_counts[bucket] = c

    # help/question signals — long-form (>30 chars) only to filter "?"
    help_msgs = [r for r in rows if len(r["text"]) > 30 and HELP_TRIGGERS.search(r["text"])]

    # long-form posts (subjective opinions)
    long_posts = [r for r in rows if len(r["text"]) >= 200]

    # temporal: hour-of-day
    hour_dist = Counter(r["dt"].hour for r in valid)

    # weekly volume
    week_dist = Counter()
    for r in valid:
        wk = r["dt"].strftime("%Y-W%W")
        week_dist[wk] += 1

    # competitor co-occurrence: messages mentioning Leetify or Aim Lab — context for positioning
    leetify_msgs = [r for r in rows if re.search(r"leetify|летифай|летиф", r["text"], re.IGNORECASE)]
    aimlab_msgs = [r for r in rows if re.search(r"aim ?lab|аим ?лаб", r["text"], re.IGNORECASE)]
    kovaaks_msgs = [r for r in rows if re.search(r"kovaaks?|ковакс?", r["text"], re.IGNORECASE)]
    prefire_msgs = [r for r in rows if re.search(r"prefire|префаер|префаир", r["text"], re.IGNORECASE)]

    # voice samples by length tier
    def samp(lst, k=15):
        return random.sample(lst, min(k, len(lst))) if lst else []

    out = []
    a = out.append

    a(f"# Sub-chat «Ретейк» — Community Insight Report")
    a(f"_Generated 2026-05-08 from `marketing/ChatExport_2026-05-08/messages*.html` ({n} messages parsed)._")
    a("")
    a("## 1. Volume & period")
    a("")
    a(f"- Messages with text: **{n}**")
    a(f"- Period: **{period_start} → {period_end}**")
    a(f"- Unique senders: **{len(sender_counts)}**")
    a(f"- Length avg / median / max: **{mean(lens):.0f} / {median(lens):.0f} / {max(lens)}** chars")
    a(f"- Messages ≥200 chars (long-form opinions): **{len(long_posts)}** ({100*len(long_posts)/n:.1f}%)")
    a("")

    a("## 2. Top senders (top 30)")
    a("")
    a("|sender|msgs|share|")
    a("|-|-|-|")
    for s, c in sender_counts.most_common(30):
        a(f"|{s}|{c}|{100*c/n:.1f}%|")
    a("")

    a("## 3. Topic buckets (any-pattern hit count)")
    a("")
    a("|bucket|hits|share|")
    a("|-|-|-|")
    for k in BUCKETS:
        h = len(bucket_hits[k])
        a(f"|{k}|{h}|{100*h/n:.1f}%|")
    a("")

    a("### 3a. Per-pattern breakdown")
    a("")
    for bucket, cnts in pattern_counts.items():
        if not cnts:
            continue
        a(f"**{bucket}**")
        for p, c in cnts.most_common():
            a(f"- `{p}` — {c}")
        a("")

    a("## 4. Sample fragments per bucket (15 random per bucket)")
    a("")
    for bucket in BUCKETS:
        msgs = bucket_hits[bucket]
        if not msgs:
            continue
        a(f"### {bucket} ({len(msgs)} hits)")
        a("")
        for r in samp(msgs, 15):
            txt = r["text"].replace("\n", " ").strip()
            if len(txt) > 240:
                txt = txt[:240] + "…"
            a(f"- _{r['sender']}_ `{r.get('ts','')}` — {txt}")
        a("")

    a("## 5. Help / question / pain signals (≥30 chars, contains help/why/explain/recommend)")
    a("")
    a(f"Total: **{len(help_msgs)}**")
    a("")
    a("Random sample (25):")
    a("")
    for r in samp(help_msgs, 25):
        txt = r["text"].replace("\n", " ").strip()
        if len(txt) > 280:
            txt = txt[:280] + "…"
        a(f"- _{r['sender']}_ `{r.get('ts','')}` — {txt}")
    a("")

    a("## 6. Long-form posts (≥200 chars) — voice samples")
    a("")
    a(f"Total: **{len(long_posts)}**")
    a("")
    a("Random 20:")
    a("")
    for r in samp(long_posts, 20):
        txt = r["text"].replace("\n", " ").strip()
        if len(txt) > 600:
            txt = txt[:600] + "…"
        a(f"- _{r['sender']}_ `{r.get('ts','')}`")
        a(f"  > {txt}")
        a("")

    a("## 7. Direct competitor mentions")
    a("")
    a("|tool|hits|")
    a("|-|-|")
    a(f"|Leetify|{len(leetify_msgs)}|")
    a(f"|Aim Lab|{len(aimlab_msgs)}|")
    a(f"|KovaaK's|{len(kovaaks_msgs)}|")
    a(f"|Prefire|{len(prefire_msgs)}|")
    a("")

    if leetify_msgs:
        a("**Leetify mentions (all):**")
        a("")
        for r in leetify_msgs[:30]:
            txt = r["text"].replace("\n", " ").strip()
            if len(txt) > 280:
                txt = txt[:280] + "…"
            a(f"- _{r['sender']}_ `{r.get('ts','')}` — {txt}")
        a("")
    if aimlab_msgs:
        a("**Aim Lab mentions (all):**")
        a("")
        for r in aimlab_msgs[:30]:
            txt = r["text"].replace("\n", " ").strip()
            if len(txt) > 280:
                txt = txt[:280] + "…"
            a(f"- _{r['sender']}_ `{r.get('ts','')}` — {txt}")
        a("")
    if kovaaks_msgs:
        a("**KovaaK's mentions:**")
        a("")
        for r in kovaaks_msgs[:30]:
            txt = r["text"].replace("\n", " ").strip()
            if len(txt) > 280:
                txt = txt[:280] + "…"
            a(f"- _{r['sender']}_ `{r.get('ts','')}` — {txt}")
        a("")

    a("## 8. Hour-of-day distribution (peak posting times)")
    a("")
    a("|hour|count|")
    a("|-|-|")
    for h in range(24):
        a(f"|{h:02d}|{hour_dist[h]}|")
    a("")

    a("## 9. Weekly volume (last 12 weeks)")
    a("")
    a("|week|msgs|")
    a("|-|-|")
    for wk, c in sorted(week_dist.items())[-12:]:
        a(f"|{wk}|{c}|")
    a("")

    REPORT.write_text("\n".join(out), encoding="utf-8")
    print(f"REPORT → {REPORT}")


if __name__ == "__main__":
    main()
