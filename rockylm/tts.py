"""
RockyLM TTS — give Rocky a voice.

Two backends, both speaking as Rocky from *Project Hail Mary*:

  peon  (default, zero extra deps)
        Plays Rocky's *recorded* voice from the OpenPeon "Rocky" pack — 58
        clips across 7 coding-event categories (CESP standard). We pick the
        clip whose line best matches the text (or a category/event), then play
        it with the system audio player. No model, no GPU, no torch.
        Pack:  https://openpeon.com/packs/rocky
        Repo:  https://github.com/Akshat1903/rocky-peon-ping

  xtts  (neural voice clone, speaks ANY text)
        Synthesizes arbitrary text in Rocky's cloned voice with Coqui XTTS v2,
        using the pack's reference audio as the speaker. Heavier: needs
        `pip install TTS`. Adapted from Pedram Amini's `rocky_say`:
        https://gist.github.com/pedramamini/fa5f6ef99dae79add220188419230642

The `rocky_transform()` helper turns plain English into Rocky-speak first, so
even the neural backend (or any text) comes out in character. RockyLM's own
output is already Rocky-speak, so for chat you usually skip the transform.

Usage:
    python -m rockylm.tts "good good good. we fix star."
    python -m rockylm.tts --event task.complete
    python -m rockylm.tts --backend xtts --transform "That is amazing, thank you!"
    python -m rockylm.tts --list
"""

import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import urllib.request

# ── Pack location ────────────────────────────────────────────────────────────
PACK_TAG = "v1.0.1"
RAW_BASE = f"https://raw.githubusercontent.com/Akshat1903/rocky-peon-ping/{PACK_TAG}"
MANIFEST_URL = f"{RAW_BASE}/rocky_pack/openpeon.json"
REFERENCE_URL = f"{RAW_BASE}/rocky_training_audio_scrubbed.wav"

CACHE_DIR = os.path.expanduser("~/.rockylm/rocky_pack")
MANIFEST_PATH = os.path.join(CACHE_DIR, "openpeon.json")
REFERENCE_PATH = os.path.join(CACHE_DIR, "rocky_training_audio_scrubbed.wav")

# Map RockyLM topic categories (from generate_data.py) -> CESP event categories.
# Used by chat --speak when a category is known; text matching is the fallback.
TOPIC_TO_EVENT = {
    "greeting": "session.start", "state": "session.start", "identity": "session.start",
    "science": "task.complete", "build": "task.complete", "fix": "task.complete",
    "predator": "task.complete", "fuel": "task.complete", "xenonite": "task.complete",
    "math": "task.complete", "fishing": "task.complete", "smart": "task.complete",
    "amaze": "task.complete", "naming": "task.complete",
    "deal": "task.acknowledge", "yesno": "task.acknowledge", "teach": "task.acknowledge",
    "help": "task.acknowledge", "encourage": "task.acknowledge",
    "danger": "task.error", "scared": "task.error", "apology": "task.error",
    "crew": "task.error",
    "idiom": "input.required", "emotion_word": "input.required", "why": "input.required",
    "hug": "input.required", "goodbye": "input.required", "joke": "input.required",
    "sound": "input.required", "friend": "input.required",
    "miss": "resource.limit", "death": "resource.limit", "home": "resource.limit",
    "mate": "resource.limit", "heat": "resource.limit", "eat": "resource.limit",
    "earth": "resource.limit", "sleep": "resource.limit", "party": "task.complete",
    "gift": "task.complete", "gesture": "task.acknowledge", "sacrifice": "input.required",
    "music": "session.start",
}

_STOP = {
    "rocky", "you", "i", "the", "a", "an", "to", "is", "it", "we", "and", "of",
    "for", "in", "on", "that", "this", "do", "no", "not", "your", "make", "want",
    "go", "now", "very",
}

