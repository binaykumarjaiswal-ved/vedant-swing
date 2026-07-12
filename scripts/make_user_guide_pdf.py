#!/usr/bin/env python3
"""Vedant Swing USER-GUIDE.pdf ΓÇö practical report layout."""

from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "USER-GUIDE.pdf"

BLUE = (30, 64, 120)
ACCENT = (59, 130, 246)
LIGHT = (240, 245, 252)
GREEN = (22, 120, 70)
RED = (180, 50, 50)
GREY = (100, 110, 125)
WHITE = (255, 255, 255)
BLACK = (25, 30, 40)

ML, MR, MT, MB = 14, 14, 12, 14


class Report(FPDF):
    def footer(self):
        self.set_y(-10)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*GREY)
        self.cell(0, 5, f"Vedant Swing User Guide  |  Page {self.page_no()}", align="C")

    @property
    def body_w(self) -> float:
        return self.w - ML - MR

    def check_space(self, h: float) -> None:
        if self.get_y() + h > self.h - MB:
            self.add_page()

    def cover(self) -> None:
        self.add_page()
        self.set_fill_color(*BLUE)
        self.rect(0, 0, self.w, 52, style="F")
        self.set_xy(ML, 16)
        self.set_font("Helvetica", "B", 22)
        self.set_text_color(*WHITE)
        self.cell(self.body_w, 10, "Vedant Swing", align="L")
        self.set_xy(ML, 28)
        self.set_font("Helvetica", "", 11)
        self.cell(self.body_w, 6, "Practical User Guide - Nifty 500 Swing Trading App", align="L")
        self.set_xy(ML, 38)
        self.set_font("Helvetica", "B", 9)
        self.cell(self.body_w, 5, "https://vedant-swing-web.onrender.com", align="L")

        y = 62
        boxes = [
            ("Market", "India NSE"),
            ("Universe", "Nifty 500"),
            ("Style", "Swing (3-7 days)"),
            ("Paper Cash", "Rs. 5,00,000"),
        ]
        bw = (self.body_w - 9) / 4
        for i, (label, val) in enumerate(boxes):
            x = ML + i * (bw + 3)
            self.set_fill_color(*LIGHT)
            self.rect(x, y, bw, 18, style="F")
            self.set_xy(x + 2, y + 3)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*GREY)
            self.cell(bw - 4, 4, label.upper())
            self.set_xy(x + 2, y + 9)
            self.set_font("Helvetica", "B", 9)
            self.set_text_color(*BLACK)
            self.cell(bw - 4, 5, val)

        self.set_xy(ML, y + 26)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        self.multi_cell(
            self.body_w,
            5,
            "This report explains every screen, button, and workflow in the Vedant Swing mobile web app. "
            "Use it as your daily reference for research, paper trading, and trade planning.",
        )

    def section(self, title: str, subtitle: str = "") -> None:
        self.check_space(16)
        self.set_fill_color(*BLUE)
        self.set_x(ML)
        self.set_font("Helvetica", "B", 11)
        self.set_text_color(*WHITE)
        self.cell(self.body_w, 8, f"  {title}", new_x="LMARGIN", new_y="NEXT", fill=True)
        if subtitle:
            self.ln(1)
            self.set_font("Helvetica", "I", 8)
            self.set_text_color(*GREY)
            self.set_x(ML)
            self.multi_cell(self.body_w, 4, subtitle)
        self.ln(2)

    def subsection(self, title: str) -> None:
        self.check_space(10)
        self.set_font("Helvetica", "B", 9.5)
        self.set_text_color(*ACCENT)
        self.set_x(ML)
        self.cell(self.body_w, 6, title, new_x="LMARGIN", new_y="NEXT")
        self.ln(1)

    def bullets(self, items: list[str]) -> None:
        self.set_font("Helvetica", "", 8.5)
        self.set_text_color(*BLACK)
        for item in items:
            self.check_space(6)
            self.set_x(ML + 2)
            self.set_font("Helvetica", "B", 8.5)
            self.set_text_color(*ACCENT)
            self.cell(4, 4.5, "-")
            self.set_font("Helvetica", "", 8.5)
            self.set_text_color(*BLACK)
            self.multi_cell(self.body_w - 6, 4.5, item)

    def numbered(self, items: list[str]) -> None:
        self.set_font("Helvetica", "", 8.5)
        for i, item in enumerate(items, 1):
            self.check_space(6)
            self.set_x(ML + 2)
            self.set_font("Helvetica", "B", 8.5)
            self.set_text_color(*BLUE)
            self.cell(6, 4.5, f"{i}.")
            self.set_font("Helvetica", "", 8.5)
            self.set_text_color(*BLACK)
            self.multi_cell(self.body_w - 8, 4.5, item)

    def table(self, headers: list[str], rows: list[list[str]], widths: list[float] | None = None) -> None:
        if widths is None:
            widths = [self.body_w / len(headers)] * len(headers)
        row_h = 6.5
        self.check_space(row_h * (len(rows) + 2))
        self.set_font("Helvetica", "B", 8)
        self.set_fill_color(*BLUE)
        self.set_text_color(*WHITE)
        self.set_x(ML)
        for h, w in zip(headers, widths):
            self.cell(w, row_h, h, border=1, fill=True, align="C")
        self.ln()
        self.set_font("Helvetica", "", 7.8)
        self.set_text_color(*BLACK)
        for ri, row in enumerate(rows):
            self.set_x(ML)
            fill = ri % 2 == 0
            if fill:
                self.set_fill_color(*LIGHT)
            for cell, w in zip(row, widths):
                self.cell(w, row_h, cell, border=1, fill=fill, align="L")
            self.ln()
        self.ln(2)

    def info_box(self, title: str, text: str, color: tuple[int, int, int] = ACCENT) -> None:
        self.check_space(22)
        y = self.get_y()
        self.set_fill_color(*LIGHT)
        self.rect(ML, y, self.body_w, 20, style="F")
        self.set_draw_color(*color)
        self.rect(ML, y, 3, 20, style="F")
        self.set_xy(ML + 5, y + 3)
        self.set_font("Helvetica", "B", 8.5)
        self.set_text_color(*color)
        self.cell(self.body_w - 8, 5, title)
        self.set_xy(ML + 5, y + 9)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*BLACK)
        self.multi_cell(self.body_w - 10, 4, text)
        self.set_y(y + 22)

    def warn_box(self, text: str) -> None:
        self.info_box("Important", text, RED)


