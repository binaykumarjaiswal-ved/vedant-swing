"""ATR-based stops/targets and risk-based position sizing. No broker orders."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def calc_atr(df: pd.DataFrame, period: int = 14) -> float:
    if df is None or len(df) < period + 1:
        return 0.0
    high = df["High"]
    low = df["Low"]
    close = df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [
            (high - low).abs(),
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    atr = float(tr.tail(period).mean())
    if np.isnan(atr):
        return 0.0
    return atr


def risk_levels(
    price: float,
    atr: float | None = None,
    df: pd.DataFrame | None = None,
) -> dict[str, Any]:
    """
    Volatility-aware target and hard stop.
    Falls back to config % if ATR unavailable.
    """
    if price <= 0:
        return {
            "entry": 0,
            "target": 0,
            "stop": 0,
            "target_pct": CONFIG.get("profit_target_pct", 3.0),
            "stop_pct": CONFIG.get("hard_stop_pct", 4.0),
            "atr": 0,
            "method": "invalid",
        }

    if atr is None and df is not None:
        atr = calc_atr(df, CONFIG.get("atr_period", 14))
    atr = float(atr or 0)

    min_target = float(CONFIG.get("min_target_pct", 2.0))
    max_target = float(CONFIG.get("max_target_pct", 5.0))
    min_stop = float(CONFIG.get("min_stop_pct", 2.0))
    max_stop = float(CONFIG.get("max_stop_pct", 6.0))
    # Default R:R design: target 1.8×ATR, stop 1.1×ATR ≈ 1.6 reward:risk
    target_atr_mult = float(CONFIG.get("target_atr_mult", 1.8))
    stop_atr_mult = float(CONFIG.get("stop_atr_mult", 1.1))
    min_rr = float(CONFIG.get("min_reward_risk", 1.4))

    if atr > 0 and price > 0:
        target_pct = (atr * target_atr_mult / price) * 100
        stop_pct = (atr * stop_atr_mult / price) * 100
        target_pct = max(min_target, min(max_target, target_pct))
        stop_pct = max(min_stop, min(max_stop, stop_pct))
        method = "atr"
    else:
        target_pct = float(CONFIG.get("profit_target_pct", 3.0))
        stop_pct = float(CONFIG.get("hard_stop_pct", CONFIG.get("loss_trigger_pct", 3.0) + 1))
        method = "fixed_pct"

    # Enforce minimum reward:risk (win rate alone is not enough — expectancy needs R)
    if stop_pct > 0 and target_pct / stop_pct < min_rr:
        target_pct = min(max_target, stop_pct * min_rr)

    entry = round(price, 2)
    target = round(entry * (1 + target_pct / 100), 2)
    stop = round(entry * (1 - stop_pct / 100), 2)

    return {
        "entry": entry,
        "target": target,
        "stop": stop,
        "target_pct": round(target_pct, 2),
        "stop_pct": round(stop_pct, 2),
        "atr": round(atr, 2),
        "method": method,
        "avg_trigger": round(entry * (1 - CONFIG.get("loss_trigger_pct", 3.0) / 100), 2),
    }


def position_size(
    price: float,
    stop: float,
    portfolio_value: float | None = None,
    risk_pct: float | None = None,
    max_investment: float | None = None,
) -> dict[str, Any]:
    """
    Size by risk: risk_amount / stop_distance.
    Caps at max_investment (default_investment).
    """
    portfolio_value = portfolio_value or float(CONFIG.get("paper_starting_cash", 500000))
    risk_pct = risk_pct if risk_pct is not None else float(CONFIG.get("risk_per_trade_pct", 1.0))
    max_investment = max_investment or float(CONFIG.get("default_investment", 30000))

    if price <= 0:
        return {"qty": 0, "amount": 0, "budget": max_investment, "risk_amount": 0, "method": "invalid"}

    risk_amount = portfolio_value * (risk_pct / 100.0)
    stop_dist = abs(price - stop) if stop and stop > 0 else price * (CONFIG.get("hard_stop_pct", 4.0) / 100)
    if stop_dist <= 0:
        stop_dist = price * 0.03

    qty_risk = int(risk_amount / stop_dist)
    qty_cap = int(max_investment / price)
    qty = max(0, min(qty_risk, qty_cap))
    if qty < 1 and max_investment >= price:
        qty = 1

    amount = round(qty * price, 2)
    return {
        "qty": qty,
        "amount": amount,
        "budget": max_investment,
        "risk_amount": round(risk_amount, 2),
        "stop_distance": round(stop_dist, 2),
        "method": "risk_pct",
        "risk_pct": risk_pct,
    }


def enrich_pick_with_risk(
    pick: dict[str, Any],
    df: pd.DataFrame | None = None,
    portfolio_value: float | None = None,
    fetch_history: bool = False,
) -> dict[str, Any]:
    """Attach ATR levels + sized qty to a scanner pick.

    By default uses atr already on the pick (from technicals) to avoid re-fetch.
    Set fetch_history=True only when you need a fresh OHLCV ATR.
    """
    price = float(pick.get("price") or pick.get("entry") or pick.get("best_buy_price") or 0)
    if price <= 0:
        return pick

    atr_hint = float(pick.get("atr") or 0)
    if df is None and fetch_history and atr_hint <= 0:
        try:
            from technical import fetch_ohlcv
            df = fetch_ohlcv(pick.get("symbol", ""), days=80)
        except Exception:
            df = None

    levels = risk_levels(price, atr=atr_hint if atr_hint > 0 else None, df=df)
    # Prefer limit near low of day if already set
    entry = float(pick.get("best_buy_price") or pick.get("entry") or price)
    if entry > 0 and abs(entry - price) / price < 0.03:
        # Rebuild levels from preferred entry
        levels = risk_levels(entry, atr=levels.get("atr"), df=df)
        levels["entry"] = round(entry, 2)
        levels["target"] = round(entry * (1 + levels["target_pct"] / 100), 2)
        levels["stop"] = round(entry * (1 - levels["stop_pct"] / 100), 2)

    sizing = position_size(
        levels["entry"],
        levels["stop"],
        portfolio_value=portfolio_value,
    )

    pick["entry"] = levels["entry"]
    pick["best_buy_price"] = levels["entry"]
    pick["target"] = levels["target"]
    pick["stop"] = levels["stop"]
    pick["target_pct"] = levels["target_pct"]
    pick["stop_pct"] = levels["stop_pct"]
    pick["atr"] = levels["atr"]
    pick["risk_method"] = levels["method"]
    pick["avg_trigger"] = levels["avg_trigger"]
    pick["buy_qty"] = sizing["qty"]
    pick["buy_amount"] = sizing["amount"]
    pick["buy_budget"] = sizing["budget"]
    pick["risk_amount"] = sizing["risk_amount"]
    return pick


def confidence_score(pick: dict[str, Any], regime: dict | None = None) -> float:
    """
    0–100 confidence for recommendation gate.
    Composite: technicals + sector + news sentiment + RR + market regime.
    """
    score = float(pick.get("swing_score") or 0)
    conf = score * 0.55  # leave more room for multi-factor boosts

    signal = (pick.get("signal") or "").upper()
    if signal == "STRONG BUY":
        conf += 12
    elif signal == "BUY":
        conf += 6

    if pick.get("strategy") in ("pullback_21ema", "breakout") or pick.get("setup_type") in (
        "pullback_trend", "breakout_vol",
    ):
        conf += 6
    if pick.get("sector_strong"):
        conf += 6
    if pick.get("macd_bullish"):
        conf += 4
    if pick.get("macd_improving"):
        conf += 2
    if pick.get("trend") == "up":
        conf += 4
    elif pick.get("trend") == "down":
        conf -= 8

    # Multi-factor quality from technicals
    qc = int(pick.get("quality_count") or 0)
    if qc >= 5:
        conf += 8
    elif qc >= 3:
        conf += 4
    elif qc <= 1:
        conf -= 6

    adx = float(pick.get("adx") or 0)
    if adx >= 25 and pick.get("trend") == "up":
        conf += 5
    elif adx and adx < 16:
        conf -= 5  # choppy — lower win rate

    rr = float(pick.get("reward_risk") or 0)
    if rr >= 1.6:
        conf += 5
    elif rr and rr < 1.2:
        conf -= 4

    # Relative strength vs Nifty
    vs = float(pick.get("vs_nifty_20d") or 0)
    if vs > 3:
        conf += 5
    elif vs > 1:
        conf += 2
    elif vs < -4:
        conf -= 5

    # RSI sweet spot for swings
    rsi = float(pick.get("rsi") or 50)
    if 40 <= rsi <= 58:
        conf += 4
    elif rsi > 72:
        conf -= 8
    elif rsi < 30:
        conf += 2  # oversold bounce possible

    # News / sentiment (stronger weight)
    if pick.get("news_sentiment") is not None:
        ns = float(pick["news_sentiment"])
        if ns > 0.35:
            conf += 10
        elif ns > 0.15:
            conf += 6
        elif ns < -0.35:
            conf -= 12
        elif ns < -0.15:
            conf -= 7
    label = (pick.get("sentiment_label") or "").upper()
    if label == "BULLISH":
        conf += 3
    elif label == "BEARISH":
        conf -= 5

    # Reward:risk
    tp = float(pick.get("target_pct") or 0)
    sp = float(pick.get("stop_pct") or 0)
    if sp > 0 and tp / sp >= 1.3:
        conf += 6
    elif sp > 0 and tp / sp >= 1.0:
        conf += 3
    elif sp > 0 and tp / sp < 0.9:
        conf -= 5

    if regime:
        if not regime.get("trade_approval", True):
            conf -= 18
        elif regime.get("regime") == "BULLISH":
            conf += 6
        elif regime.get("regime") == "BEARISH":
            conf -= 12

    # Market-wide news pulse if provided on pick
    mpulse = float(pick.get("market_sentiment_100") or 0)
    if mpulse >= 65:
        conf += 4
    elif mpulse and mpulse <= 35:
        conf -= 6

    conf = max(0, min(100, conf))
    return round(conf, 1)
