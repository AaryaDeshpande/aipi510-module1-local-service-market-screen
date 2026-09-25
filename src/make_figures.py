"""Generate three publication-ready, directly labeled market-screen charts."""

from __future__ import annotations

import os
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("MPLBACKEND", "Agg")
os.environ.setdefault("MPLCONFIGDIR", str(ROOT / ".cache/matplotlib"))

import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


DATA = ROOT / "data/processed/local_service_market_screen.csv"
OUTPUT = ROOT / "figures"
DOC_OUTPUT = ROOT / "docs/figures"
NAVY = "#183153"
TEAL = "#007E87"
GOLD = "#CF7C2A"
GREY = "#A9B7C7"
INK = "#172536"
MUTED = "#607284"
GRID = "#E1E8EF"
FOCUS = {"Dental offices", "Accounting and tax services", "Legal services"}


def style() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 11,
            "axes.titlesize": 19,
            "axes.titleweight": "bold",
            "axes.labelsize": 11,
            "axes.labelcolor": INK,
            "text.color": INK,
            "xtick.color": MUTED,
            "ytick.color": INK,
            "axes.edgecolor": GRID,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.facecolor": "white",
        }
    )


def save(fig: plt.Figure, stem: str) -> None:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    DOC_OUTPUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT / f"{stem}.png", dpi=220, bbox_inches="tight")
    fig.savefig(OUTPUT / f"{stem}.svg", bbox_inches="tight")
    shutil.copyfile(OUTPUT / f"{stem}.png", DOC_OUTPUT / f"{stem}.png")
    plt.close(fig)


def fragmentation(data: pd.DataFrame) -> None:
    chart = data.sort_values("small_establishment_share", ascending=True)
    colors = [TEAL if name in FOCUS else NAVY for name in chart["industry"]]
    fig, ax = plt.subplots(figsize=(11.5, 7.8))
    bars = ax.barh(chart["industry"], chart["small_establishment_share"] * 100, color=colors, height=0.64)
    ax.set_xlim(0, 108)
    ax.set_xlabel("Share of employer establishments with fewer than 20 employees")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.xaxis.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("Small locations dominate most of these markets", loc="left", pad=18)
    ax.text(
        0, 1.015,
        "2023 U.S. employer establishments · selected local-service industries",
        transform=ax.transAxes, color=MUTED, fontsize=11,
    )
    for bar, row in zip(bars, chart.itertuples(index=False)):
        ax.text(
            bar.get_width() + 0.7,
            bar.get_y() + bar.get_height() / 2,
            f"{row.small_establishment_share:.1%}  ·  {row.small_establishments:,.0f} locations",
            va="center", fontsize=9.3, color=INK,
        )
    ax.text(
        0, -0.14,
        "Source: U.S. Census Bureau, 2023 County Business Patterns. Small refers to the location, not its parent firm.",
        transform=ax.transAxes, color=MUTED, fontsize=9.3,
    )
    fig.subplots_adjust(left=0.32, right=0.79, bottom=0.15, top=0.87)
    save(fig, "fragmentation")


def admin_intensity(data: pd.DataFrame) -> None:
    chart = data.sort_values("admin_employment_share", ascending=True)
    fig, (left, right) = plt.subplots(
        1, 2, figsize=(13.5, 8.0), sharey=True,
        gridspec_kw={"width_ratios": [1.75, 1.05], "wspace": 0.20},
    )
    y = np.arange(len(chart))
    colors = [TEAL if name in FOCUS else NAVY for name in chart["industry"]]
    left.barh(y, chart["admin_employment_share"] * 100, color=colors, height=0.64)
    left.set_yticks(y, chart["industry"])
    left.set_xlim(0, 50)
    left.set_xlabel("Office/admin share of industry employment")
    left.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    left.xaxis.grid(True, color=GRID, linewidth=0.8)
    left.set_axisbelow(True)
    for i, value in enumerate(chart["admin_employment_share"] * 100):
        left.text(value + 0.5, i, f"{value:.1f}%", va="center", fontsize=9.2)

    wages = chart["admin_mean_wage"].to_numpy() / 1000
    right.hlines(y, 0, wages, color=GRID, linewidth=1.5)
    right.scatter(wages, y, s=65, color=GOLD, zorder=3)
    right.set_xlim(0, 72)
    right.set_xlabel("Annual mean wage for admin workers ($k)")
    right.xaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}k"))
    right.xaxis.grid(True, color=GRID, linewidth=0.8)
    right.set_axisbelow(True)
    right.tick_params(axis="y", left=False, labelleft=False)
    for i, wage in enumerate(wages):
        right.text(wage + 1.0, i, f"${wage:.1f}k", va="center", fontsize=9.1)

    fig.suptitle("Administrative intensity varies sharply", x=0.11, y=0.975, ha="left", fontsize=19, fontweight="bold")
    fig.text(0.11, 0.925, "2025 national industry estimates · SOC 43-0000 office and administrative support", color=MUTED, fontsize=11)
    fig.text(
        0.11, 0.045,
        "Source: BLS May 2025 OEWS. Share = rounded admin employment / rounded all-occupation employment; wages exclude benefits.",
        color=MUTED, fontsize=9.1,
    )
    fig.subplots_adjust(left=0.27, right=0.92, bottom=0.12, top=0.86)
    save(fig, "admin_intensity")


