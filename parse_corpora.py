#!/usr/bin/env python3
"""
parse_corpora.py
----------------
Parses both corpora into clean CSVs ready for matching.

Handles:
  - Shakespeare: Folger Shakespeare Library plain-text format
  - TNG: chakoteya.net scraper output format

Outputs
-------
  shakespeare/passages.csv
      play, act, scene, character, speech_text, passage, passage_id

  tng/lines.csv
      season, episode, title, speaker, line_text, line_id

Usage
-----
    python parse_corpora.py

Run from the project root.
"""

import os
import re
import csv
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT      = Path(__file__).parent
SHAK_RAW  = ROOT / "shakespeare" / "raw"
TNG_RAW   = ROOT / "tng" / "raw"
SHAK_OUT  = ROOT / "shakespeare" / "passages.csv"
TNG_OUT   = ROOT / "tng" / "lines.csv"

# Sliding-window config for Shakespeare passage chunking
WINDOW_WORDS = 12   # words per passage chunk
STEP_WORDS   = 6    # stride (50% overlap)

# ---------------------------------------------------------------------------
# Shakespeare parser — Folger TXT format
# ---------------------------------------------------------------------------
#
# Folger TXT structure:
#   Line 1:     Play title
#   Lines 2-N:  Header block (editors, URL, character list)
#   ACT 1       Followed by === underline
#   Scene 1     Followed by === underline
#   [...]       Stage directions in square brackets
#   SPEAKER  text   Speaker in ALL CAPS + 2 spaces + dialogue on same line
#   OR:
#   SPEAKER     Speaker alone, dialogue on following lines
#
# ---------------------------------------------------------------------------

def sliding_windows(text, window, step):
    words = text.split()
    chunks = []
    for i in range(0, max(1, len(words) - window + 1), step):
        chunk = " ".join(words[i : i + window])
        if len(chunk.split()) >= 5:
            chunks.append(chunk)
    return chunks if chunks else [text]


_SPEAKER_RE  = re.compile(r"^([A-Z][A-Z\s\'\-\.]{1,40}?)(?:\s{2,}(.+))?$")
_NOT_SPEAKER = re.compile(
    r"^(ACT\s|SCENE\s|CHARACTERS|PERSONS|THE\s(END|PLAY)|EPILOGUE|PROLOGUE"
    r"|FINIS|INDUCTION|INTRODUCTION|CHORUS|APPENDIX)",
    re.IGNORECASE,
)


def parse_shakespeare_file(path):
    raw   = path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()

    # Title from first non-blank line
    play = path.stem.replace("_", " ").strip()
    for line in lines[:3]:
        s = line.strip()
        if s and not s.startswith("by "):
            play = s
            break

    act          = 0
    scene        = 0
    records      = []
    passage_idx  = 0
    in_header    = True
    character    = None
    speech_lines = []

    def flush_speech():
        nonlocal passage_idx
        if not character or not speech_lines:
            return
        speech_text = re.sub(r"\s+", " ", " ".join(speech_lines).strip())
        if len(speech_text) < 10:
            return
        for chunk in sliding_windows(speech_text, WINDOW_WORDS, STEP_WORDS):
            records.append({
                "passage_id":  f"S{passage_idx:06d}",
                "play":        play,
                "act":         act,
                "scene":       scene,
                "character":   character,
                "speech_text": speech_text,
                "passage":     chunk,
            })
            passage_idx += 1

    for line in lines:
        stripped = line.strip()

        # Skip header until first ACT marker
        if in_header:
            if re.match(r"^ACT\s+[\dIVXivx]", stripped):
                in_header = False
            else:
                continue

        # Act marker
        m_act = re.match(r"^ACT\s+([\dIVXivx]+)", stripped, re.IGNORECASE)
        if m_act:
            flush_speech(); character = None; speech_lines = []
            a = m_act.group(1)
            try:
                act = int(a) if a.isdigit() else \
                    ["I","II","III","IV","V"].index(a.upper()) + 1
            except (ValueError, IndexError):
                act += 1
            scene = 0
            continue

        # Scene marker
        m_scene = re.match(r"^Scene\s+(\d+)", stripped, re.IGNORECASE)
        if m_scene:
            flush_speech(); character = None; speech_lines = []
            scene = int(m_scene.group(1))
            continue

        # Underline or stage direction — skip
        if re.match(r"^=+$", stripped): continue
        if stripped.startswith("["): continue
        if not stripped: continue

        # Speaker detection: line is ALL CAPS
        if (stripped == stripped.upper()
                and len(stripped) >= 2
                and not _NOT_SPEAKER.match(stripped)
                and not re.match(r"^\d", stripped)):
            m_spk = _SPEAKER_RE.match(stripped)
            if m_spk:
                flush_speech()
                character    = m_spk.group(1).strip()
                speech_lines = []
                if m_spk.group(2):
                    speech_lines.append(m_spk.group(2).strip())
                continue

        # Dialogue continuation
        if character and stripped:
            if stripped == stripped.upper() and len(stripped.split()) <= 4:
                flush_speech(); character = stripped; speech_lines = []
            else:
                speech_lines.append(stripped)

    flush_speech()
    return records


