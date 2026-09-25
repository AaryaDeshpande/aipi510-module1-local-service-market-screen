"""Build a one-page, source-labeled infographic from the reviewed market-screen CSV.

Run from any directory with: python public/make_infographic.py
The SVG is generated from the same table used by the project figures; no chart
position, bubble size, or displayed statistic is typed in by hand.
"""

from __future__ import annotations

import csv
from html import escape
from math import sqrt
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data/processed/local_service_market_screen.csv"
OUTPUT = Path(__file__).with_name("market_screen_infographic.svg")


def text(x: float, y: float, value: str, css: str = "", anchor: str = "start") -> str:
    return (
        f'<text x="{x:.1f}" y="{y:.1f}" class="{css}" '
        f'text-anchor="{anchor}">{escape(value)}</text>'
    )


def load_rows() -> dict[str, dict[str, str]]:
    with DATA.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 12 or len({row["industry"] for row in rows}) != 12:
        raise ValueError("Expected 12 unique, reviewed industries in the market screen")
    if {(row["cbp_year"], row["oews_reference_year"]) for row in rows} != {("2023", "2025")}:
        raise ValueError("Infographic source-year wording needs review")
    return {row["industry"]: row for row in rows}


def build() -> None:
    rows = load_rows()
    max_small = max(int(row["small_establishments"]) for row in rows.values())
    canvas_width, canvas_height = 1800, 1200
    plot_left, plot_right = 144, 1160
    plot_top, plot_bottom = 338, 920

    def px(share: float) -> float:
        return plot_left + (share - 0.60) / 0.40 * (plot_right - plot_left)

    def py(proxy: float) -> float:
        return plot_bottom - proxy / 150_000 * (plot_bottom - plot_top)

    def radius(count: int) -> float:
        # Circle area, not radius, is proportional to the establishment count.
        return 43 * sqrt(count / max_small)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" '
        f'viewBox="0 0 {canvas_width} {canvas_height}" role="img" '
        'aria-labelledby="title desc">',
        '<title id="title">Where should founders interview first? A local-service market screen</title>',
        '<desc id="desc">Scatterplot of 12 selected U.S. service industries. Horizontal position is the 2023 share of employer establishments with fewer than 20 employees. Vertical position is a directional office and administrative wage-payroll proxy combining 2023 Census and May 2025 BLS data. Bubble area represents the count of small employer establishments. Accounting and tax services, dental offices, legal services, and chiropractors are suggested interview starting points, not proven software opportunities. The proxy is not observed payroll, demand, or evidence of automatable work.</desc>',
        '''<style>
          text { font-family: Arial, Helvetica, sans-serif; fill: #173539; }
          .eyebrow { font-size: 21px; font-weight: 700; letter-spacing: 2.6px; fill: #087f78; }
          .title { font-size: 57px; font-weight: 700; letter-spacing: -1.4px; }
          .deck { font-size: 26px; fill: #40585a; }
          .section { font-size: 27px; font-weight: 700; }
          .axis { font-size: 19px; fill: #526467; }
          .axis-title { font-size: 21px; font-weight: 700; }
          .point-label { font-size: 18px; font-weight: 700; }
          .point-detail { font-size: 16px; fill: #4a6062; }
          .panel-heading { font-size: 27px; font-weight: 700; }
          .panel-lede { font-size: 19px; fill: #4a6062; }
          .item-name { font-size: 22px; font-weight: 700; }
          .item-value { font-size: 18px; fill: #385457; }
          .caption { font-size: 17px; fill: #3d5659; }
          .footer { font-size: 19px; fill: #ecf7f4; }
          .footer-strong { font-size: 21px; font-weight: 700; fill: #ffffff; }
        </style>''',
        '<rect width="1800" height="1200" fill="#f7f6f0"/>',
        '<rect x="0" y="0" width="1800" height="17" fill="#087f78"/>',
        text(78, 75, "PUBLIC-DATA MARKET SCREEN", "eyebrow"),
        text(78, 148, "Where should founders interview first?", "title"),
        text(80, 202, "12 selected U.S. local-service industries · structural clues, not product verdicts", "deck"),
        '<line x1="78" y1="239" x2="1722" y2="239" stroke="#cbd8d2" stroke-width="2"/>',
        text(145, 294, "Many small locations + meaningful office work", "section"),
        text(145, 322, "Directional office/admin wage-payroll proxy per establishment ($)", "axis-title"),
    ]

    for amount in (0, 50_000, 100_000, 150_000):
        y = py(amount)
        parts.append(
            f'<line x1="{plot_left}" y1="{y:.1f}" x2="{plot_right}" y2="{y:.1f}" '
            'stroke="#d9e1dc" stroke-width="2"/>'
        )
        parts.append(text(plot_left - 17, y + 7, "$" + ("0" if amount == 0 else f"{amount // 1000}k"), "axis", "end"))
    for share in (0.60, 0.70, 0.80, 0.90, 1.00):
        x = px(share)
        parts.append(
            f'<line x1="{x:.1f}" y1="{plot_top}" x2="{x:.1f}" y2="{plot_bottom}" '
            'stroke="#e3e8e2" stroke-width="2"/>'
        )
        parts.append(text(x, plot_bottom + 32, f"{share:.0%}", "axis", "middle"))
    parts.extend(
        [
            f'<line x1="{plot_left}" y1="{plot_bottom}" x2="{plot_right}" y2="{plot_bottom}" stroke="#849b98" stroke-width="3"/>',
            text((plot_left + plot_right) / 2, 1000, "Share of employer locations with fewer than 20 employees · Census 2023", "axis-title", "middle"),
        ]
    )

    interview_names = {
        "Accounting and tax services",
        "Dental offices",
        "Legal services",
        "Chiropractors",
    }
    comparison_names = {"Veterinary services", "Home health care services"}
    for name, row in rows.items():
        x = px(float(row["small_establishment_share"]))
        y = py(float(row["estimated_admin_payroll_per_establishment"]))
        r = radius(int(row["small_establishments"]))
        if name in interview_names:
            fill, stroke, opacity = "#087f78", "#075e59", "0.78"
        elif name in comparison_names:
            fill, stroke, opacity = "#e8994b", "#a55b20", "0.82"
        else:
            fill, stroke, opacity = "#8fa5a5", "#71898a", "0.45"
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.1f}" fill="{fill}" '
            f'fill-opacity="{opacity}" stroke="{stroke}" stroke-width="2"/>'
        )

    # Only the story-relevant marks receive direct labels; the full twelve-row
    # table remains in the repository for precise values and alternative cuts.
    label_specs = {
        "Veterinary services": (645, 373, "end", "Veterinary", "count"),
        "Accounting and tax services": (966, 361, "end", "Accounting / tax", "count"),
        "Dental offices": (974, 480, "end", "Dental offices", "count"),
        "Legal services": (965, 582, "end", "Legal services", "count"),
        "Chiropractors": (1105, 734, "end", "Chiropractors", "share"),
        "Home health care services": (252, 545, "start", "Home health", "share"),
    }
    for name, (x, y, anchor, label, detail_kind) in label_specs.items():
        row = rows[name]
        detail = (
            f'{int(row["small_establishments"]):,} small locations'
            if detail_kind == "count"
            else f'{float(row["small_establishment_share"]):.1%} small locations'
        )
        parts.append(text(x, y, label, "point-label", anchor))
        parts.append(text(x, y + 22, detail, "point-detail", anchor))

    # The right-hand summary spells out the interview choice without assigning
    # a subjective opportunity score or ranking industries as businesses.
    parts.extend(
        [
            '<rect x="1220" y="282" width="505" height="720" rx="24" fill="#e7f0ea"/>',
            text(1260, 342, "Four interview starting points", "panel-heading"),
            text(1260, 377, "Selected for different structural signals—", "panel-lede"),
            text(1260, 404, "not ranked product opportunities.", "panel-lede"),
        ]
    )
    item_order = [
        "Accounting and tax services",
        "Dental offices",
        "Legal services",
        "Chiropractors",
    ]
    short_names = {
        "Accounting and tax services": "Accounting / tax",
        "Dental offices": "Dental offices",
        "Legal services": "Legal services",
        "Chiropractors": "Chiropractors",
    }
    for index, name in enumerate(item_order):
        row = rows[name]
        y = 474 + index * 126
        count = int(row["small_establishments"])
        admin_share = float(row["admin_employment_share"])
        parts.extend(
            [
                f'<circle cx="1268" cy="{y - 8}" r="9" fill="#087f78"/>',
                text(1292, y, short_names[name], "item-name"),
                text(1292, y + 32, f"{count:,} small locations  ·  {admin_share:.1%} admin share", "item-value"),
            ]
        )
        if index < 3:
            parts.append(f'<line x1="1260" y1="{y + 66}" x2="1685" y2="{y + 66}" stroke="#cbdcd3" stroke-width="2"/>')
    parts.extend(
        [
            '<circle cx="1272" cy="932" r="10" fill="#087f78"/>',
            text(1295, 939, "Interview starting points", "caption"),
            '<circle cx="1272" cy="961" r="10" fill="#e8994b"/>',
            text(1295, 968, "Contrasting examples", "caption"),
            '<circle cx="1272" cy="990" r="10" fill="#8fa5a5" fill-opacity="0.55"/>',
            text(1295, 997, "Other selected industries", "caption"),
            '<rect x="0" y="1040" width="1800" height="160" fill="#173d40"/>',
            text(78, 1088, "Read the bubbles as interview leads—not addressable spend.", "footer-strong"),
            text(78, 1125, "Bubble area = number of employer locations with <20 employees. The vertical measure is a constructed proxy:", "footer"),
            text(78, 1153, "Census average employees/location × BLS office/admin employment share × BLS annual mean wage.", "footer"),
            text(78, 1181, "Sources: 2023 Census CBP + May 2025 BLS OEWS. Not observed payroll, customer demand, or evidence of automatable work.", "footer"),
            '</svg>',
        ]
    )
    OUTPUT.write_text("\n".join(parts) + "\n", encoding="utf-8")
    print(f"Wrote {OUTPUT}")


if __name__ == "__main__":
    build()
