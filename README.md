<h1 align="center">RockyLM</h1>
<p align="center"><em>A ~9M parameter LLM that talks like Rocky from Project Hail Mary — and speaks in his voice.</em></p>

---

> Rocky is the Eridian alien from *Project Hail Mary*. He communicates in musical
> chords; everything you read is a translation, and the translation has a very
> specific broken grammar: he tags questions with the literal word **"question?"**,
> repeats words three times for emotion (**"good good good"**), refers to himself
> as **"rocky"** and to you as **"grace"**, drops articles, and reasons about
> science in blunt cause→effect clauses.
>
> RockyLM is a from-scratch transformer that learns that voice, plus a TTS layer
> that speaks replies in Rocky's actual cloned/recorded voice.

This is a fork of **[GuppyLM](https://github.com/arman-bd/guppylm)** by Arman
Hossain — same tiny-LM recipe (synthetic data → BPE tokenizer → 9M vanilla
transformer → 5-minute train), with the fish character replaced by Rocky and a
voice layer added.

```
You> hi rocky
Rocky> hello grace friend. rocky happy you here. good good good.

You> what is astrophage
Rocky> astrophage eat star heat. star get cold. star sick.

You> let's make peace
Rocky> what mean make peace. question. rocky understand science. rocky not understand this.

You> we did it
Rocky> we party. question. yes. we party. rocky happy happy happy. we did it.

You> you don't have to do this
Rocky> grace say grace will die. rocky fix. grace go home. no argue. rocky decide.

You> goodbye rocky
Rocky> no understand word. goodbye. what mean. question. rocky wait for you.
```

---

## How Rocky talks

The whole point of this project. Full spec in **[STYLE.md](STYLE.md)**; the short
version:

| signature | example |
|---|---|
| **`question?` tag** on anything he asks | "grace, it's safe. question?" |
| **triple repetition** for emotion | "good good good", "bad bad bad", "amaze amaze amaze" |
| **third person** — himself and you | "rocky fix. grace go home." |
| **no articles, no auxiliaries** | "in mid of ship", "star not die", "could not fix" |
| **clipped words** | "amaze", "apology", "confuse" |
| **blunt cause→effect science** | "life is reason, star not die." |
| **literal compound names** | laptop → "portable earth thinking machine" |
| **precise numbers** | "186.3 years", "two million kilograms" |

He is **not dumb** — he is a brilliant blind engineer who perceives by sound,
lives in hot high-pressure ammonia air, builds with Xenonite, and is fiercely
loyal. Only his *grammar* is simple.

The personality lives entirely in **[`rockylm/generate_data.py`](rockylm/generate_data.py)** —
46 topic generators (greeting, science, build, the blindness/sound sense, mate,
crew, sacrifice, idioms he can't parse, danger, fishing, naming, …) authored to
obey the spec above.

---

## Try it in your browser

**[Lulzx.github.io/rockylm](https://Lulzx.github.io/rockylm)** — the trained 9M
model runs entirely client-side via ONNX + WebAssembly. No server, no API key.
The quantized model is **8.8 MB**.

## Quick start

```bash
pip install torch tokenizers          # model
# voice (peon backend) needs nothing extra; afplay/ffplay/aplay is used to play

# 1. generate data + tokenizer, then train (~5 min on Apple Silicon / a T4)
python -m rockylm prepare
python -m rockylm train

# 2. chat — add --speak to hear Rocky's voice
python -m rockylm chat
python -m rockylm chat --speak
python -m rockylm chat --speak --tts-backend xtts
```

Single-shot (real output from the trained model):

```text
$ python -m rockylm chat --prompt "what kills the astrophage"
predator eat astrophage. astrophage population stable. star not die.

$ python -m rockylm chat --prompt "goodbye rocky"
no understand word. goodbye. what mean. question. goodbye grace friend.
```

Export the trained model for the browser:

```bash
python tools/export_onnx.py     # -> docs/model.onnx (uint8) + docs/tokenizer.json
```

## Talk to Rocky on Telegram

A bot in [`bot/`](bot/) takes **voice notes**, transcribes them with Whisper,
runs them through RockyLM, and replies with **both text and Rocky's voice**:

```bash
pip install -r bot/requirements.txt
export TELEGRAM_BOT_TOKEN=...        # from @BotFather
python bot/rocky_bot.py
```

See [`bot/README.md`](bot/README.md).

## A floating Rocky on your Mac

[`mac-companion/`](mac-companion/) is a pixel **Rocky** that walks your Dock
line. Click him (or press Space), talk, and he answers in Rocky's voice with
speech bubbles. He talks to RockyLM through the local [`relay/`](relay/) server
(`/audio` voice in → Rocky voice out), so the same backend powers the bot, the
companion, and any other client.

```bash
python relay/server.py                    # serve RockyLM at :8765
cd mac-companion && ./fetch-sprites.sh && ./build.sh && ./.build/RockyCompanion
```

---

## Giving Rocky a voice (TTS)

`rockylm/tts.py` turns a reply into Rocky's voice. Two backends:

### `peon` — recorded voice (default, zero extra deps)

Plays Rocky's **actual recorded voice** from the OpenPeon "Rocky" pack — 58 clips
across 7 coding-event categories (the [CESP](https://openpeon.com) standard,
synthesized via Chatterbox voice cloning). RockyLM's reply is matched to the
closest clip (by intent words + emphasis), then played with your system audio
player. No model, no torch, no GPU.

```bash
python -m rockylm say "good good good. rocky solve problem."   # -> plays "Code good, Rocky solve"
python -m rockylm say --event task.error                       # -> plays "Bad, Rocky sorry"
python -m rockylm say --list                                   # browse all 58 clips
```

The pack downloads once to `~/.rockylm/rocky_pack/`.
Pack: <https://openpeon.com/packs/rocky> · clips: [Akshat1903/rocky-peon-ping](https://github.com/Akshat1903/rocky-peon-ping).

### `xtts` — neural voice clone (speaks any text)

Synthesizes **arbitrary** text in Rocky's cloned voice with Coqui XTTS v2, using
the pack's reference audio as the speaker. Heavier — `pip install TTS` — but it
can say lines that aren't in the soundboard.

```bash
pip install TTS
python -m rockylm say --backend xtts "rocky make long chain. we go fishing."
python -m rockylm say --backend xtts --transform "That is amazing, thank you!"
```

`--transform` runs a rule-based English→Rocky-speak pass first (drop articles,
triple emphasis, `question?` tag), so even non-RockyLM text comes out in
character. Adapted from Pedram Amini's
[`rocky_say`](https://gist.github.com/pedramamini/fa5f6ef99dae79add220188419230642).

---

## Architecture

Unchanged from GuppyLM — a vanilla transformer. Character/voice is data, not
architecture.

| | |
|---|---|
| **Parameters** | ~8.7M |
| **Layers / dim / heads** | 6 / 384 / 6 |
| **FFN** | 768 (ReLU) |
| **Vocab** | 4,096 (BPE) |
| **Max sequence** | 128 tokens |
| **Norm / Position** | LayerNorm / learned |

---

## Project structure

```
rockylm/
├── generate_data.py   ← Rocky's voice: 46 topic generators (THE personality)
├── tts.py             ← speak replies: peon (recorded) + xtts (neural clone)
├── eval_cases.py      ← held-out Rocky test cases
├── inference.py       ← chat (+ --speak)
├── config.py model.py dataset.py train.py prepare_data.py   ← unchanged recipe
bot/                   ← Telegram bot: voice note → RockyLM → text + voice
relay/                 ← HTTP server (/audio, /health) fronting RockyLM
mac-companion/         ← floating pixel-Rocky macOS app (mic → relay → voice)
docs/                  ← browser demo (ONNX + WASM), served on GitHub Pages
STYLE.md               ← deep analysis of how Rocky talks (the spec)
```

---

## Design notes

- **Why these 46 topics?** They cover Rocky's range in the film: the science
  (astrophage, predator/taumoeba, fuel, orbits), the engineering (chains,
  Xenonite, fishing-plan), the senses (blind, hears through walls), the
  relationships (Grace, his dead crew, his mate Adrian), and the human things he
  can't parse (idioms, hugs, goodbye, jokes).
- **Lower output diversity than GuppyLM, on purpose.** Rocky's voice is more
  formulaic than Guppy's free-associating fish-talk, so templates lean
  hand-authored. A 9M model locks a consistent style faster from consistent data.
- **Voice ≠ model.** TTS is a separate layer; the soundboard works even without
  training the LM, and the LM works without audio.

---

## Credits

- **[GuppyLM](https://github.com/arman-bd/guppylm)** — Arman Hossain. The base
  tiny-LM recipe this forks. MIT.
- **[OpenPeon Rocky pack](https://openpeon.com/packs/rocky)** /
  [rocky-peon-ping](https://github.com/Akshat1903/rocky-peon-ping) — recorded
  Rocky voice clips (CC-BY-NC-4.0).
- **[`rocky_say`](https://gist.github.com/pedramamini/fa5f6ef99dae79add220188419230642)**
  — Pedram Amini. The voice-clone + text-transform approach the `xtts` backend adapts.
- *Project Hail Mary* — Andy Weir. Rocky is his character.

## License

Code: MIT. Voice clips: CC-BY-NC-4.0 (their pack). Rocky is Andy Weir's character —
this is a non-commercial fan project.