def parse_shakespeare_corpus():
    play_files = sorted(SHAK_RAW.glob("*.txt"))
    if not play_files:
        print(f"  WARNING: No .txt files found in {SHAK_RAW}")
        print(f"  Run fetch_shakespeare.py first.")
        return 0

    SHAK_OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["passage_id","play","act","scene",
                  "character","speech_text","passage"]
    total = 0

    with open(SHAK_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for path in play_files:
            records = parse_shakespeare_file(path)
            writer.writerows(records)
            print(f"  {path.name:<45s}  {len(records):>5,} passages")
            total += len(records)

    return total


# ---------------------------------------------------------------------------
# TNG parser — chakoteya.net scraper format (unchanged)
# ---------------------------------------------------------------------------

SPEAKER_ALIASES = {
    "CAPTAIN PICARD": "PICARD", "JEAN-LUC PICARD": "PICARD",
    "COMMANDER RIKER": "RIKER",  "WILLIAM RIKER": "RIKER",
    "COMMANDER DATA": "DATA",    "LT. DATA": "DATA",
    "LIEUTENANT DATA": "DATA",   "COUNSELOR TROI": "TROI",
    "DEANNA TROI": "TROI",       "DR. CRUSHER": "CRUSHER",
    "DOCTOR CRUSHER": "CRUSHER", "BEVERLY CRUSHER": "CRUSHER",
    "LT. WORF": "WORF",          "LIEUTENANT WORF": "WORF",
    "LT. COMMANDER WORF": "WORF","CHIEF O'BRIEN": "O'BRIEN",
    "MILES O'BRIEN": "O'BRIEN",  "ENSIGN CRUSHER": "WESLEY",
    "WESLEY CRUSHER": "WESLEY",  "LT. LAFORGE": "LAFORGE",
    "GEORDI LAFORGE": "LAFORGE","LIEUTENANT LAFORGE": "LAFORGE",
    "LT. COMMANDER LAFORGE": "LAFORGE",
}

def normalize_speaker(raw):
    return SPEAKER_ALIASES.get(raw.strip().upper(), raw.strip().upper())


def parse_tng_file(path):
    text  = path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    meta  = {"season": 0, "episode": 0, "title": path.stem}

    # Derive season/episode from filename (e.g. S03E13_Deja_Q.txt) — these
    # were corrected by fix_tng_filenames.py and are more reliable than the
    # file headers, which still carry the scraper's original wrong numbering.
    m_fn = re.match(r"S(\d{2})E(\d{2})_", path.name)
    if m_fn:
        meta["season"]  = int(m_fn.group(1))
        meta["episode"] = int(m_fn.group(2))

    # Still read the title from the header
    for line in lines[:4]:
        m = re.match(r"TITLE:\s*(.+)", line)
        if m: meta["title"] = m.group(1).strip()

    records  = []
    line_idx = 0

    for raw_line in lines[4:]:
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("-" * 10): continue
        m = re.match(r"^([A-Z][A-Z0-9 '\-\.\/\(\)]{0,40}):\s+(.+)$", stripped)
        if m:
            speaker   = normalize_speaker(m.group(1))
            line_text = m.group(2).strip()
            if len(line_text) < 4: continue
            records.append({
                "line_id":   f"T{meta['season']:02d}{meta['episode']:02d}_{line_idx:04d}",
                "season":    meta["season"], "episode":  meta["episode"],
                "title":     meta["title"],  "speaker":  speaker,
                "line_text": line_text,
            })
            line_idx += 1
        elif len(stripped) > 4:
            records.append({
                "line_id":   f"T{meta['season']:02d}{meta['episode']:02d}_{line_idx:04d}",
                "season":    meta["season"], "episode":  meta["episode"],
                "title":     meta["title"],  "speaker":  "SCENE",
                "line_text": stripped,
            })
            line_idx += 1

    return meta, records


def parse_tng_corpus():
    ep_files = sorted(TNG_RAW.glob("*.txt"))
    if not ep_files:
        print(f"  WARNING: No .txt files found in {TNG_RAW}")
        print(f"  Run scrape_tng.py first.")
        return 0

    TNG_OUT.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["line_id","season","episode","title","speaker","line_text"]
    total = 0

    with open(TNG_OUT, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for path in ep_files:
            meta, records = parse_tng_file(path)
            writer.writerows(records)
            label = f"S{meta['season']:02d}E{meta['episode']:02d} {meta['title']}"
            print(f"  {label:<50s}  {len(records):>4,} lines")
            total += len(records)

    return total


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("PARSING SHAKESPEARE CORPUS  (Folger TXT format)")
    print("=" * 60)
    shak_total = parse_shakespeare_corpus()
    print(f"\n  -> {shak_total:,} total passages written to {SHAK_OUT}\n")

    print("=" * 60)
    print("PARSING TNG CORPUS  (chakoteya.net format)")
    print("=" * 60)
    tng_total = parse_tng_corpus()
    print(f"\n  -> {tng_total:,} total lines written to {TNG_OUT}\n")

    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"  Shakespeare passages : {shak_total:,}")
    print(f"  TNG lines            : {tng_total:,}")
    print(f"\nNext step: run match.py")


if __name__ == "__main__":
    main()
