#!/usr/bin/env python3
"""Compact USER-GUIDE.pdf — landscape 2-column, tight margins, all details."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "USER-GUIDE.txt"
OUT = ROOT / "USER-GUIDE.pdf"

MARGIN = 8
FONT = "Helvetica"
SIZE = 6.5
LINE_H = 2.7
COL_GAP = 3
FOOTER_H = 7


def plain(text: str) -> str:
    repl = {
        "\u2014": "-", "\u2192": "->", "\u2022": "-", "\u00b7": "-",
        "\u2717": "X", "\u2713": "OK", "\u2500": "", "\u2550": "",
        "\u2501": "", "\u2013": "-", "\u21bb": "Refresh",
        "\u00d7": "x", "\u20b9": "Rs.",
    }
    for a, b in repl.items():
        text = text.replace(a, b)
    return "".join(ch if ord(ch) < 256 else "?" for ch in text)


def _is_separator(line: str) -> bool:
    s = line.strip()
    return len(s) > 6 and sum(1 for c in s if c in "-=_") >= len(s) - 2


def compact_lines(text: str) -> list[str]:
    rows: list[str] = []
    skip_header = True
    for raw in text.splitlines():
        s = raw.strip()
        if not s or _is_separator(s) or s.startswith("===="):
            continue
        if skip_header:
            if "USER GUIDE" in s.upper() or s.startswith("App URL:") or s.startswith("Market:"):
                continue
            if s.startswith("QUICK START"):
                skip_header = False
            else:
                continue
        rows.append(s)
    return rows


def wrap_line(line: str, max_w: float, pdf: FPDF) -> list[str]:
    if pdf.get_string_width(line) <= max_w:
        return [line]
    words = line.split()
    out: list[str] = []
    cur = ""
    for w in words:
        test = w if not cur else f"{cur} {w}"
        if pdf.get_string_width(test) <= max_w:
            cur = test
        else:
            if cur:
                out.append(cur)
            cur = w
    if cur:
        out.append(cur)
    return out or [line]


def build_rows(text: str, col_w: float, pdf: FPDF) -> list[str]:
    rows: list[str] = []
    for line in compact_lines(plain(text)):
        rows.extend(wrap_line(line, col_w, pdf))
    return rows


class GuidePDF(FPDF):
    def footer(self):
        self.set_y(-6)
        self.set_font(FONT, size=5.5)
        self.set_text_color(100, 100, 100)
        self.cell(0, 4, f"Vedant Swing User Guide  |  Page {self.page_no()}", align="C")


def _page_bottom(pdf: FPDF) -> float:
    return pdf.h - MARGIN - FOOTER_H


def _render_columns(pdf: GuidePDF, left: list[str], right: list[str], col_w: float, left_x: float, right_x: float, y_start: float) -> None:
    y_l, y_r = y_start, y_start
    i_l, i_r = 0, 0
    bottom = _page_bottom(pdf)

    while i_l < len(left) or i_r < len(right):
        if y_l >= bottom and i_l < len(left):
            pdf.add_page()
            y_l = y_r = MARGIN + 2
            bottom = _page_bottom(pdf)
        if y_r >= bottom and i_r < len(right):
            if y_l < MARGIN + 3:
                pdf.add_page()
            y_l = y_r = MARGIN + 2
            bottom = _page_bottom(pdf)

        if i_l < len(left) and y_l + LINE_H <= bottom:
            pdf.set_xy(left_x, y_l)
            pdf.multi_cell(col_w, LINE_H, left[i_l], max_line_height=LINE_H)
            y_l = pdf.get_y()
            i_l += 1
        elif i_l < len(left):
            pdf.add_page()
            y_l = y_r = MARGIN + 2
            bottom = _page_bottom(pdf)
            continue

        if i_r < len(right) and y_r + LINE_H <= bottom:
            pdf.set_xy(right_x, y_r)
            pdf.multi_cell(col_w, LINE_H, right[i_r], max_line_height=LINE_H)
            y_r = pdf.get_y()
            i_r += 1
        elif i_r < len(right):
            pdf.add_page()
            y_l = y_r = MARGIN + 2
            bottom = _page_bottom(pdf)


def main() -> int:
    text = SRC.read_text(encoding="utf-8")

    pdf = GuidePDF(orientation="L", unit="mm", format="A4")
    pdf.set_margins(MARGIN, MARGIN, MARGIN)
    pdf.set_auto_page_break(auto=False)
    pdf.add_page()
    pdf.set_font(FONT, size=SIZE)

    body_w = pdf.w - 2 * MARGIN
    col_w = (body_w - COL_GAP) / 2
    left_x = MARGIN
    right_x = MARGIN + col_w + COL_GAP

    all_rows = build_rows(text, col_w, pdf)
    mid = (len(all_rows) + 1) // 2
    left_rows, right_rows = all_rows[:mid], all_rows[mid:]

    pdf.set_font(FONT, "B", 9)
    pdf.set_xy(MARGIN, MARGIN)
    pdf.cell(body_w, 4, "VEDANT SWING - COMPLETE USER GUIDE", align="C")
    pdf.set_font(FONT, size=6.2)
    pdf.set_xy(MARGIN, MARGIN + 4.5)
    pdf.cell(body_w, 3, "https://vedant-swing-web.onrender.com  |  Nifty 500 Swing Trading  |  All app options below", align="C")

    _render_columns(pdf, left_rows, right_rows, col_w, left_x, right_x, MARGIN + 9)

    pdf.output(str(OUT))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())