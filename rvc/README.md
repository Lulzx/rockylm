# Rocky voice (TinyTTS → RVC)

Gives the bot Rocky's *actual* trained voice on **arbitrary** text, fairseq-free
(works on ARM / new Python where `rvc-python` can't install).

```
text --TinyTTS (1.6M, generic)--> speech --RVC(rocky_voice.pth)--> Rocky voice
```

- **ContentVec** content encoder via `transformers` (`lengyue233/content-vec-best`) — no fairseq
- **`rocky_voice.pth`** loaded into vendored RVC `SynthesizerTrnMs768NSFsid` (MIT model code)
- **pitch** via `torchcrepe` (pure torch), all CPU

## Run as a service

```bash
python -m venv .venv && . .venv/bin/activate
pip install torch torchaudio transformers torchcrepe librosa soundfile scipy tiny-tts
export ROCKY_RVC_MODEL=~/rvc/models/rocky_voice.pth   # the trained model (57 MB)
python rvc/rocky_voice_server.py                       # POST /say text -> Rocky WAV
```

The Telegram bot uses it with `ROCKY_MODE=llm ROCKY_TTS=rvc ROCKY_VOICE_URL=http://127.0.0.1:8770`:
RockyLM writes the reply text, this service speaks it in Rocky's voice.

Env: `ROCKY_VOICE_PORT` (8770), `ROCKY_RVC_TRANSPOSE` (pitch shift, semitones),
`TINYTTS_SPEAKER` (MALE/FEMALE). Model weights are not committed.

Credit: RVC model code — RVC-Project (MIT); `rocky_voice.pth` — Pedram Amini's
Rocky RVC training; ContentVec — lengyue233/content-vec-best.
