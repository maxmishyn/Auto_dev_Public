import httpx, asyncio
from config import settings
from fastapi import HTTPException
import logging
from typing import List, Set
from contextlib import asynccontextmanager

logger = logging.getLogger(__name__)

_IMAGE_HEADERS = {"User-Agent": "LotVision/1.0"}

_validation_client: httpx.AsyncClient = None

def _create_validation_client() -> httpx.AsyncClient:
    """Create optimized HTTP client for image validation."""
    return httpx.AsyncClient(
        limits=httpx.Limits(
            max_connections=50,        # Max total connections
            max_keepalive_connections=20,  # Keep connections alive
        ),
        timeout=httpx.Timeout(
            connect=1.0,              # Reduced from 3s to 1s
            read=2.0,                 # Quick read timeout
            write=5.0,                # Write timeout
            pool=5.0                  # Pool timeout
        ),
        follow_redirects=True,
        headers=_IMAGE_HEADERS,
        http2=True                    # Enable HTTP/2 for better performance
    )

@asynccontextmanager
async def get_validation_client():
    """Context manager for getting the global validation client."""
    global _validation_client
    if _validation_client is None:
        _validation_client = _create_validation_client()

    try:
        yield _validation_client
    finally:
        pass

async def _check_single_optimized(url: str, client: httpx.AsyncClient, semaphore: asyncio.Semaphore) -> bool:
    """Optimized single image validation with concurrency control."""
    async with semaphore:  # Limit concurrent requests
        try:
            response = await client.head(url)

            if not (200 <= response.status_code < 300):
                return False

            content_type = response.headers.get("content-type", "")
            if not content_type.startswith("image/"):
                return False

            content_length = response.headers.get("content-length")
            if content_length and int(content_length) > 10_485_760:  # 10MB limit
                return False

            return True

        except (httpx.TimeoutException, httpx.ConnectTimeout):
            logger.debug(f"Timeout validating image: {url}")
            return False
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.debug(f"HTTP error validating image {url}: {e}")
            return False
        except Exception as e:
            logger.warning(f"Unexpected error validating image {url}: {e}")
            return False

async def validate_images_optimized(urls: List[str], max_concurrent: int = 25) -> List[str]:
    """Optimized imgae validation with connection pooling and concurrency control.

    Args:
        urls: List of image URLs to validate
        max_concurrent: Maximum concurrent requests (default: 25)

    Returns:
        List of unreachable/invalid URLs
    """
    if not urls:
        return []

    seen: Set[str] = set()
    unique_urls = []
    for url in urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)

    logger.info(f"Validating {len(unique_urls)} unique images (reduced from {len(urls)})")

    semaphore = asyncio.Semaphore(max_concurrent)

    async with get_validation_client() as client:
        tasks = [
            _check_single_optimized(url, client, semaphore)
            for url in unique_urls
        ]

        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            logger.error(f"Error during batch image validation: {e}")
            # Fallback: assume all images are invalid
            return urls

    unreachable = []
    for url, result in zip(unique_urls, results):
        if isinstance(result, Exception):
            logger.warning(f"Exception validating {url}: {result}")
            unreachable.append(url)
        elif not result:  # result is False
            unreachable.append(url)

    unreachable_set = set(unreachable)
    original_unreachable = [url for url in urls if url in unreachable_set]

    logger.info(f"Found {len(original_unreachable)} unreachable images out of {len(urls)}")
    return original_unreachable

# Old code for backward compat
async def validate_images(urls: list[str]) -> list[str]:
    """Old image validation function - redirects to optimized version."""
    return await validate_images_optimized(urls)

# Clean up function to be called on app shutdown
async def cleanup_validation_client():
    """Clean up the global validation client."""
    global _validation_client
    if _validation_client is not None:
        try:
            await _validation_client.aclose()
        except RuntimeError:
            # can ignore this error
            pass
        finally:
            _validation_client = None


def assert_batch_limits(jsonl_size: int, line_count: int, lines_data: list[str]):
    if line_count > settings.max_lines_per_batch:
        raise HTTPException(status_code=400, detail="batch_lines_limit")
    if jsonl_size > settings.file_size_limit:
        raise HTTPException(status_code=400, detail="batch_size_limit")
    for line in lines_data:
        if len(line.encode("utf-8")) > settings.line_size_limit:
            raise HTTPException(status_code=400, detail="line_size_limit")
