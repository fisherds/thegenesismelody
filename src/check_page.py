#!/usr/bin/env python3
"""
check_page.py

Checks that public/index.html matches src/TheGenesisMelody_sentences.json:
- every sentence id appears on the page exactly once, as a gm-cue span
- the page has no ids that aren't in sentences.json
- they appear in the same order
- each span's visible text matches the sentence text (ignoring punctuation,
  capitals, line breaks and footnote numbers)

Run from the repo root (standard library only):
    python3 src/check_page.py
Exits with code 1 if anything is off, and prints what and where.
"""

import json
import re
import sys
from collections import Counter
from html import unescape
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_JSON = ROOT / "src" / "TheGenesisMelody_sentences.json"
INDEX_HTML = ROOT / "public" / "index.html"


class Cues(HTMLParser):
    """Collects (id, visible text) for each gm-cue span, in page order."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth, self.cue_depth, self.cur, self.out = 0, None, None, []
        self.in_footnote = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "br" and self.cur:
            self.cur[1] += " "
        if tag != "span":
            return
        self.depth += 1
        classes = (a.get("class") or "").split()
        if "c64" in classes:          # footnote number spans
            self.in_footnote = self.depth
        if "gm-cue" in classes:
            self.cue_depth, self.cur = self.depth, [a.get("data-sentence-id"), ""]

    def handle_endtag(self, tag):
        if tag != "span":
            return
        if self.in_footnote == self.depth:
            self.in_footnote = 0
        if self.cue_depth == self.depth and self.cur:
            self.out.append(tuple(self.cur))
            self.cur = self.cue_depth = None
        self.depth -= 1

    def handle_data(self, data):
        if self.cur and not self.in_footnote:
            self.cur[1] += data


def norm(text: str) -> str:
    text = unescape(text).lower().replace("’", "'").replace("'", "")
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", text)).strip()


def main():
    sentences = json.loads(SENTENCES_JSON.read_text(encoding="utf8"))
    parser = Cues()
    parser.feed(INDEX_HTML.read_text(encoding="utf8"))
    page = parser.out

    json_ids = [s["id"] for s in sentences]
    page_ids = [i for i, _ in page]
    text_of = {s["id"]: s["text"] for s in sentences}
    problems = 0

    dupes = [i for i, n in Counter(page_ids).items() if n > 1]
    missing = [i for i in json_ids if i not in set(page_ids)]
    extra = [i for i in page_ids if i not in text_of]
    for label, ids in [("on the page more than once", dupes),
                       ("in sentences.json but not on the page", missing),
                       ("on the page but not in sentences.json", extra)]:
        if ids:
            problems += len(ids)
            print(f"{len(ids)} id(s) {label}:")
            for i in ids[:20]:
                print(f"   {i}  {text_of.get(i, '')[:80]}")

    if not dupes and not missing and not extra and page_ids != json_ids:
        problems += 1
        k = next(n for n, (a, b) in enumerate(zip(page_ids, json_ids)) if a != b)
        print(f"Order differs starting at sentence {k}: page has {text_of[page_ids[k]][:60]!r}, "
              f"sentences.json has {text_of[json_ids[k]][:60]!r}")

    for i, t in page:
        if i in text_of and norm(t) != norm(text_of[i]):
            problems += 1
            print(f"Text differs for {i}:\n   page: {norm(t)[:100]}\n   json: {norm(text_of[i])[:100]}")

    timed = sum(1 for s in sentences if s["start"] != -1)
    print(f"{len(page_ids)} sentences on the page, {len(json_ids)} in sentences.json, {timed} timed.")
    print("OK: the page matches sentences.json." if not problems else f"{problems} problem(s) found.")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
