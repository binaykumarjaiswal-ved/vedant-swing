const $ = (id) => document.getElementById(id);

let lastResult = null;
let scanPollTimer = null;

const QUICK = ["TITAN", "RELIANCE", "TCS", "HDFCBANK", "INFY", "BAJFINANCE"];
const STRATEGY_LABELS = { pullback_21ema: "Pullback 21 EMA", breakout: "Breakout", oversold_bounce: "Oversold Bounce" };
let marketContext = null;
let clockTimer = null;

function fmtIstNow(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    weekday: "short",
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: true,
  }).formatToParts(date);
  const get = (type) => parts.find((p) => p.type === type)?.value || "";
  return `${get("weekday")}, ${get("day")} ${get("month")} ${get("year")}, ${get("hour")}:${get("minute")} ${get("dayPeriod")} IST`;
}

function marketStatusClass(status) {
  const s = (status || "").toLowerCase();
  if (s === "open") return "open";
  if (s === "pre_open") return "pre_open";
  if (s === "holiday") return "holiday";
  return "closed";
}

function marketStatusLabel(status) {
  const map = {
    OPEN: "Market Open",
    CLOSED: "Market Closed",
    PRE_OPEN: "Pre-Market",
    HOLIDAY: "Holiday",
  };
  return map[status] || status || "—";
}

function renderDateTimeBar(ctx) {
  if (ctx) marketContext = ctx;
  const clock = $("live-clock");
  if (clock) clock.textContent = fmtIstNow();
  if (!marketContext) return;
  const pill = $("market-status-pill");
  const hint = $("session-hint");
  if (pill) {
    pill.textContent = marketStatusLabel(marketContext.market_status);
    pill.className = "market-status-pill " + marketStatusClass(marketContext.market_status);
  }
  if (hint) hint.textContent = marketContext.session_hint || marketContext.market_hours || "";
}

function startLiveClock() {
  renderDateTimeBar();
  if (clockTimer) clearInterval(clockTimer);
  clockTimer = setInterval(() => renderDateTimeBar(), 30000);
}

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
  const refreshed = data.updated ? `Data refreshed ${data.updated}` : "";
  const tg = data.telegram_configured ? " · Telegram on" : "";
  $("header-stats").textContent =
    `Watchlist ${data.watchlist_count ?? 0} · Alerts ${data.active_alerts ?? 0}` +
    (refreshed ? ` · ${refreshed}` : "") + tg;
  if (data.market) renderDateTimeBar(data.market);
  const du = $("dash-updated");
  if (du) du.textContent = data.updated ? `Updated ${data.updated} · Recommend-only desk` : "Recommend-only desk";
}

function renderKpis(data) {
  const grid = $("kpi-grid");
  if (!grid) return;
  const kpis = data.kpis || [];
  if (!kpis.length) {
    grid.innerHTML = '<div class="kpi-card"><span class="kpi-label">Status</span><strong class="kpi-value">Loading</strong></div>';
    return;
  }
  grid.innerHTML = kpis.map((k) => `
    <div class="kpi-card ${k.cls || "neutral"}">
      <span class="kpi-label">${escHtml(k.label)}</span>
      <strong class="kpi-value">${escHtml(String(k.value ?? "—"))}</strong>
      <span class="kpi-sub">${escHtml(k.sub || "")}</span>
    </div>`).join("");
}

