#!/usr/bin/env bash
# One-time setup for the zero-cost animation studio (Ubuntu/Debian; see README for macOS/Windows).
set -euo pipefail
cd "$(dirname "$0")"

SUDO=""
[ "$(id -u)" -ne 0 ] && SUDO="sudo"

echo "==> System packages (ffmpeg, cairo/pango for Manim, Inter font)"
$SUDO apt-get update -qq
$SUDO apt-get install -y -qq ffmpeg libcairo2-dev libpango1.0-dev pkg-config python3-venv fonts-inter

echo "==> Python environment in .venv"
python3 -m venv .venv
.venv/bin/pip install -q --upgrade pip setuptools wheel
.venv/bin/pip install -q -r requirements.txt

VOICE="${STUDIO_VOICE:-en_US-lessac-medium}"
echo "==> Piper voice: $VOICE"
mkdir -p assets/voices
lang="${VOICE%%-*}"          # en_US
family="${lang%%_*}"         # en
name_quality="${VOICE#*-}"   # lessac-medium
name="${name_quality%-*}"    # lessac
quality="${name_quality##*-}" # medium
base="https://huggingface.co/rhasspy/piper-voices/resolve/main/$family/$lang/$name/$quality"
for f in "$VOICE.onnx" "$VOICE.onnx.json"; do
  [ -f "assets/voices/$f" ] || curl -fsSL -o "assets/voices/$f" "$base/$f"
done

echo
echo "Ready. Render the heart video with:"
echo "  .venv/bin/python build.py heart            # 1080p final"
echo "  .venv/bin/python build.py heart --quality draft   # fast 480p preview"
