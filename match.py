#!/usr/bin/env python3
"""
match.py
--------
Finds Shakespeare references in TNG transcripts using a two-stage pipeline:

  Stage 0 — TF-IDF pre-filter
      For each TNG line, retrieve the top-N most lexically similar Shakespeare
      passages. Reduces 8-billion-pair space to a manageable candidate set.

  Stage 1 — Fuzzy matching (rapidfuzz)
      Token-set ratio on candidate pairs. Fast. Catches close paraphrases.

  Stage 2 — Semantic matching (sentence-transformers)
      Cosine similarity on embeddings. Slower. Catches looser allusions.

Outputs
-------
  matching/candidates.csv   — all pairs above threshold (both methods)
  matching/confirmed.csv    — high-confidence subset for analysis/viz

Usage
-----
  pip install rapidfuzz sentence-transformers scikit-learn pandas
  python match.py

Tuning constants are at the top of the file.
"""

import os
import csv
import time
import warnings
import pandas as pd
import numpy as np
from pathlib import Path
from rapidfuzz import fuzz
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity as sk_cosine
from sentence_transformers import SentenceTransformer

warnings.filterwarnings("ignore")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

ROOT        = Path(__file__).parent
SHAK_CSV    = ROOT / "shakespeare" / "passages.csv"
TNG_CSV     = ROOT / "tng" / "lines.csv"
MATCH_DIR   = ROOT / "matching"
CAND_OUT    = MATCH_DIR / "candidates.csv"
CONF_OUT    = MATCH_DIR / "confirmed.csv"
MATCH_DIR.mkdir(exist_ok=True)

# ---------------------------------------------------------------------------
# Tuning
# ---------------------------------------------------------------------------

TFIDF_TOP_N         = 20     # candidate passages per TNG line from TF-IDF
MIN_TNG_TOKENS      = 5      # skip very short TNG lines
MIN_SHAK_TOKENS     = 5      # skip very short Shakespeare passages

FUZZY_THRESHOLD     = 60     # token_set_ratio 0-100; 60 = fairly loose
SEMANTIC_THRESHOLD  = 0.72   # cosine similarity 0-1

# Confirmed = must clear BOTH thresholds OR fuzzy alone if very high
CONFIRM_FUZZY_HIGH  = 80
CONFIRM_SEMANTIC    = 0.78

# Sentence-transformer model (small & fast; swap for 'all-mpnet-base-v2'
# for higher accuracy at the cost of ~3x slower encoding)
SBERT_MODEL = "all-MiniLM-L6-v2"

# ---------------------------------------------------------------------------
# Load corpora
# ---------------------------------------------------------------------------

def load_corpora():
    print("Loading Shakespeare passages …")
    shak = pd.read_csv(SHAK_CSV, dtype=str).fillna("")
    shak = shak[shak["passage"].str.split().str.len() >= MIN_SHAK_TOKENS]
    shak = shak.reset_index(drop=True)
    print(f"  {len(shak):,} passages after length filter")

    print("Loading TNG lines …")
    tng = pd.read_csv(TNG_CSV, dtype=str).fillna("")
    tng = tng[tng["line_text"].str.split().str.len() >= MIN_TNG_TOKENS]
    # Exclude pure scene directions — they're rarely quotations
    tng = tng[tng["speaker"] != "SCENE"]
    tng = tng.reset_index(drop=True)
    print(f"  {len(tng):,} lines after length + speaker filter\n")

    return shak, tng


# ---------------------------------------------------------------------------
# Stage 0 — TF-IDF pre-filter
# ---------------------------------------------------------------------------