function renderActionReport(data) {
  const ar = data.action_report || {};
  const pill = $("action-status-pill");
  const headline = $("action-headline");
  const primaryEl = $("action-primary");
  const stepsEl = $("action-steps");
  const hint = $("action-hint");
  if (!headline) return;

  const st = (ar.status || "NO_TRADE").toLowerCase();
  if (pill) {
    pill.textContent = ar.status === "BUY" ? "BUY READY" : ar.status === "BLOCKED" ? "BLOCKED" : "NO TRADE";
    pill.className = "status-pill " + (st === "buy" ? "buy" : st === "blocked" ? "blocked" : "no_trade");
  }
  headline.textContent = ar.headline || "—";

  const p = ar.primary;
  if (p && primaryEl) {
    primaryEl.innerHTML = `
      <div class="rec-top">
        <div>
          <div class="rec-sym" data-symbol="${escHtml(p.symbol)}">${escHtml(p.symbol)}</div>
          <div class="rec-meta">${escHtml(p.sector || "")} · Score ${p.score ?? "—"} · Conf ${p.confidence ?? "—"}${p.reward_risk != null ? " · R:R " + p.reward_risk : ""}</div>
        </div>
        <span class="signal-badge ${signalClass(p.signal)}">${escHtml(p.signal || "BUY")}</span>
      </div>
      <div class="level-grid">
        <div class="level-box entry"><span>Entry</span><strong>${fmtRs(p.entry)}</strong></div>
        <div class="level-box stop"><span>Stop</span><strong>${fmtRs(p.stop)}</strong></div>
        <div class="level-box target"><span>Target</span><strong>${fmtRs(p.target)}</strong></div>
      </div>
      ${formatQualityFlags(p.quality_flags, p.quality_count)}
      <p class="rec-thesis">${escHtml(p.thesis || "")}</p>
      <p class="muted small">Qty ~${p.buy_qty ?? "—"} · Amount ~${p.buy_amount != null ? fmtRs(p.buy_amount) : "—"} · Manual broker buy only</p>`;
    bindPickClicks(primaryEl);
  } else if (primaryEl) {
    const research = ar.research_picks || [];
    primaryEl.innerHTML = research.length
      ? `<p class="empty-state">No high-confidence BUY. Nearby research ideas:</p>
         ${research.map((r) => `
           <div class="pick-row" data-symbol="${escHtml(r.symbol)}">
             <div class="pick-mid"><strong>${escHtml(r.symbol)}</strong><span>Score ${r.score ?? "—"} · ${escHtml(r.signal || "")}</span></div>
             <span class="signal-badge ${signalClass(r.signal)}">${escHtml(r.signal || "WATCH")}</span>
           </div>`).join("")}`
      : `<p class="empty-state">No recommendation yet. Run morning research on a trading day.</p>`;
    bindPickClicks(primaryEl);
  }

  if (stepsEl) {
    stepsEl.innerHTML = (ar.steps || []).map((s) => `<li>${escHtml(s)}</li>`).join("");
  }
  if (hint) {
    const parts = [ar.sentiment_hint, ar.regime_hint].filter(Boolean);
    hint.textContent = parts.join(" · ");
  }
}

const QUALITY_LABELS = {
  trend_ok: "Trend+ADX",
  ema_stack: "EMA stack",
  pullback: "Pullback",
  rsi_ok: "RSI zone",
  macd_ok: "MACD",
  stoch_ok: "Stoch turn",
  bb_ok: "BB value",
  vol_ok: "Volume",
  rs_ok: "vs Nifty RS",
  room: "Room to run",
  structure: "Higher lows",
  atr_ok: "ATR OK",
};

function formatQualityFlags(flags, count) {
  const list = Array.isArray(flags) ? flags : [];
  if (!list.length && !count) {
    return '<p class="quality-line muted small">Quality flags: —</p>';
  }
  const chips = list.map((f) => {
    const label = QUALITY_LABELS[f] || f;
    return `<span class="quality-chip">${escHtml(label)}</span>`;
  }).join("");
  const n = count != null ? count : list.length;
  return `<div class="quality-line"><span class="quality-count">${n} confirms</span>${chips || '<span class="muted small">none</span>'}</div>`;
}

