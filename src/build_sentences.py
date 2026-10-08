#!/usr/bin/env python3
"""
build_sentences.py

Rebuilds src/TheGenesisMelody_sentences.json from a Google Doc
"Web page (.html, zipped)" export. Does NOT touch public/index.html.

Usage:
    python3 src/build_sentences.py "src/gdoc-export/The Genesis Melody/TheGenesisMelody.html"

What it does:
1. Walks the export in document order and turns it into sentences:
   - headings -> one sentence each
   - prose paragraphs -> split on sentence punctuation
   - scripture lines (one <p> per line in the export) -> one entry per line,
     matching how index.html gives each scripture line its own gm-cue span
   - melody table rows -> one label sentence ("Melody Cycle 2 Division, Genesis 9:22-11:5")
     followed by the sentences of the notes cell
   - skips the Table of Contents, the site URL, footnote markers, and the Bibliography
2. Lines the new sentences up against the current sentences.json in order
   (like a text diff). Unchanged and lightly edited sentences keep their id
   and start/end; new sentences get a fresh id and start/end = -1.
4. Writes a review CSV (src/build_sentences_report.csv) and prints a summary.

Standard library only.
"""

import csv
import html
import json
import re
import secrets
import sys
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_JSON = ROOT / "src" / "TheGenesisMelody_sentences.json"
REPORT_CSV = ROOT / "src" / "build_sentences_report.csv"

REUSE_THRESHOLD = 0.75
BLOCK_TAGS = {"p", "h1", "h2", "h3", "h4", "h5", "h6", "li"}


# ---------------------------------------------------------------------------
# Parse the Google Doc export into ordered blocks
# ---------------------------------------------------------------------------

def superscript_classes(doc: str) -> set:
    """CSS classes the export uses for vertical-align:super (footnote markers)."""
    css = doc[: doc.find("</style>")]
    return set(re.findall(r"\.(c\d+)\{[^}]*vertical-align:super", css))


class ExportParser(HTMLParser):
    """Collects text blocks in document order, noting table/row/cell position."""

    def __init__(self, skip_classes):
        super().__init__(convert_charrefs=True)
        self.skip_classes = skip_classes
        self.blocks = []          # dicts: tag, text, table, row, col
        self.span_stack = []      # True if that span is skipped
        self.cur = None
        self.table = -1
        self.row = -1
        self.col = -1
        self.in_table = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "table":
            self.in_table += 1
            self.table += 1
            self.row = -1
        elif tag == "tr":
            self.row += 1
            self.col = -1
        elif tag == "td":
            self.col += 1
        elif tag == "span":
            classes = set((a.get("class") or "").split())
            skip = bool(classes & self.skip_classes)
            if skip and self.cur is not None:
                self.cur["text"] += " "   # keep "remember⁸ us" from becoming "rememberus"
            self.span_stack.append(skip)
        elif tag == "br" and self.cur is not None:
            self.cur["text"] += " "
        elif tag in BLOCK_TAGS:
            self.cur = {
                "tag": tag,
                "text": "",
                "table": self.table if self.in_table else None,
                "row": self.row if self.in_table else None,
                "col": self.col if self.in_table else None,
            }

    def handle_endtag(self, tag):
        if tag == "table":
            self.in_table -= 1
        elif tag == "span":
            if self.span_stack:
                self.span_stack.pop()
        elif tag in BLOCK_TAGS and self.cur is not None:
            self.cur["text"] = clean(self.cur["text"])
            if self.cur["text"]:
                self.blocks.append(self.cur)
            self.cur = None

    def handle_data(self, data):
        if self.cur is None or any(self.span_stack):
            return
        self.cur["text"] += data


def clean(text: str) -> str:
    text = text.replace(" ", " ").replace("​", "")
    return re.sub(r"\s+", " ", text).strip()


# ---------------------------------------------------------------------------
# Sentence splitting
# ---------------------------------------------------------------------------

# Split after . ! ? or … (plus any closing quotes/brackets) when followed by
# whitespace and something that starts a new sentence. An opening ( or [ does not
# start a new sentence: “Get yourself going…” (lekh lekha) stays together.
SPLIT_RE = re.compile(r"(?<=[.!?…])[\"”’')\]]*\s+(?=[A-Z“\"‘'0-9])")


