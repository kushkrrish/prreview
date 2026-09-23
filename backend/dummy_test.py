"""Smoke tests for the FastAPI app."""

import hashlib
import hmac

from fastapi.testclient import TestClient

from backend.main import app
from backend.settings import settings

client = TestClient(app)


def test_root_route() -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_health_route() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_github_webhook_rejects_invalid_signature() -> None:
    payload = b'{"action": "opened", "number": 1}'
    bad_signature = "sha256=" + "0" * 64

    response = client.post(
        "/webhooks/github",
        data=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": bad_signature,
        },
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid HMAC Signature"


def test_github_webhook_accepts_valid_signature_for_opened_pr(monkeypatch) -> None:
    class FakeRedis:
        async def enqueue_job(self, *_args):
            return "test-job"

    async def fake_create_pool(_settings):
        return FakeRedis()

    monkeypatch.setattr("backend.main.create_pool", fake_create_pool)
    payload = (
        b'{"action": "opened", "number": 1, '
        b'"repository": {"full_name": "owner/repo"}, '
        b'"installation": {"id": 123}}'
    )
    secret = "test-secret"
    monkeypatch.setattr(settings, "GITHUB_WEBHOOK_SECRET", secret)
    signature = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    response = client.post(
        "/webhooks/github",
        data=payload,
        headers={
            "X-GitHub-Event": "pull_request",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
