#!/usr/bin/env bash

step() { printf '\033[35m%s\033[0m\n' "$1"; }

############## INSTALLATION

# google chrome

step "core"
sudo apt install -y curl wget git htop

step "ssh"
if ! dpkg -l | grep openssh-server &> /dev/null; then
	sudo apt install -y openssh-server
	sudo systemctl enable --now ssh
fi

step "zsh"
sudo apt install -y zsh
chsh -s $(which zsh)

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

step "tmux"
sudo apt install tmux

step "tmux plugin manager"
if ! [ -d "$HOME/.tmux/plugins/tpm" ]; then
    git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
fi

step "tmux plugins"
$HOME/.tmux/plugins/tpm/bin/install_plugins

step "tmux main session"
if [ ! -e "$HOME/.local/share/tmux/resurrect/last" ] && [ ! -e "$HOME/.tmux/resurrect/last" ]; then
    tmux new-session -d -s main
    tmux run-shell "$HOME/.tmux/plugins/tmux-resurrect/scripts/save.sh"
    tmux kill-session -t main
fi

step "micro"
sudo apt install -y micro

step "vscode"
if ! dpkg -l | grep -q "^ii  code " &> /dev/null; then
    sudo curl -fsSLo /usr/share/keyrings/microsoft.asc https://packages.microsoft.com/keys/microsoft.asc
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/microsoft.asc] https://packages.microsoft.com/repos/code stable main" | sudo tee /etc/apt/sources.list.d/vscode.list
    sudo apt update && sudo apt install -y code
fi

step "keepassxc"
if ! dpkg -l | grep keepassxc &> /dev/null; then
    sudo apt -y install keepassxc
fi

step "obsidian"
if ! snap list | grep obsidian &> /dev/null; then
    snap install obsidian --classic
fi

step "tailscale"
if ! dpkg -l | grep tailscale &> /dev/null; then
	curl -fsSL https://tailscale.com/install.sh | sh
	sudo tailscale up
fi

step "ollama"
if ! command -v ollama &> /dev/null; then
    curl -fsSL https://ollama.com/install.sh | sh
fi

step "spotify"
if ! snap list | grep spotify &> /dev/null; then
    snap install spotify
fi

step "slack"
if ! snap list | grep slack &> /dev/null; then
    sudo snap install slack
fi

step "claude desktop"
if ! dpkg -l | grep -q claude-desktop &> /dev/null; then
    sudo curl -fsSLo /usr/share/keyrings/claude-desktop-archive-keyring.asc https://downloads.claude.ai/claude-desktop/key.asc
    echo "deb [arch=amd64 signed-by=/usr/share/keyrings/claude-desktop-archive-keyring.asc] https://downloads.claude.ai/claude-desktop/apt/stable stable main" | sudo tee /etc/apt/sources.list.d/claude-desktop.list
    sudo apt update && sudo apt install claude-desktop
fi

step "claude code"
curl -fsSL https://claude.ai/install.sh | bash

step "codex"
curl -fsSL https://chatgpt.com/codex/install.sh | bash

step "opencode"
curl -fsSL https://opencode.ai/install | bash

step "handy"
if ! command -v handy &> /dev/null; then
    URL=$(curl -s https://api.github.com/repos/cjpais/Handy/releases/latest | grep -o https://[^\"]*amd64\\.deb | head -1)
    curl -fsSL $URL -o /tmp/handy.deb
    sudo apt install -y /tmp/handy.deb && rm /tmp/handy.deb
fi

step "github cli"
(type -p wget >/dev/null || (sudo apt update && sudo apt install wget -y)) \
	&& sudo mkdir -p -m 755 /etc/apt/keyrings \
	&& out=$(mktemp) && wget -nv -O$out https://cli.github.com/packages/githubcli-archive-keyring.gpg \
	&& cat $out | sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg > /dev/null \
	&& sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg \
	&& sudo mkdir -p -m 755 /etc/apt/sources.list.d \
	&& echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
	&& sudo apt update \
	&& sudo apt install gh -y

step "nvm / node / npm"
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.7/install.sh | bash
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
nvm install 24


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
    ln -sf "$f" "$HOME/$(basename "$f")"
done

step "claude code - symlinks"
mkdir -p $HOME/.claude
ln -sf $DOTFILES/config/AGENTS.md $HOME/.claude/CLAUDE.md
ln -sfn $DOTFILES/skills $HOME/.claude/skills
ln -sfnT $DOTFILES/config/.claude/agents $HOME/.claude/agents
ln -sfnT $DOTFILES/config/.claude/settings.json $HOME/.claude/settings.json

step "claude code - plugins"
claude plugin marketplace add "$DOTFILES/config"
for p in "$DOTFILES"/config/plugins/*; do
    [ -d "$p" ] || continue
    claude plugin install "$(basename "$p")@dsonyy"
done

step "codex - symlinks"
mkdir -p "$HOME/.codex"
ln -sfnT "$DOTFILES/config/AGENTS.md" "$HOME/.codex/AGENTS.md"
mkdir -p "$HOME/.agents"
ln -sfnT "$DOTFILES/skills" "$HOME/.agents/skills"
ln -sfnT "$DOTFILES/config/.codex/config.toml" "$HOME/.codex/config.toml"

step "codex - plugins"
codex plugin marketplace add "$DOTFILES/config"
for p in "$DOTFILES"/config/plugins/*/.codex-plugin; do
    [ -d "$p" ] || continue
    codex plugin add "$(basename "$(dirname "$p")")@dsonyy"
done


step "lessons - symlink"
ln -sfnT "$DOTFILES/lessons" "$HOME/lessons"

step "verify agent symlinks"
broken=0
for link in "$HOME/.claude/CLAUDE.md" "$HOME/.claude/skills" "$HOME/.claude/agents" "$HOME/.claude/settings.json" "$HOME/.codex/AGENTS.md" "$HOME/.codex/config.toml" "$HOME/.agents/skills" "$HOME/lessons"; do
    if [ ! -e "$link" ]; then
        printf '\033[31mBROKEN: %s -> %s\033[0m\n' "$link" "$(readlink "$link")"
        broken=1
    fi
done
for p in "$DOTFILES"/config/plugins/*/.codex-plugin; do
    [ -d "$p" ] || continue
    name=$(basename "$(dirname "$p")")
    if ! codex plugin list 2>/dev/null | grep -q "$name@dsonyy *installed"; then
        printf '\033[31mNOT INSTALLED: %s@dsonyy (codex)\033[0m\n' "$name"
        broken=1
    fi
done
[ "$broken" -eq 0 ] && echo "all agent symlinks resolve"

step "DONE"
