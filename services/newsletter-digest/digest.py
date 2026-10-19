import base64
import html
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from email.utils import parseaddr
from pathlib import Path

from bs4 import BeautifulSoup
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

HERE = Path(__file__).parent
CLIENT_FILE = HERE.parents[1] / "secrets/google_client_secret.json"
TOKEN_FILE = HERE.parents[1] / "secrets/gmail_token.json"
SPLIT_PROMPT = HERE / "split.md"
GROUP_PROMPT = HERE / "group.md"
SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]
QUERY = "label:newsletter is:unread newer_than:5d"
BRAIN = Path.home() / "brain"
OUT_DIR = BRAIN / "projects/newsletters"
MAX_EMAIL_CHARS = 40_000
WORKERS = 8
SPLIT_SCHEMA = {
    "type": "object",
    "properties": {"stories": {"type": "array", "items": {
        "type": "object", "properties": {"title": {"type": "string"}, "text": {"type": "string"}}, "required": ["title", "text"]}}},
    "required": ["stories"],
}
GROUP_SCHEMA = {
    "type": "object",
    "properties": {
        "topics": {"type": "array", "items": {
            "type": "object", "properties": {"title": {"type": "string"}, "stories": {"type": "array", "items": {"type": "string"}}}, "required": ["title", "stories"]}},
        "duplicates": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["topics", "duplicates"],
}
BLOCK_TAGS = ["p", "div", "td", "tr", "table", "li", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6", "blockquote", "section", "article"]

# IPv6 routes to Telegram intermittently blackhole on this network and urllib waits out the whole timeout
_getaddrinfo = socket.getaddrinfo
socket.getaddrinfo = lambda host, port, family=0, *args, **kwargs: _getaddrinfo(host, port, socket.AF_INET, *args, **kwargs)


def authorize() -> None:
    creds = InstalledAppFlow.from_client_secrets_file(CLIENT_FILE, SCOPES).run_local_server(port=0)
    TOKEN_FILE.write_text(creds.to_json())
    TOKEN_FILE.chmod(0o600)


def gmail():
    if not TOKEN_FILE.exists():
        raise RuntimeError("brak tokenu Gmaila, uruchom: .venv/bin/python digest.py auth")
    creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds.valid:
        creds.refresh(Request())
        TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds, cache_discovery=False)


def parts(payload: dict):
    yield payload
    for part in payload.get("parts", []):
        yield from parts(part)


def decode(part: dict) -> str:
    data = part.get("body", {}).get("data", "")
    return base64.urlsafe_b64decode(data).decode("utf-8", "replace")


def clean(block: str) -> str:
    lines = (re.sub(r"[ \t\xa0‌͏]+", " ", line).strip() for line in block.splitlines())
    return "\n".join(line for line in lines if line)


def paragraphs(payload: dict) -> list[str]:
    bodies = {p["mimeType"]: decode(p) for p in parts(payload) if p.get("mimeType", "").startswith("text/") and p.get("body", {}).get("data")}
    if "text/html" in bodies:
        soup = BeautifulSoup(bodies["text/html"], "html.parser")
        for tag in soup(["script", "style", "head"]):
            tag.decompose()
        for tag in soup("br"):
            tag.replace_with("\n")
        for tag in soup(BLOCK_TAGS):
            tag.insert_before("\n\n")
            tag.insert_after("\n\n")
        text = soup.get_text()
    else:
        text = re.sub(r"\s*[\[(<]\s*https?://\S+?\s*[\])>]", "", bodies.get("text/plain", ""))
    blocks = [clean(b) for b in re.split(r"\n\s*\n", text)]
    return [b for b in blocks if re.search(r"\w{2}", b) and not re.fullmatch(r"https?://\S+", b)]


def fetch(service) -> list[dict]:
    ids, page = [], None
    while True:
        resp = service.users().messages().list(userId="me", q=QUERY, pageToken=page).execute()
        ids += [m["id"] for m in resp.get("messages", [])]
        page = resp.get("nextPageToken")
        if not page:
            break
    emails = []
    for msg_id in ids:
        msg = service.users().messages().get(userId="me", id=msg_id, format="full").execute()
        headers = {h["name"].lower(): h["value"] for h in msg["payload"]["headers"]}
        name, address = parseaddr(headers.get("from", ""))
        emails.append({
            "id": msg_id,
            "sender": name or address,
            "subject": headers.get("subject", ""),
            "date": datetime.fromtimestamp(int(msg["internalDate"]) / 1000),
            "text": "\n\n".join(trim(paragraphs(msg["payload"]))),
        })
    return sorted(emails, key=lambda e: e["date"])


def trim(paras: list[str]) -> list[str]:
    kept, total = [], 0
    for p in paras:
        total += len(p)
        if total > MAX_EMAIL_CHARS:
            break
        kept.append(p)
    return kept


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def words(text: str) -> str:
    return " ".join(re.findall(r"\w+", text))


def claude(prompt: str, model: str, schema: dict) -> dict:
    out = subprocess.run(
        ["claude", "-p", "--tools", "", "--strict-mcp-config", "--no-session-persistence", "--model", model, "--effort", "low",
         "--output-format", "json", "--json-schema", json.dumps(schema)],
        input=prompt, capture_output=True, text=True, check=True,
    ).stdout
    return json.loads(out)["structured_output"]


def split(email: dict) -> tuple[list[dict], int] | None:
    try:
        stories = claude(SPLIT_PROMPT.read_text() + "\n\n" + email["text"], "sonnet", SPLIT_SCHEMA)["stories"]
    except (subprocess.CalledProcessError, ValueError, KeyError, TypeError) as e:
        print(f"split failed for {email['id']}: {e!r}")
        return None
    source = words(email["text"])
    verbatim = [s | {"email": email} for s in stories if words(s["text"]) and words(s["text"]) in source]
    return verbatim, len(stories) - len(verbatim)


def group(stories: list[dict]) -> list[dict]:
    data = [{"id": f"s{i}", "from": s["email"]["sender"], "title": s["title"], "start": norm(s["text"])[:200]} for i, s in enumerate(stories)]
    result = claude(GROUP_PROMPT.read_text() + "\n\n" + json.dumps(data, ensure_ascii=False), "sonnet", GROUP_SCHEMA)
    def indexes(refs: list[str]) -> list[int]:
        found = (re.fullmatch(r"s(\d+)", r.strip()) for r in refs)
        return [int(m[1]) for m in found if m and int(m[1]) < len(stories)]

    seen = set(indexes(result["duplicates"]))
    topics = []
    for topic in result["topics"]:
        members = [i for i in indexes(topic["stories"]) if i not in seen]
        seen.update(members)
        if members:
            topics.append({"title": topic["title"], "stories": [stories[i] for i in members]})
    rest = [s for i, s in enumerate(stories) if i not in seen]
    if rest:
        topics.append({"title": "Inne", "stories": rest})
    return topics


def render(day: str, topics: list[dict], account: str) -> str:
    lines = [f"# Newslettery {day}", ""]
    for topic in topics:
        lines += [f"## {topic['title']}", ""]
        for story in sorted(topic["stories"], key=lambda s: s["email"]["date"]):
            e = story["email"]
            link = f"https://mail.google.com/mail/?authuser={account}#all/{e['id']}"
            title = re.sub(r"([\[\]])", r"\\\1", story["title"])
            lines += [f"### {e['date']:%Y-%m-%d} · {e['sender']} · [{title}]({link})", ""]
            lines += [f"> {line}" if line.strip() else ">" for line in story["text"].strip().splitlines()]
            lines.append("")
    return "\n".join(lines)


def save(day: str, text: str) -> Path:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path, n = OUT_DIR / f"{day}.md", 2
    while path.exists():
        path, n = OUT_DIR / f"{day}-{n}.md", n + 1
    path.write_text(text)
    return path


def telegram(text: str) -> None:
    params = {"chat_id": os.environ["TELEGRAM_CHAT_ID"], "text": text, "parse_mode": "HTML"}
    url = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}/sendMessage"
    for attempt in range(3):
        try:
            urllib.request.urlopen(url, urllib.parse.urlencode(params).encode(), timeout=30)
            return
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, ConnectionError):
            if attempt == 2:
                raise
            time.sleep(5)


