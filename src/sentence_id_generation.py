#!/usr/bin/env python3
"""
sentence_id_generation.py

Idempotent — safe to run multiple times.

1. Reads src/TheGenesisMelody_sentences.json
   - Preserves any existing 'id' fields
   - Generates new 12-char hex IDs for entries missing one
   - Writes updated JSON

2. Reads public/index.html
   - Finds every <span class="gm-cue"> element
   - Matches it to a sentence by (data-t-start, data-t-end) == (start, end)
   - Adds data-sentence-id to the gm-cue span if missing or corrects it if wrong
   - Writes updated HTML

NOTE: data-sentence-id lives on the gm-cue span (not the parent block element)
because many block elements contain multiple gm-cue spans — one per sentence.
The gm-cue span is the natural 1-to-1 match for a sentence entry in the JSON.
Future re-sync scripts can find a span by data-sentence-id and update its timestamps.

Logs all unexpected situations to stdout so output can be pasted back for debugging.
Exit code 1 if any hard issues (duplicates, ID mismatches) were found.
"""

import json
import secrets
import sys
from collections import defaultdict
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
SENTENCES_JSON = ROOT / "src" / "TheGenesisMelody_sentences.json"
INDEX_HTML = ROOT / "public" / "index.html"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """12-char lowercase hex, e.g. 'a1b2c3d4e5f6'."""
    return secrets.token_hex(6)


def to_float(val) -> float:
    """Parse a timestamp value to float. Raises ValueError on bad input."""
    return float(val)


def ts_key(start, end) -> tuple:
    """Normalize (start, end) to a (float, float) dict key."""
    return (to_float(start), to_float(end))


# ---------------------------------------------------------------------------
# JSON phase
# ---------------------------------------------------------------------------

def load_sentences() -> list:
    with open(SENTENCES_JSON, encoding="utf-8") as f:
        return json.load(f)


def save_sentences(sentences: list) -> None:
    with open(SENTENCES_JSON, "w", encoding="utf-8") as f:
        json.dump(sentences, f, indent=2, ensure_ascii=False)
        f.write("\n")


def assign_ids(sentences: list) -> int:
    """
    Add 'id' to any sentence missing one. Reorders fields so 'id' is first.
    Returns count of newly generated IDs.
    """
    new_count = 0
    for s in sentences:
        if not s.get("id"):
            new_id = generate_id()
            new_count += 1
        else:
            new_id = s["id"]

        # Rebuild dict with 'id' first for consistent field ordering.
        old_fields = {k: v for k, v in s.items() if k != "id"}
        s.clear()
        s["id"] = new_id
        s.update(old_fields)

    return new_count


def build_json_index(sentences: list) -> tuple[dict, list]:
    """
    Build a (start_float, end_float) -> sentence dict.
    Returns (index, issues_list).
    """
    index = {}
    issues = []
    for s in sentences:
        try:
            key = ts_key(s["start"], s["end"])
        except (KeyError, ValueError) as e:
            issues.append(
                f"JSON_BAD_TIMESTAMP  id={s.get('id', '?')}  error={e}"
                f"  text={s.get('text', '')[:60]!r}"
            )
            continue

        if key in index:
            existing = index[key]
            issues.append(
                f"DUPLICATE_JSON_KEY  start={s['start']} end={s['end']}\n"
                f"    keeping:   id={existing['id']}  text={existing['text'][:60]!r}\n"
                f"    duplicate: id={s['id']}  text={s['text'][:60]!r}"
            )
            # Keep the first one; don't overwrite.
        else:
            index[key] = s
    return index, issues


# ---------------------------------------------------------------------------
# HTML phase
# ---------------------------------------------------------------------------

