---
name: claude-chat-to-claude-code-cli-mirroring
description: Mirror the most recent claude.ai chat conversations into Claude Code session history, titled with a [MIRROR] prefix, so they can be opened with /resume. Use when the user asks to mirror, import, sync or pull claude.ai conversations into Claude Code.
---

Run the script and always print its output 1:1, on success and on error.
Do not process the conversations yourself.

```bash
bash scripts/mirror.sh [count]
```

`count` defaults to 5.