function renderRecsBoard(data) {
  const board = $("recs-board");
  if (!board) return;
  const top = data.recommendations?.top || [];
  if (!top.length) {
    board.innerHTML = `<p class="empty-state">${escHtml(data.recommendations?.message || "No confidence-gated buys today.")}</p>`;
    return;
  }
  board.innerHTML = top.map((r, i) => {
    const conf = Math.max(0, Math.min(100, Number(r.confidence) || 0));
    const sent = r.sentiment_label && r.sentiment_label !== "NO_NEWS"
      ? ` · News ${r.sentiment_label}`
      : "";
    const setup = r.setup_type ? ` · ${r.setup_type}` : "";
    const rr = r.reward_risk != null ? ` · R:R ${r.reward_risk}` : "";
    return `
      <div class="rec-card" data-symbol="${escHtml(r.symbol)}">
        <div class="rec-top">
          <div>
            <div class="rec-sym">#${i + 1} ${escHtml(r.symbol)}</div>
            <div class="rec-meta">${escHtml(r.sector || "—")} · ${escHtml(r.trend || "")}${escHtml(sent)}${escHtml(setup)}${escHtml(rr)}</div>
          </div>
          <span class="signal-badge ${signalClass(r.signal)}">${escHtml(r.signal || "BUY")}</span>
        </div>
        <div class="rec-metrics">
          <div><span>Score</span><strong>${r.score ?? "—"}</strong></div>
          <div><span>Conf</span><strong>${r.confidence ?? "—"}</strong></div>
          <div><span>Entry</span><strong>${fmtRs(r.entry)}</strong></div>
          <div><span>RSI</span><strong>${r.rsi ?? "—"}</strong></div>
        </div>
        <div class="level-grid">
          <div class="level-box entry"><span>Entry</span><strong>${fmtRs(r.entry)}</strong></div>
          <div class="level-box stop"><span>Stop ${r.stop_pct != null ? "(-" + r.stop_pct + "%)" : ""}</span><strong>${fmtRs(r.stop)}</strong></div>
          <div class="level-box target"><span>Target ${r.target_pct != null ? "(+" + r.target_pct + "%)" : ""}</span><strong>${fmtRs(r.target)}</strong></div>
        </div>
        ${formatQualityFlags(r.quality_flags, r.quality_count)}
        <p class="rec-thesis">${escHtml(r.thesis || (r.reasons || []).slice(0, 2).join(" · ") || "")}</p>
        <div class="conf-bar"><i style="width:${conf}%"></i></div>
      </div>`;
  }).join("");
  bindPickClicks(board);
}

function renderSentiment(data) {
  const s = data.sentiment || {};
  const scoreEl = $("sent-score");
  const labelEl = $("sent-label");
  const subEl = $("sent-sub");
  if (!scoreEl) return;

  const sc = s.score_100;
  scoreEl.textContent = sc != null ? sc : "—";
  scoreEl.className = "sent-score " + (sc >= 60 ? "good" : sc <= 40 ? "bad" : "neutral");
  if (labelEl) labelEl.textContent = s.label || "NEUTRAL";
  if (subEl) {
    subEl.textContent = s.action_hint
      || `${s.headline_count || 0} headlines · regime ${s.regime || "—"}`;
  }

  const bull = Number(s.bullish_pct) || 0;
  const bear = Number(s.bearish_pct) || 0;
  const bullBar = $("sent-bull-bar");
  const bearBar = $("sent-bear-bar");
  if (bullBar) bullBar.style.width = `${Math.min(100, bull)}%`;
  if (bearBar) bearBar.style.width = `${Math.min(100, bear)}%`;
  const bp = $("sent-bull-pct");
  const brp = $("sent-bear-pct");
  if (bp) bp.textContent = `${bull}%`;
  if (brp) brp.textContent = `${bear}%`;

  const feed = $("sent-feed");
  if (feed) {
    const items = s.feed || [];
    feed.innerHTML = items.length
      ? items.slice(0, 8).map((h) => {
          const cls = h.sentiment > 0.12 ? "bull" : h.sentiment < -0.12 ? "bear" : "";
          return `<li class="${cls}">${escHtml(h.title)}
            <span class="src">${escHtml(h.source || "")} · ${escHtml(h.label || "")} (${h.sentiment ?? "—"})</span></li>`;
        }).join("")
      : '<li class="muted">Sentiment feed loads with market news…</li>';
  }
}

