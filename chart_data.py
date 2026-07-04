"""OHLCV + indicators for Vedant Swing charts."""

from __future__ import annotations

from typing import Any

import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator

from nse_data import get_history


def get_chart_payload(symbol: str, days: int = 120) -> dict[str, Any]:
    df = get_history(symbol.upper().strip(), days=days)
    if df is None or df.empty or len(df) < 10:
        return {"ok": False, "error": f"No chart data for {symbol}"}

    close = df["Close"]
    ema9 = EMAIndicator(close, window=9).ema_indicator()
    ema21 = EMAIndicator(close, window=21).ema_indicator()
    ema50 = EMAIndicator(close, window=50).ema_indicator()
    rsi = RSIIndicator(close, window=14).rsi()

    candles = []
    ema9_line = []
    ema21_line = []
    ema50_line = []
    rsi_line = []

    for idx, row in df.iterrows():
        ts = int(pd.Timestamp(idx).timestamp())
        candles.append({
            "time": ts,
            "open": round(float(row["Open"]), 2),
            "high": round(float(row["High"]), 2),
            "low": round(float(row["Low"]), 2),
            "close": round(float(row["Close"]), 2),
        })
        if pd.notna(ema9.loc[idx]):
            ema9_line.append({"time": ts, "value": round(float(ema9.loc[idx]), 2)})
        if pd.notna(ema21.loc[idx]):
            ema21_line.append({"time": ts, "value": round(float(ema21.loc[idx]), 2)})
        if pd.notna(ema50.loc[idx]):
            ema50_line.append({"time": ts, "value": round(float(ema50.loc[idx]), 2)})
        if pd.notna(rsi.loc[idx]):
            rsi_line.append({"time": ts, "value": round(float(rsi.loc[idx]), 2)})

    last = candles[-1]
    return {
        "ok": True,
        "symbol": symbol.upper(),
        "candles": candles,
        "ema9": ema9_line,
        "ema21": ema21_line,
        "ema50": ema50_line,
        "rsi": rsi_line,
        "last_price": last["close"],
        "period_days": len(candles),
    }