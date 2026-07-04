"""AI analyst — Groq brain, Level 2/3 reports with checklist."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
CONFIG = json.loads((BASE_DIR / "config.json").read_text(encoding="utf-8"))

from pa_config import is_ai_enabled  # noqa: E402

AI_MODEL = CONFIG.get("ai_model", "llama-3.3-70b-versatile")
AI_MAX_TOKENS = CONFIG.get("ai_max_tokens", 1500)


def load_ai_keys() -> bool:
    if os.environ.get("GROQ_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        return True
    ai_tools = Path(CONFIG.get("ai_tools_path", r"D:\BINAY-Projects\01-GLM-AI-Tools"))
    ps1 = ai_tools / "load-ai-keys.ps1"
    if not ps1.exists():
        return False
    script = (
        f"& '{ps1}' | Out-Null; "
        "@{GEMINI_API_KEY=$env:GEMINI_API_KEY; GROQ_API_KEY=$env:GROQ_API_KEY; "
        "OPENROUTER_API_KEY=$env:OPENROUTER_API_KEY; GLM_API_KEY=$env:GLM_API_KEY} "
        "| ConvertTo-Json -Compress"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            cwd=str(ai_tools),
            check=True,
            capture_output=True,
            text=True,
        )
        keys = json.loads(result.stdout.strip())
        for name, value in keys.items():
            if value:
                os.environ[name] = value
        return bool(keys)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False


def _ask_groq_cloud(prompt: str, max_tokens: int | None = None) -> str:
    import requests

    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        return ""
    try:
        r = requests.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
            json={
                "model": AI_MODEL,
                "messages": [
                    {
                        "role": "system",
                        "content": (
                            "You are a SEBI-aware Indian equity research analyst. "
                            "Be structured, data-driven, honest about risks. "
                            "Never guarantee returns. Use Rs. for prices."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                "max_tokens": max_tokens or AI_MAX_TOKENS,
                "temperature": 0.35,
            },
            timeout=90,
        )
        r.raise_for_status()
        return r.json()["choices"][0]["message"]["content"].strip()
    except Exception:
        # Fallback to faster model
        if AI_MODEL != "llama-3.1-8b-instant":
            try:
                r = requests.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.1-8b-instant",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": min(800, max_tokens or 800),
                        "temperature": 0.4,
                    },
                    timeout=60,
                )
                r.raise_for_status()
                return r.json()["choices"][0]["message"]["content"].strip()
            except Exception:
                return ""
        return ""


def _ask(prompt: str, max_tokens: int | None = None) -> str:
    if os.environ.get("GROQ_API_KEY"):
        text = _ask_groq_cloud(prompt, max_tokens)
        if text:
            return text
    ai_tools = Path(CONFIG.get("ai_tools_path", r"D:\BINAY-Projects\01-GLM-AI-Tools"))
    if not ai_tools.exists():
        return ""
    sys.path.insert(0, str(ai_tools))
    try:
        from ai_client import ask  # noqa: WPS433
        text, _provider = ask(prompt)
        return text.strip()
    except Exception:
        return ""


def _format_headlines(p: dict) -> str:
    headlines = p.get("news_headlines") or []
    if not headlines:
        summary = (p.get("news_summary") or "").strip()
        return f"- {summary}" if summary else "- No recent headlines in RSS feeds"
    lines = []
    for h in headlines[:8]:
        title = (h.get("title") or "")[:120]
        source = h.get("source") or "News"
        sentiment = h.get("sentiment") or "neutral"
        lines.append(f"- [{source}] {title} ({sentiment})")
    return "\n".join(lines)


def _pick_context(p: dict) -> str:
    sector_note = "strong sector" if p.get("sector_strong") else "weak/neutral sector"
    lines = [
        f"{p['symbol']} ({p.get('sector', '?')} — {sector_note}) — {p.get('signal')} score {p.get('swing_score')}",
        f"  Price Rs.{p.get('price', 0):.2f} | Target +3% Rs.{p.get('target', 0):.2f} | Avg trigger Rs.{p.get('avg_trigger', '—')}",
        f"  RSI {p.get('rsi')} | Trend {p.get('trend')} | vs Nifty {p.get('vs_nifty_20d', 0):+.1f}%",
        f"  PE {p.get('pe_trailing', '—')} | EPS growth {p.get('eps_growth_pct', '—')}% | "
        f"Revenue growth {p.get('revenue_growth_pct', '—')}%",
        f"  Fundamentals: {p.get('fund_verdict', '—')} | Quarter: {p.get('quarter_trend', '—')}",
        f"  Support Rs.{p.get('support', '—')} | Resistance Rs.{p.get('resistance', '—')} | {p.get('level_note', '')}",
        f"  News sentiment {p.get('news_sentiment', 0):+.2f} ({p.get('news_count', 0)} items) | "
        f"Summary: {(p.get('news_summary') or '')[:160]}",
        "  Recent headlines (RSS — Moneycontrol, ET, Livemint, Google News):",
        _format_headlines(p),
    ]
    return "\n".join(lines)


def generate_morning_briefing(
    picks: list[dict],
    market_headlines: list[dict],
    benchmark: dict,
    sector_report: str = "",
) -> str:
    if not is_ai_enabled():
        return ""
    if not load_ai_keys():
        return ""

    pick_blocks = "\n\n".join(_pick_context(p) for p in picks[:5])
    headlines = "\n".join(f"- {h['title'][:90]}" for h in market_headlines[:8])

    prompt = f"""Indian Nifty swing research — full morning decision report (500-700 words).

