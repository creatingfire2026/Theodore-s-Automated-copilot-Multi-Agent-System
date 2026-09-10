from sentinel import ActionRequest, Decision, Sentinel


def test_low_risk_authorizes():
    result = Sentinel().authorize(
        ActionRequest("agent", "test", ["demo"], "policy")
    )
    assert result.decision is Decision.AUTHORIZED


def test_high_risk_requires_human():
    result = Sentinel().authorize(
        ActionRequest("agent", "test", ["demo"], "policy", risk="high")
    )
    assert result.decision is Decision.HUMAN_REVIEW


def test_high_risk_can_be_approved():
    result = Sentinel().authorize(
        ActionRequest("agent", "test", ["demo"], "policy", risk="critical"),
        human_approved=True,
    )
    assert result.decision is Decision.AUTHORIZED


def test_missing_authority_is_blocked():
    result = Sentinel().authorize(
        ActionRequest("agent", "test", ["demo"], "")
    )
    assert result.decision is Decision.BLOCKED


def test_verification_failure_stays_failed():
    sentinel = Sentinel()
    authorized = sentinel.authorize(
        ActionRequest("agent", "test", ["demo"], "policy")
    )
    result = sentinel.verify(authorized, success=False)
    assert result.decision is Decision.FAILED
