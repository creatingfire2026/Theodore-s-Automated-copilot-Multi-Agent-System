import hashlib
import json
import sys
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric import ed25519
from jsonschema import Draft202012Validator, FormatChecker

TESTS_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = TESTS_DIR / "fixtures" / "canonical"
SCHEMA_PATH = TESTS_DIR.parent / "schemas" / "capability_registry.schema.json"


def _jcs_string(value: str) -> str:
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
        if not all(isinstance(k, str) for k in value):
            raise TypeError("JCS object member names must be strings")
        keys = sorted(value.keys(), key=lambda k: k.encode("utf-16-be"))
        return "{" + ",".join(_jcs_string(k) + ":" + _jcs_serialize(value[k]) for k in keys) + "}"
    raise TypeError(f"Unsupported JCS type: {type(value).__name__}")


def jcs_canonicalize(data: dict) -> bytes:
    return _jcs_serialize(data).encode("utf-8")


def result(primary, terminal, gates, secondary=None, detail=None):
    return {
        "primary_verdict": primary,
        "terminal_state": terminal,
        "gates": gates,
        "secondary_classifications": secondary or [],
        "detail": detail,
    }


def evaluate_vector(fixture, manifest, validator):
    payload = fixture.get("payload")
    gates = {"structure": "NOT_EVALUATED", "cryptography": "NOT_EVALUATED", "policy": "NOT_EVALUATED", "health": "NOT_EVALUATED"}

    # Gate 1: STRUCTURE
    if not isinstance(payload, dict):
        gates["structure"] = "FAIL"
        return result("STRUCTURAL_VALIDATION_FAILED", "BLOCKED", gates, detail="payload must be an object")
    errors = sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path))
    if errors:
        gates["structure"] = "FAIL"
        return result("STRUCTURAL_VALIDATION_FAILED", "BLOCKED", gates, detail=errors[0].message)
    gates["structure"] = "PASS"

    # Gate 2: CRYPTOGRAPHY / TRUST LOOKUP
    envelope = payload["signature_envelope"]
    if envelope["anchor_key_id"] != manifest["anchor_key_id"]:
        gates["cryptography"] = "FAIL"
        return result("TRUST_FAILURE", "UNRESOLVED", gates, detail="anchor_key_id is not in admitted test trust store")

    unsigned = {k: v for k, v in payload.items() if k != "signature_envelope"}
    try:
        canonical_bytes = jcs_canonicalize(unsigned)
    except Exception as exc:
        gates["cryptography"] = "FAIL"
        return result("SIGNATURE_VERIFICATION_FAILED", "BLOCKED", gates, detail=str(exc))

    computed_hash = "sha256:" + hashlib.sha256(canonical_bytes).hexdigest()
    if computed_hash != envelope["payload_hash"]:
        gates["cryptography"] = "FAIL"
        return result("SIGNATURE_VERIFICATION_FAILED", "BLOCKED", gates, detail="payload_hash mismatch")

    try:
        public_key = ed25519.Ed25519PublicKey.from_public_bytes(bytes.fromhex(manifest["public_key_hex"]))
        signature = bytes.fromhex(envelope["signature"])
        public_key.verify(signature, canonical_bytes)
    except (ValueError, InvalidSignature):
        gates["cryptography"] = "FAIL"
        return result("SIGNATURE_VERIFICATION_FAILED", "BLOCKED", gates, detail="Ed25519 verification failed")
    gates["cryptography"] = "PASS"

    # Gate 3: POLICY
    capability_id = payload["capability_id"]
    admitted_hash = manifest.get("admitted_definition_hashes", {}).get(capability_id)
    if admitted_hash is None:
        gates["policy"] = "FAIL"
        return result("UNRESOLVED", "UNRESOLVED", gates, detail="no admitted definition hash for capability")
    if payload["definition_hash"] != admitted_hash:
        gates["policy"] = "FAIL"
        return result("VERSION_HASH_MISMATCH", "BLOCKED", gates, ["VERSION_DRIFT"], "definition hash differs from admitted reference")

    health = payload["health_vector"]
    if not health["authorized"]:
        gates["policy"] = "FAIL"
        return result("AUTHORIZATION_CHECK_FAILED", "BLOCKED", gates, ["PERMISSION_CHANGED"], "authorization required for requested operation")

    if not health["verified_healthy"] and payload["fallback_routes"]:
        if not any(route["sentinel_admission_status"] == "ADMITTED" for route in payload["fallback_routes"]):
            gates["policy"] = "FAIL"
            return result("FALLBACK_NOT_ADMITTED", "UNRESOLVED", gates, detail="no fallback route has explicit Sentinel admission")
    gates["policy"] = "PASS"

    # Gate 4: HEALTH
    prereqs = health["connected"] and health["authenticated"] and health["authorized"] and health["executable"]
    if health["verified_healthy"] and not prereqs:
        gates["health"] = "FAIL"
        return result("INVARIANT_HEALTH_VECTOR_MISMATCH", "BLOCKED", gates, detail="verified_healthy requires all prerequisite gates")
    if not health["verified_healthy"]:
        gates["health"] = "FAIL"
        return result("UNRESOLVED", "UNRESOLVED", gates, detail="health has not been freshly verified")
    gates["health"] = "PASS"
    return result("ACCEPT", "EXECUTION_ADMISSIBLE", gates)


def main():
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    manifest = json.loads((FIXTURES_DIR / "KEY_MANIFEST.json").read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    files = sorted(FIXTURES_DIR.glob("VECTOR-*.json"))
    if len(files) != 8:
        raise SystemExit(f"CRITICAL: expected 8 canonical vectors, found {len(files)}")

    print(f"Executing NULL Sentinel four-gate conformance suite across {len(files)} vectors")
    print(f"Anchor: {manifest['anchor_key_id']} -> {manifest['public_key_hex']}\n")
    passed = 0
    divergence = 0
    details = []

    for path in files:
        fixture = json.loads(path.read_text(encoding="utf-8"))
        actual = evaluate_vector(fixture, manifest, validator)
        expected_primary = fixture["expected_primary_verdict"]
        expected_terminal = fixture["expected_terminal_state"]
        expected_gates = fixture["expected_gates"]
        ok = (
            actual["primary_verdict"] == expected_primary
            and actual["terminal_state"] == expected_terminal
            and actual["gates"] == expected_gates
        )
        status = "PASS" if ok else "DIVERGENCE"
        print(f"{'✅' if ok else '❌'} [{fixture['vector_id']}] {status} -> {actual['primary_verdict']} / {actual['terminal_state']}")
        if ok:
            passed += 1
        else:
            divergence += 1
            details.append({
                "vector_id": fixture["vector_id"],
                "expected": {"primary_verdict": expected_primary, "terminal_state": expected_terminal, "gates": expected_gates},
                "actual": actual,
            })

    print("\n" + "-" * 64)
    print(f"Final Outcome: {passed}/8 Passed | {divergence} Divergences")
    if details:
        print(json.dumps(details, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
