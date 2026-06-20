# Rocky Relay

A tiny stdlib HTTP server that fronts **RockyLM** so the [Mac companion](../mac-companion)
(or any client) can do voice in / Rocky voice out. It mirrors the `/audio`
contract of [rocky-relay](https://github.com/M-A-D-A-R-A/rocky-relay).

## API

| route | in | out |
|---|---|---|
| `POST /audio` | `audio/wav` body (your voice) | `audio/wav` (Rocky's voice) + headers `X-Transcript`, `X-Reply` (percent-encoded) |
| `POST /text` | `text/plain` body | same, skipping transcription |
| `GET /health` | — | `{"status":"ok","model":"rockylm","tts":"peon"}` |

Pipeline: **Whisper** (faster-whisper) → **RockyLM** → **Rocky voice**
(`rockylm.tts`: recorded `peon` clips, or `xtts` neural clone).

## Run

```bash
pip install faster-whisper torch tokenizers     # + ffmpeg
python -m rockylm prepare && python -m rockylm train
python relay/server.py                          # http://127.0.0.1:8765
```

Env: `ROCKY_PORT` (8765), `ROCKY_TTS` (peon|xtts), `WHISPER_MODEL` (base),
`ROCKY_CHECKPOINT`, `ROCKY_TOKENIZER`.

## Quick test

```bash
curl -s -D - -X POST --data "what is astrophage" localhost:8765/text -o reply.wav | grep X-Reply
# X-Reply: this%20not%20just%20astrophage.%20this%20life...  + reply.wav is Rocky's voice
```
