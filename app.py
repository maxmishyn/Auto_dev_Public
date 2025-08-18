from fastapi import FastAPI, HTTPException, status
from fastapi.responses import Response
from schemas import RequestIn, ResponseOut, LotOut, DamageDesc
from validators import validate_images, cleanup_validation_client
from jobs import vision, translate
from delivery import post_webhook
import openai_client
from tasks import submit_lots_for_processing, process_single_lot_immediately
import asyncio
from config import settings
from utils import parse_response_output
from metrics import (
    get_metrics, get_metrics_summary, track_request, track_lot_processing,
    track_image_validation, track_processing_time, track_image_validation_time,
    MetricsMiddleware, CONTENT_TYPE_LATEST
)

app = FastAPI(title="Auto-Description Service")

# Add metrics middleware
app.add_middleware(MetricsMiddleware)

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up resources on app shutdown."""
    await cleanup_validation_client()

@app.get("/")
async def read_root() -> dict[str, str]:
    """Basic root endpoint returning a welcome message."""
    return {"message": "Hello, World!"}

@app.get("/health")
async def health_check() -> dict[str, str]:
    """Simple health check endpoint to verify service availability."""
    return {"status": "ok"}

@app.get("/metrics")
async def metrics_endpoint():
    """Prometheus metrics endpoint."""
    metrics_data = get_metrics()
    return Response(content=metrics_data, media_type=CONTENT_TYPE_LATEST)

@app.get("/metrics/summary")
async def metrics_summary() -> dict:
    """Human-readable metrics summary for monitoring dashboards."""
    return get_metrics_summary()

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
    
    # Track request processing time
    with track_processing_time("generate_descriptions"):
        # 1. Validate image URLs
        all_imgs = [img.url.unicode_string() for lot in req.lots for img in lot.images]
        
        with track_image_validation_time():
            unreachable = await validate_images(all_imgs)
        
        # Track validation results
        track_image_validation("valid", len(all_imgs) - len(unreachable))
        track_image_validation("invalid", len(unreachable))
        
        if unreachable and len(unreachable) / len(all_imgs) > 0.3:
            track_request("POST /api/v1/generate-descriptions", "validation_failed")
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
        track_lot_processing("single_lot_immediate", 1)
        track_request("POST /api/v1/generate-descriptions", "accepted_single")
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
        track_lot_processing("multi_lot_batch", len(lots_data))
        track_request("POST /api/v1/generate-descriptions", "accepted_batch")
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
