#!/usr/bin/env bash
# Download model.onnx and tokenizer.json from the GitHub release into this directory.
# (Both are also committed, so this is only needed to refresh them.)

set -e

BASE="https://github.com/Lulzx/rockylm/releases/latest/download"
DIR="$(cd "$(dirname "$0")" && pwd)"

echo "Downloading from ${BASE}..."

curl -fSL "${BASE}/rockylm-9M.onnx" -o "${DIR}/model.onnx"
echo "  model.onnx     $(du -h "${DIR}/model.onnx" | cut -f1)"

curl -fSL "${BASE}/tokenizer.json" -o "${DIR}/tokenizer.json"
echo "  tokenizer.json $(du -h "${DIR}/tokenizer.json" | cut -f1)"

echo "Done. Run: cd docs && python -m http.server 8080"
