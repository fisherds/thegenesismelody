#!/usr/bin/env python3
"""
align_sentences.py

Step 4: fill in start/end for every sentence in src/TheGenesisMelody_sentences.json
using the Whisper word timings in src/TheGenesisMelody_words.json.

How it works:
1. Both texts are broken into words (lowercase, punctuation removed).
2. The two word lists are lined up in order with a diff (difflib). Words that
   match become anchors with known times. Extra speech in the recording (an
   ad-lib, the "read for you by..." intro) and words Whisper misheard are skipped.
3. A sentence's start is when its first matched word was spoken; its end is when
   its last matched word finished. If a sentence's matches fall into groups far
   apart in time (a common word like "the" matched somewhere unrelated), only the
   largest group counts.
4. A sentence with no matches that sits between two timed sentences gets the time
   between them (e.g. "Yitskhaq," heard as "Yitzhak"). One with no room at all keeps
   start/end = -1 (not narrated) and won't highlight.

Writes:
    src/TheGenesisMelody_sentences.json   start/end filled in (ids and text unchanged)
    src/align_report.csv                  one row per sentence: match %, times, text, what Whisper heard

Run from the repo root (standard library only):
    python3 src/align_sentences.py
"""

import csv
import json
import re
from difflib import SequenceMatcher
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_JSON = ROOT / "src" / "TheGenesisMelody_sentences.json"
WORDS_JSON = ROOT / "src" / "TheGenesisMelody_words.json"
REPORT_CSV = ROOT / "src" / "align_report.csv"

LOW_MATCH = 0.5   # report flag: fewer than half of a sentence's words were matched
STRAY_GAP = 6.0   # seconds between matched words that splits a sentence's matches into groups


def tokens(text: str) -> list:
    """Lowercase words, ignoring punctuation. Hyphens and dashes split words."""
    text = text.lower().replace("’", "'").replace("‘", "'")
    text = re.sub(r"[-–—/|]", " ", text)
    return re.findall(r"[a-z0-9']+", text.replace("'", "")) if text else []


def main():
    sentences = json.loads(SENTENCES_JSON.read_text(encoding="utf8"))
    words = json.loads(WORDS_JSON.read_text(encoding="utf8"))

    # Sentence words, each remembering which sentence it came from
    text_toks, text_sent = [], []
    for si, s in enumerate(sentences):
        for t in tokens(s["text"]):
            text_toks.append(t)
            text_sent.append(si)

    # Whisper words (one Whisper word can hold two tokens, e.g. "1-23")
    audio_toks, audio_word = [], []
    for wi, w in enumerate(words):
        for t in tokens(w["text"]):
            audio_toks.append(t)
            audio_word.append(wi)

    # Line them up
    sm = SequenceMatcher(None, text_toks, audio_toks, autojunk=False)
    match_of = [None] * len(text_toks)          # text token -> whisper word index
    for blk in sm.get_matching_blocks():
        for k in range(blk.size):
            match_of[blk.a + k] = audio_word[blk.b + k]

    # Per sentence: the matched Whisper words, in order
    hits, total = {}, {}
    for ti, si in enumerate(text_sent):
        total[si] = total.get(si, 0) + 1
        if match_of[ti] is not None:
            hits.setdefault(si, []).append(match_of[ti])

    # Keep the largest group of matches that are close together in time
    first, last, matched = {}, {}, {}
    for si, ws in hits.items():
        groups = [[ws[0]]]
        for a, b in zip(ws, ws[1:]):
            if words[b]["start"] - words[a]["end"] > STRAY_GAP:
                groups.append([])
            groups[-1].append(b)
        best = max(groups, key=len)
        first[si], last[si], matched[si] = best[0], best[-1], len(best)

    timed = []
    for si, s in enumerate(sentences):
        if si in first:
            s["start"] = words[first[si]]["start"]
            s["end"] = words[last[si]]["end"]
            timed.append(si)
        else:
            s["start"] = s["end"] = -1

    # Unmatched sentences between two timed ones share the time between them
    filled = 0
    for a, b in zip(timed, timed[1:]):
        missing = list(range(a + 1, b))
        lo, hi = sentences[a]["end"], sentences[b]["start"]
        if missing and hi > lo:
            step = (hi - lo) / len(missing)
            for k, si in enumerate(missing):
                sentences[si]["start"] = round(lo + k * step, 2)
                sentences[si]["end"] = round(lo + (k + 1) * step, 2)
                filled += 1
    timed = [si for si, s in enumerate(sentences) if s["start"] != -1]

    # Close the small gaps: each sentence runs until the next timed sentence
    # starts, so the highlight doesn't flicker off between sentences. Gaps
    # longer than 3 seconds (a pause, an image, a skipped passage) are left alone.
    for a, b in zip(timed, timed[1:]):
        gap = sentences[b]["start"] - sentences[a]["end"]
        if 0 < gap <= 3:
            sentences[a]["end"] = sentences[b]["start"]

    SENTENCES_JSON.write_text(json.dumps(sentences, ensure_ascii=False, indent=2) + "\n", encoding="utf8")

    # Report
    with REPORT_CSV.open("w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["idx", "id", "match_pct", "flag", "start", "end", "text", "whisper_heard"])
        for si, s in enumerate(sentences):
            pct = matched.get(si, 0) / total[si] if total.get(si) else 0
            heard = ""
            if si in first:
                heard = " ".join(x["text"] for x in words[first[si]:last[si] + 1])
            flag = ("FILLED" if s["start"] != -1 else "NONE") if si not in first else ("LOW" if pct < LOW_MATCH else "")
            w.writerow([si, s["id"], f"{pct:.0%}", flag, s["start"], s["end"], s["text"], heard])

    n = len(sentences)
    none = sum(1 for s in sentences if s["start"] == -1)
    low = sum(1 for si in first if matched[si] / total[si] < LOW_MATCH)
    out_of_order = sum(1 for a, b in zip(timed, timed[1:]) if sentences[b]["start"] < sentences[a]["start"])
    print(f"Aligned {n} sentences to {len(words)} Whisper words")
    print(f"  words matched: {sum(matched.values())} of {len(text_toks)} ({sum(matched.values()) / len(text_toks):.1%})")
    print(f"  sentences timed: {n - none} (incl. {filled} filled from neighbors)   low match (<{LOW_MATCH:.0%}): {low}   untimed: {none}")
    print(f"  out-of-order starts: {out_of_order}")
    print(f"Review: {REPORT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