function renderMorningBriefing(data) {
  const status = $("morning-status");
  const picks = $("morning-picks");
  const report = $("morning-report-text");
  const details = $("morning-details");
  const staleBanner = $("morning-stale-banner");
  const groqBlock = $("morning-groq-block");
  const groqText = $("morning-groq-text");
  const groqMeta = $("morning-groq-meta");
  const meta = data.report_meta || {};

  if (data.has_groq_morning && groqText) {
    groqText.textContent = data.ai_morning_briefing;
    if (groqMeta) groqMeta.textContent = `Powered by Groq · ${meta.report_display || "latest report"}`;
    groqBlock?.classList.remove("hidden");
  } else if (groqText) {
    groqText.textContent =
      "Groq morning report will appear after Run now or auto scan Mon–Fri 8:30 AM IST. " +
      "Ensure GROQ_API_KEY is set on Render.";
    if (groqMeta) groqMeta.textContent = "";
  }
  const todayLabel = data.market?.today_label || "";

  $("morning-date").textContent = meta.report_display
    ? `Report date: ${meta.report_display}${meta.is_today ? " (today)" : ""}`
    : `Today: ${todayLabel}`;

  if (data.scan?.scan_running) {
    status.textContent = "Morning scan running on cloud (8–12 min)…";
    if (staleBanner) staleBanner.classList.add("hidden");
    return;
  }

  if (meta.stale && staleBanner) {
    staleBanner.classList.remove("hidden");
    staleBanner.textContent =
      `Last morning report is ${meta.age_days} day(s) old. ` +
      `${meta.next_auto}.`;
  } else if (staleBanner) {
    staleBanner.classList.add("hidden");
  }

  if (!data.has_report) {
    status.textContent = "No morning report yet — auto Mon–Fri 8:30–10:30 AM IST";
    picks.innerHTML = '<p class="muted">Tap Run now or wait for morning auto scan.</p>';
    if (details) details.classList.add("hidden");
    return;
  }

  if (meta.is_today) {
    status.textContent = `Today's top ${(data.top_picks || []).length} picks`;
  } else {
    status.textContent = `Archived picks from ${meta.report_display} (wait for next morning research)`;
  }

  const rows = data.top_picks || [];
  const html = rows.length
    ? rows.map((p) => `
      <div class="pick-row" data-symbol="${p.symbol}">
        <div class="pick-mid"><strong>#${p.rank} ${p.symbol}</strong><span>Score ${p.score} · ${p.signal}</span></div>
        <span class="signal-badge ${signalClass(p.signal)}">${p.signal}</span>
      </div>`).join("")
    : "";

  picks.innerHTML = html || '<p class="muted">Tap Run now on Monday morning for fresh report.</p>';
  bindPickClicks(picks);
  if (report) report.textContent = data.report_preview || "";
  if (details) details.classList.toggle("hidden", !data.report_preview);
}

function renderSectorHeatmap(data) {
  const el = $("sector-heatmap");
  if (!el) return;
  const hm = data.sector_heatmap;
  if (!hm?.ok || !hm.sectors?.length) {
    el.innerHTML = '<p class="muted">Sector data loading…</p>';
    return;
  }
  el.innerHTML = hm.sectors.map((s) => {
    const up = s.change_20d >= 0;
    return `
      <div class="sector-row ${s.strong ? "strong" : ""}">
        <span class="sector-name">${escHtml(s.sector)}</span>
        <div class="sector-bar-wrap"><div class="sector-bar ${up ? "up" : "down"}" style="width:${s.bar_pct}%"></div></div>
        <span>${up ? "+" : ""}${s.change_20d}%</span>
      </div>`;
  }).join("");
}

