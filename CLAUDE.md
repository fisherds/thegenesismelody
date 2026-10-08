# The Genesis Melody

Static website (Firebase Hosting → https://thegenesismelody.web.app) presenting *The Genesis Melody*, a long-form Bible study guide on the repeated creation pattern in Genesis 1–23, with a read-along audio narration that highlights each sentence as it plays.

## Source of truth

- **Master text = a Google Doc.** The author edits there, then exports `public/The Genesis Melody.pdf`.
- **Use the Google Doc "Web page (.html, zipped)" export** as the reference when updating the site. Unzip it into `src/gdoc-export/` (git-ignored), which gives `src/gdoc-export/The Genesis Melody/TheGenesisMelody.html` plus `images/`. The PDF also works: For the PDF: `pdftotext -layout "public/The Genesis Melody.pdf" out.txt`, plus `pdfimages -list` / `pdfimages -png` for images.
- `public/index.html` is the display layer. It started as a Google Docs HTML export and has been hand-maintained since.

## Layout

```
public/                      ← deployed as-is (firebase.json "public": "public")
  index.html                 ← the whole article: text, TOC sidebar, audio player, inline GM_SECTIONS script
  The Genesis Melody.pdf     ← downloadable PDF, linked from the page (~50 MB)
  audio/TheGenesisMelody.m4a ← full narration (~80 MB); audio_guide_gen*.m4a are separate older guides
  images/                    ← paintings as .webp, diagrams/charts as .svg (named by content)
  scripts/audio-highlight.js ← sentence read-along highlighting (gm-cue spans)
  styles/genesis-melody*.css
  reader.html, jacob.html    ← separate older pages (Classroom-translation reader)
src/                         ← not deployed: sentence data + sync scripts
  TheGenesisMelody_sentences.json ← sentence list {id, start, end, text}; hub between text, audio and HTML
  TheGenesisMelody_words.json     ← Whisper word timestamps (regenerated from each new recording)
  build_sentences.py              ← step 1: gdoc web export → sentences.json (reuses old ids; writes build_sentences_report.csv)
  sentence_id_generation.py       ← one-time script that added data-sentence-id to gm-cue spans
  CLAUDE.md                       ← notes on the sentence-ID system
```

## Running / deploying

- Local: `npx serve public -p 5000` (not `firebase serve`, which can't seek in the large audio file).
- Deploy: `firebase deploy` (project in `.firebaserc`).

## index.html structure

- Google-Docs CSS classes (`c20`, `c45`, …). Don't rename them. Scripture passages are wrapped into `.scripture-block` cards by JS at load. Some tables (melody cycles) are real `<table>`s from the export.
- Headings carry clean slug IDs (`#summary`, `#structure`, …) used by the sidebar TOC.
- **Audio sync:** each sentence is a `<span class="gm-cue" data-sentence-id="…" data-t-start="…" data-t-end="…">` (seconds). Some block elements also carry `data-t-start/end`. `GM_SECTIONS` (inline `<script>`) holds per-section `start_at` times for nav jumps.
- A disclaimer modal at the top currently says "Note: the text on the page is being updated to match the PDF. The audio will be re-recorded soon too." Remove that line once the new audio and timings are live.

## Update workflow (branch `calling-update-and-ids`, Oct 2026)

`sentences.json` is the hub, and each step is decoupled from the others:

1. **Text → sentences.json.** Rebuild `src/TheGenesisMelody_sentences.json` from the Google Doc web export. Every sentence gets an `id`. Reuse an existing `id` when a sentence is unchanged or nearly unchanged. `start`/`end` are placeholders until there is new audio. This step does **not** touch index.html.
2. **sentences.json → index.html**, one section at a time. Update the text and images and wrap each sentence in a `gm-cue` span carrying its `data-sentence-id`.
3. **New audio → words.json.** The author re-records and runs Whisper, which produces a new `TheGenesisMelody_words.json`.
4. **words.json → sentences.json timings.** Align the words to the sentence text and fill in `start`/`end`.
5. **sentences.json → index.html timings.** A script (`sentence_id_updates.py`, still to be written) copies `start`/`end` onto `data-t-start`/`data-t-end` by matching `data-sentence-id`. It also updates `GM_SECTIONS`.

The author makes all git commits, pushes and PRs (with GitHub Desktop). Claude only edits files.

**Progress:** step 2 is complete (2026-10-08). All 1,015 sentences in `sentences.json` are on the page, in order, one `gm-cue` each. Next is step 3: re-record the audio, add the Whisper script to the repo, and generate `TheGenesisMelody_words.json`. After that come steps 4–5: write the timing scripts and update `GM_SECTIONS`.

How to do a section:
- **Text, bold, color and links** come from the export.
- **Scripture lines** keep the page's existing markup. Each line gets its own `gm-cue`.
- **Melody table rows** have one cue for the Name cell and one for the Chapters cell.
- **New images** go into `public/images/` as WebP at about 900–1200px. The four circle diagrams are SVG.
- **Timings:** a sentence whose text is unchanged keeps its old `data-t-*`. Changed or new sentences get `-1`.
- **Manual edits:** small fixes to `sentences.json` get mirrored in the doc. To check that the doc and the page still agree, re-export into `src/gdoc-export/` and run `python3 src/build_sentences.py "src/gdoc-export/The Genesis Melody/TheGenesisMelody.html"`, then read the git diff of `sentences.json`. Any change it shows is a place where the doc and the page differ.

Status: `origin/sentence-ids` was merged into this branch on 2026-10-07. That brought in the 429 IDs in the HTML and removed the old sync tooling and `PLAN_OF_ATTACK.md`. The HTML↔JSON link is only partial: 227 of the 429 HTML IDs have no entry in `sentences.json`, and 378 of the 580 JSON sentences aren't on the page. Step 1 replaces all of this anyway.

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
