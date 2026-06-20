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
import os
import re
import subprocess
import sys
import tempfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import rvc_infer

PORT = int(os.environ.get("ROCKY_VOICE_PORT", "8770"))
MODEL = os.path.expanduser(os.environ.get("ROCKY_RVC_MODEL", "~/rvc/models/rocky_voice.pth"))
TRANSPOSE = int(os.environ.get("ROCKY_RVC_TRANSPOSE", "0"))
SPEAKER = os.environ.get("TINYTTS_SPEAKER", "MALE")


def tinytts(text, out_wav):
    """Generate base speech with TinyTTS. Returns path or None."""
    r = subprocess.run(
        ["tiny-tts", "-t", text, "-o", "base.wav", "-s", SPEAKER, "--device", "cpu"],
        capture_output=True, text=True,
    )
    m = re.search(r"Saved audio to (.+\.wav)", r.stdout + r.stderr)
    if not m or not os.path.exists(m.group(1).strip()):
        return None
    os.replace(m.group(1).strip(), out_wav)
    return out_wav


def say(text):
    """text -> Rocky-voice WAV bytes."""
    base = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    rocky = tempfile.NamedTemporaryFile(suffix=".wav", delete=False).name
    try:
        if tinytts(text, base) is None:
            return b""
        rvc_infer.convert(base, rocky, MODEL, TRANSPOSE)
        with open(rocky, "rb") as f:
            return f.read()
    finally:
        for p in (base, rocky):
            if os.path.exists(p):
                os.unlink(p)


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
    rvc_infer.load_net(MODEL)   # warm RVC synthesizer
    rvc_infer.hubert()          # warm ContentVec
    print(f"Rocky voice service on http://127.0.0.1:{PORT}  (POST /say, transpose={TRANSPOSE})", flush=True)
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
