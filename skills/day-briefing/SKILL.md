---
name: day-briefing
description: Brief the user on a day or a period across every connected source - calendar, mail, chat, issue tracker, pull requests, docs, notes in the brain, code in ~/repos and agent sessions - with action points first. Use when the user asks what happened on a day, what is on today, what they missed, what they should be aware of, for a daily summary or a recap of yesterday or of a period.
---

# Day briefing

The period is today unless the user names a day or a start ("since Friday", "last 24h"). Collect every source for that period, then write the brief.

## Sources

Use every source the session has a tool for. List the available tools first, so no connected source is left out.

- Calendar: events of the period, the rest of today, and the first event of the next day. Note invitations I have not answered.
- Mail: threads received and sent. Open any thread from a person or with a deadline; a subject line is not enough.
- Chat (Slack or similar):
  - my direct messages and group messages
  - every mention of me, by handle and by plain first name
  - every channel I am a member of, read from the start of the period. List my channels first, then read each one. Only alert-bot and social channels may be skimmed.
  - threads I took part in or was asked something in, read to the end, to see whether I answered
  - my own messages in the period, to tell answered asks from unanswered ones
- Issue tracker: my inbox, issues assigned to me that changed, and issues that are overdue or due this week.
- Pull requests: mine that are open (reviews, unresolved threads, CI as it reports now), mine that merged, and reviews requested from me. Check what others merged in the areas my open work touches.
- Docs and wiki: pages where a person mentioned or assigned me.
- Task manager: tasks completed, due and overdue. Personal briefs only.
- Notes: files in the brain modified in the period (`find -newermt`, skip `.obsidian`). Skim them for what they are about. Include the entries from the daily log, when the brain has one: `projects/<YYYY>/<YYYY>.md`, under the `## YYYY-MM` section.
- Code: for each git repo in `~/repos` (including `~/repos/worktrees`), my commits in the period on all branches, plus uncommitted changes if the period includes today.
- Agent sessions: Claude Code (`~/.claude/projects`) and Codex (`~/.codex/sessions`) sessions active in the period. Read only the first user prompts to tell what each was about.

Rules for collecting:

- A search returns one page. Follow the cursor until the start of the period is reached, or read the channel directly.
- Announcements to everyone count even when they do not name me. Look for sign-ups, registrations, booking sheets, RSVPs, forms, polls and deadlines in the company-wide and event channels.
- Verify before stating: whether I already replied, what CI shows now, who owns an item. Write "unknown" for what was not checked.
- Skip a source silently if it has nothing. Say so only if a source fails.

## What is an action point

- A question or request a person addressed to me that I have not answered.
- An announcement that asks everyone to do something by a date.
- An invitation I have not answered, or a meeting today that needs preparation.
- An item assigned to me that is overdue or due within two days.

Not an action point: a notification that only mentions me, a meeting summary from a bot, work already in progress, an open pull request with nothing waiting on me. If nothing is open, say so in one line.

## Format

In the user's language. Every item carries a clickable markdown link to its source: the message permalink, the thread, the pull request, the issue, the mail, the calendar event, the doc.

- Headline: the period in one sentence.
- **Action points**: first, as a checkbox list ordered by deadline. Each line: what to do, for whom, by when, link. Deadlines as dates.
- **Calendar**: time, title, link.
- **Chat**: what was decided or announced, grouped by topic, each with its link.
- **Mail**: one bullet per thread.
- **Issues and pull requests**: one bullet per item, with number and link.
- **Work**: notes and repos grouped by project, one bullet per project.
- **Coverage**: one line naming the sources and channels read in full, skimmed, or not read.

Show the brief in the chat only. Do not create or edit any files, tasks, messages or emails.
