"""
Export the RVC synthesizer (rocky_voice.pth) to ONNX + int8 for fast ORT inference.

The 48 kHz vocoder's conv stack is the warm-latency bottleneck on CPU. ONNX
Runtime (MLAS) + int8 weights (fast on ARM NEON) speed it up ~3-4x vs eager
PyTorch. We keep ContentVec/pitch in torch (already cheap) and run only the
synthesizer through ORT.

    python rvc/export_onnx.py [model.pth] [out.onnx]
-> writes out.onnx (fp32) and out.int8.onnx (dynamic int8).
"""
import os
import sys

import torch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from infer_pack.models_onnx import SynthesizerTrnMsNSFsidM

MODEL = os.path.expanduser(sys.argv[1] if len(sys.argv) > 1 else "~/rvc/models/rocky_voice.pth")
OUT = os.path.expanduser(sys.argv[2] if len(sys.argv) > 2 else "~/rvc/models/rocky_voice.onnx")

cpt = torch.load(MODEL, map_location="cpu", weights_only=False)
net = SynthesizerTrnMsNSFsidM(*cpt["config"], cpt.get("version", "v2"), is_half=False)
net.load_state_dict(cpt["weight"], strict=False)
net.eval()

T = 240
dummy = (
    torch.rand(1, T, 768),                       # phone (hubert feats)
    torch.tensor([T]).long(),                    # phone_lengths
    torch.randint(1, 255, (1, T)).long(),        # pitch (coarse)
    torch.rand(1, T) * 200 + 100,                # nsff0 (f0 hz)
    torch.LongTensor([0]),                       # ds (speaker id)
    torch.randn(1, 192, T),                      # rnd (flow noise)
)
names = ["phone", "phone_lengths", "pitch", "nsff0", "ds", "rnd"]
dyn = {"phone": {1: "t"}, "pitch": {1: "t"}, "nsff0": {1: "t"}, "rnd": {2: "t"}, "audio": {2: "t"}}

torch.onnx.export(net, dummy, OUT, input_names=names, output_names=["audio"],
                  dynamic_axes=dyn, opset_version=17, dynamo=False)
print(f"exported {OUT} ({os.path.getsize(OUT)/1e6:.1f} MB)")

from onnxruntime.quantization import QuantType, quantize_dynamic  # noqa: E402

int8 = OUT.replace(".onnx", ".int8.onnx")
quantize_dynamic(OUT, int8, weight_type=QuantType.QInt8)
print(f"quantized {int8} ({os.path.getsize(int8)/1e6:.1f} MB)")
