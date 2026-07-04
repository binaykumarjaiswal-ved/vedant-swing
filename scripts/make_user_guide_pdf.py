#!/usr/bin/env python3
"""Simple plain-text USER-GUIDE.pdf — no design, all content visible."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "USER-GUIDE.txt"
OUT = ROOT / "USER-GUIDE.pdf"

FONT = "Courier"
SIZE = 9
LINE_H = 4.2
MARGIN = 12
MAX_CHARS = 95


def plain(text: str) -> str:
    repl = {
        "\u2014": "-", "\u2192": "->", "\u2022": "-", "\u00b7": "-",
        "\u2717": "X", "\u2713": "OK", "\u2500": "-", "\u2550": "=",
        "\u2501": "=", "\u2013": "-", "\u21bb": "[Refresh]",
        "\u00d7": "x", "\u20b9": "Rs.",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return "".join(ch if ord(ch) < 256 else "?" for ch in text)


def wrap(line: str) -> list[str]:
    line = line.rstrip()
    if not line:
        return [""]
    if len(line) <= MAX_CHARS:
        return [line]
    out: list[str] = []
    while line:
        if len(line) <= MAX_CHARS:
            out.append(line)
            break
        cut = line.rfind(" ", 0, MAX_CHARS + 1)
        if cut < 1:
            cut = MAX_CHARS
        out.append(line[:cut].rstrip())
        line = line[cut:].lstrip()
    return out


def main() -> int:
    text = plain(SRC.read_text(encoding="utf-8"))
    rows: list[str] = []
    for raw in text.splitlines():
        s = raw.rstrip()
        if s and all(c in "-=_" for c in s) and len(s) > 10:
            rows.append("=" * 72)
        else:
            rows.extend(wrap(s))

    pdf = FPDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=True, margin=MARGIN)
    pdf.add_page()
    pdf.set_font(FONT, size=SIZE)

    w = pdf.w - pdf.l_margin - pdf.r_margin
    for row in rows:
        pdf.multi_cell(w, LINE_H, row)
        if row == "":
            pdf.ln(1)

    pdf.output(str(OUT))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())