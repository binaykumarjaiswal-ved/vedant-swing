const $ = (id) => document.getElementById(id);

let lastShareText = "";
let lastResult = null;
let scanPollTimer = null;
let eveningData = null;
let eveningFilter = "all";

const QUICK = ["TITAN", "RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"];

const STRATEGY_LABELS = {
  pullback_21ema: "Pullback 21 EMA",
  breakout: "Breakout",
  oversold_bounce: "Oversold Bounce",
};

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

function strategyLabel(key) {
  return STRATEGY_LABELS[key] || (key || "").replace(/_/g, " ");
}

function switchTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("active", p.id === `panel-${name}`));
}

function renderScanBanner(scan) {
  const el = $("scan-banner");
  if (!scan) {
    el.classList.add("hidden");
    return;
  }
  el.classList.remove("hidden", "ready", "error");
  if (scan.scan_running) {
    el.textContent = "Cloud scan running… page will refresh.";
    startScanPoll();
    return;
  }
  if (scan.today_ready || scan.has_report) {
    el.classList.add("ready");
    el.textContent = "Today's research report is ready.";
    stopScanPoll();
    return;
  }
  if (scan.scan_message) el.textContent = scan.scan_message;
  else el.classList.add("hidden");
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
    body.innerHTML = '<p class="muted">No tracked position. Use Paper tab for practice trades.</p>';
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
      <div class="stat"><span class="stat-label">Qty</span><span class="stat-val">${pos.qty}</span></div>
    </div>`;
  actions.classList.remove("hidden");
}

function renderPicks(picks, date) {
  const list = $("picks-list");
  $("picks-date").textContent = date ? `From scan: ${date}` : "No morning scan yet";
  if (!picks?.length) {
    list.innerHTML = '<p class="muted">Search a stock or wait for evening scan.</p>';
    return;
  }
  list.innerHTML = picks.map((p) => `
    <div class="pick-item" data-symbol="${p.symbol}">
      <div class="pick-left"><strong>${p.symbol}</strong><span>${p.index_group} · ${p.signal}</span></div>
      <div class="pick-right"><div class="pick-score">${p.score}/100</div><div>${fmtRs(p.price)}</div></div>
    </div>`).join("");
  bindPickClicks(list);
}

function bindPickClicks(root) {
  root.querySelectorAll("[data-symbol]").forEach((el) => {
    el.addEventListener("click", () => {
      $("symbol-input").value = el.dataset.symbol;
      switchTab("home");
      runAnalyze(el.dataset.symbol);
    });
  });
}

function renderEveningScan(payload) {
  eveningData = payload;
  const list = $("evening-scan-list");
  const meta = $("evening-scan-meta");
  const chips = $("strategy-chips");

  if (!payload?.ok || !payload.top?.length) {
    meta.textContent = "Evening scan not ready — auto at 3:45 PM IST or tap Run now.";
    chips.innerHTML = "";
    list.innerHTML = '<p class="muted">No setups saved yet.</p>';
    return;
  }

  meta.textContent = `${payload.date || ""} · ${payload.hits || 0} setups · ${payload.scanned || 0} stocks scanned`;
  const strategies = Object.keys(payload.by_strategy || {});
  chips.innerHTML = `<button type="button" class="strategy-chip active" data-strategy="all">All</button>` +
    strategies.map((s) => `<button type="button" class="strategy-chip" data-strategy="${s}">${strategyLabel(s)}</button>`).join("");

  chips.querySelectorAll(".strategy-chip").forEach((c) => {
    c.addEventListener("click", () => {
      eveningFilter = c.dataset.strategy;
      chips.querySelectorAll(".strategy-chip").forEach((x) => x.classList.toggle("active", x === c));
      paintEveningList();
    });
  });

  paintEveningList();
}

function paintEveningList() {
  const list = $("evening-scan-list");
  if (!eveningData?.ok) return;
  let rows = eveningData.top || [];
  if (eveningFilter !== "all") {
    rows = (eveningData.by_strategy?.[eveningFilter] || []).slice(0, 15);
  } else {
    rows = rows.slice(0, 12);
  }
  if (!rows.length) {
    list.innerHTML = '<p class="muted">No setups for this strategy.</p>';
    return;
  }
  list.innerHTML = rows.map((p) => `
    <div class="pick-row" data-symbol="${p.symbol}">
      <div class="pick-mid">
        <strong>${p.symbol}</strong>
        <span>${strategyLabel(p.strategy)} · ${p.index_group || "Nifty 500"} · RSI ${p.rsi ?? "—"}</span>
      </div>
      <span class="signal-badge ${signalClass(p.signal)}">${p.signal}</span>
      <span class="pick-score">${p.swing_score}/100</span>
    </div>`).join("");
  bindPickClicks(list);
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
    sectorEl.textContent = data.sector;
    sectorEl.className = "sector-tag " + (data.sector_strong !== false ? "strong" : "weak");
  } else sectorEl.classList.add("hidden");

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
  $("res-vs-nifty").textContent = data.vs_nifty_20d != null ? `${data.vs_nifty_20d >= 0 ? "+" : ""}${data.vs_nifty_20d}%` : "—";
  $("res-qty").textContent = data.buy_qty ? `${data.buy_qty} @ ${fmtRs(data.buy_amount)}` : "—";

  const reasons = data.reasons || [];
  $("res-reasons").innerHTML = reasons.length ? "<strong>Technical</strong><ul>" + reasons.map((r) => `<li>${r}</li>`).join("") + "</ul>" : "";
  $("res-fund").classList.add("hidden");
  $("res-levels").classList.add("hidden");
  $("res-news").classList.add("hidden");
  $("res-ai").classList.add("hidden");
  card.scrollIntoView({ behavior: "smooth", block: "start" });
}

function fillFromResult(target) {
  if (!lastResult) {
    toast("Analyze a stock first");
    return false;
  }
  const price = lastResult.price || 0;
  const stop = lastResult.avg_trigger || Math.round(price * 0.97 * 100) / 100;
  const targetPx = lastResult.target || Math.round(price * 1.03 * 100) / 100;
  if (target === "paper") {
    $("paper-symbol").value = lastResult.symbol;
    $("paper-price").value = price;
    $("paper-stop").value = stop;
    $("paper-target").value = targetPx;
    $("paper-qty").value = lastResult.buy_qty || 10;
    switchTab("paper");
    return true;
  }
  $("j-symbol").value = lastResult.symbol;
  $("j-entry").value = price;
  $("j-stop").value = stop;
  $("j-target").value = targetPx;
  $("j-qty").value = lastResult.buy_qty || "";
  updateRrPreview();
  switchTab("journal");
  return true;
}

function updateRrPreview() {
  const entry = parseFloat($("j-entry").value);
  const stop = parseFloat($("j-stop").value);
  const target = parseFloat($("j-target").value);
  if (!entry || !stop || !target || entry <= stop) {
    $("j-rr-preview").textContent = "Enter entry, stop, and target for R:R";
    return;
  }
  const rr = ((target - entry) / (entry - stop)).toFixed(2);
  $("j-rr-preview").textContent = `Risk/Reward: ${rr}:1 ${rr >= 2 ? "✓ Good" : "— aim for 2:1+"}`;
}

async function loadPaper() {
  try {
    const data = await fetch("/api/paper").then((r) => r.json());
    $("paper-cash").textContent = fmtRs(data.cash);
    $("paper-count").textContent = String((data.positions || []).length);
    const pos = $("paper-positions");
    if (!data.positions?.length) {
      pos.innerHTML = '<p class="muted">No open paper positions.</p>';
    } else {
      pos.innerHTML = data.positions.map((p) => `
        <div class="pick-row" data-paper-id="${p.id}">
          <div class="pick-mid"><strong>${p.symbol}</strong><span>${p.qty} @ ${fmtRs(p.entry)} · Stop ${fmtRs(p.stop)}</span></div>
          <button type="button" class="btn btn-danger btn-sm" data-sell-paper="${p.id}">Sell</button>
        </div>`).join("");
      pos.querySelectorAll("[data-sell-paper]").forEach((btn) => {
        btn.addEventListener("click", async (e) => {
          e.stopPropagation();
          const price = prompt("Exit price?");
          if (!price) return;
          const res = await fetch("/api/paper/sell", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ id: btn.dataset.sellPaper, price: parseFloat(price) }),
          }).then((r) => r.json());
          toast(res.ok ? `Closed · P&L ${fmtRs(res.pnl)}` : (res.error || "Failed"));
          loadPaper();
        });
      });
    }
    const closed = data.closed || [];
    $("paper-closed").innerHTML = closed.length
      ? "<strong>Recent closed</strong><br>" + closed.slice(0, 5).map((c) =>
          `${c.symbol} ${c.qty}@${c.entry} → ${c.exit} · ${fmtRs(c.pnl)}`).join("<br>")
      : "";
  } catch (e) {
    toast("Could not load paper portfolio");
  }
}

async function loadJournal() {
  try {
    const data = await fetch("/api/journal").then((r) => r.json());
    const list = $("journal-list");
    const entries = data.entries || [];
    if (!entries.length) {
      list.innerHTML = '<p class="muted">No journal entries yet.</p>';
      return;
    }
    list.innerHTML = entries.map((e) => `
      <div class="journal-item ${e.status}">
        <div class="journal-top">
          <strong>${e.symbol}</strong>
          <span class="signal-badge ${e.status === "open" ? "buy" : "watch"}">${e.status.toUpperCase()}</span>
        </div>
        <div class="journal-meta">
          <div><span>Entry</span>${fmtRs(e.entry)}</div>
          <div><span>Stop</span>${fmtRs(e.stop)}</div>
          <div><span>Target</span>${fmtRs(e.target)}</div>
        </div>
        <p class="muted small">${strategyLabel(e.strategy)} · R:R ${e.rr}:1 · ${e.date}${e.pnl_pct != null ? ` · ${e.pnl_pct}%` : ""}</p>
        ${e.status === "open" ? `<button type="button" class="btn btn-ghost btn-sm" data-close-journal="${e.id}" style="margin-top:0.5rem">Close trade</button>` : ""}
      </div>`).join("");
    list.querySelectorAll("[data-close-journal]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const exit = prompt("Exit price?");
        if (!exit) return;
        const res = await fetch(`/api/journal/${btn.dataset.closeJournal}/close`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ exit: parseFloat(exit) }),
        }).then((r) => r.json());
        toast(res.ok ? `Closed · ${res.entry.pnl_pct}%` : (res.error || "Failed"));
        loadJournal();
      });
    });
  } catch (e) {
    toast("Could not load journal");
  }
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
    await Promise.all([loadPaper(), loadJournal()]);
  } catch (e) {
    toast("Could not load dashboard");
  }
}

async function runAnalyze(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) return toast("Enter a stock symbol");
  $("loading").classList.remove("hidden");
  $("result-card").classList.add("hidden");
  $("btn-analyze").disabled = true;
  try {
    const res = await fetch(`/api/analyze/${encodeURIComponent(symbol)}?ai=0`);
    const data = await res.json();
    if (!data.ok) return toast(data.error || "Analysis failed");
    renderResult(data);
  } catch (e) {
    toast("Network error — cloud may be waking up");
  } finally {
    $("loading").classList.add("hidden");
    $("btn-analyze").disabled = false;
  }
}

async function runEveningScan() {
  $("btn-run-evening").disabled = true;
  $("evening-scan-meta").textContent = "Running Nifty 500 evening scan on server…";
  toast("Scan started — may take several minutes");
  try {
    const data = await fetch("/api/evening-scan").then((r) => r.json());
    if (data.ok) {
      renderEveningScan({ ok: true, date: new Date().toISOString().slice(0, 10), ...data });
      toast(`${data.hits || 0} setups found`);
    } else {
      toast(data.error || "Scan failed");
    }
  } catch (e) {
    toast("Scan request failed");
  } finally {
    $("btn-run-evening").disabled = false;
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

$("search-form").addEventListener("submit", (e) => { e.preventDefault(); runAnalyze($("symbol-input").value); });
$("btn-share").addEventListener("click", async () => {
  if (!lastShareText) return toast("Run analysis first");
  if (navigator.share) {
    try { await navigator.share({ title: "Vedant Swing", text: lastShareText }); return; } catch (e) { if (e.name === "AbortError") return; }
  }
  await navigator.clipboard.writeText(lastShareText);
  toast("Copied");
});
$("btn-copy").addEventListener("click", async () => {
  if (!lastShareText) return toast("Run analysis first");
  await navigator.clipboard.writeText(lastShareText);
  toast("Copied");
});
$("btn-refresh").addEventListener("click", loadDashboard);
$("btn-paper-from-result").addEventListener("click", () => fillFromResult("paper"));
$("btn-journal-from-result").addEventListener("click", () => fillFromResult("journal"));
$("btn-run-evening").addEventListener("click", runEveningScan);

$("tab-nav").addEventListener("click", (e) => {
  const tab = e.target.closest(".tab");
  if (tab) switchTab(tab.dataset.tab);
});

$("paper-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    symbol: $("paper-symbol").value.trim().toUpperCase(),
    qty: parseInt($("paper-qty").value, 10),
    price: parseFloat($("paper-price").value),
    stop: parseFloat($("paper-stop").value) || 0,
    target: parseFloat($("paper-target").value) || 0,
  };
  const res = await fetch("/api/paper/buy", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
  toast(res.ok ? "Paper buy placed" : (res.error || "Failed"));
  if (res.ok) { e.target.reset(); loadPaper(); }
});

$("journal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = {
    symbol: $("j-symbol").value.trim().toUpperCase(),
    entry: parseFloat($("j-entry").value),
    stop: parseFloat($("j-stop").value),
    target: parseFloat($("j-target").value),
    qty: parseInt($("j-qty").value, 10) || 0,
    strategy: $("j-strategy").value.trim(),
    notes: $("j-notes").value.trim(),
  };
  const res = await fetch("/api/journal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
  toast(res.ok ? `Saved · R:R ${res.entry.rr}:1` : (res.error || "Failed"));
  if (res.ok) { e.target.reset(); updateRrPreview(); loadJournal(); }
});

["j-entry", "j-stop", "j-target"].forEach((id) => $(id).addEventListener("input", updateRrPreview));

$("position-actions").addEventListener("click", (e) => {
  const btn = e.target.closest("[data-action]");
  if (!btn) return;
  const action = btn.dataset.action;
  if (action === "sell" && !confirm("Record sell in broker?")) return;
  fetch(`/api/position/${action}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" })
    .then((r) => r.json())
    .then((d) => { toast(d.ok ? "Recorded" : (d.error || "Failed")); if (d.ok) loadDashboard(); });
});

initChips();
loadDashboard();