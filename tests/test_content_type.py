import os
from fastapi.testclient import TestClient

# Set required environment variables before importing app
os.environ.setdefault("openai_api_key", "test")
os.environ.setdefault("shared_key", "test")

from app import app

client = TestClient(app)


def test_generate_rejects_non_json_content_type():
    payload = {
        "version": "1.0.0",
        "languages": ["en"],
        "lots": [
            {
                "webhook": "http://example.com",
                "lot_id": "1",
                "images": [{"url": "http://example.com/img.jpg"}]
            }
        ],
        "signature": "dummy"
    }
    headers = {"content-type": "application/json; charset=utf-8"}
    response = client.post("/api/v1/generate-descriptions", json=payload, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "unsupported_media_type"}
