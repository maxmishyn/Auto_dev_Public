from fastapi import FastAPI, HTTPException, status
from schemas import RequestIn, ResponseOut, LotOut, DamageDesc
from validators import validate_images
from jobs import vision, translate
from delivery import post_webhook
import openai_client
from tasks import submit_lots_for_processing, process_single_lot_immediately
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

@app.post("/api/v1/generate-descriptions", status_code=201)
async def generate_descriptions(req: RequestIn):
    """Generate car descriptions using OpenAI Vision and Translation APIs.
    
    Single lot: 
    - Processed immediately via direct OpenAI API calls (no batch)
    - If 'language' field specified, returns EN + priority language immediately
    - Remaining languages processed via batch system with subsequent webhooks
    
    Multiple lots: 
    - Processed via batch system with Celery orchestration
    - 'language' field ignored for multiple lots
    
    Results delivered via webhook in all cases.
    """
    
    # 1. Validate image URLs
    all_imgs = [img.url.unicode_string() for lot in req.lots for img in lot.images]
    unreachable = await validate_images(all_imgs)
    if unreachable and len(unreachable) / len(all_imgs) > 0.3:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "too_many_unreachable_images")

    # 2. Route based on lot count
    if len(req.lots) == 1:
        # Single lot: Process immediately (no batch API)
        lot = req.lots[0]
        lot_data = {
            "lot_id": lot.lot_id,
            "webhook": req.webhook.unicode_string(),
            "additional_info": lot.additional_info,
            "images": [{"url": img.url.unicode_string()} for img in lot.images],
            "languages": req.languages,
            "priority_language": req.language  # Priority language for immediate response
        }
        process_single_lot_immediately.delay(lot_data)
        return {"status": "accepted", "message": "Single lot submitted for immediate processing"}
    
    else:
        # Multiple lots: Use batch processing system
        lots_data = []
        for lot in req.lots:
            lot_data = {
                "lot_id": lot.lot_id,
                "webhook": req.webhook.unicode_string(),
                "additional_info": lot.additional_info,
                "images": [{"url": img.url.unicode_string()} for img in lot.images],
                "languages": req.languages,
                "priority_language": req.language  # Priority language (ignored for multiple lots)
            }
            lots_data.append(lot_data)
        
        submit_lots_for_processing.delay(lots_data)
        return {"status": "accepted", "message": "Multiple lots submitted for batch processing"}

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
