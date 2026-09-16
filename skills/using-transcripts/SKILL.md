---
name: using-transcripts
description: Locate the transcript of a call, meeting, or recording whenever the user refers to one - even without naming where it lives.
---

Order of lookup for transcript request:

1. Google Drive - Google Docs with the transcripts are stored in /projects/transcripts
2. Local files - search in the current directory, ask user for hint if nothing found.

When reading transcripts, most of the things are fine, but be aware that sometimes:

- names of the persons might be mismatched (different account names, multiple persons using the same account / microphone)
- some phrases can be incorrectly transcribed from speech to text, especially names, technical terms
- sometimes badly configured language can generate completely incorrect transcription

Other stuff:

- My name is Szymon Bednorz