function renderCompare(data) {
  const box = $("compare-result");
  if (!box) return;
  if (!data?.ok) {
    box.classList.remove("hidden");
    box.innerHTML = `<p class="muted">${escHtml(data?.error || "Compare failed")}</p>`;
    return;
  }
  box.classList.remove("hidden");
  const col = (row, win) => `
    <div class="compare-col ${win ? "winner" : ""}">
      <strong>${escHtml(row.symbol)}</strong> · ${escHtml(row.signal)}<br>
      Score <strong>${row.score}</strong> · RSI ${row.rsi}<br>
      ${fmtRs(row.price)} → ${fmtRs(row.target)}<br>
      <span class="muted small">${escHtml(row.summary || "")}</span>
    </div>`;
  box.innerHTML =
    col(data.a, data.winner === data.a.symbol) +
    col(data.b, data.winner === data.b.symbol) +
    `<div class="compare-verdict">${escHtml(data.verdict)}</div>`;
}

async function loadBacktest() {
  try {
    const data = await fetch("/api/performance?days=60").then((r) => r.json());
    if (data.ok) {
      $("bt-win").textContent = data.win_rate != null ? `${data.win_rate}%` : "—";
      $("bt-trades").textContent = data.outcomes ?? data.predictions ?? "—";
      const wins = data.win_rate != null && data.outcomes
        ? Math.round((data.win_rate / 100) * data.outcomes)
        : "—";
      $("bt-wins").textContent = wins;
      const samples = $("backtest-samples");
      if (!data.outcomes) {
        samples.innerHTML = '<p class="muted">No closed prediction outcomes yet. Keep using morning research; audit after ~5 days.</p>';
        return;
      }
      const buckets = data.by_score_bucket || {};
      samples.innerHTML = Object.keys(buckets).map((k) => {
        const b = buckets[k];
        return `<div class="pick-row"><div class="pick-mid"><strong>Score ${k}</strong><span>n=${b.n}</span></div>
          <span class="muted small">avg ${b.avg_return_pct ?? "—"}% · win ${b.win_rate ?? "—"}%</span></div>`;
      }).join("") || '<p class="muted">Building history…</p>';
      return;
    }
    $("backtest-samples").innerHTML = '<p class="muted">Performance data not ready yet.</p>';
  } catch (e) {
    $("backtest-samples").innerHTML = '<p class="muted">Performance unavailable</p>';
  }
}

