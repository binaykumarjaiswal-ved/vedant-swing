"""
Market + stock sentiment engine for Vedant Swing.

Combines RSS news lexicon scores, headline intensity, and market regime
into a clear pulse (0–100) for the professional dashboard.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
CACHE_FILE = BASE_DIR / "data" / "cache" / "sentiment_pulse.json"
CACHE_TTL_SEC = 900  # 15 minutes

# Expanded India equity lexicon (phrase-aware, longest first when matching)
POSITIVE = [
    "all-time high", "record high", "beat estimates", "beats estimates",
    "strong results", "robust growth", "order win", "order book", "mega order",
    "capacity expansion", "new plant", "breakthrough", "outperform", "upgrade to buy",
    "raised guidance", "guidance raise", "margin expansion", "profit surge",
    "profit jump", "earnings beat", "revenue growth", "volume spike", "fii buying",
    "institutional buying", "block deal buy", "stake sale premium", "dividend hike",
    "bonus issue", "stock split", "buyback", "open offer", "strategic partnership",
    "joint venture", "export growth", "demand rebound", "capex boost",
    "bullish", "rally", "surges", "surge", "jumps", "soars", "zooms", "gains",
    "rebound", "recovery", "momentum", "breakout", "uptrend", "strong",
    "positive", "optimistic", "upgrade", "outperform", "accumulate", "buy rating",
    "profit", "growth", "expansion", "deal", "contract win", "award",
    "fii inflows", "dii buying", "inflows", "risk-on", "green", "advances",
]

NEGATIVE = [
    "all-time low", "record low", "miss estimates", "misses estimates",
    "weak results", "profit warning", "guidance cut", "cut guidance",
    "margin pressure", "margin contraction", "revenue miss", "earnings miss",
    "order cancel", "order cancellation", "plant shutdown", "fire at plant",
    "fraud", "scam", "probe", "investigation", "raid", "sebi notice", "show cause",
    "penalty", "fine imposed", "default", "downgrade to sell", "rating cut",
    "fii selling", "institutional selling", "block deal sell", "promoter pledge",
    "pledge rise", "debt concern", "liquidity crunch", "layoff", "job cuts",
    "bearish", "crash", "slump", "plunges", "plunge", "tumbles", "tumble",
    "falls", "fall", "drops", "drop", "selloff", "sell-off", "correction",
    "weak", "negative", "pessimistic", "downgrade", "underperform", "reduce",
    "sell rating", "loss", "concern", "risk", "warning", "outflows",
    "fii outflows", "risk-off", "red", "declines", "break below",
    "circuit limit", "lower circuit", "ban", "restriction", "litigation",
]


def score_text(text: str) -> dict[str, Any]:
    """Return sentiment in [-1, 1] with label and hit counts."""
    t = (text or "").lower()
    if not t.strip():
        return {"score": 0.0, "label": "NEUTRAL", "pos_hits": 0, "neg_hits": 0}

    pos = sum(1 for p in POSITIVE if p in t)
    neg = sum(1 for n in NEGATIVE if n in t)
    total = pos + neg
    if total == 0:
        score = 0.0
    else:
        score = (pos - neg) / total
        # Intensity boost for multiple hits
        intensity = min(1.0, total / 6)
        score = max(-1.0, min(1.0, score * (0.7 + 0.3 * intensity)))

    if score >= 0.25:
        label = "BULLISH"
    elif score <= -0.25:
        label = "BEARISH"
    elif score >= 0.08:
        label = "MILD_BULL"
    elif score <= -0.08:
        label = "MILD_BEAR"
    else:
        label = "NEUTRAL"

    return {
        "score": round(score, 3),
        "label": label,
        "pos_hits": pos,
        "neg_hits": neg,
    }


def _pulse_from_headlines(headlines: list[dict]) -> dict[str, Any]:
    if not headlines:
        return {
            "score_100": 50,
            "avg_sentiment": 0.0,
            "label": "NEUTRAL",
            "headline_count": 0,
            "bullish_pct": 0,
            "bearish_pct": 0,
            "top_bullish": [],
            "top_bearish": [],
            "feed": [],
        }

    scores = []
    feed = []
    for h in headlines:
        raw = h.get("sentiment")
        if raw is None:
            sc = score_text(f"{h.get('title', '')} {h.get('summary', '')}")
            sent = sc["score"]
            label = sc["label"]
        else:
            sent = float(raw)
            if sent >= 0.25:
                label = "BULLISH"
            elif sent <= -0.25:
                label = "BEARISH"
            else:
                label = "NEUTRAL"
        scores.append(sent)
        feed.append({
            "title": (h.get("title") or "")[:120],
            "source": h.get("source", ""),
            "sentiment": round(sent, 2),
            "label": label,
            "link": h.get("link", ""),
        })

    avg = sum(scores) / len(scores)
    bull = sum(1 for s in scores if s > 0.1)
    bear = sum(1 for s in scores if s < -0.1)
    n = len(scores)
    # Map [-1,1] → [0,100]
    score_100 = int(round(50 + avg * 45))
    score_100 = max(0, min(100, score_100))

    if score_100 >= 65:
        overall = "RISK-ON"
    elif score_100 <= 35:
        overall = "RISK-OFF"
    elif score_100 >= 55:
        overall = "CAUTIOUS_BULL"
    elif score_100 <= 45:
        overall = "CAUTIOUS_BEAR"
    else:
        overall = "NEUTRAL"

    feed_sorted = sorted(feed, key=lambda x: abs(x["sentiment"]), reverse=True)
    return {
        "score_100": score_100,
        "avg_sentiment": round(avg, 3),
        "label": overall,
        "headline_count": n,
        "bullish_pct": round(bull / n * 100, 1),
        "bearish_pct": round(bear / n * 100, 1),
        "top_bullish": [f for f in feed_sorted if f["sentiment"] > 0.15][:5],
        "top_bearish": [f for f in feed_sorted if f["sentiment"] < -0.15][:5],
        "feed": feed_sorted[:12],
    }


def market_sentiment_pulse(force: bool = False) -> dict[str, Any]:
    """Cached market-wide news sentiment pulse."""
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not force and CACHE_FILE.exists():
        try:
            cached = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if time.time() - cached.get("ts", 0) < CACHE_TTL_SEC:
                return cached.get("pulse", cached)
        except (json.JSONDecodeError, OSError):
            pass

    try:
        cfg = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))
    except Exception:
        cfg = {}

    sources = cfg.get("news_sources") or []
    # Extra sentiment-focused sources
    extra = [
        {"name": "Google News Markets", "url": "https://news.google.com/rss/search?q=Nifty+Sensex+stock+market+India&hl=en-IN&gl=IN&ceid=IN:en"},
        {"name": "Google FII DII", "url": "https://news.google.com/rss/search?q=FII+DII+India+markets&hl=en-IN&gl=IN&ceid=IN:en"},
        {"name": "Google RBI Economy", "url": "https://news.google.com/rss/search?q=RBI+inflation+India+economy&hl=en-IN&gl=IN&ceid=IN:en"},
    ]
    # Dedupe by URL
    seen_urls = {s.get("url") for s in sources}
    for e in extra:
        if e["url"] not in seen_urls:
            sources.append(e)
            seen_urls.add(e["url"])

    from news_fetcher import fetch_news

    news = fetch_news(sources, symbols=[], max_age_hours=cfg.get("news_max_age_hours", 48))
    headlines = news.get("market_headlines") or news.get("all_headlines") or []
    # Also use all items if market empty
    if not headlines and news.get("total"):
        headlines = []
        for items in (news.get("by_symbol") or {}).values():
            headlines.extend(items)

    pulse = _pulse_from_headlines(headlines[:40])

    # Blend lightly with technical regime
    try:
        from market_regime import market_health
        regime = market_health()
        rscore = float(regime.get("score") or 50)
        blended = int(round(pulse["score_100"] * 0.55 + rscore * 0.45))
        pulse["score_100"] = max(0, min(100, blended))
        pulse["regime"] = regime.get("regime")
        pulse["regime_score"] = rscore
        pulse["trade_approval"] = regime.get("trade_approval", True)
        pulse["regime_reason"] = regime.get("reason", "")
    except Exception:
        pulse["regime"] = "NEUTRAL"
        pulse["regime_score"] = 50
        pulse["trade_approval"] = True
        pulse["regime_reason"] = ""

    # Re-label after blend
    s = pulse["score_100"]
    if s >= 65:
        pulse["label"] = "RISK-ON"
    elif s <= 35:
        pulse["label"] = "RISK-OFF"
    elif s >= 55:
        pulse["label"] = "CAUTIOUS_BULL"
    elif s <= 45:
        pulse["label"] = "CAUTIOUS_BEAR"
    else:
        pulse["label"] = "NEUTRAL"

    pulse["action_hint"] = _action_hint(pulse)
    pulse["updated"] = time.strftime("%Y-%m-%d %H:%M")

    try:
        CACHE_FILE.write_text(
            json.dumps({"ts": time.time(), "pulse": pulse}, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass
    return pulse


def _action_hint(pulse: dict) -> str:
    label = pulse.get("label", "NEUTRAL")
    if not pulse.get("trade_approval", True) or label == "RISK-OFF":
        return "Prefer NO new buys. Protect capital; wait for better market pulse."
    if label == "RISK-ON":
        return "Market pulse supports swing entries — still use stop-loss on every trade."
    if label == "CAUTIOUS_BULL":
        return "Selective buys only — high confidence + strong sectors."
    if label == "CAUTIOUS_BEAR":
        return "Reduce size / fewer trades. Wait for clearer bullish news."
    return "Neutral market — trade only A+ setups with tight risk."


def enrich_pick_sentiment(pick: dict, news_items: list | None = None) -> dict:
    """Attach richer sentiment fields to a scanner pick."""
    items = news_items or []
    if not items and pick.get("news_summary"):
        sc = score_text(pick.get("news_summary", ""))
        pick["news_sentiment"] = sc["score"]
        pick["sentiment_label"] = sc["label"]
        pick["sentiment_detail"] = sc
        return pick

    if not items:
        pick.setdefault("news_sentiment", 0.0)
        pick["sentiment_label"] = "NO_NEWS"
        return pick

    scores = []
    for it in items:
        if "sentiment" in it:
            scores.append(float(it["sentiment"]))
        else:
            scores.append(score_text(f"{it.get('title','')} {it.get('summary','')}")["score"])
    avg = sum(scores) / len(scores)
    pick["news_sentiment"] = round(avg, 3)
    if avg >= 0.25:
        pick["sentiment_label"] = "BULLISH"
    elif avg <= -0.25:
        pick["sentiment_label"] = "BEARISH"
    else:
        pick["sentiment_label"] = "NEUTRAL"
    pick["news_count"] = len(items)
    return pick
