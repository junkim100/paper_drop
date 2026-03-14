#!/usr/bin/env bash
set -euo pipefail

# Paper Drop — Deploy Script
# Parses markdown archives, copies assets, and pushes to GitHub Pages.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OPENCLAW_DIR="$HOME/openclaw"
MEMORY_DIR="$OPENCLAW_DIR/memory"
DATA_DIR="$OPENCLAW_DIR/data"

echo "=== Paper Drop Deploy ==="
echo ""

# 1. Parse markdown archives into JSON
echo "[1/5] Parsing markdown archives..."
if command -v uv &>/dev/null; then
    cd "$SCRIPT_DIR" && uv run python "$SCRIPT_DIR/parse_drops.py" \
        --paper_drops_md="$MEMORY_DIR/paper_drops.md" \
        --eval_drops_md="$MEMORY_DIR/eval_drops.md" \
        --output_dir="$SCRIPT_DIR/data"
else
    python "$SCRIPT_DIR/parse_drops.py" \
        --paper_drops_md="$MEMORY_DIR/paper_drops.md" \
        --eval_drops_md="$MEMORY_DIR/eval_drops.md" \
        --output_dir="$SCRIPT_DIR/data"
fi
echo ""

# 2. Copy audio files
echo "[2/5] Copying audio files..."
AUDIO_SRC="$DATA_DIR/audio"
AUDIO_DST="$SCRIPT_DIR/audio"
mkdir -p "$AUDIO_DST"
if [ -d "$AUDIO_SRC" ] && [ "$(ls -A "$AUDIO_SRC" 2>/dev/null)" ]; then
    # Read keep list to determine which files to include
    KEEP_FILE="$DATA_DIR/keep.txt"
    cp "$AUDIO_SRC"/*.mp3 "$AUDIO_DST/" 2>/dev/null || echo "  No .mp3 files found"
    echo "  Copied audio files"
else
    echo "  No audio source directory or empty: $AUDIO_SRC"
fi
echo ""

# 3. Copy transcript files
echo "[3/5] Copying transcript files..."
SCRIPTS_SRC="$DATA_DIR/transcripts"
SCRIPTS_DST="$SCRIPT_DIR/scripts"
mkdir -p "$SCRIPTS_DST"
if [ -d "$SCRIPTS_SRC" ] && [ "$(ls -A "$SCRIPTS_SRC" 2>/dev/null)" ]; then
    cp "$SCRIPTS_SRC"/*.txt "$SCRIPTS_DST/" 2>/dev/null || echo "  No .txt files found"
    echo "  Copied transcript files"
else
    echo "  No transcripts source directory or empty: $SCRIPTS_SRC"
fi
echo ""

# 4. Sync keep.txt from localStorage export
echo "[4/5] Checking keep state..."
KEEP_FILE="$DATA_DIR/keep.txt"
if [ -f "$KEEP_FILE" ]; then
    echo "  Keep file found: $KEEP_FILE ($(wc -l < "$KEEP_FILE") entries)"
else
    echo "  No keep.txt found (will be synced from browser localStorage)"
fi
echo ""

# 5. Commit and push
echo "[5/5] Committing and pushing to GitHub..."
cd "$SCRIPT_DIR"
git add -A
if git diff --cached --quiet; then
    echo "  No changes to commit"
else
    DATE_STR=$(date +"%Y-%m-%d %H:%M")
    git commit -m "Deploy: update drops ($DATE_STR)"
    git push origin main
    echo "  Deployed successfully!"
fi

echo ""
echo "=== Done ==="
echo "Site will be available at: https://junkim100.github.io/paper_drop/"
