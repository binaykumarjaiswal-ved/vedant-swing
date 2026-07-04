"""Gmail email alerts for Vedant Swing reports."""

from __future__ import annotations

import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from pa_config import EMAIL_APP_PASSWORD, EMAIL_ENABLED, EMAIL_FROM, EMAIL_TO

BASE_DIR = Path(__file__).parent
LOG = BASE_DIR / "data" / "email_log.json"

STRATEGY_LABELS = {
    "pullback_21ema": "Pullback 21 EMA",
    "breakout": "Breakout",
    "oversold_bounce": "Oversold Bounce",
}


def _log(subject: str, ok: bool, detail: str = "") -> None:
    try:
        data = json.loads(LOG.read_text(encoding="utf-8")) if LOG.exists() else {"events": []}
    except json.JSONDecodeError:
        data = {"events": []}
    data["events"].insert(0, {
        "time": datetime.now().isoformat(timespec="seconds"),
        "subject": subject,
        "ok": ok,
        "detail": detail[:200],
    })
    data["events"] = data["events"][:50]
    LOG.parent.mkdir(parents=True, exist_ok=True)
    LOG.write_text(json.dumps(data, indent=2), encoding="utf-8")


def is_configured() -> bool:
    return bool(EMAIL_ENABLED and EMAIL_FROM and EMAIL_TO and EMAIL_APP_PASSWORD)


def send_email(subject: str, text_body: str, html_body: str | None = None) -> bool:
    if not is_configured():
        print("EMAIL: not configured (set EMAIL_* in secrets.env or Render/GitHub Secrets)")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Vedant Swing] {subject}"
    msg["From"] = EMAIL_FROM
    msg["To"] = EMAIL_TO
    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    if html_body:
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.starttls()
            server.login(EMAIL_FROM, EMAIL_APP_PASSWORD)
            server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        _log(subject, True)
        print(f"EMAIL SENT: {subject}")
        return True
    except Exception as exc:
        _log(subject, False, str(exc))
        print(f"EMAIL FAILED: {exc}")
        return False


def format_evening_email(payload: dict) -> tuple[str, str]:
    lines = [
        "VEDANT SWING — Evening Scan Report",
        f"Date: {payload.get('generated', '')[:16]}",
        f"Universe: {payload.get('universe', 'Nifty 500')}",
        f"Scanned: {payload.get('scanned', 0)} stocks",
        f"Setups found: {payload.get('hits', 0)}",
        "",
        "── TOP SETUPS ──",
    ]
    for i, p in enumerate((payload.get("top") or [])[:10], 1):
        strat = STRATEGY_LABELS.get(p.get("strategy", ""), p.get("strategy", ""))
        lines.append(
            f"{i}. {p.get('symbol')} | {strat} | {p.get('signal')} | "
            f"Score {p.get('swing_score')} | Rs.{p.get('price', 0)}"
        )
    lines.extend(["", "Open Vedant Swing app for full analysis.", "Not SEBI advice."])
    text = "\n".join(lines)

    rows = ""
    for p in (payload.get("top") or [])[:10]:
        strat = STRATEGY_LABELS.get(p.get("strategy", ""), p.get("strategy", ""))
        rows += (
            f"<tr><td>{p.get('symbol')}</td><td>{strat}</td>"
            f"<td>{p.get('signal')}</td><td>{p.get('swing_score')}</td>"
            f"<td>Rs.{p.get('price', 0)}</td></tr>"
        )
    html = f"""<html><body style="font-family:Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px">
    <h2 style="color:#38bdf8">Vedant Swing — Evening Scan</h2>
    <p>Scanned <b>{payload.get('scanned', 0)}</b> stocks · <b>{payload.get('hits', 0)}</b> setups</p>
    <table border="1" cellpadding="8" style="border-collapse:collapse;width:100%;max-width:600px">
    <tr style="background:#1e293b"><th>Symbol</th><th>Strategy</th><th>Signal</th><th>Score</th><th>Price</th></tr>
    {rows}</table>
    <p style="color:#94a3b8;font-size:12px">Automated research. Not financial advice.</p></body></html>"""
    return text, html


def format_morning_email(text_report: str, picks: list[dict], benchmark: dict) -> tuple[str, str]:
    subject_lines = text_report.splitlines()[:8]
    body = "\n".join(subject_lines) + "\n\n" + text_report[:4000]
    rows = ""
    for p in picks[:10]:
        rows += f"<li><b>{p.get('symbol')}</b> — {p.get('signal')} — Score {p.get('swing_score')} — Rs.{p.get('price', 0)}</li>"
    html = f"""<html><body style="font-family:Segoe UI,sans-serif;background:#0f172a;color:#e2e8f0;padding:20px">
    <h2 style="color:#38bdf8">Vedant Swing — Morning Research</h2>
    <p>Nifty mood: <b>{benchmark.get('mood', 'NEUTRAL')}</b> · 20d {benchmark.get('change_20d', 0):+.1f}%</p>
    <ul>{rows}</ul>
    <pre style="background:#1e293b;padding:12px;border-radius:8px;white-space:pre-wrap">{text_report[:3000]}</pre>
    </body></html>"""
    return body, html


def send_evening_report(payload: dict) -> bool:
    text, html = format_evening_email(payload)
    day = datetime.now().strftime("%Y-%m-%d")
    return send_email(f"Evening Scan {day} — {payload.get('hits', 0)} setups", text, html)


def send_morning_report(text_report: str, picks: list[dict], benchmark: dict) -> bool:
    text, html = format_morning_email(text_report, picks, benchmark)
    day = datetime.now().strftime("%Y-%m-%d")
    return send_email(f"Morning Research {day}", text, html)


def send_alert_email(message: str) -> bool:
    day = datetime.now().strftime("%Y-%m-%d %H:%M")
    return send_email(f"Price Alert {day}", message)