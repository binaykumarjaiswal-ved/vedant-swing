"""Analysis insights — summaries, compare, backtest, PDF, freshness."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPORTS = ROOT / "data" / "reports"
if not REPORTS.exists():
    REPORTS = ROOT / "reports"


def build_quick_summary(data: dict) -> list[str]:
    lines = []
    reasons = data.get("reasons") or []
    if reasons:
        lines.append(reasons[0])
    sector = data.get("sector", "")
    if sector:
        tag = "Sector strong" if data.get("sector_strong") else "Sector weak"
        lines.append(f"{sector} — {tag}")
    sent = data.get("news_sentiment")
    if sent is not None:
        if sent > 0.15:
            lines.append("News sentiment positive")
        elif sent < -0.15:
            lines.append("News sentiment negative")
        elif data.get("news_count", 0):
            lines.append("News neutral")
    trend = data.get("trend")
    rsi = data.get("rsi")
    if trend and rsi is not None:
        lines.append(f"Trend {trend} · RSI {rsi}")
    return lines[:3]


def build_checklist(data: dict) -> list[dict]:
    min_score = 62
    items = [
        ("score", f"Score ≥ {min_score}?", (data.get("swing_score") or 0) >= min_score),
        ("signal", "Signal BUY or STRONG BUY?", data.get("signal", "") in ("BUY", "STRONG BUY")),
        ("sector", "Sector in top 5 strong?", bool(data.get("sector_strong", True))),
        ("trend", "Trend up or sideways?", data.get("trend") in ("up", "sideways")),
        ("rsi", "RSI between 35–65?", 35 <= (data.get("rsi") or 0) <= 65),
        ("universe", "In Nifty 100 universe?", bool(data.get("in_universe"))),
    ]
    return [{"id": k, "text": t, "pass": p} for k, t, p in items]


def price_freshness(symbol: str, market_open: bool) -> dict:
    cache = ROOT / "data" / "cache" / f"quote_{symbol.upper()}.json"
    stale = False
    age_min = 0
    quoted_at = ""
    if cache.exists():
        try:
            raw = json.loads(cache.read_text(encoding="utf-8"))
            ts = datetime.fromisoformat(raw["ts"])
            age_min = int((datetime.now() - ts).total_seconds() / 60)
            quoted_at = ts.strftime("%d %b, %I:%M %p")
            if market_open and age_min > 15:
                stale = True
            if not market_open and age_min > 360:
                stale = True
        except Exception:
            stale = market_open
    elif market_open:
        stale = True
    return {
        "stale": stale,
        "age_minutes": age_min,
        "quoted_at": quoted_at,
        "warning": "Price may be delayed — tap Refresh" if stale else "",
    }


def get_sector_heatmap(top_n: int = 10) -> dict:
    from sector_strength import get_sector_rankings

    ranks = get_sector_rankings()[:top_n]
    if not ranks:
        return {"ok": False, "sectors": []}
    max_chg = max(abs(r["change_20d"]) for r in ranks) or 1
    sectors = []
    for i, r in enumerate(ranks, 1):
        sectors.append({
            **r,
            "rank": i,
            "strong": i <= 5,
            "bar_pct": min(100, int(abs(r["change_20d"]) / max_chg * 100)),
        })
    return {"ok": True, "sectors": sectors, "top_n_strong": 5}


def compare_symbols(symbol_a: str, symbol_b: str) -> dict:
    from webapp.services import analyze_symbol

    a = analyze_symbol(symbol_a.upper(), with_ai=False)
    b = analyze_symbol(symbol_b.upper(), with_ai=False)
    if not a.get("ok"):
        return {"ok": False, "error": a.get("error", f"No data for {symbol_a}")}
    if not b.get("ok"):
        return {"ok": False, "error": b.get("error", f"No data for {symbol_b}")}

    winner = a["symbol"]
    if b["swing_score"] > a["swing_score"]:
        winner = b["symbol"]
    elif b["swing_score"] == a["swing_score"]:
        winner = "tie"

    return {
        "ok": True,
        "a": _compare_row(a),
        "b": _compare_row(b),
        "winner": winner,
        "verdict": f"{winner} leads on swing score" if winner != "tie" else "Both equal score",
    }


def _compare_row(d: dict) -> dict:
    return {
        "symbol": d["symbol"],
        "signal": d["signal"],
        "score": d["swing_score"],
        "price": d.get("price"),
        "target": d.get("target"),
        "rsi": d.get("rsi"),
        "trend": d.get("trend"),
        "sector": d.get("sector"),
        "sector_strong": d.get("sector_strong"),
        "pe": d.get("pe_trailing"),
        "vs_nifty": d.get("vs_nifty_20d"),
        "summary": " · ".join(build_quick_summary(d)),
    }


def build_research_pdf(data: dict) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, f"Vedant Swing — {data.get('symbol', '')} Research", ln=True)
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 8, f"Analyzed: {data.get('analyzed_at', '')}", ln=True)
    pdf.cell(0, 8, f"Signal: {data.get('signal')} | Score: {data.get('swing_score')}/100", ln=True)
    pdf.ln(4)

    for label, key in (
        ("Price", "price"), ("Target +3%", "target"), ("RSI", "rsi"),
        ("Trend", "trend"), ("Sector", "sector"), ("PE", "pe_trailing"),
    ):
        val = data.get(key)
        if val is not None and val != "":
            pdf.cell(0, 6, f"{label}: {val}", ln=True)

    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 8, "Quick summary", ln=True)
    pdf.set_font("Helvetica", "", 10)
    for line in build_quick_summary(data):
        pdf.multi_cell(0, 5, f"- {line}")

    ai = data.get("ai_note") or ""
    if ai:
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(0, 8, "AI Deep Research", ln=True)
        pdf.set_font("Helvetica", "", 9)
        clean = re.sub(r"\*\*", "", ai)
        for para in clean.split("\n"):
            para = para.strip()
            if para:
                pdf.multi_cell(0, 4, para)
                pdf.ln(1)

    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 8)
    pdf.multi_cell(0, 4, "Not SEBI-registered advice. Trade at your own risk.")

    out = BytesIO()
    pdf.output(out)
    return out.getvalue()
