---
name: lessons-writing
description: Write a lesson to ~/lessons after a hard-won fix, a long debug, a dead end, or a decision the user reversed several times. Use when asked to save, record or write down a lesson or learning.
---

One file per lesson: `~/lessons/<kebab-case-title>.md`.

```
---
title: "Short claim of what we learned"
description: "One line with the symptoms and terms someone would search for"
---
```

The body is a condensed transcript for a human or an agent: the problem as it first looked, each attempt and why it failed, what turned out to be the real problem, what worked, what to do next time. Follow the shape of what happened, a single problem and fix or a chain where each fix exposed the next problem. Keep it short.

Update an existing lesson instead of writing a near-duplicate. Preferences and always-true rules belong in `AGENTS.md`, not here.

Add or update the row in `~/lessons/index.md`: `- [Title](file.md) - description`. Then run `python3 check.py` from this skill's directory and fix what it reports.
