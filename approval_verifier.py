"""B3: concrete Ed25519 human-approval verifier for Sentinel's ``human_approval_verifier`` hook.

The human signs the exact canonical JSON bytes of an approval payload:

    {"action_id", "args_sha256", "aud", "expires_at", "human_id", "intent", "kind",
     "nonce", "risk", "scope", "tool", "trace_id", "v"}

serialised with ``sort_keys=True, separators=(",", ":"), ensure_ascii=False`` (the same
canonical form the dissent store uses). Because it is plain bytes, the payload can be
base64'd and signed offline with ``magic_sign_receipt.sh`` (``openssl pkeyutl -sign -rawin``),
exactly like dissent receipts.

``Ed25519ApprovalVerifier.check`` rejects (fail closed, never raises) on:
missing/invalid base64, non-canonical or malformed payload, unknown human, bad signature,
wrong key, any field not bound to the ActionRequest/HumanApproval (audience, trace, intent,
scope, tool, args hash, risk, action id, expiry), expired or too-far-future expiry, and a
replayed nonce. Nonces are persisted in an append-only SQLite table and consumed only
after every other check passes.

Dependency: ``cryptography`` (Ed25519).
"""
from __future__ import annotations

import base64
import binascii
import hashlib
import json
import logging
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dissent_store import _canonical, _load_public_key, _verify

logger = logging.getLogger("sentinel.approval")

APPROVAL_KIND = "sentinel-approval"
APPROVAL_VERSION = 1
APPROVAL_FIELDS = frozenset({
    "action_id", "args_sha256", "aud", "expires_at", "human_id", "intent", "kind",
    "nonce", "risk", "scope", "tool", "trace_id", "v",
})
EXPIRY_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
MAX_PAYLOAD_BYTES = 8192
DEFAULT_MAX_TTL = timedelta(hours=1)
_HEX64 = re.compile(r"[0-9a-f]{64}")
_NONCE = re.compile(r"[0-9a-f]{32,128}")

ENV_NONCE_DB = "SENTINEL_APPROVAL_NONCE_DB"
ENV_HUMAN_ID = "SENTINEL_HUMAN_ID"
ENV_AUDIENCE = "SENTINEL_MCP_AUDIENCE"

_NONCE_SCHEMA = """
CREATE TABLE IF NOT EXISTS used_nonces (
    nonce TEXT PRIMARY KEY,
    action_id TEXT NOT NULL,
    human_id TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    used_at TEXT NOT NULL
);
CREATE TRIGGER IF NOT EXISTS used_nonces_no_update BEFORE UPDATE ON used_nonces
    BEGIN SELECT RAISE(ABORT, 'used_nonces is append-only'); END;
CREATE TRIGGER IF NOT EXISTS used_nonces_no_delete BEFORE DELETE ON used_nonces
    BEGIN SELECT RAISE(ABORT, 'used_nonces is append-only'); END;
"""


class ApprovalError(Exception):
    """Approval payload or nonce store is malformed/unusable. Callers must fail closed."""


class NonceReplayed(ApprovalError):
    """The nonce was already consumed by an earlier approval."""


def args_sha256(args: Mapping[str, Any]) -> str:
    """SHA-256 hex of the canonical JSON of a tool-argument object (NaN/Infinity refused)."""
    if not isinstance(args, Mapping):
        raise ApprovalError("tool arguments must be a JSON object")
    try:
        blob = json.dumps(dict(args), sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                          allow_nan=False).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise ApprovalError(f"tool arguments are not canonical JSON: {exc.__class__.__name__}") from None
    return hashlib.sha256(blob).hexdigest()


