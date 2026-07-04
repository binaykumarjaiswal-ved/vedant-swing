const $ = (id) => document.getElementById(id);

let lastShareText = "";
let lastResult = null;
let scanPollTimer = null;

const QUICK = ["TITAN", "RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"];

function toast(msg) {
  const el = $("toast");
  el.textContent = msg;
  el.classList.remove("hidden");
  setTimeout(() => el.classList.add("hidden"), 2500);
}

function signalClass(signal) {
  const s = (signal || "").toUpperCase();
  if (s.includes("STRONG")) return "strong-buy";
  if (s === "BUY") return "buy";
  if (s === "WATCH") return "watch";
  return "avoid";
}

function fmtRs(n) {
  if (n == null || isNaN(n)) return "—";
  return "Rs." + Number(n).toLocaleString("en-IN", { maximumFractionDigits: 2 });
}

function renderScanBanner(scan) {
  const el = $("scan-banner");
  if (!scan) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden", "ready", "error");
  if (scan.scan_running || (scan.today_ready === false && scan.scan_message && scan.scan_message.includes("started"))) {
    el.textContent = "Preparing today's Level 2/3 report on cloud… (~8–12 min, 100 stocks). Page will refresh automatically.";
    startScanPoll();
    return;
  }
  if (scan.today_ready || scan.has_report) {
    el.classList.add("ready");
    el.textContent = "Today's research report is ready.";
    stopScanPoll();
    return;
  }
  if (scan.scan_message) {
    el.textContent = scan.scan_message;
  } else {
    el.classList.add("hidden");
  }
}

function startScanPoll() {
  if (scanPollTimer) return;
  scanPollTimer = setInterval(async () => {
    try {
      const s = await fetch("/api/scan-status").then((r) => r.json());
      if (s.today_ready && !s.running) {
        stopScanPoll();
        loadDashboard();
      }
    } catch (e) { /* ignore */ }
  }, 15000);
}

function stopScanPoll() {
  if (scanPollTimer) {
    clearInterval(scanPollTimer);
    scanPollTimer = null;
  }
}

function renderMarket(benchmark) {
  const pill = $("market-pill");
  const mood = (benchmark.mood || "NEUTRAL").toLowerCase();
  pill.className = "market-pill " + mood;
  pill.textContent = `Nifty ${benchmark.mood} · 20d ${benchmark.change_20d >= 0 ? "+" : ""}${benchmark.change_20d}%`;
}

function renderPosition(pos) {
  const body = $("position-body");
  const actions = $("position-actions");

  if (!pos) {
    body.innerHTML = '<p class="muted">No open position. Use your broker app to buy, then record here after cloud signal.</p>';
    actions.classList.add("hidden");
    return;
  }

  const pnlClass = pos.pnl_pct >= 0 ? "up" : "down";
  const sig = (pos.signal || "HOLD").toLowerCase();

  body.innerHTML = `
    <div class="position-hero">
      <span class="position-symbol">${pos.symbol}</span>
      <span class="pnl ${pnlClass}">${pos.pnl_pct >= 0 ? "+" : ""}${pos.pnl_pct}%</span>
    </div>
    <span class="signal-pill ${sig}">${pos.signal}</span>
    <div class="stats-grid">
      <div class="stat"><span class="stat-label">LTP</span><span class="stat-val">${fmtRs(pos.ltp)}</span></div>
      <div class="stat"><span class="stat-label">Avg</span><span class="stat-val">${fmtRs(pos.avg_price)}</span></div>
      <div class="stat"><span class="stat-label">Sell @ +3%</span><span class="stat-val green">${fmtRs(pos.sell_target)}</span></div>
      <div class="stat"><span class="stat-label">Avg trigger</span><span class="stat-val">${fmtRs(pos.avg_trigger)}</span></div>
      <div class="stat"><span class="stat-label">Qty</span><span class="stat-val">${pos.qty}</span></div>
      <div class="stat"><span class="stat-label">Invested</span><span class="stat-val">${fmtRs(pos.invested)}</span></div>
    </div>
    <p class="muted small">${pos.signal_reason || ""}</p>
  `;
  actions.classList.remove("hidden");
}