def build_tfidf_candidates(shak: pd.DataFrame, tng: pd.DataFrame) -> list[tuple]:
    """
    Returns list of (tng_idx, shak_idx) candidate pairs.
    Uses TF-IDF cosine similarity to narrow the search space.
    """
    print("Stage 0 — Building TF-IDF index …")
    t0 = time.time()

    corpus = list(shak["passage"]) + list(tng["line_text"])
    vectorizer = TfidfVectorizer(
        ngram_range=(1, 2),
        min_df=2,
        max_df=0.95,
        sublinear_tf=True,
    )
    vectorizer.fit(corpus)

    shak_vecs = vectorizer.transform(shak["passage"])
    tng_vecs  = vectorizer.transform(tng["line_text"])

    print(f"  TF-IDF matrix: {tng_vecs.shape[0]:,} TNG × {shak_vecs.shape[1]:,} features")
    print(f"  Retrieving top-{TFIDF_TOP_N} Shakespeare candidates per TNG line …")

    candidates = []
    batch_size = 500

    for start in range(0, len(tng), batch_size):
        end   = min(start + batch_size, len(tng))
        batch = tng_vecs[start:end]
        sims  = sk_cosine(batch, shak_vecs)   # (batch, n_shak)

        for local_i, row in enumerate(sims):
            tng_idx  = start + local_i
            top_idxs = np.argpartition(row, -TFIDF_TOP_N)[-TFIDF_TOP_N:]
            for shak_idx in top_idxs:
                if row[shak_idx] > 0:
                    candidates.append((tng_idx, int(shak_idx)))

        if (start // batch_size) % 10 == 0:
            pct = end / len(tng) * 100
            print(f"    {end:,}/{len(tng):,} lines processed ({pct:.0f}%)")

    print(f"  {len(candidates):,} candidate pairs in {time.time()-t0:.1f}s\n")
    return candidates


# ---------------------------------------------------------------------------
# Stage 1 — Fuzzy matching
# ---------------------------------------------------------------------------

def run_fuzzy(shak: pd.DataFrame, tng: pd.DataFrame,
              candidates: list[tuple]) -> list[dict]:
    print("Stage 1 — Fuzzy matching …")
    t0 = time.time()
    results = []

    for tng_idx, shak_idx in candidates:
        tng_text  = tng.at[tng_idx, "line_text"]
        shak_text = shak.at[shak_idx, "passage"]
        score     = fuzz.token_set_ratio(tng_text, shak_text)

        if score >= FUZZY_THRESHOLD:
            results.append({
                "tng_idx":    tng_idx,
                "shak_idx":   shak_idx,
                "fuzzy_score": score,
                "tng_text":   tng_text,
                "shak_text":  shak_text,
            })

    print(f"  {len(results):,} pairs above fuzzy threshold {FUZZY_THRESHOLD} "
          f"in {time.time()-t0:.1f}s\n")
    return results


# ---------------------------------------------------------------------------
# Stage 2 — Semantic matching
# ---------------------------------------------------------------------------

def run_semantic(shak: pd.DataFrame, tng: pd.DataFrame,
                 fuzzy_results: list[dict]) -> list[dict]:
    """
    Embed all unique texts appearing in fuzzy_results, then score each pair.
    Much cheaper than embedding the full corpus.
    """
    if not fuzzy_results:
        return []

    print("Stage 2 — Semantic matching …")
    print(f"  Loading model: {SBERT_MODEL} …")
    t0    = time.time()
    model = SentenceTransformer(SBERT_MODEL)

    # Collect unique texts to embed
    unique_tng  = list({r["tng_text"]  for r in fuzzy_results})
    unique_shak = list({r["shak_text"] for r in fuzzy_results})
    all_texts   = unique_tng + unique_shak

    print(f"  Encoding {len(all_texts):,} unique passages …")
    embeddings = model.encode(all_texts, batch_size=128,
                              show_progress_bar=True, normalize_embeddings=True)

    tng_map  = {t: embeddings[i]            for i, t in enumerate(unique_tng)}
    shak_map = {t: embeddings[len(unique_tng)+i] for i, t in enumerate(unique_shak)}

    results = []
    for r in fuzzy_results:
        ev = tng_map[r["tng_text"]]
        sv = shak_map[r["shak_text"]]
        sem_score = float(np.dot(ev, sv))   # already normalized → cosine sim

        if sem_score >= SEMANTIC_THRESHOLD or r["fuzzy_score"] >= FUZZY_THRESHOLD:
            results.append({**r, "semantic_score": round(sem_score, 4)})

    print(f"  {len(results):,} pairs retained after semantic scoring "
          f"in {time.time()-t0:.1f}s\n")
    return results


# ---------------------------------------------------------------------------
# Attach metadata & write outputs
# ---------------------------------------------------------------------------

def attach_metadata(results: list[dict],
                    shak: pd.DataFrame,
                    tng: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for r in results:
        ti = r["tng_idx"]
        si = r["shak_idx"]
        rows.append({
            # TNG metadata
            "line_id":        tng.at[ti, "line_id"],
            "tng_season":     tng.at[ti, "season"],
            "tng_episode":    tng.at[ti, "episode"],
            "tng_title":      tng.at[ti, "title"],
            "tng_speaker":    tng.at[ti, "speaker"],
            "tng_line":       r["tng_text"],
            # Shakespeare metadata
            "passage_id":     shak.at[si, "passage_id"],
            "shak_play":      shak.at[si, "play"],
            "shak_act":       shak.at[si, "act"],
            "shak_scene":     shak.at[si, "scene"],
            "shak_character": shak.at[si, "character"],
            "shak_passage":   r["shak_text"],
            "shak_speech":    shak.at[si, "speech_text"],
            # Scores
            "fuzzy_score":    r["fuzzy_score"],
            "semantic_score": r.get("semantic_score", None),
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    # De-duplicate: keep best fuzzy score per (tng_line, shak_play) pair
    df = (df.sort_values("fuzzy_score", ascending=False)
            .drop_duplicates(subset=["line_id", "shak_play"])
            .reset_index(drop=True))

    return df


def write_outputs(df: pd.DataFrame):
    if df.empty:
        print("No matches found — try lowering thresholds.")
        return

    df.to_csv(CAND_OUT, index=False)
    print(f"Candidates written: {CAND_OUT}  ({len(df):,} rows)")

    # Confirmed: high fuzzy OR (decent fuzzy AND high semantic)
    confirmed = df[
        (df["fuzzy_score"] >= CONFIRM_FUZZY_HIGH) |
        (
            (df["fuzzy_score"] >= FUZZY_THRESHOLD) &
            (df["semantic_score"].notna()) &
            (df["semantic_score"] >= CONFIRM_SEMANTIC)
        )
    ].copy()

    confirmed.to_csv(CONF_OUT, index=False)
    print(f"Confirmed written:  {CONF_OUT}  ({len(confirmed):,} rows)\n")

    # Quick summary
    print("=== Top plays referenced in confirmed matches ===")
    print(confirmed["shak_play"].value_counts().head(15).to_string())
    print("\n=== Top TNG speakers making references ===")
    print(confirmed["tng_speaker"].value_counts().head(10).to_string())


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    shak, tng = load_corpora()

    candidates   = build_tfidf_candidates(shak, tng)
    fuzzy_hits   = run_fuzzy(shak, tng, candidates)
    semantic_hits = run_semantic(shak, tng, fuzzy_hits)

    df = attach_metadata(semantic_hits, shak, tng)
    write_outputs(df)

    print("\nNext step: run visualize.py to explore the results.")


if __name__ == "__main__":
    main()
