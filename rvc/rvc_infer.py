"""
Fairseq-free RVC v2 inference.

Converts a source WAV into the voice of an RVC .pth model (e.g. rocky_voice.pth)
WITHOUT fairseq: the HuBERT/ContentVec content encoder is loaded via
transformers (lengyue233/content-vec-best), pitch via torchcrepe. Runs on CPU.

    python rvc_infer.py <input.wav> <output.wav> [model.pth] [transpose_semitones]
"""
import os
import sys

import librosa
import numpy as np
import soundfile as sf
import torch
import torch.nn.functional as F
import torchcrepe

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from infer_pack.models import SynthesizerTrnMs768NSFsid
from transformers import HubertModel

DEVICE = "cpu"
# CREPE 'tiny' is ~45x smaller than 'full' — huge CPU speedup, fine for a
# character voice. Override with ROCKY_F0_MODEL=full for max pitch accuracy.
F0_MODEL = os.environ.get("ROCKY_F0_MODEL", "tiny")
# Run the heavy 48 kHz vocoder through ONNX Runtime when a synth ONNX is given
# (static-int8 ~2.5x faster than ORT-fp32, ~3.3x faster than eager torch on ARM).
# ROCKY_RVC_ONNX = path to .onnx, or "" to use eager torch.
ONNX_PATH = os.path.expanduser(os.environ.get("ROCKY_RVC_ONNX", ""))
NOISE_SCALE = float(os.environ.get("ROCKY_RVC_NOISE", "0.66667"))
torch.set_num_threads(os.cpu_count() or 4)
_HUBERT = None
_ORT = {}
_SR = {}


def _ort_session(path):
    import onnxruntime as ort
    if path not in _ORT:
        so = ort.SessionOptions()
        so.intra_op_num_threads = os.cpu_count() or 4
        so.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _ORT[path] = ort.InferenceSession(path, so, providers=["CPUExecutionProvider"])
    return _ORT[path]


def sr_of(pth):
    """Output sample rate without building the (heavy) torch model."""
    if pth not in _SR:
        sr = torch.load(pth, map_location="cpu", weights_only=False)["sr"]
        _SR[pth] = {"32k": 32000, "40k": 40000, "48k": 48000}.get(
            sr, int(sr) if str(sr).isdigit() else 48000)
    return _SR[pth]


def warm(pth):
    """Preload whichever vocoder backend is active (ORT or torch)."""
    if ONNX_PATH:
        _ort_session(ONNX_PATH)
        sr_of(pth)
    else:
        load_net(pth)


def hubert():
    global _HUBERT
    if _HUBERT is None:
        _HUBERT = HubertModel.from_pretrained("lengyue233/content-vec-best")
        _HUBERT.eval().to(DEVICE).float()
    return _HUBERT


_NET = {}


def load_net(pth):
    if pth not in _NET:
        cpt = torch.load(pth, map_location="cpu", weights_only=False)
        net = SynthesizerTrnMs768NSFsid(*cpt["config"], is_half=False)
        net.load_state_dict(cpt["weight"], strict=False)
        net.eval().to(DEVICE).float()
        sr = cpt["sr"]
        sr = {"32k": 32000, "40k": 40000, "48k": 48000}.get(sr, int(sr) if str(sr).isdigit() else 48000)
        _NET[pth] = (net, sr)
    return _NET[pth]


def get_f0(audio16k, p_len, f0_up=0):
    hop = 160  # 16k / 160 = 100 Hz frames (matches 2x-interpolated hubert feats)
    wav = torch.tensor(audio16k, dtype=torch.float32).unsqueeze(0)
    f0 = torchcrepe.predict(wav, 16000, hop, 50, 1100, F0_MODEL,
                            batch_size=512, device=DEVICE, pad=True)[0].cpu().numpy()
    f0 = np.nan_to_num(f0) * (2 ** (f0_up / 12))
    if len(f0) < p_len:
        f0 = np.pad(f0, (0, p_len - len(f0)), mode="edge")
    f0 = f0[:p_len]
    f0_min, f0_max = 50.0, 1100.0
    mel_min, mel_max = 1127 * np.log(1 + f0_min / 700), 1127 * np.log(1 + f0_max / 700)
    f0_mel = 1127 * np.log(1 + f0 / 700)
    f0_mel = np.where(f0_mel > 0, (f0_mel - mel_min) * 254 / (mel_max - mel_min) + 1, f0_mel)
    coarse = np.rint(np.clip(f0_mel, 1, 255)).astype(np.int64)
    return coarse, f0.astype(np.float32)


def _load16k(src):
    """Fast mono 16k load: read native then soxr-lq resample (much faster than librosa default)."""
    y, file_sr = sf.read(src, dtype="float32", always_2d=False)
    if y.ndim > 1:
        y = y.mean(axis=1)
    if file_sr != 16000:
        y = librosa.resample(y, orig_sr=file_sr, target_sr=16000, res_type="soxr_lq")
    return np.ascontiguousarray(y, dtype=np.float32)


def convert(src, dst, pth, transpose=0):
    audio = _load16k(src)
    feats = torch.tensor(audio, dtype=torch.float32).unsqueeze(0).to(DEVICE)
    with torch.inference_mode():
        h = hubert()(feats, output_hidden_states=True).hidden_states[12]   # [1,T,768]
        h = F.interpolate(h.permute(0, 2, 1), scale_factor=2).permute(0, 2, 1)
        p_len = h.shape[1]
        coarse, pitchf = get_f0(audio, p_len, transpose)
        p_len = min(p_len, len(coarse))
        h = h[:, :p_len].float()

        if ONNX_PATH:  # fast path: vocoder via ONNX Runtime
            sr = sr_of(pth)
            rnd = (np.random.standard_normal((1, 192, p_len)).astype(np.float32) * NOISE_SCALE)
            feed = {
                "phone": h.numpy().astype(np.float32),
                "phone_lengths": np.array([p_len], dtype=np.int64),
                "pitch": coarse[:p_len][None].astype(np.int64),
                "nsff0": pitchf[:p_len][None].astype(np.float32),
                "ds": np.array([0], dtype=np.int64),
                "rnd": rnd,
            }
            out = _ort_session(ONNX_PATH).run(None, feed)[0].flatten()
        else:          # eager torch
            net, sr = load_net(pth)
            pitch = torch.tensor(coarse[:p_len], dtype=torch.long).unsqueeze(0)
            nsff0 = torch.tensor(pitchf[:p_len], dtype=torch.float32).unsqueeze(0)
            lengths = torch.tensor([p_len], dtype=torch.long)
            sid = torch.tensor([0], dtype=torch.long)
            out = net.infer(h, lengths, pitch, nsff0, sid)[0][0, 0].cpu().numpy()
    sf.write(dst, out, sr)
    print(f"wrote {dst}  ({len(out)/sr:.2f}s @ {sr}Hz)")


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    pth = sys.argv[3] if len(sys.argv) > 3 else os.path.expanduser("~/rvc/models/rocky_voice.pth")
    tr = int(sys.argv[4]) if len(sys.argv) > 4 else 0
    convert(src, dst, pth, tr)
