# The Genesis Melody

Static website (Firebase Hosting → https://thegenesismelody.web.app) presenting *The Genesis Melody*, a long-form Bible study guide on the repeated creation pattern in Genesis 1–23, with a read-along audio narration that highlights each sentence as it plays.

## Source of truth

- **Master text = a Google Doc.** The author edits there, then exports `public/The Genesis Melody.pdf`.
- **Use the PDF** as the reference when updating the site (`pdftotext -layout "public/The Genesis Melody.pdf" out.txt`; `pdfimages -list` / `pdfimages -png` for images). `src/The Genesis Melody.txt` is **stale** (May 2026). Don't trust it over the PDF.
- `public/index.html` is the display layer. It started as a Google Docs HTML export and has been hand-maintained since.

## Layout

```
public/                      ← deployed as-is (firebase.json "public": "public")
  index.html                 ← the whole article: text, TOC sidebar, audio player, inline GM_SECTIONS script
  The Genesis Melody.pdf     ← downloadable PDF, linked from the page (~50 MB)
  audio/TheGenesisMelody.m4a ← full narration (~80 MB); audio_guide_gen*.m4a are separate older guides
  images/                    ← imageN.png from the gdoc export, plus chart1/chart2
  scripts/audio-highlight.js ← sentence read-along highlighting (gm-cue spans)
  styles/genesis-melody*.css
  reader.html, jacob.html    ← separate older pages (Classroom-translation reader)
src/                         ← not deployed: sync tooling + Whisper data
  TheGenesisMelody_sentences.json / _words.json ← Whisper output for the May 2026 recording
  resync.py, resync_map.csv, sync-check.py, ... ← one-off sync tools from earlier rounds
  CLAUDE.md                  ← older notes on the gdoc→HTML sync workflow (partly outdated)
PLAN_OF_ATTACK.md            ← May 2026 plan for audio re-sync + word highlighting (never finished)
```

## Running / deploying

- Local: `npx serve public -p 5000` (not `firebase serve`, which can't seek in the large audio file).
- Deploy: `firebase deploy` (project in `.firebaserc`).

## index.html structure

- Google-Docs CSS classes (`c20`, `c45`, …). Don't rename them. Scripture passages are wrapped into `.scripture-block` cards by JS at load. Some tables (melody cycles) are real `<table>`s from the export.
- Headings carry clean slug IDs (`#summary`, `#structure`, …) used by the sidebar TOC.
- **Audio sync:** each sentence is a `<span class="gm-cue" data-t-start="…" data-t-end="…">` (seconds). Some block elements also carry `data-t-start/end`. `GM_SECTIONS` (inline `<script>`) holds per-section `start_at` times for nav jumps.
- A disclaimer modal at the top currently says "the text on this page is not the latest. The PDF is the latest."

## Branch status (as of 2026-10-07)

- `origin/sentence-ids` was **never merged**. It adds a stable `data-sentence-id` to all 429 `gm-cue` spans (`src/sentence_id_generation.py`), adds `id`s to `sentences.json`, re-times about the first part of the page to the May recording, and deletes the old sync files. The whole approach is tied to the May recording.
- `origin/native-audio-controls` was **never merged** either (May 2026). It's an experiment that swaps the custom player for native `<audio>` controls.
- `PLAN_OF_ATTACK.md` phases 0–1 happened on main. Phase 2+ (section-by-section re-timing, word highlighting) was only started on `sentence-ids`.

## October 2026 update: PDF vs. site

The PDF (39 pages, ~14,000 words) is much bigger than the site (~10,700 words). The two texts are about 83% similar. Main changes:

**Rewritten / expanded text**
- Foreword: new second paragraph about the pattern and "become apprentices together". Scope is now "Genesis 1-23" throughout.
- New PDF Table of Contents page. The site already has a sidebar TOC, so it isn't needed on the page.
- Background: extra Tim Mackie material (Joseph/Ezekiel classes) and a new block quote ("a zillion times over… what if I'm in the test?").
- Why Study the Melody: "God models correct behavior for us before we face our test."
- **Structure was reworked.** The four core notes are now **Creation, Calling (Identity), Testing and Choices, Collapse**. Before, they were Creation, Choice, Division, Collapse. There is a new numbered definition list, and Matthew 7:13-14 describes the two paths ("characteristic human choices" vs. "pattern breakers").
- Pattern Breakers: new material on God's mercy, the "binary model" caveat, the fourth collapse, and "deserve meter hits zero".
- Melody tables: every cycle now has a **Calling** row (Cycle 1: Imago Dei, Eph 2:6, avad/shamar; Cycle 2: Gen 7:1 and 8:15-17). Cycle 2 Creation adds za-KAR oonKAY-vah. Choice adds Ezekiel 22:9-11.
- Removed: the backpropagation aside, the "ten words / ten commandments" line, and "C/C/D/C" shorthand.
- Many new paragraphs in Gen 1-7 pattern breakers, Gen 8 intro ("It's Sunday morning!"), Stephen Langton, Gen 8-11 pattern breakers (callings of Moses, Samuel, Joseph), Haran wordplay, and the Avram calling.
- Seventh collapse table and Hagar #2 are expanded. "(Take a pause… selah)" was added inside Gen 22.
- NT section: new opener, monogenes, "Zechariah Elizabeth" gloss, Calling at baptism.
- Beyond Genesis 22: new bullet list on Genesis 23 ("pay the full price").
- Extra Sheva Observations: new paragraphs (Simeon reading aloud, the Avimelek covenant), plus a **Luke 24:44-47** scripture block.
- Your Next Steps: new opening and closing paragraphs, community diversity, and the John 20:22 Ruakh paragraph expanded. The reader link now points to the BibleProject app.
- Bibliography: expanded to 11 entries (Hagar article, Athanasius, Staton, C.S. Lewis).

**Images**
- New painted illustrations (1920px, 3–7 MB each in the PDF): p1 tree at night, p3 figures on a cliff, p8 golden tree, p16 Eve in the garden, p25 figure in a doorway of light, p29 crucifixion (1920×1080), p30 Abraham/Isaac altar (1920×1080), p38 starry sky (880×587), p10 purple/ark (1200²). Check whether that last one is an existing image.
- New diagrams: updated 4-note circle (p9, replaces `image1.png`), "Characteristic Human Choices" circle→spiral (p10), "Pattern Breaker Choices" (p12), "God's Radical Love" (p12).
- Images the PDF keeps: the 5 course tiles, the flood-moment circle (`image8`), the mission-statement image (`image18`), `chart1`/`chart2`, and the sheva verse image (`image22`).
- The PDF no longer has the small 54px cycle badges (`C3 1`, `C2`, `D`, …: `image2/4/5/7/11/13–17/19–21/23/24`). Confirm before removing them from the site.
- Extract with `pdfimages -png -f N -l N`, then re-encode for the web (WebP/JPEG, about 1200px, under 300 KB). Don't ship 7 MB PNGs.

**Audio:** the narration is being re-recorded against the new text. All `gm-cue` timestamps and `GM_SECTIONS` will need to be regenerated from a fresh Whisper run.

## Repo size caution

Binary history is about 1 GB: 5 versions of the ~75–80 MB narration, 3 PDFs, and 7 guide audio files, one of them 97 MB. GitHub rejects files over 100 MB. Each new recording or PDF commit adds roughly 50–80 MB. Consider Git LFS, or keeping large media out of git (Firebase deploys from the local `public/` folder either way).
