from fastapi import FastAPI, HTTPException, status
from schemas import RequestIn, ResponseOut, LotOut, DamageDesc, SyncResponseOut
from signature import verify_signature, calc_signature
from validators import validate_images
from jobs import vision, translate
from delivery import post_webhook
import openai_client
from tasks import submit_lots_for_processing
import asyncio
from config import settings
from utils import parse_response_output

app = FastAPI(title="Auto-Description Service")

@app.get("/")
async def read_root() -> dict[str, str]:
    """Basic root endpoint returning a welcome message."""
    return {"message": "Hello, World!"}

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint to verify service availability."""
    return {"status": "ok"}

@app.post("/api/v1/generate-descriptions")
async def generate_descriptions(req: RequestIn):
    """Generate car descriptions using OpenAI Vision and Translation APIs."""
    
    # 1. Verify signature
    try:
        verify_signature([lot.model_dump(mode='json') for lot in req.lots], req.signature)
    except HTTPException:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "invalid_signature")

    # 2. Validate image URLs
    all_imgs = [img.url.unicode_string() for lot in req.lots for img in lot.images]
    unreachable = await validate_images(all_imgs)
    if unreachable and len(unreachable) / len(all_imgs) > 0.3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "too_many_unreachable_images")

    # 3. Single lot - Synchronous mode
    if len(req.lots) == 1:
        lot = req.lots[0]
        
        # Generate English description using Vision API
        html_en = await vision.run_vision_sync(lot)
        descs = [{"language": "en", "damages": html_en}]
        
        # Parallel translation for other languages
        async def translate_to_lang(lang):
            body = translate.build_translate_body(html_en, lang)
            return await openai_client.call_responses(body)

        if len(req.languages) > 1:
            other_langs = [l for l in req.languages if l != "en"]
            translation_tasks = [translate_to_lang(lang) for lang in other_langs]
            translation_results = await asyncio.gather(*translation_tasks)
            
            for lang, result in zip(other_langs, translation_results):
                translated_text = parse_response_output(result)
                descs.append({"language": lang, "damages": translated_text})
        
        # Build response
        response_lots = [LotOut(lot_id=lot.lot_id, descriptions=[DamageDesc(**d) for d in descs])]
        signature = calc_signature([lot.model_dump(mode='json') for lot in response_lots])
        
        return SyncResponseOut(signature=signature, lots=response_lots)

    # 4. Multiple lots - Asynchronous mode (Celery)
    else:
        # Submit lots to Celery for background processing
        lots_data = []
        for lot in req.lots:
            lot_data = {
                "lot_id": lot.lot_id,
                "webhook": req.webhook.unicode_string(),
                "additional_info": lot.additional_info,
                "images": [{"url": img.url.unicode_string()} for img in lot.images],
                "languages": req.languages
            }
            lots_data.append(lot_data)
        
        submit_lots_for_processing.delay(lots_data)
        
        return {"status": "accepted", "message": "Lots submitted for processing"}

@app.middleware("http")
async def validate_content_type(request, call_next):
    """Ensure content-type is exactly application/json for POST requests."""
    if request.method == "POST" and request.url.path.startswith("/api/v1/"):
        content_type = request.headers.get("content-type", "")
        if content_type != "application/json":
            from fastapi.responses import JSONResponse
            return JSONResponse(
                status_code=400, 
                content={"detail": "unsupported_media_type"}
            )
    
    response = await call_next(request)
    return response
