#!/usr/bin/env python3
"""
annotate-audio.py

Reads TheGenesisMelody_segments.json (Whisper sentence segments) and
public/index.html, fuzzy-matches each segment to a block-level element,
then injects data-t-start / data-t-end attributes.

Outputs:
  src/index-annotated.html  — annotated copy (review before replacing index.html)
  src/audio-cues.json       — flat list of {start, end, element_index} for reference

Usage:
  python3 src/annotate-audio.py
"""

import json, re, difflib, os
from bs4 import BeautifulSoup

# ── Config ──────────────────────────────────────────────────────────────────
BASE      = os.path.dirname(os.path.abspath(__file__))
HTML_IN   = os.path.join(BASE, '..', 'public', 'index.html')
SEGS_IN   = os.path.join(BASE, 'TheGenesisMelody_segments.json')
HTML_OUT  = os.path.join(BASE, 'index-annotated.html')
CUES_OUT  = os.path.join(BASE, 'audio-cues.json')

# How far ahead (in block count) to search for a segment match
WINDOW = 25
# Minimum similarity ratio to accept a match
MIN_RATIO = 0.25

# ── Text normalisation ───────────────────────────────────────────────────────

def normalise(text):
    text = text.lower()
    # Collapse dashes/hyphens and colons used in references like "11:27" → space
    text = re.sub(r'[-–—:]+', ' ', text)
    # Strip all non-alphanumeric (keep spaces)
    text = re.sub(r'[^a-z0-9\s]', '', text)
    # Collapse whitespace
    return re.sub(r'\s+', ' ', text).strip()

# ── Load data ────────────────────────────────────────────────────────────────

with open(SEGS_IN, encoding='utf-8') as f:
    segments = json.load(f)

with open(HTML_IN, encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'lxml')

# ── Collect block elements from <main> ──────────────────────────────────────
# Include td so scripture table cells are reachable

main = soup.find('main')
ALL_BLOCK_TAGS = {'p', 'h1', 'h2', 'li', 'td'}

# Skip elements inside <script> or <style>
def is_content_block(tag):
    for parent in tag.parents:
        if parent.name in ('script', 'style', 'audio'):
            return False
    return True

blocks = [t for t in main.find_all(ALL_BLOCK_TAGS) if is_content_block(t)]

# Normalised text for each block (used for matching)
block_norms = [normalise(b.get_text(' ', strip=True)) for b in blocks]

print(f'Loaded {len(segments)} segments, {len(blocks)} blocks')

# ── Sequential fuzzy matching ─────────────────────────────────────────────────
#
# Anchor each search window by the segment's expected block position,
# derived from (segment_time / total_audio_time) * num_blocks.
# This prevents the cursor from jumping to a late section (e.g. bibliography)
# and getting stuck there for the rest of the audio.

# block_index → list of segments matched to it
block_to_segs = {}

max_time = max(s['end'] for s in segments)
cursor   = 0          # hard lower bound — never go backwards past a confirmed match

for seg in segments:
    seg_norm = normalise(seg['text'])
    if not seg_norm or len(seg_norm) < 4:
        continue

    # Expected block index based on audio position
    expected = int(seg['start'] / max_time * len(blocks))

    # Search window centred on expected position, but never before cursor
    window_start = max(cursor, expected - WINDOW)
    window_end   = min(len(blocks), expected + WINDOW)

    best_ratio = 0.0
    best_idx   = expected   # default to expected position on no match

    for i in range(window_start, window_end):
        bn = block_norms[i]
        if not bn:
            continue

        # Fast path: direct substring containment
        if seg_norm in bn:
            best_ratio = 1.0
            best_idx   = i
            break

        ratio = difflib.SequenceMatcher(None, seg_norm, bn, autojunk=False).ratio()
        if ratio > best_ratio:
            best_ratio = ratio
            best_idx   = i

    if best_ratio >= MIN_RATIO:
        block_to_segs.setdefault(best_idx, []).append(seg)
        # Advance cursor only when we have a confident forward match
        if best_idx > cursor and best_ratio >= 0.4:
            cursor = best_idx

print(f'Matched segments to {len(block_to_segs)} distinct blocks')

# ── Annotate HTML elements ────────────────────────────────────────────────────

cues_out = []

for idx, segs in sorted(block_to_segs.items()):
    t_start = min(s['start'] for s in segs)
    t_end   = max(s['end']   for s in segs)
    blocks[idx]['data-t-start'] = str(t_start)
    blocks[idx]['data-t-end']   = str(t_end)
    cues_out.append({
        'start':         t_start,
        'end':           t_end,
        'block_index':   idx,
        'block_tag':     blocks[idx].name,
        'preview':       blocks[idx].get_text(' ', strip=True)[:80],
    })

# ── Write outputs ─────────────────────────────────────────────────────────────

with open(HTML_OUT, 'w', encoding='utf-8') as f:
    f.write(str(soup))
print(f'Wrote annotated HTML → {HTML_OUT}')

cues_out.sort(key=lambda c: c['start'])
with open(CUES_OUT, 'w', encoding='utf-8') as f:
    json.dump(cues_out, f, indent=2, ensure_ascii=False)
print(f'Wrote audio cues     → {CUES_OUT}')

# ── Quick sanity report ───────────────────────────────────────────────────────

unmatched = [i for i in range(len(blocks))
             if block_norms[i] and i not in block_to_segs]
print(f'\nBlocks with no segment match: {len(unmatched)}')
if unmatched[:10]:
    print('First few unmatched blocks:')
    for i in unmatched[:10]:
        print(f'  [{i}] <{blocks[i].name}> {block_norms[i][:70]}')

print('\nFirst 10 cues:')
for c in cues_out[:10]:
    print(f'  {c["start"]:6.1f}s → {c["end"]:6.1f}s  <{c["block_tag"]}> {c["preview"]}')
