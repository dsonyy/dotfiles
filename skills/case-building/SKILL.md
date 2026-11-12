---
name: case-building
description: Build a case for a bug or product problem at Conduct - the problem with a repro and the solution with before and after, linked to the Linear ticket and the PRs, saved as one directory in the brain. Use when the user asks to build, open or write up a case, to reproduce a reported problem and document it, or to prepare a bug for handoff to another agent or person.
---

# Case building

A case is one directory in the brain, `<YYYY-MM-DD> <short title>/`, that shows someone who was not there what the problem is and where to look.

## Files

- `Case.md`: the problem. Ticket and PR links, what the user sees and what they should see, repro steps ending in expected versus actual.
- `Solution.md`: the fix. Before and after from the same repro, and where the change is. Written once a fix exists.
- Optional: `screenshots/`, `test-files/` for inputs and outputs, anything else the reader needs.

## Rules

- Minimal. Only what the reader needs to understand the problem and know where to look. Link, do not repeat: the ticket, the PR and the code say their own part.
- Show it. Lead with a screenshot cropped to the fault, a table or another visual, with one line saying where to look.
- Reproduce it yourself in the local app, the way a user would, and take before and after from that run. Say when something was read from code or reported, not seen.
- Development or synthetic data only. Customer findings as counts, never names or values.
- Linear is the product side: what the user sees, who it affects, what they should get. GitHub is the technical side, written as the repository's pull request guide says. Search both before writing "none". Create or edit them only when asked.
- Record anything the repro changed.

Finish with the directory path and what is missing.
