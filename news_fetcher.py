"""Fetch and filter trading news from public RSS feeds."""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

import feedparser

SYMBOL_ALIASES: dict[str, list[str]] = {
    "RELIANCE": ["reliance", "ril", "jio", "reliance industries"],
    "TCS": ["tcs", "tata consultancy"],
    "INFY": ["infosys", "infy"],
    "HDFCBANK": ["hdfc bank", "hdfcbank"],
    "ICICIBANK": ["icici bank", "icicibank"],
    "ITC": ["itc ltd", "itc limited"],
    "SBIN": ["sbi", "state bank"],
    "BHARTIARTL": ["airtel", "bharti airtel"],
    "TATAMOTORS": ["tata motors", "tatamotors"],
    "MARUTI": ["maruti", "maruti suzuki"],
    "HINDUNILVR": ["hul", "hindustan unilever"],
    "BAJFINANCE": ["bajaj finance", "bajfinance"],
    "KOTAKBANK": ["kotak", "kotak bank"],
    "LT": ["larsen", "l&t", "l and t"],
    "AXISBANK": ["axis bank"],
    "WIPRO": ["wipro"],
    "HCLTECH": ["hcl tech", "hcltech"],
    "SUNPHARMA": ["sun pharma", "sunpharmaceutical"],
    "TITAN": ["titan company"],
    "ADANIENT": ["adani enterprises"],
    "ADANIPORTS": ["adani ports"],
    "ZOMATO": ["zomato"],
    "INDIGO": ["indigo", "interglobe"],
    "BRITANNIA": ["britannia"],
}


def _parse_date(entry: dict) -> datetime | None:
    for field in ("published_parsed", "updated_parsed"):
        parsed = entry.get(field)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass
    return None


def _match_symbols(text: str, symbols: list[str]) -> list[str]:
    text_lower = text.lower()
    matched = []
    for sym in symbols:
        patterns = [sym.lower().replace("-", " ")]
        if sym in SYMBOL_ALIASES:
            patterns.extend(SYMBOL_ALIASES[sym])
        for pat in patterns:
            if len(pat) >= 3 and re.search(rf"\b{re.escape(pat)}\b", text_lower):
                matched.append(sym)
                break
    return matched


def _sentiment_score(text: str) -> float:
    """Delegate to expanded India-equity lexicon in sentiment_engine."""
    try:
        from sentiment_engine import score_text
        return float(score_text(text)["score"])
    except Exception:
        text_l = text.lower()
        positive = [
            "surge", "rally", "gain", "profit", "growth", "upgrade", "bullish",
            "record high", "beat estimates", "strong", "outperform", "buy",
            "expansion", "deal win", "order book", "dividend", "fii buying",
        ]
        negative = [
            "fall", "drop", "crash", "loss", "downgrade", "bearish", "weak",
            "miss estimates", "selloff", "fraud", "probe", "penalty", "slump",
            "concern", "risk", "cut", "layoff", "default", "fii selling",
        ]
        pos = sum(1 for w in positive if w in text_l)
        neg = sum(1 for w in negative if w in text_l)
        if pos + neg == 0:
            return 0.0
        return (pos - neg) / (pos + neg)


def fetch_news(sources: list[dict], symbols: list[str], max_age_hours: int = 48) -> dict[str, Any]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    all_headlines: list[dict] = []
    market_headlines: list[dict] = []
    by_symbol: dict[str, list[dict]] = {s: [] for s in symbols}

    for src in sources:
        name = src.get("name", "Unknown")
        url = src.get("url", "")
        if not url:
            continue
        try:
            feed = feedparser.parse(url)
        except Exception:
            continue
        for entry in feed.entries[:40]:
            title = entry.get("title", "").strip()
            summary = entry.get("summary", entry.get("description", ""))
            summary = re.sub(r"<[^>]+>", "", summary)[:300]
            text = f"{title} {summary}"
            pub = _parse_date(entry)
            if pub and pub < cutoff:
                continue
            item = {
                "title": title,
                "summary": summary,
                "source": name,
                "link": entry.get("link", ""),
                "published": pub.isoformat() if pub else "",
                "sentiment": _sentiment_score(text),
            }
            matched = _match_symbols(text, symbols)
            if matched:
                for sym in matched:
                    by_symbol[sym].append(item)
            else:
                market_headlines.append(item)
            all_headlines.append(item)

    seen: set[str] = set()
    for sym in by_symbol:
        unique = []
        for item in by_symbol[sym]:
            key = item["title"][:80].lower()
            if key not in seen:
                seen.add(key)
                unique.append(item)
        by_symbol[sym] = unique[:8]

    return {
        "total": len(all_headlines),
        "market_headlines": market_headlines[:20],
        "by_symbol": by_symbol,
    }


def symbol_news_score(news_items: list[dict]) -> tuple[float, str]:
    if not news_items:
        return 0.0, "No recent news"
    # Re-score with latest lexicon if missing intensity
    scores = []
    for n in news_items:
        s = n.get("sentiment")
        if s is None:
            s = _sentiment_score(f"{n.get('title', '')} {n.get('summary', '')}")
            n["sentiment"] = s
        scores.append(float(s))
    avg_sent = sum(scores) / len(scores)
    # Slight volume boost: more headlines with same direction = stronger signal
    if len(scores) >= 3 and abs(avg_sent) > 0.1:
        avg_sent = max(-1.0, min(1.0, avg_sent * 1.1))
    top = sorted(news_items, key=lambda x: abs(float(x.get("sentiment") or 0)), reverse=True)[:2]
    summary = " | ".join(t["title"][:70] for t in top)
    return avg_sent, summary