# Strong keyword → CESP event hints; matching words boost that event's clips.
EVENT_HINTS = {
    "input.required": {"mean", "understand", "confuse", "question", "why", "wait",
                       "help", "answer", "explain", "know", "what"},
    "task.error": {"bad", "error", "sorry", "fail", "break", "wrong", "problem", "sad"},
    "task.complete": {"done", "amaze", "finish", "solve", "proud", "easy",
                      "complete", "engineer", "science", "code"},
    "task.acknowledge": {"yes", "okay", "ok", "idea", "listen", "got", "understand"},
    "session.start": {"hello", "morning", "awake", "ready", "arrive", "new", "hi", "friend"},
    "resource.limit": {"tired", "rest", "full", "fuel", "limit", "token", "much", "brain"},
    "user.spam": {"stop", "busy", "impatient", "fast", "click", "brave"},
}


# ══════════════════════════════════════════════════════════════════════════════
#  TEXT TRANSFORM: English → Rocky-speak
#  (rule-based; adapted from Pedram Amini's rocky_say. RockyLM output is already
#   in this style, so this is only needed for arbitrary input text.)
# ══════════════════════════════════════════════════════════════════════════════

ARTICLES = {"a", "an", "the"}
AUXILIARIES = {"is", "are", "was", "were", "will", "would", "should", "could",
               "do", "does", "did", "has", "have", "had", "am", "been", "being"}
CONTRACTIONS = {
    "i'm": "i", "i've": "i", "i'll": "i", "i'd": "i",
    "you're": "you", "you've": "you", "you'll": "you",
    "we're": "we", "we've": "we", "we'll": "we",
    "they're": "they", "it's": "it", "that's": "that", "there's": "there",
    "what's": "what", "don't": "no", "doesn't": "no", "didn't": "no",
    "can't": "can not", "cannot": "can not", "won't": "will not",
    "isn't": "is not", "aren't": "are not", "haven't": "no have",
}
EMPHASIS_MAP = {
    "amazing": "amaze amaze amaze", "wonderful": "amaze amaze amaze",
    "incredible": "amaze amaze amaze", "fantastic": "amaze amaze amaze",
    "excellent": "good good good", "great": "good good good",
    "terrible": "bad bad bad", "awful": "bad bad bad", "horrible": "bad bad bad",
    "happy": "happy happy happy", "excited": "happy happy happy",
    "sad": "sad sad sad", "angry": "angry angry angry",
    "confused": "confuse confuse confuse", "scared": "scared scared scared",
    "afraid": "scared scared scared", "absolutely": "yes yes yes",
    "definitely": "yes yes yes",
}
PHRASE_MAP = [
    (r"i don'?t understand", "no understand"),
    (r"i do not understand", "no understand"),
    (r"i don'?t know", "rocky not know"),
    (r"what do you mean", "what mean"),
    (r"what does that mean", "what mean"),
    (r"i'?m going to", "rocky"),
    (r"going to ", ""), (r"want to ", "want "), (r"need to ", "need "),
    (r"have to ", "must "), (r"a lot of ", "many "), (r"lots of ", "many "),
    (r"right now", "now"), (r"however", "but"), (r"therefore", "so"),
    (r"really", "very"), (r"goodbye", "no understand word"),
]


def rocky_transform(text):
    """Transform English text into Rocky's speech patterns."""
    if not text or not text.strip():
        return text
    out = []
    for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
        s = sentence.strip()
        if not s:
            continue
        is_q = s.endswith("?")
        for pat, rep in PHRASE_MAP:
            s = re.sub(pat, rep, s, flags=re.IGNORECASE)
        words, new = s.split(), []
        for w in words:
            low = w.lower().rstrip(".,!?;:")
            punct = w[len(low):] if len(w) > len(low) else ""
            if low in CONTRACTIONS:
                new.append(CONTRACTIONS[low] + punct)
            elif low in EMPHASIS_MAP:
                new.append(EMPHASIS_MAP[low] + punct)
            elif low in ARTICLES:
                continue
            elif low in AUXILIARIES and new:
                continue
            else:
                new.append(w)
        s = re.sub(r"\s+", " ", " ".join(new)).strip()
        if is_q and "question" not in s.lower():
            s = s.rstrip("?").strip() + ". question?"
        out.append(s.lower())
    result = re.sub(r"\s+([.,!?])", r"\1", " ".join(out))
    return re.sub(r"\.\.+", ".", result).strip()


