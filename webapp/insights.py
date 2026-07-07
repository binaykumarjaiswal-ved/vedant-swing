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


def backtest_evening_scan(days: int = 30) -> dict:
    from technical import fetch_ohlcv

    if not REPORTS.exists():
        return {"ok": False, "error": "No scan reports"}

    files = sorted(REPORTS.glob("evening_scan_*.json"), reverse=True)[:days]
    if not files:
        return {"ok": True, "trades": 0, "wins": 0, "win_rate": 0, "samples": [], "note": "No evening scans yet"}

    trades = []
    ohlcv_cache: dict[str, object] = {}
    hold_days = 7

    for path in files:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        scan_date = path.stem.replace("evening_scan_", "")
        for pick in (data.get("top") or [])[:3]:
            sym = pick.get("symbol")
            entry = float(pick.get("price") or pick.get("entry") or 0)
            target = float(pick.get("target") or entry * 1.03)
            if not sym or entry <= 0:
                continue
            if sym not in ohlcv_cache:
                try:
                    ohlcv_cache[sym] = fetch_ohlcv(sym, days=hold_days + 30)
                except Exception:
                    ohlcv_cache[sym] = None
            try:
                outcome = _simulate_target(
                    ohlcv_cache[sym], scan_date, entry, target, hold_days=hold_days,
                )
            except Exception as exc:
                outcome = {"hit": False, "note": str(exc)[:40]}
            trades.append({
                "date": scan_date,
                "symbol": sym,
                "entry": round(entry, 2),
                "target": round(target, 2),
                **outcome,
            })

    if not trades:
        return {"ok": True, "trades": 0, "wins": 0, "win_rate": 0, "samples": []}

    wins = sum(1 for t in trades if t.get("hit"))
    return {
        "ok": True,
        "days": len(files),
        "trades": len(trades),
        "wins": wins,
        "win_rate": round(wins / len(trades) * 100, 1),
        "target_pct": 3.0,
        "hold_days": hold_days,
        "samples": trades[:12],
    }


def _normalize_ohlcv_index(df):
    import pandas as pd

    if df is None or df.empty:
        return df
    out = df.copy()
    idx = pd.to_datetime(out.index)
    if getattr(idx, "tz", None) is not None:
        idx = idx.tz_convert("Asia/Kolkata").tz_localize(None)
    out.index = idx.normalize()
    return out


def _simulate_target(df, start: str, entry: float, target: float, hold_days: int = 7) -> dict:
    import pandas as pd

    try:
        # Evening picks — measure from next session after scan date
        start_ts = pd.Timestamp(start) + pd.Timedelta(days=1)
    except ValueError:
        return {"hit": False, "note": "bad date"}

    if df is None or getattr(df, "empty", True):
        return {"hit": False, "note": "no data"}

    df = _normalize_ohlcv_index(df)
    forward = df[df.index >= start_ts.normalize()]
    if forward.empty:
        return {"hit": False, "note": "no forward data"}

    window = forward.head(hold_days)
    if window.empty:
        return {"hit": False, "note": "no forward data"}

    hit = bool((window["High"] >= target).any())
    max_high = float(window["High"].max())
    return {
        "hit": hit,
        "max_high": round(max_high, 2),
        "note": "Target hit" if hit else f"High Rs.{max_high:.2f}",
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


def notify_evening_scan_summary(result: dict) -> bool:
    from web_notify import send_telegram

    if not result.get("ok"):
        return False
    lines = [
        "Vedant Swing — Evening Scan",
        f"Setups: {result.get('hits', 0)} / {result.get('scanned', 0)} scanned",
        "",
    ]
    for p in (result.get("top") or [])[:5]:
        lines.append(
            f"• {p['symbol']} {p.get('signal')} {p.get('swing_score')}/100 "
            f"({p.get('strategy', '')})"
        )
    return send_telegram("\n".join(lines))