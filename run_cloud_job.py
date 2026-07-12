#!/usr/bin/env python3
"""Morning job: news + research + BUY scan or position update -> Telegram."""

from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG_FILE = BASE_DIR / "config.json"
REPORT_DIR = BASE_DIR / "data" / "reports"


def load_config() -> dict:
    return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))


def get_benchmark() -> dict:
    from technical import fetch_ohlcv

    df = fetch_ohlcv("NIFTYBEES", days=60)
    if df is None:
        df = fetch_ohlcv("^NSEI", days=60)
    if df is None or len(df) < 21:
        return {"mood": "NEUTRAL", "change_20d": 0}
    chg = float((df["Close"].iloc[-1] / df["Close"].iloc[-21] - 1) * 100)
    mood = "BULLISH" if chg > 2 else "BEARISH" if chg < -2 else "NEUTRAL"
    return {"mood": mood, "change_20d": round(chg, 2)}


def save_report(text: str) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    (REPORT_DIR / f"signal_{stamp}.txt").write_text(text, encoding="utf-8")
    (REPORT_DIR / f"morning_research_{stamp}.txt").write_text(text, encoding="utf-8")


def run_morning_research(cfg: dict, benchmark: dict) -> tuple[list, list, dict, str]:
    from news_fetcher import fetch_news
    from scanner import scan_universe
    from stock_universe import get_universe

    print("[News] Fetching headlines...")
    universe = get_universe()
    news = fetch_news(
        cfg.get("news_sources", []),
        universe["all"],
        cfg.get("news_max_age_hours", 48),
    )

    print("[Scan] Technical + news scoring...")
    all_scored = scan_universe(
        universe["all"],
        set(universe["nifty50"]),
        news_by_symbol=news["by_symbol"],
    )

    top_n = cfg.get("top_research_picks", 5)
    research_picks = [
        r for r in all_scored if r.get("signal") in ("BUY", "STRONG BUY", "WATCH")
    ][:top_n]

    from sector_strength import format_sector_report
    sector_report = format_sector_report(cfg.get("sector_top_n", 5) + 3)

    ai_summary = ""
    from pa_config import is_ai_enabled

    if is_ai_enabled():
        from ai_analyst import generate_morning_briefing

        print("[Groq] Generating AI morning brain report...", flush=True)
        ai_summary = generate_morning_briefing(
            research_picks,
            news["market_headlines"],
            benchmark,
            sector_report,
            news_total=news.get("total", 0),
        )
        if ai_summary:
            print(f"  [Groq] Morning AI ready ({len(ai_summary)} chars)", flush=True)
        else:
            print("  [Groq] WARNING: Morning AI empty — check GROQ_API_KEY on Render", flush=True)
    else:
        print("  [Groq] AI disabled in config", flush=True)

    from morning_report import save_morning_report
    txt_path, _ = save_morning_report(
        research_picks,
        all_scored,
        benchmark,
        {"total": news["total"]},
        news["market_headlines"],
        ai_summary,
        universe.get("source", "Nifty 50 + Next 50"),
        sector_report=sector_report,
    )
    print(f"  Research saved: {txt_path}")
    return all_scored, research_picks, news, ai_summary


def build_position_signal(benchmark: dict, news: dict | None = None) -> str:
    from ai_analyst import analyze_position
    from nse_data import nse_quote
    from strategy import evaluate_position, load_position
    from telegram_notify import format_position

    pos = load_position()
    if not pos:
        return ""

    quote = nse_quote(pos.symbol)
    if not quote or quote.get("ltp", 0) <= 0:
        return f"Could not fetch price for {pos.symbol}"

    signal = evaluate_position(quote["ltp"], pos)
    ai_note = analyze_position(signal, pos.symbol)
    msg = format_position(signal, pos.symbol)
    if ai_note:
        msg += f"\n\nAI: {ai_note}"
    if news and news.get("market_headlines"):
        msg += "\n\nMarket headlines:"
        for h in news["market_headlines"][:3]:
            msg += f"\n  - {h.get('title', '')[:80]}"
    return msg


def build_buy_signal(benchmark: dict, cfg: dict, all_scored: list) -> str:
    """Recommend-only: confidence-gated picks, no broker orders."""
    from recommender import build_recommendations, format_recommendation_message
    from scanner import log_buy_signal

    rec = build_recommendations(
        scored=all_scored,
        source="morning",
        auto_paper=cfg.get("auto_paper_trade", True),
    )
    picks = rec.get("recommendations") or []

    if not picks:
        return format_recommendation_message(rec)

    top = picks[0]
    try:
        log_buy_signal(top["symbol"], top.get("swing_score", 0), top.get("price", 0))
    except Exception:
        pass

    # AI explanation for top pick only (narrative, not order)
    ai_note = ""
    try:
        from ai_analyst import analyze_buy
        from pa_config import is_ai_enabled

        if is_ai_enabled():
            ai_note = analyze_buy(top, benchmark) or ""
    except Exception:
        pass

    msg = format_recommendation_message(rec)
    if ai_note:
        msg += f"\n\n── AI NOTE (top pick) ──\n{ai_note}"
    if rec.get("paper"):
        paper_ok = [p for p in rec["paper"] if p.get("ok")]
        if paper_ok:
            msg += "\n\nPaper auto-buy: " + ", ".join(p["symbol"] for p in paper_ok)
    return msg


def main() -> int:
    from market_calendar import is_trading_day
    from morning_digest import build_combined_morning
    from pa_config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID
    from strategy import load_position
    from telegram_commands import process_commands
    from telegram_send import send_message

    print("=" * 50)
    print("Stock Analyst Cloud —", datetime.now().isoformat())

    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
        return 1

    try:
        cmds = process_commands()
        if cmds:
            print(f"Processed {cmds} Telegram command(s)")

        if not is_trading_day():
            print("Not a trading day — commands only, no market scan.")
            return 0

        from market_calendar import ist_now, is_manual_run, should_run_morning_job

        if not should_run_morning_job() and not is_manual_run():
            print(
                f"Outside morning window (IST {ist_now().strftime('%H:%M')}) — "
                "no scan, no Telegram."
            )
            return 0

        cfg = load_config()
        benchmark = get_benchmark()
        print(f"Market: {benchmark['mood']} {benchmark['change_20d']:+.1f}%")

        all_scored, research_picks, news, ai_summary = run_morning_research(cfg, benchmark)

        if load_position():
            trading_signal = build_position_signal(benchmark, news)
        else:
            trading_signal = build_buy_signal(benchmark, cfg, all_scored)

        combined = build_combined_morning(
            cfg, benchmark, research_picks, trading_signal, ai_summary
        )
        save_report(combined)

        from market_calendar import mark_morning_sent, should_send_morning_telegram

        if should_send_morning_telegram():
            if send_message(combined):
                mark_morning_sent()
                print("  Combined morning briefing sent to Telegram")
            else:
                print("  Telegram send FAILED")
        else:
            print(
                "  Morning report saved — Telegram skipped "
                f"(IST {datetime.now().strftime('%H:%M')}, outside morning window or already sent)"
            )

        print("[OK] Job complete")
        return 0

    except Exception:
        err = traceback.format_exc()
        print(err)
        send_message(f"Stock Analyst CLOUD ERROR:\n{err[:3500]}")
        return 1


if __name__ == "__main__":
    sys.exit(main())