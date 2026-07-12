"""Morning research report — news + technical top picks."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

GROQ_SECTION = "── GROQ AI MORNING BRAIN ──"

BASE_DIR = Path(__file__).parent
REPORTS_DIR = BASE_DIR / "data" / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _desktop_dir() -> Path:
    for p in (Path.home() / "OneDrive" / "Desktop", Path.home() / "Desktop"):
        if p.exists():
            return p
    return Path.home() / "Desktop"


def _format_pick(rank: int, p: dict) -> list[str]:
    best = p.get("best_buy_price", p.get("entry", p.get("price", 0)))
    pe = p.get("pe_trailing") or "—"
    eps = p.get("eps_growth_pct")
    eps_s = f"{eps:+.1f}%" if eps is not None else "—"
    lines = [
        f"#{rank}  {p['symbol']}  ({p.get('index_group', 'Nifty')} | {p.get('sector', '?')})  —  Rs.{p.get('price', 0):.2f}",
        f"     Signal: {p.get('signal', 'WATCH')}  |  Score: {p.get('swing_score', 0):.0f}/100"
        + (f"  |  Conf: {p.get('confidence', 0):.0f}" if p.get("confidence") else ""),
        f"     Best buy: Rs.{best:.2f}  |  Qty: {p.get('buy_qty', 0)}  |  "
        f"Target: Rs.{p.get('target', 0):.2f} (+{p.get('target_pct', 3):.1f}%)  |  "
        f"Stop: Rs.{p.get('stop', p.get('avg_trigger', 0)):.2f}",
        f"     Technical: RSI {p.get('rsi', 0)} | Trend {p.get('trend', '?')} | vs Nifty {p.get('vs_nifty_20d', 0):+.1f}%",
        f"     Fundamentals: PE {pe} | EPS growth {eps_s} | {p.get('fund_verdict', '—')}",
        f"     Support Rs.{p.get('support', '—')} | Resistance Rs.{p.get('resistance', '—')} | {p.get('level_note', '')[:80]}",
    ]
    if p.get("reasons"):
        lines.append(f"     TA: {', '.join(p['reasons'][:3])}")
    if p.get("news_summary") and p["news_summary"] != "No recent news":
        lines.append(f"     News: {p['news_summary'][:120]}")
    return lines


def save_morning_report(
    picks: list[dict],
    all_scored: list[dict],
    benchmark: dict,
    news_stats: dict,
    market_headlines: list[dict],
    ai_summary: str,
    universe_source: str,
    sector_report: str = "",
) -> tuple[Path, Path]:
    from market_calendar import ist_now

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    now = ist_now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%d %b %Y %I:%M %p IST")

    lines = [
        "=" * 65,
        f"  VEDANT SWING — MORNING RESEARCH — {time_str}",
        "  Groq AI brain + Nifty 500 scan | Sector filter | PE + S/R + RSS news",
        "=" * 65,
        f"Market mood: {benchmark.get('mood', 'NEUTRAL')} (Nifty 20d: {benchmark.get('change_20d', 0):+.1f}%)",
        f"Stocks scanned: {len(all_scored)} | News items: {news_stats.get('total', 0)} | Universe: {universe_source}",
        "",
    ]

    if ai_summary:
        lines.extend(["", GROQ_SECTION, ai_summary, ""])
    else:
        lines.extend([
            "",
            GROQ_SECTION,
            "Groq AI report not generated — set GROQ_API_KEY on Render and ai_enabled=true.",
            "",
        ])

    if sector_report:
        lines.append(sector_report)
        lines.append("")

    lines.append("── TOP RESEARCH PICKS (technical scan) ──")

    if picks:
        for i, p in enumerate(picks, 1):
            lines.append("")
            lines.extend(_format_pick(i, p))
    else:
        lines.append("  No strong setups today.")

    if market_headlines:
        lines.extend(["", "── MARKET HEADLINES (RSS) ──"])
        for h in market_headlines[:10]:
            src = h.get("source", "")
            lines.append(f"  - [{src}] {h.get('title', '')[:110]}")

    lines.extend([
        "",
        "── DISCLAIMER ──",
        "Automated research only. NOT financial advice. Not SEBI-registered.",
        "=" * 65,
    ])

    text = "\n".join(lines)
    txt_path = REPORTS_DIR / f"morning_research_{date_str}.txt"
    txt_path.write_text(text, encoding="utf-8")

    desktop_path = _desktop_dir() / f"StockAnalyst_Research_{date_str}.txt"
    try:
        desktop_path.write_text(text, encoding="utf-8")
    except OSError:
        pass

    html_path = REPORTS_DIR / f"morning_research_{date_str}.html"
    html_path.write_text(_build_html(picks, benchmark, time_str, market_headlines, ai_summary), encoding="utf-8")

    if ai_summary:
        ai_path = REPORTS_DIR / f"morning_ai_{date_str}.txt"
        ai_path.write_text(ai_summary, encoding="utf-8")

    try:
        from email_notify import send_morning_report
        send_morning_report(text, picks, benchmark)
    except Exception as exc:
        print(f"EMAIL morning: {exc}")

    return txt_path, html_path


def _build_html(
    picks: list[dict],
    benchmark: dict,
    time_str: str,
    headlines: list[dict],
    ai_summary: str,
) -> str:
    rows = ""
    for i, p in enumerate(picks, 1):
        color = "#22c55e" if p.get("signal") in ("BUY", "STRONG BUY") else "#eab308"
        rows += f"""
        <div class="card">
          <h3>#{i} {p['symbol']} <span class="badge" style="background:{color}">{p.get('signal','')}</span></h3>
          <p>Score {p.get('swing_score',0)} | Rs.{p.get('price',0):.2f} | Target Rs.{p.get('target',0):.2f}</p>
          <p>RSI {p.get('rsi')} | {p.get('trend')} | News: {p.get('news_summary','')[:120]}</p>
        </div>"""

    hl = "".join(f"<li>{h.get('title','')[:100]}</li>" for h in headlines[:8])
    ai_block = f"<pre>{ai_summary}</pre>" if ai_summary else ""
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Stock Analyst Research</title>
<style>
body{{font-family:Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:24px;max-width:900px;margin:auto}}
h1{{color:#38bdf8}} .card{{background:#1e293b;border-radius:12px;padding:16px;margin:12px 0}}
.badge{{padding:4px 10px;border-radius:6px;font-size:12px;color:#000}}
pre{{white-space:pre-wrap;background:#1e293b;padding:16px;border-radius:8px}}
</style></head><body>
<h1>Stock Analyst Morning Research</h1>
<p>{time_str} | {benchmark.get('mood','NEUTRAL')} | Nifty 20d {benchmark.get('change_20d',0):+.1f}%</p>
{rows}
<h2>Market Headlines</h2><ul>{hl}</ul>
<h2>Groq AI Morning Brain</h2>{ai_block}
</body></html>"""