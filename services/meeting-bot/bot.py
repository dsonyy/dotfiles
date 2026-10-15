import html
import json
import logging
import os
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
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
SESSIONS = Path.home() / ".cache/telegram-sessions"
ACTIVE = SESSIONS / "active.json"
FILES = SESSIONS / "files"
CLAUDE = Path.home() / ".local/bin/claude"
CLAUDE_DIR = Path.home() / ".claude"

log = logging.getLogger("meetings")
FORKS = threading.Lock()
TRANSCRIPTIONS = threading.Lock()


# IPv6 routes to Telegram intermittently blackhole on this network and urllib waits out the whole timeout
_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, port, family=0, *args, **kwargs: _getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)

def api(method: str, **params) -> dict:
    data = urllib.parse.urlencode(params).encode()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(f"{API}/{method}", data, timeout=90) as resp:
                return json.load(resp)["result"]
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ConnectionError) as e:
            if attempt == 2:
                raise
            log.info(f"{method} retried after {e}")
            time.sleep(2)


def download(file_id: str, target: Path) -> None:
    file_path = api("getFile", file_id=file_id)["file_path"]
    target.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(f"https://api.telegram.org/file/bot{TOKEN}/{file_path}", target)


def reply(text: str, markup: str | None = None, **params) -> None:
    body = f"<i>{markup or html.escape(text)}</i>"
    log.info(f"reply sent: {api('sendMessage', chat_id=CHAT_ID, text=body, parse_mode='HTML', **params)['message_id']} {text}")


def find_image(msg: dict) -> dict | None:
    if "photo" in msg:
        return msg["photo"][-1]
    document = msg.get("document", {})
    return document if document.get("mime_type", "").startswith("image/") else None


def find_audio(msg: dict) -> dict | None:
    for kind in ("voice", "audio", "video", "video_note", "document"):
        if kind in msg:
            return msg[kind]
    return None


def timestamp(seconds: float) -> str:
    s = int(seconds)
    return f"{s // 3600:02}:{s % 3600 // 60:02}:{s % 60:02}"


def run_agent(session: dict, text: str, from_active: bool) -> None:
    with FORKS:
        if from_active:
            session = json.loads(ACTIVE.read_text())
        fork(session, text)


def fork(session: dict, text: str) -> None:
    prompt = f"Message from the user on Telegram:\n\n{text}\n\nAnswer them on Telegram with the telegram-messaging skill."
    mode = ["--permission-mode", session["permission_mode"]] if session.get("permission_mode") else []
    try:
        result = subprocess.run(
            [CLAUDE, "--resume", session["session_id"], "--fork-session", *mode, "--output-format", "json", "-p", prompt],
            cwd=session["cwd"], capture_output=True, text=True, timeout=3600,
        )
    except subprocess.TimeoutExpired:
        reply("Agent timed out after 1 h.")
        return
    if result.returncode:
        reply(f"Agent failed: {(result.stderr or result.stdout)[-500:]}")
        return
    if ACTIVE.exists() and json.loads(ACTIVE.read_text())["session_id"] == session["session_id"]:
        fork = {k: v for k, v in session.items() if k not in ("tmux_pane", "claude_pid")}
        ACTIVE.write_text(json.dumps(fork | {"session_id": json.loads(result.stdout)["session_id"]}))


def live_pane(session: dict) -> str | None:
    pane, pid = session.get("tmux_pane"), session.get("claude_pid")
    comm = Path(f"/proc/{pid}/comm")
    if not pane or not comm.exists() or comm.read_text().strip() != "claude":
        return None
    shell = subprocess.run(["tmux", "display", "-p", "-t", pane, "#{pane_pid}"], capture_output=True, text=True).stdout.strip()
    parent = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[1]
    return pane if shell == parent else None


def live_sessions() -> dict:
    found = {}
    for f in (CLAUDE_DIR / "sessions").glob("*.json"):
        s = json.loads(f.read_text())
        session = {"session_id": s["sessionId"], "tmux_pane": (s.get("tmux") or "").rpartition(".")[2] or None, "claude_pid": s["pid"]}
        if s.get("kind") == "interactive" and live_pane(session):
            found[s["sessionId"]] = session
    return found


def transcript_info(path: Path) -> dict:
    info = {"session_id": path.stem, "title": "", "permission_mode": None, "cwd": None}
    for line in path.open():
        if '"type":"custom-title"' in line:
            info["custom"] = json.loads(line)["customTitle"]
        elif '"type":"ai-title"' in line:
            info["title"] = json.loads(line)["aiTitle"]
        elif '"type":"last-prompt"' in line and not info["title"]:
            info["title"] = json.loads(line).get("lastPrompt", "")
        elif '"type":"permission-mode"' in line:
            info["permission_mode"] = json.loads(line)["permissionMode"]
        elif not info["cwd"] and '"cwd":"' in line:
            info["cwd"] = json.loads(line)["cwd"]
    info["title"] = info.pop("custom", info["title"])
    return info


def recent_sessions() -> list[dict]:
    live = live_sessions()
    files = sorted((CLAUDE_DIR / "projects").glob("*/*.jsonl"), key=lambda f: f.stat().st_mtime, reverse=True)
    picked = [f for f in files if f.stem in live] + [f for f in files if f.stem not in live]
    return [transcript_info(f) | live.get(f.stem, {}) for f in picked[:10]]


def label(session: dict) -> str:
    mark = "🟢" if "tmux_pane" in session else "⚪"
    return f"{mark} {Path(session['cwd'] or '?').name} · {' '.join(session['title'].split())}"[:60]


