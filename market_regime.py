"""Market regime / health filter — gate new BUY recommendations."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _ema(series, window: int):
    return series.ewm(span=window, adjust=False).mean()


def market_health(nifty_df=None) -> dict[str, Any]:
    """
    0–100 market health score for Nifty.
    trade_approval=False means block / heavily discount new BUYs.
    """
    from technical import fetch_ohlcv

    if nifty_df is None:
        nifty_df = fetch_ohlcv("NIFTYBEES", days=260)
        if nifty_df is None:
            nifty_df = fetch_ohlcv("^NSEI", days=260)

    if nifty_df is None or len(nifty_df) < 50:
        return {
            "score": 50,
            "regime": "NEUTRAL",
            "trade_approval": True,
            "reason": "Insufficient index data — default NEUTRAL",
            "change_20d": 0.0,
            "above_200dma": None,
            "above_50dma": None,
        }

    close = nifty_df["Close"]
    price = float(close.iloc[-1])
    ema50 = float(_ema(close, 50).iloc[-1])
    ema200 = float(_ema(close, 200).iloc[-1]) if len(close) >= 200 else float(_ema(close, min(100, len(close) - 1)).iloc[-1])
    chg_20d = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) > 21 else 0.0
    chg_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 6 else 0.0

    # Simple breadth proxy: 20d momentum vs volatility
    rets = close.pct_change().dropna()
    vol_20 = float(rets.tail(20).std() * (252 ** 0.5) * 100) if len(rets) >= 20 else 15.0

    score = 0
    reasons: list[str] = []

    above_50 = price > ema50
    above_200 = price > ema200

    if above_200:
        score += 30
        reasons.append("Above long EMA (bull structure)")
    else:
        reasons.append("Below long EMA (weak structure)")

    if above_50:
        score += 20
        reasons.append("Above 50 EMA")
    else:
        score += 5
        reasons.append("Below 50 EMA")

    if chg_20d > 2:
        score += 25
        reasons.append(f"20d momentum {chg_20d:+.1f}%")
    elif chg_20d > 0:
        score += 15
        reasons.append(f"20d mild up {chg_20d:+.1f}%")
    elif chg_20d > -3:
        score += 8
        reasons.append(f"20d soft {chg_20d:+.1f}%")
    else:
        reasons.append(f"20d weak {chg_20d:+.1f}%")

    if chg_5d > 0:
        score += 15
        reasons.append(f"5d positive {chg_5d:+.1f}%")
    elif chg_5d > -2:
        score += 8
    else:
        reasons.append(f"5d negative {chg_5d:+.1f}%")

    if vol_20 < 18:
        score += 10
        reasons.append("Volatility contained")
    elif vol_20 > 28:
        score -= 5
        reasons.append("High volatility regime")

    score = max(0, min(100, score))
    if score >= 70:
        regime = "BULLISH"
    elif score >= 45:
        regime = "NEUTRAL"
    else:
        regime = "BEARISH"

    min_score = CONFIG.get("regime_min_score", 45)
    trade_approval = score >= min_score
    if not CONFIG.get("regime_filter_enabled", True):
        trade_approval = True

    return {
        "score": round(score, 1),
        "regime": regime,
        "trade_approval": trade_approval,
        "reason": "; ".join(reasons[:4]),
        "change_20d": round(chg_20d, 2),
        "change_5d": round(chg_5d, 2),
        "above_200dma": above_200,
        "above_50dma": above_50,
        "volatility_ann_pct": round(vol_20, 1),
        "price": round(price, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2),
        "min_score": min_score,
    }


def apply_regime_to_picks(picks: list[dict], regime: dict | None = None) -> list[dict]:
    """Discount scores / block weak BUYs when regime is bearish."""
    regime = regime or market_health()
    approval = regime.get("trade_approval", True)
    rname = regime.get("regime", "NEUTRAL")
    rscore = float(regime.get("score") or 50)

    out = []
    for p in picks:
        row = dict(p)
        row["regime"] = rname
        row["regime_score"] = rscore
        row["regime_approval"] = approval
        if not approval:
            # Heavy penalty — do not promote weak setups in bear markets
            row["swing_score"] = max(0, float(row.get("swing_score") or 0) - 20)
            if row.get("signal") in ("BUY", "STRONG BUY"):
                if row["swing_score"] < CONFIG.get("min_buy_score", 68):
                    row["signal"] = "WATCH"
                    row["regime_note"] = "Regime weak — BUY blocked"
                else:
                    row["regime_note"] = "Regime weak — only strongest setups"
            else:
                row["regime_note"] = "Regime weak"
        elif rname == "NEUTRAL":
            row["swing_score"] = max(0, float(row.get("swing_score") or 0) - 5)
            row["regime_note"] = "Neutral market — mild discount"
        else:
            row["regime_note"] = "Bullish regime OK"
        out.append(row)

    out.sort(key=lambda x: x.get("swing_score", 0), reverse=True)
    return out
