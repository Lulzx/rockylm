"""Entry point for: python -m rockylm"""

import os
import sys

CHECKPOINT_PATH = "checkpoints/best_model.pt"
TOKENIZER_PATH = "data/tokenizer.json"
GITHUB_REPO = "Lulzx/rockylm"
RELEASE_TAG = os.environ.get("ROCKYLM_RELEASE", "latest")
RELEASE_BASE = (f"https://github.com/{GITHUB_REPO}/releases/latest/download"
                if RELEASE_TAG == "latest"
                else f"https://github.com/{GITHUB_REPO}/releases/download/{RELEASE_TAG}")


def download_model(name="rockylm-9M"):
    """Download pre-trained RockyLM weights from the GitHub release.

    Models available: rockylm-9M (default, fast) and rockylm-27M (better).
    `python -m rockylm download rockylm-27M` fetches the larger one. Each model
    ships its own config + tokenizer (they were trained on different data).
    Set ROCKYLM_RELEASE=vX.Y.Z to pin a release tag instead of `latest`.
    """
    import urllib.request

    files = [
        (f"{RELEASE_BASE}/{name}.pt", CHECKPOINT_PATH),
        (f"{RELEASE_BASE}/{name}.config.json", "checkpoints/config.json"),
        (f"{RELEASE_BASE}/{name}.tokenizer.json", TOKENIZER_PATH),
    ]

    print(f"Downloading {name} from github.com/{GITHUB_REPO} releases ({RELEASE_TAG})...\n")
    for url, dest in files:
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        print(f"  {os.path.basename(dest)}...", end=" ", flush=True)
        try:
            urllib.request.urlretrieve(url, dest)
        except Exception as e:
            print(f"FAILED ({e})\n  url: {url}")
            sys.exit(1)
        print(f"{os.path.getsize(dest) / 1e6:.1f} MB")

    print("\nDone! Run: python -m rockylm chat")


def main():
    if len(sys.argv) < 2:
        print("RockyLM — a tiny alien mind (talks like Rocky from Project Hail Mary)")
        print()
        print("Usage:")
        print("  python -m rockylm train        Train the model")
        print("  python -m rockylm prepare      Generate data & train tokenizer")
        print("  python -m rockylm chat         Chat with Rocky  (add --speak for voice)")
        print("  python -m rockylm say TEXT     Speak text in Rocky's voice")
        print("  python -m rockylm download     Download pre-trained model from the GitHub release")
        print("                                 (rockylm-9M by default; `download rockylm-27M` for the bigger one)")
        return

    cmd = sys.argv[1]
    sys.argv = sys.argv[1:]

    if cmd == "prepare":
        from .prepare_data import prepare
        prepare()

    elif cmd == "train":
        from .train import train
        train()

    elif cmd == "download":
        download_model(*sys.argv[1:2])

    elif cmd == "chat":
        if not (os.path.exists(CHECKPOINT_PATH) and os.path.exists(TOKENIZER_PATH)):
            print("Model not found. Download the pre-trained model first:\n")
            print("  python -m rockylm download\n")
            print("Or train your own:\n")
            print("  python -m rockylm prepare")
            print("  python -m rockylm train")
            return

        from .inference import main as inference_main
        inference_main()

    elif cmd == "say":
        from .tts import main as tts_main
        tts_main()

    else:
        print(f"Unknown command: {cmd}")
        print("Run 'python -m rockylm' for usage.")


main()
