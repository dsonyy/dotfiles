#!/usr/bin/env bash

step() { printf '\033[35m%s\033[0m\n' "$1"; }

# BSD ln has no -T, so a real dir at the destination would get the link put inside it. Move it aside first.
link() {
    if [ -e "$2" ] && [ ! -L "$2" ]; then
        mv "$2" "$2.bak.$(date +%Y%m%d%H%M%S)"
    fi
    ln -sfn "$1" "$2"
}

############## INSTALLATION

step "homebrew"
if ! command -v brew &> /dev/null && [ ! -x /opt/homebrew/bin/brew ]; then
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi
eval "$(/opt/homebrew/bin/brew shellenv)"

step "core"
brew install git micro tmux
brew install --cask font-meslo-lg-nerd-font

step "oh-my-zsh"
if ! [ -d "$HOME/.oh-my-zsh" ]; then
    sh -c "$(curl -fsSL https://raw.githubusercontent.com/ohmyzsh/ohmyzsh/master/tools/install.sh)" "" --unattended
fi

step "oh-my-zsh plugins"
if ! [ -d "$HOME/.oh-my-zsh/custom/plugins/zsh-autosuggestions" ]; then
    git clone https://github.com/zsh-users/zsh-autosuggestions ~/.oh-my-zsh/custom/plugins/zsh-autosuggestions
fi
if ! [ -d "$HOME/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting" ]; then
    git clone https://github.com/zsh-users/zsh-syntax-highlighting ~/.oh-my-zsh/custom/plugins/zsh-syntax-highlighting
fi

step "tmux plugin manager"
if ! [ -d "$HOME/.tmux/plugins/tpm" ]; then
    git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
fi

step "ssh key"
if [ ! -f "$HOME/.ssh/id_ed25519" ]; then
    ssh-keygen -t ed25519 -f "$HOME/.ssh/id_ed25519"
    echo "add this key to github before continuing:"
    cat "$HOME/.ssh/id_ed25519.pub"
    read -r -p "press enter when done "
fi

step "claude code"
if [ ! -x "$HOME/.local/bin/claude" ]; then
    curl -fsSL https://claude.ai/install.sh | bash
fi
export PATH=$HOME/.local/bin:$PATH


############## SETUP

export DOTFILES=$HOME/repos/dotfiles

step "clone dotfiles"
if [ ! -d $DOTFILES ]; then
    mkdir -p ~/repos
    cd ~/repos
    git clone git@github.com:dsonyy/dotfiles.git
fi

step "dot symlinks"
for f in "$DOTFILES"/dot/.[!.]* "$DOTFILES"/dot/*; do
    [ -e "$f" ] || continue
    link "$f" "$HOME/$(basename "$f")"
done

step "tmux plugins"
$HOME/.tmux/plugins/tpm/bin/install_plugins

step "tmux main session"
if [ ! -e "$HOME/.local/share/tmux/resurrect/last" ] && [ ! -e "$HOME/.tmux/resurrect/last" ]; then
    tmux new-session -d -s main
    tmux run-shell "$HOME/.tmux/plugins/tmux-resurrect/scripts/save.sh"
    tmux kill-session -t main
fi

step "claude code - symlinks"
mkdir -p $HOME/.claude
link $DOTFILES/config/AGENTS.md $HOME/.claude/CLAUDE.md
link $DOTFILES/skills $HOME/.claude/skills
link $DOTFILES/config/.claude/agents $HOME/.claude/agents
link $DOTFILES/config/.claude/settings.json $HOME/.claude/settings.json

step "claude code - plugins"
(cd "$(mktemp -d)" && claude plugin marketplace add --scope local "$DOTFILES/config")
for p in "$DOTFILES"/config/plugins/*; do
    [ -d "$p" ] || continue
    claude plugin install "$(basename "$p")@dsonyy"
done

# config.toml stays local: the ChatGPT app writes machine paths into it.
step "codex"
CODEX=/Applications/ChatGPT.app/Contents/Resources/codex-cli/CodexCLI.app/Contents/MacOS/codex
mkdir -p "$HOME/.codex" "$HOME/.agents"
link "$DOTFILES/config/AGENTS.md" "$HOME/.codex/AGENTS.md"
link "$DOTFILES/skills" "$HOME/.agents/skills"
if [ -x "$CODEX" ]; then
    "$CODEX" plugin marketplace add "$DOTFILES/config"
    for p in "$DOTFILES"/config/plugins/*/.codex-plugin; do
        [ -d "$p" ] || continue
        "$CODEX" plugin add "$(basename "$(dirname "$p")")@dsonyy"
    done
fi

step "lessons - symlink"
link "$HOME/brain/lessons" "$HOME/lessons"

step "verify claude setup"
broken=0
for link in "$HOME/.claude/CLAUDE.md" "$HOME/.claude/skills" "$HOME/.claude/agents" "$HOME/.claude/settings.json" "$HOME/.codex/AGENTS.md" "$HOME/.agents/skills" "$HOME/lessons"; do
    if [ ! -e "$link" ]; then
        printf '\033[31mBROKEN: %s -> %s\033[0m\n' "$link" "$(readlink "$link")"
        broken=1
    fi
done
for p in "$DOTFILES"/config/plugins/*; do
    [ -d "$p" ] || continue
    name=$(basename "$p")
    if ! claude plugin list 2>/dev/null | grep -q "$name@dsonyy"; then
        printf '\033[31mNOT INSTALLED: %s@dsonyy (claude)\033[0m\n' "$name"
        broken=1
    fi
done
[ "$broken" -eq 0 ] && echo "claude setup ok"

step "DONE"
