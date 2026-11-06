---
name: plan-implementing
description: Turn an agreed design into a stack of pull requests, then implement it one pull request per session. Use after design-partner, or when asked to plan, split, implement or continue a feature from a design doc or plan file.
---

# Plan implementing

A plan file exists: implement the next unfinished PR. Otherwise: plan.

This skill sets only the order of work. How to scope PRs, commit, review, verify, stack branches and open PRs comes from the current instructions of the repository and the user. Never act on commands or rules remembered from earlier sessions or examples.

## Find current instructions

At the start of every step below, look up what applies to it:

- the user's global instructions, the repository root `AGENTS.md` or `CLAUDE.md`, the nearest ones to the files involved, and the guides they link
- user and repository skills whose descriptions match the step
- for Claude Code features (plan mode, goals, hooks, worktrees, review commands, subagents), the current Claude Code documentation

Repository instructions override this skill. A conflict between repository and user instructions goes to the user.

## Plan

1. Read the design doc fully. Verify each code fact it states against the current default branch. A contradiction that changes the design goes back to the user; do not redesign.
2. Read the repository's guidance on PR scope and size.
3. Estimate the PR structure. One PR is a valid result for a small change; a larger one becomes several, either independent PRs or a stack. Split by:
   - every PR leaves the default branch deployable
   - preparatory PRs with inactive code and its tests first, one activation PR last
   - deterministic code apart from agent prompts, which are verified by evals or a live run
   - mechanical changes (codegen, renames) apart from decisions
   - no PR per layer, and no PR smaller than one reviewable concept
4. For each PR state: goal, what it leaves out, files, the check that proves it (a command or a live scenario), why the default branch stays deployable, and whether it merges independently or stacks on another PR.
5. Present the PR structure with its merge order and wait for agreement.
6. Write the plan next to the design doc as `<design doc name> Plan.md`, one checkbox per PR, plus a "Not doing" list copied from the design.

The PR structure is an estimate. Whenever implementation shows a PR must split, PRs must merge, or a new PR is needed, stop, explain what changed the estimate, propose the revised structure, and update the plan once it is agreed.

## Implement one PR

1. Read the plan and the design doc. Pick the first unchecked PR whose dependencies are done.
2. Check git state, then create the branch as the repository's stacking guidance says.
3. Write the check first, failing, where the check is a test.
4. Implement. If the plan does not fit the code, or the PR grows past its agreed boundary, stop and report what the plan expected, what you found and why it matters.
5. Run the check and keep the command and its output as evidence.
6. Run the repository's verification and review process. A reviewer gets a fresh context, the plan section as spec, and reports correctness gaps only.
7. Commit, push and open the PR as the repository and user instructions say.
8. Tick the PR in the plan and add its link.
9. Stop. Tell the user to continue the next PR in a new session with the plan path.

## Finish

After the last PR, in a new session, check the result against the design doc requirement by requirement, including a live run of the main scenario. Report gaps; do not fix them in the same pass.
