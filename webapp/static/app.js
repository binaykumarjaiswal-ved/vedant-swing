const $ = (id) => document.getElementById(id);

let lastResult = null;
let eveningData = null;
let eveningFilter = "all";
let scanPollTimer = null;

const QUICK = ["TITAN", "RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"];
const STRATEGY_LABELS = { pullback_21ema: "Pullback 21 EMA", breakout: "Breakout", oversold_bounce: "Oversold Bounce" };

function toast(msg, type = "info") {
  const el = $("toast");
  el.textContent = msg;
  el.className = "toast";
  if (type === "success") el.classList.add("toast-success");
  if (type === "error") el.classList.add("toast-error");
  el.classList.remove("hidden");
  clearTimeout(toast._timer);
  toast._timer = setTimeout(() => el.classList.add("hidden"), 3200);
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

function bindPickClicks(root) {
  root.querySelectorAll("[data-symbol]").forEach((el) => {
    el.addEventListener("click", () => {
      $("symbol-input").value = el.dataset.symbol;
      switchTab("home");
      runAnalyze(el.dataset.symbol);
    });
  });
}

function renderMarket(benchmark) {
  const pill = $("market-pill");
  const mood = (benchmark?.mood || "NEUTRAL").toLowerCase();
  pill.className = "market-pill " + mood;
  pill.textContent = `Nifty ${benchmark?.mood || "NEUTRAL"} · 20d ${benchmark?.change_20d >= 0 ? "+" : ""}${benchmark?.change_20d ?? 0}%`;
}

function renderHeaderStats(data) {
  $("header-stats").textContent =
    `Watchlist ${data.watchlist_count ?? 0} · Alerts ${data.active_alerts ?? 0} · ${data.updated || ""}`;
}

function renderResult(data) {
  lastResult = data;
  $("result-card").classList.remove("hidden");
  $("chart-card").classList.remove("hidden");
  $("res-symbol").textContent = data.symbol;
  $("res-index").textContent = data.index_group || "";
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
  $("res-ema21").textContent = data.ema21 ?? "—";
  $("res-ema50").textContent = data.ema50 ?? "—";
  const reasons = data.reasons || [];
  $("res-reasons").innerHTML = reasons.length ? "<strong>Signals</strong><ul>" + reasons.map((r) => `<li>${r}</li>`).join("") + "</ul>" : "";
  if (window.renderStockChart) window.renderStockChart(data.symbol);
}

async function runAnalyze(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) return toast("Enter symbol");
  $("loading").classList.remove("hidden");
  $("result-card").classList.add("hidden");
  $("btn-analyze").disabled = true;
  try {
    const data = await fetch(`/api/analyze/${encodeURIComponent(symbol)}?ai=0`).then((r) => r.json());
    if (!data.ok) return toast(data.error || "Failed");
    renderResult(data);
  } catch (e) {
    toast("Network error");
  } finally {
    $("loading").classList.add("hidden");
    $("btn-analyze").disabled = false;
  }
}

function paintEveningList() {
  const list = $("evening-scan-list");
  if (!eveningData?.ok) return;
  let rows = eveningFilter === "all" ? (eveningData.top || []).slice(0, 12) : (eveningData.by_strategy?.[eveningFilter] || []).slice(0, 15);
  if (!rows.length) {
    list.innerHTML = '<p class="muted">No setups.</p>';
    return;
  }
  list.innerHTML = rows.map((p) => `
    <div class="pick-row" data-symbol="${p.symbol}">
      <div class="pick-mid"><strong>${p.symbol}</strong><span>${strategyLabel(p.strategy)} · ${p.swing_score}/100</span></div>
      <span class="signal-badge ${signalClass(p.signal)}">${p.signal}</span>
    </div>`).join("");
  bindPickClicks(list);
}

