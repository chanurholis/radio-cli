#!/usr/bin/env bash
# radio-cli installer (macOS / Linux). Usage:  curl -fsSL <RAW_URL>/install.sh | bash   or   ./install.sh
set -euo pipefail
RAW="${RADIO_RAW:-https://raw.githubusercontent.com/chanurholis/radio-cli/main}" # set USER once the repo exists
DIR="${RADIO_HOME:-$HOME/.local/share/radio-cli}"
BIN="${RADIO_BIN:-$HOME/.local/bin}"

command -v python3 >/dev/null || {
  echo "python3 (>=3.8) is required"
  exit 1
}

# player: mpv or ffplay
if ! command -v mpv >/dev/null && ! command -v ffplay >/dev/null; then
  echo "installing mpv..."
  if command -v brew >/dev/null; then
    brew install mpv
  elif command -v apt-get >/dev/null; then
    sudo apt-get install -y mpv
  elif command -v dnf >/dev/null; then
    sudo dnf install -y mpv
  elif command -v pacman >/dev/null; then
    sudo pacman -S --noconfirm mpv
  else
    echo "install mpv or ffmpeg manually, then run this again"
    exit 1
  fi
fi

mkdir -p "$DIR" "$BIN"
for f in radio.py tui.py; do
  if [ -f "$(dirname "${BASH_SOURCE[0]:-x}")/$f" ]; then
    cp "$(dirname "${BASH_SOURCE[0]}")/$f" "$DIR/$f"
  else curl -fsSL "$RAW/$f" -o "$DIR/$f"; fi
done
printf '#!/bin/sh\nexec python3 "%s/radio.py" "$@"\n' "$DIR" >"$BIN/radio"
chmod +x "$BIN/radio"

echo "installed: $BIN/radio"
case ":$PATH:" in *":$BIN:"*) ;; *)
  echo "add it to PATH (once):"
  echo "  echo 'export PATH=\"$BIN:\$PATH\"' >> ~/.$(basename "$SHELL")rc   # bash/zsh"
  echo "  fish_add_path $BIN                                            # fish"
  ;;
esac
echo "try:  radio"
