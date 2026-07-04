#!/usr/bin/env python3
"""Generate Vedant Swing USER-GUIDE.pdf."""

from __future__ import annotations

import re
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "USER-GUIDE.txt"
OUT = ROOT / "USER-GUIDE.pdf"


def _clean(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2192", "->").replace("\u2022", "-")
    text = text.replace("\u2717", "X").replace("\u2713", "OK").replace("\u00b7", "-")
    text = text.replace("\u2500", "-").replace("\u2550", "=")
    return text.encode("latin-1", errors="replace").decode("latin-1")


def _is_rule(line: str) -> bool:
    s = line.strip()
    return len(s) >= 8 and len(set(s)) <= 2 and s[0] in "-=_"


def _wrap_for_pdf(line: str, width: int = 95) -> list[str]:
    if len(line) <= width:
        return [line]
    parts: list[str] = []
    while len(line) > width:
        cut = line.rfind(" ", 0, width)
        if cut < 20:
            cut = width
        parts.append(line[:cut].rstrip())
        line = line[cut:].lstrip()
    if line:
        parts.append(line)
    return parts or [""]


def _write_lines(pdf: FPDF, lines: list[str], h: float = 5.5) -> None:
    w = pdf.w - pdf.l_margin - pdf.r_margin
    for chunk in lines:
        for row in _wrap_for_pdf(chunk):
            pdf.multi_cell(w, h, row)


def build_pdf(text: str) -> FPDF:
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.set_margins(15, 15, 15)

    lines = [_clean(ln.rstrip()) for ln in text.splitlines()]

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 18)
    pdf.cell(0, 12, "Vedant Swing - User Guide", new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(80, 80, 80)
    pdf.cell(0, 6, "https://vedant-swing-web.onrender.com", new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(4)

    for raw in lines:
        line = raw.strip()

        if not line:
            pdf.ln(3)
            continue

        if _is_rule(line):
            pdf.ln(2)
            pdf.set_draw_color(180, 180, 180)
            pdf.line(15, pdf.get_y(), 195, pdf.get_y())
            pdf.ln(4)
            continue

        if line.startswith("VEDANT SWING") and "USER GUIDE" in line:
            continue
        if line.startswith("===="):
            continue

        if line.isupper() and len(line) < 60 and not line.startswith("HTTP"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 12)
            pdf.set_text_color(20, 60, 140)
            _write_lines(pdf, [line], 7)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            continue

        if line.startswith("TAB ") or line.startswith("--"):
            pdf.ln(1)
            pdf.set_font("Helvetica", "B", 11)
            pdf.set_text_color(30, 30, 30)
            _write_lines(pdf, [line.strip("- ").strip()], 6)
            pdf.set_font("Helvetica", "", 10)
            pdf.set_text_color(0, 0, 0)
            continue

        if re.match(r"^\d+\.\s+[A-Z]", line):
            pdf.set_font("Helvetica", "B", 10)
            _write_lines(pdf, [line])
            pdf.set_font("Helvetica", "", 10)
            continue

        pdf.set_font("Helvetica", "", 10)
        _write_lines(pdf, [line])

    return pdf


def main() -> int:
    pdf = build_pdf(SRC.read_text(encoding="utf-8"))
    pdf.output(str(OUT))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())