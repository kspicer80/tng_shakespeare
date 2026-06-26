#!/usr/bin/env python3
"""
scrape_tng.py
-------------
Scrapes all Star Trek: TNG episode transcripts from chakoteya.net and saves
each episode as an individual .txt file in tng/raw/.

Output filename format:  S{season:02d}E{episode:02d}_{slug}.txt
Example:                 S01E01_Encounter_at_Farpoint.txt

Usage:
    python scrape_tng.py

Dependencies:
    pip install requests beautifulsoup4
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_URL   = "http://www.chakoteya.net/NextGen/"
INDEX_URL  = BASE_URL + "episodes.htm"
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tng", "raw")
DELAY_SEC  = 1.5          # polite crawl delay between requests
TIMEOUT    = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (compatible; TNG-Shakespeare-Research-Bot/1.0; "
        "academic use)"
    )
}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def slugify(title: str) -> str:
    """Turn an episode title into a filesystem-safe slug."""
    slug = re.sub(r"[^\w\s-]", "", title)
    slug = re.sub(r"[\s]+", "_", slug.strip())
    return slug[:60]   # cap length


def get_soup(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_episode_number(text: str):
    """
    Chakoteya episode numbers are sometimes formatted as '101', '102' …
    meaning season 1 ep 1, season 1 ep 2, etc.
    Returns (season, episode) as ints, or (None, None) if unparseable.
    """
    text = text.strip()
    # Try explicit "Season X, Episode Y" style first
    m = re.search(r"(\d{1,2})[xX\-](\d{1,2})", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Three-digit code like "101" → S01E01, "212" → S02E12
    m = re.match(r"^(\d)(\d{2})$", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    # Four-digit like "0101"
    m = re.match(r"^(\d{2})(\d{2})$", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return None, None


# ---------------------------------------------------------------------------
# Index scraping — build list of (season, episode, title, url)
# ---------------------------------------------------------------------------

def get_episode_list():
    """
    Parse the chakoteya episode index to get every episode URL.
    Returns list of dicts: {season, episode, title, url}
    """
    print(f"Fetching episode index: {INDEX_URL}")
    soup = get_soup(INDEX_URL)
    episodes = []

    # The index page has links like "101.htm", "102.htm" etc.
    # Each link's visible text is the episode title.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # Match links that look like episode pages: digits + .htm
        if re.match(r"^\d+\.htm$", href):
            title = a.get_text(strip=True)
            ep_code = href.replace(".htm", "")
            season, episode = parse_episode_number(ep_code)
            if season is None:
                # fallback: treat code as sequential
                season, episode = 0, int(ep_code)
            full_url = BASE_URL + href
            episodes.append({
                "season":  season,
                "episode": episode,
                "title":   title or f"Episode_{ep_code}",
                "url":     full_url,
                "code":    ep_code,
            })

    print(f"  Found {len(episodes)} episode links.")
    return episodes


# ---------------------------------------------------------------------------
# Single episode scraping
# ---------------------------------------------------------------------------

def scrape_episode(ep: dict) -> str:
    """
    Download one episode transcript page and return cleaned plain text.
    Format of saved text:
        TITLE: <title>
        SEASON: <n>  EPISODE: <n>
        URL: <url>
        ---
        SPEAKER: dialogue line
        [SCENE DIRECTION or action in brackets]
    """
    soup = get_soup(ep["url"])

    lines = []
    lines.append(f"TITLE: {ep['title']}")
    lines.append(f"SEASON: {ep['season']}  EPISODE: {ep['episode']}")
    lines.append(f"URL: {ep['url']}")
    lines.append("-" * 60)

    # Chakoteya transcripts: the body text is inside <td> elements.
    # Speaker names are in <b> tags; dialogue follows as plain text nodes.
    # We walk the main content td looking for bold tags and text nodes.

    # Find the main content table cell (widest td or just parse all text)
    body_td = None
    for td in soup.find_all("td"):
        text_len = len(td.get_text())
        if text_len > 500:
            body_td = td
            break

    if body_td is None:
        body_td = soup.body

    current_speaker = None
    buffer = []

    def flush_buffer():
        if current_speaker and buffer:
            combined = " ".join(buffer).strip()
            if combined:
                lines.append(f"{current_speaker}: {combined}")
        elif buffer:
            combined = " ".join(buffer).strip()
            if combined:
                lines.append(combined)
        buffer.clear()

    for element in body_td.descendants:
        # Bold tag = speaker name
        if element.name == "b":
            flush_buffer()
            current_speaker = element.get_text(strip=True).upper()
            current_speaker = re.sub(r"[:\s]+$", "", current_speaker)

        # Text node = dialogue or stage direction
        elif element.name is None:  # NavigableString
            text = str(element).strip()
            text = re.sub(r"\s+", " ", text)
            # Skip empty, skip nav artifacts, skip copyright lines
            if not text:
                continue
            if len(text) < 2:
                continue
            if "chakoteya" in text.lower():
                continue
            # Newlines / paragraph breaks → flush
            if "\n" in str(element):
                if text:
                    buffer.append(text)
                flush_buffer()
                current_speaker = None
            else:
                buffer.append(text)

        # Line break → flush current line
        elif element.name == "br":
            flush_buffer()

        # Paragraph or div → flush and break speaker context
        elif element.name in ("p", "div", "tr"):
            flush_buffer()

    flush_buffer()

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    episodes = get_episode_list()

    if not episodes:
        print("ERROR: No episodes found. The site structure may have changed.")
        print("Check the index URL manually:", INDEX_URL)
        return

    print(f"\nScraping {len(episodes)} episodes into: {OUTPUT_DIR}\n")

    success = 0
    failed  = []

    for i, ep in enumerate(episodes, 1):
        slug     = slugify(ep["title"])
        filename = f"S{ep['season']:02d}E{ep['episode']:02d}_{slug}.txt"
        filepath = os.path.join(OUTPUT_DIR, filename)

        if os.path.exists(filepath):
            print(f"  [{i:3d}/{len(episodes)}] SKIP (exists): {filename}")
            success += 1
            continue

        try:
            print(f"  [{i:3d}/{len(episodes)}] Scraping: {filename} ...", end=" ", flush=True)
            content = scrape_episode(ep)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(content)
            print(f"OK  ({len(content):,} chars)")
            success += 1
        except Exception as e:
            print(f"FAILED: {e}")
            failed.append((ep, str(e)))

        time.sleep(DELAY_SEC)

    print(f"\nDone. {success}/{len(episodes)} episodes saved.")
    if failed:
        print(f"\nFailed episodes ({len(failed)}):")
        for ep, err in failed:
            print(f"  S{ep['season']:02d}E{ep['episode']:02d} {ep['title']!r}: {err}")
        print("\nTip: re-run the script — skips already-downloaded files.")


if __name__ == "__main__":
    main()
