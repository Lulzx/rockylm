"""
Rocky Telegram bot.

Send it a voice note (or text). It transcribes your voice with Whisper, runs the
message through the trained RockyLM, and replies with BOTH:
  - text   — RockyLM's answer, in Rocky-speak
  - voice  — Rocky's actual voice (a matching clip from the OpenPeon pack, or,
             if ROCKY_TTS=xtts and Coqui TTS is installed, the exact reply
             synthesized in his cloned voice)

Setup:
    pip install python-telegram-bot[all] faster-whisper   # + torch tokenizers
    export TELEGRAM_BOT_TOKEN=123456:ABC...               # from @BotFather
    python -m rockylm prepare && python -m rockylm train  # make checkpoints/best_model.pt
    python bot/rocky_bot.py

Env:
    TELEGRAM_BOT_TOKEN   required — bot token from @BotFather
    ROCKY_TTS            peon (default, recorded clips) | xtts (neural clone)
    ROCKY_CHECKPOINT     default checkpoints/best_model.pt
    ROCKY_TOKENIZER      default data/tokenizer.json
    WHISPER_MODEL        default "base"  (tiny|base|small|medium)
"""

import asyncio
import os
import subprocess
import sys
import tempfile

# make `rockylm` importable when run as `python bot/rocky_bot.py`
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (Application, CommandHandler, ContextTypes,
                          MessageHandler, filters)

from rockylm import tts
from rockylm.inference import RockyInference

CHECKPOINT = os.environ.get("ROCKY_CHECKPOINT", "checkpoints/best_model.pt")
TOKENIZER = os.environ.get("ROCKY_TOKENIZER", "data/tokenizer.json")
TTS_BACKEND = os.environ.get("ROCKY_TTS", "peon")
WHISPER_SIZE = os.environ.get("WHISPER_MODEL", "base")

# Lazily-initialised singletons (loaded once, reused across messages).
_engine = None
_whisper = None


def engine():
    global _engine
    if _engine is None:
        if not os.path.exists(CHECKPOINT):
            raise FileNotFoundError(
                f"No model at {CHECKPOINT}. Train first:\n"
                "  python -m rockylm prepare && python -m rockylm train"
            )
        _engine = RockyInference(CHECKPOINT, TOKENIZER, device="cpu")
    return _engine


def whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        print(f"Loading Whisper '{WHISPER_SIZE}'...", flush=True)
        _whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _whisper


# ── core pipeline (all blocking; called via asyncio.to_thread) ───────────────

def transcribe(audio_path):
    segments, _ = whisper().transcribe(audio_path)
    return " ".join(seg.text for seg in segments).strip()


def rocky_reply(text):
    out = engine().chat_completion([{"role": "user", "content": text}])
    return out["choices"][0]["message"]["content"] or "..."


def to_voice_ogg(reply_text):
    """Produce an OGG/Opus voice note of Rocky for `reply_text`. Returns path or None."""
    wav = None
    if TTS_BACKEND == "xtts":
        wav = tts.synth_xtts(reply_text, verbose=False)
    if wav is None:  # peon (default) or xtts fallback
        wav, _label, _ev = tts.clip_for(text=reply_text)
    if not wav or not os.path.exists(wav):
        return None
    ogg = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False).name
    # Telegram voice notes must be OGG/Opus
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", wav, "-c:a", "libopus", "-b:a", "32k", ogg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return ogg if r.returncode == 0 else None


# ── handlers ─────────────────────────────────────────────────────────────────

async def respond(update: Update, user_text: str):
    chat = update.effective_chat
    await chat.send_action(ChatAction.TYPING)
    reply = await asyncio.to_thread(rocky_reply, user_text)

    # 1) text
    await update.message.reply_text(reply)

    # 2) voice
    await chat.send_action(ChatAction.RECORD_VOICE)
    ogg = await asyncio.to_thread(to_voice_ogg, reply)
    if ogg:
        try:
            with open(ogg, "rb") as f:
                await update.message.reply_voice(voice=f)
        finally:
            os.unlink(ogg)


async def on_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_file = await (update.message.voice or update.message.audio).get_file()
    with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp:
        ogg_in = tmp.name
    await tg_file.download_to_drive(ogg_in)
    try:
        await update.effective_chat.send_action(ChatAction.TYPING)
        heard = await asyncio.to_thread(transcribe, ogg_in)
    finally:
        os.unlink(ogg_in)
    if not heard:
        await update.message.reply_text("rocky not hear word. question.")
        return
    await update.message.reply_text(f"_rocky hear:_ {heard}", parse_mode="Markdown")
    await respond(update, heard)


async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await respond(update, update.message.text)


async def on_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "hello grace friend. rocky here. ready work.\n"
        "send rocky voice note or text. rocky answer. question?"
    )


def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN (from @BotFather) first.", file=sys.stderr)
        sys.exit(1)
    engine()  # fail fast if no checkpoint
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    print(f"Rocky bot running (tts={TTS_BACKEND}, whisper={WHISPER_SIZE}). Ctrl-C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
