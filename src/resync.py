#!/usr/bin/env python3
"""
resync.py — Phase 0 of the audio re-sync plan.

Parses all gm-cue spans from public/index.html, fuzzy-matches each one to the
best sentence in TheGenesisMelody_sentences.json, and writes src/resync_map.csv
with proposed new timestamps and text changes flagged for review.

Cross-references src/The Genesis Melody.txt to flag potential Whisper errors.
"""

import bisect
import csv
import json
import re
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

ROOT           = Path(__file__).parent.parent
HTML_FILE      = ROOT / "public" / "index.html"
SENTENCES_FILE = ROOT / "src" / "TheGenesisMelody_sentences.json"
TXT_FILE       = ROOT / "src" / "The Genesis Melody.txt"
OUTPUT_CSV     = ROOT / "src" / "resync_map.csv"

# Old and new audio end times (seconds) — used for time-proportional seeding
OLD_MAX = 4660
NEW_MAX = 4893

# Classes that indicate a scripture passage element — spans inside these are frozen
SCRIPTURE_PARENT_CLASSES = {"c20", "c24", "c81"}


# ── Normalisation ─────────────────────────────────────────────────────────

def normalize(text):
    text = text.lower()
    text = re.sub(r"[^\w\s]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def similarity(a, b):
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


# ── HTML parser ───────────────────────────────────────────────────────────

class CueSpanParser(HTMLParser):
    """Extract every gm-cue span with its timestamps, text, and scripture flag."""

    def __init__(self):
        super().__init__()
        self._in_scripture = False   # inside a scripture block element
        self._in_cue       = False
        self._cue_depth    = 0
        self._cue_data     = None
        self.spans         = []

    def handle_starttag(self, tag, attrs):
        attrs_d = dict(attrs)
        classes = set(attrs_d.get("class", "").split())

        # Detect scripture container elements
        if tag in ("p", "li", "td") and classes & SCRIPTURE_PARENT_CLASSES:
            self._in_scripture = True

        if tag == "span" and "gm-cue" in classes:
            t_start = attrs_d.get("data-t-start")
            t_end   = attrs_d.get("data-t-end")
            if t_start is not None and t_end is not None:
                if not self._in_cue:
                    self._in_cue    = True
                    self._cue_depth = 1
                    self._cue_data  = {
                        "old_start":    int(t_start),
                        "old_end":      int(t_end),
                        "text_parts":   [],
                        "is_scripture": self._in_scripture,
                        "html_line":    self.getpos()[0],
                    }
                else:
                    self._cue_depth += 1
                return

        if self._in_cue:
            self._cue_depth += 1

    def handle_endtag(self, tag):
        if self._in_cue:
            self._cue_depth -= 1
            if self._cue_depth == 0:
                raw = " ".join(self._cue_data["text_parts"])
                raw = re.sub(r"\s+", " ", raw).strip()
                self._cue_data["html_text"] = raw
                self.spans.append(self._cue_data)
                self._in_cue   = False
                self._cue_data = None

        # Reset scripture flag when the container closes
        if tag in ("p", "li", "td"):
            self._in_scripture = False

    def handle_data(self, data):
        if self._in_cue:
            self._cue_data["text_parts"].append(data)


def parse_cue_spans(html_path):
    parser = CueSpanParser()
    parser.feed(html_path.read_text(encoding="utf-8"))
    return parser.spans


# ── .txt file helpers ─────────────────────────────────────────────────────

def load_txt_lines(txt_path):
    return [l.strip() for l in txt_path.read_text(encoding="utf-8").splitlines() if l.strip()]


def best_txt_match(text, txt_lines):
    best_score, best_line = 0.0, None
    for line in txt_lines:
        s = similarity(text, line)
        if s > best_score:
            best_score, best_line = s, line
    if best_score >= 0.65:
        return best_line, best_score
    return None, best_score


# ── Sentence matching ─────────────────────────────────────────────────────

def time_hint(old_start, sentences):
    """
    Estimate the index into `sentences` that corresponds to `old_start`
    by proportional scaling, then binary-search to the nearest sentence.
    """
    estimated_new_time = old_start * (NEW_MAX / OLD_MAX)
    starts = [s["start"] for s in sentences]
    idx = bisect.bisect_left(starts, estimated_new_time)
    return max(0, min(idx, len(sentences) - 1))


def find_best_sentence(span_text, sentences, time_idx):
    """
    Find the best-matching sentence for a cue span.

    Uses a window centred on `time_idx` (the time-proportional estimate).
    Also tries pairs of adjacent sentences (span may straddle a boundary).

    Returns (sentence_index, score, sentence_dict).
    """
    window = 60
    lo = max(0, time_idx - window // 2)
    hi = min(len(sentences), time_idx + window // 2)

    best_score, best_idx = 0.0, time_idx

    for i in range(lo, hi):
        s = similarity(span_text, sentences[i]["text"])
        if s > best_score:
            best_score, best_idx = s, i

    # Try adjacent pairs
    for i in range(lo, hi - 1):
        combined = sentences[i]["text"] + " " + sentences[i + 1]["text"]
        s = similarity(span_text, combined)
        if s > best_score:
            best_score, best_idx = s, i

    # If still poor, widen the window
    if best_score < 0.50:
        lo2 = max(0, time_idx - 120)
        hi2 = min(len(sentences), time_idx + 120)
        for i in range(lo2, hi2):
            s = similarity(span_text, sentences[i]["text"])
            if s > best_score:
                best_score, best_idx = s, i
        for i in range(lo2, hi2 - 1):
            combined = sentences[i]["text"] + " " + sentences[i + 1]["text"]
            s = similarity(span_text, combined)
            if s > best_score:
                best_score, best_idx = s, i

    return best_idx, best_score, sentences[best_idx]


# ── Flag logic ────────────────────────────────────────────────────────────

def compute_flag(score, span_text, new_text, is_scripture, is_heading, txt_score):
    if is_heading:
        return "HEADING_SKIP"

    if is_scripture:
        # For scripture, only timestamp matters; text is frozen regardless
        if score < 0.40:
            return "SCRIPTURE_LOW_CONF"
        return "SCRIPTURE_OK"

    if score < 0.60:
        return "MANUAL_REVIEW"
    if score < 0.85:
        flag = "LOW_CONFIDENCE"
    else:
        # High confidence — check if text actually differs
        text_sim = similarity(span_text, new_text)
        flag = "TEXT_CHANGED" if text_sim < 0.97 else "OK"

    # Potential Whisper error: .txt file doesn't agree with sentences file
    if txt_score is not None and txt_score < 0.70:
        flag += "+WHISPER_CHECK"

    return flag


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("Loading files…")
    spans     = parse_cue_spans(HTML_FILE)
    sentences = json.loads(SENTENCES_FILE.read_text(encoding="utf-8"))
    txt_lines = load_txt_lines(TXT_FILE)

    print(f"  {len(spans)} gm-cue spans in HTML")
    print(f"  {len(sentences)} sentences in new file")
    print(f"  {len(txt_lines)} non-empty lines in .txt")
    print()

    rows = []
    counts = {
        "OK": 0, "TEXT_CHANGED": 0, "LOW_CONFIDENCE": 0,
        "MANUAL_REVIEW": 0, "HEADING_SKIP": 0,
        "SCRIPTURE_OK": 0, "SCRIPTURE_LOW_CONF": 0,
        "WHISPER_CHECK": 0,
    }

    for span in spans:
        span_text  = span["html_text"]
        is_heading = len(span_text.split()) <= 4

        # Time-proportional index estimate — independent per span, no drift cascade
        t_idx = time_hint(span["old_start"], sentences)

        best_idx, score, best_sent = find_best_sentence(span_text, sentences, t_idx)

        # Cross-check against .txt
        txt_match, txt_score = best_txt_match(span_text, txt_lines)

        flag = compute_flag(
            score, span_text, best_sent["text"],
            span["is_scripture"], is_heading, txt_score
        )

        # Update counters
        for key in counts:
            if key in flag:
                counts[key] += 1

        rows.append({
            "html_line":    span["html_line"],
            "old_start":    span["old_start"],
            "old_end":      span["old_end"],
            "html_text":    span_text,
            "new_start":    best_sent["start"],
            "new_end":      best_sent["end"],
            "new_text":     best_sent["text"],
            "match_score":  f"{score:.3f}",
            "txt_match":    txt_match or "",
            "txt_score":    f"{txt_score:.3f}",
            "is_scripture": "YES" if span["is_scripture"] else "",
            "flag":         flag,
            "notes":        "",
        })

    # Write CSV
    fieldnames = [
        "html_line", "old_start", "old_end", "html_text",
        "new_start", "new_end", "new_text",
        "match_score", "txt_match", "txt_score",
        "is_scripture", "flag", "notes",
    ]
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Written → {OUTPUT_CSV}")
    print()
    print("Flag summary:")
    for k, v in counts.items():
        print(f"  {k:<22} {v}")
    print()
    print("Next: open src/resync_map.csv, review MANUAL_REVIEW + WHISPER_CHECK rows,")
    print("then start Phase 1 with the user.")


if __name__ == "__main__":
    main()
