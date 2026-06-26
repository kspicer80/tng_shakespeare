#!/usr/bin/env python3
"""
export_charts.py
----------------
Saves each visualization from the analysis as individual PNG files
suitable for embedding in a blog post or other document.

Output: analysis/charts/
    01_plays_bar.png
    02_speakers_bar.png
    03_heatmap.png
    04_timeline.png
    05_scatter.png

Usage:
    python export_charts.py

Dependencies: pandas, matplotlib (already installed from visualize_pdf.py)
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import textwrap
from pathlib import Path

ROOT      = Path(__file__).parent
CONF_CSV  = ROOT / "matching" / "confirmed.csv"
OUT_DIR   = ROOT / "analysis" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# ── Palette ──────────────────────────────────────────────────────────────────
BG     = "#08090d"
BG2    = "#0e1018"
BG3    = "#141720"
GOLD   = "#c9a84c"
GOLD2  = "#e8cc80"
TEAL   = "#4db8b8"
LCARS  = "#ff9900"
LCARS2 = "#cc6600"
MUTED  = "#7a7560"
TEXT   = "#d4c9a8"
BORDER = "#2a2e3a"

ACCENT_CYCLE = [GOLD, TEAL, LCARS, "#cc3300", "#88aacc",
                LCARS2, "#6688aa", "#aa88cc", "#558866", "#996644"]

DPI = 150   # increase to 200+ for print-quality


def set_dark_style():
    plt.rcParams.update({
        "figure.facecolor": BG,
        "axes.facecolor":   BG2,
        "axes.edgecolor":   BORDER,
        "axes.labelcolor":  MUTED,
        "axes.titlecolor":  GOLD2,
        "xtick.color":      MUTED,
        "ytick.color":      MUTED,
        "text.color":       TEXT,
        "grid.color":       BG3,
        "grid.linewidth":   0.6,
        "font.family":      "monospace",
        "font.size":        9,
        "axes.titlesize":   12,
        "axes.titlepad":    12,
    })


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


# ── 1. Plays bar ─────────────────────────────────────────────────────────────

def chart_plays_bar(df):
    vc = df["shak_play"].value_counts().head(15)
    colours = [GOLD if i == 0 else TEAL if i == 1 else LCARS
               for i in range(len(vc))]

    fig, ax = plt.subplots(figsize=(10, 6.5))
    bars = ax.barh(vc.index[::-1], vc.values[::-1],
                   color=colours[::-1], height=0.65)
    for bar, val in zip(bars, vc.values[::-1]):
        ax.text(bar.get_width() + 0.4,
                bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=8.5, color=TEXT)
    ax.set_xlabel("Number of confirmed references", color=MUTED, labelpad=8)
    ax.set_title("Top 15 Shakespeare Plays Referenced in TNG", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines[:].set_visible(False)
    ax.set_xlim(0, vc.values.max() * 1.12)
    fig.tight_layout()
    out = OUT_DIR / "01_plays_bar.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 2. Speakers bar ──────────────────────────────────────────────────────────

def chart_speakers_bar(df):
    vc = df["tng_speaker"].value_counts().head(10)
    colours = []
    for sp in vc.index:
        if sp == "PICARD":  colours.append(GOLD)
        elif sp == "DATA":  colours.append(TEAL)
        else:               colours.append(LCARS)

    fig, ax = plt.subplots(figsize=(9, 5.5))
    bars = ax.barh(vc.index[::-1], vc.values[::-1],
                   color=colours[::-1], height=0.6)
    for bar, val in zip(bars, vc.values[::-1]):
        ax.text(bar.get_width() + 0.5,
                bar.get_y() + bar.get_height() / 2,
                str(val), va="center", fontsize=9, color=TEXT)
    ax.set_xlabel("Number of confirmed references", color=MUTED, labelpad=8)
    ax.set_title("Top 10 TNG Speakers Quoting Shakespeare", pad=14)
    ax.grid(axis="x", alpha=0.25)
    ax.spines[:].set_visible(False)
    ax.set_xlim(0, vc.values.max() * 1.14)

    from matplotlib.patches import Patch
    ax.legend(handles=[
        Patch(color=GOLD,  label="Picard"),
        Patch(color=TEAL,  label="Data"),
        Patch(color=LCARS, label="Other"),
    ], loc="lower right", facecolor=BG3, edgecolor=BORDER,
       labelcolor=TEXT, fontsize=8.5)

    fig.tight_layout()
    out = OUT_DIR / "02_speakers_bar.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 3. Heatmap ───────────────────────────────────────────────────────────────

def chart_heatmap(df):
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

    fig, ax = plt.subplots(figsize=(13, 4.5))
    im = ax.imshow(pivot.values, aspect="auto", cmap=cmap)
    ax.set_xticks(range(len(top10)))
    ax.set_xticklabels(
        [textwrap.fill(p, 16) for p in top10],
        rotation=35, ha="right", fontsize=7.5)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"Season {s}" for s in pivot.index], fontsize=9)
    for i in range(pivot.shape[0]):
        for j in range(pivot.shape[1]):
            v = pivot.values[i, j]
            if v > 0:
                ax.text(j, i, str(v), ha="center", va="center",
                        fontsize=8,
                        color=BG if v > pivot.values.max() * 0.55 else TEXT)
    cb = fig.colorbar(im, ax=ax, shrink=0.75, pad=0.02)
    cb.ax.yaxis.set_tick_params(color=MUTED)
    plt.setp(cb.ax.yaxis.get_ticklabels(), color=MUTED, fontsize=7)
    ax.set_title("Shakespeare References by Season and Play (Top 10 Plays)",
                 pad=14)
    ax.spines[:].set_visible(False)
    fig.tight_layout()
    out = OUT_DIR / "03_heatmap.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 4. Timeline ──────────────────────────────────────────────────────────────

def chart_timeline(df):
    per_ep = (
        df.groupby(["ep_global", "tng_season", "tng_episode", "tng_title"])
        .size()
        .reset_index(name="count")
        .sort_values("ep_global")
    )
    per_ep["cumulative"] = per_ep["count"].cumsum()
    season_starts = per_ep.groupby("tng_season")["ep_global"].min().reset_index()

    fig, ax1 = plt.subplots(figsize=(13, 4.5))
    ax2 = ax1.twinx()

    ax1.bar(per_ep["ep_global"], per_ep["count"],
            color=LCARS, alpha=0.55, width=0.9, label="Per episode")
    ax2.plot(per_ep["ep_global"], per_ep["cumulative"],
             color=GOLD, linewidth=2, label="Cumulative")

    for _, row in season_starts.iterrows():
        ax1.axvline(row["ep_global"], color=BORDER,
                    linewidth=0.8, linestyle="--", alpha=0.7)
        ax1.text(row["ep_global"] + 0.5,
                 ax1.get_ylim()[1] * 0.88,
                 f"S{int(row['tng_season'])}", fontsize=7.5,
                 color=MUTED, va="top")

    ax1.set_xlabel("Global episode number", color=MUTED, labelpad=8)
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
               facecolor=BG3, edgecolor=BORDER,
               labelcolor=TEXT, fontsize=8.5, loc="upper left")
    ax1.set_title("Shakespeare References Across All 176 Episodes", pad=14)
    fig.tight_layout()
    out = OUT_DIR / "04_timeline.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── 5. Scatter ───────────────────────────────────────────────────────────────

def chart_scatter(df):
    sub = df[df["semantic_score"].notna()].copy()
    if len(sub) > 2000:
        sub = sub.sample(2000, random_state=42)

    top_plays = sub["shak_play"].value_counts().head(8).index.tolist()

    fig, ax = plt.subplots(figsize=(10, 6.5))
    for i, play in enumerate(top_plays):
        mask = sub["shak_play"] == play
        ax.scatter(sub.loc[mask, "semantic_score"],
                   sub.loc[mask, "fuzzy_score"],
                   label=play,
                   color=ACCENT_CYCLE[i % len(ACCENT_CYCLE)],
                   alpha=0.65, s=22, linewidths=0)
    others = sub[~sub["shak_play"].isin(top_plays)]
    if len(others):
        ax.scatter(others["semantic_score"], others["fuzzy_score"],
                   label="Other", color=MUTED, alpha=0.3, s=14, linewidths=0)

    ax.axhline(80,   color=GOLD,  linewidth=0.8, linestyle="--", alpha=0.5)
    ax.axvline(0.78, color=TEAL,  linewidth=0.8, linestyle="--", alpha=0.5)
    ax.text(0.782, 81, "high-confidence zone", fontsize=7, color=MUTED)

    ax.set_xlabel("Semantic similarity score", color=MUTED, labelpad=8)
    ax.set_ylabel("Fuzzy match score (token set ratio)", color=MUTED, labelpad=8)
    ax.set_title("Fuzzy vs. Semantic Score by Play", pad=14)
    ax.grid(alpha=0.2)
    ax.spines[:].set_visible(False)
    ax.legend(facecolor=BG3, edgecolor=BORDER, labelcolor=TEXT,
              fontsize=7.5, markerscale=1.4,
              loc="lower right", ncol=2)
    fig.tight_layout()
    out = OUT_DIR / "05_scatter.png"
    fig.savefig(out, dpi=DPI, bbox_inches="tight", facecolor=BG)
    plt.close(fig)
    print(f"  Saved: {out.name}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    set_dark_style()
    df = load()
    print(f"Loaded {len(df):,} confirmed matches.\n")
    print(f"Saving charts to {OUT_DIR}/\n")

    chart_plays_bar(df)
    chart_speakers_bar(df)
    chart_heatmap(df)
    chart_timeline(df)
    chart_scatter(df)

    print(f"\nDone. Copy analysis/charts/ to your Hugo static directory:")
    print(f"  cp -r analysis/charts/ /path/to/hugo-site/static/img/imgforblogposts/tng_shakespeare/")
    print(f"  Images are referenced in the blog post as:")
    print(f"  /img/imgforblogposts/tng_shakespeare/01_plays_bar.png  etc.")


if __name__ == "__main__":
    main()
