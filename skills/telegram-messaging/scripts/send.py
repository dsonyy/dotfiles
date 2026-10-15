#!/usr/bin/env python3
import json
import os
import socket
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ENV_FILE = Path.home() / "repos/dotfiles/.env"


# IPv6 routes to Telegram intermittently blackhole on this network and urllib waits out the whole timeout
_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, port, family=0, *args, **kwargs: _getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

def load_env() -> None:
    for line in ENV_FILE.read_text().splitlines():
        key, sep, value = line.partition("=")
        if sep and key.startswith("TELEGRAM_"):
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


def main() -> None:
    text = " ".join(sys.argv[1:]) or sys.stdin.read()
    load_env()
    params = {
        "chat_id": os.environ["TELEGRAM_CHAT_ID"],
        "text": text.strip(),
        "parse_mode": "HTML",
        "link_preview_options": json.dumps({"is_disabled": True}),
    }
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    try:
        with urllib.request.urlopen(url, urllib.parse.urlencode(params).encode(), timeout=30) as resp:
            print("sent", json.load(resp)["result"]["message_id"])
    except urllib.error.HTTPError as e:
        sys.exit(e.read().decode())


if __name__ == "__main__":
    main()
