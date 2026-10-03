---
name: lingo-collecting
description: Collect unfamiliar terms, names, acronyms and phrases from a source (meeting transcript, slides, screenshots, docs, chat) into a growing per-project vocabulary file. Use when asked to build or update a vocabulary, glossary, lingo or jargon list, to explain the terms people used in a meeting, or when ramping up on a new team, company, domain or language.
---

Turn what other people say into terms the user can look up and reuse. One vocabulary file per project, growing over time.

## Inputs

- Sources: transcript, slide screenshots, docs. If a transcript is not at hand, locate it with the `using-transcripts` skill. Read images directly - slides often define what speakers only mention.
- Target file: the project's vocabulary file (e.g. `<project>/VOCABULARY.md`). Ask once if unclear. Read it fully before adding anything.

## What counts as a term

Collect what a smart newcomer would not know:

- Organisation-specific names: products, internal systems and tools, entities in their data model, customers, partners.
- Acronyms and abbreviations.
- Domain and industry jargon.
- Phrases and idioms that a non-native speaker may misread or not know.

Never add people's names - not as terms and not inside explanations. Skip general vocabulary and anything the user clearly already knows (check the user's notes and memory for their background). When in doubt, include it - a short entry is cheap, a missing one is not.

## File format

The file is a single markdown table and nothing else: no headings, bullet points, images or prose.

```markdown
| Term | Explanation | Sources |
|---|---|---|
| SI (System Integrator) | Consulting firm that runs implementation projects for clients. | [[source note]] 35:24, slide "Where we're going" |
```

- Term: the canonical name, with acronym expansion and aliases (including misheard spellings) in parentheses.
- Explanation: 1-2 sentences. A short quote only when it shows meaning better than a definition.
- Sources: link to the source note plus timestamp or slide name. Never embed images.
- Keep rows alphabetical. Use the language of the existing file; for a new file, the user's note language. Never put `|` inside a cell.
- Append `?` to the term when the meaning is inferred rather than stated, and say what the guess is based on. Never invent a definition.
- For public, well-known terms (industry standards, vendor products), a quick web check is fine; cite it inline.

## Merging into an existing file

- Same term already present: extend it - add the new usage and source, refine the definition. Never duplicate.
- Different words for the same thing: one entry, the others as aliases.
- Same word, different meanings: one entry, list each meaning separately.
- Do not reorder or rewrite entries you are not changing.

## Speech-to-text noise

Transcripts mangle names and jargon. Reconcile spellings against slides, docs and other sources. Fix the obvious ones, mark uncertain ones with `?`, keep the misheard form as an alias if it is likely to recur.

## Finish

Report how many terms were added and updated, and list the ones marked `?` so the user can confirm them.
