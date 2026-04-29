#!/usr/bin/env python3
"""
sync-check.py
Compare "The Genesis Melody.txt" (plain-text Google Doc export) against
TheGenesisMelody.html and produce a CSV of text differences.

Usage:
    python3 sync-check.py
Outputs:
    sync-changes.csv  — review this, then ask Claude to apply approved rows
"""

import re, csv, html, difflib, unicodedata
from html.parser import HTMLParser

# ── Section map: HTML anchor ID → heading text as it appears in the .txt ──
SECTIONS = [
    ('a-quick-foreword',                              'A Quick Foreword'),
    ('introduction-and-motivation',                   'Introduction and Motivation'),
    ('summary',                                       'Summary'),
    ('background',                                    'Background'),
    ('why-study-the-melody',                          'Why Study the Melody'),
    ('structure',                                     'Structure'),
    ('pattern-breakers',                              'Pattern Breakers!'),
    ('melody-observations',                           'Melody Observations'),
    ('genesis-1-7-the-melody-template',               'Genesis 1-7: The Melody Template'),
    ('genesis-1-7-pattern-breakers',                  'Genesis 1-7: Pattern Breakers!'),
    ('genesis-8-11-the-second-round',                 'Genesis 8-11: The Second Round of the Melody'),
    ('genesis-8-11-pattern-breakers',                 'Genesis 8-11: Pattern Breakers!'),
    ('genesis-11-27-cycles-three-to-seven-with-avraham', 'Genesis 11:27-22:19: Cycles Three to Seven with Avraham'),
    ('the-melody-points-to-jesus',                    'The Melody Points to Jesus'),
    ('the-seventh-collapse',                          "The Seventh Collapse: Avraham's Test"),
    ('seeing-the-melody-in-the-new-testament',        'Seeing the Melody in the New Testament'),
    ('beyond-genesis-22',                             'Beyond Genesis 22: After the Sheva Cycle'),
    ('extra-sheva-observations',                      'Extra Sheva Observations'),
    ('your-next-steps',                               'Your Next Steps'),
    ('closing-thoughts',                              'Closing Thoughts'),
    ('a-short-farewell-prayer',                       'A Short Farewell Prayer'),
    ('bibliography',                                  'Bibliography'),
]

SECTION_HEADINGS = {title for _, title in SECTIONS}
SECTION_ID_MAP   = {title: sid for sid, title in SECTIONS}

# ─────────────────────────────────────────────
# Text normalisation
# ─────────────────────────────────────────────

def normalise(text):
    """Decode entities, collapse whitespace, strip footnote markers."""
    # Decode HTML entities
    text = html.unescape(text)
    # Normalise Unicode (curly quotes → straight etc.)
    text = unicodedata.normalize('NFKC', text)
    # Curly quotes → straight
    text = text.replace('‘', "'").replace('’', "'")
    text = text.replace('“', '"').replace('”', '"')
    text = text.replace('—', '--').replace('–', '-')
    text = text.replace('…', '...')
    text = text.replace(' ', ' ')   # non-breaking space
    # Strip comment markers like [a], [b]
    text = re.sub(r'\[[a-z]\]', '', text)
    # Strip bare superscript footnote numbers (digit alone between word chars)
    text = re.sub(r'(?<=\w)(\d+)(?=\s)', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def is_empty(text):
    return not normalise(text)

def is_scripture_like(text):
    """Rough heuristic: short lines starting with a verse number."""
    t = text.strip()
    return bool(re.match(r'^\d+[:.]?\d*\s', t)) or len(t) < 80

# ─────────────────────────────────────────────
# Extract paragraphs from HTML by section
# ─────────────────────────────────────────────

class TextExtractor(HTMLParser):
    """Pull text out of an HTML string, skipping script/style."""
    def __init__(self):
        super().__init__()
        self.text = []
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'audio'):
            self._skip += 1

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'audio') and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        if not self._skip:
            self.text.append(data)

    def get_text(self):
        return ''.join(self.text)


