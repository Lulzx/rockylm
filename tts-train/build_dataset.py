"""
Build a Piper (LJSpeech-style) training dataset for a Rocky voice.

Source: the OpenPeon Rocky pack — 58 clips that already ship with transcripts
(the `label` of each sound in openpeon.json). We resample each clip to 22050 Hz
mono 16-bit (Piper "medium" quality) and write a `metadata.csv` of
`wav|text` lines that `python -m piper.train fit` consumes.

  python tts-train/build_dataset.py            # -> tts-train/dataset/{audio,metadata.csv}

Add more data later (e.g. segmented film audio) by dropping wavs in audio/ and
appending `wav|text` lines to metadata.csv.
"""

import json
import os
import subprocess
import sys

PACK = os.path.expanduser("~/.rockylm/rocky_pack")
MANIFEST = os.path.join(PACK, "openpeon.json")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dataset")
AUDIO_DIR = os.path.join(OUT, "audio")
SAMPLE_RATE = 22050


def ensure_pack():
    if not os.path.exists(MANIFEST):
        # reuse the project's downloader
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from rockylm import tts
        tts.ensure_pack(verbose=True)


def clean_text(label):
    """Normalize a clip label into spoken text for espeak-ng."""
    t = label.strip().lower()
    # the labels are already Rocky-speak; just tidy punctuation/spacing
    t = t.replace(" ,", ",").strip(" .")
    return t + "."


def main():
    ensure_pack()
    manifest = json.load(open(MANIFEST))
    os.makedirs(AUDIO_DIR, exist_ok=True)

    rows = []
    for event, body in manifest["categories"].items():
        for snd in body.get("sounds", []):
            name = snd["file"].split("/")[-1]
            src = os.path.join(PACK, "sounds", name)
            if not os.path.exists(src):
                continue
            dst = os.path.join(AUDIO_DIR, name)
            # resample -> 22050 Hz mono 16-bit PCM
            subprocess.run(
                ["ffmpeg", "-y", "-i", src, "-ar", str(SAMPLE_RATE), "-ac", "1",
                 "-c:a", "pcm_s16le", dst],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True,
            )
            rows.append((name, clean_text(snd["label"])))

    csv_path = os.path.join(OUT, "metadata.csv")
    with open(csv_path, "w") as f:
        for name, text in rows:
            f.write(f"{name}|{text}\n")

    total_sec = 0.0
    for name, _ in rows:
        out = subprocess.run(["ffprobe", "-v", "quiet", "-show_entries",
                              "format=duration", "-of", "csv=p=0",
                              os.path.join(AUDIO_DIR, name)], capture_output=True, text=True)
        try:
            total_sec += float(out.stdout.strip())
        except ValueError:
            pass

    print(f"Dataset: {len(rows)} utterances, ~{total_sec/60:.1f} min total audio")
    print(f"  audio:    {AUDIO_DIR}/ (22050 Hz mono)")
    print(f"  metadata: {csv_path}")
    print("\nSample lines:")
    for name, text in rows[:5]:
        print(f"  {name}|{text}")


if __name__ == "__main__":
    main()