function renderPicks(picks, date) {
  const list = $("picks-list");
  $("picks-date").textContent = date ? `From scan: ${date}` : "No morning scan yet";

  if (!picks || !picks.length) {
    list.innerHTML = '<p class="muted">Run morning scan or search a stock above.</p>';
    return;
  }

  list.innerHTML = picks.map((p) => {
    const sector = p.sector ? ` · ${p.sector}` : "";
    const pe = p.pe != null ? ` · PE ${p.pe}` : "";
    return `
    <div class="pick-item" data-symbol="${p.symbol}">
      <div class="pick-left">
        <strong>${p.symbol}</strong>
        <span>${p.index_group}${sector} · ${p.signal}${pe}</span>
      </div>
      <div class="pick-right">
        <div class="pick-score">${p.score}/100</div>
        <div>${fmtRs(p.price)}</div>
      </div>
    </div>`;
  }).join("");

  list.querySelectorAll(".pick-item").forEach((el) => {
    el.addEventListener("click", () => {
      $("symbol-input").value = el.dataset.symbol;
      runAnalyze(el.dataset.symbol);
    });
  });
}

function renderResult(data) {
  lastResult = data;
  lastShareText = data.share_text || "";

  const card = $("result-card");
  card.classList.remove("hidden");

  $("res-symbol").textContent = data.symbol;
  $("res-index").textContent = data.index_group || "";
  const sectorEl = $("res-sector");
  if (data.sector) {
    sectorEl.classList.remove("hidden");
    const strong = data.sector_strong !== false;
    sectorEl.textContent = strong ? `${data.sector} · Strong sector` : `${data.sector} · Weak sector`;
    sectorEl.className = "sector-tag " + (strong ? "strong" : "weak");
  } else {
    sectorEl.classList.add("hidden");
  }
  const sigEl = $("res-signal");
  sigEl.textContent = data.signal;
  sigEl.className = "signal-badge " + signalClass(data.signal);

  const score = data.swing_score || 0;
  $("res-score").textContent = score;
  $("res-score-bar").style.width = score + "%";

  $("res-price").textContent = fmtRs(data.price);
  $("res-target").textContent = fmtRs(data.target);
  $("res-rsi").textContent = data.rsi ?? "—";
  $("res-trend").textContent = data.trend ?? "—";
  const vn = data.vs_nifty_20d;
  $("res-vs-nifty").textContent = vn != null ? `${vn >= 0 ? "+" : ""}${vn}%` : "—";
  $("res-qty").textContent = data.buy_qty ? `${data.buy_qty} @ ${fmtRs(data.buy_amount)}` : "—";

  const fundEl = $("res-fund");
  const hasFund = data.pe_trailing || data.fund_verdict || data.eps_growth_pct != null;
  if (hasFund) {
    fundEl.classList.remove("hidden");
    const eps = data.eps_growth_pct != null ? `${data.eps_growth_pct >= 0 ? "+" : ""}${data.eps_growth_pct}%` : "—";
    const rev = data.revenue_growth_pct != null ? `${data.revenue_growth_pct >= 0 ? "+" : ""}${data.revenue_growth_pct}%` : "—";
    fundEl.innerHTML = `<strong>Fundamentals</strong>
      <div class="stats-grid compact">
        <div class="stat"><span class="stat-label">PE</span><span class="stat-val">${data.pe_trailing ?? "—"}</span></div>
        <div class="stat"><span class="stat-label">EPS growth</span><span class="stat-val">${eps}</span></div>
        <div class="stat"><span class="stat-label">Revenue</span><span class="stat-val">${rev}</span></div>
        <div class="stat"><span class="stat-label">Quarter</span><span class="stat-val">${data.quarter_trend ?? "—"}</span></div>
      </div>
      <p class="muted small">${data.fund_verdict || ""}</p>`;
  } else {
    fundEl.classList.add("hidden");
  }

  const levelsEl = $("res-levels");
  if (data.support || data.resistance) {
    levelsEl.classList.remove("hidden");
    levelsEl.innerHTML = `<strong>Support / Resistance</strong>
      <div class="stats-grid compact">
        <div class="stat"><span class="stat-label">Support</span><span class="stat-val green">${fmtRs(data.support)}</span></div>
        <div class="stat"><span class="stat-label">Resistance</span><span class="stat-val">${fmtRs(data.resistance)}</span></div>
        <div class="stat"><span class="stat-label">Pivot S1</span><span class="stat-val">${fmtRs(data.pivot_s1)}</span></div>
        <div class="stat"><span class="stat-label">Pivot R1</span><span class="stat-val">${fmtRs(data.pivot_r1)}</span></div>
      </div>
      <p class="muted small">${data.level_note || ""}</p>`;
  } else {
    levelsEl.classList.add("hidden");
  }

  const reasons = data.reasons || [];
  $("res-reasons").innerHTML = reasons.length
    ? "<strong>Technical</strong><ul>" + reasons.map((r) => `<li>${r}</li>`).join("") + "</ul>"
    : "";

  const newsEl = $("res-news");
  if (data.news_headlines && data.news_headlines.length) {
    newsEl.classList.remove("hidden");
    newsEl.innerHTML = "<strong>News</strong><ul>" +
      data.news_headlines.map((n) => `<li>${n.title}</li>`).join("") + "</ul>";
  } else if (data.news_summary) {
    newsEl.classList.remove("hidden");
    newsEl.innerHTML = `<strong>News</strong><p>${data.news_summary}</p>`;
  } else {
    newsEl.classList.add("hidden");
  }

  const aiEl = $("res-ai");
  if (data.ai_note) {
    aiEl.classList.remove("hidden");
    aiEl.innerHTML = `<strong>Groq AI — Verdict + Risks + Checklist</strong><pre class="ai-text">${data.ai_note}</pre>`;
  } else {
    aiEl.classList.add("hidden");
  }

  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function renderEveningScan(payload) {
  const list = $("evening-scan-list");
  const meta = $("evening-scan-meta");
  if (!payload || !payload.ok || !payload.top?.length) {
    meta.textContent = "Evening scan not ready yet — runs automatically after 3:45 PM IST.";
    list.innerHTML = '<p class="muted">No setups saved yet.</p>';
    return;
  }
  meta.textContent = `${payload.date || ""} · ${payload.hits || 0} setups from ${payload.scanned || 0} stocks`;
  list.innerHTML = payload.top.slice(0, 10).map((p) => `
    <div class="pick-row">
      <div>
        <strong>${p.symbol}</strong>
        <span class="muted small">${p.strategy || ""}</span>
      </div>
      <span class="signal-badge ${signalClass(p.signal)}">${p.signal}</span>
      <span>${p.swing_score}/100</span>
    </div>
  `).join("");
}

async function loadDashboard() {
  try {
    const [dashRes, eveRes] = await Promise.all([
      fetch("/api/dashboard"),
      fetch("/api/evening-scan/latest"),
    ]);
    const data = await dashRes.json();
    const evening = await eveRes.json();
    renderMarket(data.benchmark);
    renderScanBanner({ ...data.scan, has_report: data.has_report });
    renderPosition(data.position);
    renderPicks(data.top_picks, data.report_date);
    renderEveningScan(evening);
    $("report-preview").textContent = data.report_preview || "No morning report saved yet.";
  } catch (e) {
    toast("Could not load dashboard");
  }
}

async function runAnalyze(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) {
    toast("Enter a stock symbol");
    return;
  }

  $("loading").classList.remove("hidden");
  $("result-card").classList.add("hidden");
  $("btn-analyze").disabled = true;

  try {
    const res = await fetch(`/api/analyze/${encodeURIComponent(symbol)}`);
    const data = await res.json();
    if (!data.ok) {
      toast(data.error || "Analysis failed");
      return;
    }
    renderResult(data);
  } catch (e) {
    toast("Network error — retry in a moment (cloud may be waking up)");
  } finally {
    $("loading").classList.add("hidden");
    $("btn-analyze").disabled = false;
  }
}

