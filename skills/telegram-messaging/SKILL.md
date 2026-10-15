---
name: telegram-messaging
description: Send the user a short message on Telegram through their own bot. Use when the user asks to send, notify, ping or report something to them on Telegram, or when a long-running task should report its result to their phone.
---

```bash
python3 scripts/send.py <<'EOF'
<message>
EOF
```

Prints `sent <id>`, or the Telegram error.

## Writing

- Result first. No greeting, intro or sign-off.
- A few short lines. Long content goes elsewhere; the message carries the gist and a link.
- Say plainly what was not checked.
- Language of the conversation. Plain dash "-", never the em dash.

## Formatting

Telegram HTML only. Markdown shows up as literal characters.

- Tags: `<b>`, `<i>`, `<code>`, `<pre>`, `<a href="https://...">`, `<blockquote>`, `<blockquote expandable>`.
- Escape `&`, `<`, `>` as `&amp;`, `&lt;`, `&gt;`, also inside `href`.
- No headings, tables or Markdown lists. Lists are lines starting with `- `.
- Links must be `http(s)://`; other schemes are stripped.
- Max 4096 characters.
