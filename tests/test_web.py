"""Tests for the FastAPI web dashboard."""

import pytest
from fastapi.testclient import TestClient

from src.web.app import app, _cache

client = TestClient(app)


def _reset_cache():
    _cache["results"] = {}
    _cache["last_run"] = None
    _cache["running"] = False


def test_health():
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_dashboard_empty():
    _reset_cache()
    resp = client.get("/")
    assert resp.status_code == 200
    assert "No results yet" in resp.text


def test_results_empty():
    _reset_cache()
    resp = client.get("/results")
    assert resp.status_code == 200
    data = resp.json()
    assert data["results"] == {}
    assert data["running"] is False


def test_results_agent_not_found():
    _reset_cache()
    resp = client.get("/results/nonexistent")
    assert resp.status_code == 404


def test_results_agent_found():
    _reset_cache()
    _cache["results"]["financial"] = {"success": True, "data": {"quotes": []}, "error": None}
    resp = client.get("/results/financial")
    assert resp.status_code == 200
    assert resp.json()["success"] is True


def test_dashboard_shows_results():
    _reset_cache()
    _cache["results"]["financial"] = {"success": True, "data": {}, "error": None}
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Financial" in resp.text
