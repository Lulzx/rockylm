#!/usr/bin/env bash
# Fetch the pixel-Rocky sprite frames into ~/.rockycompanion/sprites
# Sprites: Rocky pixel art by agentrocky / rocky-relay (no license stated;
# fetched at setup time, not redistributed here). Override dir with ROCKY_SPRITES.
set -e
DIR="${ROCKY_SPRITES:-$HOME/.rockycompanion/sprites}"
BASE="https://raw.githubusercontent.com/M-A-D-A-R-A/rocky-relay/main/mac-companion/RockyCompanion/Resources/Sprites"
mkdir -p "$DIR"
for s in stand walkleft1 walkleft2 jazz1 jazz2 jazz3; do
  echo "  $s.png"
  curl -fSL "$BASE/$s.png" -o "$DIR/$s.png"
done
echo "Sprites in $DIR  (RockyCompanion loads them from there; falls back to a drawn Rocky if missing)"
