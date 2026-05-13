"""
Parse Telegram HTML export → JSONL.

Each message becomes one JSON line:
{ts, sender, text, msg_id, reply_to_id}

Joined messages (no from_name = same sender as previous) inherit sender from prior.
Skips service messages and media-only (no text node).
"""

import json
import re
import sys
from pathlib import Path

from lxml import html as lxml_html


# CLI: python parse_chat.py [<export_folder>] [<output_jsonl>]
DEFAULT_EXPORT = Path(r"D:/Obsidian/opacity/40_Projects/cs2-ddm/marketing/ChatExport_2026-05-08")
DEFAULT_OUT = Path(r"D:/Obsidian/opacity/40_Projects/cs2-ddm/marketing/_analyze/messages.jsonl")
EXPORT = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_EXPORT
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_OUT

DATE_RE = re.compile(r"(\d{2}\.\d{2}\.\d{4} \d{2}:\d{2}:\d{2})")
MSG_ID_RE = re.compile(r"message(\d+)")


def parse_file(path: Path, last_sender: str | None) -> tuple[list[dict], str | None]:
    """Return (messages, sender_after_file) — sender is needed for joined-message continuity."""
    out: list[dict] = []
    with open(path, "rb") as f:
        tree = lxml_html.parse(f)
    for div in tree.xpath('//div[contains(@class,"message")]'):
        cls = div.get("class") or ""
        if "service" in cls:
            continue
        msg_id_m = MSG_ID_RE.match(div.get("id") or "")
        msg_id = int(msg_id_m.group(1)) if msg_id_m else None

        # date
        date_div = div.xpath('.//div[contains(@class,"date")]/@title')
        ts = None
        if date_div:
            m = DATE_RE.search(date_div[0])
            if m:
                ts = m.group(1)

        # sender
        from_div = div.xpath('.//div[contains(@class,"from_name")]')
        if from_div:
            sender = from_div[0].text_content().strip()
            last_sender = sender
        else:
            sender = last_sender

        # reply_to
        reply_to = None
        reply_link = div.xpath('.//div[contains(@class,"reply_to")]//a/@href')
        if reply_link:
            m = re.search(r"go_to_message(\d+)", reply_link[0])
            if m:
                reply_to = int(m.group(1))

        # text — bypass forwarded headers, signatures, etc. by grabbing the .text div under .body
        text_nodes = div.xpath('.//div[contains(@class,"body")]/div[contains(@class,"text") and not(contains(@class,"bold"))]')
        text = ""
        if text_nodes:
            text = text_nodes[0].text_content().strip()

        if not text:
            # skip media-only / sticker / poll / file — they have no text node or empty
            continue

        out.append({
            "ts": ts,
            "sender": sender,
            "text": text,
            "msg_id": msg_id,
            "reply_to": reply_to,
            "src": path.name,
        })
    return out, last_sender


def main():
    files = sorted(
        EXPORT.glob("messages*.html"),
        key=lambda p: int(re.search(r"messages(\d*)\.html", p.name).group(1) or 1),
    )
    print(f"files: {len(files)}", file=sys.stderr)

    n = 0
    last_sender: str | None = None
    with open(OUT, "w", encoding="utf-8") as fout:
        for i, fp in enumerate(files):
            try:
                msgs, last_sender = parse_file(fp, last_sender)
            except Exception as e:
                print(f"  ERROR {fp.name}: {e}", file=sys.stderr)
                continue
            for m in msgs:
                fout.write(json.dumps(m, ensure_ascii=False) + "\n")
                n += 1
            if (i + 1) % 50 == 0:
                print(f"  {i + 1}/{len(files)} files, {n} messages", file=sys.stderr)
    print(f"DONE: {n} messages → {OUT}", file=sys.stderr)


if __name__ == "__main__":
    main()
