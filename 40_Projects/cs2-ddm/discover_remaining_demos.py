"""One-shot: enumerate demos in backup not yet rebatched + map to disk paths."""
import sqlite3
from pathlib import Path

TOP10 = {
    "spirit-vs-the-mongolz-m2-ancient.dem", "passion-ua-vs-faze-m2-nuke.dem",
    "mouz-vs-spirit-m2-mirage.dem", "spirit-vs-the-mongolz-m2-mirage.dem",
    "spirit-vs-vitality-m1-mirage.dem", "spirit-vs-virtus-pro-m1-ancient.dem",
    "faze-vs-pain-m2-dust2.dem", "spirit-vs-the-mongolz-m1-nuke.dem",
    "faze-vs-pain-m1-nuke.dem", "passion-ua-vs-faze-m1-anubis.dem",
}

EXT = Path("D:/Obsidian/opacity/40_Projects/for_analysis")

all_files = list(EXT.rglob("*.dem"))
name_to_path = {f.name: f.as_posix() for f in all_files}

b = sqlite3.connect("analytics.db.pre-staged-rebatch-2026-05-16")
rows = b.execute(
    "SELECT demo_name, COUNT(*) FROM engagements "
    "WHERE demo_name IS NOT NULL GROUP BY demo_name ORDER BY 2 DESC"
).fetchall()
b.close()

remaining, missing = [], []
for name, n in rows:
    if name in TOP10:
        continue
    if name in name_to_path:
        remaining.append((name, name_to_path[name], n))
    else:
        missing.append((name, n))

print(f"Available for full corpus rebatch: {len(remaining)}")
print(f"Missing on disk: {len(missing)}")
print()
if missing:
    print("Missing demos (will be skipped):")
    for name, n in missing[:20]:
        print(f"  {n:3d}  {name}")
    if len(missing) > 20:
        print(f"  ... +{len(missing) - 20} more")
print()
print("First 5 available (top by row count):")
for name, path, n in remaining[:5]:
    print(f"  {n:3d}  {name}")
print()
print(f"Sum pre-fix engagement rows (will be DELETED and rebatched): {sum(n for _, _, n in remaining)}")

with open("full_corpus_demo_list.txt", "w", encoding="utf-8") as f:
    for name, path, n in remaining:
        f.write(f"{name}\t{path}\t{n}\n")
print(f"\nWrote {len(remaining)} entries to full_corpus_demo_list.txt")
