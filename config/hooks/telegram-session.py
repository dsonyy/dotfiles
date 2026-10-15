#!/usr/bin/env python3
import json
import os
import re
import sys
import time
from pathlib import Path

SESSIONS = Path.home() / ".cache/telegram-sessions"
TTL = 24 * 3600

event = json.load(sys.stdin)
command = event.get("tool_input", {}).get("command", "")
if "telegram-messaging" not in command or "send.py" not in command:
    sys.exit()
sent = re.search(r"^sent (\d+)$", str(event.get("tool_response", {}).get("stdout", "")), re.M)
if not sent:
    sys.exit()

pid = os.getppid()
while pid > 1 and Path(f"/proc/{pid}/comm").read_text().strip() != "claude":
    pid = int(Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1])

SESSIONS.mkdir(parents=True, exist_ok=True)
for old in SESSIONS.glob("*.json"):
    if time.time() - old.stat().st_mtime > TTL:
        old.unlink()
(SESSIONS / f"{sent[1]}.json").write_text(json.dumps({
    "session_id": event["session_id"],
    "cwd": event["cwd"],
    "permission_mode": event.get("permission_mode", "default"),
    "tmux_pane": os.environ.get("TMUX_PANE"),
    "claude_pid": pid,
}))
