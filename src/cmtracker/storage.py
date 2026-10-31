"""SQLite-Persistenz für Preisverlauf, gesendete Alerts und Käufe."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .models import Offer, PriceGuide, Snapshot, utcnow

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_key TEXT NOT NULL,
    taken_at TEXT NOT NULL,
    offer_count INTEGER NOT NULL,
    total_offer_count INTEGER NOT NULL,
    min_price REAL,
    avg5_price REAL,
    median_price REAL,
    trend REAL,
    avg1 REAL,
    avg7 REAL,
    avg30 REAL,
    low REAL,
    product_url TEXT,
    offers_json TEXT NOT NULL DEFAULT '[]'
);
CREATE INDEX IF NOT EXISTS idx_snapshots_card_time ON snapshots(card_key, taken_at);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_key TEXT NOT NULL,
    rule TEXT NOT NULL,
    price REAL,
    message TEXT,
    sent_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_alerts_card_rule ON alerts(card_key, rule, sent_at);

CREATE TABLE IF NOT EXISTS purchases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    card_key TEXT NOT NULL,
    article_id TEXT,
    seller TEXT,
    price REAL NOT NULL,
    quantity INTEGER NOT NULL,
    mode TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""

# Kauf-Status, die als "gekauft" bzw. budgetrelevant zählen
REAL_PURCHASE_STATUSES = ("in_cart", "ordered")
SIMULATED_STATUSES = ("simulated",)


def _ts(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


@dataclass(slots=True)
class AlertRecord:
    card_key: str
    rule: str
    price: float | None
    message: str
    sent_at: datetime


@dataclass(slots=True)
class PurchaseRecord:
    id: int
    card_key: str
    article_id: str | None
    seller: str | None
    price: float
    quantity: int
    mode: str
    status: str
    detail: str | None
    created_at: datetime


class Storage:
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        # Scheduler und Weboberfläche greifen parallel zu -> WAL + Wartezeit bei Locks
        self.conn = sqlite3.connect(self.path, timeout=30)
        self.conn.row_factory = sqlite3.Row
        if self.path != ":memory:":
            self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------------ Snapshots

    def save_snapshot(self, snap: Snapshot) -> int:
        g = snap.price_guide
        cur = self.conn.execute(
            """INSERT INTO snapshots (card_key, taken_at, offer_count, total_offer_count,
                   min_price, avg5_price, median_price, trend, avg1, avg7, avg30, low,
                   product_url, offers_json)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                snap.card_key,
                _ts(snap.taken_at),
                snap.offer_count,
                snap.total_offer_count,
                snap.min_price,
                snap.avg5_price,
                snap.median_price,
                g.trend,
                g.avg1,
                g.avg7,
                g.avg30,
                g.low,
                snap.product_url,
                json.dumps([o.to_dict() for o in snap.offers], ensure_ascii=False),
            ),
        )
        self.conn.commit()
        snap.id = cur.lastrowid
        return snap.id

    @staticmethod
    def _row_to_snapshot(row: sqlite3.Row, with_offers: bool = True) -> Snapshot:
        offers = [Offer.from_dict(o) for o in json.loads(row["offers_json"])] if with_offers else []
        return Snapshot(
            id=row["id"],
            card_key=row["card_key"],
            taken_at=datetime.fromisoformat(row["taken_at"]),
            offer_count=row["offer_count"],
            total_offer_count=row["total_offer_count"],
            min_price=row["min_price"],
            avg5_price=row["avg5_price"],
            median_price=row["median_price"],
            price_guide=PriceGuide(
                trend=row["trend"],
                avg1=row["avg1"],
                avg7=row["avg7"],
                avg30=row["avg30"],
                low=row["low"],
            ),
            offers=offers,
            product_url=row["product_url"],
        )

    def latest_snapshot(self, card_key: str) -> Snapshot | None:
        row = self.conn.execute(
            "SELECT * FROM snapshots WHERE card_key=? ORDER BY taken_at DESC, id DESC LIMIT 1",
            (card_key,),
        ).fetchone()
        return self._row_to_snapshot(row) if row else None

    def snapshot_at_or_before(self, card_key: str, when: datetime) -> Snapshot | None:
        row = self.conn.execute(
            """SELECT * FROM snapshots WHERE card_key=? AND taken_at<=?
               ORDER BY taken_at DESC, id DESC LIMIT 1""",
            (card_key, _ts(when)),
        ).fetchone()
        return self._row_to_snapshot(row, with_offers=False) if row else None

    def history(self, card_key: str, since: datetime | None = None) -> list[Snapshot]:
        if since is None:
            rows = self.conn.execute(
                "SELECT * FROM snapshots WHERE card_key=? ORDER BY taken_at, id", (card_key,)
            )
        else:
            rows = self.conn.execute(
                "SELECT * FROM snapshots WHERE card_key=? AND taken_at>=? ORDER BY taken_at, id",
                (card_key, _ts(since)),
            )
        return [self._row_to_snapshot(r, with_offers=False) for r in rows]

    def all_time_low(self, card_key: str) -> float | None:
        row = self.conn.execute(
            "SELECT MIN(min_price) AS p FROM snapshots WHERE card_key=?", (card_key,)
        ).fetchone()
        return row["p"] if row else None

    def known_card_keys(self) -> list[str]:
        return [r[0] for r in self.conn.execute("SELECT DISTINCT card_key FROM snapshots")]

    # ------------------------------------------------------------------ Alerts

    def record_alert(self, card_key: str, rule: str, price: float | None, message: str) -> None:
        self.conn.execute(
            "INSERT INTO alerts (card_key, rule, price, message, sent_at) VALUES (?,?,?,?,?)",
            (card_key, rule, price, message, _ts(utcnow())),
        )
        self.conn.commit()

    def last_alert(self, card_key: str, rule: str) -> AlertRecord | None:
        row = self.conn.execute(
            """SELECT * FROM alerts WHERE card_key=? AND rule=?
               ORDER BY sent_at DESC, id DESC LIMIT 1""",
            (card_key, rule),
        ).fetchone()
        return self._row_to_alert(row) if row else None

    def alerts_since(self, since: datetime, card_key: str | None = None) -> list[AlertRecord]:
        sql = "SELECT * FROM alerts WHERE sent_at>=?"
        args: list[object] = [_ts(since)]
        if card_key:
            sql += " AND card_key=?"
            args.append(card_key)
        rows = self.conn.execute(sql + " ORDER BY sent_at DESC, id DESC", args)
        return [self._row_to_alert(r) for r in rows]

    @staticmethod
    def _row_to_alert(row: sqlite3.Row) -> AlertRecord:
        return AlertRecord(
            card_key=row["card_key"],
            rule=row["rule"],
            price=row["price"],
            message=row["message"],
            sent_at=datetime.fromisoformat(row["sent_at"]),
        )

    # ------------------------------------------------------------------ Käufe

    def record_purchase(
        self,
        card_key: str,
        article_id: str | None,
        seller: str | None,
        price: float,
        quantity: int,
        mode: str,
        status: str,
        detail: str | None = None,
    ) -> int:
        cur = self.conn.execute(
            """INSERT INTO purchases (card_key, article_id, seller, price, quantity, mode,
                   status, detail, created_at) VALUES (?,?,?,?,?,?,?,?,?)""",
            (card_key, article_id, seller, price, quantity, mode, status, detail, _ts(utcnow())),
        )
        self.conn.commit()
        return cur.lastrowid

    def bought_quantity(self, card_key: str, statuses: tuple[str, ...]) -> int:
        marks = ",".join("?" * len(statuses))
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(quantity),0) FROM purchases WHERE card_key=? "
            f"AND status IN ({marks})",
            (card_key, *statuses),
        ).fetchone()
        return int(row[0])

    def spent_since(self, since: datetime, statuses: tuple[str, ...]) -> float:
        marks = ",".join("?" * len(statuses))
        row = self.conn.execute(
            f"SELECT COALESCE(SUM(price*quantity),0) FROM purchases WHERE created_at>=? "
            f"AND status IN ({marks})",
            (_ts(since), *statuses),
        ).fetchone()
        return float(row[0])

    def handled_article_ids(self, card_key: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT article_id FROM purchases WHERE card_key=? AND article_id IS NOT NULL "
            "AND status != 'failed'",
            (card_key,),
        )
        return {r[0] for r in rows}

    def purchases(self, limit: int = 50) -> list[PurchaseRecord]:
        rows = self.conn.execute(
            "SELECT * FROM purchases ORDER BY created_at DESC, id DESC LIMIT ?", (limit,)
        )
        return [
            PurchaseRecord(
                id=r["id"],
                card_key=r["card_key"],
                article_id=r["article_id"],
                seller=r["seller"],
                price=r["price"],
                quantity=r["quantity"],
                mode=r["mode"],
                status=r["status"],
                detail=r["detail"],
                created_at=datetime.fromisoformat(r["created_at"]),
            )
            for r in rows
        ]

    def delete_card_data(self, card_key: str) -> None:
        for table in ("snapshots", "alerts", "purchases"):
            self.conn.execute(f"DELETE FROM {table} WHERE card_key=?", (card_key,))
        self.conn.execute("DELETE FROM meta WHERE key=?", (f"status:{card_key}",))
        self.conn.commit()

    # ------------------------------------------------------------------ Meta

    def get_meta(self, key: str) -> str | None:
        row = self.conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return row[0] if row else None

    def set_card_status(self, card_key: str, error: str | None) -> None:
        self.set_meta(
            f"status:{card_key}",
            json.dumps({"checked_at": _ts(utcnow()), "error": error}, ensure_ascii=False),
        )

    def card_status(self, card_key: str) -> dict | None:
        raw = self.get_meta(f"status:{card_key}")
        if not raw:
            return None
        data = json.loads(raw)
        data["checked_at"] = datetime.fromisoformat(data["checked_at"])
        return data

    def purchases_for(self, card_key: str, limit: int = 50) -> list[PurchaseRecord]:
        return [p for p in self.purchases(limit=1000) if p.card_key == card_key][:limit]

    def set_meta(self, key: str, value: str) -> None:
        self.conn.execute(
            "INSERT INTO meta (key, value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )
        self.conn.commit()
