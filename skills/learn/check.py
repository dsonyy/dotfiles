#!/usr/bin/env python3
import re
import sys
from pathlib import Path

ROOT = Path.home() / "lessons"
ROW = re.compile(r"^- \[(.+)\]\(([a-z0-9-]+\.md)\) - (.+)$")
FIELD = r'^{}: "(.+)"$'

errors = []
rows = {}
for line in (ROOT / "index.md").read_text().splitlines():
    if line.startswith("- "):
        row = ROW.match(line)
        if row:
            rows[row.group(2)] = row.group(1, 3)
        else:
            errors.append(f"index.md: malformed row: {line}")

for path in sorted(ROOT.glob("*.md")):
    if path.name == "index.md":
        continue
    text = path.read_text()
    title = re.search(FIELD.format("title"), text, re.M)
    description = re.search(FIELD.format("description"), text, re.M)
    if not text.startswith("---\n") or not title or not description:
        errors.append(f"{path.name}: front matter needs quoted title and description")
    elif path.name not in rows:
        errors.append(f"{path.name}: no row in index.md")
    elif rows[path.name] != (title.group(1), description.group(1)):
        errors.append(f"{path.name}: index row title or description differs from front matter")

for name in rows:
    if not (ROOT / name).exists():
        errors.append(f"index.md: row points at missing {name}")

if errors:
    sys.exit("\n".join(errors))
print(f"lessons: ok, {len(rows)} lessons")
