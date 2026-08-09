import hashlib
import json
from copy import deepcopy
from pathlib import Path
from cryptography.hazmat.primitives.asymmetric import ed25519

CANONICAL_SEED = bytes.fromhex("01" * 32)
PRIVATE_KEY = ed25519.Ed25519PrivateKey.from_private_bytes(CANONICAL_SEED)
PUBLIC_KEY = PRIVATE_KEY.public_key()
KEY_ID = "sentinel-root-test-key-01"
PUBLIC_KEY_HEX = PUBLIC_KEY.public_bytes_raw().hex()
ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = Path(__file__).resolve().parent / "fixtures" / "canonical"
REFERENCE_HASH = "sha256:a4f8d2b992147321e3f8902d1847529810427389472109847230918239012832"
TIMESTAMP = "2026-08-09T00:00:00Z"


def _jcs_string(value: str) -> str:
    # Current canonical fixtures use ASCII strings only. json.dumps produces
    # RFC 8785-compatible escaping for this constrained domain.
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _jcs_serialize(value) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, str):
        return _jcs_string(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        raise TypeError("Canonical fixture profile forbids floats; production validators must use a full RFC 8785 implementation")
    if isinstance(value, list):
        return "[" + ",".join(_jcs_serialize(v) for v in value) + "]"
    if isinstance(value, dict):
        for key in value:
            if not isinstance(key, str):
                raise TypeError("JCS object member names must be strings")
        keys = sorted(value.keys(), key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(_jcs_string(k) + ":" + _jcs_serialize(value[k]) for k in keys) + "}"
    raise TypeError(f"Unsupported JCS type: {type(value).__name__}")


def jcs_canonicalize(data: dict) -> bytes:
    return _jcs_serialize(data).encode("utf-8")


def build_signed_payload(unsigned_payload: dict, key_id: str = KEY_ID) -> dict:
    canonical_bytes = jcs_canonicalize(unsigned_payload)
    payload_hash = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    signature = PRIVATE_KEY.sign(canonical_bytes).hex()
    payload = deepcopy(unsigned_payload)
    payload["signature_envelope"] = {
        "anchor_key_id": key_id,
        "canonicalization": "RFC8785-JCS",
        "payload_hash": payload_hash,
        "signature_algorithm": "Ed25519",
        "timestamp": TIMESTAMP,
        "signature": signature,
    }
    return payload


def write_fixture(vector_id, description, expected_primary_verdict, expected_terminal_state,
                  expected_gates, payload, secondary_classifications=None):
    fixture = {
        "vector_id": vector_id,
        "description": description,
        "expected_primary_verdict": expected_primary_verdict,
        "expected_terminal_state": expected_terminal_state,
        "expected_gates": expected_gates,
        "expected_secondary_classifications": secondary_classifications or [],
        "payload": payload,
    }
    path = OUTPUT_DIR / f"{vector_id}.json"
    path.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def base_payload():
    return {
        "capability_id": "github_issue_writer",
        "version": "1.2.0",
        "definition_hash": REFERENCE_HASH,
        "health_vector": {
            "connected": True,
            "authenticated": True,
            "authorized": True,
            "executable": True,
            "verified_healthy": True,
        },
        "fallback_routes": [],
    }


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "profile": "NULL-SENTINEL-TEST-ANCHOR-v1",
        "warning": "TEST-ONLY KEY MATERIAL. NEVER ADMIT THIS KEY IN PRODUCTION.",
        "anchor_key_id": KEY_ID,
        "seed_hex": CANONICAL_SEED.hex(),
        "public_key_hex": PUBLIC_KEY_HEX,
        "algorithm": "Ed25519",
        "canonicalization": "RFC8785-JCS",
        "admitted_definition_hashes": {"github_issue_writer": REFERENCE_HASH},
    }
    (OUTPUT_DIR / "KEY_MANIFEST.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    base = base_payload()

    write_fixture(
        "VECTOR-001", "All gates pass with a valid signature and healthy state.",
        "ACCEPT", "EXECUTION_ADMISSIBLE",
        {"structure": "PASS", "cryptography": "PASS", "policy": "PASS", "health": "PASS"},
        build_signed_payload(base),
    )

    v2 = deepcopy(base)
    v2["health_vector"]["connected"] = False
    write_fixture(
        "VECTOR-002", "verified_healthy=true while connected=false; health conjunction violation.",
        "INVARIANT_HEALTH_VECTOR_MISMATCH", "BLOCKED",
        {"structure": "PASS", "cryptography": "PASS", "policy": "PASS", "health": "FAIL"},
        build_signed_payload(v2),
    )

    v3 = deepcopy(base)
    v3["health_vector"].update({"authorized": False, "executable": False, "verified_healthy": False})
    write_fixture(
        "VECTOR-003", "Authenticated identity lacks required authorization.",
        "AUTHORIZATION_CHECK_FAILED", "BLOCKED",
        {"structure": "PASS", "cryptography": "PASS", "policy": "FAIL", "health": "NOT_EVALUATED"},
        build_signed_payload(v3), ["PERMISSION_CHANGED"],
    )

    v4 = deepcopy(base)
    v4["health_vector"]["verified_healthy"] = False
    v4["fallback_routes"] = [{
        "fallback_capability_id": "backup_runner",
        "sentinel_admission_status": "UNEVALUATED",
        "resolution_state": "UNRESOLVED",
    }]
    write_fixture(
        "VECTOR-004", "Fallback route exists but has not received explicit Sentinel admission.",
        "FALLBACK_NOT_ADMITTED", "UNRESOLVED",
        {"structure": "PASS", "cryptography": "PASS", "policy": "FAIL", "health": "NOT_EVALUATED"},
        build_signed_payload(v4),
    )

    v5 = build_signed_payload(base)
    v5["signature_envelope"]["signature"] = "00" * 64
    write_fixture(
        "VECTOR-005", "Structurally valid record with a forged Ed25519 signature.",
        "SIGNATURE_VERIFICATION_FAILED", "BLOCKED",
        {"structure": "PASS", "cryptography": "FAIL", "policy": "NOT_EVALUATED", "health": "NOT_EVALUATED"},
        v5,
    )

    v6 = deepcopy(base)
    v6["definition_hash"] = "sha256:" + "00" * 32
    v6["health_vector"]["verified_healthy"] = False
    write_fixture(
        "VECTOR-006", "Observed definition hash differs from the admitted reference hash.",
        "VERSION_HASH_MISMATCH", "BLOCKED",
        {"structure": "PASS", "cryptography": "PASS", "policy": "FAIL", "health": "NOT_EVALUATED"},
        build_signed_payload(v6), ["VERSION_DRIFT"],
    )

    v7 = build_signed_payload(base)
    v7["version"] = "1.2.1"  # semantic mutation after signing
    write_fixture(
        "VECTOR-007", "Signed payload is semantically modified after signing.",
        "SIGNATURE_VERIFICATION_FAILED", "BLOCKED",
        {"structure": "PASS", "cryptography": "FAIL", "policy": "NOT_EVALUATED", "health": "NOT_EVALUATED"},
        v7,
    )

    v8 = build_signed_payload(base, key_id="unrecognized-key-id-99")
    write_fixture(
        "VECTOR-008", "Signature envelope references an unknown anchor key ID.",
        "TRUST_FAILURE", "UNRESOLVED",
        {"structure": "PASS", "cryptography": "FAIL", "policy": "NOT_EVALUATED", "health": "NOT_EVALUATED"},
        v8,
    )

    print(f"Generated 8 canonical vectors and KEY_MANIFEST.json at {OUTPUT_DIR}")
    print(f"Derived public key: {PUBLIC_KEY_HEX}")


if __name__ == "__main__":
    main()
