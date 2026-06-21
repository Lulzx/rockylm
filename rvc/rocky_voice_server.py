"""
Rocky voice service — text in, Rocky's voice (WAV) out.

Pipeline:  text --TinyTTS--> generic speech --RVC(rocky_voice.pth)--> Rocky voice

Loads TinyTTS (subprocess), ContentVec, and the RVC model ONCE and keeps them
warm, so each request is fast. The Telegram bot's `rvc` TTS backend calls this.

  POST /say    body = text/plain   -> audio/wav (Rocky voice, 48 kHz)
  GET  /health -> {"status":"ok"}

Run (in the venv that has tiny-tts + the fairseq-free RVC deps):
    python rvc/rocky_voice_server.py
Env: ROCKY_VOICE_PORT=8770, ROCKY_RVC_MODEL=~/rvc/models/rocky_voice.pth,
     ROCKY_RVC_TRANSPOSE=0, TINYTTS_SPEAKER=MALE
"""
import glob
import hashlib
import os
import sys
import tempfile
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rvc_infer

PORT = int(os.environ.get("ROCKY_VOICE_PORT", "8770"))
MODEL = os.path.expanduser(os.environ.get("ROCKY_RVC_MODEL", "~/rvc/models/rocky_voice.pth"))
TRANSPOSE = int(os.environ.get("ROCKY_RVC_TRANSPOSE", "0"))
SPEAKER = os.environ.get("TINYTTS_SPEAKER", "MALE")

_TTS = None


def tts_engine():
    """TinyTTS loaded once and kept warm (avoids per-call torch import)."""
    global _TTS
    if _TTS is None:
        from tiny_tts import TinyTTS
        _TTS = TinyTTS(device="cpu")
    return _TTS


def tinytts(text, out_wav):
    """Generate base speech with TinyTTS (in-process). Returns path or None."""
    tts_engine().speak(text, output_path=out_wav, speaker=SPEAKER)
    if os.path.exists(out_wav):
        return out_wav
    # TinyTTS sometimes renames into ./infer_outputs/ — grab the newest
    cand = sorted(glob.glob("infer_outputs/*.wav"), key=os.path.getmtime)
    return cand[-1] if cand else None


# text -> WAV cache. RockyLM emits a small set of distinct replies, so most
# requests are repeats -> instant. Persists to disk so it survives restarts and
# can be pre-warmed offline.
CACHE_DIR = os.path.expanduser(os.environ.get("ROCKY_VOICE_CACHE_DIR", "~/rvc/cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
_MEM = OrderedDict()
_MEM_MAX = int(os.environ.get("ROCKY_VOICE_CACHE", "512"))


def _key(text):
    return hashlib.sha1(f"{TRANSPOSE}|{SPEAKER}|{text}".encode()).hexdigest()


def say(text):
    """text -> Rocky-voice WAV bytes (cached by text)."""
    k = _key(text)
    if k in _MEM:                                   # hot path: instant
        _MEM.move_to_end(k)
        return _MEM[k]
    disk = os.path.join(CACHE_DIR, k + ".wav")
    if os.path.exists(disk):                        # warm path: read from disk
        with open(disk, "rb") as f:
            wav = f.read()
        _MEM[k] = wav
        return wav

    base = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        src = tinytts(text, base)
        if src is None:
            return b""
        rvc_infer.convert(src, disk, MODEL, TRANSPOSE)   # synth straight to cache
        with open(disk, "rb") as f:
            wav = f.read()
    finally:
        if os.path.exists(base):
            os.unlink(base)
    _MEM[k] = wav
    if len(_MEM) > _MEM_MAX:
        _MEM.popitem(last=False)
    return wav


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_GET(self):
        if self.path == "/health":
            body = b'{"status":"ok","voice":"rocky-rvc"}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        text = self.rfile.read(n).decode("utf-8", "ignore").strip() if n else ""
        if not text:
            self.send_response(400)
            self.end_headers()
            return
        try:
            wav = say(text)
        except Exception as e:
            print(f"  say error: {e}", flush=True)
            wav = b""
        self.send_response(200 if wav else 500)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Content-Length", str(len(wav)))
        self.end_headers()
        if wav:
            self.wfile.write(wav)


def main():
    print(f"Loading Rocky voice models (TinyTTS + ContentVec + {os.path.basename(MODEL)})...", flush=True)
    tts_engine()                # warm TinyTTS
    rvc_infer.warm(MODEL)       # warm RVC vocoder (ORT or torch)
    rvc_infer.hubert()          # warm ContentVec
    print(f"Rocky voice service on http://127.0.0.1:{PORT}  (POST /say, transpose={TRANSPOSE})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
