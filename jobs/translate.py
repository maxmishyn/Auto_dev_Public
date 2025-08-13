from config import settings


def build_translate_body(text_en: str, lang: str) -> dict:
    """Construct the request body for translating HTML text.

    The function prepares a two-message conversation where the system
    instructs the model to translate provided HTML into the target language
    while preserving all markup. The original HTML is passed as the user
    message to ensure tags remain untouched.
    """
    system_message = {
        "role": "system",
        "content": (
            f"Translate the following HTML into {lang}. "
            "Preserve markup and return only translated HTML."
        ),
    }
    user_message = {"role": "user", "content": text_en}

    return {
        "model": settings.translate_model,
        "input": [system_message, user_message],
        "max_output_tokens": 4096,
        "temperature": 0,
    }

def translate_jsonl(lot_id: str, text_en: str, languages: list[str]) -> list[dict]:
    data = []
    for lang in (l for l in languages if l.lower() != "en"):
        data.append({"custom_id": f"tr:{lot_id}:{lang}", "method": "POST", "url": "/v1/responses", "body": build_translate_body(text_en, lang)})
    return data