#!/usr/bin/env python3
import json, sys, hashlib
from pathlib import Path

REQUIRED = ["request_id","created_at","requestor","target","requested_transition","state","authority","risk","epistemic_status"]

def canonical_hash(obj):
    x = dict(obj)
    x["record_hash"] = None
    raw = json.dumps(x, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()

def main(path):
    obj = json.loads(Path(path).read_text())
    errors = []
    missing = [k for k in REQUIRED if k not in obj]
    if missing:
        errors.append("Missing required: " + ", ".join(missing))
    risk = obj.get("risk", {})
    auth = obj.get("authority", {})
    if auth.get("class") == "AUTO_EXECUTE" and risk.get("level") in {"HIGH", "CRITICAL"}:
        errors.append("HIGH/CRITICAL cannot AUTO_EXECUTE")
    if obj.get("execution", {}).get("attempted") and not obj.get("verification", {}).get("method"):
        errors.append("Execution attempted without verification method")
    if errors:
        print("INVALID")
        for error in errors:
            print("-", error)
        return 1
    print("VALID")
    print("record_hash:", canonical_hash(obj))
    return 0

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("usage: null_validate.py <application.json>")
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
