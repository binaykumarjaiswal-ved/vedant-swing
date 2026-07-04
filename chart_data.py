"""OHLCV + indicators for Vedant Swing charts."""

from __future__ import annotations

from typing import Any

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

from nse_data import CHART_RANGES, get_chart_history, nse_quote


def _series_points(df: pd.DataFrame, col: pd.Series) -> list[dict]:
    points = []
    for idx, val in col.items():
        if pd.notna(val):
            points.append({"time": int(pd.Timestamp(idx).timestamp()), "value": round(float(val), 2)})
    return points


def get_chart_payload(symbol: str, range_key: str = "6m", days: int | None = None) -> dict[str, Any]:
    symbol = symbol.upper().strip()
    if days and range_key == "6m":
        if days <= 35:
            range_key = "1m"
        elif days <= 100:
            range_key = "3m"
        elif days <= 200:
            range_key = "6m"
        else:
            range_key = "1y"

    cfg = CHART_RANGES.get(range_key, CHART_RANGES["6m"])
    df = get_chart_history(symbol, cfg["period"], cfg["interval"])
    if df is None or df.empty or len(df) < 5:
        return {"ok": False, "error": f"No chart data for {symbol}"}

    close = df["Close"]
    ema9 = EMAIndicator(close, window=9).ema_indicator()
    ema21 = EMAIndicator(close, window=21).ema_indicator()
    ema50 = EMAIndicator(close, window=50).ema_indicator()
    rsi = RSIIndicator(close, window=14).rsi()

    candles: list[dict] = []
    volumes: list[dict] = []

    for idx, row in df.iterrows():
        ts = int(pd.Timestamp(idx).timestamp())
        o = round(float(row["Open"]), 2)
        h = round(float(row["High"]), 2)
        l = round(float(row["Low"]), 2)
        c = round(float(row["Close"]), 2)
        candles.append({"time": ts, "open": o, "high": h, "low": l, "close": c})
        vol = int(row.get("Volume", 0) or 0)
        if vol > 0:
            color = "rgba(34, 197, 94, 0.5)" if c >= o else "rgba(239, 68, 68, 0.5)"
            volumes.append({"time": ts, "value": vol, "color": color})

    first = candles[0]
    last = candles[-1]
    period_high = max(c["high"] for c in candles)
    period_low = min(c["low"] for c in candles)
    total_volume = sum(v["value"] for v in volumes)
    ref_price = first["open"] or first["close"]
    change = round(last["close"] - ref_price, 2)
    change_pct = round((change / ref_price) * 100, 2) if ref_price else 0.0

    quote = nse_quote(symbol)
    if quote and range_key in ("1d", "5d"):
        if quote.get("change_pct") is not None:
            change_pct = round(float(quote["change_pct"]), 2)
        if quote.get("ltp"):
            last["close"] = round(float(quote["ltp"]), 2)
            change = round(last["close"] - float(quote.get("prev_close") or ref_price), 2)

    payload: dict[str, Any] = {
        "ok": True,
        "symbol": symbol,
        "range": range_key,
        "range_label": cfg["label"],
        "interval": cfg["interval"],
        "candles": candles,
        "volume": volumes,
        "ema9": _series_points(df, ema9) if len(candles) >= 9 else [],
        "ema21": _series_points(df, ema21) if len(candles) >= 21 else [],
        "ema50": _series_points(df, ema50) if len(candles) >= 50 else [],
        "rsi": _series_points(df, rsi),
        "last_price": last["close"],
        "period_days": len(candles),
        "stats": {
            "open": first["open"],
            "high": period_high,
            "low": period_low,
            "close": last["close"],
            "volume": total_volume,
            "change": change,
            "change_pct": change_pct,
            "prev_close": round(float(quote.get("prev_close", ref_price)), 2) if quote else ref_price,
        },
    }
    if quote:
        payload["quote"] = {
            "ltp": quote.get("ltp"),
            "day_high": quote.get("high"),
            "day_low": quote.get("low"),
            "source": quote.get("source"),
        }
    return payload