def build_report() -> Report:
    pdf = Report(orientation="P", unit="mm", format="A4")
    pdf.set_margins(ML, MT, MR)
    pdf.set_auto_page_break(auto=True, margin=MB)

    pdf.cover()

    # --- Quick start ---
    pdf.add_page()
    pdf.section("Quick Start", "Get the app on your phone in 2 minutes")
    pdf.numbered([
        "Open https://vedant-swing-web.onrender.com in Chrome or Safari",
        'Tap menu -> "Add to Home screen" (works like a real app)',
        "First load after idle may take 30-60 seconds (cloud wake-up)",
        "Tap Refresh (top-right) if numbers look stale",
    ])
    pdf.ln(2)
    pdf.subsection("Top Bar - Always Visible")
    pdf.table(
        ["Element", "What it does"],
        [
            ["Refresh", "Reloads market mood, scans, watchlist, paper, journal, alerts"],
            ["Subtitle", "Watchlist count | Active alerts | Current time (IST)"],
            ["Market pill", "Nifty BULLISH / BEARISH / NEUTRAL + 20-day % change"],
        ],
        [45, pdf.body_w - 45],
    )

    pdf.section("App Tabs Overview")
    pdf.table(
        ["Tab", "Purpose", "Main actions"],
        [
            ["Home", "Research hub", "Search, chart, analyze, morning research"],
            ["Watch", "Track favourites", "Add/remove symbols, tap to analyze"],
            ["Paper", "Practice trades", "Virtual Rs.5L portfolio, buy/sell"],
            ["Journal", "Trade discipline", "Plan entry/stop/target, log R:R"],
            ["Alerts", "Price triggers", "Above/below alerts, history"],
        ],
        [18, 38, pdf.body_w - 56],
    )

    # --- Home tab ---
    pdf.add_page()
    pdf.section("Home Tab", "Your main research and decision screen")

    pdf.subsection("Search Stock")
    pdf.bullets([
        "Symbol box: type NSE ticker (TITAN, RELIANCE, M&M)",
        "Analyze: runs full technical scoring",
        "Quick chips: one-tap analyze for popular stocks",
    ])

    pdf.subsection("Price Chart (Google Finance style)")
    pdf.table(
        ["Button", "Period shown", "Candle type"],
        [
            ["1D", "Today", "5-minute"],
            ["5D", "Last 5 days", "15-minute"],
            ["1M", "1 month", "Daily"],
            ["3M", "3 months", "Daily"],
            ["6M", "6 months (default)", "Daily"],
            ["1Y", "1 year", "Daily"],
            ["5Y", "5 years", "Weekly"],
            ["MAX", "Full history", "Weekly"],
        ],
        [14, 42, pdf.body_w - 56],
    )
    pdf.table(
        ["Stat", "Meaning"],
        [
            ["Open / High / Low / Close", "Price range for selected period"],
            ["Volume", "K=thousands, L=lakhs, Cr=crore shares"],
            ["RSI", "Below 30 oversold | Above 70 overbought"],
            ["EMA lines", "Purple=9 | Blue=21 | Orange=50 day trend"],
        ],
        [55, pdf.body_w - 55],
    )

    pdf.subsection("Analysis Result Card")
    pdf.table(
        ["Field / Button", "Action"],
        [
            ["Signal badge", "STRONG BUY / BUY / WATCH / AVOID"],
            ["Score 0-100", "Higher = stronger swing setup"],
            ["Target +3%", "Suggested profit level for swing"],
            ["+ Watchlist", "Save stock to Watch tab"],
            ["+ Alert", "Pre-fill price alert form"],
            ["Paper Buy", "One-tap virtual buy (green=OK, red=error)"],
            ["Journal", "Pre-fill trade plan form"],
        ],
        [45, pdf.body_w - 45],
    )

    pdf.subsection("Evening Swing Scan")
    pdf.bullets([
        "Auto-runs 3:45 PM IST on trading days (Nifty 500 scan)",
        "Run now: manual scan when you want fresh setups",
        "Filters: All | Pullback 21 EMA | Breakout | Oversold Bounce",
        "Tap any row to open full stock analysis",
    ])

    pdf.info_box(
        "Position Tracker",
        "Shows one real tracked position if synced from cloud. "
        "Record Average / Record Sell logs your live trade. "
        "Empty? Use Paper tab for practice instead.",
    )

    # --- Other tabs ---
    pdf.add_page()
    pdf.section("Watch Tab", "Personal shortlist of stocks to monitor")
    pdf.bullets([
        "Add symbol + Add button to build your list",
        "Tap any stock to analyze on Home tab",
        "Remove deletes from watchlist",
        "Shortcut: Analyze stock -> + Watchlist on Home",
    ])

    pdf.section("Paper Tab", "Virtual trading - Rs. 5,00,000 starting cash")
    pdf.table(
        ["Item", "Details"],
        [
            ["Cash", "Remaining virtual money"],
            ["Open positions", "Stocks you hold in paper mode"],
            ["Sell", "Enter exit price -> shows profit/loss"],
            ["Place buy", "Manual buy with symbol, qty, entry, stop, target"],
        ],
        [40, pdf.body_w - 40],
    )
    pdf.warn_box(
        "One stock = one position only. Sell first before buying the same symbol again. "
        "Paper trading is NOT connected to your demat account.",
    )

    pdf.section("Journal Tab", "Plan trades before you enter - build discipline")
    pdf.table(
        ["Field", "Purpose"],
        [
            ["Entry", "Planned buy price"],
            ["Stop", "Maximum loss exit price"],
            ["Target", "Profit exit price"],
            ["R:R preview", "Risk-reward ratio (aim for 2:1 or better)"],
            ["Close", "Mark trade finished with actual exit price"],
        ],
        [35, pdf.body_w - 35],
    )

    pdf.section("Alerts Tab", "Know when price hits your level")
    pdf.bullets([
        "Price above: alert when stock crosses level upward",
        "Price below: alert when stock falls under level",
        "Check alerts now: manual trigger (auto every 30 min on cloud)",
        "Alert History: see past triggered alerts",
    ])

    # --- Reference ---
    pdf.add_page()
    pdf.section("Signal Reference", "How to read analysis badges")
    pdf.table(
        ["Signal", "Meaning", "Action"],
        [
            ["STRONG BUY", "Best setups - multiple signals align", "Priority review"],
            ["BUY", "Good swing entry", "Consider for watchlist/paper"],
            ["WATCH", "Not ready yet", "Wait for better entry"],
            ["AVOID", "Weak or against trend", "Skip"],
        ],
        [28, 62, pdf.body_w - 90],
    )

    pdf.subsection("Swing Score Guide")
    pdf.table(
        ["Score", "Quality"],
        [
            ["70+", "Strong candidate"],
            ["62-69", "Acceptable (scan minimum)"],
            ["Below 62", "Usually filtered out"],
        ],
        [30, pdf.body_w - 30],
    )

    pdf.section("3 Evening Scan Strategies")
    pdf.table(
        ["Strategy", "When to use", "Idea"],
        [
            ["Pullback 21 EMA", "Uptrend dip", "Buy near 21-day average, RSI 40-55"],
            ["Breakout", "Momentum", "Price breaks tight range with volume"],
            ["Oversold Bounce", "Quick bounce", "RSI low but trend still up (higher risk)"],
        ],
        [38, 32, pdf.body_w - 70],
    )

    pdf.section("Daily Routine (IST)", "Suggested workflow - no laptop needed")
    pdf.table(
        ["Time", "Action"],
        [
            ["9:00 AM", "Morning research runs on cloud automatically"],
            ["9:15 AM", "Open app -> check Alerts tab"],
            ["10:00 AM", "Analyze watchlist stocks, check chart timeframes"],
            ["3:45 PM", "Evening Nifty 500 scan runs automatically"],
            ["4:00 PM", "Review Evening Scan on Home tab"],
            ["4:30 PM", "Shortlist -> Watchlist -> Paper or Journal"],
        ],
        [28, pdf.body_w - 28],
    )

    pdf.section("Toast Messages", "Bottom popup feedback")
    pdf.table(
        ["Color", "Meaning", "Examples"],
        [
            ["Green", "Success", "Bought 10 TCS, added to watchlist"],
            ["Red", "Error", "Already holding stock, insufficient cash"],
            ["Grey", "Info", "Scan running, loading data"],
        ],
        [18, 28, pdf.body_w - 46],
    )

    pdf.ln(2)
    pdf.info_box(
        "Phase 2 (Coming later)",
        "Angel One broker link | Email alerts (SETUP_GMAIL_ALERTS.txt) | Telegram notifications",
    )
    pdf.warn_box(
        "DISCLAIMER: Vedant Swing is a personal research tool. Not SEBI-registered advice. "
        "Not financial advice. Trade at your own risk.",
    )

    return pdf


def main() -> int:
    pdf = build_report()
    pdf.output(str(OUT))
    print(str(OUT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