# ══════════════════════════════════════════════════════════════════════════════
#  PEON BACKEND — play Rocky's recorded voice from the OpenPeon pack
# ══════════════════════════════════════════════════════════════════════════════

def _download(url, dest):
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)


def ensure_pack(verbose=True):
    """Download the OpenPeon Rocky pack (manifest + 58 clips) on first use."""
    if not os.path.exists(MANIFEST_PATH):
        if verbose:
            print("Downloading Rocky voice pack manifest...", file=sys.stderr)
        _download(MANIFEST_URL, MANIFEST_PATH)
    manifest = json.load(open(MANIFEST_PATH))
    sounds_dir = os.path.join(CACHE_DIR, "sounds")
    n = 0
    for cat in manifest["categories"].values():
        for snd in cat.get("sounds", []):
            name = snd["file"].split("/")[-1]
            dest = os.path.join(sounds_dir, name)
            if not os.path.exists(dest):
                _download(f"{RAW_BASE}/rocky_pack/{snd['file']}", dest)
                n += 1
    if verbose and n:
        print(f"Downloaded {n} Rocky clips to {CACHE_DIR}", file=sys.stderr)
    return manifest


def _clip_path(snd):
    return os.path.join(CACHE_DIR, "sounds", snd["file"].split("/")[-1])


def _tokens(text):
    return [t for t in re.findall(r"[a-z]+", text.lower()) if t not in _STOP]


def _all_sounds(manifest):
    out = []
    for event, body in manifest["categories"].items():
        for snd in body.get("sounds", []):
            out.append((event, snd))
    return out


def pick_clip(manifest, text=None, event=None, category=None):
    """Choose the best-matching clip for given text / CESP event / topic category."""
    # 1. explicit CESP event wins
    if event and event in manifest["categories"]:
        return event, random.choice(manifest["categories"][event]["sounds"])
    # 2. RockyLM topic category -> CESP event
    if category and TOPIC_TO_EVENT.get(category) in manifest["categories"]:
        ev = TOPIC_TO_EVENT[category]
        return ev, random.choice(manifest["categories"][ev]["sounds"])
    # 3. match text against clip labels by shared distinctive words
    if text:
        want = set(_tokens(text))
        best, best_score = None, 0
        for ev, snd in _all_sounds(manifest):
            label_toks = set(_tokens(snd["label"]))
            score = len(want & label_toks)
            # bonus for matching emphasis triples like "good good good" / "amaze"
            for key in ("amaze", "good", "bad", "sad", "happy", "yes", "confuse"):
                if key in want and key in label_toks:
                    score += 1
            # bonus when the text's intent words point at this clip's event
            score += 2 * len(want & EVENT_HINTS.get(ev, set()))
            if score > best_score:
                best, best_score = (ev, snd), score
        if best:
            return best
    # 4. fallback: random clip
    return random.choice(_all_sounds(manifest))


def _player():
    for p in ("afplay", "ffplay", "aplay", "paplay", "mpv"):
        if shutil.which(p):
            return p
    return None


def play(path):
    """Play a wav with whatever system player is available."""
    p = _player()
    if not p:
        print(f"(no audio player found — clip at {path})", file=sys.stderr)
        return False
    cmd = {
        "afplay": [p, path],
        "ffplay": [p, "-nodisp", "-autoexit", "-loglevel", "quiet", path],
        "aplay": [p, "-q", path],
        "paplay": [p, path],
        "mpv": [p, "--really-quiet", path],
    }[p]
    subprocess.run(cmd, check=False)
    return True


def clip_for(text=None, event=None, category=None, verbose=False):
    """Resolve the best Rocky clip WITHOUT playing it.

    Returns (wav_path, label, event). Used by the Telegram bot to attach
    Rocky's recorded voice to a reply.
    """
    manifest = ensure_pack(verbose=verbose)
    ev, snd = pick_clip(manifest, text=text, event=event, category=category)
    return _clip_path(snd), snd["label"], ev


