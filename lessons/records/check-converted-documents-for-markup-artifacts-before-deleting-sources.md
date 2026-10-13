---
title: "Check converted documents for markup artifacts before deleting sources"
tags: ["agents", "testing", "data-loss"]
---

# Check converted documents for markup artifacts before deleting sources

**Context**: 2026-10-13. A Google Drive notes migration converted about 80 Google Docs tabs
from the HTML export into Obsidian Markdown with a custom converter. The checks run before
reporting done counted words and images per tab and found full coverage, so the exports
were deleted. The user then opened `Recruitment 2025.md` and found it badly formatted.
Google Docs splits text into many spans and the converter wrapped each span separately, so
the output was full of `==a====b==` and `**x****y**`. It wrote code, which Docs stores as
monospace paragraphs, as plain text, so Python comments became Markdown headings. It
glued list items in table cells together with no separator. Fixing it meant downloading
all 50 exports again from the Drive trash.

**Problem**: word and image coverage checks prove nothing is lost, but they say nothing
about how the result renders. Markup damage keeps every word.

**Rule**: before declaring a document conversion done or deleting its sources, check the
output for rendering artifacts. Grep for doubled markers (`====`, `****`), for lines that
start with `#` and look like code, for unbalanced `**` and `==` outside code blocks, and
for table cells that lost their separators. Open the largest and most complex file and
read part of it. Keep the sources until the user has looked at the result.

**Applies to**: any HTML, DOCX or Google Docs to Markdown conversion, and any migration
where the source is deleted after converting.