function renderEveningScan(payload) {
  eveningData = payload;
  const meta = $("evening-scan-meta");
  const chips = $("strategy-chips");
  if (!payload?.ok || !payload.top?.length) {
    meta.textContent = "Evening scan pending — auto 3:45 PM IST or Run now";
    chips.innerHTML = "";
    $("evening-scan-list").innerHTML = '<p class="muted">No setups yet.</p>';
    return;
  }
  meta.textContent = `${payload.date} · ${payload.hits} setups / ${payload.scanned} stocks`;
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

async function loadWatchlist() {
  const data = await fetch("/api/watchlists/default").then((r) => r.json());
  const body = $("watchlist-body");
  if (!data.ok || !data.symbols?.length) {
    body.innerHTML = '<p class="muted">Watchlist empty — add from analysis or above.</p>';
    return;
  }
  body.innerHTML = data.symbols.map((s) => `
    <div class="pick-row" data-symbol="${s}">
      <div class="pick-mid"><strong>${s}</strong><span>${data.notes?.[s] || "Tap to analyze"}</span></div>
      <button type="button" class="btn btn-danger btn-sm" data-rm-watch="${s}">Remove</button>
    </div>`).join("");
  bindPickClicks(body);
  body.querySelectorAll("[data-rm-watch]").forEach((btn) => {
    btn.addEventListener("click", async (e) => {
      e.stopPropagation();
      await fetch("/api/watchlists/default/remove", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: btn.dataset.rmWatch }) });
      loadWatchlist();
      loadDashboard();
    });
  });
}

async function loadPaper() {
  const data = await fetch("/api/paper").then((r) => r.json());
  $("paper-cash").textContent = fmtRs(data.cash);
  $("paper-count").textContent = String((data.positions || []).length);
  const pos = $("paper-positions");
  if (!data.positions?.length) pos.innerHTML = '<p class="muted">No paper positions.</p>';
  else {
    pos.innerHTML = data.positions.map((p) => `
      <div class="pick-row">
        <div class="pick-mid"><strong>${p.symbol}</strong><span>${p.qty} @ ${fmtRs(p.entry)}</span></div>
        <button type="button" class="btn btn-danger btn-sm" data-sell-paper="${p.id}">Sell</button>
      </div>`).join("");
    pos.querySelectorAll("[data-sell-paper]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const price = prompt("Exit price?");
        if (!price) return;
        const res = await fetch("/api/paper/sell", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ id: btn.dataset.sellPaper, price: parseFloat(price) }) }).then((r) => r.json());
        toast(res.ok ? `P&L ${fmtRs(res.pnl)}` : res.error);
        loadPaper();
      });
    });
  }
  $("paper-closed").innerHTML = (data.closed || []).slice(0, 5).map((c) => `${c.symbol} ${fmtRs(c.pnl)}`).join("<br>") || "";
}

async function loadJournal() {
  const data = await fetch("/api/journal").then((r) => r.json());
  const list = $("journal-list");
  if (!data.entries?.length) return list.innerHTML = '<p class="muted">No entries.</p>';
  list.innerHTML = data.entries.map((e) => `
    <div class="journal-item ${e.status}">
      <div class="journal-top"><strong>${e.symbol}</strong><span>${e.status}</span></div>
      <div class="journal-meta">
        <div><span>Entry</span>${fmtRs(e.entry)}</div>
        <div><span>Stop</span>${fmtRs(e.stop)}</div>
        <div><span>Target</span>${fmtRs(e.target)}</div>
      </div>
      <p class="muted small">R:R ${e.rr}:1 · ${e.date}</p>
      ${e.status === "open" ? `<button class="btn btn-ghost btn-sm" data-close-j="${e.id}">Close</button>` : ""}
    </div>`).join("");
  list.querySelectorAll("[data-close-j]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const exit = prompt("Exit price?");
      if (!exit) return;
      const res = await fetch(`/api/journal/${btn.dataset.closeJ}/close`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ exit: parseFloat(exit) }) }).then((r) => r.json());
      toast(res.ok ? `Closed ${res.entry.pnl_pct}%` : res.error);
      loadJournal();
    });
  });
}