def speak_peon(text=None, event=None, category=None, verbose=True):
    """Speak as Rocky using a recorded pack clip. Returns the clip label."""
    path, label, ev = clip_for(text=text, event=event, category=category, verbose=verbose)
    if verbose:
        print(f"  🔊 [{ev}] rocky: \"{label}\"", file=sys.stderr)
    play(path)
    return label


# ══════════════════════════════════════════════════════════════════════════════
#  XTTS BACKEND — neural voice clone (speaks arbitrary text)
# ══════════════════════════════════════════════════════════════════════════════

def ensure_reference(verbose=True):
    if not os.path.exists(REFERENCE_PATH):
        if verbose:
            print("Downloading Rocky reference audio for voice clone...", file=sys.stderr)
        _download(REFERENCE_URL, REFERENCE_PATH)
    return REFERENCE_PATH


_XTTS = None


def synth_xtts(text, out_path=None, verbose=True):
    """Synthesize `text` to a wav file in Rocky's cloned voice. No playback.

    Returns the wav path, or None if Coqui TTS is not installed.
    """
    global _XTTS
    try:
        from TTS.api import TTS
    except ImportError:
        return None
    reference = ensure_reference(verbose=verbose)
    out_path = out_path or os.path.join(CACHE_DIR, "_rocky_say.wav")
    if _XTTS is None:  # cache the model across calls (bot reuse)
        if verbose:
            print("Loading XTTS v2 (first call is slow)...", file=sys.stderr)
        _XTTS = TTS("tts_models/multilingual/multi-dataset/xtts_v2")
    _XTTS.tts_to_file(text=text, speaker_wav=reference, language="en", file_path=out_path)
    return out_path


def speak_xtts(text, out_path=None, verbose=True):
    """Synthesize `text` in Rocky's cloned voice via Coqui XTTS v2, then play."""
    if verbose:
        print(f"  synthesizing: \"{text}\"", file=sys.stderr)
    path = synth_xtts(text, out_path=out_path, verbose=verbose)
    if path is None:
        print(
            "xtts backend needs Coqui TTS:  pip install TTS\n"
            "(Falling back to the recorded 'peon' backend.)",
            file=sys.stderr,
        )
        return speak_peon(text=text, verbose=verbose)
    play(path)
    return path


# ══════════════════════════════════════════════════════════════════════════════
#  PUBLIC ENTRY
# ══════════════════════════════════════════════════════════════════════════════

def speak(text, backend="peon", event=None, category=None, transform=False, verbose=True):
    """Speak text as Rocky. backend = 'peon' (recorded) or 'xtts' (neural clone)."""
    if transform and text:
        text = rocky_transform(text)
        if verbose:
            print(f"  rocky-speak: {text}", file=sys.stderr)
    if backend == "xtts":
        return speak_xtts(text, verbose=verbose)
    return speak_peon(text=text, event=event, category=category, verbose=verbose)


def main():
    import argparse
    p = argparse.ArgumentParser(description="Speak text in Rocky's voice")
    p.add_argument("text", nargs="*", help="text to speak (Rocky-speak or English with --transform)")
    p.add_argument("--backend", "-b", default="peon", choices=["peon", "xtts"])
    p.add_argument("--event", "-e", help="play a clip for a CESP event, e.g. task.complete")
    p.add_argument("--category", "-c", help="RockyLM topic category to map to an event")
    p.add_argument("--transform", "-t", action="store_true", help="convert English -> Rocky-speak first")
    p.add_argument("--list", "-l", action="store_true", help="list pack events and clips")
    args = p.parse_args()

    if args.list:
        m = ensure_pack()
        for ev, body in m["categories"].items():
            print(f"\n{ev}:")
            for snd in body.get("sounds", []):
                print(f"  {snd['file'].split('/')[-1]:24} \"{snd['label']}\"")
        return

    text = " ".join(args.text).strip()
    if not text and not sys.stdin.isatty():
        text = sys.stdin.read().strip()
    if not text and not args.event:
        print("nothing to say. give text, or --event, or --list.", file=sys.stderr)
        sys.exit(1)
    speak(text or None, backend=args.backend, event=args.event,
          category=args.category, transform=args.transform)


if __name__ == "__main__":
    main()
