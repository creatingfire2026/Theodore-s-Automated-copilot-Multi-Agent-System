"""Append-only, signed, hash-chained, anchored store of protected A7 dissents (F34 fix).

Sentinel queries this store itself, so a caller can no longer bypass a protected
dissent by omitting ``protected_dissent_id``.

Layers (every one is re-checked on every read; any failure raises DissentStoreError,
which Sentinel maps to HUMAN_REVIEW):
1. SQLite BEFORE UPDATE/DELETE triggers abort in-place edits (stops mistakes only).
2. Hash chain: ``row_hash = sha256(canonical_row + prev_hash)``; seq must be 1..n.
3. Signatures: every ``dissent`` row is Ed25519-signed by the A7 key; every
   ``receipt`` row is Ed25519-signed by the human key and bound to the dissent row hash.
4. Signed head anchor: after each append a separate file (outside the db
   directory) records ``(count, head row_hash)`` signed by A7 or the human key.
   The store must equal or extend the anchor, so truncating the newest rows or
   rewriting the chain is detected.

Remaining limit: an attacker who restores an OLDER db together with its OLDER
anchor file (a consistent rollback) is not detected, and anyone holding a
private key can sign as that role.

Dependency: ``cryptography`` (Ed25519).
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import tempfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from aip001_council import may_file_protected_dissent
from dissent_witness import HttpDissentWitness

GENESIS_HASH = "0" * 64
ENV_DB = "SENTINEL_DISSENT_DB"
ENV_PUBKEY = "SENTINEL_HUMAN_PUBKEY"
ENV_A7_PUBKEY = "SENTINEL_A7_PUBKEY"
ENV_ANCHOR = "SENTINEL_DISSENT_ANCHOR"
ENV_WITNESS_URL = "SENTINEL_DISSENT_WITNESS_URL"
ENV_WITNESS_PUBKEY = "SENTINEL_DISSENT_WITNESS_PUBKEY"
ENV_REQUIRE_WITNESS = "SENTINEL_REQUIRE_DISSENT_WITNESS"
ANCHOR_SIGNERS = ("A7", "human")
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


def now_ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def compute_row_hash(row: dict, prev_hash: str) -> str:
    content = {k: row[k] for k in ROW_FIELDS}
    return hashlib.sha256(_canonical(content) + prev_hash.encode("ascii")).hexdigest()


def dissent_payload(dissent_id: str, target: str, reason: str, author: str, ts: str) -> bytes:
    """Exact bytes A7 signs to file a protected dissent."""
    return _canonical({"kind": "dissent", "dissent_id": dissent_id, "target": target,
                       "reason": reason, "author": author, "ts": ts})


RECEIPT_FIELDS = ("kind", "dissent_id", "dissent_row_hash", "target", "reason", "author", "ts")


def receipt_payload(dissent_id: str, dissent_row_hash: str, target: str, reason: str, author: str, ts: str) -> bytes:
    """Exact bytes a human signs to clear one specific dissent row."""
    return _canonical({
        "kind": "receipt", "dissent_id": dissent_id, "dissent_row_hash": dissent_row_hash,
        "target": target, "reason": reason, "author": author, "ts": ts,
    })


def parse_receipt_payload(payload_bytes: bytes) -> dict[str, str]:
    """Decode and strictly validate canonical receipt payload bytes."""
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise DissentWriteRejected(f"receipt payload is not valid UTF-8 JSON: {exc.__class__.__name__}") from None
    if not isinstance(data, dict) or set(data) != set(RECEIPT_FIELDS):
        raise DissentWriteRejected("receipt payload has unexpected or missing fields")
    if not all(isinstance(data[k], str) for k in RECEIPT_FIELDS) or data["kind"] != "receipt":
        raise DissentWriteRejected("receipt payload fields must be strings with kind='receipt'")
    canonical = receipt_payload(
        data["dissent_id"], data["dissent_row_hash"], data["target"],
        data["reason"], data["author"], data["ts"],
    )
    if payload_bytes != canonical:
        raise DissentWriteRejected("receipt payload is not canonical JSON")
    return data


def anchor_payload(count: int, head_hash: str, ts: str, signer: str) -> bytes:
    return _canonical({"kind": "anchor", "count": count, "head_hash": head_hash, "ts": ts, "signer": signer})


def sign_b64(private_key, payload: bytes) -> str:
    return base64.b64encode(private_key.sign(payload)).decode("ascii")


def _load_public_key(path, label: str):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    from cryptography.hazmat.primitives.serialization import load_pem_public_key

    if not path:
        raise DissentStoreError(f"no {label} public key configured")
    try:
        pem_bytes = Path(path).expanduser().read_bytes().strip().replace(b"\r\n", b"\n")
        key = load_pem_public_key(pem_bytes)
    except Exception as exc:  # noqa: BLE001 - any failure is a config failure
        raise DissentStoreError(f"{label} public key unreadable: {exc.__class__.__name__}") from None
    if not isinstance(key, Ed25519PublicKey):
        raise DissentStoreError(f"{label} public key is not Ed25519")
    return key


def load_public_key(path):
    return _load_public_key(path, "human")


def load_private_key(path, passphrase: bytes | None = None):
    """Load an Ed25519 PEM private key; refuses group/world-readable files on POSIX."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import load_pem_private_key

    p = Path(path).expanduser()
    if os.name == "posix" and p.stat().st_mode & 0o077:
        raise DissentStoreError(f"private key {p} is readable by others; chmod 600 it")
    try:
        key = load_pem_private_key(p.read_bytes(), password=passphrase)
    except (TypeError, ValueError) as exc:
        raise DissentStoreError(f"private key {p} could not be loaded (wrong or missing passphrase?): "
                                f"{exc.__class__.__name__}") from None
    if not isinstance(key, Ed25519PrivateKey):
        raise DissentStoreError("private key is not Ed25519")
    return key


