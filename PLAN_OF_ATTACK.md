# Plan of Attack: Audio Re-sync + Word Highlighting

## What we're doing

1. **Re-sync all `gm-cue` timestamps** in `public/index.html` to the new audio recording, using `src/TheGenesisMelody_sentences.json` as the new source of truth.
2. **Patch HTML text** where the spoken words changed (punctuation, phrasing, a few rewrites).
3. **Update `GM_SECTIONS`** nav jump timestamps in the inline `<script>`.
4. **Add word-level highlighting** as a second layer, using `src/TheGenesisMelody_words.json`.

---

## Why this is hard

- **408 `gm-cue` spans** need new timestamps; **576 sentences** in the new file → not a 1-to-1 index match.
- Old segments split some spoken sentences into multiple spans; new file may join them or split differently.
- Text changed in nearly every sentence (mostly punctuation, but some real rewrites mid-document).
- Timestamps drift up to 100+ seconds by mid-document; new audio is 233 seconds longer overall.
- Direct index alignment fails — we must match by **fuzzy text similarity**.

---

## Decisions locked in

1. **Word highlighting: static `gm-word` spans** injected by a build script. Reliable DOM targeting; ~5,000–8,000 extra spans is fine.
2. **Words JSON loading: eager async fetch on page load.** Copy `src/TheGenesisMelody_words.json` to `public/data/TheGenesisMelody_words.json` and start fetching it the moment the page loads (non-blocking, runs in parallel with the user reading). By the time anyone clicks "Read & Listen" the fetch will almost certainly be complete. If not, word highlighting activates the instant the fetch resolves — sentence highlighting works immediately regardless.
3. **Text changes: prose paragraphs only.** Update visible text where the sentences file diverges from the HTML, but **never touch scripture span HTML** (bold, color classes, footnote anchors). Cross-reference `src/The Genesis Melody.txt` as a sanity check — Whisper sometimes mishears words, and where the text file and sentences file disagree on a non-scriptural word, prefer the text file's version (the written word) over Whisper's transcription, unless the change is clearly an intentional re-phrasing when reading aloud.
4. **Keep `src/The Genesis Melody.txt`** — it's up to date and useful as a reference. **Delete `src/TheGenesisMelody_segments.json`** once Phase 2 is complete and validated.

---

## Phase 0 — Build the matching tool

Write `src/resync.py`:

1. Parse all `<span class="gm-cue" data-t-start="X" data-t-end="Y">` spans from `index.html` — capture current timestamps, visible inner text (strip child HTML tags), and line number.
2. Load `TheGenesisMelody_sentences.json`.
3. For each HTML span, find the best-matching sentence using normalized fuzzy text similarity (lowercase, strip punctuation, difflib SequenceMatcher ratio). Because a single HTML span sometimes covers parts of two adjacent sentences, also try concatenating neighboring sentence pairs.
4. Output `src/resync_map.csv` with columns:
   - `html_line`, `old_start`, `old_end`, `html_text`
   - `new_start`, `new_end`, `new_text`
   - `match_score`, `flag`
   - `flag` values: `OK` (score ≥ 0.85) | `TEXT_CHANGED` (OK but text differs) | `LOW_CONFIDENCE` (score < 0.85) | `MANUAL_REVIEW` (score < 0.6 or span covers multiple sentences)
5. Also load `src/The Genesis Melody.txt` and flag rows where the sentence text disagrees with the .txt file — those are potential Whisper errors to check manually.

**No HTML changes in this phase — tooling only.**

---

## Phase 1 — Review the mapping

Before any edits, review `resync_map.csv` section by section:

- Confirm high-confidence matches look right.
- For `LOW_CONFIDENCE` / `MANUAL_REVIEW` rows, identify the correct sentence manually and annotate the CSV.
- For `TEXT_CHANGED` rows, decide: use Whisper's text (intentional re-phrasing) or .txt file text (Whisper error). Note the decision.
- Note any spans that need to be re-split or merged because the sentence boundaries shifted between old and new audio.

This produces a fully validated mapping we can apply with confidence in Phase 2.

---

## Phase 2 — Section-by-section HTML timestamp + text updates

Work through **one section at a time** in document order. Sections (12 total):

| # | Section | Approx. span count |
|---|---------|-------------------|
| 1 | A Quick Foreword | ~9 |
| 2 | Introduction & Motivation | ~37 |
| 3 | Background | ~7 |
| 4 | Why Study the Melody | ~24 |
| 5 | Structure | ~20 |
| 6 | Pattern Breakers! | ~16 |
| 7 | Melody Observations (intro) | ~5 |
| 8 | Genesis 1–7: The Melody Template | ~36 |
| 9 | Genesis 8–11: The Second Round | ~73 |
| 10 | Genesis 11:27–22:19: Cycles 3–7 | ~26 |
| 11 | The Melody Points to Jesus | ~133 |
| 12 | Next Steps / Closing | ~22 |

