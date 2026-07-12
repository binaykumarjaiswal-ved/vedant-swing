"""Rank sectors by multi-period momentum — Today / Week / 20d / Month."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from sector_map import SECTOR_ETF, get_sector
from technical import fetch_ohlcv

BASE_DIR = Path(__file__).parent
CACHE = BASE_DIR / "data" / "cache" / "sector_strength.json"

# Trading-day lookbacks
PERIODS = {
    "today": {"bars": 1, "label": "Today", "key": "change_1d"},
    "week": {"bars": 5, "label": "Weekly", "key": "change_5d"},
    "d20": {"bars": 20, "label": "20-day", "key": "change_20d"},
    "month": {"bars": 21, "label": "Monthly", "key": "change_month"},
}


def _pct_change(df, bars: int) -> float:
    if df is None or len(df) < bars + 1:
        return 0.0
    try:
        last = float(df["Close"].iloc[-1])
        prev = float(df["Close"].iloc[-(bars + 1)])
        if prev <= 0:
            return 0.0
        return (last / prev - 1) * 100
    except Exception:
        return 0.0


def _sector_period_changes(etf_symbol: str) -> dict[str, float]:
    df = fetch_ohlcv(etf_symbol, days=90)
    out = {}
    for pid, meta in PERIODS.items():
        out[meta["key"]] = round(_pct_change(df, meta["bars"]), 2)
    return out


def get_sector_rankings(period: str = "d20") -> list[dict]:
    """
    Return sectors sorted by the selected period.
    period: today | week | d20 | month
    """
    if period not in PERIODS:
        period = "d20"
    sort_key = PERIODS[period]["key"]

    multi = _load_or_build_multi()
    ranks = list(multi.get("sectors") or [])
    ranks = sorted(ranks, key=lambda x: float(x.get(sort_key) or 0), reverse=True)
    # Normalize legacy field name for callers that expect change_20d
    out = []
    for r in ranks:
        row = dict(r)
        row["change"] = float(row.get(sort_key) or 0)
        # Keep change_20d for filter compatibility
        if "change_20d" not in row:
            row["change_20d"] = float(row.get("change_20d") or row.get("change") or 0)
        out.append(row)
    return out


def _load_or_build_multi() -> dict:
    if CACHE.exists():
        try:
            d = json.loads(CACHE.read_text(encoding="utf-8"))
            age_ok = datetime.now() - datetime.fromisoformat(d["updated"]) < timedelta(hours=6)
            if age_ok and d.get("sectors") and "change_1d" in (d["sectors"][0] or {}):
                return d
        except (json.JSONDecodeError, KeyError, ValueError, IndexError):
            pass

    seen_etfs: dict[str, dict] = {}
    by_name: dict[str, dict] = {}

    for sector, etf in SECTOR_ETF.items():
        if etf not in seen_etfs:
            seen_etfs[etf] = _sector_period_changes(etf)
        ch = seen_etfs[etf]
        if sector not in by_name:
            by_name[sector] = {
                "sector": sector,
                "etf": etf,
                **ch,
            }

    sectors = list(by_name.values())
    payload = {
        "updated": datetime.now().isoformat(),
        "sectors": sectors,
        "periods": {k: v["label"] for k, v in PERIODS.items()},
    }
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


def get_all_period_rankings(top_n: int = 12) -> dict:
    """Full multi-period payload for dashboard tabs."""
    multi = _load_or_build_multi()
    result = {
        "ok": True,
        "updated": multi.get("updated", ""),
        "periods": {},
    }
    for pid, meta in PERIODS.items():
        key = meta["key"]
        ranks = sorted(
            multi.get("sectors") or [],
            key=lambda x: float(x.get(key) or 0),
            reverse=True,
        )[:top_n]
        max_chg = max((abs(float(r.get(key) or 0)) for r in ranks), default=1) or 1
        rows = []
        for i, r in enumerate(ranks, 1):
            chg = float(r.get(key) or 0)
            rows.append({
                "sector": r.get("sector"),
                "etf": r.get("etf"),
                "change": round(chg, 2),
                "change_20d": float(r.get("change_20d") or 0),  # filter compat
                "rank": i,
                "strong": i <= 5,
                "bar_pct": min(100, int(abs(chg) / max_chg * 100)),
            })
        result["periods"][pid] = {
            "id": pid,
            "label": meta["label"],
            "key": key,
            "sectors": rows,
            "top_n_strong": 5,
        }
    return result


def strong_sectors(top_n: int = 5) -> set[str]:
    # Filter still uses 20-day momentum (stable for swing)
    ranks = get_sector_rankings("d20")
    return {r["sector"] for r in ranks[:top_n]}


def sector_filter_pass(symbol: str, top_n: int = 5) -> tuple[bool, str]:
    sector = get_sector(symbol)
    if sector == "Other":
        return True, sector
    strong = strong_sectors(top_n)
    ok = sector in strong
    return ok, sector


def format_sector_report(top_n: int = 8) -> str:
    lines = ["── SECTOR STRENGTH ──"]
    multi = get_all_period_rankings(top_n=top_n)
    for pid in ("today", "week", "d20", "month"):
        block = multi["periods"].get(pid) or {}
        lines.append(f"  [{block.get('label', pid)}]")
        for i, r in enumerate((block.get("sectors") or [])[:5], 1):
            tag = "STRONG" if r.get("strong") else ""
            lines.append(f"    #{i} {r['sector']}: {r['change']:+.1f}% {tag}")
    return "\n".join(lines)
