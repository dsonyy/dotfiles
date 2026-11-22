import fcntl
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
GROUP_ID = int(os.environ["TELEGRAM_GROUP_ID"])
API = f"https://api.telegram.org/bot{TOKEN}"
MAX_BYTES = 20 * 1024 * 1024
NOTES_DIR = Path.home() / "brain/projects/meetings"
FILES = Path.home() / ".cache/telegram-sessions/files"
CLAUDE_DIR = Path.home() / ".claude"
BRAIN = Path.home() / "brain"
STATE = Path.home() / ".local/state/meeting-bot"
MAIN = STATE / "main.json"
TOPICS = STATE / "topics.json"
BOT_WINDOW = "main:=bot"
PROMPT = "Telegram (answer there with the telegram-messaging skill): "
COMPACT_AFTER = 55 * 60
COMPACT_TOKENS = 50_000
SWEEP_AFTER = 7 * 24 * 3600
DISARMED = Path.home() / ".alarm"
CAMERA_LOCK = Path("/tmp/camera.lock")

log = logging.getLogger("meetings")
RESUMES = threading.Lock()
STATE_LOCK = threading.Lock()
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
    log.info(f"reply sent: {api('sendMessage', **{'chat_id': CHAT_ID} | params, text=body, parse_mode='HTML')['message_id']} {text}")


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


def transcript(session_id: str) -> Path | None:
    return next((CLAUDE_DIR / "projects").glob(f"*/{session_id}.jsonl"), None)


def context_tokens(session_id: str) -> int:
    usage = {}
    for line in transcript(session_id).open():
        if '"type":"assistant"' in line:
            usage = json.loads(line)["message"].get("usage") or usage
    return sum(usage.get(k, 0) for k in ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens"))


def load(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def store(thread: str | None, **fields) -> dict:
    with STATE_LOCK:
        if thread is None:
            path, data = MAIN, load(MAIN) | fields
            result = data
        else:
            path, data = TOPICS, load(TOPICS)
            data[thread] = result = data.get(thread, {}) | fields
        STATE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=1))
    return result


def place(thread: str | None) -> dict:
    return {"chat_id": CHAT_ID} if thread is None else {"chat_id": GROUP_ID, "message_thread_id": thread}


def link(thread: str) -> str:
    return f"https://t.me/c/{str(GROUP_ID).removeprefix('-100')}/{thread}"


def start_claude(args: list[str], thread: str | None) -> dict | None:
    exists = subprocess.run(["tmux", "list-panes", "-t", BOT_WINDOW], capture_output=True).returncode == 0
    create = ["split-window", "-d", "-t", BOT_WINDOW] if exists else ["new-window", "-d", "-t", "main:", "-n", "bot"]
    window = subprocess.run(["tmux", *create, "-c", str(BRAIN), "-P", "-F", "#{pane_id}"], capture_output=True, text=True)
    if window.returncode:
        reply(f"Could not open a tmux pane: {window.stderr.strip()}", **place(thread))
        return None
    subprocess.run(["tmux", "select-layout", "-t", BOT_WINDOW, "tiled"])
    pane = window.stdout.strip()
    env = [] if thread is None else [f"TELEGRAM_CHAT_ID={GROUP_ID}", f"TELEGRAM_THREAD_ID={thread}"]
    subprocess.run(["tmux", "send-keys", "-t", pane, shlex.join(["env", *env, "claude", *args]), "Enter"])
    for _ in range(30):
        time.sleep(1)
        session = next((s for s in live_sessions().values() if s["tmux_pane"] == pane), None)
        if session:
            return session
    reply(f"Claude in tmux pane {pane} did not start.", **place(thread))
    return None


def live(thread: str | None) -> dict | None:
    session = load(MAIN) if thread is None else load(TOPICS)[thread]
    if live_pane(session):
        return session
    args = ["--resume", session["session_id"]] if session.get("session_id") else []
    if args:
        reply("Session not live, resuming it.", **place(thread))
    started = start_claude(args, thread)
    return started and store(thread, **started)


def type_into(pane: str, text: str) -> None:
    typed = " ".join("".join(c for c in text if c.isprintable() or c.isspace()).split())
    subprocess.run(["tmux", "send-keys", "-t", pane, "-l", typed])
    subprocess.run(["tmux", "send-keys", "-t", pane, "Enter"])


def deliver(thread: str | None, text: str, message_id: int) -> None:
    with RESUMES:
        session = live(thread)
        if not session:
            return
        type_into(session["tmux_pane"], text)
    api("setMessageReaction", chat_id=place(thread)["chat_id"], message_id=message_id, reaction=json.dumps([{"type": "emoji", "emoji": "👀"}]))


def start_topic(thread: str) -> None:
    with RESUMES:
        session = live(thread)
    if session:
        reply(f"Session started in tmux pane {session['tmux_pane']}.", **place(thread))


def new_topic(name: str, private: bool) -> None:
    if not name:
        reply("Usage: /new <name>", chat_id=CHAT_ID if private else GROUP_ID)
        return
    thread = str(api("createForumTopic", chat_id=GROUP_ID, name=name)["message_thread_id"])
    store(thread, name=name, last_activity=time.time(), closed=False)
    if private:
        reply(f"Topic {name}: {link(thread)}")
    threading.Thread(target=start_topic, args=(thread,)).start()


