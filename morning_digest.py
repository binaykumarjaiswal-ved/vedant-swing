"""One combined morning Telegram message — AI news + research + signal + ETF."""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import feedparser


def fetch_ai_news(sources: list[dict], max_items: int = 5) -> str:
    lines = ["AI NEWS TODAY"]
    count = 0
    for src in sources:
        try:
            feed = feedparser.parse(src["url"])
        except Exception:
            continue
        for entry in feed.entries[:3]:
            title = re.sub(r"<[^>]+>", "", entry.get("title", "").strip())
            if not title:
                continue
            lines.append(f"  - {title[:100]}")
            count += 1
            if count >= max_items:
                break
        if count >= max_items:
            break
    if count == 0:
        lines.append("  (no headlines fetched)")
    return "\n".join(lines)


def format_research_picks(picks: list[dict], max_picks: int = 5) -> str:
    lines = ["TOP RESEARCH PICKS (3% swing)"]
    if not picks:
        lines.append("  No strong setups today.")
        return "\n".join(lines)
    for i, p in enumerate(picks[:max_picks], 1):
        best = p.get("best_buy_price", p.get("entry", p.get("price", 0)))
        lines.append(
            f"  #{i} {p['symbol']} — {p.get('signal', 'WATCH')} "
            f"score {p.get('swing_score', 0):.0f} | buy Rs.{best:.2f}"
        )
    return "\n".join(lines)


def read_etf_section(cfg: dict) -> str:
    if not cfg.get("digest", {}).get("send_etf_signals", True):
        return ""
    etf_path = cfg.get("digest", {}).get("etf_agent_path", "")
    if not etf_path:
        return ""
    folder = Path(etf_path) / "reports"
    if not folder.exists():
        return ""
    reports = sorted(folder.glob("daily_action_*.txt"), reverse=True)
    if not reports:
        return ""
    lines = ["ETF BUY/SELL SIGNALS"]
    for line in reports[0].read_text(encoding="utf-8", errors="replace").splitlines():
        if any(x in line for x in ("BUY", "SELL", "TRIM", "ADD", "▶", "Market mood")):
            lines.append(line.strip())
        if len(lines) > 12:
            break
    return "\n".join(lines) if len(lines) > 1 else ""


def build_combined_morning(
    cfg: dict,
    benchmark: dict,
    research_picks: list[dict],
    trading_signal: str,
    ai_summary: str = "",
) -> str:
    """Single morning message for Telegram."""
    now = datetime.now().strftime("%d %b %Y %I:%M %p")
    digest_cfg = cfg.get("digest", {})
    parts = [
        f"MORNING BRIEFING — {now}",
        "=" * 40,
        f"Market: {benchmark.get('mood', 'NEUTRAL')} ({benchmark.get('change_20d', 0):+.1f}% 20d)",
        "",
    ]

    if digest_cfg.get("send_ai_news", True):
        sources = digest_cfg.get("ai_news_sources", [])
        if sources:
            parts.append(fetch_ai_news(sources, digest_cfg.get("max_news_items", 5)))
            parts.append("")

    parts.append(format_research_picks(research_picks, cfg.get("top_research_picks", 5)))
    parts.append("")

    if ai_summary:
        parts.extend(["AI BRIEFING", ai_summary[:600], ""])

    etf = read_etf_section(cfg)
    if etf:
        parts.append(etf)
        parts.append("")

    parts.extend([
        "── TODAY'S TRADING SIGNAL ──",
        trading_signal.strip(),
        "",
        "Not financial advice. Do your own research.",
    ])
    return "\n".join(parts)