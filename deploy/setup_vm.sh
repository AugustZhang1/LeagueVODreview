#!/usr/bin/env bash
# Set up the crawler on a fresh Debian 12 VM. Safe to run twice.
set -euo pipefail

# For a private repo, create a deploy key on the VM (ssh-keygen -t ed25519), add the public key
# under the repo's Settings -> Deploy keys, and use the SSH URL here.
REPO_URL="https://github.com/USER/LeagueVODreview.git"
REPO_DIR="$HOME/LeagueVODreview"
SERVICE_USER="$(id -un)"

echo "== 1/4 swap file"
if ! swapon --show=NAME --noheadings | grep -q '^/swapfile$' && [ ! -f /swapfile ]; then
    sudo fallocate -l 2G /swapfile
    sudo chmod 600 /swapfile
    sudo mkswap /swapfile
fi
if ! swapon --show=NAME --noheadings | grep -q '^/swapfile$'; then
    sudo swapon /swapfile
fi
if ! grep -q '^/swapfile ' /etc/fstab; then
    echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

echo "== 2/4 python, code, venv"
sudo apt-get update -y
sudo apt-get install -y python3 python3-venv git curl ca-certificates
if [ -d "$REPO_DIR/.git" ]; then
    git -C "$REPO_DIR" pull --ff-only
else
    git clone "$REPO_URL" "$REPO_DIR"
fi
cd "$REPO_DIR"
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 12) else 1)'; then
    [ -d .venv ] || python3 -m venv .venv
    .venv/bin/pip install -e ".[vm]"
else
    # Debian 12 ships Python 3.11; uv fetches 3.12.
    export PATH="$HOME/.local/bin:$PATH"
    command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
    [ -d .venv ] || uv venv -p 3.12 .venv
    uv pip install -p .venv -e ".[vm]"
fi

echo "== 3/4 .env"
# `gcloud compute scp .env` lands in ~ before the repo exists; move it into place.
if [ ! -f "$REPO_DIR/.env" ] && [ -f "$HOME/.env" ]; then
    mv "$HOME/.env" "$REPO_DIR/.env"
fi
if [ ! -f "$REPO_DIR/.env" ]; then
    echo "Missing $REPO_DIR/.env. From your laptop run:"
    echo "  gcloud compute scp .env lol-crawler:~/.env --zone us-central1-a"
    echo "then run this script again."
    exit 1
fi
chmod 600 "$REPO_DIR/.env"

echo "== 4/4 systemd service"
sed -e "s|@USER@|$SERVICE_USER|g" -e "s|@REPO@|$REPO_DIR|g" \
    "$REPO_DIR/deploy/lolcrawler.service" | sudo tee /etc/systemd/system/lolcrawler.service >/dev/null
sudo systemctl daemon-reload
sudo systemctl enable lolcrawler
sudo systemctl restart lolcrawler
echo "Done. Check: systemctl status lolcrawler"
