# NULL Conformance Specification v1

## Purpose
This document defines the language-independent behavior required of any NULL capability validator implementation. Implementations serve this specification; they do not define it.

## Authority order
1. Canonical schema contracts
2. This conformance specification
3. Deterministic test vectors
4. Validator implementations

If implementations disagree, the disagreement is a validator divergence. No implementation wins by priority or language choice.

## Validation gates
A capability record is EXECUTION_ADMISSIBLE only when all four gates pass:

1. STRUCTURAL_VALID — record conforms to the canonical JSON Schema.
2. CRYPTOGRAPHIC_VALID — canonical payload hash and Ed25519 signature verify against an admitted Sentinel anchor key.
3. POLICY_VALID — Sentinel authorization, fallback, version, trust, and admission invariants hold.
4. HEALTH_VALID — the health vector is internally consistent and satisfies the requested operation.

EXECUTION_ADMISSIBLE does not imply EXECUTION_SUCCEEDED.

## Canonicalization
Signed payloads MUST be canonicalized with RFC 8785 JSON Canonicalization Scheme (JCS) before hashing or signing.

For a payload P:

canonical_bytes = JCS(P)
payload_hash = "sha256:" + lowercase_hex(SHA256(canonical_bytes))

Any post-signing modification that changes canonical_bytes MUST invalidate signature verification.

## Definition integrity
Each capability definition MUST expose a definition_hash:

"sha256:" + lowercase_hex(SHA256(canonical capability definition bytes))

A mismatch between the admitted definition hash and the observed local definition hash produces VERSION_DRIFT or VERSION_HASH_MISMATCH according to the verdict vocabulary below and MUST force verified_healthy=false until revalidation completes.

## Signature verification
The schema validates only signature-envelope structure.

The validator MUST verify:
- anchor_key_id exists in the admitted trust store;
- signature_algorithm is supported;
- payload_hash equals the hash recomputed from canonical payload bytes;
- Ed25519 signature is valid for the canonical signed payload under the admitted public key;
- the signed payload binds the capability identity, version, definition hash, health vector, fallback state, and other fields defined by the canonical signing profile.

Unknown anchor keys MUST NOT be silently trusted.

## Independent health gates
The following are independent state dimensions:

CONNECTED
AUTHENTICATED
AUTHORIZED
EXECUTABLE
VERIFIED_HEALTHY

The validator MUST NOT collapse them into one readiness bit.

Invariant:

verified_healthy=true => connected=true AND authenticated=true AND authorized=true AND executable=true

The reverse is not automatic: all prerequisite booleans being true does not itself prove verified_healthy=true. Fresh verification evidence may still be required.

## Fallback semantics
The presence of a fallback capability never grants authority.

A fallback route remains operationally UNRESOLVED until Sentinel admission is explicit.

Allowed admission states:
- UNEVALUATED
- PENDING_ADMISSION
- ADMITTED
- REJECTED

Before ADMITTED, execution through the fallback MUST be blocked and the terminal state remains UNRESOLVED.

ADMITTED requires an admission record reference verifiable under the policy layer.

## Failure classification
Transport, identity, authority, integrity, and health failures MUST remain distinguishable.

Examples:
- connection unavailable -> UNREACHABLE
- authentication expired -> AUTH_EXPIRED
- authenticated but required scope missing -> PERMISSION_CHANGED / AUTHORIZATION_CHECK_FAILED
- definition hash changed -> VERSION_DRIFT / VERSION_HASH_MISMATCH
- signature invalid -> SIGNATURE_VERIFICATION_FAILED
- fallback not admitted -> FALLBACK_NOT_ADMITTED with state UNRESOLVED
- impossible health vector -> INVARIANT_HEALTH_VECTOR_MISMATCH

## Verdict vocabulary
Implementations MUST emit a machine-readable primary verdict from this baseline set:

- ACCEPT
- REJECT
- UNRESOLVED
- STRUCTURAL_VALIDATION_FAILED
- SIGNATURE_VERIFICATION_FAILED
- TRUST_FAILURE
- AUTHORIZATION_CHECK_FAILED
- FALLBACK_NOT_ADMITTED
- VERSION_HASH_MISMATCH
- INVARIANT_HEALTH_VECTOR_MISMATCH
- VALIDATOR_DIVERGENCE

A validator MAY emit secondary classifications such as PERMISSION_CHANGED or VERSION_DRIFT, but the primary verdict for a given test vector must match the canonical expected verdict.

## Deterministic test vectors
Each vector MUST define:
- vector_id
- input payload or fixture reference
- trusted anchor-key material or explicit trust-state fixture
- expected structural result
- expected cryptographic result
- expected policy result
- expected health result
- expected primary verdict
- expected terminal state

Vectors isolate one principal failure mode whenever possible so a failure occurs at the intended gate.

## Baseline vectors
- VECTOR-001: all gates true + valid signature -> ACCEPT
- VECTOR-002: connected=false, verified_healthy=true -> INVARIANT_HEALTH_VECTOR_MISMATCH
- VECTOR-003: authenticated=true, authorized=false -> AUTHORIZATION_CHECK_FAILED; secondary PERMISSION_CHANGED
- VECTOR-004: fallback exists but not ADMITTED -> FALLBACK_NOT_ADMITTED; terminal UNRESOLVED
- VECTOR-005: structurally valid record + forged signature -> SIGNATURE_VERIFICATION_FAILED
- VECTOR-006: observed definition hash differs from admitted hash -> VERSION_HASH_MISMATCH; secondary VERSION_DRIFT
- VECTOR-007: signed payload modified after signing -> SIGNATURE_VERIFICATION_FAILED
- VECTOR-008: unknown anchor_key_id -> TRUST_FAILURE; terminal UNRESOLVED

## Cross-implementation conformance gate
For every canonical vector V:

TS_VALIDATOR(V).primary_verdict MUST equal RUST_VALIDATOR(V).primary_verdict

and both MUST equal the specification's expected primary verdict.

If independent implementations disagree:

state = VALIDATOR_DIVERGENCE
admission = UNRESOLVED
execution = BLOCKED

No implementation is permitted to override the other merely because it ran first or is considered the reference implementation.

## Execution boundary
Validation authorizes at most an attempt.

AUTHORIZED != EXECUTED
EXECUTION_ADMISSIBLE != EXECUTION_SUCCEEDED
EXECUTED != VERIFIED
VERIFIED != VERIFIED_HEALTHY

## Evidence and regression
Every canonical vector is a regression guard. Any implementation change that alters a canonical verdict requires either:
- correction of an implementation bug while restoring the existing expected verdict; or
- an explicit specification/version change with preserved history and migrated vectors.

Canonical fixtures are never silently rewritten to make a new implementation pass.