function escHtml(s) {
  return String(s || "").replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderResult(data) {
  lastResult = data;
  $("result-card").classList.remove("hidden");
  $("chart-card").classList.remove("hidden");
  $("res-symbol").textContent = data.symbol;
  $("res-index").textContent = data.index_group || "";
  const timeBar = $("res-time-bar");
  if (timeBar) {
    const mkt = data.market || marketContext || {};
    const priceTag = data.price_label || (mkt.market_open ? "Live LTP" : "Close / last price");
    const src = (data.live_source || "nse").toUpperCase();
    timeBar.innerHTML =
      `<strong>Analyzed:</strong> ${escHtml(data.analyzed_at || "—")} · ` +
      `<strong>${escHtml(priceTag)}</strong> (${escHtml(src)}) · ` +
      `${escHtml(marketStatusLabel(mkt.market_status))}` +
      (mkt.market_hours ? ` · NSE ${escHtml(mkt.market_hours)}` : "");
  }
  const sigEl = $("res-signal");
  sigEl.textContent = data.signal;
  sigEl.className = "signal-badge " + signalClass(data.signal);
  const stale = $("res-stale-banner");
  const fresh = data.price_freshness || {};
  if (stale) {
    stale.classList.toggle("hidden", !fresh.stale);
    stale.textContent = fresh.warning || "";
  }

  const qs = $("res-quick-summary");
  if (qs) {
    const lines = data.quick_summary || [];
    qs.innerHTML = lines.map((l) => `<span class="summary-chip">${escHtml(l)}</span>`).join("");
  }

  const cl = $("res-checklist");
  if (cl) {
    cl.innerHTML = (data.checklist || []).map((item) =>
      `<li class="${item.pass ? "pass" : "fail"}">${escHtml(item.text)}</li>`
    ).join("");
  }

  const score = data.swing_score || 0;
  $("res-score").textContent = score;
  $("res-score-bar").style.width = score + "%";
  $("res-price").textContent = fmtRs(data.price);
  $("res-target").textContent = fmtRs(data.target);
  if ($("res-stop")) $("res-stop").textContent = fmtRs(data.stop || data.avg_trigger);
  $("res-rsi").textContent = data.rsi ?? "—";
  $("res-trend").textContent = data.trend ?? "—";
  if ($("res-sentiment")) {
    const sl = data.sentiment_label || (data.news_sentiment != null ? `News ${data.news_sentiment}` : "—");
    $("res-sentiment").textContent = sl;
  }
  if ($("res-ema21")) $("res-ema21").textContent = data.ema21 ?? "—";
  if ($("res-ema50")) $("res-ema50").textContent = data.ema50 ?? "—";
  const reasons = data.reasons || [];
  $("res-reasons").innerHTML = reasons.length ? "<strong>Signals</strong><ul>" + reasons.map((r) => `<li>${escHtml(r)}</li>`).join("") + "</ul>" : "";

  const hasFund = data.pe_trailing || data.sector || data.quarter_trend || data.fund_verdict;
  $("res-fund-block").classList.toggle("hidden", !hasFund);
  if (hasFund) {
    $("res-pe").textContent = data.pe_trailing ?? "—";
    const sector = data.sector || "—";
    $("res-sector").textContent = data.sector_strong === false ? `${sector} (weak)` : sector;
    $("res-quarter").textContent = data.quarter_trend ?? "—";
    $("res-fund-verdict").textContent = data.fund_verdict ?? "—";
  }

  const hasLevels = data.support || data.resistance;
  $("res-levels-block").classList.toggle("hidden", !hasLevels);
  if (hasLevels) {
    const note = data.level_note ? ` · ${data.level_note}` : "";
    $("res-levels").textContent = `Support ${fmtRs(data.support)} · Resistance ${fmtRs(data.resistance)}${note}`;
  }

  const headlines = data.news_headlines || [];
  $("res-news-block").classList.toggle("hidden", !headlines.length && !data.news_summary);
  if (headlines.length) {
    $("res-news-list").innerHTML = headlines.map((h) =>
      `<li><span class="news-src">${escHtml(h.source)}</span> ${escHtml(h.title)} <em class="news-sent">${escHtml(h.sentiment)}</em></li>`
    ).join("");
  } else if (data.news_summary) {
    $("res-news-list").innerHTML = `<li>${escHtml(data.news_summary)}</li>`;
  }

  const showAi = data.ai_enabled !== false;
  $("res-ai-block").classList.toggle("hidden", !showAi);
  if (showAi) {
    if (data.ai_note) {
      $("res-ai-meta").textContent = data.analyzed_at ? `Generated ${data.analyzed_at}` : "Groq powered";
      $("res-ai-text").textContent = data.ai_note;
    } else if (data.ai_status === "no_key") {
      $("res-ai-meta").textContent = "API key missing";
      $("res-ai-text").textContent = "Add GROQ_API_KEY in Render environment variables to enable AI reports.";
    } else {
      $("res-ai-meta").textContent = "Unavailable";
      $("res-ai-text").textContent = "AI research could not be generated. Try again in a moment.";
    }
  }

  if (window.renderStockChart) window.renderStockChart(data.symbol);
}

async function runAnalyze(symbol) {
  symbol = (symbol || "").trim().toUpperCase();
  if (!symbol) return toast("Enter symbol");
  $("loading").classList.remove("hidden");
  $("result-card").classList.add("hidden");
  $("btn-analyze").disabled = true;
  try {
    const data = await fetch(`/api/analyze/${encodeURIComponent(symbol)}?ai=1`).then((r) => r.json());
    if (!data.ok) return toast(data.error || "Failed");
    renderResult(data);
  } catch (e) {
    toast("Network error");
  } finally {
    $("loading").classList.add("hidden");
    $("btn-analyze").disabled = false;
  }
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
    const dash = await fetch("/api/dashboard");
    const data = await dash.json();
    renderMarket(data.benchmark);
    renderHeaderStats(data);
    renderKpis(data);
    renderActionReport(data);
    renderRecsBoard(data);
    renderSentiment(data);
    renderMorningBriefing(data);
    renderSectorHeatmap(data);
    renderPosition(data);

    await Promise.all([loadWatchlist(), loadPaper(), loadJournal(), loadAlerts(), loadBacktest()]);
  } catch (e) {
    toast("Load failed");
  }
}

