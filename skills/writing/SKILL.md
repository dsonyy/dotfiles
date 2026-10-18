---
name: writing
description: Write prose in a plain, factual reporting style and write up work sessions. Use when writing or rewriting any text for people to read, or when asked to write up or save what we did.
---

The Writing rules in the global CLAUDE.md still apply. This skill adds to them.

## Tone

- Report, do not narrate. Journalistic, plain, factual. No drama, suspense, punchlines or morals.
- Nothing is "huge", "crucial", "fascinating". Facts carry their own weight.
- No significance inflation: "plays a key role", "is a testament to", "marks a turning point", "reflects a broader trend".
- No trailing interpretation: ", highlighting...", ", which shows how...".
- No promotional words: "rich", "remarkable", "groundbreaking", "gem", "vibrant".
- No ending with outlook, lessons or "despite the challenges". End on state of things and open items.

## Language

- Plain copula: "is", not "serves as", "stands as", "represents".
- No "not only X but also Y", no "it's not X, it's Y" as decoration.
- No rule-of-three triplets for rhythm.
- One name per thing for the whole text. No synonym cycling.
- No hedging preambles ("information is limited, but likely..."). Write "unconfirmed" or "unknown" and say why.
- Attribute precisely: who, where, when. One source is not consensus. Mark what came from an agent or was not verified first-hand.
- Match the language of the conversation.

## Formatting

- Short paragraphs, blank line between them.
- Headings: one level (##), sentence case, by topic. No headings that only hold other headings.
- No bold in prose, no "**Label:** text" lists, no emoji, straight quotes.
- No section summaries ("In summary", "Overall").
- No reader-facing chat: "let me know", "I can also", "below is a detailed overview".
- Sources inline where used, and a full list at the end.

## Default form: work report

Used when asked to write up a session or work and no other form is named.

- Chronological, top to bottom, in the order things happened.
- First person plural ("we"). Not a dialogue, no tool calls. The user's words only as short quotes where they changed direction.
- Keep the technique: file names, paths, offsets, commands, numbers, exact error messages.
- Keep dead ends and mistakes: what failed, why, and how it was fixed.
- No length limit. As long as the content needs.
- End with where the results are and what is still open.
- Save to `~/brain/projects/<project>/SUMMARY.md`. Link the project's data folder if it has one.

## Before saving

Reread the text against every rule above and the CLAUDE.md Writing rules, and fix what you find.
