"""Validate past predictions against actual price paths (model audit)."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))


def _forward_path(symbol: str, pred_date: str, horizon: int = 7) -> dict[str, Any] | None:
    """OHLCV path from pred_date for up to horizon trading days after."""
    from technical import fetch_ohlcv

    df = fetch_ohlcv(symbol, days=120)
    if df is None or df.empty:
        return None

    # Normalize index to dates
    idx = df.index
    try:
        dates = [d.date() if hasattr(d, "date") else d for d in idx]
    except Exception:
        return None

    from datetime import date as date_cls

    try:
        pd0 = datetime.strptime(pred_date, "%Y-%m-%d").date()
    except ValueError:
        return None

    # First bar on or after pred_date
    start_i = None
    for i, d in enumerate(dates):
        if isinstance(d, date_cls) and d >= pd0:
            start_i = i
            break
    if start_i is None:
        return None

    window = df.iloc[start_i : start_i + horizon + 1]
    if len(window) < 2:
        return None

    entry_close = float(window["Close"].iloc[0])
    highs = window["High"].astype(float)
    lows = window["Low"].astype(float)
    last_close = float(window["Close"].iloc[-1])
    max_high = float(highs.max())
    min_low = float(lows.min())

    return {
        "entry_close": entry_close,
        "last_close": last_close,
        "max_high": max_high,
        "min_low": min_low,
        "bars": len(window),
        "return_pct": ((last_close / entry_close) - 1) * 100 if entry_close else 0,
        "max_gain_pct": ((max_high / entry_close) - 1) * 100 if entry_close else 0,
        "max_loss_pct": ((min_low / entry_close) - 1) * 100 if entry_close else 0,
    }


def audit_pending(min_age_days: int = 5, max_age_days: int = 21) -> dict[str, Any]:
    """Score pending predictions that are old enough."""
    from history_db import pending_predictions, save_outcome
    from market_calendar import ist_now

    pending = pending_predictions(max_age_days=max_age_days, min_age_days=min_age_days)
    audited = []
    errors = []

    for p in pending:
        symbol = p["symbol"]
        pred_date = p["pred_date"]
        entry = float(p.get("entry") or 0)
        target = float(p.get("target") or 0)
        stop = float(p.get("stop") or 0)
        horizon = int(p.get("horizon_days") or CONFIG.get("max_hold_days", 7))

        path = _forward_path(symbol, pred_date, horizon=horizon)
        if not path:
            errors.append({"symbol": symbol, "error": "no path data"})
            continue

        # Prefer stored entry; else first close
        if entry <= 0:
            entry = path["entry_close"]

        hit_target = False
        hit_stop = False
        if target > 0 and path["max_high"] >= target:
            hit_target = True
        if stop > 0 and path["min_low"] <= stop:
            hit_stop = True

        # Exit rule: target first if both (optimistic for audit — document this)
        if hit_target and not hit_stop:
            exit_price = target
            status = "target"
            ret = ((exit_price / entry) - 1) * 100
        elif hit_stop and not hit_target:
            exit_price = stop
            status = "stop"
            ret = ((exit_price / entry) - 1) * 100
        elif hit_target and hit_stop:
            # Ambiguous — use max gain vs max loss magnitude
            exit_price = target
            status = "both_hit_assume_target"
            ret = ((exit_price / entry) - 1) * 100
        else:
            exit_price = path["last_close"]
            status = "time_exit"
            ret = ((exit_price / entry) - 1) * 100

        outcome = {
            "symbol": symbol,
            "pred_date": pred_date,
            "check_date": ist_now().strftime("%Y-%m-%d"),
            "entry": entry,
            "exit_price": round(exit_price, 2),
            "return_pct": round(ret, 2),
            "hit_target": hit_target,
            "hit_stop": hit_stop,
            "max_gain_pct": round(path["max_gain_pct"], 2),
            "max_loss_pct": round(path["max_loss_pct"], 2),
            "days_held": path["bars"] - 1,
            "status": status,
            "notes": f"horizon={horizon}",
        }
        try:
            save_outcome(int(p["id"]), outcome)
            audited.append(outcome)
        except Exception as exc:
            errors.append({"symbol": symbol, "error": str(exc)})

    from history_db import performance_summary

    summary = performance_summary(days=90)
    return {
        "ok": True,
        "audited": len(audited),
        "errors": errors[:10],
        "outcomes": audited,
        "performance": summary,
        "generated": datetime.now().isoformat(timespec="seconds"),
    }


def run_audit_report() -> Path:
    result = audit_pending()
    out = BASE_DIR / "data" / "reports" / f"model_audit_{datetime.now().strftime('%Y-%m-%d')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    path = run_audit_report()
    print("Wrote", path)
    data = json.loads(path.read_text(encoding="utf-8"))
    print(json.dumps(data.get("performance"), indent=2))
