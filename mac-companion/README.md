# Rocky Companion (macOS)

A floating pixel **Rocky** that lives on your Dock line, listens to your
microphone, asks **RockyLM** (via the local relay), and answers in **Rocky's
voice** — with speech bubbles for what you said and what he replied.

```
[ you click Rocky / press Space ] → 🎤 record
        → POST /audio → relay (Whisper → RockyLM → Rocky voice)
        → 💬 bubbles (transcript + reply)  +  🔊 plays Rocky's voice
```

## Run

**1. Start the relay** (serves RockyLM over HTTP — see [`../relay`](../relay)):

```bash
python -m rockylm prepare && python -m rockylm train   # one-time: make a model
python relay/server.py                                 # http://127.0.0.1:8765
```

**2. Get the sprite frames** (downloaded at setup, not bundled):

```bash
./fetch-sprites.sh        # -> ~/.rockycompanion/sprites
```

**3. Build & run the companion:**

```bash
./build.sh                # SwiftPM, or swiftc fallback if SwiftPM is broken
./.build/RockyCompanion
```

Or with Xcode: `open RockyCompanion.xcodeproj` then `Cmd+R`.
Point at a non-default relay with `ROCKY_RELAY=http://host:port`.

## Controls

- **Click Rocky**, or press **Space / Tab / Enter** → start/stop recording.
- Rocky walks the Dock line while idle; stops while listening/thinking.
- A red dot under Rocky means he's listening.

## Notes

- macOS will ask for **microphone** permission on first record. If global keys
  don't toggle, click Rocky once to focus him (he runs as an accessory overlay
  with no Dock icon). For full mic + key entitlements, run from the Xcode
  project (it carries the Info.plist + entitlements).
- If sprites are missing, the companion draws a simple fallback Rocky, so it
  still runs without `fetch-sprites.sh`.

## Files

```
Sources/RockyCompanion/
  main.swift           floating always-on-top transparent window
  CompanionView.swift  sprite animation, Dock-line walk, bubbles, record toggle
  Audio.swift          mic → WAV recorder + WAV player
  RelayClient.swift    POST /audio, reads X-Transcript / X-Reply, plays reply
fetch-sprites.sh       download pixel-Rocky frames
build.sh               SwiftPM build, with swiftc fallback
```

## Credits

Concept and pixel-Rocky sprites adapted from
[M-A-D-A-R-A/rocky-relay](https://github.com/M-A-D-A-R-A/rocky-relay) (whose
`/audio` API this relay mirrors) and, upstream of it,
[itmesneha/agentrocky](https://github.com/itmesneha/agentrocky). Sprites are
fetched at setup, not redistributed here. Rocky is Andy Weir's character;
non-commercial fan project.