def extract_element_text(html_fragment):
    p = TextExtractor()
    p.feed(html_fragment)
    return normalise(p.get_text())


def extract_html_sections(html_path):
    """
    Returns dict: section_id → list of paragraph strings (normalised).
    Paragraphs inside scripture-block divs are joined into one entry.
    """
    with open(html_path, encoding='utf-8') as f:
        raw = f.read()

    # Work only inside <main ...>...</main>
    main_match = re.search(r'<main\b[^>]*>(.*?)</main>', raw, re.DOTALL)
    if not main_match:
        raise ValueError("Could not find <main> element in HTML")
    main_html = main_match.group(1)

    sections = {sid: [] for sid, _ in SECTIONS}
    current_id = None

    # Split on heading tags that carry our known IDs
    heading_pattern = re.compile(
        r'(<h[12]\b[^>]*\bid="([^"]+)"[^>]*>.*?</h[12]>)', re.DOTALL)

    # Split into chunks: [pre-first-heading, (heading, content), ...]
    parts = re.split(r'(<h[12]\b[^>]*\bid="[^"]+?"[^>]*>.*?</h[12]>)', main_html, flags=re.DOTALL)

    for part in parts:
        # Is this a heading?
        hm = re.match(r'<h[12]\b[^>]*\bid="([^"]+)"', part)
        if hm:
            current_id = hm.group(1)
            continue
        if current_id not in sections:
            continue

        # Extract paragraphs and scripture blocks from this chunk
        # Scripture blocks first (joined as one paragraph)
        chunk = part

        # Handle scripture-block divs: join all their text as one paragraph
        scripture_re = re.compile(r'<div class="scripture-block">(.*?)</div>', re.DOTALL)
        for sm in scripture_re.finditer(chunk):
            text = extract_element_text(sm.group(1))
            if text:
                sections[current_id].append(('[scripture] ' + text))
        chunk = scripture_re.sub('', chunk)

        # Regular paragraphs and list items
        para_re = re.compile(r'<(?:p|li)\b[^>]*>(.*?)</(?:p|li)>', re.DOTALL)
        for pm in para_re.finditer(chunk):
            text = extract_element_text(pm.group(1))
            if text and not is_empty(text):
                sections[current_id].append(text)

    return sections

# ─────────────────────────────────────────────
# Extract paragraphs from .txt by section
# ─────────────────────────────────────────────

def extract_txt_sections(txt_path):
    """
    Returns dict: section_id → list of paragraph strings (normalised).

    Google Doc plain-text export: each paragraph = one line. Blank lines are
    empty paragraphs. We treat each non-blank line as one paragraph.

    TOC skip: the exported file contains an in-doc TOC (lines 12-32 roughly)
    where section headings are listed consecutively. We skip those by ignoring
    heading-only lines that appear before the first real prose under a heading.
    """
    with open(txt_path, encoding='utf-8') as f:
        raw_lines = f.readlines()

    sections   = {sid: [] for sid, _ in SECTIONS}
    current_id = None
    toc_done   = False   # True after we've seen the real first prose paragraph

    for raw_line in raw_lines:
        norm = normalise(raw_line.rstrip('\n'))

        # Skip blank / whitespace-only lines
        if not norm:
            continue

        # Skip preamble lines at the very top (before any heading)
        if current_id is None and not toc_done:
            if (norm.startswith('Note:') or norm.startswith('It works well')
                    or 'The Genesis Melody' in norm):
                continue

        # Is this line a known section heading?
        if norm in SECTION_HEADINGS:
            sid = SECTION_ID_MAP[norm]
            if not toc_done:
                # Could be TOC list entry or real heading.
                # If we've already set current_id to this same section,
                # this is the second (real) occurrence — past the TOC.
                if current_id == sid:
                    toc_done = True
                else:
                    current_id = sid   # tentatively set; may be overwritten by TOC
            else:
                current_id = sid
            continue

        # Regular prose line
        if current_id and toc_done:
            sections[current_id].append(norm)
        elif current_id and not toc_done:
            # First prose we see after the initial heading cluster → TOC is done
            toc_done = True
            sections[current_id].append(norm)

    return sections

