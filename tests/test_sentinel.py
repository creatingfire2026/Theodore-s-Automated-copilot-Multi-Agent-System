from datetime import datetime, timedelta, timezone

from sentinel import ActionRequest, AuthorityGrant, Decision, Sentinel


def make_grant(
    *,
    actor_id="agent",
    actions=("execute",),
    scope=("demo",),
    risk_ceiling="critical",
    expires_at=None,
):
    return AuthorityGrant(
        grant_id="grant-001",
        actor_id=actor_id,
        allowed_actions=actions,
        allowed_scope=scope,
        risk_ceiling=risk_ceiling,
        expires_at=expires_at or datetime.now(timezone.utc) + timedelta(hours=1),
    )


def make_request(**overrides):
    values = {
        "actor": "agent",
        "intent": "test bounded action",
        "scope": ["demo"],
        "authority": "policy-v1",
        "risk": "low",
        "grant": make_grant(),
        "idempotency_key": "action-001",
    }
    values.update(overrides)
    return ActionRequest(**values)


def test_valid_low_risk_request_authorizes():
    result = Sentinel().authorize(make_request())
    assert result.decision is Decision.AUTHORIZED


def test_high_risk_requires_explicit_human_approval_reference():
    sentinel = Sentinel()
    request = make_request(risk="high", idempotency_key="high-1")
    result = sentinel.authorize(request, human_approved=True)
    assert result.decision is Decision.HUMAN_REVIEW

    approved_request = make_request(risk="high", idempotency_key="high-2")
    approved = sentinel.authorize(
        approved_request, human_approved=True, approval_ref="approval-ticket-42"
    )
    assert approved.decision is Decision.AUTHORIZED


def test_missing_actor_is_blocked():
    result = Sentinel().authorize(make_request(actor="  "))
    assert result.decision is Decision.BLOCKED
    assert result.reason == "missing actor identity"


def test_missing_scope_is_blocked():
    result = Sentinel().authorize(make_request(scope=[]))
    assert result.decision is Decision.BLOCKED


def test_invalid_risk_label_is_blocked():
    result = Sentinel().authorize(make_request(risk="supercritical"))
    assert result.decision is Decision.BLOCKED
    assert result.reason == "invalid risk label"


def test_missing_grant_is_blocked_even_if_legacy_authority_string_exists():
    result = Sentinel().authorize(make_request(grant=None, authority="policy-v1"))
    assert result.decision is Decision.BLOCKED
    assert "explicit authority grant" in result.reason


def test_grant_for_another_actor_is_blocked():
    result = Sentinel().authorize(make_request(grant=make_grant(actor_id="other")))
    assert result.decision is Decision.BLOCKED


def test_scope_outside_grant_is_blocked():
    result = Sentinel().authorize(make_request(scope=["demo", "production"]))
    assert result.decision is Decision.BLOCKED


def test_action_outside_grant_is_blocked():
    result = Sentinel().authorize(make_request(action="deploy"))
    assert result.decision is Decision.BLOCKED


def test_risk_above_grant_ceiling_is_blocked():
    result = Sentinel().authorize(
        make_request(risk="high", grant=make_grant(risk_ceiling="medium"))
    )
    assert result.decision is Decision.BLOCKED


def test_expired_grant_is_blocked():
    expired = datetime.now(timezone.utc) - timedelta(seconds=1)
    result = Sentinel().authorize(make_request(grant=make_grant(expires_at=expired)))
    assert result.decision is Decision.BLOCKED
    assert "expired" in result.reason


def test_naive_grant_expiry_is_blocked_fail_closed():
    result = Sentinel().authorize(
        make_request(grant=make_grant(expires_at=datetime(2099, 1, 1)))
    )
    assert result.decision is Decision.BLOCKED


def test_stale_preconditions_are_blocked():
    result = Sentinel().authorize(make_request(preconditions_valid=False))
    assert result.decision is Decision.BLOCKED
    assert "preconditions" in result.reason


def test_missing_idempotency_key_is_blocked():
    result = Sentinel().authorize(make_request(idempotency_key=""))
    assert result.decision is Decision.BLOCKED


def test_duplicate_idempotency_key_cannot_repeat_authorized_action():
    sentinel = Sentinel()
    first = sentinel.authorize(make_request())
    second = sentinel.authorize(make_request())
    assert first.decision is Decision.AUTHORIZED
    assert second.decision is Decision.BLOCKED
    assert "already used" in second.reason


def test_denied_key_cannot_be_reused_to_bypass_denial():
    sentinel = Sentinel()
    denied = sentinel.authorize(make_request(grant=None))
    retry = sentinel.authorize(make_request(grant=make_grant()))
    assert denied.decision is Decision.BLOCKED
    assert retry.decision is Decision.BLOCKED
    assert "already used" in retry.reason


def test_verification_failure_is_not_success():
    sentinel = Sentinel()
    authorized = sentinel.authorize(make_request())
    result = sentinel.verify(authorized, success=False)
    assert result.decision is Decision.FAILED


def test_verification_does_not_authorize_blocked_request():
    sentinel = Sentinel()
    blocked = sentinel.authorize(make_request(grant=None))
    assert sentinel.verify(blocked, success=True) is blocked
