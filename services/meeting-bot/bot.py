import html
import json
import logging
import os
import shlex
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
CLAUDE_DIR = Path.home() / ".claude"

log = logging.getLogger("meetings")
RESUMES = threading.Lock()
DIRS = {"Home": "~", "Brain": "~/brain", "Repos": "~/repos", "Data": "~/data"}
awaiting_path = False
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


def show_dirs() -> None:
    buttons = [[{"text": name, "callback_data": f"new:{path}"}] for name, path in DIRS.items()]
    buttons += [[{"text": "Specify", "callback_data": "new:?"}]]
    reply("Where should the new session start?", reply_markup=json.dumps({"inline_keyboard": buttons}))


def start_claude(cwd: str, args: list[str]) -> dict | None:
    window = subprocess.run(
        ["tmux", "new-window", "-d", "-t", "main:", "-c", cwd, "-P", "-F", "#{pane_id}"], capture_output=True, text=True
    )
    if window.returncode:
        reply(f"Could not open a tmux window: {window.stderr.strip()}")
        return None
    pane = window.stdout.strip()
    subprocess.run(["tmux", "send-keys", "-t", pane, shlex.join(["claude", *args]), "Enter"])
    for _ in range(30):
        time.sleep(1)
        session = next((s for s in live_sessions().values() if s["tmux_pane"] == pane), None)
        if session:
            return session
    reply(f"Claude in tmux pane {pane} did not start.")
    return None


def activate(session: dict) -> dict:
    SESSIONS.mkdir(parents=True, exist_ok=True)
    ACTIVE.write_text(json.dumps(session))
    return session


def new_session(path: str) -> None:
    cwd = Path(path).expanduser()
    if not cwd.is_dir():
        reply(f"No such directory: {path}. Send another path or /sessions.")
        return
    global awaiting_path
    awaiting_path = False
    session = start_claude(str(cwd), [])
    if session:
        activate(session | {"cwd": str(cwd)})
        reply(f"New session in tmux pane {session['tmux_pane']}, in {path}. Plain messages go to it.")


def resume(session: dict) -> dict | None:
    live = live_sessions().get(session["session_id"])
    if live:
        return activate(session | live)
    mode = ["--permission-mode", session["permission_mode"]] if session.get("permission_mode") else []
    reply("Session not live, resuming it.")
    started = start_claude(session["cwd"], ["--resume", session["session_id"], *mode])
    return started and activate(session | started)


def pick_session(query: dict) -> None:
    try:
        api("answerCallbackQuery", callback_query_id=query["id"])
    except urllib.error.HTTPError:
        log.info("callback query expired")
    global awaiting_path
    if query["data"] == "new":
        show_dirs()
        return
    if query["data"] == "new:?":
        awaiting_path = True
        reply("Send the directory path.")
        return
    if query["data"].startswith("new:"):
        new_session(query["data"][4:])
        return
    session = next((s for s in recent_sessions() if s["session_id"] == query["data"]), None)
    if not session:
        reply("Session not found.")
        return
    activate(session)
    reply(f"Active: {label(session)}")


def deliver(session: dict, text: str) -> None:
    with RESUMES:
        session = session if live_pane(session) else resume(session)
        if not session:
            return
        pane = session["tmux_pane"]
        typed = " ".join("".join(c for c in text if c.isprintable() or c.isspace()).split())
        subprocess.run(["tmux", "send-keys", "-t", pane, "-l", f"Telegram (answer there with the telegram-messaging skill): {typed}"])
        subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"])
    reply(f"Sent to the live session in tmux pane {pane}.")


def forward(msg: dict) -> None:
    global awaiting_path
    if msg["text"].startswith("/sessions"):
        awaiting_path = False
        show_sessions()
        return
    if awaiting_path:
        threading.Thread(target=new_session, args=(msg["text"].strip(),)).start()
        return
    replied = SESSIONS / f"{msg.get('reply_to_message', {}).get('message_id')}.json"
    if replied.exists():
        threading.Thread(target=deliver, args=(json.loads(replied.read_text()), msg["text"])).start()
    elif ACTIVE.exists():
        threading.Thread(target=deliver, args=(json.loads(ACTIVE.read_text()), msg["text"])).start()
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
