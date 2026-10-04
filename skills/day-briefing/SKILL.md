---
name: day-briefing
description: Summarize one day across Todoist, Gmail, Google Calendar, notes in ~/brain, code in ~/repos and agent sessions. Use when the user asks what happened on a day, what is on today, for a daily summary or a recap of yesterday.
---

# Day briefing

The day is today unless the user names one. Collect each source for that day, then write the brief.

Sources:
- Google Calendar: events of the day, plus the first event of the next day.
- Gmail: threads received and sent that day. Flag the ones waiting for my reply.
- Todoist: tasks completed that day, tasks due that day, overdue tasks.
- Notes: files in `~/brain` modified that day (`find -newermt`, skip `.obsidian`). Skim them for what they are about. Include the day's entry in `~/brain/LOG.md`.
- Code: for each git repo in `~/repos` (including `~/repos/worktrees`), my commits that day on all branches, plus uncommitted changes if the day is today.
- Agent sessions: Claude Code (`~/.claude/projects`) and Codex (`~/.codex/sessions`) sessions active that day. Read only the first user prompts to tell what each was about.

Skip a source silently if it has nothing for the day. Say so only if a source fails.

Format, in the user's language:
- Headline: the day in one sentence.
- **Calendar**: time, title, link.
- **Mail**: one bullet per thread; waiting-for-reply first.
- **Todoist**: done, due, overdue.
- **Work**: notes and repos grouped by project, one bullet per project.
- **Open loops**: a checkbox list of what is unfinished or needs a reply, ending with the single most important next step.

Show the brief in the chat only. Do not create or edit any files, tasks or emails.
