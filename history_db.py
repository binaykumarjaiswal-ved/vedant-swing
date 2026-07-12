"""SQLite history for scans, predictions, and outcomes (model audit)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "vedant_swing.db"


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS scans (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                scan_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                score REAL,
                signal TEXT,
                strategy TEXT,
                price REAL,
                confidence REAL,
                data_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(scan_date, symbol, strategy)
            );
            CREATE INDEX IF NOT EXISTS idx_scans_date ON scans(scan_date);
            CREATE INDEX IF NOT EXISTS idx_scans_symbol ON scans(symbol);

            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                pred_date TEXT NOT NULL,
                symbol TEXT NOT NULL,
                score REAL,
                confidence REAL,
                signal TEXT,
                strategy TEXT,
                entry REAL,
                stop REAL,
                target REAL,
                qty INTEGER,
                target_pct REAL,
                stop_pct REAL,
                horizon_days INTEGER DEFAULT 7,
                regime TEXT,
                regime_score REAL,
                source TEXT,
                data_json TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(pred_date, symbol, source)
            );
            CREATE INDEX IF NOT EXISTS idx_pred_date ON predictions(pred_date);

            CREATE TABLE IF NOT EXISTS outcomes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prediction_id INTEGER NOT NULL,
                symbol TEXT NOT NULL,
                pred_date TEXT NOT NULL,
                check_date TEXT NOT NULL,
                entry REAL,
                exit_price REAL,
                return_pct REAL,
                hit_target INTEGER,
                hit_stop INTEGER,
                max_gain_pct REAL,
                max_loss_pct REAL,
                days_held INTEGER,
                status TEXT,
                notes TEXT,
                created_at TEXT NOT NULL,
                UNIQUE(prediction_id),
                FOREIGN KEY(prediction_id) REFERENCES predictions(id)
            );

            CREATE TABLE IF NOT EXISTS daily_regime (
                day TEXT PRIMARY KEY,
                score REAL,
                regime TEXT,
                trade_approval INTEGER,
                data_json TEXT,
                created_at TEXT NOT NULL
            );
            """
        )


def log_scan_batch(scan_date: str, rows: list[dict[str, Any]], strategy: str = "scan") -> int:
    """Log many scan rows. Returns count inserted/updated."""
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    n = 0
    with _connect() as conn:
        for r in rows:
            sym = (r.get("symbol") or "").upper()
            if not sym:
                continue
            strat = r.get("strategy") or strategy
            payload = {
                k: r.get(k)
                for k in (
                    "swing_score", "signal", "price", "entry", "target", "stop",
                    "rsi", "trend", "confidence", "reasons", "sector",
                )
                if k in r or r.get(k) is not None
            }
            conn.execute(
                """
                INSERT INTO scans (scan_date, symbol, score, signal, strategy, price,
                                  confidence, data_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(scan_date, symbol, strategy) DO UPDATE SET
                    score=excluded.score,
                    signal=excluded.signal,
                    price=excluded.price,
                    confidence=excluded.confidence,
                    data_json=excluded.data_json,
                    created_at=excluded.created_at
                """,
                (
                    scan_date,
                    sym,
                    float(r.get("swing_score") or r.get("score") or 0),
                    r.get("signal"),
                    strat,
                    float(r.get("price") or r.get("entry") or 0),
                    float(r.get("confidence") or 0),
                    json.dumps(payload, default=str),
                    now,
                ),
            )
            n += 1
    return n


def log_prediction(pick: dict[str, Any], source: str = "morning") -> int | None:
    """Log a BUY recommendation for later outcome validation."""
    init_db()
    from market_calendar import ist_now

    pred_date = pick.get("pred_date") or ist_now().strftime("%Y-%m-%d")
    symbol = (pick.get("symbol") or "").upper()
    if not symbol:
        return None
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        cur = conn.execute(
            """
            INSERT INTO predictions (
                pred_date, symbol, score, confidence, signal, strategy,
                entry, stop, target, qty, target_pct, stop_pct, horizon_days,
                regime, regime_score, source, data_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(pred_date, symbol, source) DO UPDATE SET
                score=excluded.score,
                confidence=excluded.confidence,
                signal=excluded.signal,
                strategy=excluded.strategy,
                entry=excluded.entry,
                stop=excluded.stop,
                target=excluded.target,
                qty=excluded.qty,
                target_pct=excluded.target_pct,
                stop_pct=excluded.stop_pct,
                regime=excluded.regime,
                regime_score=excluded.regime_score,
                data_json=excluded.data_json,
                created_at=excluded.created_at
            """,
            (
                pred_date,
                symbol,
                float(pick.get("swing_score") or pick.get("score") or 0),
                float(pick.get("confidence") or 0),
                pick.get("signal") or "BUY",
                pick.get("strategy") or "composite",
                float(pick.get("entry") or pick.get("best_buy_price") or pick.get("price") or 0),
                float(pick.get("stop") or 0),
                float(pick.get("target") or 0),
                int(pick.get("buy_qty") or pick.get("qty") or 0),
                float(pick.get("target_pct") or 0),
                float(pick.get("stop_pct") or 0),
                int(pick.get("horizon_days") or 7),
                pick.get("regime") or "",
                float(pick.get("regime_score") or 0),
                source,
                json.dumps(pick, default=str)[:8000],
                now,
            ),
        )
        # Fetch id
        row = conn.execute(
            "SELECT id FROM predictions WHERE pred_date=? AND symbol=? AND source=?",
            (pred_date, symbol, source),
        ).fetchone()
        return int(row["id"]) if row else cur.lastrowid


