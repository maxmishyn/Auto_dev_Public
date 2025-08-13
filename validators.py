import httpx, asyncio
from config import settings
from fastapi import HTTPException

_IMAGE_HEADERS = {"User-Agent": "LotVision/1.0"}

async def _check_single(url: str) -> bool:
    async with httpx.AsyncClient(timeout=settings.connect_timeout) as client:
        for _ in range(2):                       # ≤ 2 попытки
            try:
                r = await client.head(url, headers=_IMAGE_HEADERS, follow_redirects=True)
                if r.status_code in range(200, 300) and \
                   r.headers.get("content-type", "").startswith("image/") and \
                   int(r.headers.get("content-length", 0)) <= 10_485_760:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)               # back-off фикс. 2 s
    return False

async def validate_images(urls: list[str]) -> list[str]:  # → недоступные URL-ы
    results = await asyncio.gather(*[_check_single(u) for u in urls])
    return [u for u, ok in zip(urls, results) if not ok]


def assert_batch_limits(jsonl_size: int, line_count: int, lines_data: list[str]):
    if line_count > settings.max_lines_per_batch:
        raise HTTPException(status_code=400, detail="batch_lines_limit")
    if jsonl_size > settings.file_size_limit:
        raise HTTPException(status_code=400, detail="batch_size_limit")
    for line in lines_data:
        if len(line.encode("utf-8")) > settings.line_size_limit:
            raise HTTPException(status_code=400, detail="line_size_limit")