async function loadAlerts() {
  const [alerts, log] = await Promise.all([
    fetch("/api/alerts").then((r) => r.json()),
    fetch("/api/alert-log").then((r) => r.json()),
  ]);
  const list = $("alerts-list");
  const rows = (alerts.alerts || []).filter((a) => a.status === "active");
  if (!rows.length) list.innerHTML = '<p class="muted">No active alerts.</p>';
  else {
    list.innerHTML = rows.map((a) => `
      <div class="journal-item open">
        <div class="journal-top"><strong>${a.symbol}</strong><button class="btn btn-danger btn-sm" data-del-alert="${a.id}">Delete</button></div>
        <p class="muted small">${a.condition} Rs.${a.price} · ${a.note || ""}</p>
      </div>`).join("");
    list.querySelectorAll("[data-del-alert]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/alerts/${btn.dataset.delAlert}`, { method: "DELETE" });
        loadAlerts();
        loadDashboard();
      });
    });
  }
  $("alert-log").innerHTML = (log.events || []).slice(0, 8).map((e) => `${e.time?.slice(0, 16)} — ${e.message}`).join("<br>") || "No triggers yet";
}

async function loadDashboard() {
  try {
    const [dash, eve] = await Promise.all([fetch("/api/dashboard"), fetch("/api/evening-scan/latest")]);
    const data = await dash.json();
    const evening = await eve.json();
    renderMarket(data.benchmark);
    renderHeaderStats(data);
    renderEveningScan(evening);
    await Promise.all([loadWatchlist(), loadPaper(), loadJournal(), loadAlerts()]);
  } catch (e) {
    toast("Load failed");
  }
}

function paperBuyPayload(symbol, price, qty, stop, target) {
  return {
    symbol: (symbol || "").trim().toUpperCase(),
    qty: Math.max(1, parseInt(qty, 10) || 1),
    price: parseFloat(price) || 0,
    stop: parseFloat(stop) || 0,
    target: parseFloat(target) || 0,
  };
}