def log_regime(day: str, regime: dict[str, Any]) -> None:
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO daily_regime (day, score, regime, trade_approval, data_json, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(day) DO UPDATE SET
                score=excluded.score,
                regime=excluded.regime,
                trade_approval=excluded.trade_approval,
                data_json=excluded.data_json,
                created_at=excluded.created_at
            """,
            (
                day,
                float(regime.get("score") or 0),
                regime.get("regime") or "NEUTRAL",
                1 if regime.get("trade_approval") else 0,
                json.dumps(regime, default=str),
                now,
            ),
        )


def pending_predictions(max_age_days: int = 14, min_age_days: int = 5) -> list[dict]:
    """Predictions old enough to score, without an outcome yet."""
    init_db()
    from market_calendar import ist_now

    today = ist_now().date()
    oldest = (today - timedelta(days=max_age_days)).isoformat()
    newest = (today - timedelta(days=min_age_days)).isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT p.* FROM predictions p
            LEFT JOIN outcomes o ON o.prediction_id = p.id
            WHERE o.id IS NULL
              AND p.pred_date >= ? AND p.pred_date <= ?
              AND p.entry > 0
            ORDER BY p.pred_date ASC
            """,
            (oldest, newest),
        ).fetchall()
    return [dict(r) for r in rows]


def save_outcome(prediction_id: int, outcome: dict[str, Any]) -> None:
    init_db()
    now = datetime.now().isoformat(timespec="seconds")
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO outcomes (
                prediction_id, symbol, pred_date, check_date, entry, exit_price,
                return_pct, hit_target, hit_stop, max_gain_pct, max_loss_pct,
                days_held, status, notes, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(prediction_id) DO UPDATE SET
                check_date=excluded.check_date,
                exit_price=excluded.exit_price,
                return_pct=excluded.return_pct,
                hit_target=excluded.hit_target,
                hit_stop=excluded.hit_stop,
                max_gain_pct=excluded.max_gain_pct,
                max_loss_pct=excluded.max_loss_pct,
                days_held=excluded.days_held,
                status=excluded.status,
                notes=excluded.notes,
                created_at=excluded.created_at
            """,
            (
                prediction_id,
                outcome["symbol"],
                outcome["pred_date"],
                outcome.get("check_date") or now[:10],
                float(outcome.get("entry") or 0),
                float(outcome.get("exit_price") or 0),
                float(outcome.get("return_pct") or 0),
                1 if outcome.get("hit_target") else 0,
                1 if outcome.get("hit_stop") else 0,
                float(outcome.get("max_gain_pct") or 0),
                float(outcome.get("max_loss_pct") or 0),
                int(outcome.get("days_held") or 0),
                outcome.get("status") or "closed",
                outcome.get("notes") or "",
                now,
            ),
        )


def performance_summary(days: int = 60) -> dict[str, Any]:
    """Aggregate model performance from outcomes."""
    init_db()
    from market_calendar import ist_now

    since = (ist_now().date() - timedelta(days=days)).isoformat()
    with _connect() as conn:
        outcomes = conn.execute(
            """
            SELECT o.*, p.score, p.confidence, p.strategy, p.signal
            FROM outcomes o
            JOIN predictions p ON p.id = o.prediction_id
            WHERE o.pred_date >= ?
            """,
            (since,),
        ).fetchall()
        pred_count = conn.execute(
            "SELECT COUNT(*) AS n FROM predictions WHERE pred_date >= ?",
            (since,),
        ).fetchone()["n"]
        open_count = conn.execute(
            """
            SELECT COUNT(*) AS n FROM predictions p
            LEFT JOIN outcomes o ON o.prediction_id = p.id
            WHERE o.id IS NULL AND p.pred_date >= ?
            """,
            (since,),
        ).fetchone()["n"]

    rows = [dict(r) for r in outcomes]
    if not rows:
        return {
            "ok": True,
            "days": days,
            "predictions": pred_count,
            "outcomes": 0,
            "open_predictions": open_count,
            "win_rate": None,
            "avg_return_pct": None,
            "hit_target_rate": None,
            "by_score_bucket": {},
            "message": "Not enough closed outcomes yet. Keep logging predictions.",
        }

    wins = sum(1 for r in rows if (r.get("return_pct") or 0) > 0)
    hits = sum(1 for r in rows if r.get("hit_target"))
    avg_ret = sum(r.get("return_pct") or 0 for r in rows) / len(rows)

    buckets: dict[str, list[float]] = {"0-50": [], "50-62": [], "62-75": [], "75-100": []}
    for r in rows:
        s = float(r.get("score") or 0)
        ret = float(r.get("return_pct") or 0)
        if s < 50:
            buckets["0-50"].append(ret)
        elif s < 62:
            buckets["50-62"].append(ret)
        elif s < 75:
            buckets["62-75"].append(ret)
        else:
            buckets["75-100"].append(ret)

    by_bucket = {}
    for k, vals in buckets.items():
        if vals:
            by_bucket[k] = {
                "n": len(vals),
                "avg_return_pct": round(sum(vals) / len(vals), 2),
                "win_rate": round(sum(1 for v in vals if v > 0) / len(vals) * 100, 1),
            }
        else:
            by_bucket[k] = {"n": 0, "avg_return_pct": None, "win_rate": None}

    return {
        "ok": True,
        "days": days,
        "predictions": pred_count,
        "outcomes": len(rows),
        "open_predictions": open_count,
        "win_rate": round(wins / len(rows) * 100, 1),
        "hit_target_rate": round(hits / len(rows) * 100, 1),
        "avg_return_pct": round(avg_ret, 2),
        "by_score_bucket": by_bucket,
        "sample_outcomes": rows[-10:],
    }


def latest_recommendations(limit: int = 10) -> list[dict]:
    init_db()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM predictions
            ORDER BY pred_date DESC, confidence DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# Init on import for convenience
try:
    init_db()
except Exception:
    pass