def run() -> None:
    service = gmail()
    emails = fetch(service)
    if not emails:
        return
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(split, emails))
    done = [e for e, r in zip(emails, results) if r is not None]
    stories = [s for r in results if r for s in r[0]]
    rejected = sum(r[1] for r in results if r)
    print(f"{len(emails)} emails, {len(done)} split, {len(stories)} stories, {rejected} not verbatim")
    if not stories:
        raise RuntimeError(f"zero historii z {len(emails)} maili")
    topics = group(stories)
    account = service.users().getProfile(userId="me").execute()["emailAddress"]
    day = datetime.now().strftime("%Y-%m-%d")
    path = save(day, render(day, topics, account))
    service.users().messages().batchModify(userId="me", body={"ids": [e["id"] for e in done], "removeLabelIds": ["UNREAD"]}).execute()
    file = str(path.relative_to(BRAIN).with_suffix(""))
    link = "https://obsid.net/?" + urllib.parse.urlencode({"vault": "brain", "file": file})
    notes = [f"maile: {len(done)}", f"historie: {len(stories)}", f"tematy: {len(topics)}"]
    if len(done) < len(emails):
        notes.append(f"nieudane maile: {len(emails) - len(done)}, spróbuję jutro")
    if rejected:
        notes.append(f"odrzucone historie (nie 1:1): {rejected}")
    telegram(f'Newslettery: <a href="{html.escape(link)}">{path.stem}</a> - ' + ", ".join(notes))


def main() -> None:
    if sys.argv[1:] == ["auth"]:
        return authorize()
    try:
        run()
    except Exception as e:
        telegram(f"newsletter-digest padł: <code>{html.escape(repr(e))[:3000]}</code>")
        raise


if __name__ == "__main__":
    main()