def split_sentences(text: str) -> list:
    parts, start = [], 0
    for m in SPLIT_RE.finditer(text):
        piece = text[start:m.start() + len(m.group(0).rstrip())].strip()
        # Don't split after "i.e." / "e.g."
        if re.search(r"\b(i\.e|e\.g)\.$", piece):
            continue
        # Don't split inside parentheses: "(Take a pause… selah. Perfect Father Son alignment)"
        if piece.count("(") > piece.count(")"):
            continue
        parts.append(piece)
        start = m.end()
    tail = text[start:].strip()
    if tail:
        parts.append(tail)
    # re-glue any pieces that were held back by the i.e./e.g. rule, and keep a
    # repeated call together: “Avraham! Avraham!”
    out = []
    word = lambda s: re.sub(r"\W", "", s).lower()
    for p in parts:
        if out and (re.search(r"\b(i\.e|e\.g)\.$", out[-1]) or word(p) == word(out[-1])):
            out[-1] += " " + p
        else:
            out.append(p)
    return out


def split_list_item(text: str) -> list:
    """'Melody Observations - A detailed look...' -> title, then the description."""
    m = re.match(r"^(.{3,60}?) - (.+)$", text)
    if m:
        return [m.group(1)] + split_sentences(m.group(2))
    return split_sentences(text)


# ---------------------------------------------------------------------------
# Blocks -> ordered sentence list
# ---------------------------------------------------------------------------

def blocks_to_sentences(blocks: list) -> list:
    """Returns [{text, section}] in document order."""
    out = []
    section = ""
    skipping = None   # "toc" | "bib" | None

    # Group table blocks by (table, row) so each row can be handled together.
    i = 0
    while i < len(blocks):
        b = blocks[i]
        text = b["text"]

        if text == "Bibliography" and skipping != "toc":
            skipping = "bib"   # runs to the end of the document
        elif b["tag"].startswith("h"):
            if skipping == "toc":
                skipping = None
            if skipping is None:
                section = text
        elif text == "Table of Contents":
            skipping = "toc"

        if skipping:
            i += 1
            continue

        if b["table"] is not None:
            # Collect the whole row
            t, r = b["table"], b["row"]
            row = []
            while i < len(blocks) and blocks[i]["table"] == t and blocks[i]["row"] == r:
                row.append(blocks[i])
                i += 1
            out.extend({"text": s, "section": section} for s in row_to_sentences(row))
            continue

        if re.match(r"^https?://\S+$", text):
            pass
        elif b["tag"].startswith("h"):
            out.append({"text": text, "section": section})
        elif b["tag"] == "li":
            out.extend({"text": s, "section": section} for s in split_list_item(text))
        else:
            out.extend({"text": s, "section": section} for s in split_sentences(text))
        i += 1
    return out


def row_to_sentences(row: list) -> list:
    cols = {}
    for b in row:
        cols.setdefault(b["col"], []).append(b["text"])
    ncols = max(cols) + 1 if cols else 0
    first = " ".join(cols.get(0, []))

    # Header rows ("Name | Chapters | Distinctive Notes")
    if first in ("Name", "Chapters"):
        return []

    sentences = []
    if ncols >= 4:
        # Course tiles row (Heaven and Earth, Adam to Noah, ...): one sentence per
        # caption, so each course name highlights in turn as it's read
        return [t for c in sorted(cols) for t in cols[c]]
    if ncols >= 3:
        # Name cell and Chapters cell are separate sentences, since a highlight
        # span can't cross table cells ("Melody Cycle 1 Creation", "Genesis 1:1 - 2:3 plus 2:4-15")
        sentences.extend(" ".join(cols[c]) for c in range(ncols - 1) if cols.get(c))
        label = ""
        notes = cols.get(ncols - 1, [])
    elif ncols == 2:
        label = first
        notes = cols.get(1, [])
    else:
        # Single-column or link-only rows (e.g. course image captions): read as-is
        return [t for c in sorted(cols) for t in cols[c]]

    if label:
        sentences.append(label)
    for para in notes:
        sentences.extend(split_sentences(para))
    return sentences


