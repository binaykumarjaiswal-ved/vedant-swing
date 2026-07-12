"""Technical analysis tuned for 3% swing within ~1 week."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import EMAIndicator, MACD

from nse_data import YAHOO_MAP, get_history


def yahoo_symbol(symbol: str) -> str:
    if symbol.startswith("^"):
        return symbol
    t = YAHOO_MAP.get(symbol, f"{symbol}.NS")
    return t if t.endswith(".NS") else f"{t}.NS"


def fetch_ohlcv(symbol: str, days: int = 120) -> pd.DataFrame | None:
    df = get_history(symbol, days=days)
    if df is None or df.empty or len(df) < 30:
        return None
    return df


def _safe_float(val, default=0.0) -> float:
    try:
        if val is None or (isinstance(val, float) and np.isnan(val)):
            return default
        return float(val)
    except (TypeError, ValueError):
        return default


def analyze_technicals(symbol: str, nifty_df: pd.DataFrame | None = None) -> dict[str, Any]:
    df = fetch_ohlcv(symbol)
    if df is None:
        return {"status": "error", "symbol": symbol, "error": "no price data"}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    rsi = RSIIndicator(close, window=14).rsi()
    macd_ind = MACD(close)
    ema21 = EMAIndicator(close, window=21).ema_indicator()
    ema20 = EMAIndicator(close, window=20).ema_indicator()
    ema50 = EMAIndicator(close, window=50).ema_indicator()

    price = _safe_float(close.iloc[-1])
    rsi_val = _safe_float(rsi.iloc[-1], 50)
    macd_val = _safe_float(macd_ind.macd().iloc[-1])
    macd_sig = _safe_float(macd_ind.macd_signal().iloc[-1])
    macd_hist = _safe_float(macd_ind.macd_diff().iloc[-1])
    ema21_val = _safe_float(ema21.iloc[-1])
    ema20_val = _safe_float(ema20.iloc[-1])
    ema50_val = _safe_float(ema50.iloc[-1])
    vol_avg = _safe_float(volume.tail(20).mean())
    vol_today = _safe_float(volume.iloc[-1])
    vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0

    chg_5d = _safe_float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0
    chg_20d = _safe_float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    low_52 = _safe_float(low.tail(252).min(), price)
    high_52 = _safe_float(high.tail(252).max(), price)
    range_pos = ((price - low_52) / (high_52 - low_52) * 100) if high_52 > low_52 else 50

    vs_nifty = 0.0
    if nifty_df is not None and len(nifty_df) > 21:
        n_chg = _safe_float((nifty_df["Close"].iloc[-1] / nifty_df["Close"].iloc[-21] - 1) * 100)
        vs_nifty = chg_20d - n_chg

    if price > ema20_val > ema50_val:
        trend = "up"
    elif price < ema20_val < ema50_val:
        trend = "down"
    else:
        trend = "sideways"

    macd_bullish = macd_val > macd_sig and macd_hist > 0
    score = 0.0
    reasons = []

    if 40 <= rsi_val <= 60:
        score += 25
        reasons.append(f"RSI {rsi_val:.0f} ideal for 3% bounce")
    elif 35 <= rsi_val < 40:
        score += 18
        reasons.append(f"RSI {rsi_val:.0f} oversold bounce")
    elif 60 < rsi_val <= 68:
        score += 12
        reasons.append(f"RSI {rsi_val:.0f} mild momentum")
    elif rsi_val > 72:
        score -= 15
        reasons.append(f"RSI {rsi_val:.0f} overbought")

    if macd_bullish:
        score += 20
        reasons.append("MACD bullish crossover")
    if price > ema20_val:
        score += 12
        reasons.append("Above 20 EMA")
    if trend == "up":
        score += 10
        reasons.append("Uptrend intact")
    if -2 <= chg_5d <= 4:
        score += 8
        reasons.append(f"5d move {chg_5d:+.1f}% — room for 3%")
    elif chg_5d > 6:
        score -= 8
        reasons.append(f"Already up {chg_5d:.1f}% in 5d")
    if vol_ratio >= 1.15:
        score += 8
        reasons.append(f"Volume +{(vol_ratio - 1) * 100:.0f}%")
    if 25 <= range_pos <= 70:
        score += 10
        reasons.append(f"Mid 52w range ({range_pos:.0f}%)")
    elif range_pos > 88:
        score -= 12
        reasons.append("Near 52w high")
    if vs_nifty > 1.5:
        score += 8
        reasons.append(f"Beating Nifty by {vs_nifty:+.1f}%")
    elif vs_nifty < -4:
        score -= 6

    score = max(0, min(100, score))

    # ATR for risk engine (14-period)
    atr_val = 0.0
    try:
        prev_c = close.shift(1)
        tr = pd.concat(
            [(high - low).abs(), (high - prev_c).abs(), (low - prev_c).abs()],
            axis=1,
        ).max(axis=1)
        atr_val = float(tr.tail(14).mean())
        if np.isnan(atr_val):
            atr_val = 0.0
    except Exception:
        atr_val = 0.0

    target_pct = 3.0
    stop_pct = 4.0
    if atr_val > 0 and price > 0:
        target_pct = max(2.0, min(5.0, (atr_val * 1.5 / price) * 100))
        stop_pct = max(2.0, min(6.0, (atr_val * 1.2 / price) * 100))

    entry = price
    target = round(price * (1 + target_pct / 100), 2)
    stop = round(price * (1 - stop_pct / 100), 2)
    avg_trigger = round(price * 0.97, 2)

    return {
        "status": "ok",
        "symbol": symbol,
        "price": price,
        "rsi": round(rsi_val, 1),
        "macd_bullish": macd_bullish,
        "trend": trend,
        "chg_5d": round(chg_5d, 2),
        "chg_20d": round(chg_20d, 2),
        "vs_nifty_20d": round(vs_nifty, 2),
        "range_position": round(range_pos, 1),
        "volume_ratio": round(vol_ratio, 2),
        "ema21": round(ema21_val, 2),
        "ema20": round(ema20_val, 2),
        "ema50": round(ema50_val, 2),
        "atr": round(atr_val, 2),
        "swing_score": round(score, 1),
        "reasons": reasons,
        "entry": entry,
        "target": target,
        "stop": stop,
        "avg_trigger": avg_trigger,
        "target_pct": round(target_pct, 2),
        "stop_pct": round(stop_pct, 2),
    }