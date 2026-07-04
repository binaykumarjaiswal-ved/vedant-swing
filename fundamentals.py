"""PE, earnings, quarterly growth — yfinance with cache."""

from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

import yfinance as yf

from nse_data import YAHOO_MAP

BASE_DIR = Path(__file__).parent
CACHE_DIR = BASE_DIR / "data" / "cache" / "fundamentals"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_HOURS = 24


def _ticker(symbol: str) -> str:
    t = YAHOO_MAP.get(symbol, f"{symbol}.NS")
    return t if t.endswith(".NS") else f"{t}.NS"


def _cache_path(symbol: str) -> Path:
    return CACHE_DIR / f"{symbol}.json"


def _read_cache(symbol: str) -> dict | None:
    p = _cache_path(symbol)
    if not p.exists():
        return None
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        age_h = (datetime.now() - datetime.fromisoformat(d["ts"])).total_seconds() / 3600
        if age_h < CACHE_HOURS:
            return d["data"]
    except (json.JSONDecodeError, KeyError, ValueError):
        pass
    return None


def _write_cache(symbol: str, data: dict) -> None:
    _cache_path(symbol).write_text(
        json.dumps({"ts": datetime.now().isoformat(), "data": data}, indent=2),
        encoding="utf-8",
    )


def fetch_fundamentals(symbol: str) -> dict:
    """PE, EPS growth, revenue growth, last earnings, verdict."""
    cached = _read_cache(symbol)
    if cached:
        return cached

    result = {
        "pe_trailing": None,
        "pe_forward": None,
        "eps_growth_pct": None,
        "revenue_growth_pct": None,
        "profit_margin_pct": None,
        "last_earnings": "",
        "quarter_trend": "unknown",
        "fund_score": 50,
        "fund_verdict": "No data",
        "fund_notes": [],
    }

    try:
        t = yf.Ticker(_ticker(symbol))
        info = t.info or {}

        pe = info.get("trailingPE") or info.get("forwardPE")
        fpe = info.get("forwardPE")
        if pe and pe > 0:
            result["pe_trailing"] = round(float(pe), 1)
        if fpe and fpe > 0:
            result["pe_forward"] = round(float(fpe), 1)

        eg = info.get("earningsQuarterlyGrowth") or info.get("earningsGrowth")
        if eg is not None:
            result["eps_growth_pct"] = round(float(eg) * 100, 1)

        rg = info.get("revenueGrowth")
        if rg is not None:
            result["revenue_growth_pct"] = round(float(rg) * 100, 1)

        margin = info.get("profitMargins")
        if margin is not None:
            result["profit_margin_pct"] = round(float(margin) * 100, 1)

        # Last earnings date
        try:
            cal = t.calendar
            if cal is not None and not (hasattr(cal, "empty") and cal.empty):
                if isinstance(cal, dict) and cal.get("Earnings Date"):
                    ed = cal["Earnings Date"]
                    if isinstance(ed, list) and ed:
                        result["last_earnings"] = str(ed[0])[:10]
                elif hasattr(cal, "index"):
                    result["last_earnings"] = str(cal.index[0])[:10] if len(cal.index) else ""
        except Exception:
            pass

        score = 50
        notes = []

        if result["eps_growth_pct"] is not None:
            if result["eps_growth_pct"] > 15:
                score += 15
                result["quarter_trend"] = "strong"
                notes.append(f"EPS growth {result['eps_growth_pct']:+.1f}%")
            elif result["eps_growth_pct"] > 5:
                score += 8
                result["quarter_trend"] = "positive"
                notes.append(f"EPS growth {result['eps_growth_pct']:+.1f}%")
            elif result["eps_growth_pct"] < -10:
                score -= 15
                result["quarter_trend"] = "weak"
                notes.append(f"EPS decline {result['eps_growth_pct']:.1f}%")

        if result["revenue_growth_pct"] is not None:
            if result["revenue_growth_pct"] > 10:
                score += 8
                notes.append(f"Revenue +{result['revenue_growth_pct']:.1f}%")
            elif result["revenue_growth_pct"] < 0:
                score -= 8
                notes.append(f"Revenue {result['revenue_growth_pct']:.1f}%")

        if result["pe_trailing"]:
            pe_v = result["pe_trailing"]
            if pe_v < 25:
                score += 5
                notes.append(f"PE {pe_v} reasonable")
            elif pe_v > 50:
                score -= 8
                notes.append(f"PE {pe_v} expensive")

        score = max(0, min(100, score))
        result["fund_score"] = score
        result["fund_notes"] = notes

        if score >= 65:
            result["fund_verdict"] = "Strong fundamentals"
        elif score >= 50:
            result["fund_verdict"] = "Average fundamentals"
        else:
            result["fund_verdict"] = "Weak fundamentals"

        _write_cache(symbol, result)
        time.sleep(0.15)
    except Exception:
        result["fund_verdict"] = "Fetch failed"

    return result


def blend_fundamental_score(swing_score: float, fund: dict, weight: float = 0.12) -> float:
    fs = fund.get("fund_score", 50)
    blended = swing_score * (1 - weight) + fs * weight
    if fund.get("quarter_trend") == "weak":
        blended -= 10
    elif fund.get("quarter_trend") == "strong":
        blended += 4
    return max(0, min(100, round(blended, 1)))