import httpx
from config import settings
from utils import backoff

async def post_webhook(url: str, payload: dict):
    last_error = None
    last_status_code = None
    
    for attempt in range(settings.max_retries):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(url, json=payload)
                if r.status_code in range(200, 300):
                    return
                last_status_code = r.status_code
                last_error = r.text
        except Exception as e:
            last_error = str(e)
            last_status_code = None
        await backoff(attempt)
    
    error_msg = f"webhook_delivery_failed to {url}"
    if last_status_code:
        error_msg += f" - HTTP {last_status_code}"
    if last_error:
        error_msg += f" - {last_error}"
    raise RuntimeError(error_msg)
