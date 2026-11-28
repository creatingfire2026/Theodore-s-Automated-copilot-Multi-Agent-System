"""Append-only, hash-chained audit log for the Sentinel MCP gateway (B4).

Each row: ``row_hash = sha256(canonical({seq, kind, ts, body}) + prev_hash)``; seq must be 1..n
and the chain is re-verified on every read and before every append. SQLite triggers abort
in-place UPDATE/DELETE (stops mistakes, not a determined attacker with file access).

Limits (honest): rows are NOT signed and there is no external head anchor or witness yet, so
someone with write access to the file can rebuild a consistent chain or truncate it. The
protected A7 dissent store (dissent_store.py) remains the signed + anchored log.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from dissent_store import GENESIS_HASH, _canonical, now_ts

ENV_AUDIT_DB = "SENTINEL_MCP_AUDIT_DB"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_log (
    seq INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    ts TEXT NOT NULL,
    body TEXT NOT NULL,
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL UNIQUE
);
CREATE TRIGGER IF NOT EXISTS audit_log_no_update BEFORE UPDATE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS audit_log_no_delete BEFORE DELETE ON audit_log
    BEGIN SELECT RAISE(ABORT, 'audit_log is append-only'); END;
"""


class AuditLogError(Exception):
    """Audit log missing, unreadable, or its hash chain does not verify. Callers must fail closed."""


def audit_row_hash(seq: int, kind: str, ts: str, body: str, prev_hash: str) -> str:
    content = _canonical({"seq": seq, "kind": kind, "ts": ts, "body": body})
    return hashlib.sha256(content + prev_hash.encode("ascii")).hexdigest()


class AuditLog:
    def __init__(self, path) -> None:
        if not path:
            raise AuditLogError("no audit log path configured")
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self.path.exists():
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
            conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            conn.row_factory = sqlite3.Row
            conn.executescript(_SCHEMA)
            return conn
        except (OSError, sqlite3.Error) as exc:
            raise AuditLogError(f"audit log unusable: {exc.__class__.__name__}") from None

    @staticmethod
    def _verified(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        rows = [dict(r) for r in conn.execute("SELECT * FROM audit_log ORDER BY seq")]
        prev = GENESIS_HASH
        for i, r in enumerate(rows, start=1):
            if r["seq"] != i:
                raise AuditLogError(f"audit log sequence gap at seq {r['seq']} (expected {i})")
            if r["prev_hash"] != prev or audit_row_hash(r["seq"], r["kind"], r["ts"], r["body"], prev) != r["row_hash"]:
                raise AuditLogError(f"audit log hash chain broken at seq {i}")
            prev = r["row_hash"]
        return rows

    def append(self, kind: str, body: dict[str, Any]) -> str:
        if not kind or not isinstance(body, dict):
            raise AuditLogError("audit entry needs a kind and a dict body")
        body_text = _canonical(body).decode("utf-8")
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = self._verified(conn)
            seq = len(rows) + 1
            prev = rows[-1]["row_hash"] if rows else GENESIS_HASH
            ts = now_ts()
            row_hash = audit_row_hash(seq, kind, ts, body_text, prev)
            conn.execute(
                "INSERT INTO audit_log (seq, kind, ts, body, prev_hash, row_hash) VALUES (?, ?, ?, ?, ?, ?)",
                (seq, kind, ts, body_text, prev, row_hash),
            )
            conn.execute("COMMIT")
            return row_hash
        except AuditLogError:
            conn.execute("ROLLBACK")
            raise
        except sqlite3.Error as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise AuditLogError(f"audit append failed: {exc.__class__.__name__}") from None
        finally:
            conn.close()

    def entries(self, kind: str | None = None) -> list[dict[str, Any]]:
        conn = self._connect()
        try:
            rows = self._verified(conn)
        finally:
            conn.close()
        out = []
        for r in rows:
            if kind is None or r["kind"] == kind:
                out.append({"seq": r["seq"], "kind": r["kind"], "ts": r["ts"],
                            "body": json.loads(r["body"]), "row_hash": r["row_hash"]})
        return out

    def head(self) -> tuple[int, str]:
        conn = self._connect()
        try:
            rows = self._verified(conn)
        finally:
            conn.close()
        return (len(rows), rows[-1]["row_hash"] if rows else GENESIS_HASH)
