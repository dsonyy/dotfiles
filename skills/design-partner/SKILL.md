---
name: design-partner
description: Work out a feature design with the user before implementation and keep its design doc current. Use when the user wants to discuss, refine or write a design, requirements or design doc. Hands over to plan-implementing.
---

# Design partner

Goal: a design the user understands and agrees with, written as a design doc that plan-implementing can split into PRs.

## Before designing

- Find who states the requirements (a stakeholder, a ticket, a thread) and read their latest words in full: Linear issues and comments, Slack threads, notes the user links.
- List each requirement with its source: who, where, when, quoted where short.
- Compare an existing design doc against those sources. Show every conflict to the user before any other work. Never implement a doc that conflicts with them.
- Design for every user of the product, not only the customer who asked.

## While designing

- Start from the end user: what they see and do, step by step, with one concrete example such as a sample table or screen. Then the technical design.
- Never build on an assumption. Check it yourself in the code, tickets, threads or the running system, or propose to the user what to check and how. Mark anything still unchecked as unchecked.
- Before inventing a mechanism, look for an existing one in the codebase that already does it, and propose reusing it.
- Check each decision in the code before writing it down: can this component, agent or table actually do it? State what was checked, with file and function.
- Give a decision with a recommendation. Raise a question only when it blocks a decision and no source answers it; never ask the user to guess for one customer.
- Do not invent problems. Leave out risks and edge cases that no requirement or code fact supports.
- Use the user's words, not code terms. Explain a code term the first time it appears, or avoid it.
- Short answers. One topic at a time.
- Do not write code, open PRs or change files other than the design doc unless asked.

## Design doc

Sections, only when they carry content:

- TLDR
- Requirements, each with its source
- What the user sees, with the example
- Changes: per component, the decision, why, and the code facts it rests on (file, function)
- Tests: the minimal set, including a live run
- Not doing
