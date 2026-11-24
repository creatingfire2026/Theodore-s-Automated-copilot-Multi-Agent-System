"""Append-only, hash-chained store of protected A7 dissents (fix for audit finding F34).

Sentinel queries this store itself, so a caller can no longer bypass a protected
dissent by omitting ``protected_dissent_id``.

Guarantees (and their limits):
* SQLite BEFORE UPDATE/DELETE triggers abort in-place edits. They stop mistakes,
  not an attacker with write access to the file (who can drop them).
* Every row carries ``prev_hash`` and ``row_hash = sha256(canonical_row + prev_hash)``.
  Editing, deleting, or reordering a row breaks the chain on the next read.
  Limits: a hash chain has no secret, so (a) removing the newest rows (tail
  truncation) or (b) rewriting the whole chain consistently is NOT detected by
  the chain alone. Anchor ``head()`` externally if you need that.
* Only a ``receipt`` row whose Ed25519 signature verifies against the configured
  human public key clears a dissent. Receipts are re-verified on every read, so
  forging or editing one fails closed.
* Any read problem raises ``DissentStoreError``; Sentinel maps that to HUMAN_REVIEW.

Dependency: ``cryptography`` (Ed25519).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aip001_council import may_file_protected_dissent

GENESIS_HASH = "0" * 64
ENV_DB = "SENTINEL_DISSENT_DB"
ENV_PUBKEY = "SENTINEL_HUMAN_PUBKEY"
REQUIRED_TRIGGERS = frozenset({"dissent_log_no_update", "dissent_log_no_delete"})
ROW_FIELDS = ("seq", "kind", "dissent_id", "target", "reason", "author", "ts", "dissent_row_hash", "signature")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS dissent_log (
    seq INTEGER PRIMARY KEY,
    kind TEXT NOT NULL CHECK (kind IN ('dissent', 'receipt')),
    dissent_id TEXT NOT NULL,
    target TEXT NOT NULL,
    reason TEXT NOT NULL,
    author TEXT NOT NULL,
    ts TEXT NOT NULL,
    dissent_row_hash TEXT NOT NULL DEFAULT '',
    signature TEXT NOT NULL DEFAULT '',
    prev_hash TEXT NOT NULL,
    row_hash TEXT NOT NULL UNIQUE
);
CREATE UNIQUE INDEX IF NOT EXISTS dissent_log_one_dissent_per_id
    ON dissent_log (dissent_id) WHERE kind = 'dissent';
CREATE TRIGGER IF NOT EXISTS dissent_log_no_update BEFORE UPDATE ON dissent_log
    BEGIN SELECT RAISE(ABORT, 'dissent_log is append-only'); END;
CREATE TRIGGER IF NOT EXISTS dissent_log_no_delete BEFORE DELETE ON dissent_log
    BEGIN SELECT RAISE(ABORT, 'dissent_log is append-only'); END;
"""


class DissentStoreError(Exception):
    """Store missing, unreadable, corrupt, tampered, or misconfigured. Callers must fail closed."""


class DissentWriteRejected(DissentStoreError):
    """A write was refused (wrong author, bad signature, unknown dissent, ...)."""


@dataclass(frozen=True)
class Dissent:
    seq: int
    dissent_id: str
    target: str
    reason: str
    author: str
    ts: str
    row_hash: str


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def compute_row_hash(row: dict, prev_hash: str) -> str:
    content = {k: row[k] for k in ROW_FIELDS}
    return hashlib.sha256(_canonical(content) + prev_hash.encode("ascii")).hexdigest()


def receipt_payload(dissent_id: str, dissent_row_hash: str, target: str, reason: str, author: str, ts: str) -> bytes:
    """Exact bytes a human signs to clear one specific dissent row."""
    return _canonical({
        "kind": "receipt", "dissent_id": dissent_id, "dissent_row_hash": dissent_row_hash,
        "target": target, "reason": reason, "author": author, "ts": ts,
    })


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def load_public_key(path: str | os.PathLike):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    try:
        key = load_pem_public_key(Path(path).read_bytes())
    except Exception as exc:  # noqa: BLE001 - any failure is a config failure
        raise DissentStoreError(f"human public key unreadable: {exc.__class__.__name__}") from None
    if not isinstance(key, Ed25519PublicKey):
        raise DissentStoreError("human public key is not Ed25519")
    return key