def maintain() -> None:
    main = load(MAIN)
    if main.get("last_message") and not main.get("compacted") and time.time() - main["last_message"] > COMPACT_AFTER:
        store(None, compacted=True)
        tokens = context_tokens(main["session_id"])
        if live_pane(main) and tokens > COMPACT_TOKENS:
            type_into(main["tmux_pane"], "/compact")
            log.info(f"main session compacted at {tokens} tokens")
    for thread, topic in load(TOPICS).items():
        path = transcript(topic.get("session_id", ""))
        idle = time.time() - max(topic["last_activity"], path.stat().st_mtime if path else 0)
        if topic["closed"] or idle < SWEEP_AFTER:
            continue
        try:
            api("closeForumTopic", chat_id=GROUP_ID, message_thread_id=thread)
        except urllib.error.HTTPError:
            log.info(f"topic {thread} was already closed")
        if live_pane(topic):
            subprocess.run(["tmux", "kill-pane", "-t", topic["tmux_pane"]])
        store(thread, closed=True)
        log.info(f"topic {thread} swept")


def alarm_status() -> tuple[str, str]:
    on = not DISARMED.exists()
    button = {"text": "Turn off" if on else "Turn on", "callback_data": "alarm:off" if on else "alarm:on"}
    photo = {"text": "Take photo", "callback_data": "photo"}
    return f"Alarm is {'on' if on else 'off'}.", json.dumps({"inline_keyboard": [[button, photo]]})


def show_alarm() -> None:
    text, markup = alarm_status()
    reply(text, reply_markup=markup)


def set_alarm(query: dict) -> None:
    DISARMED.touch() if query["data"] == "alarm:off" else DISARMED.unlink(missing_ok=True)
    text, markup = alarm_status()
    api("editMessageText", chat_id=CHAT_ID, message_id=query["message"]["message_id"], text=f"<i>{html.escape(text)}</i>", parse_mode="HTML", reply_markup=markup)
    log.info(f"alarm set: {text}")


def take_photo() -> bytes:
    # webcam-alarm holds the same lock while it opens the exclusive camera
    with CAMERA_LOCK.open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        return subprocess.run(
            ["ffmpeg", "-loglevel", "error", "-fflags", "nobuffer", "-f", "v4l2", "-input_format", "mjpeg",
             "-video_size", "1280x720", "-i", "/dev/video0", "-frames:v", "1", "-c:v", "copy", "-f", "mjpeg", "-"],
            capture_output=True, check=True,
        ).stdout


def send_photo() -> None:
    try:
        jpeg = take_photo()
    except subprocess.CalledProcessError as e:
        reply(f"Camera failed: {e.stderr.decode().strip()}")
        return
    boundary = os.urandom(16).hex()
    body = f'--{boundary}\r\nContent-Disposition: form-data; name="photo"; filename="cam.jpg"\r\n\r\n'.encode()
    body += jpeg + f"\r\n--{boundary}--\r\n".encode()
    headers = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
    with urllib.request.urlopen(urllib.request.Request(f"{API}/sendPhoto?chat_id={CHAT_ID}", body, headers), timeout=90) as resp:
        log.info(f"photo sent: {json.load(resp)['result']['message_id']}")


def answer(query: dict) -> None:
    try:
        api("answerCallbackQuery", callback_query_id=query["id"])
    except urllib.error.HTTPError:
        log.info("callback query expired")


def command(text: str) -> tuple[str, str]:
    head, _, arg = text.partition(" ")
    return head.partition("@")[0], arg.strip()


def forward(msg: dict) -> None:
    name, arg = command(msg["text"])
    if name == "/alarm":
        show_alarm()
        return
    if name == "/new":
        new_topic(arg, private=True)
        return
    if name == "/compact":
        threading.Thread(target=deliver, args=(None, "/compact", msg["message_id"])).start()
        return
    main = store(None, last_message=time.time(), compacted=False)
    topics = load(TOPICS)
    owner = next((t for t in topics if topics[t].get("session_id") == main.get("session_id")), None)
    if owner:
        reply(f"This session lives in topic {topics[owner]['name']}: {link(owner)}")
        return
    threading.Thread(target=deliver, args=(None, PROMPT + msg["text"], msg["message_id"])).start()


def group(msg: dict) -> None:
    if "text" not in msg:
        return
    name, arg = command(msg["text"])
    if name == "/new":
        new_topic(arg, private=False)
        return
    thread = str(msg["message_thread_id"]) if msg.get("is_topic_message") else None
    if thread not in load(TOPICS):
        reply("Start a topic with /new <name>.", **(place(thread) if thread else {"chat_id": GROUP_ID}))
        return
    store(thread, last_activity=time.time(), closed=False)
    threading.Thread(target=deliver, args=(thread, PROMPT + msg["text"], msg["message_id"])).start()


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
    new = {"command": "new", "description": "Start a session in a new topic"}
    compact = {"command": "compact", "description": "Compact the main session"}
    alarm = {"command": "alarm", "description": "Turn the camera alarm on or off"}
    api("setMyCommands", commands=json.dumps([alarm, new, compact]), scope=json.dumps({"type": "all_private_chats"}))
    api("setMyCommands", commands=json.dumps([new]), scope=json.dumps({"type": "chat", "chat_id": GROUP_ID}))
    offset = 0
    while True:
        try:
            maintain()
        except Exception:
            log.exception("maintenance failed")
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
            if (msg or query or {}).get("from", {}).get("id") != CHAT_ID or chat not in (CHAT_ID, GROUP_ID):
                continue
            try:
                if query:
                    answer(query)
                    if query["data"] == "photo":
                        send_photo()
                    elif query["data"].startswith("alarm:"):
                        set_alarm(query)
                elif chat == GROUP_ID:
                    group(msg)
                else:
                    handle(msg)
            except Exception as e:
                log.exception("handling failed")
                reply(f"Error: {e}")


if __name__ == "__main__":
    main()
