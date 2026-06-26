#!/usr/bin/env python3
"""
visualize_pdf.py
----------------
Reads matching/confirmed.csv and produces a multi-page PDF report:
    analysis/shakespeare_in_tng.pdf

Pages:
  1. Title page + summary stats
  2. Bar — Top 15 Shakespeare plays referenced
  3. Bar — Top 10 TNG speakers
  4. Heatmap — Season × play (top 10 plays)
  5. Timeline — References across episode order
  6. Scatter — Fuzzy vs semantic score
  7. Table — Top 40 confirmed matches

Usage:
    python visualize_pdf.py

Dependencies (all standard in Anaconda):
    pip install matplotlib pandas
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.colors import LinearSegmentedColormap
import textwrap
from pathlib import Path

ROOT     = Path(__file__).parent
CONF_CSV = ROOT / "matching" / "confirmed.csv"
OUT_DIR  = ROOT / "analysis"
OUT_PDF  = OUT_DIR / "shakespeare_in_tng.pdf"
OUT_DIR.mkdir(exist_ok=True)

# ── Palette ──────────────────────────────────────────────────────────────────
BG      = "#08090d"
BG2     = "#0e1018"
BG3     = "#141720"
GOLD    = "#c9a84c"
GOLD2   = "#e8cc80"
TEAL    = "#4db8b8"
LCARS   = "#ff9900"
LCARS2  = "#cc6600"
MUTED   = "#7a7560"
TEXT    = "#d4c9a8"
BORDER  = "#2a2e3a"

ACCENT_CYCLE = [GOLD, TEAL, LCARS, "#cc3300", "#88aacc",
                LCARS2, "#6688aa", "#aa88cc", "#558866", "#996644"]

def set_dark_style():
    plt.rcParams.update({
        "figure.facecolor":  BG,
        "axes.facecolor":    BG2,
        "axes.edgecolor":    BORDER,
        "axes.labelcolor":   MUTED,
        "axes.titlecolor":   GOLD2,
        "xtick.color":       MUTED,
        "ytick.color":       MUTED,
        "text.color":        TEXT,
        "grid.color":        BG3,
        "grid.linewidth":    0.6,
        "font.family":       "monospace",
        "font.size":         9,
        "axes.titlesize":    11,
        "axes.titlepad":     10,
    })

# ── Load & prep ──────────────────────────────────────────────────────────────

def load():
    df = pd.read_csv(CONF_CSV)
    df["tng_season"]     = pd.to_numeric(df["tng_season"],     errors="coerce")
    df["tng_episode"]    = pd.to_numeric(df["tng_episode"],    errors="coerce")
    df["fuzzy_score"]    = pd.to_numeric(df["fuzzy_score"],    errors="coerce")
    df["semantic_score"] = pd.to_numeric(df["semantic_score"], errors="coerce")
    df["shak_play"]      = df["shak_play"].str.title()

    ep_order = (
        df[["tng_season", "tng_episode"]]
        .drop_duplicates()
        .sort_values(["tng_season", "tng_episode"])
        .reset_index(drop=True)
    )
    ep_order["ep_global"] = ep_order.index + 1
    df = df.merge(ep_order, on=["tng_season", "tng_episode"], how="left")
    return df

# ── Page helpers ─────────────────────────────────────────────────────────────

def page_title(pdf, df):
    fig = plt.figure(figsize=(11, 8.5))
    fig.patch.set_facecolor(BG)

    # Decorative LCARS bar
    bar_ax = fig.add_axes([0, 0.92, 1, 0.04])
    bar_ax.set_axis_off()
    widths  = [0.18, 0.04, 0.28, 0.02, 0.48]
    colours = [LCARS, LCARS2, TEAL, BG, GOLD]
    left = 0
    for w, c in zip(widths, colours):
        bar_ax.barh(0, w, left=left, color=c, height=1)
        left += w

    ax = fig.add_axes([0.1, 0.3, 0.8, 0.55])
    ax.set_axis_off()
    ax.text(0.5, 0.92, "STARFLEET COMPUTATIONAL HUMANITIES",
            ha="center", va="top", fontsize=9, color=LCARS,
            fontfamily="monospace",
            transform=ax.transAxes)
    ax.text(0.5, 0.78, "The Bard Aboard\nthe Enterprise",
            ha="center", va="top", fontsize=36, color=GOLD2,
            fontfamily="serif", fontstyle="italic", linespacing=1.2,
            transform=ax.transAxes)
    ax.text(0.5, 0.50,
            "Shakespeare References in Star Trek: The Next Generation\n"
            "Detected via TF-IDF Pre-filter · Fuzzy Matching · Semantic Similarity",
            ha="center", va="top", fontsize=11, color=MUTED,
            fontfamily="monospace", linespacing=1.6,
            transform=ax.transAxes)

    # Stats row
    stats = [
        (len(df),                             "confirmed\nreferences"),
        (df["shak_play"].nunique(),            "Shakespeare\nplays"),
        (df["tng_speaker"].nunique(),          "unique\nspeakers"),
        (df[["tng_season","tng_episode"]]\
          .drop_duplicates().shape[0],         "episodes\nwith refs"),
        (int(df["tng_season"].max()),          "seasons\ncovered"),
    ]
    sx = fig.add_axes([0.05, 0.12, 0.9, 0.18])
    sx.set_axis_off()
    for i, (num, label) in enumerate(stats):
        x = 0.1 + i * 0.2
        sx.text(x, 0.75, str(num), ha="center", va="center",
                fontsize=28, color=GOLD, fontfamily="serif",
                transform=sx.transAxes)
        sx.text(x, 0.20, label, ha="center", va="center",
                fontsize=8, color=MUTED, fontfamily="monospace",
                transform=sx.transAxes)

    # Bottom bar
    bot = fig.add_axes([0, 0, 1, 0.025])
    bot.set_axis_off()
    left = 0
    for w, c in zip([0.48, 0.02, 0.28, 0.04, 0.18],
                    [GOLD, BG, TEAL, LCARS2, LCARS]):
        bot.barh(0, w, left=left, color=c, height=1)
        left += w

    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_plays_bar(pdf, df):
    vc = df["shak_play"].value_counts().head(15)
    fig, ax = plt.subplots(figsize=(11, 7))
    colours = [GOLD if i == 0 else TEAL if i == 1 else LCARS
               for i in range(len(vc))]
    bars = ax.barh(vc.index[::-1], vc.values[::-1],
                   color=colours[::-1], height=0.65)
    for bar, val in zip(bars, vc.values[::-1]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                str(val), va="center", fontsize=8, color=TEXT)
    ax.set_xlabel("Number of references", color=MUTED)
    ax.set_title("Top 15 Shakespeare Plays Referenced in TNG", pad=14)
    ax.grid(axis="x", alpha=0.3)
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_speakers_bar(pdf, df):
    vc = df["tng_speaker"].value_counts().head(10)
    colours = []
    for sp in vc.index:
        if sp == "PICARD": colours.append(GOLD)
        elif sp == "DATA":  colours.append(TEAL)
        else:               colours.append(LCARS)

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.barh(vc.index[::-1], vc.values[::-1],
                   color=colours[::-1], height=0.6)
    for bar, val in zip(bars, vc.values[::-1]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                str(val), va="center", fontsize=9, color=TEXT)
    ax.set_xlabel("Number of references", color=MUTED)
    ax.set_title("Top 10 TNG Speakers Quoting Shakespeare", pad=14)
    ax.grid(axis="x", alpha=0.3)
    ax.spines[:].set_visible(False)
    # Legend
    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=GOLD,  label="Picard"),
        Patch(color=TEAL,  label="Data"),
        Patch(color=LCARS, label="Other"),
    ], loc="lower right", facecolor=BG3, edgecolor=BORDER,
       labelcolor=TEXT, fontsize=8)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_heatmap(pdf, df):
    top10 = df["shak_play"].value_counts().head(10).index.tolist()
    pivot = (
        df[df["shak_play"].isin(top10)]
        .groupby(["tng_season", "shak_play"])
        .size()
        .unstack(fill_value=0)
        .reindex(columns=top10, fill_value=0)
    )

    cmap = LinearSegmentedColormap.from_list(
        "gold_dark", [BG2, "#3a2a0a", "#8a6020", GOLD], N=256)

    fig, ax = plt.subplots(figsize=(13, 5))
    im = ax.imshow(pivot.values, aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(top10)))
    ax.set_xticklabels(
        [textwrap.fill(p, 18) for p in top10],
        rotation=35, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"Season {s}" for s in pivot.index], fontsize=9)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if v > 0:
                ax.text(j, i, str(v), ha="center", va="center",
                        fontsize=8,
                        color=BG if v > pivot.values.max()*0.6 else TEXT)
    cb = fig.colorbar(im, ax=ax, shrink=0.7, pad=0.02)
    cb.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=MUTED, fontsize=7)
    ax.set_title("References by Season × Play (Top 10 Plays)", pad=14)
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_timeline(pdf, df):
    per_ep = (
        df.groupby(["ep_global", "tng_season", "tng_episode", "tng_title"])
        .size()
        .reset_index(name="count")
        .sort_values("ep_global")
    )
    per_ep["cumulative"] = per_ep["count"].cumsum()

    # Season boundary lines
    season_starts = (
        per_ep.groupby("tng_season")["ep_global"].min().reset_index()
    )

    fig, ax1 = plt.subplots(figsize=(13, 5))
    ax2 = ax1.twinx()

    ax1.bar(per_ep["ep_global"], per_ep["count"],
            color=LCARS, alpha=0.55, width=0.9, label="Per episode")
    ax2.plot(per_ep["ep_global"], per_ep["cumulative"],
             color=GOLD, linewidth=2, label="Cumulative")

    for _, row in season_starts.iterrows():
        ax1.axvline(row["ep_global"], color=BORDER, linewidth=0.8,
                    linestyle="--", alpha=0.7)
        ax1.text(row["ep_global"] + 0.5, ax1.get_ylim()[1] * 0.92,
                 f"S{int(row['tng_season'])}", fontsize=7,
                 color=MUTED, va="top")

    ax1.set_xlabel("Global episode number", color=MUTED)
    ax1.set_ylabel("References per episode", color=LCARS)
    ax2.set_ylabel("Cumulative references", color=GOLD)
    ax1.tick_params(axis="y", labelcolor=LCARS)
    ax2.tick_params(axis="y", labelcolor=GOLD)
    ax1.grid(axis="x", alpha=0.2)
    ax1.spines[:].set_visible(False)
    ax2.spines[:].set_visible(False)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2,
               facecolor=BG3, edgecolor=BORDER, labelcolor=TEXT,
               fontsize=8, loc="upper left")
    ax1.set_title("Shakespeare References Across All Episodes", pad=14)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_scatter(pdf, df):
    sub = df[df["semantic_score"].notna()].copy()
    if len(sub) > 2000:
        sub = sub.sample(2000, random_state=42)

    top_plays = sub["shak_play"].value_counts().head(8).index.tolist()
    fig, ax = plt.subplots(figsize=(11, 7))

    for i, play in enumerate(top_plays):
        mask = sub["shak_play"] == play
        ax.scatter(sub.loc[mask, "semantic_score"],
                   sub.loc[mask, "fuzzy_score"],
                   label=play, color=ACCENT_CYCLE[i % len(ACCENT_CYCLE)],
                   alpha=0.65, s=22, linewidths=0)

    others = sub[~sub["shak_play"].isin(top_plays)]
    if len(others):
        ax.scatter(others["semantic_score"], others["fuzzy_score"],
                   label="Other", color=MUTED, alpha=0.3, s=14, linewidths=0)

    ax.axhline(80, color=GOLD,  linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axvline(0.78, color=TEAL, linewidth=0.8, linestyle="--", alpha=0.5)
    ax.text(0.785, 81, "confirm zone", fontsize=7, color=MUTED)

    ax.set_xlabel("Semantic similarity score", color=MUTED)
    ax.set_ylabel("Fuzzy match score (token set ratio)", color=MUTED)
    ax.set_title("Fuzzy vs Semantic Score by Play", pad=14)
    ax.grid(alpha=0.2)
    ax.spines[:].set_visible(False)
    ax.legend(facecolor=BG3, edgecolor=BORDER, labelcolor=TEXT,
              fontsize=7, markerscale=1.4,
              loc="lower right", ncol=2)
    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


def page_table(pdf, df):
    cols = ["tng_season", "tng_episode", "tng_speaker",
            "tng_line", "shak_play", "shak_passage", "fuzzy_score"]
    top = (df[cols]
           .sort_values("fuzzy_score", ascending=False)
           .head(40)
           .reset_index(drop=True))

    def wrap(s, w):
        return "\n".join(textwrap.wrap(str(s), w)) if pd.notna(s) else ""

    col_widths  = [0.04, 0.04, 0.07, 0.28, 0.17, 0.32, 0.05]
    col_headers = ["S", "E", "Speaker", "TNG line",
                   "Play", "Shakespeare passage", "Score"]

    fig, ax = plt.subplots(figsize=(14, 20))
    ax.set_axis_off()
    ax.set_title("Top 40 Confirmed Matches (sorted by fuzzy score)", pad=14)

    row_height = 0.023
    y = 0.97
    x_positions = []
    cx = 0
    for w in col_widths:
        x_positions.append(cx)
        cx += w

    # Header row
    for xi, (xp, hdr) in enumerate(zip(x_positions, col_headers)):
        ax.text(xp, y, hdr, fontsize=7, color=GOLD,
                fontweight="bold", transform=ax.transAxes, va="top")
    y -= row_height * 0.8
    ax.plot([0, 1], [y, y], color=BORDER, linewidth=0.8,
            transform=ax.transAxes, clip_on=False)
    y -= row_height * 0.4

    for idx, row in top.iterrows():
        cells = [
            str(int(row["tng_season"])),
            str(int(row["tng_episode"])),
            row["tng_speaker"],
            wrap(row["tng_line"], 38),
            wrap(row["shak_play"], 22),
            wrap(row["shak_passage"], 44),
            str(int(row["fuzzy_score"])),
        ]
        cell_colours = [TEXT, TEXT, LCARS, TEAL, MUTED, GOLD2, LCARS]
        n_lines = max(c.count("\n") + 1 for c in cells)
        rh = row_height * max(n_lines, 1)

        for xi, (xp, cell, colour) in enumerate(
                zip(x_positions, cells, cell_colours)):
            ax.text(xp, y, cell, fontsize=6.5, color=colour,
                    transform=ax.transAxes, va="top", linespacing=1.3)

        y -= rh
        if idx % 2 == 0:
            ax.axhspan(y, y + rh, facecolor=BG3, alpha=0.4,
                       transform=ax.transAxes)

        if y < 0.02:
            break

    fig.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    set_dark_style()
    df = load()
    print(f"Loaded {len(df):,} confirmed matches.")

    with PdfPages(OUT_PDF) as pdf:
        print("  Page 1: Title …")
        page_title(pdf, df)
        print("  Page 2: Plays bar …")
        page_plays_bar(pdf, df)
        print("  Page 3: Speakers bar …")
        page_speakers_bar(pdf, df)
        print("  Page 4: Heatmap …")
        page_heatmap(pdf, df)
        print("  Page 5: Timeline …")
        page_timeline(pdf, df)
        print("  Page 6: Scatter …")
        page_scatter(pdf, df)
        print("  Page 7: Table …")
        page_table(pdf, df)

        d = pdf.infodict()
        d["Title"]   = "The Bard Aboard the Enterprise"
        d["Author"]  = "TNG Shakespeare Reference Detector"
        d["Subject"] = "Shakespeare references in Star Trek: TNG"

    print(f"\nDone → {OUT_PDF}")


if __name__ == "__main__":
    main()
