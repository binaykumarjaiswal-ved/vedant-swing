"""
Unified daily BUY recommender — recommend only, never places broker orders.

Pipeline:
  scan → regime → risk levels → confidence → top N → log → optional paper
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
OUT_DIR = BASE_DIR / "data" / "reports"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _reload_config() -> dict:
    global CONFIG
    CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    return CONFIG


def build_recommendations(
    scored: list[dict[str, Any]] | None = None,
    limit: int | None = None,
    source: str = "morning",
    auto_paper: bool | None = None,
) -> dict[str, Any]:
    """
    Produce ranked BUY recommendations with confidence and risk fields.
    """
    _reload_config()
    from market_calendar import ist_now
    from market_regime import apply_regime_to_picks, market_health
    from risk_engine import confidence_score, enrich_pick_with_risk

    day = ist_now().strftime("%Y-%m-%d")
    limit = limit or int(CONFIG.get("recommend_top_n", 3))
    min_conf = float(CONFIG.get("min_confidence", 68))
    min_score = float(CONFIG.get("min_buy_score", 65))

    regime = market_health()
    market_pulse = {}
    try:
        from sentiment_engine import market_sentiment_pulse
        market_pulse = market_sentiment_pulse()
    except Exception:
        market_pulse = {}
    try:
        from history_db import log_regime
        log_regime(day, regime)
    except Exception:
        pass

    if scored is None:
        from scanner import scan_universe
        from stock_universe import get_universe

        universe = get_universe()
        scored = scan_universe(universe["all"], set(universe["nifty50"]))

    # Apply regime discount
    ranked = apply_regime_to_picks(scored, regime)

    # Enrich top candidates with ATR risk (limit API calls)
    candidates = []
    for row in ranked[: max(20, limit * 5)]:
        if float(row.get("swing_score") or 0) < min_score - 10:
            continue
        try:
            enrich_pick_with_risk(row)
        except Exception:
            pass
        try:
            from sentiment_engine import enrich_pick_sentiment
            enrich_pick_sentiment(row)
        except Exception:
            pass
        if market_pulse:
            row["market_sentiment_100"] = market_pulse.get("score_100")
            row["market_sentiment_label"] = market_pulse.get("label")
        conf = confidence_score(row, regime)
        row["confidence"] = conf
        row["pred_date"] = day
        row["horizon_days"] = int(CONFIG.get("max_hold_days", 7))
        # Plain-language thesis for dashboard
        row["thesis"] = _build_thesis(row)
        candidates.append(row)

    candidates.sort(
        key=lambda x: (x.get("confidence", 0), x.get("swing_score", 0)),
        reverse=True,
    )

    # Only BUY / STRONG BUY with confidence gate
    min_quality = int(CONFIG.get("min_quality_flags", 3))
    buys = [
        c for c in candidates
        if c.get("signal") in ("BUY", "STRONG BUY")
        and float(c.get("confidence") or 0) >= min_conf
        and float(c.get("swing_score") or 0) >= min_score
        and int(c.get("quality_count") or 0) >= min_quality
        and float(c.get("reward_risk") or 0) >= float(CONFIG.get("min_reward_risk", 1.4)) * 0.9
    ]

    # If regime blocks, allow zero buys (honest NO TRADE day)
    if not regime.get("trade_approval", True) and CONFIG.get("regime_strict", True):
        # Keep only exceptional confidence
        exception_floor = min_conf + 10
        buys = [b for b in buys if float(b.get("confidence") or 0) >= exception_floor]

    top = buys[:limit]
    watch = [
        c for c in candidates
        if c not in top and c.get("signal") in ("BUY", "STRONG BUY", "WATCH")
    ][:5]

    # Log scans + predictions
    try:
        from history_db import log_prediction, log_scan_batch

        log_scan_batch(day, ranked[:100], strategy="composite")
        for p in top:
            log_prediction(p, source=source)
    except Exception as exc:
        print(f"[recommender] history log: {exc}", flush=True)

    paper_results = []
    if auto_paper is None:
        auto_paper = bool(CONFIG.get("auto_paper_trade", True))
    if auto_paper and top:
        paper_results = _maybe_auto_paper(top)

    payload = {
        "ok": True,
        "date": day,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "regime": regime,
        "market_sentiment": market_pulse,
        "min_confidence": min_conf,
        "min_buy_score": min_score,
        "recommendations": top,
        "watch": watch,
        "scanned": len(scored),
        "paper": paper_results,
        "broker_integration": False,
        "mode": "recommend_only",
        "message": (
            f"{len(top)} BUY recommendation(s)"
            if top
            else _no_trade_message(regime, min_conf)
        ),
    }

    path = OUT_DIR / f"recommendations_{day}.json"
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    payload["file"] = str(path)
    return payload


def _build_thesis(row: dict) -> str:
    bits = []
    if row.get("trend"):
        bits.append(f"Trend {row['trend']}")
    if row.get("rsi") is not None:
        bits.append(f"RSI {row['rsi']}")
    if row.get("sector"):
        bits.append(str(row["sector"]))
    if row.get("sector_strong"):
        bits.append("strong sector")
    if row.get("sentiment_label") and row["sentiment_label"] not in ("NO_NEWS", "NEUTRAL"):
        bits.append(f"news {row['sentiment_label'].lower()}")
    if row.get("vs_nifty_20d") is not None:
        bits.append(f"vs Nifty {row['vs_nifty_20d']:+.1f}%")
    qf = row.get("quality_flags") or []
    if qf:
        bits.append(f"flags:{','.join(qf[:4])}")
    reasons = row.get("reasons") or []
    if reasons:
        bits.append(str(reasons[0])[:60])
    return " · ".join(bits[:6]) if bits else "Composite technical setup"


def _no_trade_message(regime: dict, min_conf: float) -> str:
    if not regime.get("trade_approval", True):
        return (
            f"NO TRADE — market regime {regime.get('regime')} "
            f"(score {regime.get('score')}). New BUYs blocked."
        )
    return f"NO TRADE — no setup met confidence ≥ {min_conf}."


def _maybe_auto_paper(picks: list[dict]) -> list[dict]:
    """Open paper positions for high-confidence picks (virtual only)."""
    from paper_trading import get_portfolio, paper_buy

    results = []
    max_open = int(CONFIG.get("max_paper_positions", 3))
    min_conf = float(CONFIG.get("auto_paper_min_confidence", 72))
    portfolio = get_portfolio()
    open_n = len(portfolio.get("positions") or [])

    for p in picks:
        if open_n >= max_open:
            results.append({"symbol": p["symbol"], "ok": False, "error": "max paper positions"})
            break
        if float(p.get("confidence") or 0) < min_conf:
            continue
        qty = int(p.get("buy_qty") or 0)
        price = float(p.get("entry") or p.get("price") or 0)
        if qty < 1 or price <= 0:
            continue
        r = paper_buy(
            p["symbol"],
            qty,
            price,
            stop=float(p.get("stop") or 0),
            target=float(p.get("target") or 0),
            strategy=p.get("strategy") or "auto_recommend",
            link_journal=True,
        )
        results.append({"symbol": p["symbol"], **r})
        if r.get("ok"):
            open_n += 1
    return results


def format_recommendation_message(payload: dict) -> str:
    """Telegram / text friendly summary."""
    regime = payload.get("regime") or {}
    lines = [
        "VEDANT SWING — DAILY BUY RECOMMENDATIONS",
        f"{payload.get('date', '')} | Mode: RECOMMEND ONLY (no broker)",
        f"Regime: {regime.get('regime', '?')} ({regime.get('score', 0)}/100) "
        f"{'OK' if regime.get('trade_approval') else 'BLOCK'}",
        f"Market note: {regime.get('reason', '')[:120]}",
        "",
    ]
    recs = payload.get("recommendations") or []
    if not recs:
        lines.append(payload.get("message") or "No BUY today.")
        lines.append("")
        lines.append("This is research only. Not SEBI advice. No auto-broker orders.")
        return "\n".join(lines)

    for i, p in enumerate(recs, 1):
        lines.extend([
            f"#{i} {p.get('symbol')} — {p.get('signal')} | "
            f"Score {p.get('swing_score', 0):.0f} | Conf {p.get('confidence', 0):.0f}",
            f"   Entry Rs.{p.get('entry') or p.get('price')} | "
            f"Target Rs.{p.get('target')} (+{p.get('target_pct', 0):.1f}%) | "
            f"Stop Rs.{p.get('stop')} (-{p.get('stop_pct', 0):.1f}%)",
            f"   Qty ~{p.get('buy_qty', 0)} | Amount ~Rs.{p.get('buy_amount', 0)} | "
            f"Strategy: {p.get('strategy', 'composite')}",
        ])
        reasons = p.get("reasons") or []
        if reasons:
            lines.append(f"   Why: {', '.join(str(r) for r in reasons[:3])}")
        if p.get("regime_note"):
            lines.append(f"   Regime: {p['regime_note']}")
        lines.append("")

    lines.extend([
        "ACTION: Buy manually in your broker if you agree. Bot will NOT place orders.",
        "Paper: auto paper-trade may open virtual positions when confidence is high.",
        "Not SEBI-registered advice. Capital at risk.",
    ])
    return "\n".join(lines)


def get_latest_recommendations() -> dict[str, Any]:
    files = sorted(OUT_DIR.glob("recommendations_*.json"), reverse=True)
    if not files:
        return {"ok": False, "error": "No recommendations yet"}
    try:
        data = json.loads(files[0].read_text(encoding="utf-8"))
        data["ok"] = True
        data["file"] = str(files[0])
        return data
    except (json.JSONDecodeError, OSError) as exc:
        return {"ok": False, "error": str(exc)}


if __name__ == "__main__":
    # Quick path: limited scan for CLI smoke test
    from scanner import scan_universe
    from stock_universe import get_universe

    u = get_universe()
    # Faster CLI test: first 40 symbols
    scored = scan_universe(u["all"][:40], set(u["nifty50"]))
    result = build_recommendations(scored, auto_paper=False)
    print(format_recommendation_message(result))
    print("File:", result.get("file"))