# ---------------------------------------------------------------------------
# Carry ids (and timings) over from the current sentences.json
# ---------------------------------------------------------------------------

def norm(text: str) -> str:
    text = html.unescape(text).lower()
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    text = re.sub(r"[^a-z0-9' ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def similarity(a: str, b: str) -> float:
    sm = SequenceMatcher(None, a, b, autojunk=False)
    if sm.real_quick_ratio() < REUSE_THRESHOLD or sm.quick_ratio() < REUSE_THRESHOLD:
        return 0.0
    return sm.ratio()


def align_block(old: list, new: list) -> list:
    """In-order fuzzy pairing inside one changed stretch: picks the set of
    (old, new) pairs with the highest total similarity that never cross."""
    n, m = len(old), len(new)
    score = [[similarity(norm(o["text"]), norm(s["text"])) for s in new] for o in old]
    best = [[0.0] * (m + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(m - 1, -1, -1):
            pair = score[i][j] + best[i + 1][j + 1] if score[i][j] >= REUSE_THRESHOLD else 0.0
            best[i][j] = max(pair, best[i + 1][j], best[i][j + 1])
    pairs, i, j = [], 0, 0
    while i < n and j < m:
        if score[i][j] >= REUSE_THRESHOLD and best[i][j] == score[i][j] + best[i + 1][j + 1]:
            pairs.append((i, j, score[i][j]))
            i, j = i + 1, j + 1
        elif best[i][j] == best[i + 1][j]:
            i += 1
        else:
            j += 1
    return pairs


def assign_ids(new: list, old: list) -> None:
    """Line the old and new sentence lists up in order, like a text diff.
    Unchanged sentences keep their id and timings in place, so identical
    sentences (e.g. a heading and a list item with the same words) can't swap.
    Edited sentences are fuzzy-matched in order inside each changed stretch."""
    def carry(s, o, source, score):
        s.update(id=o["id"], start=o.get("start", -1), end=o.get("end", -1),
                 source=source, score=round(score, 3), matched=o["text"])

    sm = SequenceMatcher(None, [norm(o["text"]) for o in old],
                         [norm(s["text"]) for s in new], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for o, s in zip(old[i1:i2], new[j1:j2]):
                carry(s, o, "same", 1.0)
        elif op == "replace":
            for i, j, r in align_block(old[i1:i2], new[j1:j2]):
                carry(new[j1 + j], old[i1 + i], "edited", r)

    used = {s["id"] for s in new if "id" in s}
    for s in new:
        if "id" not in s:
            s.update(id=fresh_id(used), start=-1, end=-1, source="new", score="", matched="")


def fresh_id(used: set) -> str:
    while True:
        sid = secrets.token_hex(6)
        if sid not in used:
            used.add(sid)
            return sid


# ---------------------------------------------------------------------------

def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    export = Path(sys.argv[1])
    doc = export.read_text(encoding="utf8")

    parser = ExportParser(superscript_classes(doc))
    parser.feed(doc[doc.find("<body"):])
    new = blocks_to_sentences(parser.blocks)

    old = json.loads(SENTENCES_JSON.read_text(encoding="utf8")) if SENTENCES_JSON.exists() else []
    assign_ids(new, old)

    SENTENCES_JSON.write_text(
        json.dumps(
            [{"id": s["id"], "start": s["start"], "end": s["end"], "text": s["text"]} for s in new],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf8",
    )

    with REPORT_CSV.open("w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["idx", "section", "id", "source", "score", "text", "matched_old_text"])
        for k, s in enumerate(new):
            w.writerow([k, s["section"], s["id"], s["source"], s["score"], s["text"], s["matched"]])

    count = lambda src: sum(s["source"] == src for s in new)
    print(f"Wrote {len(new)} sentences to {SENTENCES_JSON.relative_to(ROOT)}")
    print(f"  unchanged: {count('same')}   edited (id kept): {count('edited')}   new: {count('new')}")
    print(f"  old ids dropped: {len({o['id'] for o in old} - {s['id'] for s in new})} of {len(old)}")
    print(f"Review: {REPORT_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
