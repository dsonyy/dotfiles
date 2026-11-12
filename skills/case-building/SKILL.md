---
name: case-building
description: Build a case for a bug or product problem at Conduct - the Linear ticket, linked PRs, a problem description and a clear repro, saved as one directory in the brain. Use when the user asks to build, open or write up a case, to reproduce a reported problem and document it, or to prepare a bug for handoff to another agent or person.
---

# Case building

A case is one directory that lets someone who was not there see the problem and reproduce it.
Build as much of it as the evidence allows, and say what is missing.

## Directory

`<YYYY-MM-DD> <short title>/` in the brain

- `Case.md`
- `screenshots/`
- `test-files/`: inputs used and outputs produced
- `Details.md`: only when needed, for code references, raw evidence, fix scope and open questions

## Case.md, in this order

1. Ticket: the Linear link, or "none". Search Linear before writing "none". Do not create or edit a ticket unless asked.
2. PRs: those linked on the ticket or found by its ID, or "none".
3. Problem: what the user sees and what they should see, in two or three sentences. Then one paragraph on the cause, if known.
4. Repro: numbered steps from a clean start with the exact inputs, ending in expected versus actual. If it did not reproduce, say so and what was tried.

## Rules

- Reproduce it yourself in the local app, the way a user would, before writing the repro. Steps copied from a report are a claim.
- Open Case.md with the one or two screenshots that show the fault, cropped to it, each with a line saying where to look. All other screenshots go at the end.
- Development or synthetic data only. Customer findings as counts, never names or values.
- Mark each fact as seen first-hand, read from code, or reported by someone.
- Record anything changed by accident during the repro.

Finish with the directory path and the list of what is missing.
