"""Vedant Swing web API — cloud + local."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CONFIG = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))

from pa_config import is_ai_enabled  # noqa: E402
DATA_DIR = ROOT / "data"
REPORTS_DIR = DATA_DIR / "reports"
if not REPORTS_DIR.exists():
    REPORTS_DIR = ROOT / "reports"


def _sync():
    try:
        from cloud_sync import pull_state
        pull_state()
    except Exception:
        pass


def _benchmark() -> dict:
    from technical import fetch_ohlcv

    df = fetch_ohlcv("NIFTYBEES", days=60)
    if df is None:
        df = fetch_ohlcv("^NSEI", days=60)
    if df is None or len(df) < 21:
        return {"mood": "NEUTRAL", "change_20d": 0}
    chg = float((df["Close"].iloc[-1] / df["Close"].iloc[-21] - 1) * 100)
    mood = "BULLISH" if chg > 2 else "BEARISH" if chg < -2 else "NEUTRAL"
    return {"mood": mood, "change_20d": round(chg, 2)}


def _latest_report_path() -> Path | None:
    from market_calendar import ist_now

    today = ist_now().strftime("%Y-%m-%d")
    today_file = REPORTS_DIR / f"morning_research_{today}.txt"
    if today_file.exists():
        return today_file
    files = sorted(REPORTS_DIR.glob("morning_research_*.txt"), reverse=True)
    return files[0] if files else None


def _report_meta(report_date: str) -> dict:
    from datetime import datetime as dt

    from market_calendar import get_market_context, ist_now

    today = ist_now().strftime("%Y-%m-%d")
    if not report_date:
        return {
            "report_date": "",
            "report_display": "",
            "is_today": False,
            "age_days": 0,
            "stale": False,
            "next_auto": "Mon–Fri 8:30–10:30 AM IST",
        }
    try:
        rd = dt.strptime(report_date, "%Y-%m-%d").date()
        td = dt.strptime(today, "%Y-%m-%d").date()
        age = (td - rd).days
    except ValueError:
        age = 0
    ctx = get_market_context()
    is_today = report_date == today
    return {
        "report_date": report_date,
        "report_display": dt.strptime(report_date, "%Y-%m-%d").strftime("%d %b %Y"),
        "is_today": is_today,
        "age_days": age,
        "stale": age > 0,
        "next_auto": "Next trading day 8:30 AM IST" if not ctx.get("trading_day") else (
            "Today 8:30–10:30 AM IST" if not is_today else "Ready for today"
        ),
    }


def _extract_groq_morning(text: str) -> str:
    marker = "── GROQ AI MORNING BRAIN ──"
    if marker not in text:
        legacy = "── AI MORNING BRIEFING ──"
        if legacy in text:
            marker = legacy
        else:
            return ""
    chunk = text.split(marker, 1)[1]
    for end in ("── TOP RESEARCH PICKS", "── DISCLAIMER", "── MARKET HEADLINES"):
        if end in chunk:
            chunk = chunk.split(end, 1)[0]
    return chunk.strip()


def _parse_top_picks(text: str) -> list[dict]:
    picks = []
    blocks = re.split(r"(?=^#\d+\s)", text, flags=re.MULTILINE)
    for block in blocks:
        m = re.match(r"#(\d+)\s+(\w+)\s+\(([^)]+)\)\s+—\s+Rs\.([\d.]+)", block)
        if not m:
            continue
        meta = [p.strip() for p in m.group(3).split("|")]
        index_group = meta[0] if meta else m.group(3)
        sector = meta[1] if len(meta) > 1 else ""
        signal_m = re.search(r"Signal:\s+(\S+(?:\s+\S+)?)\s+\|\s+Score:\s+(\d+)/100", block)
        target_m = re.search(r"Target \+3%:\s+Rs\.([\d.]+)", block)
        pe_m = re.search(r"PE\s+([\d.]+|—)", block)
        sr_m = re.search(r"Support Rs\.([\d.]+|—)\s+\|\s+Resistance Rs\.([\d.]+|—)", block)
        pe_raw = pe_m.group(1) if pe_m else "—"
        picks.append({
            "rank": int(m.group(1)),
            "symbol": m.group(2),
            "index_group": index_group,
            "sector": sector,
            "price": float(m.group(4)),
            "signal": signal_m.group(1) if signal_m else "—",
            "score": int(signal_m.group(2)) if signal_m else 0,
            "target": float(target_m.group(1)) if target_m else 0,
            "pe": float(pe_raw) if pe_raw != "—" else None,
            "support": float(sr_m.group(1)) if sr_m and sr_m.group(1) != "—" else None,
            "resistance": float(sr_m.group(2)) if sr_m and sr_m.group(2) != "—" else None,
        })
    return picks[: CONFIG.get("top_research_picks", 5)]


def get_dashboard() -> dict:
    _sync()
    scan_info = {"today_ready": False, "scan_running": False, "scan_message": ""}
    try:
        from web_morning import get_scan_status, report_exists_for_today, run_morning_if_needed

        if not report_exists_for_today():
            result = run_morning_if_needed(background=True)
            scan_info = {
                "today_ready": report_exists_for_today(),
                "scan_running": result.get("started") or get_scan_status().get("running"),
                "scan_message": result.get("message", ""),
                "scan_source": "render",
            }
        else:
            scan_info = {"today_ready": True, "scan_running": False, "scan_message": "Report ready"}
    except Exception:
        pass

    from nse_data import nse_quote
    from strategy import CONFIG as STRAT_CFG, evaluate_position, load_position

    benchmark = _benchmark()
    report_path = _latest_report_path()
    report_date = ""
    report_preview = ""
    top_picks: list[dict] = []

    report_meta = _report_meta("")
    ai_morning_briefing = ""
    if report_path:
        report_date = report_path.stem.replace("morning_research_", "")
        report_meta = _report_meta(report_date)
        text = report_path.read_text(encoding="utf-8")
        ai_morning_briefing = _extract_groq_morning(text)
        if not ai_morning_briefing:
            ai_file = REPORTS_DIR / f"morning_ai_{report_date}.txt"
            if ai_file.exists():
                ai_morning_briefing = ai_file.read_text(encoding="utf-8").strip()
        report_preview = ai_morning_briefing or text[:1200]
        top_picks = _parse_top_picks(text)

    position_data = None
    pos = load_position()
    if pos:
        quote = nse_quote(pos.symbol)
        ltp = quote.get("ltp", 0) if quote else 0
        signal = evaluate_position(ltp, pos) if ltp > 0 else None
        position_data = {
            "symbol": pos.symbol,
            "qty": pos.total_qty,
            "avg_price": round(pos.avg_price, 2),
            "invested": round(pos.total_invested, 2),
            "opened": pos.opened,
            "averages": f"{pos.average_count}/{STRAT_CFG['max_averages']}",
            "sell_target": pos.sell_target(),
            "avg_trigger": pos.next_avg_trigger(),
            "ltp": ltp,
            "change_pct": quote.get("change_pct", 0) if quote else 0,
            "pnl_pct": round(pos.pnl_pct(ltp), 2) if ltp else 0,
            "signal": signal["signal"] if signal else "—",
            "signal_reason": signal.get("reason", "") if signal else "",
        }

    try:
        from watchlists import get_watchlist
        from alerts import list_alerts
        wl = get_watchlist("default")
        watchlist_count = len(wl.get("symbols", [])) if wl.get("ok") else 0
        active_alerts = len(list_alerts(active_only=True))
    except Exception:
        watchlist_count = 0
        active_alerts = 0

    from market_calendar import get_market_context, ist_now

    from webapp.insights import get_sector_heatmap
    from web_notify import is_telegram_configured

    ctx = get_market_context()
    recs = _latest_recs_summary()
    regime = _regime_summary()
    perf = _perf_summary()
    sentiment = _sentiment_summary(recs)
    action = _build_action_report(recs, regime, sentiment, benchmark, top_picks)

    return {
        "app": CONFIG.get("app_name", "Vedant Swing"),
        "updated": ist_now().strftime("%d %b %Y, %I:%M %p IST"),
        "market": ctx,
        "sector_heatmap": get_sector_heatmap(),
        "telegram_configured": is_telegram_configured(),
        "benchmark": benchmark,
        "watchlist_count": watchlist_count,
        "active_alerts": active_alerts,
        "strategy": {
            "profit_target_pct": CONFIG.get("profit_target_pct", 3.0),
            "loss_trigger_pct": CONFIG.get("loss_trigger_pct", 3.0),
            "hard_stop_pct": CONFIG.get("hard_stop_pct", 4.0),
            "max_averages": CONFIG.get("max_averages", 1),
            "default_investment": CONFIG.get("default_investment", 30000),
            "min_confidence": CONFIG.get("min_confidence", 68),
            "broker_integration": False,
            "mode": "recommend_only",
        },
        "position": position_data,
        "report_date": report_date,
        "report_meta": report_meta,
        "report_preview": report_preview,
        "top_picks": top_picks,
        "has_report": bool(report_path),
        "ai_morning_briefing": ai_morning_briefing,
        "has_groq_morning": bool(ai_morning_briefing),
        "scan": scan_info,
        "recommendations": recs,
        "performance": perf,
        "regime": regime,
        "sentiment": sentiment,
        "action_report": action,
        "kpis": _build_kpis(benchmark, regime, sentiment, perf, recs),
        "mode": "morning_only",
    }


def _sentiment_summary(recs: dict | None = None) -> dict:
    try:
        from sentiment_engine import market_sentiment_pulse
        pulse = market_sentiment_pulse()
        if recs and recs.get("market_sentiment"):
            # Prefer pulse stored with last recommender run if fresher fields
            pass
        return {"ok": True, **pulse}
    except Exception as exc:
        return {
            "ok": False,
            "score_100": 50,
            "label": "NEUTRAL",
            "action_hint": "Sentiment unavailable",
            "error": str(exc)[:120],
            "feed": [],
        }


def _build_kpis(benchmark, regime, sentiment, perf, recs) -> list:
    def mood_cls(v, hi=60, lo=40):
        if v is None:
            return "neutral"
        if v >= hi:
            return "good"
        if v <= lo:
            return "bad"
        return "neutral"

    conf_top = None
    if recs and recs.get("top"):
        conf_top = recs["top"][0].get("confidence")

    return [
        {
            "id": "regime",
            "label": "Market Regime",
            "value": regime.get("regime", "—"),
            "sub": f"Health {regime.get('score', '—')}/100",
            "cls": mood_cls(regime.get("score"), 70, 45),
        },
        {
            "id": "sentiment",
            "label": "News Sentiment",
            "value": sentiment.get("label", "—"),
            "sub": f"Pulse {sentiment.get('score_100', '—')}/100",
            "cls": mood_cls(sentiment.get("score_100"), 60, 40),
        },
        {
            "id": "nifty",
            "label": "Nifty 20d",
            "value": f"{benchmark.get('change_20d', 0):+.1f}%",
            "sub": benchmark.get("mood", "NEUTRAL"),
            "cls": "good" if (benchmark.get("change_20d") or 0) > 1 else (
                "bad" if (benchmark.get("change_20d") or 0) < -1 else "neutral"
            ),
        },
        {
            "id": "edge",
            "label": "Model Edge",
            "value": f"{perf.get('win_rate')}%" if perf.get("win_rate") is not None else "Building",
            "sub": f"{perf.get('outcomes') or 0} closed trades",
            "cls": mood_cls(perf.get("win_rate"), 55, 45) if perf.get("win_rate") is not None else "neutral",
        },
        {
            "id": "action",
            "label": "Today Action",
            "value": (recs.get("top") or [{}])[0].get("symbol") if recs.get("top") else "NO TRADE",
            "sub": f"Conf {conf_top}" if conf_top is not None else (recs.get("message") or "Waiting")[:40],
            "cls": "good" if recs.get("top") else "neutral",
        },
    ]


def _build_action_report(recs, regime, sentiment, benchmark, top_picks) -> dict:
    """Human-readable daily decision board."""
    top = (recs or {}).get("top") or []
    primary = top[0] if top else None
    status = "BUY" if primary else "NO_TRADE"
    if not regime.get("trade_approval", True):
        status = "BLOCKED"

    steps = []
    if status == "BLOCKED":
        steps = [
            "Market regime is weak — new buys blocked by risk rules.",
            "Review open positions only: use stop / target.",
            "Wait for regime health ≥ threshold before new entries.",
        ]
    elif status == "NO_TRADE":
        steps = [
            "No setup met confidence threshold today.",
            "Check watchlist for near-setup stocks.",
            "Do not force a trade — capital protection first.",
        ]
    else:
        steps = [
            f"Primary pick: {primary.get('symbol')} ({primary.get('signal')}).",
            f"Plan entry near Rs.{primary.get('entry')} · stop Rs.{primary.get('stop')} · target Rs.{primary.get('target')}.",
            f"Size ~{primary.get('buy_qty') or '—'} shares (risk-sized). Buy manually in broker.",
            "Bot never places broker orders. Set stop in broker after fill.",
        ]

    # Fallback research picks when no high-conf BUY
    research = top or [
        {
            "symbol": p.get("symbol"),
            "score": p.get("score"),
            "signal": p.get("signal"),
            "entry": p.get("price"),
            "confidence": None,
            "thesis": f"Research pick · score {p.get('score')}",
        }
        for p in (top_picks or [])[:5]
    ]

    return {
        "status": status,
        "headline": (
            f"BUY {primary['symbol']}" if primary and status == "BUY"
            else "NO TRADE TODAY" if status == "NO_TRADE"
            else "NEW BUYS BLOCKED"
        ),
        "primary": primary,
        "alternates": top[1:3],
        "research_picks": research[:5],
        "steps": steps,
        "sentiment_hint": sentiment.get("action_hint", ""),
        "regime_hint": regime.get("reason", ""),
        "disclaimer": "Research only. Not SEBI advice. No auto-broker orders.",
    }


def _latest_recs_summary() -> dict:
    try:
        from recommender import get_latest_recommendations

        data = get_latest_recommendations()
        if not data.get("ok"):
            return {"ok": False, "count": 0, "message": data.get("error") or data.get("message")}
        recs = data.get("recommendations") or []
        watch = data.get("watch") or []
        return {
            "ok": True,
            "date": data.get("date"),
            "count": len(recs),
            "message": data.get("message"),
            "regime": data.get("regime"),
            "market_sentiment": data.get("market_sentiment"),
            "top": [
                {
                    "symbol": r.get("symbol"),
                    "score": r.get("swing_score"),
                    "confidence": r.get("confidence"),
                    "entry": r.get("entry") or r.get("price"),
                    "target": r.get("target"),
                    "stop": r.get("stop"),
                    "target_pct": r.get("target_pct"),
                    "stop_pct": r.get("stop_pct"),
                    "buy_qty": r.get("buy_qty"),
                    "buy_amount": r.get("buy_amount"),
                    "signal": r.get("signal"),
                    "sector": r.get("sector"),
                    "rsi": r.get("rsi"),
                    "trend": r.get("trend"),
                    "thesis": r.get("thesis") or r.get("strategy_reason") or "",
                    "sentiment_label": r.get("sentiment_label"),
                    "news_sentiment": r.get("news_sentiment"),
                    "reasons": (r.get("reasons") or [])[:4],
                }
                for r in recs[:5]
            ],
            "watch": [
                {
                    "symbol": r.get("symbol"),
                    "score": r.get("swing_score"),
                    "signal": r.get("signal"),
                    "confidence": r.get("confidence"),
                }
                for r in watch[:5]
            ],
        }
    except Exception:
        return {"ok": False, "count": 0}


def _perf_summary() -> dict:
    try:
        from history_db import performance_summary

        return performance_summary(days=60)
    except Exception:
        return {"ok": False}


def _regime_summary() -> dict:
    try:
        from market_regime import market_health

        return market_health()
    except Exception:
        return {"regime": "NEUTRAL", "score": 50, "trade_approval": True}


def run_morning_scan_api(force: bool = False) -> dict:
    from web_morning import run_morning_manual

    return run_morning_manual(force=force, background=True)


def get_scan_status_api() -> dict:
    try:
        from web_morning import get_scan_status, report_exists_for_today
        return {**get_scan_status(), "today_ready": report_exists_for_today()}
    except Exception as exc:
        return {"running": False, "today_ready": False, "last_error": str(exc)}


def cron_morning_scan(secret: str) -> dict:
    import os
    from web_morning import run_morning_force

    expected = os.environ.get("CRON_SECRET", "").strip()
    if not expected or secret != expected:
        return {"ok": False, "error": "Unauthorized"}
    return {"ok": True, **run_morning_force()}


def analyze_symbol(symbol: str, with_ai: bool = True) -> dict:
    from ai_analyst import analyze_symbol_deep
    from news_fetcher import fetch_news
    from nse_data import nse_quote
    from scanner import _apply_news_score, enrich_deep
    from sector_map import get_sector
    from sector_strength import sector_filter_pass
    from stock_universe import get_universe
    from strategy import enrich_pick_with_order
    from technical import analyze_technicals, fetch_ohlcv

    symbol = symbol.upper().strip()
    if not symbol or not re.match(r"^[A-Z0-9&-]{2,20}$", symbol):
        return {"ok": False, "error": "Invalid symbol. Use NSE ticker e.g. TITAN, RELIANCE"}

    universe = get_universe()
    nifty50_set = set(universe["nifty50"])
    in_universe = symbol in universe["all"]

    nifty_df = fetch_ohlcv("NIFTYBEES", days=60)
    if nifty_df is None:
        nifty_df = fetch_ohlcv("^NSEI", days=60)

    tech = analyze_technicals(symbol, nifty_df)
    if tech.get("status") != "ok":
        return {"ok": False, "error": f"No price data for {symbol}"}

    live = nse_quote(symbol)
    if live and live.get("ltp", 0) > 0:
        enrich_pick_with_order(tech, live)
    else:
        tech["live_source"] = "history"
        tech["change_pct"] = 0
        enrich_pick_with_order(tech)

    score = tech["swing_score"]
    if tech["macd_bullish"] and 40 <= tech["rsi"] <= 62:
        score = min(100, score + 5)
    if tech["trend"] == "down":
        score = max(0, score - 8)

    news = fetch_news(
        CONFIG.get("news_sources", []),
        [symbol],
        CONFIG.get("news_max_age_hours", 48),
    )
    news_items = news["by_symbol"].get(symbol, [])
    score, news_meta = _apply_news_score(score, news_items)
    try:
        from sentiment_engine import enrich_pick_sentiment
        tech = enrich_pick_sentiment({**tech, **news_meta}, news_items)
        news_meta = {**news_meta, "sentiment_label": tech.get("sentiment_label"), "news_sentiment": tech.get("news_sentiment", news_meta.get("news_sentiment"))}
    except Exception:
        pass

    min_score = CONFIG.get("min_buy_score", 62)
    if score >= 75:
        signal = "STRONG BUY"
    elif score >= min_score:
        signal = "BUY"
    elif score >= 50:
        signal = "WATCH"
    else:
        signal = "AVOID"

    result = {
        **tech,
        **news_meta,
        "swing_score": round(score, 1),
        "signal": signal,
        "index_group": (
            "Nifty 50" if symbol in nifty50_set
            else "Nifty Next 50" if in_universe
            else "Outside Nifty 100"
        ),
        "in_universe": in_universe,
        "news_headlines": [
            {"title": n["title"], "source": n["source"], "sentiment": n["sentiment"]}
            for n in news_items[:5]
        ],
        "market_mood": _benchmark(),
    }

    enrich_deep(result)
    top_n = CONFIG.get("sector_top_n", 5)
    if CONFIG.get("sector_filter_enabled", True):
        ok, sector = sector_filter_pass(symbol, top_n)
        result["sector"] = sector
        result["sector_strong"] = ok
        if not ok:
            result["swing_score"] = max(0, result["swing_score"] - 10)
    else:
        result["sector"] = get_sector(symbol)
        result["sector_strong"] = True

    s = result["swing_score"]
    if s >= 75:
        result["signal"] = "STRONG BUY"
    elif s >= min_score:
        result["signal"] = "BUY"
    elif s >= 50:
        result["signal"] = "WATCH"
    else:
        result["signal"] = "AVOID"

    ai_note = ""
    ai_status = ""
    if with_ai and is_ai_enabled():
        ai_note = analyze_symbol_deep(result, result["market_mood"])
        if not ai_note:
            import os
            ai_status = "no_key" if not os.environ.get("GROQ_API_KEY") else "failed"
    from market_calendar import get_market_context, ist_now

    ctx = get_market_context()
    result["ai_enabled"] = is_ai_enabled()
    result["ai_note"] = ai_note
    result["ai_status"] = ai_status
    result["ok"] = True
    result["analyzed_at"] = ist_now().strftime("%d %b %Y, %I:%M %p IST")
    result["market"] = ctx
    result["price_label"] = (
        "Live LTP" if ctx["market_open"] else "Close / last price"
    )
    from webapp.insights import build_checklist, build_quick_summary, price_freshness

    result["quick_summary"] = build_quick_summary(result)
    result["checklist"] = build_checklist(result)
    result["price_freshness"] = price_freshness(symbol, ctx["market_open"])
    return result


def format_share_text(data: dict) -> str:
    if not data.get("ok"):
        return data.get("error", "Analysis failed")

    sector = data.get("sector", "")
    sector_tag = f" | {sector}" if sector else ""
    lines = [
        f"Stock Analyst AI — {data['symbol']}{sector_tag}",
        f"Signal: {data['signal']} | Score: {data['swing_score']}/100",
        f"Price: Rs.{data.get('price', 0):.2f} | Target +3%: Rs.{data.get('target', 0):.2f}",
        f"RSI {data.get('rsi')} | Trend {data.get('trend')} | vs Nifty {data.get('vs_nifty_20d', 0):+.1f}%",
    ]
    pe = data.get("pe_trailing")
    if pe:
        lines.append(f"PE {pe} | {data.get('fund_verdict', '')} | Quarter: {data.get('quarter_trend', '—')}")
    sup = data.get("support")
    res = data.get("resistance")
    if sup or res:
        lines.append(f"Support Rs.{sup or '—'} | Resistance Rs.{res or '—'}")
    if data.get("reasons"):
        lines.append("TA: " + ", ".join(data["reasons"][:3]))
    if data.get("news_summary"):
        lines.append(f"News: {data['news_summary'][:100]}")
    if data.get("ai_note"):
        lines.append(f"AI:\n{data['ai_note'][:800]}")
    lines.append("— Not SEBI advice. Trade at your own risk.")
    return "\n".join(lines)


def _save_position_to_github():
    from cloud_sync import push_position
    from strategy import POSITION_FILE

    if not POSITION_FILE.exists():
        return True
    text = POSITION_FILE.read_text(encoding="utf-8")
    return push_position(text)


def position_action(action: str, symbol: str | None = None, price: float | None = None) -> dict:
    from nse_data import nse_quote
    from strategy import (
        CONFIG as STRAT_CFG,
        add_average,
        calc_best_buy_price,
        close_position,
        load_position,
        open_position,
    )

    _sync()
    err = None
    ok = False

    if action == "buy":
        if not symbol:
            return {"ok": False, "error": "Symbol required"}
        if load_position():
            return {"ok": False, "error": f"Already holding {load_position().symbol}"}
        if not price or price <= 0:
            q = nse_quote(symbol.upper())
            if not q:
                return {"ok": False, "error": "No price"}
            price = calc_best_buy_price(q)
        open_position(symbol.upper(), price, None)
        ok = True
    elif action == "sell":
        if not load_position():
            return {"ok": False, "error": "No open position"}
        close_position()
        ok = True
    elif action == "average":
        pos = load_position()
        if not pos:
            return {"ok": False, "error": "No open position"}
        if not pos.can_average():
            return {"ok": False, "error": "Max averages reached"}
        if not price or price <= 0:
            q = nse_quote(pos.symbol)
            price = calc_best_buy_price(q) if q else 0
        if price <= 0:
            return {"ok": False, "error": "No price"}
        add_average(pos, price)
        ok = True
    elif action == "status":
        ok = True
    else:
        return {"ok": False, "error": "Unknown action"}

    if ok and action in ("buy", "sell", "average"):
        if not _save_position_to_github():
            err = "Saved locally but GitHub sync failed — check GITHUB_TOKEN on server"

    dash = get_dashboard()
    return {"ok": ok, "position": dash.get("position"), "error": err}


def list_reports() -> list[dict]:
    _sync()
    items = []
    for path in sorted(REPORTS_DIR.glob("morning_research_*.txt"), reverse=True)[:14]:
        date = path.stem.replace("morning_research_", "")
        items.append({"date": date, "size": path.stat().st_size})
    return items


def get_report(date: str) -> dict:
    _sync()
    path = REPORTS_DIR / f"morning_research_{date}.txt"
    if not path.exists():
        return {"ok": False, "error": "Report not found"}
    text = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "date": date,
        "text": text,
        "top_picks": _parse_top_picks(text),
    }