def format_expiry(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime(EXPIRY_FORMAT)


def parse_expiry(text: str) -> datetime:
    if not isinstance(text, str):
        raise ApprovalError("expires_at must be a string")
    try:
        return datetime.strptime(text, EXPIRY_FORMAT).replace(tzinfo=timezone.utc)
    except ValueError:
        raise ApprovalError(f"expires_at {text!r} is not YYYY-MM-DDTHH:MM:SSZ") from None


def approval_payload(*, action_id: str, trace_id: str, human_id: str, aud: str, tool: str,
                     args_sha256: str, intent: str, scope: list[str] | tuple[str, ...], risk: str,
                     nonce: str, expires_at: str) -> bytes:
    """Exact bytes the human signs to approve one action."""
    return _canonical({
        "kind": APPROVAL_KIND, "v": APPROVAL_VERSION, "action_id": action_id, "trace_id": trace_id,
        "human_id": human_id, "aud": aud, "tool": tool, "args_sha256": args_sha256,
        "intent": intent, "scope": list(scope), "risk": risk, "nonce": nonce, "expires_at": expires_at,
    })


def parse_approval_payload(payload_bytes: bytes) -> dict[str, Any]:
    """Decode and strictly validate canonical approval payload bytes."""
    if len(payload_bytes) > MAX_PAYLOAD_BYTES:
        raise ApprovalError("approval payload too large")
    try:
        data = json.loads(payload_bytes.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise ApprovalError(f"approval payload is not valid UTF-8 JSON: {exc.__class__.__name__}") from None
    if not isinstance(data, dict) or set(data) != APPROVAL_FIELDS:
        raise ApprovalError("approval payload has unexpected or missing fields")
    if data["kind"] != APPROVAL_KIND or data["v"] != APPROVAL_VERSION or isinstance(data["v"], bool):
        raise ApprovalError("approval payload kind/version not supported")
    for key in APPROVAL_FIELDS - {"v", "scope"}:
        if not isinstance(data[key], str) or not data[key]:
            raise ApprovalError(f"approval payload field {key!r} must be a non-empty string")
    scope = data["scope"]
    if not isinstance(scope, list) or not scope or not all(isinstance(s, str) and s for s in scope):
        raise ApprovalError("approval payload scope must be a non-empty list of strings")
    if not _HEX64.fullmatch(data["args_sha256"]):
        raise ApprovalError("args_sha256 must be 64 lowercase hex chars")
    if not _NONCE.fullmatch(data["nonce"]):
        raise ApprovalError("nonce must be 32-128 lowercase hex chars")
    parse_expiry(data["expires_at"])
    canonical = approval_payload(**{k: data[k] for k in APPROVAL_FIELDS - {"kind", "v"}})
    if payload_bytes != canonical:
        raise ApprovalError("approval payload is not canonical JSON")
    return data


def _strict_b64(text: str, label: str) -> bytes:
    if not isinstance(text, str):
        raise ApprovalError(f"{label} must be a string")
    cleaned = "".join(text.split())
    if not cleaned:
        raise ApprovalError(f"{label} is empty")
    try:
        return base64.b64decode(cleaned, validate=True)
    except (binascii.Error, ValueError):
        raise ApprovalError(f"{label} is not valid base64") from None


class NonceStore:
    """Persistent one-shot nonce registry (append-only SQLite, file created 0600)."""

    def __init__(self, path) -> None:
        if not path:
            raise ApprovalError("no approval nonce store path configured")
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if not self.path.exists():
                os.close(os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600))
            conn = sqlite3.connect(self.path, timeout=5, isolation_level=None)
            conn.executescript(_NONCE_SCHEMA)
            return conn
        except (OSError, sqlite3.Error) as exc:
            raise ApprovalError(f"nonce store unusable: {exc.__class__.__name__}") from None

    def consume(self, *, nonce: str, action_id: str, human_id: str, expires_at: str, used_at: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO used_nonces (nonce, action_id, human_id, expires_at, used_at) VALUES (?, ?, ?, ?, ?)",
                (nonce, action_id, human_id, expires_at, used_at),
            )
        except sqlite3.IntegrityError:
            raise NonceReplayed(f"nonce for action {action_id!r} was already used (replay)") from None
        except sqlite3.Error as exc:
            raise ApprovalError(f"nonce store write failed: {exc.__class__.__name__}") from None
        finally:
            conn.close()

    def is_used(self, nonce: str) -> bool:
        conn = self._connect()
        try:
            return conn.execute("SELECT 1 FROM used_nonces WHERE nonce = ?", (nonce,)).fetchone() is not None
        finally:
            conn.close()


@dataclass(frozen=True)
class ApprovalCheck:
    ok: bool
    reason: str


class Ed25519ApprovalVerifier:
    """Callable ``(HumanApproval, ActionRequest) -> bool`` for ``Sentinel(human_approval_verifier=...)``."""

    def __init__(self, *, audience: str, trusted_humans: Mapping[str, Any], nonce_store: NonceStore,
                 max_ttl: timedelta = DEFAULT_MAX_TTL,
                 clock: Callable[[], datetime] | None = None) -> None:
        if not audience:
            raise ApprovalError("verifier needs a non-empty audience")
        if not trusted_humans:
            raise ApprovalError("verifier needs at least one trusted human public key")
        self.audience = audience
        self.trusted_humans = dict(trusted_humans)
        self.nonce_store = nonce_store
        self.max_ttl = max_ttl
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.last_reason = ""

    @classmethod
    def from_env(cls, *, audience: str | None = None) -> "Ed25519ApprovalVerifier | None":
        """Build from SENTINEL_HUMAN_PUBKEY (+ SENTINEL_HUMAN_ID, SENTINEL_APPROVAL_NONCE_DB). None if no key."""
        pub = os.environ.get("SENTINEL_HUMAN_PUBKEY")
        if not pub:
            return None
        human_id = os.environ.get(ENV_HUMAN_ID, "theodore")
        nonce_db = os.environ.get(ENV_NONCE_DB, str(Path("~/.sentinel/approval_nonces.db").expanduser()))
        key = _load_public_key(pub, "human")
        return cls(audience=audience or os.environ.get(ENV_AUDIENCE, "sentinel-mcp"),
                   trusted_humans={human_id: key}, nonce_store=NonceStore(nonce_db))

    def __call__(self, approval, request) -> bool:
        result = self.check(approval, request)
        self.last_reason = result.reason
        if not result.ok:
            logger.warning("approval rejected trace=%s: %s", getattr(request, "trace_id", "?"), result.reason)
        return result.ok

    def check(self, approval, request) -> ApprovalCheck:
        try:
            return self._check(approval, request)
        except NonceReplayed as exc:
            return ApprovalCheck(False, f"replay: {exc}")
        except ApprovalError as exc:
            return ApprovalCheck(False, str(exc))
        except Exception as exc:  # noqa: BLE001 - any unexpected failure must not authorize
            logger.exception("approval verifier crashed")
            return ApprovalCheck(False, f"verifier error: {exc.__class__.__name__}")

    def _check(self, approval, request) -> ApprovalCheck:
        payload_bytes = _strict_b64(approval.payload_b64, "approval payload")
        data = parse_approval_payload(payload_bytes)

        key = self.trusted_humans.get(data["human_id"])
        if key is None or approval.human_id != data["human_id"]:
            return ApprovalCheck(False, f"unknown or mismatched human_id {data['human_id']!r}")
        _strict_b64(approval.signature, "approval signature")
        if not _verify(key, "".join(approval.signature.split()), payload_bytes):
            return ApprovalCheck(False, "signature does not verify for this human key")

        risk = request.risk.strip().lower() if isinstance(request.risk, str) else ""
        bindings = (
            ("aud", data["aud"] == self.audience and data["aud"] == request.aud),
            ("action_id", data["action_id"] == approval.approval_id),
            ("trace_id", data["trace_id"] == request.trace_id == approval.trace_id),
            ("intent", data["intent"] == request.intent == approval.action),
            ("scope", tuple(data["scope"]) == tuple(request.scope) == tuple(approval.scope)),
            ("tool", data["tool"] == request.tool),
            ("args_sha256", data["args_sha256"] == request.args_sha256),
            ("risk", data["risk"] == risk),
            ("expires_at", data["expires_at"] == approval.expires_at),
        )
        for name, ok in bindings:
            if not ok:
                return ApprovalCheck(False, f"approval not bound to this action: {name} mismatch")

        now = self.clock()
        expires = parse_expiry(data["expires_at"])
        if now >= expires:
            return ApprovalCheck(False, f"approval expired at {data['expires_at']}")
        if expires - now > self.max_ttl:
            return ApprovalCheck(False, "approval expiry is further out than the allowed max TTL")

        self.nonce_store.consume(nonce=data["nonce"], action_id=data["action_id"], human_id=data["human_id"],
                                 expires_at=data["expires_at"], used_at=format_expiry(now))
        return ApprovalCheck(True, "approval signature and bindings verified; nonce consumed")


__all__ = [
    "APPROVAL_FIELDS", "ApprovalCheck", "ApprovalError", "Ed25519ApprovalVerifier", "NonceReplayed",
    "NonceStore", "approval_payload", "args_sha256", "format_expiry", "parse_approval_payload", "parse_expiry",
]
