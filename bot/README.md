# Rocky Telegram bot

Send a **voice note** (or text). The bot transcribes it with Whisper, answers
with the trained **RockyLM**, and replies with **both text and Rocky's voice**.

```
you 🎤 "Hey Rocky, what is astrophage?"
rocky (text)  astrophage eat star heat. star get cold. star sick.
rocky 🔊       "Science time"          ← Rocky's recorded voice
```

## Run

```bash
pip install -r bot/requirements.txt           # + ffmpeg on your PATH
export TELEGRAM_BOT_TOKEN=...                  # from @BotFather

# one-time: train a model so checkpoints/best_model.pt exists
python -m rockylm prepare && python -m rockylm train

python bot/rocky_bot.py
```

## How it works

| step | tool |
|---|---|
| voice note → text | `faster-whisper` (local, CPU int8) |
| text → Rocky reply | trained RockyLM (`rockylm.inference`) |
| reply → voice note | `rockylm.tts` → OGG/Opus via `ffmpeg` |

**Voice backends** (`ROCKY_TTS`):
- `peon` (default) — plays Rocky's *recorded* voice; the bot picks the pack clip
  that best matches the reply. Zero heavy deps, instant.
- `xtts` — synthesizes the *exact* reply text in Rocky's cloned voice
  (`pip install TTS`, ~1.8 GB model on first run).

> Note on `peon`: the text is RockyLM's exact answer; the voice clip is the
> closest-matching recorded Rocky line, so they're thematically aligned but not
> word-for-word identical. Use `xtts` for word-for-word voice.

Config via env — see `.env.example`.
