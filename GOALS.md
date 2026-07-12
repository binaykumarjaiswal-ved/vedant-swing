# Vedant Swing — Goals (Recommend-Only)

**Canonical product:** this repo only (`vedant-swing`).  
**Mode:** automatic **stock BUY recommendations** — **no broker auto-trade**.  
**Market:** NSE India, Nifty 500 universe.  
**Horizon:** delivery swing, roughly 3–7 trading days.

## Definition of success

After **30–40 paper trades** (or 6+ weeks of logged predictions):

| Metric | Target |
|--------|--------|
| Win rate (hit target or positive exit) | ≥ 55% |
| Average expectancy (R multiples) | > 0 |
| Max paper drawdown from peak | ≤ 12% |
| Score audit | Higher score buckets beat lower ones on avg 7d return |

If metrics fail after enough samples → **recalibrate weights / pause new BUYs**, do not add more features blindly.

## What the system does

1. **Scan** Nifty 500 with technical + sector + light fundamental + capped news weight  
2. **Regime gate** — reduce or block new BUYs in bearish markets  
3. **Risk** — ATR-based stop/target, risk-based size, max **1** optional average (not 5×)  
4. **Recommend** Top 1–3 BUY with entry / stop / target / qty / confidence  
5. **Log** every prediction to SQLite for model audit  
6. **Paper trade** high-confidence picks automatically (virtual cash only)  
7. **AI (Groq)** explains picks — does **not** place orders and is not the sole decision

## Explicitly out of scope

- Angel One / any broker order placement  
- Crypto / US stocks / options as primary  
- Parallel bot copies (Stock Analyst, Kimi workspace) — reference only  

## Daily routine (MORNING ONLY)

| Time (IST) | Action |
|------------|--------|
| ~8:30–10:30 | Morning research + BUY recommendation |
| Market hours | Position check: SELL / HOLD / optional 1× AVERAGE / hard STOP |

Evening scan has been **removed permanently**.

## Config flags (see `config.json`)

- `broker_integration`: always `false`  
- `auto_paper_trade`: paper-only auto buy when confidence high  
- `max_averages`: 1  
- `hard_stop_enabled`: true  
- `regime_filter_enabled`: true  

