"""Persistence for the five tables: farmers, runs, alerts, ledger, tickets.

`Repository` is the interface the rest of the app uses. A backend only implements three primitives
(`_put`, `_get`, `_all`); everything else is built on those, so SQLite and Supabase behave the same.
Pick the backend with DB_BACKEND.
"""

from __future__ import annotations

import json
import sqlite3
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, TypeVar

import httpx
from pydantic import BaseModel

from .config import Settings
from .models import Alert, Farmer, LedgerEntry, RunRecord, Ticket, now

M = TypeVar("M", bound=BaseModel)


@dataclass(frozen=True)
class TableSpec:
    name: str
    model: type[BaseModel]
    columns: tuple[str, ...]  # the id column first
    json_columns: tuple[str, ...] = ()


FARMERS = TableSpec(
    "farmers", Farmer,
    ("id", "name", "phone", "state", "district", "crops", "land_acres", "category", "language", "documents",
     "created_at"),
    ("crops", "documents"),
)
RUNS = TableSpec(
    "runs", RunRecord,
    ("id", "kind", "status", "target", "streaming_url", "video_url", "result", "error", "steps",
     "cost_credits", "mode", "created_at", "updated_at"),
    ("result", "error"),
)
ALERTS = TableSpec(
    "alerts", Alert,
    ("id", "farmer_id", "type", "title", "detail", "source_url", "evidence", "claim_id", "created_at"),
    ("evidence",),
)
LEDGER = TableSpec(
    "ledger", LedgerEntry,
    ("id", "farmer_id", "kind", "amount_rs", "formula", "confirmed", "created_at"),
)
TICKETS = TableSpec(
    "tickets", Ticket,
    ("id", "farmer_id", "intent", "query", "reason", "status", "created_at"),
)

SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS farmers (
    id TEXT PRIMARY KEY, name TEXT NOT NULL, phone TEXT, state TEXT NOT NULL, district TEXT NOT NULL,
    crops TEXT NOT NULL, land_acres REAL NOT NULL, category TEXT NOT NULL, language TEXT NOT NULL,
    documents TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY, kind TEXT NOT NULL, status TEXT NOT NULL, target TEXT NOT NULL,
    streaming_url TEXT, video_url TEXT, result TEXT, error TEXT, steps INTEGER, cost_credits REAL, mode TEXT NOT NULL,
    created_at TEXT NOT NULL, updated_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS alerts (
    id TEXT PRIMARY KEY, farmer_id TEXT, type TEXT NOT NULL, title TEXT NOT NULL, detail TEXT NOT NULL,
    source_url TEXT NOT NULL, evidence TEXT NOT NULL, claim_id TEXT, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ledger (
    id TEXT PRIMARY KEY, farmer_id TEXT NOT NULL, kind TEXT NOT NULL, amount_rs REAL NOT NULL,
    formula TEXT NOT NULL, confirmed INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tickets (
    id TEXT PRIMARY KEY, farmer_id TEXT, intent TEXT NOT NULL, query TEXT NOT NULL, reason TEXT NOT NULL,
    status TEXT NOT NULL, created_at TEXT NOT NULL);
"""


def _newest_first(rows: list[M]) -> list[M]:
    return sorted(rows, key=lambda r: r.created_at, reverse=True)  # type: ignore[attr-defined]


class Repository(ABC):
    # --- primitives a backend implements ----------------------------------------------------------------
    @abstractmethod
    def _put(self, spec: TableSpec, model: BaseModel) -> None: ...

    @abstractmethod
    def _get(self, spec: TableSpec, row_id: str) -> BaseModel | None: ...

    @abstractmethod
    def _all(self, spec: TableSpec) -> list[Any]: ...

    # --- farmers ----------------------------------------------------------------------------------------
    def upsert_farmer(self, farmer: Farmer) -> Farmer:
        self._put(FARMERS, farmer)
        return farmer

    def get_farmer(self, farmer_id: str) -> Farmer | None:
        return self._get(FARMERS, farmer_id)  # type: ignore[return-value]

    def list_farmers(self) -> list[Farmer]:
        return sorted(self._all(FARMERS), key=lambda f: f.id)

    # --- runs -------------------------------------------------------------------------------------------
    def save_run(self, run: RunRecord) -> RunRecord:
        self._put(RUNS, run)
        return run

    def get_run(self, run_id: str) -> RunRecord | None:
        return self._get(RUNS, run_id)  # type: ignore[return-value]

    def update_run(self, run_id: str, **fields: Any) -> RunRecord:
        run = self.get_run(run_id)
        if run is None:
            raise KeyError(run_id)
        run = run.model_copy(update={**fields, "updated_at": now()})
        self._put(RUNS, run)
        return run

    def list_runs(self) -> list[RunRecord]:
        return _newest_first(self._all(RUNS))

    # --- alerts -----------------------------------------------------------------------------------------
    def add_alert(self, alert: Alert) -> Alert:
        self._put(ALERTS, alert)
        return alert

    def list_alerts(self, farmer_id: str | None = None) -> list[Alert]:
        rows = self._all(ALERTS)
        if farmer_id:  # an alert with no farmer is area-wide and is shown to everyone
            rows = [a for a in rows if a.farmer_id in (None, farmer_id)]
        return _newest_first(rows)

    # --- ledger -----------------------------------------------------------------------------------------
    def add_ledger(self, entry: LedgerEntry) -> LedgerEntry:
        self._put(LEDGER, entry)
        return entry

    def confirm_ledger(self, entry_id: str) -> LedgerEntry:
        entry = self._get(LEDGER, entry_id)
        if entry is None:
            raise KeyError(entry_id)
        entry = entry.model_copy(update={"confirmed": True})  # type: ignore[attr-defined]
        self._put(LEDGER, entry)
        return entry  # type: ignore[return-value]

    def list_ledger(self, farmer_id: str | None = None) -> list[LedgerEntry]:
        rows = self._all(LEDGER)
        if farmer_id:
            rows = [e for e in rows if e.farmer_id == farmer_id]
        return _newest_first(rows)

    # --- tickets ----------------------------------------------------------------------------------------
    def create_ticket(self, ticket: Ticket) -> Ticket:
        self._put(TICKETS, ticket)
        return ticket

    def get_ticket(self, ticket_id: str) -> Ticket | None:
        return self._get(TICKETS, ticket_id)  # type: ignore[return-value]

    def list_tickets(self) -> list[Ticket]:
        return _newest_first(self._all(TICKETS))


class SqliteRepository(Repository):
    def __init__(self, path: str | Any) -> None:
        self.path = str(path)
        with self._conn() as conn:
            conn.executescript(SQLITE_SCHEMA)

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        return conn

    def _put(self, spec: TableSpec, model: BaseModel) -> None:
        data = model.model_dump(mode="json")
        values = [
            json.dumps(data[c]) if c in spec.json_columns else data[c] for c in spec.columns
        ]
        marks = ", ".join("?" for _ in spec.columns)
        sql = f"INSERT OR REPLACE INTO {spec.name} ({', '.join(spec.columns)}) VALUES ({marks})"
        conn = self._conn()
        try:
            with conn:
                conn.execute(sql, values)
        finally:
            conn.close()

    def _row(self, spec: TableSpec, row: sqlite3.Row) -> BaseModel:
        data = dict(row)
        for c in spec.json_columns:
            if data[c] is not None:
                data[c] = json.loads(data[c])
        return spec.model.model_validate(data)

    def _get(self, spec: TableSpec, row_id: str) -> BaseModel | None:
        conn = self._conn()
        try:
            row = conn.execute(f"SELECT * FROM {spec.name} WHERE id = ?", (row_id,)).fetchone()
        finally:
            conn.close()
        return self._row(spec, row) if row else None

    def _all(self, spec: TableSpec) -> list[Any]:
        conn = self._conn()
        try:
            rows = conn.execute(f"SELECT * FROM {spec.name}").fetchall()
        finally:
            conn.close()
        return [self._row(spec, r) for r in rows]


class SupabaseRepository(Repository):
    """Supabase through its PostgREST API (no SDK). Create the tables with docs/supabase.sql first."""

    def __init__(self, url: str, key: str, transport: httpx.BaseTransport | None = None) -> None:
        if not url or not key:
            raise ValueError("DB_BACKEND=supabase needs SUPABASE_URL and SUPABASE_KEY")
        self._client = httpx.Client(
            base_url=f"{url.rstrip('/')}/rest/v1",
            headers={"apikey": key, "Authorization": f"Bearer {key}"},
            timeout=15,
            transport=transport,
        )

    def _put(self, spec: TableSpec, model: BaseModel) -> None:
        r = self._client.post(
            f"/{spec.name}",
            params={"on_conflict": "id"},
            headers={"Prefer": "resolution=merge-duplicates,return=minimal"},
            json=model.model_dump(mode="json"),
        )
        r.raise_for_status()

    def _get(self, spec: TableSpec, row_id: str) -> BaseModel | None:
        r = self._client.get(f"/{spec.name}", params={"id": f"eq.{row_id}", "select": "*"})
        r.raise_for_status()
        rows = r.json()
        return spec.model.model_validate(rows[0]) if rows else None

    def _all(self, spec: TableSpec) -> list[Any]:
        r = self._client.get(f"/{spec.name}", params={"select": "*"})
        r.raise_for_status()
        return [spec.model.model_validate(row) for row in r.json()]


def make_repository(settings: Settings) -> Repository:
    if settings.db_backend == "supabase":
        return SupabaseRepository(settings.supabase_url, settings.supabase_key)
    settings.sqlite_path.parent.mkdir(parents=True, exist_ok=True)
    return SqliteRepository(settings.sqlite_path)
