"""
Pre-warm the Rocky voice cache.

Generates RockyLM's likely replies (over the USER prompt templates) and POSTs
each unique one to the voice service, so its disk cache is populated and the
bot serves those replies' audio instantly. Run once after deploy (and again if
you retrain or change ROCKY_TEMP).

    cd ~/rockylm && .venv/bin/python rvc/prewarm.py
"""
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from rockylm.generate_data import USER
from rockylm.inference import RockyInference

URL = os.environ.get("ROCKY_VOICE_URL", "http://127.0.0.1:8770")
CKPT = os.environ.get("ROCKY_CHECKPOINT", "checkpoints/best_model.pt")
TOK = os.environ.get("ROCKY_TOKENIZER", "data/tokenizer.json")
TEMP = float(os.environ.get("ROCKY_TEMP", "0.4"))
SAMPLES = int(os.environ.get("PREWARM_SAMPLES", "3"))  # samples per prompt

eng = RockyInference(CKPT, TOK, device="cpu")
prompts = [m for msgs in USER.values() for m in msgs]

seen = set()
for p in prompts:
    for _ in range(SAMPLES):
        r = eng.chat_completion([{"role": "user", "content": p}], temperature=TEMP)
        r = r["choices"][0]["message"]["content"]
        if r:
            seen.add(r)
print(f"{len(seen)} unique replies -> warming cache", flush=True)

for i, r in enumerate(sorted(seen), 1):
    try:
        req = urllib.request.Request(URL + "/say", data=r.encode("utf-8"),
                                     headers={"Content-Type": "text/plain"})
        urllib.request.urlopen(req, timeout=120).read()
        if i % 10 == 0 or i == len(seen):
            print(f"  {i}/{len(seen)} cached", flush=True)
    except Exception as e:
        print(f"  err on {r!r}: {e}", flush=True)
print("done", flush=True)
