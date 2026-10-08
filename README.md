# thegenesismelody
Website for https://thegenesismelody.web.app: *The Genesis Melody* study guide, with a read-along audio narration that highlights each sentence as it's read.

The **Google Doc is the master text**. The site (`public/index.html`), the PDF, and the recording all follow it.

## One-time setup

- **Git LFS:** the audio files in `public/audio/*.m4a` are stored with Git LFS. Install it (`brew install git-lfs`, then `git lfs install`) before cloning, or run `git lfs pull` after cloning, so you get the real audio files instead of small pointer files. Deploy only from a checkout that has the real files.
- **ffmpeg** (used by Whisper to read the audio): `brew install ffmpeg`
- **Python environment for Whisper** (Python 3.13; PyTorch doesn't support 3.14 yet):
  ```
  python3.13 -m venv src/.venv
  src/.venv/bin/pip install -r src/requirements.txt
  ```
  The first Whisper run downloads the `turbo` model (~1.5 GB) to `~/.cache/whisper`.
- **Firebase CLI** for deploying: `npm install -g firebase-tools`, then `firebase login`.

## Local testing

```
npx serve public -p 5000
```
Use this instead of `firebase serve`. `firebase serve` can't skip to a specific time in the large audio file, but `npx serve` can.

## Deploying

```
firebase deploy
```
This uploads the `public/` folder from your machine as it is, whatever branch you're on. Don't leave large raw files (like a `.WAV` recording) in `public/`.

---

## Updating the guide

Run all commands from the repo root. Every step that edits files can be reviewed in GitHub Desktop before you commit.

### A. Text or image changes in the Google Doc

1. **Edit the Google Doc.**
2. **Export it.** In Google Docs, choose *File → Download → Web page (.html, zipped)*. Unzip it into `src/gdoc-export/` (git-ignored), replacing what's there, so the file is at
   `src/gdoc-export/The Genesis Melody/TheGenesisMelody.html`.
3. **Rebuild the sentence list:**
   ```
   python3 src/build_sentences.py "src/gdoc-export/The Genesis Melody/TheGenesisMelody.html"
   ```
   It prints how many sentences are unchanged, edited, new, or dropped.
   **The GitHub Desktop diff of `src/TheGenesisMelody_sentences.json` shows exactly what changed in the doc.** `src/build_sentences_report.csv` lists every sentence and its status.
4. **Update `public/index.html` to match.** This step is done by hand (or with Claude Code). For each new or changed sentence:
   - Each sentence on the page is one `<span class="gm-cue" data-sentence-id="…">`, and its id must match the one in `sentences.json`.
   - New sentences get `data-t-start="-1" data-t-end="-1"` until step 6.
   - Keep the page's scripture coloring. Copy bold, italics, colors and links from the doc.
   - New images go in `public/images/`: paintings as `.webp` (about 900–1200px), diagrams and charts as `.svg`. Name them by what they show.
5. **Check the page against the sentence list:**
   ```
   python3 src/check_page.py
   ```
   It should end with `OK: the page matches sentences.json.` If not, it lists each sentence that's missing, extra, out of order, or worded differently.
6. **Re-time the edited sentences** with the existing recording, if the audio still matches the text:
   ```
   python3 src/align_sentences.py
   python3 src/apply_timings.py
   ```
   If you changed what's *read aloud*, re-record that part instead (see B).
7. **Re-export the PDF** (*File → Download → PDF*) to `public/The Genesis Melody.pdf`.
8. **Test locally, commit, deploy.**

### B. New or edited audio recording

1. **Edit and export the narration** (Camtasia) to `public/audio/TheGenesisMelody.m4a`. Keep the raw `.WAV` **outside** the repo.
2. **Transcribe it with Whisper** (about 30 minutes for the 2-hour recording; keep the Mac awake):
   ```
   src/.venv/bin/python src/make_words.py
   ```
   This writes word timings to `src/TheGenesisMelody_words.json`, plus `src/TheGenesisMelody_whisper_segments.json` for spot-checking.
3. **Line up the words with the sentences:**
   ```
   python3 src/align_sentences.py
   ```
   Check the summary: words matched should be in the mid-90s %, with **0 out-of-order starts**. Open `src/align_report.csv` and look at rows flagged:
   - `NONE`: not timed. Usually text that isn't read aloud (verse references, markers). These just won't highlight.
   - `LOW`: few words matched. Usually fine (numbers read differently, "Abraham" vs "Avraham"). Compare the `text` and `whisper_heard` columns.
   - `FILLED`: no match, so it got the time between its neighbors. Usually right.
4. **Put the timings on the page:**
   ```
   python3 src/apply_timings.py
   python3 src/check_page.py
   ```
   This updates every sentence's highlight timing and the audio player's section jump points (`GM_SECTIONS`).
5. **Test locally.** Click *Read & Listen*, jump to a few sections from the audio panel, and confirm the highlight follows the voice.
6. **Commit and deploy.**

### C. Both (text changes and a new recording)

Do **A** steps 1–5, then all of **B**.

---

## Files at a glance

| File | What it is |
|---|---|
| `public/index.html` | The whole guide: text, images, audio player |
| `public/audio/TheGenesisMelody.m4a` | The narration (Git LFS) |
| `src/TheGenesisMelody_sentences.json` | Every sentence: `id`, `start`, `end`, `text`. Connects the doc, the audio, and the page |
| `src/TheGenesisMelody_words.json` | Whisper word timings for the current recording |
| `src/build_sentences.py` | Google Doc export → `sentences.json` (keeps ids stable) |
| `src/make_words.py` | Recording → `words.json` (Whisper `turbo`) |
| `src/align_sentences.py` | `words.json` → `start`/`end` in `sentences.json` |
| `src/apply_timings.py` | `sentences.json` → highlight timings on the page |
| `src/check_page.py` | Checks the page and `sentences.json` match (ids, order, text) |

`CLAUDE.md` has more detail on how the page and the scripts work.
