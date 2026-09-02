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
pip install -r rvc/requirements.txt
python rvc/rocky_voice_server.py                       # POST /say text -> Rocky WAV
```

On first run the server downloads `rocky_voice.pth` (57 MB, Pedram Amini's
trained RVC v2 model, from <https://pedramamini.com/dropbox/rocky_voice.pth>)
to `~/rvc/models/`. Point `ROCKY_RVC_MODEL` somewhere else to change that, or
drop your own `.pth` there. ContentVec (`lengyue233/content-vec-best`) and
CREPE weights are fetched by `transformers` / `torchcrepe` on first use.

The Telegram bot uses it with `ROCKY_MODE=llm ROCKY_TTS=rvc ROCKY_VOICE_URL=http://127.0.0.1:8770`:
RockyLM writes the reply text, this service speaks it in Rocky's voice.

Env: `ROCKY_VOICE_PORT` (8770), `ROCKY_RVC_TRANSPOSE` (pitch shift, semitones),
`TINYTTS_SPEAKER` (MALE/FEMALE). Model weights are not committed; the RockyLM
weights are on the GitHub release and `rocky_voice.pth` is auto-downloaded.

Credit: RVC model code — RVC-Project (MIT); `rocky_voice.pth` — Pedram Amini's
Rocky RVC training; ContentVec — lengyue233/content-vec-best.
