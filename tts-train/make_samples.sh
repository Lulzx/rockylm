#!/usr/bin/env bash
# Export the latest Piper Rocky checkpoint to ONNX and synthesize sample phrases.
# Run from the piper1-gpl venv:  bash tts-train/make_samples.sh
set -e
R="$(cd "$(dirname "$0")" && pwd)"

# newest checkpoint from training
CKPT="$(ls -t "$R"/runs/lightning_logs/version_*/checkpoints/*.ckpt 2>/dev/null | head -1)"
[ -z "$CKPT" ] && { echo "no checkpoint found in $R/runs"; exit 1; }
echo "checkpoint: $CKPT"

echo "exporting -> rocky.onnx ..."
python3 -m piper.train.export_onnx --checkpoint "$CKPT" --output-file "$R/rocky.onnx"

mkdir -p "$R/samples"
i=0
while IFS= read -r line; do
  [ -z "$line" ] && continue
  i=$((i+1))
  out="$R/samples/$(printf '%02d' $i).wav"
  echo "  [$i] $line"
  echo "$line" | python3 -m piper -m "$R/rocky.onnx" -c "$R/rocky.json" -f "$out" 2>/dev/null
done <<'PHRASES'
rocky here. ready work.
good good good.
what is astrophage. question?
bad bad bad. rocky sorry.
amaze amaze amaze.
we go home. question?
rocky make long chain. we go fishing.
PHRASES

echo "samples in $R/samples/"
ls -la "$R/samples/"
