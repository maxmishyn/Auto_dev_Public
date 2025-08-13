import os
from fastapi.testclient import TestClient

# Set required environment variables before importing app and others
os.environ.setdefault("openai_api_key", "test")
os.environ.setdefault("shared_key", "test")

from app import app
from signature import calc_signature
from schemas import LotIn

client = TestClient(app)

def test_sync_response_has_valid_signature(monkeypatch):
    async def mock_validate_images(urls):
        return []
    async def mock_call_responses(body):
        return {"choices": [{"message": {"content": "<p>Damage</p>"}}]}
    monkeypatch.setattr("app.validate_images", mock_validate_images)
    monkeypatch.setattr("app.call_responses", mock_call_responses)

    lot = {
        "webhook": "http://example.com",
        "lot_id": "1",
        "images": [{"url": "http://example.com/img.jpg"}]
    }
    payload = {
        "version": "1.0.0",
        "languages": ["en"],
        "lots": [lot]
    }
    payload["signature"] = calc_signature([LotIn(**lot)])

    response = client.post(
        "/api/v1/generate-descriptions",
        json=payload,
        headers={"content-type": "application/json"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["signature"]
    assert data["signature"] == calc_signature(data["lots"])
