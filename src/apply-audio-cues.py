#!/usr/bin/env python3
"""
apply-audio-cues.py

Injects data-t-start / data-t-end into public/index.html using the
block_index values from src/audio-cues.json.

Identifies each target element by its sequential position among all
block-level elements inside <main> — the same ordering used by
annotate-audio.py — so there is no ambiguity between elements that
share the same CSS class.

Usage:
    python3 src/apply-audio-cues.py
"""

import json, os, re
from bs4 import BeautifulSoup

BASE     = os.path.dirname(os.path.abspath(__file__))
HTML_IN  = os.path.join(BASE, '..', 'public', 'index.html')
CUES_IN  = os.path.join(BASE, 'audio-cues.json')
HTML_OUT = os.path.join(BASE, '..', 'public', 'index.html')

ALL_BLOCK_TAGS = {'p', 'h1', 'h2', 'li', 'td'}

def is_content_block(tag):
    for parent in tag.parents:
        if parent.name in ('script', 'style', 'audio'):
            return False
    return True

# ── Load cues ────────────────────────────────────────────────────────────────
with open(CUES_IN) as f:
    cues_list = json.load(f)

# Collapse multiple cues per block → widest time span
cue_map = {}
for cue in cues_list:
    idx = cue['block_index']
    if idx in cue_map:
        s, e = cue_map[idx]
        cue_map[idx] = (min(s, cue['start']), max(e, cue['end']))
    else:
        cue_map[idx] = (cue['start'], cue['end'])

print(f'Loaded {len(cue_map)} unique block annotations')

# ── Parse HTML ───────────────────────────────────────────────────────────────
with open(HTML_IN, encoding='utf-8') as f:
    raw = f.read()

# Guard: make sure there are no stale data-t-* attributes
if 'data-t-start' in raw:
    print('WARNING: stale data-t-start found — stripping before re-injection')
    raw = re.sub(r'\s+data-t-(?:start|end)="[^"]*"', '', raw)

soup = BeautifulSoup(raw, 'html.parser')
main = soup.find('main')
blocks = [t for t in main.find_all(ALL_BLOCK_TAGS) if is_content_block(t)]
print(f'Found {len(blocks)} block elements in <main>')

# ── Inject attributes at the correct sequential index ────────────────────────
injected = 0
for idx, (t_start, t_end) in sorted(cue_map.items()):
    if idx >= len(blocks):
        print(f'  SKIP: block_index {idx} out of range')
        continue
    el = blocks[idx]
    el['data-t-start'] = str(t_start)
    el['data-t-end']   = str(t_end)
    injected += 1

print(f'Injected attributes into {injected} elements')

# ── Serialize back to HTML ────────────────────────────────────────────────────
# html.parser's formatter preserves attribute quoting and entity encoding
# better than lxml for round-trips on Google Doc HTML.
output = str(soup)

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(output)

# Verify
verify_count = output.count('data-t-start=')
print(f'Verified: {verify_count} data-t-start attributes in output')
if verify_count != injected:
    print('  WARNING: count mismatch — check for duplicates')