**For each section:**
1. Read the relevant HTML block.
2. Apply validated mapping: update `data-t-start` and `data-t-end` on each span.
3. Where `TEXT_CHANGED` is flagged and the decision is to update: carefully patch the visible text, preserving all inner HTML markup (bold, links, footnote anchors, `c16` / `c11` classes, etc.).
4. Never modify scripture passage spans — their text and HTML structure stay frozen.
5. Sanity check: timestamp sequence within the section should be monotonically increasing with no large gaps or overlaps.
6. Pause and show the user the diff for that section before moving on. User approves → next section.

**One section per conversation turn** — small, reviewable chunks.

---

## Phase 3 — Update `GM_SECTIONS` nav timestamps

The `GM_SECTIONS` array in the inline `<script>` (21 entries) has stale `start_at` values after the audio re-recording. After Phase 2:

- For each section entry, find the sentence in `TheGenesisMelody_sentences.json` whose text matches the section heading or the first line of that section.
- Update `start_at` with that sentence's `start` time.
- All 21 entries in one commit.

---

## Phase 4 — Word-level highlighting

### 4a — Copy words data to public

Copy `src/TheGenesisMelody_words.json` → `public/data/TheGenesisMelody_words.json`.

### 4b — Inject word spans (build script)

Write `src/inject_words.py`:
1. Read the updated `public/index.html` (after Phase 2).
2. For each `gm-cue` span, collect all words from `TheGenesisMelody_words.json` whose `start` time falls within `[data-t-start, data-t-end]`.
3. Tokenize the span's visible text into words. Fuzzy-align HTML words to JSON words (strip punctuation for comparison).
4. Wrap each matched word token in: `<span class="gm-word" data-w-start="X.XX" data-w-end="Y.YY">word</span>` — preserving surrounding punctuation outside the span.
5. Words inside scripture spans: skip (don't inject word spans into scripture passages).
6. Output the modified HTML back to `public/index.html`.

### 4c — CSS additions (`public/styles/genesis-melody.css`)

```css
.gm-word-reading {
  background-color: rgba(255, 200, 0, 0.40);
  border-radius: 2px;
  transition: background-color 0.06s;
}
```

The sentence `.gm-reading` highlight is the broader, stronger layer. The word `.gm-word-reading` is a tighter, lighter highlight within it.

### 4d — JS: eager async fetch + word highlight layer

In `public/scripts/audio-highlight.js`, add:

1. **On page load**: immediately start `fetch('/data/TheGenesisMelody_words.json')` and store the result in a `wordCues` array (same format as `cues`: `{start, end, el}`). This runs in parallel with everything else — does not block page load or audio playback.
2. **`findWordCue(time)`**: same binary search as `findCue`, but over `wordCues`.
3. **`setWordHighlight(cue)`**: same pattern as `setHighlight` — adds/removes `.gm-word-reading`. No scroll-into-view (the sentence highlight already handles that).
4. In the `timeupdate` and `seeked` handlers: call `setWordHighlight(findWordCue(audio.currentTime))` — but only if `wordCues` is populated (graceful degradation if fetch hasn't completed or fails).
5. In `clearHighlight`: also clear the word highlight.

The fetch resolves within 1–2 seconds on any reasonable connection. Because the user typically spends several seconds reading the page before clicking "Read & Listen," word highlighting will be ready in time.

---

## Phase 5 — Test & cleanup

- Play the audio and visually verify sentence highlights track correctly through all 12 sections.
- Verify word highlighting advances smoothly within sentences.
- Check edge cases: seeking forward/backward, pausing mid-sentence.
- Verify all 21 `GM_SECTIONS` nav jumps land at the right spot.
- Delete `src/TheGenesisMelody_segments.json`.

---

## Order of work (summary)

```
Phase 0  →  resync.py builds resync_map.csv
Phase 1  →  review + annotate the map together
Phase 2  →  12 sections × (apply + user review + commit)
Phase 3  →  GM_SECTIONS timestamps (1 commit)
Phase 4a →  copy words JSON to public/data/
Phase 4b →  inject_words.py builds word spans into HTML
Phase 4c →  CSS word highlight style
Phase 4d →  audio-highlight.js fetch + word highlight logic
Phase 5  →  test, delete segments file
```
