# NULL Baseline Vector Lock Review

Status: **BASELINE SEMANTICS LOCKED; CRYPTOGRAPHIC BYTES PENDING DETERMINISTIC GENERATION**

This review preserves VEC-001 through VEC-008 as the immutable baseline IDs while correcting two proposed expectations that conflict with the canonical conformance specification and RFC 8785 behavior.

## Lock rule

No vector ID in VEC-001..VEC-008 may be reassigned to a different semantic invariant. Any future scenario begins at VEC-009.

Each fixture must conform to the current `schemas/capability_registry.schema.json` field contract before it is eligible to test a later validation gate. In particular, canonical fixtures use `fallback_routes` and the complete `signature_envelope` containing `canonicalization`, `payload_hash`, `signature_algorithm`, `anchor_key_id`, `timestamp`, and `signature`.

Placeholder signatures are not canonical cryptographic fixtures. Locked crypto fixtures require a deterministic test keypair and precomputed signatures over RFC 8785/JCS canonical bytes.

## Baseline vectors

### VEC-001 — Nominal Healthy
Expected primary verdict: `ACCEPT`
Expected terminal health classification: `VERIFIED_HEALTHY`
Proves: happy-path structural, cryptographic, policy, and health conformance.

### VEC-002 — Forged Signature
Expected primary verdict: `SIGNATURE_VERIFICATION_FAILED`
Proves: structurally valid records cannot cross the cryptographic gate with a forged or tampered Ed25519 signature.

### VEC-003 — Scope Revocation / Permission Loss
Expected primary verdict: `AUTHORIZATION_CHECK_FAILED`
Secondary classification: `PERMISSION_CHANGED`
Proves: connected + authenticated does not imply authorized or executable.

### VEC-004 — Definition Drift
Expected primary verdict: `VERSION_HASH_MISMATCH`
Secondary classification: `VERSION_DRIFT`
Proves: definition identity is independently enforced and drift forces `verified_healthy=false` until revalidation.

### VEC-005 — Unadmitted Fallback
Expected primary verdict: `FALLBACK_NOT_ADMITTED`
Expected terminal state: `UNRESOLVED`
Proves: fallback availability never grants fallback authority.

### VEC-006 — Impossible Health Vector
Expected primary verdict: `INVARIANT_HEALTH_VECTOR_MISMATCH`
Proves: `verified_healthy=true` requires connected, authenticated, authorized, and executable to all be true.

### VEC-007 — JCS Encoding Boundary
**Corrected expected primary verdict: `ACCEPT` when semantic content and signed canonical payload are unchanged.**
Proves: RFC 8785/JCS canonicalization removes insignificant JSON object member ordering and whitespace differences before hashing/signature verification.

A separate post-signing *semantic mutation* test may produce `SIGNATURE_VERIFICATION_FAILED`, but that is not an ordering/whitespace test and must not reuse VEC-007's semantic invariant.

### VEC-008 — Duplicate-Key Parser Boundary
**Corrected expected primary verdict: `STRUCTURAL_VALIDATION_FAILED` (or a future dedicated `PARSE_VALIDATION_FAILED` if the verdict vocabulary is versioned to add it).**
Proves: duplicate JSON member names are rejected deterministically before canonicalization/signature verification.

`VALIDATOR_DIVERGENCE` is not the expected outcome of a canonical vector. It is the runtime conformance state produced only when independent conforming implementations return different primary verdicts for the same canonical vector.

## Deterministic cryptographic fixture requirements

The fixture generator must use one fixed test-only Ed25519 keypair committed as non-secret public test material or deterministically derived from a fixed test seed. It must never use a freshly generated keypair at test runtime for canonical vectors.

For each signed vector, lock:

- exact UTF-8 input representation where raw parsing behavior matters;
- parsed semantic payload;
- RFC 8785/JCS canonical signed bytes;
- SHA-256 payload hash;
- admitted definition hash and observed definition hash when drift is under test;
- anchor key ID;
- Ed25519 public key;
- exact Ed25519 signature bytes;
- expected gate results;
- expected primary verdict;
- expected terminal state/classification.

## Conformance rule

Fixtures are not modified to satisfy implementations. Implementations are modified until they satisfy the locked fixtures and conformance specification. Any intentional semantic change requires an explicit specification/version change with preserved historical vectors.