def _verify_signature(public_key, signature_b64: str, payload: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature

    try:
        public_key.verify(base64.b64decode(signature_b64, validate=True), payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


class DissentStore:
    def __init__(self, path: str | os.PathLike, human_pubkey_path: str | os.PathLike | None) -> None:
        self.path = Path(path)
        self.human_pubkey_path = Path(human_pubkey_path) if human_pubkey_path else None

    @classmethod
    def from_env(cls) -> "DissentStore | None":
        db = os.environ.get(ENV_DB)
        return cls(db, os.environ.get(ENV_PUBKEY)) if db else None

    # -- setup ---------------------------------------------------------------
    def initialize(self) -> None:
        """Create the database file and schema (idempotent)."""
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()

    # -- low level -----------------------------------------------------------
    def _connect_ro(self) -> sqlite3.Connection:
        if not self.path.is_file():
            raise DissentStoreError(f"dissent store missing: {self.path}")
        try:
            conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
            conn.execute("SELECT 1 FROM dissent_log LIMIT 1").fetchall()
        except sqlite3.Error as exc:
            raise DissentStoreError(f"dissent store unreadable: {exc}") from None
        return conn

    def _public_key(self):
        if self.human_pubkey_path is None:
            raise DissentStoreError(f"no human public key configured ({ENV_PUBKEY})")
        return load_public_key(self.human_pubkey_path)

    def _read_verified(self, conn: sqlite3.Connection) -> list[dict]:
        """Return all rows after verifying triggers, chain, and every receipt signature."""
        try:
            triggers = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='dissent_log'")}
            if not REQUIRED_TRIGGERS <= triggers:
                raise DissentStoreError("append-only triggers missing")
            cur = conn.execute(
                "SELECT seq, kind, dissent_id, target, reason, author, ts, dissent_row_hash, signature,"
                " prev_hash, row_hash FROM dissent_log ORDER BY seq")
            cols = [d[0] for d in cur.description]
            rows = [dict(zip(cols, r)) for r in cur.fetchall()]
        except sqlite3.Error as exc:
            raise DissentStoreError(f"dissent store unreadable: {exc}") from None

        public_key = self._public_key()
        prev = GENESIS_HASH
        dissents: dict[str, dict] = {}
        for expected_seq, row in enumerate(rows, start=1):
            if row["seq"] != expected_seq:
                raise DissentStoreError(f"chain gap at seq {expected_seq} (row deleted or reordered)")
            if row["prev_hash"] != prev or compute_row_hash(row, prev) != row["row_hash"]:
                raise DissentStoreError(f"hash chain broken at seq {row['seq']}")
            if row["kind"] == "dissent":
                if not may_file_protected_dissent(row["author"]):
                    raise DissentStoreError(f"dissent seq {row['seq']} not authored by A7")
                dissents[row["dissent_id"]] = row
            elif row["kind"] == "receipt":
                target = dissents.get(row["dissent_id"])
                if target is None or target["row_hash"] != row["dissent_row_hash"]:
                    raise DissentStoreError(f"receipt seq {row['seq']} references no earlier dissent")
                payload = receipt_payload(row["dissent_id"], row["dissent_row_hash"], row["target"],
                                          row["reason"], row["author"], row["ts"])
                if not _verify_signature(public_key, row["signature"], payload):
                    raise DissentStoreError(f"receipt seq {row['seq']} has an invalid human signature")
            else:
                raise DissentStoreError(f"unknown row kind at seq {row['seq']}")
            prev = row["row_hash"]
        return rows

    def _append(self, row: dict) -> str:
        if not self.path.is_file():
            raise DissentStoreError(f"dissent store missing: {self.path} (run init first)")
        conn = sqlite3.connect(self.path, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = self._read_verified(conn)
            prev = rows[-1]["row_hash"] if rows else GENESIS_HASH
            row = dict(row, seq=len(rows) + 1)
            row["prev_hash"] = prev
            row["row_hash"] = compute_row_hash(row, prev)
            conn.execute(
                "INSERT INTO dissent_log (seq, kind, dissent_id, target, reason, author, ts,"
                " dissent_row_hash, signature, prev_hash, row_hash) VALUES"
                " (:seq, :kind, :dissent_id, :target, :reason, :author, :ts, :dissent_row_hash,"
                " :signature, :prev_hash, :row_hash)", row)
            conn.execute("COMMIT")
            return row["row_hash"]
        except sqlite3.IntegrityError as exc:
            conn.execute("ROLLBACK")
            raise DissentWriteRejected(f"write rejected: {exc}") from None
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # -- writers -------------------------------------------------------------
    def append_dissent(self, *, author: str, dissent_id: str, target: str, reason: str) -> str:
        """Record a protected dissent. Only council node A7 may write one."""
        if not may_file_protected_dissent(author):
            raise DissentWriteRejected(f"only A7 may file a protected dissent (got {author!r})")
        if not (dissent_id and target and reason and reason.strip()):
            raise DissentWriteRejected("dissent needs dissent_id, target, and reason")
        return self._append({"kind": "dissent", "dissent_id": dissent_id, "target": target,
                             "reason": reason, "author": author, "ts": _now(),
                             "dissent_row_hash": "", "signature": ""})

    def dissent(self, dissent_id: str) -> Dissent | None:
        conn = self._connect_ro()
        try:
            for row in self._read_verified(conn):
                if row["kind"] == "dissent" and row["dissent_id"] == dissent_id:
                    return Dissent(row["seq"], row["dissent_id"], row["target"], row["reason"],
                                   row["author"], row["ts"], row["row_hash"])
        finally:
            conn.close()
        return None

    def append_receipt(self, *, dissent_id: str, author: str, reason: str, ts: str, signature_b64: str) -> str:
        """Record a signed human clearing receipt. Signature must verify before it is written."""
        if not (author and reason and reason.strip()):
            raise DissentWriteRejected("receipt needs a human author and a justification")
        dissent = self.dissent(dissent_id)
        if dissent is None:
            raise DissentWriteRejected(f"no dissent {dissent_id!r} to clear")
        payload = receipt_payload(dissent_id, dissent.row_hash, dissent.target, reason, author, ts)
        if not _verify_signature(self._public_key(), signature_b64, payload):
            raise DissentWriteRejected("receipt signature does not verify against the human public key")
        return self._append({"kind": "receipt", "dissent_id": dissent_id, "target": dissent.target,
                             "reason": reason, "author": author, "ts": ts,
                             "dissent_row_hash": dissent.row_hash, "signature": signature_b64})

    # -- readers -------------------------------------------------------------
    def open_dissents(self) -> list[Dissent]:
        """Dissents with no valid later receipt. Raises DissentStoreError on any integrity problem."""
        conn = self._connect_ro()
        try:
            rows = self._read_verified(conn)
        finally:
            conn.close()
        cleared = {r["dissent_id"] for r in rows if r["kind"] == "receipt"}
        return [Dissent(r["seq"], r["dissent_id"], r["target"], r["reason"], r["author"], r["ts"], r["row_hash"])
                for r in rows if r["kind"] == "dissent" and r["dissent_id"] not in cleared]

    def known_dissent_ids(self) -> set[str]:
        conn = self._connect_ro()
        try:
            return {r["dissent_id"] for r in self._read_verified(conn) if r["kind"] == "dissent"}
        finally:
            conn.close()

    def head(self) -> tuple[int, str]:
        """(row count, newest row_hash): anchor this externally to detect tail truncation."""
        conn = self._connect_ro()
        try:
            rows = self._read_verified(conn)
        finally:
            conn.close()
        return (len(rows), rows[-1]["row_hash"] if rows else GENESIS_HASH)


def dissent_matches(dissent: Dissent, *, trace_id: str, intent: str, scope: list[str]) -> bool:
    """A dissent applies if its target is '*', the trace_id, the intent, or any scope entry (exact match)."""
    t = dissent.target
    return t == "*" or t == trace_id or t == intent or t in scope
