"""
Make an old rhasspy Piper checkpoint usable by piper1-gpl for fine-tuning.

The published `lessac/medium` checkpoint stores an old-format Lightning hparam
blob (e.g. `sample_bytes`) that the refactored piper1-gpl model rejects, and
its key layout predates the current code. We:
  1. instantiate a fresh piper1-gpl VitsModel with the architecture hparams,
  2. warm-load the old weights into it (strict=False),
  3. re-save a clean checkpoint with matching state_dict + minimal hparams,
so `--ckpt_path <clean> --weights_only true` fine-tunes cleanly.

    python tts-train/prep_checkpoint.py base_lessac_medium.ckpt base_lessac_medium.clean.ckpt
"""

import inspect
import os
import sys

import torch
from piper.train.vits.lightning import VitsModel

SRC = sys.argv[1] if len(sys.argv) > 1 else "base_lessac_medium.ckpt"
DST = sys.argv[2] if len(sys.argv) > 2 else "base_lessac_medium.clean.ckpt"
HERE = os.path.dirname(os.path.abspath(__file__))
SRC = SRC if os.path.isabs(SRC) else os.path.join(HERE, SRC)
DST = DST if os.path.isabs(DST) else os.path.join(HERE, DST)

old = torch.load(SRC, map_location="cpu", weights_only=False)
hp = old.get("hyper_parameters", {})
sd = old["state_dict"]

sig = set(inspect.signature(VitsModel.__init__).parameters)
drop = {"self", "kwargs", "dataset", "vocoder_warmstart_ckpt"}
model_args = {k: hp[k] for k in hp if k in sig and k not in drop}
# required minimums (medium / en defaults if absent)
model_args.setdefault("sample_rate", 22050)
model_args.setdefault("num_symbols", 256)
model_args.setdefault("num_speakers", 1)
print("model args kept:", sorted(model_args))

model = VitsModel(**model_args)
res = model.load_state_dict(sd, strict=False)
total = len(model.state_dict())
matched = total - len(res.missing_keys)
print(f"warm-loaded {matched}/{total} params "
      f"(missing {len(res.missing_keys)}, unexpected {len(res.unexpected_keys)})")
if res.missing_keys[:3]:
    print("  e.g. missing:", res.missing_keys[:3])
if res.unexpected_keys[:3]:
    print("  e.g. unexpected:", res.unexpected_keys[:3])

torch.save({
    "state_dict": model.state_dict(),
    "hyper_parameters": model_args,
    "epoch": 0,
    "global_step": 0,
    "pytorch-lightning_version": "2.0.0",
    "loops": {},
    "callbacks": {},
    "optimizer_states": [],
    "lr_schedulers": [],
}, DST)
print(f"wrote clean checkpoint -> {DST}")
