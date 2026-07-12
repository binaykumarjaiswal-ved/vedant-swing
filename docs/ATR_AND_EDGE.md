# ATR logic & edge framework (Vedant Swing)

## What is ATR?

**ATR = Average True Range** (usually 14 days).

True Range each day is the greatest of:

1. High − Low  
2. |High − previous close|  
3. |Low − previous close|

ATR is the average of True Range. It measures **how much the stock typically moves**, not direction.

| Stock type | ATR idea |
|------------|----------|
| Quiet large-cap | Small ATR % → tighter stop/target |
| Volatile mid-cap | Large ATR % → wider stop/target |

Fixed +3% / −3% on every stock is wrong: a 1%/day stock and a 3%/day stock need different levels.

## How we use ATR

| Level | Formula (default) | Purpose |
|-------|-------------------|---------|
| **Stop** | Entry − **1.1 × ATR** | Room for normal noise; cut if thesis fails |
| **Target** | Entry + **1.8 × ATR** | Take profit at realistic swing |
| **R:R** | Target distance / Stop distance | Aim **≥ 1.4** (often ~1.6) |
| **Position size** | Risk 1% of capital / stop distance | Same rupee risk across stocks |

Clamps keep levels sane (e.g. stop ~1.8–5.5%, target ~2–5.5%).

Optional **structure stop**: recent swing low if it sits in a sensible band.

## Why this helps win rate *and* expectancy

- **Win rate** alone is not enough. 55% wins with 1:2 loss size still loses money.  
- We filter for **quality + R:R**: fewer trades, better average win vs loss.  
- **ADX / chop filter** avoids sideways markets (low win rate for trend swings).  
- **Pullback + volume + RS** prefer entries with room and demand.

## Extra indicators now in the score

| Indicator | Role |
|-----------|------|
| **EMA 9/21/50 stack** | Trend alignment |
| **ADX + DI** | Trend strength / avoid chop |
| **RSI 14** | Not overbought for new longs |
| **MACD + histogram slope** | Momentum confirmation |
| **Stochastic** | Timing (turn from oversold) |
| **Bollinger %B** | Value entry vs extension |
| **Volume ratio + 5d/20d vol** | Participation |
| **vs Nifty 20d** | Relative strength |
| **Higher-low structure** | Demand holding |
| **ATR %** | Volatility regime |
| **Quality flags count** | Need multi-confirm before BUY |

## Gates before a BUY recommendation

1. Signal BUY / STRONG BUY  
2. Score ≥ `min_buy_score` (default 68)  
3. Confidence ≥ `min_confidence` (default 70)  
4. **Quality flags ≥ 3**  
5. **Reward:risk ≥ ~1.4**  
6. Market regime not blocking  

## Honest limits

No indicator guarantees profit. Edge is measured by **model audit** (predictions vs outcomes).  
After 30–40 paper trades, if win rate / expectancy fail → recalibrate weights, don’t add random indicators.
