#!/usr/bin/env python3
"""
apply_timings.py

Step 5: copy start/end from src/TheGenesisMelody_sentences.json onto the page.

- Every <span class="gm-cue" data-sentence-id="..."> in public/index.html gets
  data-t-start / data-t-end from the sentence with the same id.
- Leftover data-t-start / data-t-end on other elements (paragraphs, table cells)
  are removed. Only gm-cue spans are read by public/scripts/audio-highlight.js.
- GM_SECTIONS (the audio player's section jump points, in the inline <script>)
  gets each section's start: the start of the first timed cue at or after that
  section's heading.

Run from the repo root after align_sentences.py (standard library only):
    python3 src/apply_timings.py
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_JSON = ROOT / "src" / "TheGenesisMelody_sentences.json"
INDEX_HTML = ROOT / "public" / "index.html"

CUE_RE = re.compile(r'<span class="gm-cue" data-sentence-id="([^"]+)" data-t-end="[^"]*" data-t-start="[^"]*">')


def fmt(t) -> str:
    """-1 stays -1; times are written with up to 2 decimals and no trailing zeros."""
    if t == -1:
        return "-1"
    return f"{t:.2f}".rstrip("0").rstrip(".")


def main():
    sentences = {s["id"]: s for s in json.loads(SENTENCES_JSON.read_text(encoding="utf8"))}
    html = INDEX_HTML.read_text(encoding="utf8")

    # 1. Cue timings
    missing = []

    def set_cue(m):
        sid = m.group(1)
        s = sentences.get(sid)
        if s is None:
            missing.append(sid)
            return m.group(0)
        return f'<span class="gm-cue" data-sentence-id="{sid}" data-t-end="{fmt(s["end"])}" data-t-start="{fmt(s["start"])}">'

    html, cues = CUE_RE.subn(set_cue, html)

    # 2. Remove stale timings from everything that isn't a gm-cue span
    stale = 0

    def strip_stale(m):
        nonlocal stale
        tag = m.group(0)
        if 'class="gm-cue"' in tag:
            return tag
        new = re.sub(r' data-t-(?:start|end)="[^"]*"', "", tag)
        stale += new != tag
        return new

    html = re.sub(r"<[a-zA-Z][^>]*\sdata-t-(?:start|end)=\"[^\"]*\"[^>]*>", strip_stale, html)

    # 3. GM_SECTIONS jump points
    timed = []
    for m in re.finditer(r'<span class="gm-cue" data-sentence-id="[^"]+" data-t-end="[^"]*" data-t-start="([^"]*)">', html):
        if m.group(1) != "-1":
            timed.append((m.start(), float(m.group(1))))

    def section_start(section_id):
        pos = html.find(f'id="{section_id}"')
        if pos == -1:
            return None
        for p, t in timed:
            if p >= pos:
                return t
        return timed[-1][1] if timed else None

    updated = []

    def set_section(m):
        sid, before, old = m.group(1), m.group(0), m.group(2)
        t = section_start(sid)
        if t is None:
            return before
        new_val = fmt(int(t * 10) / 10)   # round down to 0.1s so the jump lands just before the heading
        if not updated:
            new_val = "0"   # first section starts at the very beginning, including the spoken title/intro
        updated.append((sid, old, new_val))
        return before.replace(f"start_at: {old}", f"start_at: {new_val}")

    html = re.sub(r"\{ id: '([^']+)',[^}]*?start_at: ([0-9.]+)\s*\}", set_section, html)

    INDEX_HTML.write_text(html, encoding="utf8")

    print(f"Updated {cues} gm-cue spans in {INDEX_HTML.relative_to(ROOT)}")
    if missing:
        print(f"  WARNING: {len(missing)} cue ids not found in sentences.json: {missing[:5]}")
    print(f"  removed stale timings from {stale} other elements")
    print(f"  GM_SECTIONS jump points updated: {len(updated)}")
    for sid, old, new in updated:
        print(f"    {sid:50} {old:>6} -> {new}")


if __name__ == "__main__":
    main()
