from config import settings
from schemas import LotIn
import openai_client
from utils import parse_response_output
from .prompt import vision_prompt

def build_vision_body_from_data(lot_data: dict) -> dict:
    """Формирует тело запроса для Vision API, эндпоинт /v1/responses."""
    images = [
        {"type": "input_image", "image_url": img['url'], "detail": "low"}
        for img in lot_data['images']
    ]
    user_text = (
        "Текст объявления который был предоставлен вместе с фотографиями, "
        "Относитесь к тексту объявления критически...\n\n"
        f"Описание пользователя: {lot_data.get('additional_info') or ''}"
    )
    return {
        "model": settings.vision_model,
        "reasoning": {"effort": "medium"},
        "input": [
            {"role": "system", "content": vision_prompt},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}, *images]},
        ],
    }

async def build_vision_body(lot: LotIn) -> dict:
    images = [
        {"type": "input_image", "image_url": img.url.unicode_string(), "detail": "low"}
        for img in lot.images
    ]
    user_text = (
        "Текст объявления который был предоставлен вместе с фотографиями, "
        "Относитесь к тексту объявления критически...\n\n"
        f"Описание пользователя: {lot.additional_info or ''}"
    )
    return {
        "model": settings.vision_model,
        "reasoning": {"effort": "medium"},
        "input": [
            {"role": "system", "content": vision_prompt},
            {"role": "user", "content": [{"type": "input_text", "text": user_text}, *images]},
        ],
    }

async def run_vision_sync(lot: LotIn) -> str:      # → английский HTML
    body = await build_vision_body(lot)
    result = await openai_client.call_responses(body)
    print(f"VISION_API_RESPONSE: {result}")
    return parse_response_output(result)
