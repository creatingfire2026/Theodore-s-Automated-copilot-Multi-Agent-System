import logging

from sentinel import ActionRequest, Decision, Sentinel, TestResult


def req(**kw):
    kw.setdefault("aud", "sentinel")
    return ActionRequest("agent", "test", ["demo"], kw.pop("authority", "policy"), **kw)


def test_low_risk_authorizes():
    result = Sentinel().authorize(req())
    assert result.decision is Decision.AUTHORIZED


def test_high_risk_requires_human():
    result = Sentinel().authorize(req(risk="high"))
    assert result.decision is Decision.HUMAN_REVIEW


def test_high_risk_can_be_approved():
    result = Sentinel().authorize(req(risk="critical"), human_approved=True)
    assert result.decision is Decision.AUTHORIZED


def test_missing_authority_is_blocked():
    result = Sentinel().authorize(req(authority=""))
    assert result.decision is Decision.BLOCKED


def test_verification_failure_stays_failed():
    sentinel = Sentinel()
    authorized = sentinel.authorize(req())
    result = sentinel.verify(authorized, success=False)
    assert result.decision is Decision.FAILED


# --- AIP-001 amendment: audience ---------------------------------------------------


def test_missing_audience_is_blocked_and_logged(caplog):
    with caplog.at_level(logging.WARNING, logger="sentinel"):
        result = Sentinel().authorize(req(aud=""))
    assert result.decision is Decision.BLOCKED
    assert result.reason == "missing audience (aud)"
    assert "missing audience" in caplog.text


def test_wrong_audience_is_blocked_with_reason(caplog):
    with caplog.at_level(logging.WARNING, logger="sentinel"):
        result = Sentinel("eth-desk").authorize(req(aud="aether-sentinel"))
    assert result.decision is Decision.BLOCKED
    assert "'aether-sentinel'" in result.reason and "'eth-desk'" in result.reason
    assert "wrong audience" in caplog.text


def test_audience_is_checked_before_human_approval():
    result = Sentinel("eth-desk").authorize(req(aud="other", risk="critical"), human_approved=True)
    assert result.decision is Decision.BLOCKED


def test_matching_audience_authorizes():
    assert Sentinel("eth-desk").authorize(req(aud="eth-desk")).decision is Decision.AUTHORIZED


def test_rejections_reach_the_tombstone_hook():
    graves = []
    sentinel = Sentinel("eth-desk", on_reject=lambda r, d: graves.append((r.trace_id, d.reason)))
    request = req(aud="someone-else")
    sentinel.authorize(request)
    assert graves == [(request.trace_id, "wrong audience: envelope addressed to 'someone-else', receiver is 'eth-desk'")]


def test_empty_agent_id_is_refused():
    try:
        Sentinel("")
    except ValueError:
        return
    raise AssertionError("Sentinel('') should raise")


# --- AIP-001 amendment: test-result attestation ------------------------------------


def test_only_success_counts_as_verified():
    sentinel = Sentinel()
    authorized = sentinel.authorize(req())
    result = sentinel.verify(authorized, True, TestResult("42774884628", "success"))
    assert result.decision is Decision.VERIFIED
    assert "42774884628" in result.reason


def test_startup_failure_is_not_verified():
    # PR #17's CI runs ended in startup_failure before any job ran.
    sentinel = Sentinel()
    authorized = sentinel.authorize(req())
    result = sentinel.verify(authorized, True, TestResult("42774884628", "startup_failure"))
    assert result.decision is Decision.FAILED
    assert "startup_failure" in result.reason


def test_missing_attestation_is_not_verified():
    sentinel = Sentinel()
    authorized = sentinel.authorize(req())
    assert sentinel.verify(authorized, True).decision is Decision.FAILED
    assert sentinel.verify(authorized, True, TestResult("", "success")).decision is Decision.FAILED


def test_attestation_can_ride_on_the_request_and_failures_are_tombstoned():
    graves = []
    sentinel = Sentinel(on_reject=lambda r, d: graves.append(d.reason))
    request = req(test_result=TestResult("123", "failure"))
    authorized = sentinel.authorize(request)
    result = sentinel.verify(authorized, True, request=request)
    assert result.decision is Decision.FAILED
    assert graves == ["test run 123 concluded 'failure', not 'success'"]
    ok = req(test_result=TestResult("124", "success"))
    assert sentinel.verify(sentinel.authorize(ok), True, request=ok).decision is Decision.VERIFIED
