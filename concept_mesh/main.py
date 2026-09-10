"""HTTP service exposing the Sentinel control-plane primitives."""

from fastapi import FastAPI
from pydantic import BaseModel, Field

from sentinel import ActionRequest, Decision, Sentinel

app = FastAPI(title="Sentinel Control Plane", version="0.1.0")
sentinel = Sentinel()


class ActionPayload(BaseModel):
    actor: str
    intent: str
    scope: list[str] = Field(min_length=1)
    authority: str
    risk: str = "low"
    preconditions: list[str] = Field(default_factory=list)
    evidence: list[object] = Field(default_factory=list)
    human_approved: bool = False


class VerifyPayload(BaseModel):
    trace_id: str
    decision: str
    reason: str
    success: bool


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "sentinel"}


@app.post("/v1/actions/authorize")
def authorize(payload: ActionPayload) -> dict[str, str]:
    request = ActionRequest(
        actor=payload.actor,
        intent=payload.intent,
        scope=payload.scope,
        authority=payload.authority,
        risk=payload.risk,
        preconditions=payload.preconditions,
        evidence=payload.evidence,
    )
    result = sentinel.authorize(request, human_approved=payload.human_approved)
    return {
        "trace_id": result.trace_id,
        "decision": result.decision.value,
        "reason": result.reason,
    }


@app.post("/v1/actions/verify")
def verify(payload: VerifyPayload) -> dict[str, str]:
    try:
        decision = Decision(payload.decision)
    except ValueError:
        decision = Decision.BLOCKED
    result = sentinel.verify(
        type("DecisionRecordLike", (), {
            "trace_id": payload.trace_id,
            "decision": decision,
            "reason": payload.reason,
        })(),
        success=payload.success,
    )
    return {
        "trace_id": result.trace_id,
        "decision": result.decision.value,
        "reason": result.reason,
    }
