"""Synthesize Rocky phrases with TinyTTS (base voice) into tinytts_base/.

The tiny-tts CLI ignores -o's path and writes to ./infer_outputs/<name>_...wav,
printing 'Saved audio to <path>'. We parse that and copy to a clean name.
Run with the venv that has tiny-tts:  python tts-train/tinytts_samples.py
"""
import os
import re
import shutil
import subprocess

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "tinytts_base")
os.makedirs(OUT, exist_ok=True)

PHRASES = [
    "rocky here. ready work.",
    "good good good.",
    "what is astrophage, question?",
    "bad bad bad. rocky sorry.",
    "amaze amaze amaze.",
    "we go home, question?",
]

for i, text in enumerate(PHRASES, 1):
    r = subprocess.run(
        ["tiny-tts", "-t", text, "-o", f"rk{i}.wav", "-s", "MALE", "--device", "cpu"],
        capture_output=True, text=True,
    )
    m = re.search(r"Saved audio to (.+\.wav)", r.stdout + r.stderr)
    src = m.group(1).strip() if m else None
    dst = os.path.join(OUT, f"{i:02d}.wav")
    if src and os.path.exists(src):
        shutil.copy(src, dst)
        print(f"  [{i}] {text:38s} -> {dst}  ({os.path.getsize(dst)} bytes)")
    else:
        print(f"  [{i}] {text:38s} FAILED: {(r.stderr or r.stdout)[-160:]}")

print(f"\nbase samples in {OUT}")
