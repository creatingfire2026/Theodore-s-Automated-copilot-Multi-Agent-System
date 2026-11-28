"""Authenticated client for Sentinel's independent Cloudflare dissent witness.

The witness signs its checkpoint with a dedicated Ed25519 key held only by the
Cloudflare Worker. Append requests carry the existing A7 or human row signature;
no witness private key or bearer credential is exposed to A7.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key


class DissentWitnessError(Exception):
    """The independent witness is unavailable, inconsistent, or unauthenticated."""


class HttpDissentWitness:
    def __init__(self, base_url: str, public_key_path: str | Path, *, timeout: float = 3.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.public_key_path = Path(public_key_path).expanduser()
        self.timeout = timeout
        try:
            key = load_pem_public_key(self.public_key_path.read_bytes())
        except Exception as exc:  # noqa: BLE001
            raise DissentWitnessError(f"witness public key unreadable: {exc.__class__.__name__}") from None
        if not isinstance(key, Ed25519PublicKey):
            raise DissentWitnessError("witness public key is not Ed25519")
        self.public_key = key

    def _request(self, method: str, path: str, body: dict | None = None) -> dict:
        data = None if body is None else json.dumps(
            body, sort_keys=True, separators=(",", ":"), ensure_ascii=False
        ).encode("utf-8")
        request = urllib.request.Request(
            self.base_url + path, data=data, method=method,
            headers={"Accept": "application/json", **({"Content-Type": "application/json"} if data is not None else {})},
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.loads(response.read(65537).decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
            raise DissentWitnessError(f"witness request failed: {exc.__class__.__name__}") from None
        if not isinstance(payload, dict) or payload.get("ok") is False:
            reason = payload.get("error", "invalid witness response") if isinstance(payload, dict) else "invalid witness response"
            raise DissentWitnessError(str(reason)[:200])
        return payload

    def _verified_checkpoint(self, response: dict) -> dict:
        try:
            checkpoint = response["checkpoint"]
            signature = response["signature"]
            payload = {
                "seq": checkpoint["seq"],
                "head_hash": checkpoint["head_hash"],
                "prev_hash": checkpoint["prev_hash"],
                "witness_id": checkpoint["witness_id"],
                "ts": checkpoint["ts"],
            }
            if not isinstance(payload["seq"], int) or payload["seq"] < 0:
                raise ValueError("invalid sequence")
            if any(not isinstance(payload[k], str) for k in ("head_hash", "prev_hash", "witness_id", "ts")):
                raise ValueError("invalid checkpoint fields")
            import base64
            self.public_key.verify(
                base64.b64decode(signature, validate=True),
                json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8"),
            )
        except (KeyError, TypeError, ValueError, InvalidSignature) as exc:
            raise DissentWitnessError(f"witness checkpoint signature or schema invalid: {exc.__class__.__name__}") from None
        return payload

    def checkpoint(self) -> dict:
        return self._verified_checkpoint(self._request("GET", "/v1/checkpoint"))

    def assert_matches(self, seq: int, head_hash: str) -> None:
        checkpoint = self.checkpoint()
        if checkpoint["seq"] != seq or checkpoint["head_hash"] != head_hash:
            raise DissentWitnessError(
                f"local store does not match independent witness "
                f"(local={seq}:{head_hash}, witness={checkpoint['seq']}:{checkpoint['head_hash']})"
            )

    def advance(self, row: dict) -> dict:
        response = self._request("POST", "/v1/advance", {"row": row})
        checkpoint = self._verified_checkpoint(response)
        if checkpoint["seq"] != row.get("seq") or checkpoint["head_hash"] != row.get("row_hash"):
            raise DissentWitnessError("witness acknowledged a different checkpoint")
        return checkpoint