function renderPosition(data) {
  const body = $("position-body");
  const actions = $("position-actions");
  if (!body) return;
  const p = data.position;
  if (!p) {
    body.innerHTML = '<p class="muted">No tracked live position. Paper tab is for practice only.</p>';
    actions?.classList.add("hidden");
    return;
  }
  const pnlCls = (p.pnl_pct || 0) >= 0 ? "green" : "red";
  body.innerHTML = `
    <div class="rec-card" style="cursor:default">
      <div class="rec-top">
        <div><div class="rec-sym">${escHtml(p.symbol)}</div>
        <div class="rec-meta">Qty ${p.qty} · Avg ${fmtRs(p.avg_price)} · Opened ${escHtml(p.opened || "")}</div></div>
        <span class="signal-badge ${signalClass(p.signal)}">${escHtml(p.signal || "—")}</span>
      </div>
      <div class="level-grid">
        <div class="level-box entry"><span>LTP</span><strong>${fmtRs(p.ltp)}</strong></div>
        <div class="level-box stop"><span>Stop zone</span><strong>${fmtRs(p.avg_trigger)}</strong></div>
        <div class="level-box target"><span>Target</span><strong>${fmtRs(p.sell_target)}</strong></div>
      </div>
      <p class="rec-thesis">P&amp;L <span class="${pnlCls}">${p.pnl_pct ?? 0}%</span> · ${escHtml(p.signal_reason || "")}</p>
    </div>`;
  actions?.classList.remove("hidden");
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
      const jMsg = res.journal ? " · Journal linked" : "";
      toast(`Bought ${body.qty} ${sym} @ ${fmtRs(body.price)}${jMsg}`, "success");
      if (opts.form) opts.form.reset();
      await Promise.all([loadPaper(), loadJournal()]);
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
$("btn-run-morning")?.addEventListener("click", async () => {
  const force = confirm("Run morning scan now? On weekends this uses Force mode (8–12 min on cloud).");
  if (!force) return;
  $("btn-run-morning").disabled = true;
  toast("Morning scan starting…");
  try {
    const url = "/api/morning-scan?force=1";
    const d = await fetch(url).then((r) => r.json());
    toast(d.message || (d.started ? "Scan started" : "Could not start"));
    if (d.started) setTimeout(loadDashboard, 15000);
    else loadDashboard();
  } finally {
    $("btn-run-morning").disabled = false;
  }
});
$("btn-paper-from-result").addEventListener("click", quickPaperBuyFromResult);
$("btn-export-pdf").addEventListener("click", () => {
  if (!lastResult?.symbol) return toast("Analyze a stock first", "error");
  window.open(`/api/export/pdf/${encodeURIComponent(lastResult.symbol)}`, "_blank");
});
$("compare-form")?.addEventListener("submit", async (e) => {
  e.preventDefault();
  const a = $("cmp-a").value.trim();
  const b = $("cmp-b").value.trim();
  if (!a || !b) return toast("Enter both symbols");
  toast("Comparing…");
  const data = await fetch(`/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}`).then((r) => r.json());
  renderCompare(data);
});
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

startLiveClock();
loadDashboard();