async function shareResult() {
  if (!lastShareText) {
    toast("Run analysis first");
    return;
  }
  if (navigator.share) {
    try {
      await navigator.share({
        title: `Stock Analyst — ${lastResult?.symbol || ""}`,
        text: lastShareText,
      });
      return;
    } catch (e) {
      if (e.name === "AbortError") return;
    }
  }
  await copyText(lastShareText);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast("Copied to clipboard");
  } catch (e) {
    toast("Copy failed");
  }
}

async function positionAction(action) {
  if (action === "sell" && !confirm("Record that you sold in broker?")) return;
  if (action === "average" && !confirm("Record average down in broker?")) return;

  try {
    const res = await fetch(`/api/position/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" });
    const data = await res.json();
    if (data.ok) {
      toast(action === "sell" ? "Position closed" : "Recorded");
      loadDashboard();
    } else {
      toast(data.error || "Failed");
    }
  } catch (e) {
    toast("Action failed");
  }
}

function initChips() {
  const row = $("quick-chips");
  row.innerHTML = QUICK.map((s) => `<button type="button" class="chip" data-sym="${s}">${s}</button>`).join("");
  row.querySelectorAll(".chip").forEach((c) => {
    c.addEventListener("click", () => {
      $("symbol-input").value = c.dataset.sym;
      runAnalyze(c.dataset.sym);
    });
  });
}

$("search-form").addEventListener("submit", (e) => {
  e.preventDefault();
  runAnalyze($("symbol-input").value);
});

$("btn-share").addEventListener("click", shareResult);
$("btn-copy").addEventListener("click", () => copyText(lastShareText));
$("btn-refresh").addEventListener("click", loadDashboard);

$("position-actions").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (btn) positionAction(btn.dataset.action);
});

initChips();
loadDashboard();