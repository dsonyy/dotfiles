# Lessons index

Match the task to tags, open only the records that match. Never read `records/` wholesale.
Record shape: front matter `title` + `tags`, H1 equal to the title, then `**Context**:`,
optional `**Problem**:`, `**Rule**:`, `**Applies to**:`.
Run `python3 ~/lessons/check.py` after editing anything here.

## Tags

One to four per record, from this list only. `check.py` reads the block below, so the fence
and one-tag-per-line shape are load-bearing. A near-synonym of an existing tag makes older
lessons unfindable, so adding one is a deliberate edit.

```
linux
shell
tmux
git
ssh
network
filesystem
packaging
docker
node
typescript
python
postgres
testing
debugging
deploy
security
performance
concurrency
data-loss
agents
```

## Catalog

- [Mount NTFS with ntfs-3g, not the ntfs3 kernel driver](records/mount-ntfs-with-ntfs-3g-not-the-ntfs3-kernel-driver.md) | linux, filesystem, debugging
- [Surface conflicting instructions instead of arbitrating them](records/surface-conflicting-instructions-instead-of-arbitrating-them.md) | agents, git
- [Check converted documents for markup artifacts before deleting sources](records/check-converted-documents-for-markup-artifacts-before-deleting-sources.md) | agents, testing, data-loss
