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

CHECKPOINT = os.environ.get("ROCKY_CHECKPOINT", "checkpoints/best_model.pt")
TOKENIZER = os.environ.get("ROCKY_TOKENIZER", "data/tokenizer.json")
TTS_BACKEND = os.environ.get("ROCKY_TTS", "peon")
WHISPER_SIZE = os.environ.get("WHISPER_MODEL", "base")
# "pack" = reply ONLY with OpenPeon Rocky clips (text == voice, always matched).
# "llm"  = generate text with RockyLM, then voice it via ROCKY_TTS.
MODE = os.environ.get("ROCKY_MODE", "pack")

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
        from rockylm.inference import RockyInference  # lazy: only needed in llm mode
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


def wav_to_ogg(wav):
    """Convert a WAV to an OGG/Opus voice note (what Telegram wants). Path or None."""
    if not wav or not os.path.exists(wav):
        return None
    ogg = tempfile.NamedTemporaryFile(suffix=".ogg", delete=False).name
    r = subprocess.run(
        ["ffmpeg", "-y", "-i", wav, "-c:a", "libopus", "-b:a", "32k", ogg],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return ogg if r.returncode == 0 else None


def pack_reply(text):
    """Pack-only reply: the single best OpenPeon Rocky clip for `text`.
    Returns (label, ogg_path) — the label IS the spoken line, so text == voice."""
    wav, label, _ev = tts.clip_for(text=text)
    return label, wav_to_ogg(wav)


def to_voice_ogg(reply_text):
    """LLM-mode voicing: synth/clip for arbitrary reply text. Path or None."""
    wav = tts.synth_xtts(reply_text, verbose=False) if TTS_BACKEND == "xtts" else None
    if wav is None:
        wav, _label, _ev = tts.clip_for(text=reply_text)
    return wav_to_ogg(wav)


# ── handlers ─────────────────────────────────────────────────────────────────

async def _send_voice(update, ogg):
    if ogg:
        try:
            with open(ogg, "rb") as f:
                await update.message.reply_voice(voice=f)
        finally:
            os.unlink(ogg)


async def respond(update: Update, user_text: str):
    chat = update.effective_chat

    if MODE == "pack":
        # text and voice come from the SAME clip -> always matched
        await chat.send_action(ChatAction.RECORD_VOICE)
        label, ogg = await asyncio.to_thread(pack_reply, user_text)
        await update.message.reply_text(label)
        await _send_voice(update, ogg)
        return

    # llm mode: RockyLM text, then voice it
    await chat.send_action(ChatAction.TYPING)
    reply = await asyncio.to_thread(rocky_reply, user_text)
    await update.message.reply_text(reply)
    await chat.send_action(ChatAction.RECORD_VOICE)
    ogg = await asyncio.to_thread(to_voice_ogg, reply)
    await _send_voice(update, ogg)


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


def load_dotenv(path):
    """Minimal .env loader so `python bot/rocky_bot.py` just works."""
    if os.path.exists(path):
        for line in open(path):
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())


def main():
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        print("Set TELEGRAM_BOT_TOKEN (from @BotFather) first.", file=sys.stderr)
        sys.exit(1)
    if MODE == "llm":
        engine()  # fail fast if no checkpoint
    else:
        tts.ensure_pack(verbose=True)  # pre-download the OpenPeon clips

    builder = Application.builder().token(token)
    # Telegram is blocked on some networks (e.g. India). Route through a proxy
    # you trust if provided — needed for both polling and sending. Supports
    # http(s):// and socks5:// (socks needs: pip install "httpx[socks]").
    proxy = (os.environ.get("TELEGRAM_PROXY") or os.environ.get("ALL_PROXY")
             or os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy"))
    if proxy:
        builder = builder.proxy(proxy).get_updates_proxy(proxy)
        print(f"Using proxy for Telegram: {proxy}")

    app = builder.build()
    app.add_handler(CommandHandler("start", on_start))
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, on_voice))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    detail = "pack-only (OpenPeon clips)" if MODE == "pack" else f"llm + tts={TTS_BACKEND}"
    print(f"Rocky bot running (mode={MODE}: {detail}, whisper={WHISPER_SIZE}). Ctrl-C to stop.")
    app.run_polling()


if __name__ == "__main__":
    main()
