from openai import AsyncOpenAI, APIStatusError
from typing import Dict
from config import settings
from utils import backoff
import aiofiles, uuid, json, os, tempfile
from validators import assert_batch_limits

client = AsyncOpenAI(
    base_url=settings.openai_base_url,
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout,
)

file_client = AsyncOpenAI(
    # Official base includes `/v1`; resource helpers send paths like "/files"
    base_url="https://api.openai.com/v1",
    api_key=settings.openai_api_key,
    timeout=settings.openai_timeout,
)

async def call_responses(body: dict) -> dict:
    for attempt in range(settings.max_retries):
        try:
            response = await client.post("/v1/responses", body=body, cast_to=Dict)
            return response
        except APIStatusError as e:
            if e.status_code in {429, 500, 502, 503, 504}:
                await backoff(attempt)
                continue
            raise
    raise RuntimeError("OpenAI max retries reached")

async def start_batch(lines: list[dict], endpoint: str, custom_id: str | None = None) -> str:   # → batch_id
    tmp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".jsonl")
    tmp_path = tmp_file.name
    tmp_file.close()

    serialized_lines = [json.dumps(line, separators=(",", ":")) for line in lines]

    try:
        async with aiofiles.open(tmp_path, "w", encoding="utf-8") as f:
            for raw in serialized_lines:
                await f.write(raw + "\n")

        size = os.path.getsize(tmp_path)
        assert_batch_limits(size, len(lines), serialized_lines)

        # 1. upload
        with open(tmp_path, "rb") as f:
            # Use the official OpenAI endpoint for file upload
            file_obj = await file_client.files.create(
                file=f,
                purpose="batch",
            )

        # 2. create batch (also through the official endpoint)
        batch = await file_client.batches.create(
            input_file_id=file_obj.id,
            endpoint=endpoint,
            completion_window="24h",
            metadata={"custom_id": custom_id} if custom_id else None,
        )
        return batch.id
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


async def retrieve_batch(batch_id: str):
    """Fetch batch status from the official endpoint."""
    return await file_client.batches.retrieve(batch_id)
