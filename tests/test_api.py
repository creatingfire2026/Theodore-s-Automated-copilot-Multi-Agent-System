from fastapi.testclient import TestClient

from concept_mesh.main import app


client = TestClient(app)


def test_health():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_authorize():
    response = client.post(
        "/v1/actions/authorize",
        json={
            "actor": "termux-agent",
            "intent": "bounded test action",
            "scope": ["demo"],
            "authority": "test-policy",
        },
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "authorized"
