# NULL Admission Decision Logs v1

## Decision
Admission decision logs are the next canonical fixture scope after the baseline capability conformance vectors. Probe execution traces follow later as an observability layer.

## Why this comes first
Admission logs sit at the Sentinel commitment boundary. They are deterministic, compact, auditable, replayable, and directly tied to policy enforcement. This makes them the strongest next step for proving that locked invariants are actually enforced before execution.

Probe traces remain important, but they are higher-cardinality, more privacy-sensitive, and harder to make deterministic in CI. They should be layered on after admission semantics are stable.

## Required admission log fields
Each decision record MUST include:

- `decision_id`
- `timestamp`
- `schema_version`
- `assertion_set_version`
- `request_id`
- `capability_id`
- `registry_state_hash`
- `policy_version`
- `requested_operation`
- `required_scopes`
- `observed_scopes`
- `health_vector`
- `fallback_state`
- `assertion_results`
- `primary_verdict`
- `secondary_classifications`
- `terminal_state`
- `reason_codes`
- `evidence_refs`
- `sentinel_actor_id`
- `previous_record_hash`
- `record_hash`

## Assertion result model
Each locked invariant is evaluated independently and recorded explicitly:

```json
{
  "assertion_id": "AUTHORIZATION_SCOPE_PRESENT",
  "status": "PASS|FAIL|UNKNOWN",
  "evidence_refs": [],
  "reason_code": ""
}
```

No aggregate verdict may erase the individual assertion results that produced it.

## Core invariants represented in admission logs

1. Authentication and authorization remain independent dimensions.
2. Capability version and definition integrity remain independent from authority.
3. Fallback availability does not imply fallback eligibility.
4. Fallback execution before explicit Sentinel admission remains `UNRESOLVED` and blocked.
5. `verified_healthy=true` requires connected, authenticated, authorized, and executable to all be true.
6. Cryptographic trust failure and permission failure remain distinct classifications.
7. Execution admission is not execution success.

## Canonical verdicts
Admission logs SHOULD use the conformance-spec primary verdict vocabulary, including:

- `ACCEPT`
- `REJECT`
- `UNRESOLVED`
- `STRUCTURAL_VALIDATION_FAILED`
- `SIGNATURE_VERIFICATION_FAILED`
- `TRUST_FAILURE`
- `AUTHORIZATION_CHECK_FAILED`
- `FALLBACK_NOT_ADMITTED`
- `VERSION_HASH_MISMATCH`
- `INVARIANT_HEALTH_VECTOR_MISMATCH`
- `VALIDATOR_DIVERGENCE`

## Storage rule
Admission logs are append-only evidence. Corrections create new records referencing superseded records. Historical decisions are never overwritten.

## CI fixture strategy
Admission fixtures MUST be deterministic and function-scoped. Each fixture isolates one policy outcome and includes:

- exact registry input reference
- assertion-set version
- exact assertion results
- expected primary verdict
- expected terminal state
- expected reason codes
- expected evidence references

A validator or Sentinel policy change that alters a canonical admission verdict requires either an implementation fix or an explicit specification/version change. Fixtures are not silently tuned to match implementations.

## Relationship to probe traces
Probe traces answer: **How did runtime state evolve?**

Admission logs answer: **Why was this action allowed, denied, or left unresolved?**

The desired long-term correlation is:

`trace_id -> registry mutation -> admission_decision_id -> execution_receipt_id -> verification_record_id`

But probe traces are not required to establish admission correctness.

## Privacy boundary
Admission logs SHOULD store references/hashes to sensitive evidence rather than full prompt, response, credential, or PII payloads whenever possible. Sensitive raw evidence belongs in a separately governed evidence store.

## Next implementation checkpoint
1. Add `admission_decision.schema.json`.
2. Create deterministic admission fixtures derived from VEC-001..VEC-008.
3. Require every validator verdict to emit or map to one admission decision record.
4. Add probe execution trace schema only after admission fixtures pass CI deterministically.
