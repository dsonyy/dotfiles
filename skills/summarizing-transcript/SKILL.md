---
name: summarizing-transcript
description: Summarize a call, meeting, or recording transcript into a filtered Q&A document. Use whenever asked to summarize, distill, or extract notes, insights, or takeaways from a transcript of any kind of conversation.
---

If the transcript is not already at hand, locate it with the `using-transcripts` skill.

Output is a markdown document in Q&A form, grouped by topic, not chronological.

## Rules

- Every claim becomes a question plus its answer. Question is what was really being asked, not the literal wording.
- Group questions under topic headings. Order topics by importance, not by when they came up.
- Lose nothing the speakers said that carries information. Drop greetings, scheduling chatter, filler, repetition, ASR noise.
- Answers in my own words, compressed. Quote only when the exact wording matters.
- ASR mangles names, companies and technical terms. Fix the obvious ones, mark uncertain ones with `?`, never silently invent.
- Keep numbers, dates, names, statuses and commitments verbatim.
- Do not add analysis or opinion unless asked. If asked, put it in a clearly separate section at the end.
- Link to the transcript file and related notes at the top.
- Match the language of the transcript.
