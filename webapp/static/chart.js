/* Vedant Swing — TradingView Lightweight Charts + Google Finance ranges */

let chartInstance = null;
let candleSeries = null;
let volumeSeries = null;
let ema9Series = null;
let ema21Series = null;
let ema50Series = null;
let currentSymbol = null;
let currentRange = "6m";

const CHART_RANGES = ["1d", "5d", "1m", "3m", "6m", "1y", "5y", "max"];

function fmtRs(n) {
  if (n == null || isNaN(n)) return "—";
  return "Rs." + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function fmtVol(n) {
  if (n == null || isNaN(n)) return "—";
  const v = Number(n);
  if (v >= 1e7) return (v / 1e7).toFixed(2) + " Cr";
  if (v >= 1e5) return (v / 1e5).toFixed(2) + " L";
  if (v >= 1e3) return (v / 1e3).toFixed(1) + " K";
  return String(Math.round(v));
}

function destroyChart() {
  if (chartInstance) {
    chartInstance.remove();
    chartInstance = null;
    candleSeries = null;
    volumeSeries = null;
    ema9Series = null;
    ema21Series = null;
    ema50Series = null;
  }
}

function setActiveRangeChip(range) {
  document.querySelectorAll(".range-chip").forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.range === range);
  });
}

function renderChartStats(data) {
  const stats = data.stats || {};
  const title = document.getElementById("chart-symbol-title");
  const meta = document.getElementById("chart-meta");
  const lastEl = document.getElementById("chart-last-price");
  const changeEl = document.getElementById("chart-change");

  if (title) title.textContent = data.symbol || "Price Chart";
  if (meta) {
    meta.textContent = `${data.range_label || data.range} · ${data.interval} candles · ${data.period_days} bars`;
  }
  if (lastEl) lastEl.textContent = fmtRs(stats.close ?? data.last_price);

  const chg = stats.change ?? 0;
  const chgPct = stats.change_pct ?? 0;
  const sign = chg >= 0 ? "+" : "";
  if (changeEl) {
    changeEl.textContent = `${sign}${chg.toFixed(2)} (${sign}${chgPct.toFixed(2)}%)`;
    changeEl.className = "chart-change " + (chg >= 0 ? "up" : "down");
  }

  const set = (id, val) => {
    const el = document.getElementById(id);
    if (el) el.textContent = val;
  };
  set("cs-open", fmtRs(stats.open));
  set("cs-high", fmtRs(stats.high));
  set("cs-low", fmtRs(stats.low));
  set("cs-close", fmtRs(stats.close));
  set("cs-volume", fmtVol(stats.volume));
  const rsiLast = (data.rsi || []).at(-1);
  set("cs-rsi", rsiLast ? rsiLast.value.toFixed(1) : "—");
}

function buildChart(wrap, data) {
  destroyChart();
  wrap.innerHTML = "";

  chartInstance = LightweightCharts.createChart(wrap, {
    width: wrap.clientWidth,
    height: 320,
    layout: { background: { color: "#0b1220" }, textColor: "#8b9cb8" },
    grid: { vertLines: { color: "#243049" }, horzLines: { color: "#243049" } },
    timeScale: { borderColor: "#243049", timeVisible: true, secondsVisible: currentRange === "1d" },
    rightPriceScale: { borderColor: "#243049" },
    crosshair: { mode: LightweightCharts.CrosshairMode.Normal },
  });

  candleSeries = chartInstance.addCandlestickSeries({
    upColor: "#22c55e",
    downColor: "#ef4444",
    borderVisible: false,
    wickUpColor: "#22c55e",
    wickDownColor: "#ef4444",
  });
  candleSeries.setData(data.candles);

  if (data.volume?.length) {
    volumeSeries = chartInstance.addHistogramSeries({
      priceFormat: { type: "volume" },
      priceScaleId: "vol",
    });
    chartInstance.priceScale("vol").applyOptions({
      scaleMargins: { top: 0.82, bottom: 0 },
    });
    volumeSeries.setData(data.volume);
  }

  if (data.ema9?.length) {
    ema9Series = chartInstance.addLineSeries({ color: "#a78bfa", lineWidth: 1, title: "EMA9" });
    ema9Series.setData(data.ema9);
  }
  if (data.ema21?.length) {
    ema21Series = chartInstance.addLineSeries({ color: "#3b82f6", lineWidth: 2, title: "EMA21" });
    ema21Series.setData(data.ema21);
  }
  if (data.ema50?.length) {
    ema50Series = chartInstance.addLineSeries({ color: "#f59e0b", lineWidth: 2, title: "EMA50" });
    ema50Series.setData(data.ema50);
  }

  chartInstance.timeScale().fitContent();
}

async function renderStockChart(symbol, range) {
  const wrap = document.getElementById("chart-wrap");
  const meta = document.getElementById("chart-meta");
  if (!wrap || !window.LightweightCharts) return;

  if (symbol) currentSymbol = symbol.toUpperCase();
  if (range && CHART_RANGES.includes(range)) currentRange = range;
  if (!currentSymbol) return;

  setActiveRangeChip(currentRange);
  if (meta) meta.textContent = `Loading ${currentSymbol} (${currentRange.toUpperCase()})…`;

  try {
    const data = await fetch(
      `/api/chart/${encodeURIComponent(currentSymbol)}?range=${encodeURIComponent(currentRange)}`
    ).then((r) => r.json());

    if (!data.ok) {
      if (meta) meta.textContent = data.error || "Chart unavailable";
      return;
    }

    renderChartStats(data);
    buildChart(wrap, data);
  } catch (e) {
    if (meta) meta.textContent = "Chart load failed";
  }
}

function bindRangeNav() {
  const nav = document.getElementById("chart-range-nav");
  if (!nav || nav.dataset.bound) return;
  nav.dataset.bound = "1";
  nav.addEventListener("click", (e) => {
    const btn = e.target.closest(".range-chip");
    if (!btn || !currentSymbol) return;
    const range = btn.dataset.range;
    if (range === currentRange) return;
    renderStockChart(currentSymbol, range);
  });
}

function bindChartResize() {
  if (window._chartResizeBound) return;
  window._chartResizeBound = true;
  window.addEventListener("resize", () => {
    const wrap = document.getElementById("chart-wrap");
    if (chartInstance && wrap) {
      chartInstance.applyOptions({ width: wrap.clientWidth });
    }
  });
}

bindRangeNav();
bindChartResize();

window.renderStockChart = renderStockChart;
window.destroyChart = destroyChart;
window.getChartRange = () => currentRange;