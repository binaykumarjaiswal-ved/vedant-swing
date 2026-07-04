"""Three built-in swing strategies for Vedant Swing."""

from __future__ import annotations

from typing import Any

from technical import analyze_technicals, fetch_ohlcv


def _base_row(tech: dict[str, Any], strategy: str, reason: str) -> dict[str, Any] | None:
    if tech.get("status") != "ok":
        return None
    return {
        **tech,
        "strategy": strategy,
        "strategy_reason": reason,
        "swing_score": tech.get("swing_score", 0),
        "signal": "SETUP",
    }


def pullback_to_ema(tech: dict[str, Any]) -> dict[str, Any] | None:
    price = tech.get("price", 0)
    ema21 = tech.get("ema21", 0) or tech.get("ema20", 0)
    ema50 = tech.get("ema50", 0)
    rsi = tech.get("rsi", 50)
    if price <= 0 or ema21 <= 0 or ema50 <= 0:
        return None
    if price < ema50:
        return None
    dist = abs(price - ema21) / price * 100
    if dist > 3:
        return None
    if not (40 <= rsi <= 55):
        return None
    if tech.get("trend") == "down":
        return None
    row = _base_row(tech, "pullback_21ema", "Pullback near 21 EMA in uptrend")
    if row:
        row["swing_score"] = min(100, row["swing_score"] + 8)
        row["signal"] = "BUY"
    return row


def breakout_consolidation(symbol: str, tech: dict[str, Any]) -> dict[str, Any] | None:
    df = fetch_ohlcv(symbol, days=30)
    if df is None or len(df) < 12:
        return None
    window = df.tail(10)
    hi = float(window["High"].max())
    lo = float(window["Low"].min())
    if lo <= 0:
        return None
    range_pct = (hi - lo) / lo * 100
    if range_pct > 8:
        return None
    price = tech.get("price", 0)
    vol_ratio = tech.get("volume_ratio", 1)
    if price < hi * 0.995:
        return None
    if vol_ratio < 1.5:
        return None
    row = _base_row(tech, "breakout", f"Tight {range_pct:.1f}% range breakout with volume")
    if row:
        row["swing_score"] = min(100, row["swing_score"] + 10)
        row["signal"] = "STRONG BUY" if vol_ratio >= 2 else "BUY"
    return row


def oversold_bounce(tech: dict[str, Any], nifty100: set[str]) -> dict[str, Any] | None:
    sym = tech.get("symbol", "")
    if sym not in nifty100:
        return None
    rsi = tech.get("rsi", 50)
    if rsi >= 35:
        return None
    if tech.get("trend") == "down":
        return None
    row = _base_row(tech, "oversold_bounce", "Oversold RSI with support bounce setup")
    if row:
        row["swing_score"] = min(100, row["swing_score"] + 5)
        row["signal"] = "WATCH" if rsi < 30 else "BUY"
    return row


def classify_symbol(symbol: str, nifty100: set[str], nifty_df=None) -> list[dict[str, Any]]:
    tech = analyze_technicals(symbol, nifty_df)
    hits = []
    for fn, args in (
        (pullback_to_ema, (tech,)),
        (breakout_consolidation, (symbol, tech)),
        (oversold_bounce, (tech, nifty100)),
    ):
        row = fn(*args)
        if row:
            hits.append(row)
    return hits