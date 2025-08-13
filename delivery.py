import httpx
from config import settings
from utils import backoff

async def post_webhook(url: str, payload: dict):
    for attempt in range(settings.max_retries):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json=payload)
                if r.status_code in range(200, 300):
                    return
        except Exception:
            pass
        await backoff(attempt)
    raise RuntimeError("webhook_delivery_failed")