def market_screen(data: pd.DataFrame) -> None:
    # Wide canvas keeps the same figure legible in both the article and slides.
    fig, ax = plt.subplots(figsize=(14.5, 6.4))
    x = data["small_establishment_share"].to_numpy() * 100
    y = data["estimated_admin_payroll_per_establishment"].to_numpy() / 1000
    counts = data["small_establishments"].to_numpy()
    # Scatter area is proportional to the count of small employer locations.
    sizes = counts / 125
    colors = [TEAL if name in FOCUS else GREY for name in data["industry"]]
    ax.scatter(x, y, s=sizes, c=colors, alpha=0.7, edgecolor="white", linewidth=1.5, zorder=3)
    ax.set_xlim(58, 103)
    ax.set_ylim(0, 158)
    ax.set_xlabel("Share of employer establishments with fewer than 20 employees (CBP 2023)")
    ax.set_ylabel("Admin wage-bill proxy per average establishment ($k)")
    ax.xaxis.set_major_formatter(mtick.PercentFormatter(decimals=0))
    ax.yaxis.set_major_formatter(mtick.StrMethodFormatter("${x:,.0f}k"))
    ax.grid(True, color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    ax.set_title("A screen for interviews, not a ranking of businesses", loc="left", pad=20)
    ax.text(
        0, 1.015, "Each bubble is an industry; area represents the number of small employer locations",
        transform=ax.transAxes, color=MUTED, fontsize=11,
    )

    offsets = {
        "Dental offices": (-6, -16),
        "Accounting and tax services": (-10, 13),
        "Legal services": (-85, -18),
        "Veterinary services": (8, 0),
        "Chiropractors": (8, -7),
        "Home health care services": (9, 0),
        "Automotive repair and maintenance": (-126, 8),
        "Landscaping services": (-112, -14),
    }
    for row in data.itertuples(index=False):
        if row.industry in offsets:
            label = row.industry.replace(" and maintenance", " & maintenance").replace(" services", "")
            dx, dy = offsets[row.industry]
            ax.annotate(
                label,
                (row.small_establishment_share * 100, row.estimated_admin_payroll_per_establishment / 1000),
                xytext=(dx, dy), textcoords="offset points", fontsize=9.0,
                ha="right" if dx < 0 else "left", va="center", color=INK,
            )

    for count in (25_000, 75_000, 150_000):
        ax.scatter([], [], s=count / 125, color=GREY, alpha=0.7, edgecolor="white", label=f"{count/1000:.0f}k locations")
    ax.legend(
        title="Small employer locations", loc="lower left", bbox_to_anchor=(0.01, 0.03),
        frameon=False, labelspacing=1.4, borderpad=0.3,
    )
    ax.text(
        0, -0.18,
        "Proxy uses average employees across all establishments × OEWS admin share × annual mean wage.\n"
        "It is not observed small-office payroll, savings, or willingness to pay.",
        transform=ax.transAxes, color=MUTED, fontsize=8.8,
    )
    fig.subplots_adjust(left=0.10, right=0.97, bottom=0.22, top=0.84)
    save(fig, "market_screen")


def main() -> None:
    style()
    data = pd.read_csv(DATA)
    if len(data) != 12:
        raise ValueError("Expected the 12 reviewed industries in the processed screen")
    fragmentation(data)
    admin_intensity(data)
    market_screen(data)
    print(f"Wrote three charts (PNG and SVG) to {OUTPUT}")


if __name__ == "__main__":
    main()
