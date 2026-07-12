"""
Technical analysis for ~1-week delivery swings.

Score blends trend quality, momentum, volume, structure, and volatility
(not a single indicator). ATR drives stop/target distance (risk engine).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator, StochasticOscillator
from ta.trend import ADXIndicator, EMAIndicator, MACD
from ta.volatility import AverageTrueRange, BollingerBands

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


def _calc_atr_series(high, low, close, period: int = 14) -> pd.Series:
    try:
        return AverageTrueRange(high, low, close, window=period).average_true_range()
    except Exception:
        prev = close.shift(1)
        tr = pd.concat(
            [(high - low).abs(), (high - prev).abs(), (low - prev).abs()],
            axis=1,
        ).max(axis=1)
        return tr.rolling(period).mean()


def analyze_technicals(symbol: str, nifty_df: pd.DataFrame | None = None) -> dict[str, Any]:
    df = fetch_ohlcv(symbol)
    if df is None:
        return {"status": "error", "symbol": symbol, "error": "no price data"}

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]

    # ── Core indicators ──
    rsi = RSIIndicator(close, window=14).rsi()
    macd_ind = MACD(close)
    ema9 = EMAIndicator(close, window=9).ema_indicator()
    ema21 = EMAIndicator(close, window=21).ema_indicator()
    ema20 = EMAIndicator(close, window=20).ema_indicator()
    ema50 = EMAIndicator(close, window=50).ema_indicator()

    atr_s = _calc_atr_series(high, low, close, 14)
    atr_val = _safe_float(atr_s.iloc[-1])

    # ADX — trend strength (avoid chop)
    adx_val, plus_di, minus_di = 20.0, 20.0, 20.0
    try:
        if len(close) >= 30:
            adx_i = ADXIndicator(high, low, close, window=14)
            adx_val = _safe_float(adx_i.adx().iloc[-1], 20)
            plus_di = _safe_float(adx_i.adx_pos().iloc[-1], 20)
            minus_di = _safe_float(adx_i.adx_neg().iloc[-1], 20)
    except Exception:
        pass

    # Stochastic — timing (not overbought entries)
    stoch_k, stoch_d = 50.0, 50.0
    try:
        st = StochasticOscillator(high, low, close, window=14, smooth_window=3)
        stoch_k = _safe_float(st.stoch().iloc[-1], 50)
        stoch_d = _safe_float(st.stoch_signal().iloc[-1], 50)
    except Exception:
        pass

    # Bollinger %B — location in band
    bb_pct = 0.5
    bb_width = 0.0
    try:
        bb = BollingerBands(close, window=20, window_dev=2)
        mid = bb.bollinger_mavg()
        upper = bb.bollinger_hband()
        lower = bb.bollinger_lband()
        u = _safe_float(upper.iloc[-1])
        l = _safe_float(lower.iloc[-1])
        m = _safe_float(mid.iloc[-1])
        price_tmp = _safe_float(close.iloc[-1])
        if u > l:
            bb_pct = (price_tmp - l) / (u - l)
        if m > 0:
            bb_width = (u - l) / m * 100
    except Exception:
        pass

    price = _safe_float(close.iloc[-1])
    rsi_val = _safe_float(rsi.iloc[-1], 50)
    macd_val = _safe_float(macd_ind.macd().iloc[-1])
    macd_sig = _safe_float(macd_ind.macd_signal().iloc[-1])
    macd_hist = _safe_float(macd_ind.macd_diff().iloc[-1])
    macd_hist_prev = _safe_float(macd_ind.macd_diff().iloc[-2]) if len(close) > 2 else 0
    ema9_val = _safe_float(ema9.iloc[-1])
    ema21_val = _safe_float(ema21.iloc[-1])
    ema20_val = _safe_float(ema20.iloc[-1])
    ema50_val = _safe_float(ema50.iloc[-1])

    vol_avg = _safe_float(volume.tail(20).mean())
    vol_today = _safe_float(volume.iloc[-1])
    vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0
    # Rising volume trend (5d avg vs 20d)
    vol_5 = _safe_float(volume.tail(5).mean())
    vol_trend = vol_5 / vol_avg if vol_avg > 0 else 1.0

    chg_5d = _safe_float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0
    chg_20d = _safe_float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 20 else 0

    low_52 = _safe_float(low.tail(min(252, len(low))).min(), price)
    high_52 = _safe_float(high.tail(min(252, len(high))).max(), price)
    range_pos = ((price - low_52) / (high_52 - low_52) * 100) if high_52 > low_52 else 50

    # Distance from EMAs in ATR units (pullback quality)
    atr_safe = atr_val if atr_val > 0 else price * 0.02
    dist_ema21_atr = abs(price - ema21_val) / atr_safe if atr_safe else 99
    dist_ema50_atr = abs(price - ema50_val) / atr_safe if atr_safe else 99

    # Higher-low structure (last 3 swing lows approx)
    structure_ok = False
    try:
        recent_lows = low.tail(15)
        if len(recent_lows) >= 10:
            l1 = _safe_float(recent_lows.iloc[-10:-5].min())
            l2 = _safe_float(recent_lows.iloc[-5:].min())
            structure_ok = l2 >= l1 * 0.995  # not making lower lows
    except Exception:
        pass

    vs_nifty = 0.0
    if nifty_df is not None and len(nifty_df) > 21:
        n_chg = _safe_float((nifty_df["Close"].iloc[-1] / nifty_df["Close"].iloc[-21] - 1) * 100)
        vs_nifty = chg_20d - n_chg

    # Trend classification
    if price > ema20_val > ema50_val and plus_di >= minus_di:
        trend = "up"
    elif price < ema20_val < ema50_val and minus_di > plus_di:
        trend = "down"
    else:
        trend = "sideways"

    macd_bullish = macd_val > macd_sig and macd_hist > 0
    macd_improving = macd_hist > macd_hist_prev
    stoch_bullish = stoch_k > stoch_d and stoch_k < 80
    stoch_oversold_cross = stoch_k > stoch_d and stoch_k < 35

    # ── Multi-factor score (quality-first for better win rate) ──
    score = 0.0
    reasons: list[str] = []
    quality_flags: list[str] = []

    # 1) Trend quality (max ~22)
    if trend == "up" and adx_val >= 22:
        score += 18
        reasons.append(f"Uptrend + ADX {adx_val:.0f} (strong trend)")
        quality_flags.append("trend_ok")
    elif trend == "up":
        score += 10
        reasons.append("Uptrend (weak ADX — chop risk)")
    elif trend == "sideways" and adx_val < 18:
        score += 2
        reasons.append("Sideways chop — low edge")
    elif trend == "down":
        score -= 14
        reasons.append("Downtrend — avoid long swings")

    if price > ema9_val > ema21_val > ema50_val:
        score += 8
        reasons.append("EMA stack bullish (9>21>50)")
        quality_flags.append("ema_stack")
    elif price > ema20_val:
        score += 5
        reasons.append("Above 20 EMA")

    # 2) Pullback entry quality (max ~16) — buy dips in uptrend, not chase
    if trend == "up" and 0.3 <= dist_ema21_atr <= 1.8:
        score += 14
        reasons.append(f"Healthy pullback to 21 EMA ({dist_ema21_atr:.1f}×ATR)")
        quality_flags.append("pullback")
    elif trend == "up" and dist_ema21_atr < 0.3:
        score += 4
        reasons.append("Tight at EMA — wait for dip or breakout vol")
    elif dist_ema21_atr > 3.5:
        score -= 8
        reasons.append("Extended far above EMA — chase risk")

    # 3) RSI (max ~14) — prefer 40–58 for swings
    if 42 <= rsi_val <= 58:
        score += 14
        reasons.append(f"RSI {rsi_val:.0f} ideal swing zone")
        quality_flags.append("rsi_ok")
    elif 35 <= rsi_val < 42:
        score += 10
        reasons.append(f"RSI {rsi_val:.0f} oversold bounce zone")
    elif 58 < rsi_val <= 65:
        score += 6
        reasons.append(f"RSI {rsi_val:.0f} mild momentum")
    elif rsi_val > 72:
        score -= 16
        reasons.append(f"RSI {rsi_val:.0f} overbought — skip")
    elif rsi_val < 30:
        score += 4
        reasons.append(f"RSI {rsi_val:.0f} deep oversold")

    # 4) MACD (max ~12)
    if macd_bullish and macd_improving:
        score += 12
        reasons.append("MACD bullish + histogram rising")
        quality_flags.append("macd_ok")
    elif macd_bullish:
        score += 7
        reasons.append("MACD bullish")
    elif macd_hist < 0 and macd_improving:
        score += 4
        reasons.append("MACD improving from below")
    elif not macd_bullish and trend == "down":
        score -= 4

    # 5) Stochastic timing (max ~8)
    if stoch_oversold_cross:
        score += 8
        reasons.append(f"Stoch turn up from oversold (K={stoch_k:.0f})")
        quality_flags.append("stoch_ok")
    elif stoch_bullish and stoch_k < 70:
        score += 5
        reasons.append(f"Stochastic supportive (K={stoch_k:.0f})")
    elif stoch_k > 85:
        score -= 6
        reasons.append("Stochastic overbought")

    # 6) Bollinger location (max ~8)
    if 0.2 <= bb_pct <= 0.55 and trend == "up":
        score += 8
        reasons.append("BB mid-lower zone in uptrend (value entry)")
        quality_flags.append("bb_ok")
    elif bb_pct > 0.92:
        score -= 10
        reasons.append("At upper Bollinger — extended")
    elif bb_pct < 0.15 and trend != "down":
        score += 5
        reasons.append("Near lower band — bounce candidate")

    # 7) Volume confirmation (max ~10)
    if vol_ratio >= 1.4 and chg_5d >= 0:
        score += 10
        reasons.append(f"Volume surge {vol_ratio:.1f}× on strength")
        quality_flags.append("vol_ok")
    elif vol_ratio >= 1.15:
        score += 6
        reasons.append(f"Volume +{(vol_ratio - 1) * 100:.0f}%")
    elif vol_trend < 0.75:
        score -= 4
        reasons.append("Volume drying up")

    # 8) Relative strength vs Nifty (max ~10)
    if vs_nifty > 3:
        score += 10
        reasons.append(f"Strong RS vs Nifty {vs_nifty:+.1f}%")
        quality_flags.append("rs_ok")
    elif vs_nifty > 1:
        score += 6
        reasons.append(f"Beating Nifty {vs_nifty:+.1f}%")
    elif vs_nifty < -5:
        score -= 8
        reasons.append(f"Lagging Nifty {vs_nifty:+.1f}%")

    # 9) 52w location + room to run
    if 30 <= range_pos <= 72:
        score += 6
        reasons.append(f"Mid 52w range ({range_pos:.0f}%)")
    elif range_pos > 90:
        score -= 12
        reasons.append("Near 52w high — limited upside room")
    elif range_pos < 15:
        score -= 4
        reasons.append("Near 52w low — weak demand zone")

    # 10) Already extended 5d?
    if -1.5 <= chg_5d <= 3.5:
        score += 6
        reasons.append(f"5d {chg_5d:+.1f}% — room for swing")
        quality_flags.append("room")
    elif chg_5d > 7:
        score -= 12
        reasons.append(f"Already up {chg_5d:.1f}% in 5d — late")
    elif chg_5d < -8:
        score -= 4
        reasons.append("Sharp 5d drop — wait for base")

    # 11) Structure
    if structure_ok and trend == "up":
        score += 5
        reasons.append("Higher-low structure intact")
        quality_flags.append("structure")

    # 12) Volatility regime (ATR%) — too wild = lower win rate for fixed holds
    atr_pct = (atr_val / price * 100) if price > 0 else 0
    if 1.2 <= atr_pct <= 4.0:
        score += 4
        quality_flags.append("atr_ok")
    elif atr_pct > 6:
        score -= 8
        reasons.append(f"ATR {atr_pct:.1f}% — too volatile for clean swing")
    elif atr_pct < 0.8:
        score -= 2
        reasons.append("Very low volatility — may stall")

    # Quality gate: need multiple independent confirms for high scores
    quality_count = len(set(quality_flags))
    if quality_count >= 5:
        score += 6
        reasons.append(f"Multi-factor quality ({quality_count} confirms)")
    elif quality_count <= 1 and score > 50:
        score -= 10
        reasons.append("Thin confirmation — score capped")

    score = max(0, min(100, score))

    # ── ATR-based levels (aligned with risk_engine defaults) ──
    # Target ~1.8×ATR, Stop ~1.1×ATR → aims for ~1.6 R:R before clamps
    target_pct = 3.0
    stop_pct = 4.0
    if atr_val > 0 and price > 0:
        target_pct = max(2.0, min(5.5, (atr_val * 1.8 / price) * 100))
        stop_pct = max(1.8, min(5.5, (atr_val * 1.1 / price) * 100))
        # Enforce min reward:risk ~ 1.4 after clamps
        if target_pct < stop_pct * 1.4:
            target_pct = min(5.5, stop_pct * 1.5)

    entry = price
    target = round(price * (1 + target_pct / 100), 2)
    stop = round(price * (1 - stop_pct / 100), 2)
    # Prefer structural stop below recent swing low if tighter/safer
    try:
        swing_low = _safe_float(low.tail(10).min())
        if swing_low > 0 and swing_low < price:
            struct_stop = swing_low * 0.995
            struct_pct = (price - struct_stop) / price * 100
            if 1.5 <= struct_pct <= stop_pct * 1.15:
                stop = round(struct_stop, 2)
                stop_pct = round(struct_pct, 2)
                reasons.append("Stop near swing low (structure)")
    except Exception:
        pass

    avg_trigger = round(price * 0.97, 2)
    rr = round(target_pct / stop_pct, 2) if stop_pct > 0 else 0

    setup_type = "mixed"
    if "pullback" in quality_flags and trend == "up":
        setup_type = "pullback_trend"
    elif bb_pct > 0.7 and vol_ratio >= 1.3 and trend == "up":
        setup_type = "breakout_vol"
    elif rsi_val < 40 and stoch_oversold_cross:
        setup_type = "oversold_bounce"

    return {
        "status": "ok",
        "symbol": symbol,
        "price": price,
        "rsi": round(rsi_val, 1),
        "stoch_k": round(stoch_k, 1),
        "stoch_d": round(stoch_d, 1),
        "adx": round(adx_val, 1),
        "plus_di": round(plus_di, 1),
        "minus_di": round(minus_di, 1),
        "bb_pct": round(bb_pct, 2),
        "bb_width": round(bb_width, 2),
        "macd_bullish": macd_bullish,
        "macd_improving": macd_improving,
        "trend": trend,
        "setup_type": setup_type,
        "quality_flags": quality_flags,
        "quality_count": quality_count,
        "chg_5d": round(chg_5d, 2),
        "chg_20d": round(chg_20d, 2),
        "vs_nifty_20d": round(vs_nifty, 2),
        "range_position": round(range_pos, 1),
        "volume_ratio": round(vol_ratio, 2),
        "volume_trend": round(vol_trend, 2),
        "ema9": round(ema9_val, 2),
        "ema21": round(ema21_val, 2),
        "ema20": round(ema20_val, 2),
        "ema50": round(ema50_val, 2),
        "atr": round(atr_val, 2),
        "atr_pct": round(atr_pct, 2),
        "dist_ema21_atr": round(dist_ema21_atr, 2),
        "reward_risk": rr,
        "swing_score": round(score, 1),
        "reasons": reasons,
        "entry": entry,
        "target": target,
        "stop": stop,
        "avg_trigger": avg_trigger,
        "target_pct": round(target_pct, 2),
        "stop_pct": round(stop_pct, 2),
    }
