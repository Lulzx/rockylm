"""
Rocky Relay — a tiny HTTP server that fronts RockyLM for the Mac companion.

  POST /audio   body = audio/wav (your voice)
                -> transcribes with Whisper, runs RockyLM, returns Rocky's
                   voice as a WAV body, with the text in response headers:
                   X-Transcript : what you said
                   X-Reply      : Rocky's answer (Rocky-speak)
  POST /text    body = text/plain  -> same, but skips transcription (testing)
  GET  /health  -> {"status":"ok","model":"rockylm","tts":"peon|xtts"}

This mirrors the `/audio` contract of github.com/M-A-D-A-R-A/rocky-relay so the
floating Mac companion (mac-companion/) can drive RockyLM locally.

Run:
    python -m rockylm prepare && python -m rockylm train   # need checkpoints
    python relay/server.py                                 # :8765
Env: ROCKY_TTS=peon|xtts, WHISPER_MODEL=base, ROCKY_PORT=8765
"""

import json
import os
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rockylm import tts
from rockylm.inference import RockyInference

PORT = int(os.environ.get("ROCKY_PORT", "8765"))
CHECKPOINT = os.environ.get("ROCKY_CHECKPOINT", "checkpoints/best_model.pt")
TOKENIZER = os.environ.get("ROCKY_TOKENIZER", "data/tokenizer.json")
TTS_BACKEND = os.environ.get("ROCKY_TTS", "peon")
WHISPER_SIZE = os.environ.get("WHISPER_MODEL", "base")

_engine = None
_whisper = None


def engine():
    global _engine
    if _engine is None:
        _engine = RockyInference(CHECKPOINT, TOKENIZER, device="cpu")
    return _engine


def whisper():
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel
        print(f"Loading Whisper '{WHISPER_SIZE}'...", flush=True)
        _whisper = WhisperModel(WHISPER_SIZE, device="cpu", compute_type="int8")
    return _whisper


def transcribe(wav_path):
    segments, _ = whisper().transcribe(wav_path)
    return " ".join(s.text for s in segments).strip()


def rocky_reply(text):
    out = engine().chat_completion([{"role": "user", "content": text}])
    return out["choices"][0]["message"]["content"] or "..."


def reply_wav(reply_text):
    """Return WAV bytes of Rocky's voice for the reply."""
    wav = None
    if TTS_BACKEND == "xtts":
        wav = tts.synth_xtts(reply_text, verbose=False)
    if wav is None:
        wav, _label, _ev = tts.clip_for(text=reply_text)
    if not wav or not os.path.exists(wav):
        return b""
    # ensure plain PCM WAV (clips already are; xtts output too)
    with open(wav, "rb") as f:
        return f.read()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _audio(self, transcript, reply, wav_bytes):
        self.send_response(200)
        self.send_header("Content-Type", "audio/wav")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "X-Transcript, X-Reply")
        self.send_header("X-Transcript", quote(transcript))
        self.send_header("X-Reply", quote(reply))
        self.send_header("Content-Length", str(len(wav_bytes)))
        self.end_headers()
        self.wfile.write(wav_bytes)

    def do_GET(self):
        if self.path == "/health":
            self._json(200, {"status": "ok", "model": "rockylm", "tts": TTS_BACKEND})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n) if n else b""
        try:
            if self.path == "/audio":
                with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                    f.write(body)
                    path = f.name
                try:
                    transcript = transcribe(path)
                finally:
                    os.unlink(path)
            elif self.path == "/text":
                transcript = body.decode("utf-8", "ignore").strip()
            else:
                return self._json(404, {"error": "not found"})

            if not transcript:
                return self._audio("", "rocky not hear word. question.",
                                   reply_wav("rocky not hear word. question."))
            reply = rocky_reply(transcript)
            print(f"  heard: {transcript!r}  ->  rocky: {reply!r}", flush=True)
            self._audio(transcript, reply, reply_wav(reply))
        except Exception as e:
            self._json(500, {"error": str(e)})


def main():
    if not os.path.exists(CHECKPOINT):
        print(f"No model at {CHECKPOINT}. Train first:\n"
              "  python -m rockylm prepare && python -m rockylm train", file=sys.stderr)
        sys.exit(1)
    engine()  # warm up / fail fast
    print(f"Rocky relay on http://127.0.0.1:{PORT}  (tts={TTS_BACKEND}, whisper={WHISPER_SIZE})")
    print("  POST /audio (wav) | POST /text | GET /health")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
