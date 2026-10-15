import html
import json
import logging
import os
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from faster_whisper import WhisperModel

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = int(os.environ["TELEGRAM_CHAT_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"
MAX_BYTES = 20 * 1024 * 1024
NOTES_DIR = Path.home() / "brain/projects/meetings"
AUDIO_DIR = Path.home() / "data/projects/meetings"
SESSIONS = Path.home() / ".cache/telegram-sessions"
CLAUDE = Path.home() / ".local/bin/claude"

log = logging.getLogger("meetings")


def api(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data, timeout=90) as resp:
        return json.load(resp)["result"]


def reply(text: str, **params) -> None:
    log.info(f"reply sent: {api('sendMessage', chat_id=CHAT_ID, text=text, **params)['message_id']} {text}")


def find_audio(msg: dict) -> dict | None:
    for kind in ("voice", "audio", "video", "video_note", "document"):
        if kind in msg:
            return msg[kind]
    return None


def timestamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02}"


def run_agent(session: dict, text: str) -> None:
    prompt = f"The user replied on Telegram to your last message:\n\n{text}\n\nAnswer them on Telegram with the telegram-messaging skill."
    result = subprocess.run(
        [CLAUDE, "--resume", session["session_id"], "--fork-session", "--permission-mode", session["permission_mode"], "-p", prompt],
        cwd=session["cwd"], capture_output=True, text=True,
    )
    if result.returncode:
        reply(f"Agent failed: {(result.stderr or result.stdout)[-500:]}")


def live_pane(session: dict) -> str | None:
    pane, pid = session.get("tmux_pane"), session.get("claude_pid")
    comm = Path(f"/proc/{pid}/comm")
    if not pane or not comm.exists() or comm.read_text().strip() != "claude":
        return None
    shell = subprocess.run(["tmux", "display", "-p", "-t", pane, "#{pane_pid}"], capture_output=True, text=True).stdout.strip()
    parent = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1]
    return pane if shell == parent else None


def forward(msg: dict) -> None:
    replied = msg.get("reply_to_message")
    if not replied:
        reply("Reply to an agent's message to forward it.")
        return
    session_file = SESSIONS / f"{replied['message_id']}.json"
    if not session_file.exists():
        reply("No agent session for that message.")
        return
    session = json.loads(session_file.read_text())
    pane = live_pane(session)
    if pane:
        subprocess.run(["tmux", "send-keys", "-t", pane, "-l", f"Telegram reply: {' '.join(msg['text'].split())}"])
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"])
        reply(f"Sent to the live session in tmux pane {pane}.")
        return
    threading.Thread(target=run_agent, args=(session, msg["text"])).start()
    reply("Session not live, forked it.")


def handle(msg: dict) -> None:
    if "text" in msg:
        forward(msg)
        return
    media = find_audio(msg)
    if not media:
        return
    size_mb = media.get("file_size", 0) / 1024 / 1024
    if media.get("file_size", 0) > MAX_BYTES:
        reply(f"Recording too long: {size_mb:.0f} MB, the limit is 20 MB.")
        return

    reply("Transcribing...")
    recorded = datetime.fromtimestamp(msg["date"])
    name = f"{recorded:%Y-%m-%d-%H-%M-%S} Recording"
    audio = AUDIO_DIR / f"{name}{Path(media.get('file_name') or 'voice.ogg').suffix}"
    file_path = api("getFile", file_id=media["file_id"])["file_path"]
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}", audio)

    model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
    segments, info = model.transcribe(str(audio), vad_filter=True)
    lines = [f"[{timestamp(s.start)}] {s.text.strip()}" for s in segments]

    note = NOTES_DIR / f"{name}.md"
    note.write_text(
        f"---\ndate: {recorded:%Y-%m-%dT%H:%M}\nduration: {timestamp(info.duration)}\n"
        f"language: {info.language}\naudio: {audio.name}\n---\n\n" + "\n".join(lines) + "\n"
    )
    link = "https://obsid.net/?" + urllib.parse.urlencode({"vault": "brain", "file": f"projects/meetings/{name}"})
    reply(f'Done: <a href="{html.escape(link)}">{name}</a> ({timestamp(info.duration)})', parse_mode="HTML")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    offset = 0
    while True:
        try:
            updates = api("getUpdates", offset=offset, timeout=60)
        except Exception:
            log.exception("getUpdates failed")
            time.sleep(10)
            continue
        for update in updates:
            offset = update["update_id"] + 1
            msg = update.get("message")
            log.info(f"update {update['update_id']}: {sorted(msg or update)}")
            if not msg or msg["chat"]["id"] != CHAT_ID:
                continue
            try:
                handle(msg)
            except Exception as e:
                log.exception("handling failed")
                reply(f"Error: {e}")


if __name__ == "__main__":
    main()
