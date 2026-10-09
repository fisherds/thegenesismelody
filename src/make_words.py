#!/usr/bin/env python3
"""
make_words.py

Step 3: transcribe the narration with OpenAI Whisper and write word-level
timestamps to src/TheGenesisMelody_words.json.

Output format (a flat list, one entry per spoken word, times in seconds):
    [{"start": 0.0, "end": 0.48, "text": "The"}, ...]

Also writes src/TheGenesisMelody_whisper_segments.json (Whisper's segment-level
text and times), which is handy for spot-checking what Whisper heard.

The words don't need to be spelled perfectly. The next step aligns them to the
known sentence text in TheGenesisMelody_sentences.json, so what matters most
is the timing.

Setup (once):
    python3.13 -m venv src/.venv
    src/.venv/bin/pip install -r src/requirements.txt
    brew install ffmpeg

Run (from the repo root; ~20-60 minutes for the ~2 hour recording on CPU):
    src/.venv/bin/python src/make_words.py

Options:
    --audio  path to the narration    (default: public/audio/TheGenesisMelody.m4a)
    --model  Whisper model name       (default: turbo; "base" is faster but less accurate)
    --device cpu or mps               (default: cpu; Whisper's word timing isn't reliable on mps)
"""

import argparse
import json
import time
from pathlib import Path

import whisper

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIO = ROOT / "public" / "audio" / "TheGenesisMelody.m4a"
WORDS_JSON = ROOT / "src" / "TheGenesisMelody_words.json"
SEGMENTS_JSON = ROOT / "src" / "TheGenesisMelody_whisper_segments.json"

# Names and Hebrew words from the guide, so Whisper spells them the way the text does.
PROMPT = (
    "The Genesis Melody. Avraham, Avram, Sarai, Yitskhaq, Elohim, Yahweh, Ruakh, "
    "zakar, sheva, Beer-Sheva, Avimelek, Terakh, Haran, Hagar, Ishmael, na'ar, "
    "Mahalalel, Yared, Enoch, Methuselah, Japheth, Rivqah, tohu va-vohu, tehom, "
    "yalad ben, heron, monogenes, teleios, Imago Dei, BibleProject."
)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audio", default=str(DEFAULT_AUDIO))
    ap.add_argument("--model", default="turbo")
    ap.add_argument("--device", default="cpu")
    args = ap.parse_args()

    start = time.time()
    print(f"Loading Whisper model '{args.model}' on {args.device} (first run downloads it)...")
    model = whisper.load_model(args.model, device=args.device)

    print(f"Transcribing {args.audio} ...")
    result = model.transcribe(
        args.audio,
        language="en",
        word_timestamps=True,
        initial_prompt=PROMPT,
        fp16=(args.device != "cpu"),
        verbose=False,  # shows a progress bar instead of printing every segment
    )

    words = [
        {"start": round(float(w["start"]), 2), "end": round(float(w["end"]), 2), "text": w["word"].strip()}
        for seg in result["segments"]
        for w in seg.get("words", [])
        if w["word"].strip()
    ]
    segments = [
        {"start": round(float(s["start"]), 2), "end": round(float(s["end"]), 2), "text": s["text"].strip()}
        for s in result["segments"]
    ]

    WORDS_JSON.write_text(json.dumps(words, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    SEGMENTS_JSON.write_text(json.dumps(segments, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    minutes = (time.time() - start) / 60
    last = words[-1]["end"] if words else 0
    print(f"Wrote {len(words)} words to {WORDS_JSON.relative_to(ROOT)}")
    print(f"Wrote {len(segments)} segments to {SEGMENTS_JSON.relative_to(ROOT)}")
    print(f"Audio covered: {last / 60:.1f} minutes. Took {minutes:.1f} minutes.")


if __name__ == "__main__":
    main()
