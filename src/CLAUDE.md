# Genesis Melody Sync Workflow

## What this folder is

`sync-check.py` diffs a Google Doc plain-text export (`The Genesis Melody.txt`) against `TheGenesisMelody.html` and writes `sync-changes.csv`. The Google Doc is the primary authoring tool; the HTML is the display layer. This script bridges them.

## Sync steps (run after each Google Doc update)

1. Export plain text from Google Doc → save as `The Genesis Melody.txt` in this folder
2. Run `python3 sync-check.py` → generates `sync-changes.csv`
3. Share the CSV output with Claude and approve which rows to apply
4. Claude applies approved changes to `TheGenesisMelody.html`

## Reading the CSV

Focus on rows where action is likely needed:
- `modified` with similarity < 0.95 — real text edits
- `added_in_txt` — new content in the doc not yet in HTML
- `removed_from_txt` — content in HTML that was deleted from the doc

High-similarity `modified` rows (≥ 0.95) are usually formatting noise — review but often skip.

## Known false positives to ignore

The Google Doc plain-text export introduces formatting artifacts. Do NOT apply these to the HTML:

1. **List numbering** — TXT has `"1. Introduction and Motivation..."`, HTML intentionally omits the number.
2. **Scripture line splits** — TXT exports each verse clause on its own line; HTML joins them. Both are correct.
3. **Bullet `* ` prefixes** — Some TXT lines start with `* ` (genealogy lists, etc.). HTML strips these.
4. **Bibliography footnote numbers** — TXT has `"6. Patton, Andy..."`, HTML has `"Patton, Andy..."`.
5. **Google Doc comment lines** — Personal notes from Doc sidebar comments that leaked into the TXT export (e.g., `"I really like this forward: original and so personal, warm, and inviting!"`). Never add these to the HTML.
6. **TXT preamble note** — The TXT file starts with `"Note: there is an audio version..."` and `"It works well to listen..."`. These are reader notes for the TXT. The HTML already has the audio player — do not add this text.

## HTML structure notes

- `TheGenesisMelody.html` uses Google Doc exported CSS classes (`c20`, `c24`, `c81`, etc.)
- Scripture passages are visually wrapped in `.scripture-block` cards by JavaScript at page load
- The sidebar TOC uses clean slug IDs (e.g., `#summary`, `#background`) not Google Doc's auto-generated IDs
- `zoom: 1.15` is applied to `.gdoc-content` (an inner wrapper div) to uniformly scale the Google Doc font sizes