# ─────────────────────────────────────────────
# Diff two paragraph lists, return change rows
# ─────────────────────────────────────────────

def diff_sections(section_id, section_name, html_paras, txt_paras):
    """
    Use SequenceMatcher to align paragraphs and find changes.
    Returns list of dicts for CSV rows.
    """
    rows = []

    # Filter out scripture-block entries from diffing (they're hard to compare)
    html_plain = [p for p in html_paras if not p.startswith('[scripture]')]
    txt_plain  = txt_paras  # txt has no such markers

    matcher = difflib.SequenceMatcher(None, html_plain, txt_plain, autojunk=False)

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == 'equal':
            continue
        elif tag == 'replace':
            # Pair up as many as we can
            pairs = list(zip(html_plain[i1:i2], txt_plain[j1:j2]))
            for hp, tp in pairs:
                ratio = difflib.SequenceMatcher(None, hp, tp).ratio()
                if ratio < 0.98:   # ignore near-identical (whitespace etc.)
                    rows.append({
                        'section':     section_name,
                        'section_id':  section_id,
                        'change_type': 'modified',
                        'html_text':   hp,
                        'txt_text':    tp,
                        'similarity':  f'{ratio:.2f}',
                    })
            # Any leftovers on either side
            for hp in html_plain[i1 + len(pairs):i2]:
                rows.append({'section': section_name, 'section_id': section_id,
                             'change_type': 'removed_from_txt', 'html_text': hp, 'txt_text': '', 'similarity': '0.00'})
            for tp in txt_plain[j1 + len(pairs):j2]:
                rows.append({'section': section_name, 'section_id': section_id,
                             'change_type': 'added_in_txt', 'html_text': '', 'txt_text': tp, 'similarity': '0.00'})
        elif tag == 'delete':
            for hp in html_plain[i1:i2]:
                rows.append({'section': section_name, 'section_id': section_id,
                             'change_type': 'removed_from_txt', 'html_text': hp, 'txt_text': '', 'similarity': '0.00'})
        elif tag == 'insert':
            for tp in txt_plain[j1:j2]:
                rows.append({'section': section_name, 'section_id': section_id,
                             'change_type': 'added_in_txt', 'html_text': '', 'txt_text': tp, 'similarity': '0.00'})

    return rows

# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    html_path = os.path.join(base, '..', 'public', 'index.html')
    txt_path  = os.path.join(base, 'The Genesis Melody.txt')
    out_path  = os.path.join(base, 'sync-changes.csv')

    print(f'Reading HTML:  {html_path}')
    html_sections = extract_html_sections(html_path)

    print(f'Reading TXT:   {txt_path}')
    txt_sections  = extract_txt_sections(txt_path)

    all_rows = []
    for sid, title in SECTIONS:
        html_paras = html_sections.get(sid, [])
        txt_paras  = txt_sections.get(sid, [])

        if not html_paras and not txt_paras:
            continue

        rows = diff_sections(sid, title, html_paras, txt_paras)
        all_rows.extend(rows)

        if rows:
            print(f'  [{title}]  {len(rows)} difference(s)')
        else:
            print(f'  [{title}]  ✓ match')

    if not all_rows:
        print('\nNo differences found — HTML and TXT are in sync.')
        return

    fields = ['section', 'section_id', 'change_type', 'similarity', 'html_text', 'txt_text']
    with open(out_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_rows)

    print(f'\nWrote {len(all_rows)} row(s) to {out_path}')
    print('Review the CSV, then share it with Claude to apply approved changes.')

if __name__ == '__main__':
    main()
