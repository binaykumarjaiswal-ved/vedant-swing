/* Vedant Swing — TradingView Lightweight Charts */

let chartInstance = null;
let candleSeries = null;
let ema21Series = null;
let ema50Series = null;

function destroyChart() {
  if (chartInstance) {
    chartInstance.remove();
    chartInstance = null;
    candleSeries = null;
    ema21Series = null;
    ema50Series = null;
  }
}

async function renderStockChart(symbol) {
  const wrap = document.getElementById("chart-wrap");
  const meta = document.getElementById("chart-meta");
  if (!wrap || !window.LightweightCharts) return;

  destroyChart();
  wrap.innerHTML = "";
  meta.textContent = `Loading ${symbol}…`;

  try {
    const data = await fetch(`/api/chart/${encodeURIComponent(symbol)}`).then((r) => r.json());
    if (!data.ok) {
      meta.textContent = data.error || "Chart unavailable";
      return;
    }

    chartInstance = LightweightCharts.createChart(wrap, {
      width: wrap.clientWidth,
      height: 280,
      layout: { background: { color: "#0b1220" }, textColor: "#8b9cb8" },
      grid: { vertLines: { color: "#243049" }, horzLines: { color: "#243049" } },
      timeScale: { borderColor: "#243049" },
      rightPriceScale: { borderColor: "#243049" },
    });

    candleSeries = chartInstance.addCandlestickSeries({
      upColor: "#22c55e",
      downColor: "#ef4444",
      borderVisible: false,
      wickUpColor: "#22c55e",
      wickDownColor: "#ef4444",
    });
    candleSeries.setData(data.candles);

    ema21Series = chartInstance.addLineSeries({ color: "#3b82f6", lineWidth: 2, title: "EMA21" });
    ema21Series.setData(data.ema21 || []);

    ema50Series = chartInstance.addLineSeries({ color: "#f59e0b", lineWidth: 2, title: "EMA50" });
    ema50Series.setData(data.ema50 || []);

    chartInstance.timeScale().fitContent();
    meta.textContent = `${symbol} · ${data.period_days} days · Last Rs.${data.last_price}`;
  } catch (e) {
    meta.textContent = "Chart load failed";
  }
}

window.renderStockChart = renderStockChart;
window.destroyChart = destroyChart;