async function executePaperBuy(body, opts = {}) {
  const sym = body.symbol;
  if (!sym) {
    toast("Enter a stock symbol", "error");
    return { ok: false };
  }
  if (!body.price || body.price <= 0) {
    toast("Enter a valid entry price", "error");
    return { ok: false };
  }
  if (!body.qty || body.qty <= 0) {
    toast("Quantity must be at least 1", "error");
    return { ok: false };
  }

  const portfolio = await fetch("/api/paper").then((r) => r.json()).catch(() => ({}));
  if ((portfolio.positions || []).some((p) => p.symbol === sym)) {
    toast(`Already holding ${sym}. Sell first.`, "error");
    return { ok: false, error: "duplicate" };
  }

  const btn = opts.button;
  if (btn) btn.disabled = true;
  try {
    const res = await fetch("/api/paper/buy", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }).then((r) => r.json());
    if (res.ok) {
      toast(`Bought ${body.qty} ${sym} @ ${fmtRs(body.price)}`, "success");
      if (opts.form) opts.form.reset();
      await loadPaper();
      loadDashboard();
    } else {
      toast(res.error || "Paper buy failed", "error");
    }
    return res;
  } catch (e) {
    toast("Network error — try again", "error");
    return { ok: false };
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function quickPaperBuyFromResult() {
  if (!lastResult) return toast("Analyze a stock first", "error");
  const p = lastResult.price || 0;
  const stop = lastResult.avg_trigger || Math.round(p * 0.97 * 100) / 100;
  const target = lastResult.target || Math.round(p * 1.03 * 100) / 100;
  const body = paperBuyPayload(lastResult.symbol, p, lastResult.buy_qty || 10, stop, target);
  const res = await executePaperBuy(body, { button: $("btn-paper-from-result") });
  if (res.ok) switchTab("paper");
}

function fillFromResult(mode) {
  if (!lastResult) return toast("Analyze first", "error");
  const p = lastResult.price || 0;
  const stop = lastResult.avg_trigger || Math.round(p * 0.97 * 100) / 100;
  const target = lastResult.target || Math.round(p * 1.03 * 100) / 100;
  if (mode === "paper") {
    $("paper-symbol").value = lastResult.symbol;
    $("paper-price").value = p;
    $("paper-stop").value = stop;
    $("paper-target").value = target;
    $("paper-qty").value = lastResult.buy_qty || 10;
    switchTab("paper");
    toast(`${lastResult.symbol} ready — tap Place buy`, "success");
  } else {
    $("j-symbol").value = lastResult.symbol;
    $("j-entry").value = p;
    $("j-stop").value = stop;
    $("j-target").value = target;
    switchTab("journal");
  }
}

function updateRrPreview() {
  const entry = parseFloat($("j-entry").value);
  const stop = parseFloat($("j-stop").value);
  const target = parseFloat($("j-target").value);
  if (!entry || !stop || !target || entry <= stop) {
    $("j-rr-preview").textContent = "Enter entry, stop, target";
    return;
  }
  $("j-rr-preview").textContent = `R:R ${((target - entry) / (entry - stop)).toFixed(2)}:1`;
}

$("search-form").addEventListener("submit", (e) => { e.preventDefault(); runAnalyze($("symbol-input").value); });
$("btn-refresh").addEventListener("click", loadDashboard);
$("btn-run-evening").addEventListener("click", async () => {
  $("btn-run-evening").disabled = true;
  toast("Scan running…");
  try {
    const d = await fetch("/api/evening-scan").then((r) => r.json());
    renderEveningScan({ ok: true, date: new Date().toISOString().slice(0, 10), ...d });
    toast(`${d.hits || 0} setups`);
  } finally { $("btn-run-evening").disabled = false; }
});
$("btn-paper-from-result").addEventListener("click", quickPaperBuyFromResult);
$("btn-journal-from-result").addEventListener("click", () => fillFromResult("journal"));
$("btn-add-watch").addEventListener("click", async () => {
  if (!lastResult) return toast("Analyze first");
  const res = await fetch("/api/watchlists/default/add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: lastResult.symbol }) }).then((r) => r.json());
  toast(res.ok ? `${lastResult.symbol} added` : res.error);
  loadWatchlist();
  loadDashboard();
});
$("btn-add-alert").addEventListener("click", () => {
  if (!lastResult) return toast("Analyze first");
  $("a-symbol").value = lastResult.symbol;
  $("a-price").value = lastResult.target || lastResult.price;
  $("a-condition").value = "above";
  switchTab("alerts");
});
$("tab-nav").addEventListener("click", (e) => { const t = e.target.closest(".tab"); if (t) switchTab(t.dataset.tab); });
$("watch-add-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const sym = $("watch-symbol").value.trim().toUpperCase();
  const res = await fetch("/api/watchlists/default/add", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ symbol: sym }) }).then((r) => r.json());
  toast(res.ok ? "Added" : res.error);
  if (res.ok) { e.target.reset(); loadWatchlist(); loadDashboard(); }
});
$("paper-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = paperBuyPayload(
    $("paper-symbol").value,
    $("paper-price").value,
    $("paper-qty").value,
    $("paper-stop").value,
    $("paper-target").value,
  );
  await executePaperBuy(body, { form: e.target, button: e.target.querySelector("button[type=submit]") });
});
$("journal-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { symbol: $("j-symbol").value, entry: +$("j-entry").value, stop: +$("j-stop").value, target: +$("j-target").value, qty: +$("j-qty").value || 0, strategy: $("j-strategy").value };
  const res = await fetch("/api/journal", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
  toast(res.ok ? `Saved R:R ${res.entry.rr}` : res.error);
  if (res.ok) { e.target.reset(); loadJournal(); }
});
$("alert-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = { symbol: $("a-symbol").value, condition: $("a-condition").value, price: +$("a-price").value, note: $("a-note").value };
  const res = await fetch("/api/alerts", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
  toast(res.ok ? "Alert created" : res.error);
  if (res.ok) { e.target.reset(); loadAlerts(); loadDashboard(); }
});
$("btn-check-alerts").addEventListener("click", async () => {
  const res = await fetch("/api/alerts/check").then((r) => r.json());
  toast(res.triggered ? `${res.triggered} alert(s) fired` : "No triggers");
  loadAlerts();
});
["j-entry", "j-stop", "j-target"].forEach((id) => $(id).addEventListener("input", updateRrPreview));

$("quick-chips").innerHTML = QUICK.map((s) => `<button type="button" class="chip" data-sym="${s}">${s}</button>`).join("");
document.querySelectorAll(".chip").forEach((c) => c.addEventListener("click", () => { $("symbol-input").value = c.dataset.sym; runAnalyze(c.dataset.sym); }));

loadDashboard();