#!/usr/bin/env python3
"""Generate Vedant Swing USER-GUIDE.pdf without external dependencies."""

from __future__ import annotations

import re
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "USER-GUIDE.txt"
OUT = ROOT / "USER-GUIDE.pdf"

PAGE_W, PAGE_H = 612, 842
MARGIN_X, MARGIN_TOP, MARGIN_BOTTOM = 50, 50, 50
FONT_SIZE, LEADING = 10, 13
LINES_PER_PAGE = (PAGE_H - MARGIN_TOP - MARGIN_BOTTOM) // LEADING


def _sanitize(text: str) -> str:
    text = text.replace("\u2014", "-").replace("\u2192", "->").replace("\u2022", "-")
    text = text.replace("\u2717", "X").replace("\u2713", "OK").replace("\u00b7", "-")
    text = re.sub(r"[^\x09\x0a\x0d\x20-\x7e]", "?", text)
    return text


def _escape_pdf(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap(line: str, width: int = 92) -> list[str]:
    if len(line) <= width:
        return [line]
    words = line.split()
    rows: list[str] = []
    cur = ""
    for w in words:
        chunk = w if not cur else f"{cur} {w}"
        if len(chunk) <= width:
            cur = chunk
        else:
            if cur:
                rows.append(cur)
            cur = w
    if cur:
        rows.append(cur)
    return rows or [""]


def _flatten_lines(text: str) -> list[str]:
    out: list[str] = []
    for raw in text.splitlines():
        line = _sanitize(raw.rstrip())
        if not line.strip():
            out.append("")
        else:
            out.extend(_wrap(line))
    return out


def _paginate(lines: list[str]) -> list[list[str]]:
    pages: list[list[str]] = []
    cur: list[str] = []
    for line in lines:
        if len(cur) >= LINES_PER_PAGE:
            pages.append(cur)
            cur = []
        cur.append(line)
    if cur:
        pages.append(cur)
    return pages or [[""]]


def _page_stream(page_lines: list[str]) -> bytes:
    y = PAGE_H - MARGIN_TOP
    parts = ["BT", f"/F1 {FONT_SIZE} Tf", f"{MARGIN_X} {y} Td", f"{LEADING} TL"]
    first = True
    for row in page_lines:
        if not first:
            parts.append("T*")
        parts.append(f"({_escape_pdf(row)}) Tj")
        first = False
    parts.append("ET")
    return "\n".join(parts).encode("latin-1", errors="replace")


def build_pdf(text: str) -> bytes:
    page_texts = _paginate(_flatten_lines(text))
    objects: list[bytes] = []

    # 1: Catalog (placeholder, fixed after pages built)
    objects.append(b"__CATALOG__")
    # 2: Pages (placeholder)
    objects.append(b"__PAGES__")
    font_id = 3
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids: list[int] = []
    for page_lines in page_texts:
        stream = _page_stream(page_lines)
        compressed = zlib.compress(stream)
        content_id = len(objects)
        objects.append(
            f"<< /Length {len(compressed)} /Filter /FlateDecode >>\nstream\n".encode()
            + compressed
            + b"\nendstream"
        )
        page_id = len(objects)
        objects.append(
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {PAGE_W} {PAGE_H}] "
            f"/Contents {content_id} 0 R "
            f"/Resources << /Font << /F1 {font_id} 0 R >> >> >>".encode()
        )
        page_ids.append(page_id)

    kids = " ".join(f"{pid} 0 R" for pid in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[0] = b"<< /Type /Catalog /Pages 2 0 R >>"

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{i} 0 obj\n".encode())
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_pos = len(pdf)
    n = len(objects)
    pdf.extend(f"xref\n0 {n + 1}\n".encode())
    pdf.extend(b"0000000000 65535 f \n")
    for off in offsets[1:]:
        pdf.extend(f"{off:010d} 00000 n \n".encode())
    pdf.extend(f"trailer\n<< /Size {n + 1} /Root 1 0 R >>\n".encode())
    pdf.extend(f"startxref\n{xref_pos}\n%%EOF\n".encode())
    return bytes(pdf)


def main() -> int:
    OUT.write_bytes(build_pdf(SRC.read_text(encoding="utf-8")))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())