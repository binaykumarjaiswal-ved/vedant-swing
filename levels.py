"""Support and resistance from price history."""

from __future__ import annotations

import pandas as pd


def calc_support_resistance(df: pd.DataFrame, price: float) -> dict:
    """Swing S/R + classic pivot levels."""
    if df is None or len(df) < 20:
        return {
            "support": round(price * 0.97, 2),
            "resistance": round(price * 1.03, 2),
            "pivot": round(price, 2),
            "s1": round(price * 0.99, 2),
            "r1": round(price * 1.01, 2),
            "near_support": False,
            "near_resistance": False,
            "level_note": "Estimated from price",
        }

    recent = df.tail(60)
    low_col = recent["Low"]
    high_col = recent["High"]

    support = float(low_col.min())
    resistance = float(high_col.max())

    # Nearest swing low above absolute min (second support)
    lows_sorted = sorted(low_col.nsmallest(5).unique())
    support2 = lows_sorted[1] if len(lows_sorted) > 1 else support

    last = recent.iloc[-1]
    pivot = (float(last["High"]) + float(last["Low"]) + float(last["Close"])) / 3
    s1 = 2 * pivot - float(last["High"])
    r1 = 2 * pivot - float(last["Low"])

    dist_sup = ((price - support) / price) * 100 if price else 0
    dist_res = ((resistance - price) / price) * 100 if price else 0

    note_parts = []
    if dist_sup < 3:
        note_parts.append(f"Near support Rs.{support:.0f}")
    if dist_res < 3:
        note_parts.append(f"Near resistance Rs.{resistance:.0f}")
    if price >= resistance * 0.98:
        note_parts.append("Testing resistance")
    if price <= support * 1.02:
        note_parts.append("Near support bounce zone")

    return {
        "support": round(support, 2),
        "support2": round(support2, 2),
        "resistance": round(resistance, 2),
        "pivot": round(pivot, 2),
        "s1": round(s1, 2),
        "r1": round(r1, 2),
        "near_support": dist_sup < 3,
        "near_resistance": dist_res < 3,
        "dist_support_pct": round(dist_sup, 1),
        "dist_resistance_pct": round(dist_res, 1),
        "level_note": " | ".join(note_parts) if note_parts else f"S {support:.0f} / R {resistance:.0f}",
    }