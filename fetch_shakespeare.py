#!/usr/bin/env python3
"""
fetch_shakespeare.py
--------------------
Downloads all Shakespeare plays in plain-text format from the Folger
Shakespeare Library (https://shakespeare.folger.edu), which offers
authoritative, free texts for non-commercial use.

Output: shakespeare/raw/<Play_Title>.txt  (one file per work)

Usage:
    python fetch_shakespeare.py

Dependencies:
    pip install requests
"""

import os
import re
import time
import requests
from pathlib import Path

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

OUT_DIR   = Path(__file__).parent / "shakespeare" / "raw"
DELAY_SEC = 1.0   # polite delay between requests
TIMEOUT   = 30

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TNG-Shakespeare-Research-Bot/1.0; "
        "academic non-commercial use)"
    )
}

# ---------------------------------------------------------------------------
# Complete Folger TXT short-URL catalogue
# Each entry: (short_url_suffix, canonical_title)
# URLs resolve to Folger's S3 bucket — stable since 2015.
# ---------------------------------------------------------------------------

FOLGER_PLAYS = [
    # Comedies
    ("txtfssAWWtxt", "Alls_Well_That_Ends_Well"),
    ("txtfssAYLtxt", "As_You_Like_It"),
    ("txtfssErrtxt", "The_Comedy_of_Errors"),
    ("txtfssLLLtxt", "Loves_Labors_Lost"),
    ("txtfssMM_txt", "Measure_for_Measure"),
    ("txtfssMV_txt", "The_Merchant_of_Venice"),
    ("txtfssWivtxt", "The_Merry_Wives_of_Windsor"),
    ("txtfssMNDtxt", "A_Midsummer_Nights_Dream"),
    ("txtfssAdotxt", "Much_Ado_About_Nothing"),
    ("txtfssShrtxt", "The_Taming_of_the_Shrew"),
    ("txtfssTN_txt", "Twelfth_Night"),
    ("txtfssTGVtxt", "The_Two_Gentlemen_of_Verona"),
    ("txtfssTNKtxt", "The_Two_Noble_Kinsmen"),
    ("txtfssCymtxt", "Cymbeline"),
    ("txtfssPertxt", "Pericles"),
    ("txtfssTmptxt", "The_Tempest"),
    ("txtfssWT_txt", "The_Winters_Tale"),
    # Histories
    ("txtfss1H4txt", "Henry_IV_Part_1"),
    ("txtfss2H4txt", "Henry_IV_Part_2"),
    ("txtfssH5_txt", "Henry_V"),
    ("txtfss1H6txt", "Henry_VI_Part_1"),
    ("txtfss2H6txt", "Henry_VI_Part_2"),
    ("txtfss3H6txt", "Henry_VI_Part_3"),
    ("txtfssH8_txt", "Henry_VIII"),
    ("txtfssJn_txt", "King_John"),
    ("txtfssR2_txt", "Richard_II"),
    ("txtfssR3_txt", "Richard_III"),
    # Tragedies
    ("txtfssAnttxt", "Antony_and_Cleopatra"),
    ("txtfssCortxt", "Coriolanus"),
    ("txtfssHamtxt", "Hamlet"),
    ("txtfssJC_txt", "Julius_Caesar"),
    ("txtfssLr_txt", "King_Lear"),
    ("txtfssMactxt", "Macbeth"),
    ("txtfssOthtxt", "Othello"),
    ("txtfssRomtxt", "Romeo_and_Juliet"),
    ("txtfssTimtxt", "Timon_of_Athens"),
    ("txtfssTittxt", "Titus_Andronicus"),
    ("txtfssTrotxt", "Troilus_and_Cressida"),
    # Poems & Sonnets (optional — parser skips non-dramatic texts gracefully)
    ("txtfssSontxt", "Shakespeares_Sonnets"),
    ("txtfssLuctxt", "Lucrece"),
    ("txtfssVentxt", "Venus_and_Adonis"),
]

BASE_URL = "https://flgr.sh/"


# ---------------------------------------------------------------------------
# Download helper
# ---------------------------------------------------------------------------

def fetch_play(suffix: str, title: str) -> str | None:
    """Download one play and return its text, or None on failure."""
    url = BASE_URL + suffix
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT,
                            allow_redirects=True)
        resp.raise_for_status()
        # Folger files are UTF-8
        return resp.content.decode("utf-8", errors="replace")
    except Exception as e:
        print(f"  ERROR: {e}")
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {len(FOLGER_PLAYS)} Shakespeare works")
    print(f"Source : https://shakespeare.folger.edu")
    print(f"Output : {OUT_DIR}\n")

    success, failed = 0, []

    for i, (suffix, title) in enumerate(FOLGER_PLAYS, 1):
        out_path = OUT_DIR / f"{title}.txt"

        if out_path.exists():
            print(f"  [{i:02d}/{len(FOLGER_PLAYS)}] SKIP (exists): {title}")
            success += 1
            continue

        print(f"  [{i:02d}/{len(FOLGER_PLAYS)}] Fetching {title} ...",
              end=" ", flush=True)
        text = fetch_play(suffix, title)

        if text:
            out_path.write_text(text, encoding="utf-8")
            kb = len(text) // 1024
            print(f"OK  ({kb} KB)")
            success += 1
        else:
            print("FAILED")
            failed.append(title)

        time.sleep(DELAY_SEC)

    print(f"\nDone. {success}/{len(FOLGER_PLAYS)} works saved to {OUT_DIR}")

    if failed:
        print(f"\nFailed ({len(failed)}):")
        for t in failed:
            print(f"  {t}")
        print("Re-run the script to retry — existing files are skipped.")


if __name__ == "__main__":
    main()
