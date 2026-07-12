"""
Historical backtest of technical score buckets + simple swing rules.

Recommend-only validation — no broker simulation beyond entry/exit prices.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _score_bar(df: pd.DataFrame, i: int) -> float | None:
    """Lightweight score at bar i using lookback only (no future leak)."""
    if i < 55:
        return None
    window = df.iloc[: i + 1]
    close = window["Close"]
    high = window["High"]
    low = window["Low"]
    volume = window["Volume"]

    # RSI 14
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, np.nan)
    rsi = float((100 - (100 / (1 + rs))).iloc[-1])
    if np.isnan(rsi):
        rsi = 50.0

    ema20 = float(close.ewm(span=20, adjust=False).mean().iloc[-1])
    ema50 = float(close.ewm(span=50, adjust=False).mean().iloc[-1])
    price = float(close.iloc[-1])
    vol_avg = float(volume.tail(20).mean()) if len(volume) >= 20 else float(volume.mean())
    vol_today = float(volume.iloc[-1])
    vol_ratio = vol_today / vol_avg if vol_avg > 0 else 1.0
    chg_5d = float((close.iloc[-1] / close.iloc[-6] - 1) * 100) if len(close) > 5 else 0

    score = 0.0
    if 40 <= rsi <= 60:
        score += 25
    elif 35 <= rsi < 40:
        score += 18
    elif 60 < rsi <= 68:
        score += 12
    elif rsi > 72:
        score -= 15

    if price > ema20:
        score += 12
    if price > ema20 > ema50:
        score += 10
    if -2 <= chg_5d <= 4:
        score += 8
    elif chg_5d > 6:
        score -= 8
    if vol_ratio >= 1.15:
        score += 8

    return max(0, min(100, score))


def backtest_symbol(
    symbol: str,
    days: int = 400,
    horizon: int = 7,
    target_pct: float = 3.0,
    stop_pct: float = 3.0,
    min_score: float = 62,
) -> dict[str, Any]:
    from technical import fetch_ohlcv

    df = fetch_ohlcv(symbol, days=days)
    if df is None or len(df) < 80:
        return {"symbol": symbol, "ok": False, "error": "insufficient data", "trades": []}

    trades = []
    i = 55
    while i < len(df) - horizon - 1:
        sc = _score_bar(df, i)
        if sc is None or sc < min_score:
            i += 1
            continue

        entry = float(df["Close"].iloc[i])
        target = entry * (1 + target_pct / 100)
        stop = entry * (1 - stop_pct / 100)
        fwd = df.iloc[i + 1 : i + 1 + horizon]
        hit_t = False
        hit_s = False
        exit_price = float(fwd["Close"].iloc[-1])
        exit_reason = "time"
        for _, bar in fwd.iterrows():
            hi = float(bar["High"])
            lo = float(bar["Low"])
            if lo <= stop:
                hit_s = True
                exit_price = stop
                exit_reason = "stop"
                break
            if hi >= target:
                hit_t = True
                exit_price = target
                exit_reason = "target"
                break

        ret = ((exit_price / entry) - 1) * 100
        trades.append({
            "symbol": symbol,
            "score": round(sc, 1),
            "entry": round(entry, 2),
            "exit": round(exit_price, 2),
            "return_pct": round(ret, 2),
            "exit_reason": exit_reason,
            "hit_target": hit_t,
            "hit_stop": hit_s,
        })
        # Skip horizon to avoid overlapping trades on same symbol
        i += horizon

    if not trades:
        return {"symbol": symbol, "ok": True, "trades": [], "n": 0}

    rets = [t["return_pct"] for t in trades]
    wins = sum(1 for r in rets if r > 0)
    return {
        "symbol": symbol,
        "ok": True,
        "n": len(trades),
        "win_rate": round(wins / len(trades) * 100, 1),
        "avg_return_pct": round(sum(rets) / len(rets), 2),
        "hit_target_rate": round(sum(1 for t in trades if t["hit_target"]) / len(trades) * 100, 1),
        "trades": trades,
    }


def backtest_universe(
    symbols: list[str] | None = None,
    max_symbols: int = 40,
    horizon: int = 7,
    min_score: float = 62,
) -> dict[str, Any]:
    from stock_universe import get_universe

    if symbols is None:
        symbols = get_universe()["all"][:max_symbols]
    else:
        symbols = symbols[:max_symbols]

    all_trades = []
    per_symbol = []
    for i, sym in enumerate(symbols):
        print(f"[Backtest] {i + 1}/{len(symbols)} {sym}", flush=True)
        r = backtest_symbol(sym, horizon=horizon, min_score=min_score)
        if r.get("ok") and r.get("trades"):
            all_trades.extend(r["trades"])
            per_symbol.append({
                "symbol": sym,
                "n": r["n"],
                "win_rate": r["win_rate"],
                "avg_return_pct": r["avg_return_pct"],
            })

    if not all_trades:
        return {
            "ok": True,
            "n_trades": 0,
            "message": "No trades met score threshold in sample.",
            "symbols_tested": len(symbols),
        }

    rets = [t["return_pct"] for t in all_trades]
    wins = sum(1 for r in rets if r > 0)

    # Score buckets
    buckets = {"62-70": [], "70-80": [], "80-100": []}
    for t in all_trades:
        s = t["score"]
        if s < 70:
            buckets["62-70"].append(t["return_pct"])
        elif s < 80:
            buckets["70-80"].append(t["return_pct"])
        else:
            buckets["80-100"].append(t["return_pct"])

    by_bucket = {}
    for k, vals in buckets.items():
        if vals:
            by_bucket[k] = {
                "n": len(vals),
                "avg_return_pct": round(sum(vals) / len(vals), 2),
                "win_rate": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
            }

    result = {
        "ok": True,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "symbols_tested": len(symbols),
        "n_trades": len(all_trades),
        "win_rate": round(wins / len(all_trades) * 100, 1),
        "avg_return_pct": round(sum(rets) / len(rets), 2),
        "hit_target_rate": round(
            sum(1 for t in all_trades if t["hit_target"]) / len(all_trades) * 100, 1
        ),
        "by_score_bucket": by_bucket,
        "top_symbols": sorted(per_symbol, key=lambda x: x.get("avg_return_pct") or 0, reverse=True)[:10],
        "min_score": min_score,
        "horizon_days": horizon,
        "note": "Historical heuristic backtest. Not a guarantee of future results.",
    }

    out = BASE_DIR / "data" / "reports" / f"backtest_{datetime.now().strftime('%Y-%m-%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    result["file"] = str(out)
    return result


if __name__ == "__main__":
    import sys

    n = int(sys.argv[1]) if len(sys.argv) > 1 else 25
    r = backtest_universe(max_symbols=n)
    print(json.dumps({k: r[k] for k in r if k != "top_symbols"}, indent=2))
    print("Top symbols:", r.get("top_symbols"))
