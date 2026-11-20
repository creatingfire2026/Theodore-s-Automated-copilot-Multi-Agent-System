#!/usr/bin/env python3
import hashlib
import json
import sys
from pathlib import Path

REQUIRED = [
    "schema_version",
    "request_id",
    "created_at",
    "requestor",
    "target",
    "requested_transition",
    "state",
    "authority",
    "risk",
    "epistemic_status",
]
POST_EXECUTION_STATES = {
    "EXECUTING",
    "VERIFYING",
    "VERIFIED",
    "ACTIVE",
    "FAILED",
    "DIAGNOSE",
    "RETRY",
    "ROLLBACK",
    "ESCALATE",
    "ACCESS_BLIND_SPOT",
}
VERIFIED_STATES = {"VERIFIED", "ACTIVE"}
FAILED_VERIFICATION_STATES = {"FAILED", "DIAGNOSE", "RETRY", "ROLLBACK", "ESCALATE"}


class ValidationError(Exception):
    pass


def canonical_hash(obj):
    payload = {key: value for key, value in obj.items() if key != "record_hash"}
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def load_records(path):
    file_path = Path(path)
    try:
        raw = file_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValidationError(f"Unable to read {path}: {exc.strerror or exc}") from exc

    if file_path.suffix == ".jsonl":
        records = []
        for line_number, line in enumerate(raw.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValidationError(
                    f"Invalid JSON on line {line_number}: {exc.msg}"
                ) from exc
            if not isinstance(record, dict):
                raise ValidationError(
                    f"Line {line_number}: top-level JSON value must be an object"
                )
            records.append(record)
        if not records:
            raise ValidationError("No JSON records found")
        return records

    try:
        document = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValidationError(
            f"Invalid JSON: {exc.msg} at line {exc.lineno} column {exc.colno}"
        ) from exc

    if isinstance(document, dict):
        return [document]
    if isinstance(document, list):
        if not document:
            raise ValidationError("Top-level JSON array must not be empty")
        for index, record in enumerate(document, start=1):
            if not isinstance(record, dict):
                raise ValidationError(
                    f"Record {index}: top-level JSON value must be an object"
                )
        return document
    raise ValidationError("Top-level JSON value must be an object or array of objects")


def validate_record(obj, index, previous_hash):
    errors = []
    missing = [key for key in REQUIRED if key not in obj]
    if missing:
        errors.append("Missing required: " + ", ".join(missing))

    risk = obj.get("risk", {})
    auth = obj.get("authority", {})
    execution = obj.get("execution", {})
    verification = obj.get("verification", {})
    capability_health = obj.get("capability_health", {})
    state = obj.get("state")

    if auth.get("class") == "AUTO_EXECUTE" and risk.get("level") in {"HIGH", "CRITICAL"}:
        errors.append("HIGH/CRITICAL cannot AUTO_EXECUTE")

    if execution.get("attempted") and not verification.get("method"):
        errors.append("Execution attempted without verification method")

    if state == "AUTHORIZED" and execution.get("attempted"):
        errors.append("AUTHORIZED records cannot claim attempted execution")

    if state == "AUTHORIZED" and verification.get("passed") is True:
        errors.append("AUTHORIZED records cannot claim verified outcomes")

    if verification.get("passed") is True:
        if not verification.get("method"):
            errors.append("Verified outcomes require a verification method")
        if state not in VERIFIED_STATES:
            errors.append("Verified outcomes require state VERIFIED or ACTIVE")

    if state in VERIFIED_STATES and verification.get("passed") is not True:
        errors.append("VERIFIED/ACTIVE records require verification.passed=true")

    if verification.get("passed") is False and state not in FAILED_VERIFICATION_STATES:
        errors.append(
            "Verification failures must transition to FAILED, DIAGNOSE, RETRY, ROLLBACK, or ESCALATE"
        )

    if state == "ACCESS_BLIND_SPOT":
        if verification.get("passed") is True:
            errors.append("ACCESS_BLIND_SPOT cannot claim verification success")
        if not verification.get("method"):
            errors.append("ACCESS_BLIND_SPOT requires a verification method")
        if not execution.get("attempted"):
            errors.append("ACCESS_BLIND_SPOT requires an execution attempt")

    if execution.get("attempted") and state not in POST_EXECUTION_STATES:
        errors.append(
            "Execution attempts require a post-execution state such as EXECUTING, VERIFYING, VERIFIED, ACTIVE, FAILED, DIAGNOSE, RETRY, ROLLBACK, ESCALATE, or ACCESS_BLIND_SPOT"
        )

    if capability_health.get("health") == "PERMISSION_CHANGED":
        if capability_health.get("permission") != "DENIED":
            errors.append("PERMISSION_CHANGED requires permission=DENIED")
        if not capability_health.get("required_scope"):
            errors.append("PERMISSION_CHANGED requires at least one required_scope entry")
        if "observed_scope" not in capability_health:
            errors.append("PERMISSION_CHANGED requires observed_scope evidence")

    expected_hash = canonical_hash(obj)
    recorded_hash = obj.get("record_hash")
    if recorded_hash not in (None, expected_hash):
        errors.append(
            f"record_hash mismatch: expected {expected_hash}, found {recorded_hash}"
        )

    if previous_hash is not None and obj.get("previous_record_hash") != previous_hash:
        errors.append(
            f"previous_record_hash mismatch: expected {previous_hash}, found {obj.get('previous_record_hash')}"
        )

    return [f"Record {index}: {error}" for error in errors], expected_hash


def main(path):
    try:
        records = load_records(path)
    except ValidationError as exc:
        print("INVALID")
        print("-", exc)
        return 1

    all_errors = []
    hashes = []
    previous_hash = None
    for index, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            all_errors.append(f"Record {index}: top-level JSON value must be an object")
            continue
        record_errors, expected_hash = validate_record(record, index, previous_hash)
        all_errors.extend(record_errors)
        hashes.append(expected_hash)
        previous_hash = expected_hash

    if all_errors:
        print("INVALID")
        for error in all_errors:
            print("-", error)
        return 1

    print("VALID")
    for index, record_hash in enumerate(hashes, start=1):
        label = "record_hash" if len(hashes) == 1 else f"record[{index}]_hash"
        print(f"{label}: {record_hash}")
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: null_validate.py <application.json|ledger.jsonl>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