STRATEGY: Delivery swing, +3% profit target, Rs.30,000/trade, max 5 averages on -3%.
UNIVERSE: Nifty 50 + Next 50 | Scan: 100 stocks | Sector filter: top 5 strong sectors only.

MARKET: {benchmark.get('mood')} | Nifty 20d {benchmark.get('change_20d', 0):+.1f}%

{sector_report}

TOP 5 PICKS (technical + PE + quarterly + support/resistance):
{pick_blocks}

HEADLINES:
{headlines}

Write structured report with these EXACT sections:

1. MARKET VERDICT (2-3 lines)
2. STRONG SECTORS TODAY (bullet list)
3. TOP 3 STOCK PICKS — for each: Why buy, PE/earnings view, support/resistance, 3% target logic
4. RISKS (bullet list — market, sector, stock-specific)
5. DECISION CHECKLIST (numbered yes/no items trader should verify before buying)
6. FINAL RECOMMENDATION — best 1 stock for today or "No buy — wait"

End: "Not SEBI-registered advice. Trade at your own risk."
"""

    text = _ask(prompt, max_tokens=1500)
    return f"[AI Research — Groq {AI_MODEL}]\n{text}" if text else ""


def analyze_buy(pick: dict, benchmark: dict) -> str:
    if not is_ai_enabled():
        return ""
    if not load_ai_keys():
        return ""

    prompt = f"""Analyze this stock for a 3% delivery swing (max 7 days). Use all data below.

MARKET: {benchmark.get('mood')} Nifty 20d {benchmark.get('change_20d', 0):+.1f}%

STOCK DATA:
{_pick_context(pick)}
TA reasons: {', '.join(pick.get('reasons', [])[:4])}

Write:
A) VERDICT: BUY / WATCH / AVOID (one word + 1 line why)
B) FUNDAMENTAL VIEW (PE, earnings trend — 2 lines)
C) TECHNICAL VIEW (RSI, MACD, S/R — 2 lines)
D) ENTRY PLAN: buy zone, target Rs.{pick.get('target', 0):.2f}, stop/average trigger
E) TOP 3 RISKS
F) CHECKLIST: 5 yes/no questions before buying

Max 350 words. Not SEBI advice."""

    text = _ask(prompt, max_tokens=900)
    return f"[AI Research — Groq {AI_MODEL}]\n{text}" if text else ""


def analyze_symbol_deep(pick: dict, benchmark: dict) -> str:
    """Full Groq deep-research report for in-app stock analysis."""
    if not is_ai_enabled():
        return ""
    if not load_ai_keys():
        return ""

    headlines = _format_headlines(pick)
    prompt = f"""You are the research brain for Vedant Swing — an Indian NSE delivery swing app (+3% target, Rs.30k/trade, max 7 days).

Use ONLY the data below (technicals, fundamentals, support/resistance, real RSS news). Cross-check news against price action. Be decisive.

MARKET CONTEXT
- Mood: {benchmark.get('mood')} | Nifty 20d change: {benchmark.get('change_20d', 0):+.1f}%

STOCK RESEARCH PACK
{_pick_context(pick)}
Technical signals: {', '.join(pick.get('reasons', [])[:6])}

Write a structured DEEP RESEARCH REPORT (450-600 words) with these EXACT sections:

1. EXECUTIVE VERDICT — BUY / WATCH / AVOID (bold one-liner + 2 sentences)
2. NEWS & CATALYSTS — what headlines mean for this swing; cite specific headlines
3. FUNDAMENTAL SNAPSHOT — PE, earnings/revenue trend, sector strength ({pick.get('sector_strong')})
4. TECHNICAL SETUP — RSI, trend, EMA stack, support/resistance, vs Nifty
5. TRADE PLAN — entry zone, target Rs.{pick.get('target', 0):.2f}, average trigger, position size note
6. RISKS — 4 bullets (market, sector, news, stock-specific)
7. PRE-BUY CHECKLIST — 6 numbered yes/no items the trader must verify

End with: "Not SEBI-registered advice. Trade at your own risk."

RECENT HEADLINES (reference in section 2):
{headlines}
"""

    text = _ask(prompt, max_tokens=AI_MAX_TOKENS)
    return f"[AI Deep Research — Groq {AI_MODEL}]\n{text}" if text else ""


def analyze_position(signal: dict, symbol: str) -> str:
    if not is_ai_enabled():
        return ""
    if not load_ai_keys():
        return ""

    prompt = f"""Open swing position review for {symbol}.

Signal: {signal['signal']}
LTP Rs.{signal.get('ltp', 0):.2f} | Avg Rs.{signal.get('avg_price', 0):.2f} | P&L {signal.get('pnl_pct', 0):+.2f}%
Reason: {signal.get('reason', '')}

Give: ACTION (Hold/Sell/Average), 2-line rationale, 2 risks, 3-item checklist.
Not SEBI advice."""

    return _ask(prompt, max_tokens=500)