# dotfiles

- Terminal centric.
- Interchangeable harnesses. Do not vendor-lock.

`setup.sh` installs everything on a fresh Ubuntu and symlinks this repo into place.

- `dot/` - shell, git and tmux dotfiles, symlinked into `~`
- `config/` - global `AGENTS.md`, settings, hooks and plugins for Claude Code, Codex and pi
- `skills/` - agent skills, shared through `~/.claude/skills` and `~/.agents/skills`
- `services/` - systemd user services and their code
- `templates/` - starter `AGENTS.md` for new projects
- `windows/` - scripts for the Windows side of the dual boot

The repo is public. Secrets live in `.env` and `secrets/`, both gitignored. Services load `.env` with `EnvironmentFile=`.
