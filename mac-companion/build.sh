#!/usr/bin/env bash
# Build RockyCompanion. Tries SwiftPM first; falls back to swiftc directly
# (useful if `swift build` is broken on your machine).
set -e
cd "$(dirname "$0")"
if swift build -c release 2>/dev/null; then
  echo "Built via SwiftPM: $(swift build -c release --show-bin-path)/RockyCompanion"
  exit 0
fi
echo "SwiftPM unavailable — building with swiftc..."
SDK="$(xcrun --show-sdk-path)"
mkdir -p .build
xcrun swiftc -O -sdk "$SDK" -framework AppKit -framework AVFoundation \
  Sources/RockyCompanion/*.swift -o .build/RockyCompanion
echo "Built: $(pwd)/.build/RockyCompanion"
echo "Run:   ROCKY_RELAY=http://127.0.0.1:8765 ./.build/RockyCompanion"