def update_html(json_index: dict) -> tuple[str, list]:
    """
    Parse HTML, add/update data-sentence-id on each gm-cue span.
    Returns (updated_html_str, issues_list).
    """
    issues = []
    raw = INDEX_HTML.read_text(encoding="utf-8")
    soup = BeautifulSoup(raw, "html.parser")

    gm_cues = soup.find_all("span", class_="gm-cue")
    print(f"  Found {len(gm_cues)} gm-cue spans in HTML")

    # ---- Parse timestamps from every gm-cue span ----
    valid_spans = []  # list of (key, span)
    for span in gm_cues:
        t_start = span.get("data-t-start")
        t_end = span.get("data-t-end")
        if t_start is None or t_end is None:
            issues.append(
                f"GCM_CUE_MISSING_TIMESTAMPS  text={span.get_text()[:60]!r}"
            )
            continue
        try:
            key = ts_key(t_start, t_end)
        except ValueError:
            issues.append(
                f"GCM_CUE_BAD_TIMESTAMPS  data-t-start={t_start!r} data-t-end={t_end!r}"
                f"  text={span.get_text()[:60]!r}"
            )
            continue
        valid_spans.append((key, span))

    # ---- Group by timestamp key to detect duplicates ----
    html_key_groups: dict[tuple, list] = defaultdict(list)
    for key, span in valid_spans:
        html_key_groups[key].append(span)

    for key, spans in html_key_groups.items():
        if len(spans) > 1:
            issues.append(
                f"DUPLICATE_HTML_TIMESTAMPS  start={key[0]} end={key[1]}"
                f"  ({len(spans)} spans share this timestamp — Phase 2: each needs its own timestamps)"
            )

    # ---- Match each span to its sentence and set data-sentence-id ----
    # Rule: each gm-cue span MUST have a unique data-sentence-id — no duplicates allowed.
    # For duplicate timestamp groups: first span gets the JSON ID (if matched), subsequent
    # spans keep their existing ID (if any) or get a fresh generated ID. This ensures
    # idempotency: once a span has any ID it won't be changed by a subsequent run unless
    # it's the first span for a key and needs to match the JSON.
    matched = 0
    skipped_already_correct = 0
    matched_json_ids: set[str] = set()
    all_assigned_ids: set[str] = set()  # guard against accidental duplicates within this run

    for key, spans in html_key_groups.items():
        sentence = json_index.get(key)

        for i, span in enumerate(spans):
            existing_id = span.get("data-sentence-id")
            is_first = (i == 0)

            if sentence is None:
                # No JSON match for this timestamp.
                if existing_id and existing_id not in all_assigned_ids:
                    # Already has a unique ID — leave it alone.
                    all_assigned_ids.add(existing_id)
                    skipped_already_correct += 1
                    matched += 1
                elif not existing_id:
                    # Assign a fresh ID. Log it so Phase 2 can create a JSON entry.
                    new_id = generate_id()
                    span["data-sentence-id"] = new_id
                    all_assigned_ids.add(new_id)
                    matched += 1
                    t_start_raw = span.get("data-t-start", "?")
                    t_end_raw = span.get("data-t-end", "?")
                    is_float_ts = "." in str(t_start_raw) or "." in str(t_end_raw)
                    tag = "HTML_FLOAT_TIMESTAMP_NEW_ID" if is_float_ts else "HTML_NO_JSON_MATCH_NEW_ID"
                    issues.append(
                        f"{tag}  start={key[0]} end={key[1]}"
                        f"  assigned={new_id}"
                        f"  text={span.get_text()[:60]!r}"
                    )
                continue

            # We have a JSON match.
            if is_first:
                # First span for this key: must use the JSON sentence ID.
                target_id = sentence["id"]
                matched_json_ids.add(target_id)
            else:
                # Duplicate span: must NOT share the first span's ID.
                # Keep existing unique ID, or generate a new one.
                if existing_id and existing_id not in all_assigned_ids:
                    target_id = existing_id
                else:
                    target_id = generate_id()
                    issues.append(
                        f"DUPLICATE_SPAN_NEW_ID  start={key[0]} end={key[1]}"
                        f"  span {i+1}/{len(spans)}  assigned={target_id}"
                        f"  (Phase 2: needs its own JSON entry and corrected timestamps)"
                        f"  text={span.get_text()[:40]!r}"
                    )

            if existing_id == target_id:
                all_assigned_ids.add(target_id)
                skipped_already_correct += 1
                matched += 1
            else:
                if existing_id and existing_id != target_id and is_first:
                    issues.append(
                        f"ID_MISMATCH  start={key[0]} end={key[1]}"
                        f"  html_id={existing_id!r}  json_id={target_id!r}  (correcting)"
                        f"  text={span.get_text()[:40]!r}"
                    )
                span["data-sentence-id"] = target_id
                all_assigned_ids.add(target_id)
                matched += 1

    print(f"  {matched} gm-cue spans matched  "
          f"({skipped_already_correct} already correct, "
          f"{matched - skipped_already_correct} newly written)")

    # ---- Find JSON sentences with no HTML match ----
    all_json_ids = {s["id"] for s in json_index.values()}
    for missing_id in sorted(all_json_ids - matched_json_ids):
        sentence = next((s for s in json_index.values() if s["id"] == missing_id), None)
        if sentence:
            issues.append(
                f"JSON_NO_HTML_MATCH  id={missing_id}"
                f"  start={sentence['start']} end={sentence['end']}"
                f"  text={sentence['text'][:60]!r}"
            )

    return str(soup), issues


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=== sentence_id_generation.py ===\n")
    hard_issue = False

    # ---- Step 1: JSON ----
    print("Step 1: sentences JSON")
    sentences = load_sentences()
    print(f"  Loaded {len(sentences)} sentences")

    new_id_count = assign_ids(sentences)
    print(f"  New IDs generated: {new_id_count}")

    json_index, json_issues = build_json_index(sentences)

    save_sentences(sentences)
    print(f"  Saved → {SENTENCES_JSON.relative_to(ROOT)}")

    # ---- Step 2: HTML ----
    print("\nStep 2: HTML")
    html_out, html_issues = update_html(json_index)
    INDEX_HTML.write_text(html_out, encoding="utf-8")
    print(f"  Saved → {INDEX_HTML.relative_to(ROOT)}")

    # ---- Step 3: Issues report ----
    all_issues = json_issues + html_issues
    print(f"\n=== ISSUES ({len(all_issues)}) ===")
    if all_issues:
        for issue in all_issues:
            print(f"  {issue}")
        hard_kinds = ("DUPLICATE_JSON_KEY", "DUPLICATE_HTML_TIMESTAMPS", "ID_MISMATCH",
                      "JSON_BAD_TIMESTAMP", "GCM_CUE_BAD_TIMESTAMPS", "JSON_NO_HTML_MATCH")
        hard_issue = any(any(issue.startswith(k) for k in hard_kinds) for issue in all_issues)
    else:
        print("  None — everything matched cleanly.")

    print()
    if hard_issue:
        print("Exit 1: hard issues found (see above).")
        sys.exit(1)
    else:
        print("Done.")


if __name__ == "__main__":
    main()