def _public_bytes(key) -> bytes:
    from cryptography.hazmat.primitives import serialization
    return key.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def public_key_info(key) -> dict[str, str]:
    """Return raw 32-byte encodings and SHA-256 fingerprints for an Ed25519 public key."""
    raw = _public_bytes(key)
    digest = hashlib.sha256(raw).digest()
    return {
        "raw_hex": raw.hex(),
        "raw_b64": base64.b64encode(raw).decode("ascii"),
        "sha256_hex": digest.hex(),
        "fingerprint": "SHA256:" + base64.b64encode(digest).decode("ascii").rstrip("="),
    }


def _verify(public_key, signature_b64: str, payload: bytes) -> bool:
    from cryptography.exceptions import InvalidSignature

    try:
        public_key.verify(base64.b64decode(signature_b64, validate=True), payload)
        return True
    except (InvalidSignature, ValueError, TypeError):
        return False


def _write_private_file(path: Path, data: bytes) -> None:
    """Atomic write with 0600 permissions."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise


class DissentStore:
    def __init__(self, path, human_pubkey_path, a7_pubkey_path=None, anchor_path=None,
                 *, witness=None, require_witness: bool | None = None) -> None:
        self.path = Path(path)
        self.human_pubkey_path = Path(human_pubkey_path) if human_pubkey_path else None
        self.a7_pubkey_path = Path(a7_pubkey_path) if a7_pubkey_path else None
        self.anchor_path = Path(anchor_path) if anchor_path else None
        self._witness_config_error = None
        if witness is None:
            witness_url = os.environ.get(ENV_WITNESS_URL)
            witness_pubkey = os.environ.get(ENV_WITNESS_PUBKEY)
            if bool(witness_url) != bool(witness_pubkey):
                self._witness_config_error = f"{ENV_WITNESS_URL} and {ENV_WITNESS_PUBKEY} must be configured together"
            elif witness_url and witness_pubkey:
                try:
                    witness = HttpDissentWitness(witness_url, witness_pubkey)
                except Exception as exc:  # noqa: BLE001 - witness configuration must fail closed
                    self._witness_config_error = f"witness configuration invalid: {exc.__class__.__name__}"
        self.witness = witness
        if require_witness is None:
            require_witness = os.environ.get(ENV_REQUIRE_WITNESS, "") == "1"
        self.require_witness = bool(require_witness)

    @classmethod
    def from_env(cls) -> "DissentStore | None":
        db = os.environ.get(ENV_DB)
        if not db:
            return None
        return cls(db, os.environ.get(ENV_PUBKEY), os.environ.get(ENV_A7_PUBKEY), os.environ.get(ENV_ANCHOR))

    # -- keys / anchor -------------------------------------------------------
    def _keys(self) -> dict:
        return {"human": _load_public_key(self.human_pubkey_path, "human"),
                "A7": _load_public_key(self.a7_pubkey_path, "A7")}

    def _check_anchor_location(self) -> Path:
        if self.anchor_path is None:
            raise DissentStoreError(f"no head anchor configured ({ENV_ANCHOR})")
        if self.anchor_path.resolve().parent == self.path.resolve().parent:
            raise DissentStoreError("head anchor must live outside the dissent store directory")
        return self.anchor_path

    def _read_anchor(self, keys: dict) -> tuple[int, str]:
        path = self._check_anchor_location()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            count, head, ts, signer, sig = (data["count"], data["head_hash"], data["ts"],
                                            data["signer"], data["signature"])
        except FileNotFoundError:
            raise DissentStoreError(f"head anchor missing: {path}") from None
        except (OSError, ValueError, KeyError, TypeError) as exc:
            raise DissentStoreError(f"head anchor unreadable: {exc.__class__.__name__}") from None
        if (not isinstance(count, int) or isinstance(count, bool) or count < 0
                or not isinstance(head, str) or signer not in ANCHOR_SIGNERS):
            raise DissentStoreError("head anchor malformed")
        if not _verify(keys[signer], sig, anchor_payload(count, head, ts, signer)):
            raise DissentStoreError("head anchor signature invalid")
        return count, head

    def _write_anchor(self, count: int, head: str, signer: tuple[str, object]) -> None:
        role, key = signer
        ts = now_ts()
        body = {"count": count, "head_hash": head, "ts": ts, "signer": role,
                "signature": sign_b64(key, anchor_payload(count, head, ts, role))}
        _write_private_file(self._check_anchor_location(), _canonical(body) + b"\n")

    def _check_signer(self, signer, keys: dict) -> None:
        if not (isinstance(signer, tuple) and len(signer) == 2 and signer[0] in ANCHOR_SIGNERS):
            raise DissentWriteRejected("anchor signer must be ('A7'|'human', private_key)")
        if _public_bytes(signer[1].public_key()) != _public_bytes(keys[signer[0]]):
            raise DissentWriteRejected(f"anchor signing key does not match the configured {signer[0]} public key")

    # -- setup ---------------------------------------------------------------
    def initialize(self, anchor_signer: tuple[str, object]) -> None:
        """Create the db (idempotent) and the genesis head anchor if none exists."""
        keys = self._keys()
        self._check_signer(anchor_signer, keys)
        self._check_anchor_location()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path)
        try:
            conn.executescript(_SCHEMA)
        finally:
            conn.close()
        if os.name == "posix":
            os.chmod(self.path, 0o600)
        if not self.anchor_path.exists():
            if self.head_unanchored()[0] != 0:
                raise DissentStoreError("refusing to anchor a non-empty store with no prior anchor")
            self._write_anchor(0, GENESIS_HASH, anchor_signer)
        self.head()  # full verification

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

    def _rows(self, conn) -> list[dict]:
        try:
            triggers = {r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='dissent_log'")}
            if not REQUIRED_TRIGGERS <= triggers:
                raise DissentStoreError("append-only triggers missing")
            cur = conn.execute(
                "SELECT seq, kind, dissent_id, target, reason, author, ts, dissent_row_hash, signature,"
                " prev_hash, row_hash FROM dissent_log ORDER BY seq")
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]
        except sqlite3.Error as exc:
            raise DissentStoreError(f"dissent store unreadable: {exc}") from None

    def _read_verified(self, conn: sqlite3.Connection, keys: dict | None = None,
                       *, check_witness: bool = True) -> list[dict]:
        """Verify triggers, chain, signatures, local anchor, and optionally the remote witness."""
        keys = keys or self._keys()
        rows = self._rows(conn)
        prev = GENESIS_HASH
        dissents: dict[str, dict] = {}
        cleared_hashes: set[str] = set()
        for expected_seq, row in enumerate(rows, start=1):
            if row["seq"] != expected_seq:
                raise DissentStoreError(f"chain gap at seq {expected_seq} (row deleted or reordered)")
            if row["prev_hash"] != prev or compute_row_hash(row, prev) != row["row_hash"]:
                raise DissentStoreError(f"hash chain broken at seq {row['seq']}")
            if row["kind"] == "dissent":
                if row["dissent_id"] in dissents:
                    raise DissentStoreError(f"duplicate dissent ID at seq {row['seq']}")
                if not may_file_protected_dissent(row["author"]):
                    raise DissentStoreError(f"dissent seq {row['seq']} not authored by A7")
                payload = dissent_payload(row["dissent_id"], row["target"], row["reason"], row["author"], row["ts"])
                if not _verify(keys["A7"], row["signature"], payload):
                    raise DissentStoreError(f"dissent seq {row['seq']} has an invalid A7 signature")
                dissents[row["dissent_id"]] = row
            elif row["kind"] == "receipt":
                target = dissents.get(row["dissent_id"])
                if target is None or target["row_hash"] != row["dissent_row_hash"]:
                    raise DissentStoreError(f"receipt seq {row['seq']} references no earlier dissent")
                if row["dissent_row_hash"] in cleared_hashes:
                    raise DissentStoreError(f"duplicate receipt for dissent row at seq {row['seq']}")
                cleared_hashes.add(row["dissent_row_hash"])
                payload = receipt_payload(row["dissent_id"], row["dissent_row_hash"], row["target"],
                                          row["reason"], row["author"], row["ts"])
                if not _verify(keys["human"], row["signature"], payload):
                    raise DissentStoreError(f"receipt seq {row['seq']} has an invalid human signature")
            else:
                raise DissentStoreError(f"unknown row kind at seq {row['seq']}")
            prev = row["row_hash"]
        anchored_count, anchored_head = self._read_anchor(keys)
        if len(rows) < anchored_count:
            raise DissentStoreError(f"store truncated: {len(rows)} rows < anchored {anchored_count}")
        actual = rows[anchored_count - 1]["row_hash"] if anchored_count else GENESIS_HASH
        if actual != anchored_head:
            raise DissentStoreError(f"store diverges from signed head anchor at row {anchored_count} (rewritten)")
        latest_head = rows[-1]["row_hash"] if rows else GENESIS_HASH
        if check_witness:
            self._check_witness(len(rows), latest_head)
        return rows

    def sync_witness(self) -> tuple[int, str]:
        """Explicitly replay a locally valid suffix when a prior append committed but its witness call failed.

        This cannot repair rollback: the remote checkpoint must be an exact ancestor
        of the local verified chain. A remote-ahead or divergent state is rejected.
        """
        if self._witness_config_error:
            raise DissentStoreError(self._witness_config_error)
        if self.witness is None:
            raise DissentStoreError("independent dissent witness is not configured")
        conn = self._connect_ro()
        try:
            rows = self._read_verified(conn, check_witness=False)
        finally:
            conn.close()
        try:
            checkpoint = self.witness.checkpoint()
        except Exception as exc:  # noqa: BLE001 - recovery must not bypass witness availability
            raise DissentStoreError(f"cannot read independent witness: {exc.__class__.__name__}") from None
        remote_seq = checkpoint["seq"]
        if remote_seq > len(rows):
            raise DissentStoreError("witness is ahead of the local store; rollback or data loss suspected")
        local_prefix = rows[remote_seq - 1]["row_hash"] if remote_seq else GENESIS_HASH
        if checkpoint["head_hash"] != local_prefix:
            raise DissentStoreError("local chain diverges from the independent witness; refusing reconciliation")
        for row in rows[remote_seq:]:
            try:
                self.witness.advance(row)
            except Exception as exc:  # noqa: BLE001
                raise DissentStoreError(f"witness reconciliation stopped: {exc.__class__.__name__}") from None
        latest_head = rows[-1]["row_hash"] if rows else GENESIS_HASH
        self._check_witness(len(rows), latest_head)
        return len(rows), latest_head

    def _check_witness(self, seq: int, head_hash: str) -> None:
        if self._witness_config_error:
            raise DissentStoreError(self._witness_config_error)
        if self.witness is None:
            if self.require_witness:
                raise DissentStoreError("independent dissent witness required but not configured")
            return
        try:
            self.witness.assert_matches(seq, head_hash)
        except DissentStoreError:
            raise
        except Exception as exc:  # noqa: BLE001 - unavailable or malformed witness must fail closed
            raise DissentStoreError(f"independent dissent witness failed: {exc.__class__.__name__}") from None

    def _advance_witness(self, row: dict) -> None:
        self._check_witness(row["seq"] - 1, row["prev_hash"])
        if self.witness is None:
            return
        try:
            self.witness.advance(row)
            self._check_witness(row["seq"], row["row_hash"])
        except DissentStoreError:
            raise
        except Exception as exc:  # noqa: BLE001 - never report an unwitnessed append as complete
            raise DissentStoreError(
                f"local dissent append committed but witness advancement failed: {exc.__class__.__name__}"
            ) from None

    def _append(self, row: dict, anchor_signer) -> str:
        keys = self._keys()
        self._check_signer(anchor_signer, keys)
        if not self.path.is_file():
            raise DissentStoreError(f"dissent store missing: {self.path} (run init first)")
        conn = sqlite3.connect(self.path, isolation_level=None)
        try:
            conn.execute("BEGIN IMMEDIATE")
            rows = self._read_verified(conn, keys)
            prev = rows[-1]["row_hash"] if rows else GENESIS_HASH
            row = dict(row, seq=len(rows) + 1)
            row["prev_hash"] = prev
            row["row_hash"] = compute_row_hash(row, prev)
            conn.execute(
                "INSERT INTO dissent_log (seq, kind, dissent_id, target, reason, author, ts,"
                " dissent_row_hash, signature, prev_hash, row_hash) VALUES"
                " (:seq, :kind, :dissent_id, :target, :reason, :author, :ts, :dissent_row_hash,"
                " :signature, :prev_hash, :row_hash)", row)
            # Advance the signed anchor while BEGIN IMMEDIATE still holds the SQLite
            # writer lock. A second writer cannot commit a later row and then have
            # this writer overwrite its newer anchor with a stale one.
            #
            # Crash safety is fail-closed: a crash after the anchor write but before
            # COMMIT leaves the anchor ahead of the database, so readers reject the
            # store and require operator recovery rather than authorizing stale state.
            self._write_anchor(row["seq"], row["row_hash"], anchor_signer)
            conn.execute("COMMIT")
            # The remote monotonic witness is advanced only after the local row and
            # signed anchor commit. If this call fails, the local store is ahead and
            # every subsequent authorization fails closed until operator recovery.
            self._advance_witness(row)
            return row["row_hash"]
        except sqlite3.IntegrityError as exc:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise DissentWriteRejected(f"write rejected: {exc}") from None
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    # -- writers -------------------------------------------------------------
    def append_dissent(self, *, author: str, dissent_id: str, target: str, reason: str, ts: str,
                       signature_b64: str, anchor_signer) -> str:
        """Record a protected dissent. Must be authored by A7 and signed by the A7 key."""
        if not may_file_protected_dissent(author):
            raise DissentWriteRejected(f"only A7 may file a protected dissent (got {author!r})")
        if not (dissent_id and target and reason and reason.strip() and ts):
            raise DissentWriteRejected("dissent needs dissent_id, target, reason, and ts")
        if not signature_b64 or not _verify(self._keys()["A7"], signature_b64,
                                            dissent_payload(dissent_id, target, reason, author, ts)):
            raise DissentWriteRejected("dissent is unsigned or its signature does not verify against the A7 key")
        return self._append({"kind": "dissent", "dissent_id": dissent_id, "target": target,
                             "reason": reason, "author": author, "ts": ts,
                             "dissent_row_hash": "", "signature": signature_b64}, anchor_signer)

    def append_receipt(self, *, dissent_id: str, author: str, reason: str, ts: str, signature_b64: str,
                       anchor_signer) -> str:
        """Record a signed human clearing receipt. Signature must verify before it is written."""
        if not (author and reason and reason.strip()):
            raise DissentWriteRejected("receipt needs a human author and a justification")
        dissent = self.dissent(dissent_id)
        if dissent is None:
            raise DissentWriteRejected(f"no dissent {dissent_id!r} to clear")
        payload = receipt_payload(dissent_id, dissent.row_hash, dissent.target, reason, author, ts)
        if not _verify(self._keys()["human"], signature_b64, payload):
            raise DissentWriteRejected("receipt signature does not verify against the human public key")
        return self._append({"kind": "receipt", "dissent_id": dissent_id, "target": dissent.target,
                             "reason": reason, "author": author, "ts": ts,
                             "dissent_row_hash": dissent.row_hash, "signature": signature_b64}, anchor_signer)

    # -- readers -------------------------------------------------------------
    def _verified_rows(self) -> list[dict]:
        conn = self._connect_ro()
        try:
            return self._read_verified(conn)
        finally:
            conn.close()

    @staticmethod
    def _as_dissent(r: dict) -> Dissent:
        return Dissent(r["seq"], r["dissent_id"], r["target"], r["reason"], r["author"], r["ts"], r["row_hash"])

    def dissent(self, dissent_id: str) -> Dissent | None:
        for r in self._verified_rows():
            if r["kind"] == "dissent" and r["dissent_id"] == dissent_id:
                return self._as_dissent(r)
        return None

    def open_dissents(self) -> list[Dissent]:
        """Dissents with no valid later receipt. Raises DissentStoreError on any integrity problem."""
        rows = self._verified_rows()
        cleared = {r["dissent_row_hash"] for r in rows if r["kind"] == "receipt"}
        return [self._as_dissent(r) for r in rows
                if r["kind"] == "dissent" and r["row_hash"] not in cleared]

    def known_dissent_ids(self) -> set[str]:
        return {r["dissent_id"] for r in self._verified_rows() if r["kind"] == "dissent"}

    def head(self) -> tuple[int, str]:
        rows = self._verified_rows()
        return (len(rows), rows[-1]["row_hash"] if rows else GENESIS_HASH)

    def head_unanchored(self) -> tuple[int, str]:
        conn = self._connect_ro()
        try:
            rows = self._rows(conn)
        finally:
            conn.close()
        return (len(rows), rows[-1]["row_hash"] if rows else GENESIS_HASH)


def clear_dissent(store: DissentStore, human_key, *, dissent_id: str, human: str, reason: str) -> str:
    """Sign and append a human receipt; the human key also signs the new head anchor."""
    dissent = store.dissent(dissent_id)
    if dissent is None:
        raise DissentWriteRejected(f"no dissent {dissent_id!r}")
    ts = now_ts()
    sig = sign_b64(human_key, receipt_payload(dissent.dissent_id, dissent.row_hash, dissent.target, reason, human, ts))
    return store.append_receipt(dissent_id=dissent_id, author=human, reason=reason, ts=ts,
                                signature_b64=sig, anchor_signer=("human", human_key))


def clear_dissent_signed(store: DissentStore, *, dissent_id: str, human: str, reason: str, ts: str,
                         signature_b64: str, anchor_signer) -> str:
    """Append an externally signed human clearing receipt (e.g. signed offline on Magic via openssl)."""
    return store.append_receipt(dissent_id=dissent_id, author=human, reason=reason, ts=ts,
                                signature_b64=signature_b64, anchor_signer=anchor_signer)


def dissent_matches(dissent: Dissent, *, trace_id: str, intent: str, scope: list[str]) -> bool:
    """A dissent applies if its target is '*', the trace_id, the intent, or any scope entry (exact match)."""
    t = dissent.target
    return t == "*" or t == trace_id or t == intent or t in scope
