"""
Launcher for Piper training that works with PyTorch 2.6+.

Newer PyTorch defaults `torch.load(weights_only=True)`, which Lightning uses to
read `--ckpt_path`. Official Piper checkpoints embed a `pathlib.PosixPath`
(and similar) objects, so that strict load fails. We trust the official
rhasspy checkpoints, so we relax the loader before handing off to Piper's CLI.

Usage (from the piper1-gpl venv):
    python /path/to/tts-train/train.py fit \
      --data.voice_name rocky --data.csv_path .../metadata.csv ...
"""

import pathlib
import sys

import torch

# Allowlist the globals Piper checkpoints contain, and relax weights_only for
# the trusted official checkpoint we fine-tune from.
try:
    torch.serialization.add_safe_globals([
        pathlib.PosixPath, pathlib.PurePosixPath, pathlib.WindowsPath, pathlib.PurePath,
    ])
except Exception:
    pass

_orig_load = torch.load


def _load(*args, **kwargs):
    kwargs["weights_only"] = False
    return _orig_load(*args, **kwargs)


torch.load = _load

from piper.train.__main__ import main  # noqa: E402

if __name__ == "__main__":
    main()
