#!/bin/bash
# Build "Joy OSC.app" and zip it into releases/.
# Builds for this Mac's chip (Apple Silicon or Intel). Needs internet the first time.
set -euo pipefail
cd "$(dirname "$0")"

if ! command -v uv >/dev/null; then
  echo "Installing uv (Python manager)..."
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# uv's Python ships a modern Tk; the macOS system Python's Tk 8.5 is too old
uv venv -q --allow-existing -p 3.12 .build-venv
uv pip install -q -p .build-venv -r requirements.txt pyinstaller

.build-venv/bin/pyinstaller --noconfirm --clean --windowed \
  --name "Joy OSC" --osx-bundle-identifier com.joyosc.app \
  --distpath build/dist --workpath build/work --specpath build \
  joy_osc_app.py

arch="$(uname -m)"
mkdir -p releases
rm -f "releases/Joy-OSC-mac-$arch.zip"
ditto -c -k --keepParent "build/dist/Joy OSC.app" "releases/Joy-OSC-mac-$arch.zip"
echo "Done: releases/Joy-OSC-mac-$arch.zip"
