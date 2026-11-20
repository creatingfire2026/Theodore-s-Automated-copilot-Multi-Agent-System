# NULL Capability Health Model v1

## Purpose
Represent capability condition precisely enough that NULL does not confuse a healthy connection with sufficient authority, or an authorization problem with a transport failure.

## Canonical health states

- HEALTHY
- DEGRADED
- AUTH_EXPIRED
- RATE_LIMITED
- PERMISSION_CHANGED
- VERSION_DRIFT
- UNREACHABLE
- COMPROMISED
- REVOKED

## Required health dimensions

Every capability assessment SHOULD distinguish at least:

- provider
- capability identifier
- transport / connection state
- authentication state
- authorization / permission state
- required scope
- observed scope
- version state
- rate-limit state
- trust / compromise state
- fallback capability
- last verification evidence
- resulting NULL classification

## Canonical example

```text
Capability: github.repository.write
Provider: GitHub MCP
Connection: HEALTHY
Authentication: HEALTHY
Permission: DENIED
Required scope: contents:write
Observed scope: contents:read
Classification: PERMISSION_CHANGED
Fallback: direct GitHub connector
```

Interpretation: the provider and transport are reachable and authentication is valid, but the capability cannot perform the requested write because the observed authorization scope is narrower than required. NULL must not classify this as UNREACHABLE or AUTH_EXPIRED.

## Transition guidance

### HEALTHY
All required transport, authentication, permission, version, rate-limit, and trust checks currently satisfy the requested capability.

### DEGRADED
Capability remains usable but performance, completeness, latency, or reliability is materially reduced.

### AUTH_EXPIRED
Connection may remain reachable, but credentials or authentication session are no longer valid.

### RATE_LIMITED
Provider is reachable and authorization may be valid, but execution is temporarily constrained by provider quota or throttling.

### PERMISSION_CHANGED
Authentication succeeds, but current permissions no longer satisfy the previously expected or currently requested capability.

### VERSION_DRIFT
Observed tool/server/schema/runtime version differs materially from the admitted or verified version and requires revalidation.

### UNREACHABLE
The capability endpoint, connector, runtime, or transport cannot currently be observed or contacted.

### COMPROMISED
Evidence indicates the capability, credentials, provider path, artifact, or execution surface cannot presently be trusted. Execution must stop except for pre-authorized containment and evidence preservation.

### REVOKED
The capability has been intentionally withdrawn from use by policy, owner action, provider action, or Sentinel decision.

## Sentinel rules

1. Health is multi-dimensional. One healthy dimension never implies overall capability health.
2. `Connection: HEALTHY` plus `Permission: DENIED` resolves to `PERMISSION_CHANGED` when a previously expected scope is absent or insufficient.
3. `Authentication: FAILED/EXPIRED` resolves to `AUTH_EXPIRED`, not `PERMISSION_CHANGED`, unless independent evidence shows both conditions.
4. `UNREACHABLE` is reserved for loss of observable transport/service access, not authorization denial.
5. `COMPROMISED` requires evidence; uncertainty alone becomes `THREAT_INDICATOR` or `ACCESS_BLIND_SPOT` rather than compromise by assertion.
6. A fallback is a candidate path, not proof of equivalent capability. It must pass Sentinel admission for the requested action.
7. Any transition away from HEALTHY must append evidence to the operational ledger.
8. Recovery to HEALTHY requires fresh verification of the dimension that previously failed.

## Machine-readable target

A future `capability_registry.json` entry should expose these independent fields:

```json
{
  "capability_id": "github.repository.write",
  "provider": "GitHub MCP",
  "health": "PERMISSION_CHANGED",
  "connection": "HEALTHY",
  "authentication": "HEALTHY",
  "permission": "DENIED",
  "required_scope": ["contents:write"],
  "observed_scope": ["contents:read"],
  "version_state": "HEALTHY",
  "rate_limit_state": "HEALTHY",
  "trust_state": "HEALTHY",
  "fallbacks": ["direct GitHub connector"],
  "last_verified_at": null,
  "verification_evidence": []
}
```

## Invariant

CONNECTED != AUTHENTICATED != AUTHORIZED != EXECUTABLE != VERIFIED_HEALTHY