def show_sessions() -> None:
    buttons = [[{"text": "➕ New session", "callback_data": "new"}]]
    buttons += [[{"text": label(s), "callback_data": s["session_id"]}] for s in recent_sessions()]
    reply("Pick a session. Plain messages go to it.", reply_markup=json.dumps({"inline_keyboard": buttons}))


def new_session() -> None:
    cwd = str(Path.home() / "brain")
    window = subprocess.run(
        ["tmux", "new-window", "-d", "-t", "main:", "-c", cwd, "-P", "-F", "#{pane_id}"], capture_output=True, text=True
    )
    if window.returncode:
        reply(f"Could not open a tmux window: {window.stderr.strip()}")
        return
    pane = window.stdout.strip()
    subprocess.run(["tmux", "send-keys", "-t", pane, "claude", "Enter"])
    for _ in range(30):
        time.sleep(1)
        session = next((s for s in live_sessions().values() if s["tmux_pane"] == pane), None)
        if session:
            SESSIONS.mkdir(parents=True, exist_ok=True)
            ACTIVE.write_text(json.dumps(session | {"cwd": cwd}))
            reply(f"New session in tmux pane {pane}, in ~/brain. Plain messages go to it.")
            return
    reply(f"New session in tmux pane {pane} did not start.")


def pick_session(query: dict) -> None:
    try:
        api("answerCallbackQuery", callback_query_id=query["id"])
    except urllib.error.HTTPError:
        log.info("callback query expired")
    if query["data"] == "new":
        new_session()
        return
    session = next((s for s in recent_sessions() if s["session_id"] == query["data"]), None)
    if not session:
        reply("Session not found.")
        return
    SESSIONS.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(json.dumps(session))
    reply(f"Active: {label(session)}")


def deliver(session: dict, text: str, from_active: bool = False) -> None:
    pane = live_pane(session)
    if pane:
        typed = " ".join("".join(c for c in text if c.isprintable() or c.isspace()).split())
        subprocess.run(["tmux", "send-keys", "-t", pane, "-l", f"Telegram (answer there with the telegram-messaging skill): {typed}"])
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"])
        reply(f"Sent to the live session in tmux pane {pane}.")
        return
    threading.Thread(target=run_agent, args=(session, text, from_active)).start()
    reply("Session not live, forked it.")


def forward(msg: dict) -> None:
    if msg["text"].startswith("/sessions"):
        show_sessions()
        return
    replied = SESSIONS / f"{msg.get('reply_to_message', {}).get('message_id')}.json"
    if replied.exists():
        deliver(json.loads(replied.read_text()), msg["text"])
    elif ACTIVE.exists():
        deliver(json.loads(ACTIVE.read_text()), msg["text"], from_active=True)
    else:
        reply("Pick a session with /sessions or reply to an agent's message.")


def handle(msg: dict) -> None:
    if "text" in msg:
        forward(msg)
        return
    image = find_image(msg)
    if image:
        path = FILES / f"{msg['message_id']}{Path(image.get('file_name') or 'photo.jpg').suffix}"
        download(image["file_id"], path)
        forward(msg | {"text": f"{msg.get('caption', '')} [image: {path}]".strip()})
        return
    media = find_audio(msg)
    if not media:
        return
    size_mb = media.get("file_size", 0) / 1024 / 1024
    if media.get("file_size", 0) > MAX_BYTES:
        reply(f"Recording too long: {size_mb:.0f} MB, the limit is 20 MB.")
        return

    reply("Transcribing...")
    threading.Thread(target=transcribe, args=(msg, media)).start()


def transcribe(msg: dict, media: dict) -> None:
    with TRANSCRIPTIONS:
        try:
            write_transcript(msg, media)
        except Exception as e:
            log.exception("transcription failed")
            reply(f"Transcription failed: {e}")


def write_transcript(msg: dict, media: dict) -> None:
    recorded = datetime.fromtimestamp(msg["date"])
    name = f"{recorded:%Y-%m-%d-%H-%M-%S} Recording"
    with tempfile.TemporaryDirectory() as tmp:
        audio = Path(tmp) / f"audio{Path(media.get('file_name') or 'voice.ogg').suffix}"
        download(media["file_id"], audio)
        model = WhisperModel("large-v3-turbo", device="cpu", compute_type="int8")
        segments, info = model.transcribe(str(audio), vad_filter=True)
        lines = [f"[{timestamp(s.start)}] {s.text.strip()}" for s in segments]

    note = NOTES_DIR / f"{name}.md"
    note.write_text(
        f"---\ndate: {recorded:%Y-%m-%dT%H:%M}\nduration: {timestamp(info.duration)}\n"
        f"language: {info.language}\n---\n\n" + "\n".join(lines) + "\n"
    )
    link = "https://obsid.net/?" + urllib.parse.urlencode({"vault": "brain", "file": f"projects/meetings/{name}"})
    reply(f"Done: {name}", markup=f'Done: <a href="{html.escape(link)}">{name}</a> ({timestamp(info.duration)})')


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    api("setMyCommands", commands=json.dumps([{"command": "sessions", "description": "Pick an agent session"}]), scope=json.dumps({"type": "all_private_chats"}))
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
            query = update.get("callback_query")
            log.info(f"update {update['update_id']}: {sorted(msg or update)}")
            chat = (msg or (query or {}).get("message") or {}).get("chat", {}).get("id")
            if chat != CHAT_ID:
                continue
            try:
                pick_session(query) if query else handle(msg)
            except Exception as e:
                log.exception("handling failed")
                reply(f"Error: {e}")


if __name__ == "__main__":
    main()
