# The Bard Aboard the Enterprise: Complete Project Reproduction Guide

A step-by-step walkthrough for building the Shakespeare-in-TNG reference
detection pipeline entirely from scratch, including data acquisition,
environment setup, parsing, matching, and visualization.

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Prerequisites](#2-prerequisites)
3. [Project Folder Structure](#3-project-folder-structure)
4. [Environment Setup](#4-environment-setup)
5. [Download the Shakespeare Corpus](#5-download-the-shakespeare-corpus)
6. [Scrape the TNG Transcripts](#6-scrape-the-tng-transcripts)
7. [Fix TNG Filenames](#7-fix-tng-filenames)
8. [Parse Both Corpora into CSVs](#8-parse-both-corpora-into-csvs)
9. [Run the Matching Pipeline](#9-run-the-matching-pipeline)
10. [Generate the PDF Visualization](#10-generate-the-pdf-visualization)
11. [Write the Blog Post](#11-write-the-blog-post)
12. [Full File Inventory](#12-full-file-inventory)
13. [Troubleshooting](#13-troubleshooting)
14. [Tuning and Extending the Project](#14-tuning-and-extending-the-project)

---

## 1. Project Overview

This project builds a computational pipeline to detect Shakespeare references
in all 176 episodes of *Star Trek: The Next Generation*. The pipeline has
six stages:

```
fetch_shakespeare.py          scrape_tng.py
        |                           |
        v                           v
shakespeare/raw/*.txt         tng/raw/*.txt
(Folger TXT format)       (chakoteya.net format)
        |                           |
        +----------+----------------+
                   |
           parse_corpora.py
                   |
     +-------------+-------------+
     |                           |
shakespeare/passages.csv    tng/lines.csv
     |                           |
     +-------------+-------------+
                   |
               match.py
                   |
     +-------------+-------------+
     |                           |
matching/candidates.csv  matching/confirmed.csv
                   |
          visualize_pdf.py
                   |
     analysis/shakespeare_in_tng.pdf
```

**Data sources:**
- **Shakespeare**: [Folger Shakespeare Library](https://shakespeare.folger.edu)
  — authoritative plain-text editions, free for non-commercial use, 42 works
- **TNG**: [chakoteya.net](http://www.chakoteya.net/NextGen/)
  — speaker-tagged transcripts for all 176 episodes

**Final outputs:**
- `matching/confirmed.csv` — ~1,100 high-confidence Shakespeare references
- `analysis/shakespeare_in_tng.pdf` — 7-page visual report
- `tng_shakespeare_blog_post.md` — blog post draft

---

## 2. Prerequisites

### Hardware
- Any modern Mac, Linux, or Windows machine
- ~2 GB free disk space
- ~8 GB RAM recommended (sentence-transformers encoding step)

### Software
- [Anaconda](https://www.anaconda.com/download) or
  [Miniconda](https://docs.conda.io/en/latest/miniconda.html)
- Git (optional)
- A text editor or IDE

### Knowledge assumed
- Basic comfort with the command line / Terminal
- Basic Python familiarity

---

## 3. Project Folder Structure

Only the top-level project folder needs to exist upfront. All subfolders
are created automatically by the scripts.

```
star_trek_next_generation_and_shakespeare/
│
├── fetch_shakespeare.py       ← downloads Shakespeare from Folger
├── scrape_tng.py              ← downloads TNG transcripts from chakoteya.net
├── fix_tng_filenames.py       ← corrects S/E numbering
├── parse_corpora.py           ← produces the two CSVs
├── match.py                   ← fuzzy + semantic matching
├── visualize_pdf.py           ← PDF report generator
│
├── shakespeare/
│   └── raw/                   ← populated by fetch_shakespeare.py
│
├── tng/
│   └── raw/                   ← populated by scrape_tng.py
│
├── matching/                  ← populated by match.py
│   ├── candidates.csv
│   └── confirmed.csv
│
└── analysis/                  ← populated by visualize_pdf.py
    └── shakespeare_in_tng.pdf
```

**Create the project folder:**

```bash
mkdir star_trek_next_generation_and_shakespeare
cd star_trek_next_generation_and_shakespeare
```

Then copy all six scripts into this folder.

---

## 4. Environment Setup

### Why a dedicated conda environment?

The matching step requires `sentence-transformers`, which requires
PyTorch >= 2.4. Installing this into a base Anaconda environment often
conflicts with existing PyTorch versions. A fresh dedicated environment
avoids this entirely.

### Create and activate the environment

```bash
conda create -n tng_shakespeare python=3.11
conda activate tng_shakespeare
```

You should see `(tng_shakespeare)` at the start of your terminal prompt.
**All subsequent commands assume this environment is active.**

### Install PyTorch

```bash
conda install pytorch torchvision torchaudio -c pytorch
```

Verify the version is 2.4 or higher:

```bash
python -c "import torch; print(torch.__version__)"
```

### Install remaining dependencies

```bash
pip install requests beautifulsoup4 rapidfuzz sentence-transformers \
            scikit-learn pandas matplotlib
```

### Verify all imports work

```bash
python -c "
import requests, bs4, rapidfuzz, sentence_transformers
import sklearn, pandas, matplotlib, torch
print('All imports OK')
print('PyTorch:', torch.__version__)
"
```

---

## 5. Download the Shakespeare Corpus

### Source: Folger Shakespeare Library

The [Folger Shakespeare Library](https://www.folger.edu/explore/shakespeares-works/download/)
is the world's largest Shakespeare collection. It offers free plain-text
editions of all 42 works for non-commercial use.

**Folger TXT format** (what the files look like):

```
Hamlet
by William Shakespeare
Edited by Barbara A. Mowat and Paul Werstine
Folger Shakespeare Library
https://shakespeare.folger.edu/shakespeares-works/hamlet/

Characters in the Play
======================
THE GHOST
HAMLET, Prince of Denmark ...

ACT 1
=====

Scene 1
=======
[Enter Barnardo and Francisco, two sentinels.]

BARNARDO  Who's there?

FRANCISCO
Nay, answer me. Stand and unfold yourself.
```

Key structural elements the parser relies on:
- Title on the first line
- `ACT n` followed by `=====` underline
- `Scene n` followed by `=====` underline
- Stage directions in `[square brackets]`
- Speaker names in `ALL CAPS` followed by 2+ spaces and dialogue on the
  same line, OR speaker alone on a line with dialogue on the next line(s)

### The script: `fetch_shakespeare.py`

This script contains the complete Folger short-URL catalogue for all
42 works and downloads them one by one into `shakespeare/raw/`.

**Run:**

```bash
python fetch_shakespeare.py
```

### Expected output

```
Downloading 42 Shakespeare works
Source : https://shakespeare.folger.edu
Output : .../shakespeare/raw

  [01/42] Fetching Alls_Well_That_Ends_Well ... OK  (148 KB)
  [02/42] Fetching As_You_Like_It ... OK  (136 KB)
  ...
  [42/42] Fetching The_Winters_Tale ... OK  (152 KB)

Done. 42/42 works saved to .../shakespeare/raw
```

### Runtime

Approximately 1–2 minutes with the 1-second polite delay built into
the script. Re-running is safe — existing files are skipped.

### What gets downloaded

All 37 plays plus the Sonnets, Lucrece, and Venus and Adonis. The parser
handles the poems gracefully (they have no speaker tags and will produce
zero passages, which is fine — only the plays matter for matching).

---

## 6. Scrape the TNG Transcripts

### Source: chakoteya.net

[chakoteya.net/NextGen](http://www.chakoteya.net/NextGen/) has
speaker-tagged transcripts for all 176 TNG episodes in a consistent
`SPEAKER: dialogue` format.

### The script: `scrape_tng.py`

Fetches the episode index, then downloads all 176 transcripts into
`tng/raw/`, one file per episode.

**Run:**

```bash
python scrape_tng.py
```

### Expected output

```
Fetching episode index: http://www.chakoteya.net/NextGen/episodes.htm
  Found 176 episode links.

Scraping 176 episodes into: .../tng/raw

  [  1/176] Scraping: S01E01_Encounter_at_Farpoint.txt ... OK  (56,906 chars)
  [  2/176] Scraping: S01E03_The_Naked_Now.txt ... OK  (30,512 chars)
  ...
  [176/176] Scraping: S02E77_All_Good_Things.txt ... OK  (71,099 chars)

Done. 176/176 episodes saved.
```

### Runtime

Approximately 5–8 minutes with the 1.5-second polite crawl delay.
Re-running is safe — existing files are skipped.

### Important: filenames will be wrong above episode 99

The scraper misreads chakoteya's sequential episode codes (1, 2, 3…176)
as season/episode pairs for 3-digit numbers. Episode 101 becomes
`S01E01` instead of the correct `S05E02`. This is fixed in the next step.

---

## 7. Fix TNG Filenames

### The problem

After scraping, season numbers are wrong for episodes 26 onward:

| Wrong name | Correct name |
|---|---|
| `S01E27_The_Child.txt` | `S02E01_The_Child.txt` |
| `S02E00_Redemption.txt` | `S04E26_Redemption.txt` |
| `S02E77_All_Good_Things.txt` | `S07E25_All_Good_Things.txt` |

### The script: `fix_tng_filenames.py`

Contains the complete canonical 176-episode TNG list and renames files
by matching on title slug. Always dry-run first.

**Step 1 — preview (nothing changes):**

```bash
python fix_tng_filenames.py --dry-run
```

**Step 2 — rename for real:**

```bash
python fix_tng_filenames.py
```

### Expected output

```
Renamed 171 files.

Could not match 2 episodes:
  seq= 60  S03E13  Deja_Q
  seq= 71  S03E24  Menage_a_Troi
```

### Manual fix for the two accent episodes

```bash
cd tng/raw
ls | grep -i deja      # find the actual wrong name
ls | grep -i nage      # find the actual wrong name
mv "S01E61_Déjà_Q.txt"        "S03E13_Deja_Q.txt"
mv "S01E72_Ménage_à_Troi.txt" "S03E24_Menage_a_Troi.txt"
cd ../..
```

### Verify

```bash
ls tng/raw/ | grep "^S07"
```

You should see Season 7 episodes correctly labeled `S07E01_` through
`S07E25_`.

---

## 8. Parse Both Corpora into CSVs

### The script: `parse_corpora.py`

Reads every `.txt` file from `shakespeare/raw/` and `tng/raw/` and
produces two clean CSVs.

**Run:**

```bash
python parse_corpora.py
```

### What it does

**Shakespeare side (Folger TXT format):**
- Skips the header block (editors, character list) until the first `ACT`
- Detects act and scene from `ACT n` / `Scene n` + underline markers
- Strips stage directions in `[square brackets]`
- Detects speaker lines (ALL CAPS, 2+ leading spaces before dialogue,
  or speaker alone then dialogue on following lines)
- Chunks each speech into overlapping 12-word windows (6-word step)
- Writes `shakespeare/passages.csv`

**TNG side (chakoteya.net format):**
- Parses `SPEAKER: dialogue` lines from each episode file
- Normalizes speaker name variants (`CAPTAIN PICARD` → `PICARD`, etc.)
- Tags unattributed lines as speaker `SCENE`
- Writes `tng/lines.csv`

### Expected output

```
============================================================
PARSING SHAKESPEARE CORPUS  (Folger TXT format)
============================================================
  Alls_Well_That_Ends_Well.txt              2,891 passages
  As_You_Like_It.txt                        3,044 passages
  ...
  -> ~95,000 total passages written to shakespeare/passages.csv

============================================================
PARSING TNG CORPUS  (chakoteya.net format)
============================================================
  S01E01_Encounter_at_Farpoint   1,203 lines
  S01E02_The_Naked_Now             897 lines
  ...
  -> 76,499 total lines written to tng/lines.csv

SUMMARY
  Shakespeare passages : ~95,000
  TNG lines            : 76,499
```

> **Note on passage count**: The Folger TXT format produces somewhat
> fewer passages than the original tagged format (~95k vs ~108k) because
> the Folger files don't include the `<n%>` position markers that were
> spuriously generating extra chunks in the original parser. The match
> quality is the same or better.

### CSV schemas

**`shakespeare/passages.csv`**

| Column | Description |
|--------|-------------|
| `passage_id` | Unique ID (e.g. `S000042`) |
| `play` | Play title |
| `act` | Act number |
| `scene` | Scene number |
| `character` | Speaker name |
| `speech_text` | Full speech text |
| `passage` | 12-word sliding window chunk |

**`tng/lines.csv`**

| Column | Description |
|--------|-------------|
| `line_id` | Unique ID (e.g. `T010112_0034`) |
| `season` | Season number |
| `episode` | Episode number within season |
| `title` | Episode title |
| `speaker` | Normalized speaker name |
| `line_text` | Dialogue text |

---

## 9. Run the Matching Pipeline

### The script: `match.py`

Compares every TNG line against every Shakespeare passage using a
three-stage pipeline. Without the pre-filter, comparing all pairs would
require evaluating ~7 billion combinations — infeasible on a laptop.

**Run:**

```bash
python match.py
```

### The three stages

**Stage 0 — TF-IDF pre-filter (~75 seconds)**

A TF-IDF vectorizer is fit on the combined corpus. For each TNG line,
the top 20 most lexically similar Shakespeare passages are retrieved via
sparse cosine similarity. Reduces ~7 billion pairs to ~800,000 candidates.

```python
vectorizer = TfidfVectorizer(ngram_range=(1, 2), min_df=2,
                              max_df=0.95, sublinear_tf=True)
sims    = sk_cosine(tng_batch, shak_vecs)
top_idx = np.argpartition(row, -TFIDF_TOP_N)[-TFIDF_TOP_N:]
```

**Stage 1 — Fuzzy matching (~45 seconds)**

`rapidfuzz`'s `token_set_ratio` runs over the 800,000 candidate pairs.
Token-set ratio is order-insensitive — ideal for paraphrases where words
are rearranged or substituted ("If you prick us" → "If you prick me").

```python
score = fuzz.token_set_ratio(tng_text, shak_text)
if score >= FUZZY_THRESHOLD:  # default: 60
    results.append(...)
```

**Stage 2 — Semantic similarity (~5 minutes)**

`sentence-transformers` (`all-MiniLM-L6-v2`) encodes only the unique texts
that survived Stage 1 (~25,000) and computes cosine similarity on the
embeddings. Catches thematic allusions where wording has diverged but
meaning is similar.

```python
model      = SentenceTransformer("all-MiniLM-L6-v2")
embeddings = model.encode(all_texts, batch_size=128,
                           normalize_embeddings=True)
sem_score  = float(np.dot(tng_emb, shak_emb))
```

### Tuning constants (top of `match.py`)

```python
TFIDF_TOP_N         = 20    # candidates per TNG line
FUZZY_THRESHOLD     = 60    # token_set_ratio (0-100); raise to reduce noise
SEMANTIC_THRESHOLD  = 0.72  # cosine similarity (0-1)
CONFIRM_FUZZY_HIGH  = 80    # high-confidence fuzzy floor
CONFIRM_SEMANTIC    = 0.78  # high-confidence semantic floor
```

If confirmed matches seem too noisy, raise `FUZZY_THRESHOLD` to 65–70.
If too few matches, lower it to 55.

### Expected output

```
Loading Shakespeare passages …
  ~91,000 passages after length filter
Loading TNG lines …
  40,107 lines after length + speaker filter
Stage 0 — TF-IDF pre-filter …   ~800,000 candidate pairs
Stage 1 — Fuzzy matching …      ~33,000 pairs above threshold 60
Stage 2 — Semantic matching …   encoding ~25,000 unique passages
Candidates : matching/candidates.csv  (~30,000 rows)
Confirmed  : matching/confirmed.csv   (~1,100 rows)

Top plays referenced:
  Hamlet                91
  Twelfth Night         76
  Henry VIII            70
  Othello               65
  ...

Top speakers:
  PICARD    223
  DATA      137
  WORF       86
  ...
```

### Output files

**`matching/candidates.csv`** — all pairs above the loose threshold.
Use for manual review and threshold calibration.

**`matching/confirmed.csv`** — high-confidence subset. All downstream
analysis uses this file.

| Column | Description |
|--------|-------------|
| `tng_season` / `tng_episode` | Season and episode number |
| `tng_title` | Episode title |
| `tng_speaker` | Normalized speaker name |
| `tng_line` | TNG dialogue text |
| `shak_play` | Shakespeare play title |
| `shak_act` / `shak_scene` | Act and scene number |
| `shak_character` | Shakespeare character |
| `shak_passage` | Matched 12-word window |
| `shak_speech` | Full original speech |
| `fuzzy_score` | rapidfuzz token_set_ratio (0–100) |
| `semantic_score` | Cosine similarity (0–1) |

---

## 10. Generate the PDF Visualization

### The script: `visualize_pdf.py`

Reads `matching/confirmed.csv` and produces a 7-page dark-themed PDF
report using matplotlib's `PdfPages`. No additional installs needed.

**Run:**

```bash
python visualize_pdf.py
```

### Expected output

```
Loaded 1,109 confirmed matches.
  Page 1: Title …
  Page 2: Plays bar …
  Page 3: Speakers bar …
  Page 4: Heatmap …
  Page 5: Timeline …
  Page 6: Scatter …
  Page 7: Table …

Done → analysis/shakespeare_in_tng.pdf
```

### Page-by-page contents

| Page | Content |
|------|---------|
| 1 | Title page with 5 summary statistics |
| 2 | Horizontal bar: top 15 Shakespeare plays referenced |
| 3 | Horizontal bar: top 10 TNG speakers (Picard in gold, Data in teal) |
| 4 | Heatmap: references by season × play (top 10 plays) |
| 5 | Timeline: per-episode bar + cumulative line with season markers |
| 6 | Scatter: fuzzy vs semantic score, coloured by play |
| 7 | Table: top 40 confirmed matches with all metadata |

Open `analysis/shakespeare_in_tng.pdf` in Preview (Mac), any PDF viewer,
or directly from Google Drive. Unlike the HTML version, PDFs open without
macOS sandbox restrictions regardless of storage location.

---

## 11. Write the Blog Post

A complete draft blog post in the voice of the *Digital Forays* blog is
available as `tng_shakespeare_blog_post.md`. It covers the intellectual
motivation, pipeline walkthrough with code excerpts, and reflections on
the intentional/allusive/coincidental distinction in reference detection.

To publish to the Hugo-based *Digital Forays* site:

1. Copy `tng_shakespeare_blog_post.md` to `content/posts/` in the Hugo
   site repository
2. Adjust the frontmatter `date:` field as needed
3. Add any visualization images to `static/images/imgforblogposts/`
   and reference them in the post with standard markdown image syntax
4. Run `hugo server` to preview locally before pushing

---

## 12. Full File Inventory

### Scripts (all go in project root)

| File | Purpose | Run order |
|------|---------|-----------|
| `fetch_shakespeare.py` | Downloads 42 Shakespeare works from Folger | 1 |
| `scrape_tng.py` | Downloads 176 TNG transcripts from chakoteya.net | 2 |
| `fix_tng_filenames.py` | Corrects season/episode numbering | 3 |
| `parse_corpora.py` | Produces passages.csv and lines.csv | 4 |
| `match.py` | Three-stage matching pipeline | 5 |
| `visualize_pdf.py` | 7-page PDF report | 6 |

### Generated files

| File | Produced by | Size (approx.) |
|------|-------------|----------------|
| `shakespeare/raw/*.txt` (42 files) | `fetch_shakespeare.py` | ~6 MB total |
| `tng/raw/*.txt` (176 files) | `scrape_tng.py` | ~5 MB total |
| `shakespeare/passages.csv` | `parse_corpora.py` | ~25 MB |
| `tng/lines.csv` | `parse_corpora.py` | ~9 MB |
| `matching/candidates.csv` | `match.py` | ~18 MB |
| `matching/confirmed.csv` | `match.py` | ~700 KB |
| `analysis/shakespeare_in_tng.pdf` | `visualize_pdf.py` | ~500 KB |

### Dependencies

| Package | Used in | Install via |
|---------|---------|-------------|
| `requests` | `fetch_shakespeare.py`, `scrape_tng.py` | pip |
| `beautifulsoup4` | `scrape_tng.py` | pip |
| `rapidfuzz` | `match.py` | pip |
| `sentence-transformers` | `match.py` | pip |
| `scikit-learn` | `match.py` | pip |
| `pandas` | `parse_corpora.py`, `match.py`, `visualize_pdf.py` | pip |
| `matplotlib` | `visualize_pdf.py` | conda/pip |
| `pytorch` | `match.py` (via sentence-transformers) | conda `-c pytorch` |
| `numpy` | `match.py` | installed with scikit-learn |

**One-line install:**
```bash
conda install pytorch torchvision torchaudio -c pytorch && \
pip install requests beautifulsoup4 rapidfuzz sentence-transformers \
            scikit-learn pandas matplotlib
```

---

## 13. Troubleshooting

### `sentence_transformers` fails with PyTorch version error

```
Disabling PyTorch because PyTorch >= 2.4 is required but found 2.2.2
```

You are in the wrong environment. Run:
```bash
conda activate tng_shakespeare
python match.py
```
If it still fails inside the dedicated environment:
```bash
conda install pytorch torchvision torchaudio -c pytorch --force-reinstall
```

### `AttributeError: 'Text' object has no property 'letter_spacing'`

Remove `letter_spacing=2` from the offending `ax.text()` call in
`visualize_pdf.py`. It is a CSS property, not valid in matplotlib.

### `ValueError: 'transform' is not allowed as a keyword argument` in axhline

Replace:
```python
ax.axhline(y, color=BORDER, linewidth=0.8, transform=ax.transAxes)
```
With:
```python
ax.plot([0, 1], [y, y], color=BORDER, linewidth=0.8,
        transform=ax.transAxes, clip_on=False)
```

### HTML file gives `Operation not permitted (NSPOSIXErrorDomain:1)` on Mac

macOS sandbox restriction on files opened from cloud storage paths.
Use `visualize_pdf.py` instead — PDFs open without this restriction.

### `fix_tng_filenames.py` reports 2 unmatched episodes

Expected. Rename manually (see Step 7). These are the two episodes with
accented characters (*Déjà Q* and *Ménage à Troi*).

### Shakespeare passage count seems low

The Folger TXT format produces ~95k passages vs the ~108k from the
original tagged format. This is expected and correct — the difference
was artificial inflation from formatting artifacts in the old format.

### Very few confirmed matches (< 200)

Lower the thresholds in `match.py`:
```python
FUZZY_THRESHOLD    = 55
CONFIRM_FUZZY_HIGH = 75
CONFIRM_SEMANTIC   = 0.74
```

### Too many confirmed matches (> 3,000) with obvious noise

Raise the thresholds:
```python
FUZZY_THRESHOLD    = 65
CONFIRM_FUZZY_HIGH = 85
CONFIRM_SEMANTIC   = 0.82
```

---

## 14. Tuning and Extending the Project

### Use a larger, more accurate semantic model

Default (`all-MiniLM-L6-v2`) is fast. For higher accuracy at ~3× slower:
```python
SBERT_MODEL = "all-mpnet-base-v2"   # in match.py
```

### Add genre metadata to passages

In `parse_corpora.py`, add a `GENRES` dict mapping play titles to
`comedy`, `history`, or `tragedy`, and write a `genre` column to
`passages.csv`. This unlocks genre-level analysis in the visualizations.

### Add a manual review / annotation layer

Create `matching/reviewed.csv` with a `verdict` column
(`confirmed`, `possible`, `coincidence`). Fill it in during close
reading sessions to build human-validated ground truth and formally
evaluate the pipeline's precision.

### Episode deep-dive script

Write `drill_down.py` to print all confirmed matches for a given episode:
```bash
python drill_down.py --season 3 --episode 13   # Déjà Q
```

### Network graph of character → play relationships

Use `networkx` to draw a bipartite graph with TNG speakers on one side,
Shakespeare plays on the other, and edge weights proportional to
reference count:
```bash
pip install networkx
```

### Export to Tableau or Gephi

Both `candidates.csv` and `confirmed.csv` load directly into Tableau
(for interactive dashboards) and Gephi (for network analysis) without
further transformation.

---

*Data sources: Folger Shakespeare Library (shakespeare.folger.edu) for
Shakespeare texts; chakoteya.net for TNG transcripts. Both are used here
for non-commercial academic research.*
