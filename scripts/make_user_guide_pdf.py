#!/usr/bin/env python3
"""Vedant Swing USER-GUIDE.pdf — Hindi labels, logo, phone-friendly text."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "USER-GUIDE.pdf"
LOGO = ROOT / "assets" / "vedant-swing-logo.png"
HINDI_REG = Path(r"C:\Windows\Fonts\Nirmala.ttf")
HINDI_BOLD = Path(r"C:\Windows\Fonts\NirmalaB.ttf")

BLUE = (30, 64, 120)
ACCENT = (59, 130, 246)
LIGHT = (240, 245, 252)
RED = (180, 50, 50)
GREY = (100, 110, 125)
WHITE = (255, 255, 255)
BLACK = (25, 30, 40)

ML, MR, MT, MB = 12, 12, 10, 12
BODY = 10.5
TABLE = 9.5
ROW_H = 8.0


def bi(en: str, hi: str) -> str:
    return f"{en}  |  {hi}"


def ensure_logo() -> Path:
    if not LOGO.exists():
        subprocess.run([sys.executable, str(ROOT / "scripts" / "create_logo.py")], check=True)
    return LOGO


class Report(FPDF):
    def __init__(self) -> None:
        super().__init__(orientation="P", unit="mm", format="A4")
        self.set_margins(ML, MT, MR)
        self.set_auto_page_break(auto=True, margin=MB)
        self.add_font("Nirmala", "", str(HINDI_REG))
        self.add_font("Nirmala", "B", str(HINDI_BOLD))

    def footer(self):
        self.set_y(-10)
        self.use_hi(8)
        self.set_text_color(*GREY)
        self.cell(0, 5, bi(f"Page {self.page_no()}", f"पृष्ठ {self.page_no()}"), align="C")

    @property
    def body_w(self) -> float:
        return self.w - ML - MR

    def use_en(self, size: float = BODY, bold: bool = False) -> None:
        self.set_font("Helvetica", "B" if bold else "", size)

    def use_hi(self, size: float = BODY, bold: bool = False) -> None:
        self.set_font("Nirmala", "B" if bold else "", size)

    def check_space(self, h: float) -> None:
        if self.get_y() + h > self.h - MB:
            self.add_page()

    def cover(self) -> None:
        self.add_page()
        logo = ensure_logo()
        self.set_fill_color(*BLUE)
        self.rect(0, 0, self.w, 58, style="F")
        self.image(str(logo), x=ML, y=10, w=28)
        self.set_xy(ML + 32, 14)
        self.use_en(24, bold=True)
        self.set_text_color(*WHITE)
        self.cell(self.body_w - 32, 10, "Vedant Swing")
        self.set_xy(ML + 32, 26)
        self.use_hi(12, bold=True)
        self.cell(self.body_w - 32, 7, "वेदांत स्विंग - उपयोगकर्ता गाइड")
        self.set_xy(ML + 32, 36)
        self.use_en(9, bold=True)
        self.cell(self.body_w - 32, 5, "https://vedant-swing-web.onrender.com")
        self.set_xy(ML + 32, 44)
        self.use_hi(8)
        self.cell(self.body_w - 32, 5, "Nifty 500 स्विंग ट्रेडिंग ऐप")

        y = 66
        boxes = [
            (bi("Market", "बाजार"), "India NSE"),
            (bi("Universe", "स्टॉक"), "Nifty 500"),
            (bi("Style", "शैली"), "Swing 3-7d"),
            (bi("Paper", "पेपर"), "Rs.5,00,000"),
        ]
        bw = (self.body_w - 9) / 4
        for i, (label, val) in enumerate(boxes):
            x = ML + i * (bw + 3)
            self.set_fill_color(*LIGHT)
            self.rect(x, y, bw, 20, style="F")
            self.set_xy(x + 2, y + 3)
            self.use_hi(7.5)
            self.set_text_color(*GREY)
            self.multi_cell(bw - 4, 3.5, label, align="C")
            self.set_xy(x + 2, y + 12)
            self.use_en(10, bold=True)
            self.set_text_color(*BLACK)
            self.cell(bw - 4, 5, val, align="C")

        self.set_xy(ML, y + 26)
        self.use_hi(BODY)
        self.set_text_color(*BLACK)
        self.multi_cell(self.body_w, 5.5, bi(
            "Practical guide for every screen, button and daily workflow.",
            "हर स्क्रीन, बटन और दैनिक कार्य की व्यावहारिक गाइड।",
        ))

    def section(self, title_en: str, title_hi: str, subtitle: str = "") -> None:
        self.check_space(18)
        self.set_fill_color(*BLUE)
        self.set_x(ML)
        self.use_hi(13, bold=True)
        self.set_text_color(*WHITE)
        self.cell(self.body_w, 9, f"  {bi(title_en, title_hi)}", new_x="LMARGIN", new_y="NEXT", fill=True)
        if subtitle:
            self.ln(1)
            self.use_hi(9)
            self.set_text_color(*GREY)
            self.set_x(ML)
            self.multi_cell(self.body_w, 4.5, subtitle)
        self.ln(2)

    def subsection(self, title_en: str, title_hi: str) -> None:
        self.check_space(10)
        self.use_hi(11, bold=True)
        self.set_text_color(*ACCENT)
        self.set_x(ML)
        self.cell(self.body_w, 6, bi(title_en, title_hi), new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullets(self, items: list[tuple[str, str]]) -> None:
        for en, hi in items:
            self.check_space(8)
            self.set_x(ML + 2)
            self.use_en(BODY, bold=True)
            self.set_text_color(*ACCENT)
            self.cell(5, 5.5, "-")
            self.use_hi(BODY)
            self.set_text_color(*BLACK)
            self.multi_cell(self.body_w - 7, 5.5, bi(en, hi))

    def numbered(self, items: list[tuple[str, str]]) -> None:
        for i, (en, hi) in enumerate(items, 1):
            self.check_space(8)
            self.set_x(ML + 2)
            self.use_en(BODY, bold=True)
            self.set_text_color(*BLUE)
            self.cell(7, 5.5, f"{i}.")
            self.use_hi(BODY)
            self.set_text_color(*BLACK)
            self.multi_cell(self.body_w - 9, 5.5, bi(en, hi))

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
        if widths is None:
            widths = [self.body_w / len(headers)] * len(headers)
        self.check_space(ROW_H * (len(rows) + 2))
        self.use_hi(TABLE, bold=True)
        self.set_fill_color(*BLUE)
        self.set_text_color(*WHITE)
        self.set_x(ML)
        for h, w in zip(headers, widths):
            self.cell(w, ROW_H, h, border=1, fill=True, align="C")
        self.ln()
        self.use_hi(TABLE)
        self.set_text_color(*BLACK)
        for ri, row in enumerate(rows):
            self.set_x(ML)
            fill = ri % 2 == 0
            if fill:
                self.set_fill_color(*LIGHT)
            for cell, w in zip(row, widths):
                self.cell(w, ROW_H, cell, border=1, fill=fill, align="L")
            self.ln()
        self.ln(2)

    def info_box(self, title_en: str, title_hi: str, text_en: str, text_hi: str) -> None:
        self.check_space(28)
        y = self.get_y()
        self.set_fill_color(*LIGHT)
        self.rect(ML, y, self.body_w, 26, style="F")
        self.set_draw_color(*ACCENT)
        self.rect(ML, y, 3, 26, style="F")
        self.set_xy(ML + 5, y + 3)
        self.use_hi(10, bold=True)
        self.set_text_color(*ACCENT)
        self.cell(self.body_w - 8, 5, bi(title_en, title_hi))
        self.set_xy(ML + 5, y + 10)
        self.use_hi(BODY)
        self.set_text_color(*BLACK)
        self.multi_cell(self.body_w - 10, 5, bi(text_en, text_hi))
        self.set_y(y + 28)

    def warn_box(self, text_en: str, text_hi: str) -> None:
        self.info_box("Important", "महत्वपूर्ण", text_en, text_hi)


def build_report() -> Report:
    pdf = Report()
    pdf.cover()

    pdf.add_page()
    pdf.section("Quick Start", "त्वरित शुरुआत", bi(
        "Get the app on your phone in 2 minutes",
        "2 मिनट में फोन पर ऐप लगाएं",
    ))
    pdf.numbered([
        (bi("Open app URL in Chrome or Safari", "Chrome/Safari में लिंक खोलें"),
         "vedant-swing-web.onrender.com"),
        (bi("Menu -> Add to Home screen", "मेनू -> होम स्क्रीन में जोड़ें"),
         bi("Works like a real app", "असली ऐप जैसा")),
        (bi("First load may take 30-60 sec", "पहली बार 30-60 सेकंड"),
         bi("Cloud wake-up time", "सर्वर जागने में समय")),
        (bi("Tap Refresh if data is old", "पुराना डेटा हो तो रिफ्रेश"),
         bi("Top-right button", "ऊपर दाएं बटन")),
    ])
    pdf.ln(2)
    pdf.subsection("Top Bar", "ऊपरी पट्टी")
    pdf.table(
        [bi("Item", "विकल्प"), bi("Use", "उपयोग")],
        [
            [bi("Refresh", "रिफ्रेश"), bi("Reload all data", "सारा डेटा रीलोड")],
            [bi("Subtitle", "सूचना"), bi("Watchlist | Alerts | Time", "वॉचलिस्ट | अलर्ट | समय")],
            [bi("Market pill", "बाजार"), bi("Nifty BULLISH/BEARISH + 20d %", "निफ्टी मूड + 20 दिन %")],
        ],
        [42, pdf.body_w - 42],
    )

    pdf.section("App Tabs", "ऐप टैब")
    pdf.table(
        [bi("Tab", "टैब"), bi("Hindi", "हिंदी"), bi("Main use", "मुख्य काम")],
        [
            ["Home", "होम", bi("Search, chart, scan", "खोज, चार्ट, स्कैन")],
            ["Watch", "वॉचलिस्ट", bi("Favourite stocks", "पसंदीदा शेयर")],
            ["Paper", "पेपर", bi("Virtual Rs.5L trading", "अभ्यास ट्रेडिंग")],
            ["Journal", "जर्नल", bi("Trade plan + R:R", "ट्रेड योजना")],
            ["Alerts", "अलर्ट", bi("Price above/below", "कीमत अलर्ट")],
        ],
        [22, 28, pdf.body_w - 50],
    )

    pdf.add_page()
    pdf.section("Home Tab", "होम टैब", bi("Main research screen", "मुख्य शोध स्क्रीन"))

    pdf.subsection("Search Stock", "शेयर खोजें")
    pdf.bullets([
        (bi("Symbol box: NSE name", "सिंबल बॉक्स: NSE नाम"), bi("TITAN, RELIANCE, M&M", "उदाहरण")),
        (bi("Analyze button", "विश्लेषण बटन"), bi("Full technical score", "पूरा स्कोर")),
        (bi("Quick chips", "त्वरित बटन"), bi("One-tap popular stocks", "लोकप्रिय शेयर")),
    ])

    pdf.subsection("Price Chart", "कीमत चार्ट")
    pdf.table(
        [bi("Btn", "बटन"), bi("Period", "अवधि"), bi("Type", "प्रकार")],
        [
            ["1D", bi("Today", "आज"), bi("5 min", "5 मिनट")],
            ["5D", bi("5 days", "5 दिन"), bi("15 min", "15 मिनट")],
            ["1M", bi("1 month", "1 महीना"), "Daily"],
            ["6M", bi("6 months", "6 महीने"), "Daily"],
            ["1Y", bi("1 year", "1 साल"), "Daily"],
            ["MAX", bi("Full", "पूरा"), "Weekly"],
        ],
        [14, 40, pdf.body_w - 54],
    )

    pdf.subsection("Analysis Card", "विश्लेषण कार्ड")
    pdf.table(
        [bi("Button", "बटन"), bi("Action", "काम")],
        [
            [bi("+ Watchlist", "+ वॉचलिस्ट"), bi("Save to Watch tab", "सूची में जोड़ें")],
            [bi("+ Alert", "+ अलर्ट"), bi("Open alert form", "अलर्ट फॉर्म")],
            [bi("Paper Buy", "पेपर खरीद"), bi("Virtual buy + message", "अभ्यास खरीद")],
            [bi("Journal", "जर्नल"), bi("Fill trade plan", "योजना भरें")],
        ],
        [48, pdf.body_w - 48],
    )

    pdf.subsection("Evening Scan", "शाम की स्कैन")
    pdf.bullets([
        (bi("Auto 3:45 PM IST", "ऑटो 3:45 बजे"), bi("Nifty 500 scan", "500 स्टॉक स्कैन")),
        (bi("Run now", "अभी चलाएं"), bi("Manual scan", "मैन्युअल स्कैन")),
        (bi("Tap stock row", "पंक्ति दबाएं"), bi("Open analysis", "विश्लेषण खोलें")),
    ])

    pdf.add_page()
    pdf.section("Watch Tab", "वॉचलिस्ट टैब")
    pdf.bullets([
        (bi("Add symbol", "सिंबल जोड़ें"), bi("Build your list", "सूची बनाएं")),
        (bi("Tap stock", "शेयर दबाएं"), bi("Analyze on Home", "होम पर विश्लेषण")),
        (bi("Remove", "हटाएं"), bi("Delete from list", "सूची से हटाएं")),
    ])

    pdf.section("Paper Tab", "पेपर ट्रेडिंग")
    pdf.table(
        [bi("Item", "विकल्प"), bi("Details", "विवरण")],
        [
            [bi("Cash", "नकद"), bi("Virtual money left", "बची राशि")],
            [bi("Sell", "बेचें"), bi("Enter exit price", "बिक्री कीमत")],
            [bi("Place buy", "खरीदें"), bi("Symbol, qty, price", "सिंबल, मात्रा, कीमत")],
        ],
        [40, pdf.body_w - 40],
    )
    pdf.warn_box(
        bi("One stock = one position. Sell first before rebuy.", "एक शेयर एक बार। दोबारा खरीद से पहले बेचें।"),
        bi("Not connected to demat account.", "डीमैट से जुड़ा नहीं।"),
    )

    pdf.section("Journal Tab", "जर्नल टैब")
    pdf.table(
        [bi("Field", "फ़ील्ड"), bi("Meaning", "अर्थ")],
        [
            [bi("Entry", "प्रवेश"), bi("Buy price plan", "खरीद कीमत")],
            [bi("Stop", "स्टॉप"), bi("Loss limit", "नुकसान सीमा")],
            [bi("Target", "लक्ष्य"), bi("Profit goal", "मुनाफा लक्ष्य")],
            [bi("R:R", "जोखिम:लाभ"), bi("Risk reward ratio", "अनुपात")],
        ],
        [38, pdf.body_w - 38],
    )

    pdf.section("Alerts Tab", "अलर्ट टैब")
    pdf.bullets([
        (bi("Price above", "ऊपर कीमत"), bi("Alert when price rises", "बढ़ने पर सूचना")),
        (bi("Price below", "नीचे कीमत"), bi("Alert when price falls", "गिरने पर सूचना")),
        (bi("Check now", "अभी जांचें"), bi("Manual alert check", "तुरंत जांच")),
    ])

    pdf.add_page()
    pdf.section("Signals", "संकेत")
    pdf.table(
        [bi("Signal", "संकेत"), bi("Meaning", "अर्थ"), bi("Action", "कार्रवाई")],
        [
            ["STRONG BUY", bi("Best setup", "सबसे अच्छा"), bi("Review first", "पहले देखें")],
            ["BUY", bi("Good entry", "अच्छी एंट्री"), bi("Watchlist/Paper", "सूची/पेपर")],
            ["WATCH", bi("Wait", "प्रतीक्षा"), bi("Not yet", "अभी नहीं")],
            ["AVOID", bi("Skip", "छोड़ें"), bi("No trade", "ट्रेड नहीं")],
        ],
        [30, 55, pdf.body_w - 85],
    )

    pdf.section("Daily Routine IST", "दैनिक दिनचर्या")
    pdf.table(
        [bi("Time", "समय"), bi("Action", "काम")],
        [
            ["9:00 AM", bi("Morning research auto", "सुबह रिपोर्ट")],
            ["9:15 AM", bi("Check Alerts tab", "अलर्ट देखें")],
            ["3:45 PM", bi("Evening scan auto", "शाम स्कैन")],
            ["4:00 PM", bi("Review setups on Home", "सेटअप देखें")],
            ["4:30 PM", bi("Paper trade or Journal", "पेपर/जर्नल")],
        ],
        [28, pdf.body_w - 28],
    )

    pdf.section("Toast Messages", "संदेश रंग")
    pdf.table(
        [bi("Color", "रंग"), bi("Meaning", "अर्थ")],
        [
            [bi("Green", "हरा"), bi("Success - buy done", "सफल")],
            [bi("Red", "लाल"), bi("Error - duplicate buy", "त्रुटि")],
            [bi("Grey", "धूसर"), bi("Loading / scan running", "लोड हो रहा")],
        ],
        [30, pdf.body_w - 30],
    )

    pdf.warn_box(
        bi("DISCLAIMER: Not SEBI advice. Research tool only. Trade at your own risk.",
           "अस्वीकरण: SEBI सलाह नहीं। केवल शोध। जोखिम आपका।"),
        bi("Personal use only.", "केवल व्यक्तिगत उपयोग।"),
    )

    return pdf


def main() -> int:
    pdf = build_report()
    pdf.output(str(OUT))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())