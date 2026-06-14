"""SQLite persistence: clients + receipts. Stdlib only — light enough for a 1 GB VPS.

State we keep locally:
- clients: TG id -> name, currency, sheet tab, active flag
- receipts: full audit log + dedup (image hash) + sheet-sync status
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone

from .models import Receipt

_SCHEMA = """
CREATE TABLE IF NOT EXISTS clients (
    tg_id      INTEGER PRIMARY KEY,
    name       TEXT NOT NULL,
    currency   TEXT DEFAULT 'USD',
    sheet_tab  TEXT,
    active     INTEGER DEFAULT 1,
    created_at TEXT
);
CREATE TABLE IF NOT EXISTS receipts (
    id         TEXT PRIMARY KEY,           -- image sha256[:16]
    tg_id      INTEGER NOT NULL,
    merchant   TEXT,
    date       TEXT,
    total      TEXT,
    currency   TEXT,
    category   TEXT,
    payload    TEXT,                        -- full Receipt JSON
    synced     INTEGER DEFAULT 0,           -- 1 once written to Sheets
    created_at TEXT,
    UNIQUE(id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, db_path: str):
        # check_same_thread=False + a lock: PTB runs handlers on one loop, but be safe.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = threading.Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            self._conn.commit()

    # --- clients ---
    def add_client(self, tg_id: int, name: str, currency: str = "USD", sheet_tab: str | None = None) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO clients(tg_id,name,currency,sheet_tab,active,created_at) "
                "VALUES(?,?,?,?,1,?) "
                "ON CONFLICT(tg_id) DO UPDATE SET name=excluded.name, "
                "currency=excluded.currency, sheet_tab=excluded.sheet_tab, active=1",
                (tg_id, name, currency, sheet_tab or name, _now()),
            )
            self._conn.commit()

    def get_client(self, tg_id: int) -> sqlite3.Row | None:
        with self._lock:
            cur = self._conn.execute("SELECT * FROM clients WHERE tg_id=? AND active=1", (tg_id,))
            return cur.fetchone()

    def list_clients(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute("SELECT * FROM clients ORDER BY name").fetchall()

    def deactivate_client(self, tg_id: int) -> None:
        with self._lock:
            self._conn.execute("UPDATE clients SET active=0 WHERE tg_id=?", (tg_id,))
            self._conn.commit()

    # --- receipts ---
    def exists(self, receipt_id: str) -> bool:
        with self._lock:
            return self._conn.execute("SELECT 1 FROM receipts WHERE id=?", (receipt_id,)).fetchone() is not None

    def save_receipt(self, receipt_id: str, tg_id: int, r: Receipt) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO receipts"
                "(id,tg_id,merchant,date,total,currency,category,payload,synced,created_at) "
                "VALUES(?,?,?,?,?,?,?,?,0,?)",
                (
                    receipt_id,
                    tg_id,
                    r.merchant,
                    r.date.isoformat() if r.date else None,
                    str(r.total) if r.total is not None else None,
                    r.currency,
                    r.category.value,
                    r.model_dump_json(),
                    _now(),
                ),
            )
            self._conn.commit()

    def mark_synced(self, receipt_id: str) -> None:
        with self._lock:
            self._conn.execute("UPDATE receipts SET synced=1 WHERE id=?", (receipt_id,))
            self._conn.commit()

    def delete_receipt(self, receipt_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM receipts WHERE id=?", (receipt_id,))
            self._conn.commit()

    def unsynced(self) -> list[sqlite3.Row]:
        with self._lock:
            return self._conn.execute("SELECT * FROM receipts WHERE synced=0 ORDER BY created_at").fetchall()

    def load_receipt(self, receipt_id: str) -> Receipt | None:
        with self._lock:
            row = self._conn.execute("SELECT payload FROM receipts WHERE id=?", (receipt_id,)).fetchone()
        if not row:
            return None
        return Receipt.model_validate(json.loads(row["payload"]))

    def close(self) -> None:
        with self._lock:
            self._conn.close()
