#!/usr/bin/env python3
"""Vedant Swing — cloud web dashboard."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from flask import Flask, Response, jsonify, render_template, request

from webapp.services import (
    analyze_symbol,
    cron_morning_scan,
    format_share_text,
    get_dashboard,
    get_report,
    get_scan_status_api,
    list_reports,
    position_action,
)

app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# Bump when UI changes — forces browsers to load new JS/CSS after deploy
BUILD_VERSION = os.environ.get("RENDER_GIT_COMMIT", "a3e1300")[:7]


@app.after_request
def _no_cache_html(response):
    if request.path == "/" or request.path.endswith(".html"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    return response


@app.route("/")
def index():
    return render_template("index.html", build_ver=BUILD_VERSION)


@app.route("/api/health")
def api_health():
    return jsonify({"ok": True, "service": "vedant-swing"})


@app.route("/api/dashboard")
def api_dashboard():
    return jsonify(get_dashboard())


@app.route("/api/scan-status")
def api_scan_status():
    return jsonify(get_scan_status_api())


@app.route("/api/cron/morning")
def api_cron_morning():
    key = request.args.get("key", "")
    return jsonify(cron_morning_scan(key))


@app.route("/api/analyze/<symbol>")
def api_analyze(symbol: str):
    with_ai = request.args.get("ai", "1") != "0"
    data = analyze_symbol(symbol, with_ai=with_ai)
    if data.get("ok"):
        data["share_text"] = format_share_text(data)
    return jsonify(data)


@app.route("/api/share/<symbol>")
def api_share(symbol: str):
    data = analyze_symbol(symbol, with_ai=True)
    return jsonify({"text": format_share_text(data)})


@app.route("/api/reports")
def api_reports():
    return jsonify({"reports": list_reports()})


@app.route("/api/reports/<date>")
def api_report(date: str):
    return jsonify(get_report(date))


@app.route("/api/position/<action>", methods=["POST"])
def api_position(action: str):
    body = request.get_json(silent=True) or {}
    result = position_action(
        action,
        symbol=body.get("symbol"),
        price=body.get("price"),
    )
    return jsonify(result)


@app.route("/api/evening-scan")
def api_evening_scan():
    from evening_scan import run_evening_scan
    return jsonify(run_evening_scan())


@app.route("/api/evening-scan/latest")
def api_evening_scan_latest():
    from webapp.services import get_latest_evening_scan
    return jsonify(get_latest_evening_scan())


@app.route("/api/paper")
def api_paper():
    from paper_trading import get_portfolio
    return jsonify(get_portfolio())


@app.route("/api/paper/<action>", methods=["POST"])
def api_paper_action(action: str):
    from paper_trading import paper_buy, paper_sell
    body = request.get_json(silent=True) or {}
    if action == "buy":
        return jsonify(paper_buy(
            body.get("symbol", ""),
            int(body.get("qty", 0)),
            float(body.get("price", 0)),
            float(body.get("stop", 0)),
            float(body.get("target", 0)),
            link_journal=body.get("link_journal", True),
            strategy=body.get("strategy", "paper"),
        ))
    if action == "sell":
        return jsonify(paper_sell(body.get("id", ""), float(body.get("price", 0))))
    return jsonify({"ok": False, "error": "Unknown action"})


@app.route("/api/journal")
def api_journal():
    from journal import list_entries
    return jsonify({"entries": list_entries()})


@app.route("/api/journal", methods=["POST"])
def api_journal_add():
    from journal import add_entry
    body = request.get_json(silent=True) or {}
    return jsonify(add_entry(
        body.get("symbol", ""),
        float(body.get("entry", 0)),
        float(body.get("stop", 0)),
        float(body.get("target", 0)),
        strategy=body.get("strategy", ""),
        notes=body.get("notes", ""),
        qty=int(body.get("qty", 0)),
    ))


@app.route("/api/journal/<entry_id>/close", methods=["POST"])
def api_journal_close(entry_id: str):
    from journal import close_entry
    body = request.get_json(silent=True) or {}
    return jsonify(close_entry(entry_id, float(body.get("exit", 0))))


@app.route("/api/chart/<symbol>")
def api_chart(symbol: str):
    from chart_data import get_chart_payload
    range_key = request.args.get("range", request.args.get("period", "6m")).lower()
    days_raw = request.args.get("days")
    days = int(days_raw) if days_raw else None
    return jsonify(get_chart_payload(symbol, range_key=range_key, days=days))


@app.route("/api/watchlists")
def api_watchlists():
    from watchlists import list_watchlists
    return jsonify(list_watchlists())


@app.route("/api/watchlists/<watchlist_id>")
def api_watchlist_get(watchlist_id: str):
    from watchlists import get_watchlist
    return jsonify(get_watchlist(watchlist_id))


@app.route("/api/watchlists/<watchlist_id>/add", methods=["POST"])
def api_watchlist_add(watchlist_id: str):
    from watchlists import add_symbol
    body = request.get_json(silent=True) or {}
    return jsonify(add_symbol(body.get("symbol", ""), watchlist_id, body.get("note", "")))


@app.route("/api/watchlists/<watchlist_id>/remove", methods=["POST"])
def api_watchlist_remove(watchlist_id: str):
    from watchlists import remove_symbol
    body = request.get_json(silent=True) or {}
    return jsonify(remove_symbol(body.get("symbol", ""), watchlist_id))


@app.route("/api/alerts")
def api_alerts_list():
    from alerts import list_alerts
    return jsonify({"alerts": list_alerts(active_only=False)})


@app.route("/api/alerts", methods=["POST"])
def api_alerts_add():
    from alerts import add_alert
    body = request.get_json(silent=True) or {}
    return jsonify(add_alert(
        body.get("symbol", ""),
        body.get("condition", "above"),
        float(body.get("price", 0)),
        body.get("note", ""),
    ))


@app.route("/api/alerts/<alert_id>", methods=["DELETE"])
def api_alerts_delete(alert_id: str):
    from alerts import remove_alert
    return jsonify(remove_alert(alert_id))


@app.route("/api/alerts/check")
def api_alerts_check():
    from alerts import check_alerts
    return jsonify(check_alerts())


@app.route("/api/email/status")
def api_email_status():
    from email_notify import is_configured
    return jsonify({"configured": is_configured()})


@app.route("/api/compare")
def api_compare():
    from webapp.insights import compare_symbols

    a = request.args.get("a", "").strip()
    b = request.args.get("b", "").strip()
    if not a or not b:
        return jsonify({"ok": False, "error": "Provide ?a=SYMBOL&b=SYMBOL"})
    return jsonify(compare_symbols(a, b))


@app.route("/api/backtest")
def api_backtest():
    from webapp.insights import backtest_evening_scan

    days = int(request.args.get("days", 30))
    return jsonify(backtest_evening_scan(days=min(days, 60)))


@app.route("/api/export/pdf/<symbol>")
def api_export_pdf(symbol: str):
    from webapp.insights import build_research_pdf

    data = analyze_symbol(symbol, with_ai=True)
    if not data.get("ok"):
        return jsonify(data), 404
    pdf_bytes = build_research_pdf(data)
    fname = f"{symbol.upper()}_research.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@app.route("/api/telegram/status")
def api_telegram_status():
    from web_notify import is_telegram_configured
    return jsonify({"configured": is_telegram_configured()})


@app.route("/api/alert-log")
def api_alert_log():
    from pathlib import Path
    import json
    log = Path(__file__).resolve().parent.parent / "data" / "alert_log.json"
    if not log.exists():
        return jsonify({"events": []})
    try:
        return jsonify(json.loads(log.read_text(encoding="utf-8")))
    except json.JSONDecodeError:
        return jsonify({"events": []})


def main():
    port = int(os.environ.get("PORT", 5050))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()