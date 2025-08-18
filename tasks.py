from celery_app import celery
from config import settings
from jobs import vision, translate
from delivery import post_webhook
from openai_client import start_batch, retrieve_batch, file_client
import openai_client
import redis
import json
import asyncio
from utils import parse_response_output
from signature import calc_signature
from schemas import LotOut, DamageDesc, ResponseOut

redis_client = redis.from_url(settings.redis_url)

VISION_PENDING_QUEUE = "vision_pending_queue"
TRANSLATE_PENDING_QUEUE = "translate_pending_queue"
ACTIVE_BATCH_COUNT = "active_batch_count"
BATCH_TO_CUSTOM_IDS = "batch_to_custom_ids"

async def _process_queue_async(queue_name: str, endpoint: str, job_type: str):
    lines_to_process = []
    custom_id_map = {}
    
    while len(lines_to_process) < settings.max_lines_per_batch:
        task_data = redis_client.lpop(queue_name)
        if not task_data:
            break
        
        task = json.loads(task_data)
        
        if job_type == "vision":
            lot_id = task['lot_id']
            body = vision.build_vision_body_from_data(task)
            lines_to_process.append({"custom_id": lot_id, "method": "POST", "url": endpoint, "body": body})
            custom_id_map[lot_id] = task
        elif job_type == "translate":
            custom_id = task['custom_id']
            body = translate.build_translate_body(task['text'], task['lang'])
            lines_to_process.append({"custom_id": custom_id, "method": "POST", "url": endpoint, "body": body})
            custom_id_map[custom_id] = task

    if not lines_to_process:
        return

    print(f"Starting {job_type} batch with {len(lines_to_process)} items.")
    batch_id = await start_batch(lines_to_process, endpoint, custom_id=f"{job_type}_batch")
    
    redis_client.incr(ACTIVE_BATCH_COUNT)

    # Store job_type along with the custom_id_map
    redis_data = {
        "job_type": job_type,
        "custom_id_map": custom_id_map
    }
    redis_client.set(f"{BATCH_TO_CUSTOM_IDS}:{batch_id}", json.dumps(redis_data))

    print(f"Started {job_type} batch {batch_id}.")

async def _check_batch_status_async():
    active_batch_ids = [
        key.decode().split(':', 1)[1]
        for key in redis_client.scan_iter(f"{BATCH_TO_CUSTOM_IDS}:*")
    ]
    if not active_batch_ids:
        return

    tasks = [retrieve_batch(batch_id) for batch_id in active_batch_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for i, result in enumerate(results):
        batch_id = active_batch_ids[i]
        if isinstance(result, Exception):
            print(f"Error retrieving batch {batch_id}: {result}. Deleting key.")
            redis_client.delete(f"{BATCH_TO_CUSTOM_IDS}:{batch_id}") # Удаляем битый ключ
            continue
        
        if result.status in ['completed', 'failed', 'expired', 'cancelled']:
            handle_completed_batch.delay(result.id, result.status)

async def _handle_completed_batch_async(batch_id: str, status: str):
    print(f"Handling completed batch {batch_id} with status {status}")
    redis_client.decr(ACTIVE_BATCH_COUNT)
    batch_key = f"{BATCH_TO_CUSTOM_IDS}:{batch_id}"
    custom_id_map_json = redis_client.get(batch_key)
    if not custom_id_map_json:
        return
    
    redis_data = json.loads(custom_id_map_json)
    job_type = redis_data.get("job_type")
    custom_id_map = redis_data.get("custom_id_map", {})

    batch = await retrieve_batch(batch_id)

    # 1. Обработка УСПЕШНЫХ результатов
    if batch.output_file_id:
        print(f"Processing successes from output_file_id: {batch.output_file_id}")
        content = await file_client.files.content(batch.output_file_id)
        results = {json.loads(line)['custom_id']: parse_response_output(json.loads(line)['response']['body']) for line in content.iter_lines()}

        if job_type == 'vision':
            for lot_id, html_en in results.items():
                original_lot = custom_id_map.get(lot_id, {})
                redis_client.set(f"result:{lot_id}:en", html_en)
                for lang in original_lot.get('languages', []):
                    if lang != 'en':
                        task = {"custom_id": f"tr:{lot_id}:{lang}", "text": html_en, "lang": lang, "original_lot": original_lot}
                        redis_client.rpush(TRANSLATE_PENDING_QUEUE, json.dumps(task))
                _check_and_send_webhook_if_ready(lot_id, original_lot)
        elif job_type == 'translate':
            for custom_id, translated_text in results.items():
                _, lot_id, lang = custom_id.split(":")
                redis_client.set(f"result:{lot_id}:{lang}", translated_text)
                _check_and_send_webhook_if_ready(lot_id, custom_id_map[custom_id]['original_lot'])

    # 2. Обработка ОШИБОЧНЫХ результатов
    if batch.error_file_id:
        print(f"Processing errors from error_file_id: {batch.error_file_id}")
        error_content = await file_client.files.content(batch.error_file_id)
        for line in error_content.iter_lines():
            if not line: continue
            error_data = json.loads(line)
            custom_id = error_data.get('custom_id')
            error_message = error_data.get('response', {}).get('body', {}).get('error', {}).get('message', 'Unknown processing error')

            if not custom_id: continue
            original_lot = custom_id_map.get(custom_id)
            if not original_lot or not original_lot.get('webhook'): continue

            error_response = {
                "lots": [{
                    "lot_id": custom_id,
                    "error": {"message": error_message, "code": "processing_failed"}
                }]
            }
            error_signature = calc_signature(error_response["lots"])
            error_response["version"] = "1.0.0"
            error_response["signature"] = error_signature
            post_webhook_task.delay(original_lot['webhook'], error_response)

    redis_client.delete(batch_key)

def _check_and_send_webhook_if_ready(lot_id, original_lot):
    languages = original_lot.get('languages', [])
    if not languages:
        return

    results = redis_client.mget([f"result:{lot_id}:{lang}" for lang in languages])
    if all(r is not None for r in results):
        descriptions = [{"language": lang, "damages": res.decode()} for lang, res in zip(languages, results)]
        response_lots = [LotOut(lot_id=lot_id, descriptions=[DamageDesc(**d) for d in descriptions]).model_dump()]
        signature = calc_signature(response_lots)
        out = ResponseOut(signature=signature, lots=response_lots).model_dump()
        post_webhook_task.delay(original_lot['webhook'], out)

@celery.task(name="tasks.process_single_lot_immediately")
def process_single_lot_immediately(lot_data: dict):
    """Process a single lot immediately using direct OpenAI API calls (no batch)."""
    asyncio.run(_process_single_lot_async(lot_data))

async def _process_single_lot_async(lot_data: dict):
    """Async function to process a single lot directly via OpenAI API."""
    try:
        # 1. Generate English description using Vision API
        html_en = await _call_vision_direct(lot_data)
        
        # Store English result
        lot_id = lot_data['lot_id']
        redis_client.set(f"result:{lot_id}:en", html_en)
        
        # 2. Generate translations for other languages
        languages = lot_data.get('languages', [])
        other_langs = [lang for lang in languages if lang != 'en']
        
        if other_langs:
            # Parallel translation requests
            translation_tasks = [_call_translate_direct(html_en, lang) for lang in other_langs]
            translation_results = await asyncio.gather(*translation_tasks)
            
            # Store translation results
            for lang, translated_text in zip(other_langs, translation_results):
                redis_client.set(f"result:{lot_id}:{lang}", translated_text)
        
        # 3. Send webhook with complete results
        _check_and_send_webhook_if_ready(lot_id, lot_data)
        
    except asyncio.TimeoutError as e:
        print(f"Timeout processing single lot {lot_data.get('lot_id')}: {e}")
        # Send timeout error webhook
        error_response = {
            "lots": [{
                "lot_id": lot_data.get('lot_id'),
                "error": {"message": "Processing timeout - vision analysis took too long", "code": "timeout_error"}
            }]
        }
        error_signature = calc_signature(error_response["lots"])
        error_response["version"] = "1.0.0"
        error_response["signature"] = error_signature
        post_webhook_task.delay(lot_data.get('webhook'), error_response)
    except Exception as e:
        print(f"Error processing single lot {lot_data.get('lot_id')}: {e}")
        # Send general error webhook
        error_response = {
            "lots": [{
                "lot_id": lot_data.get('lot_id'),
                "error": {"message": str(e), "code": "processing_failed"}
            }]
        }
        error_signature = calc_signature(error_response["lots"])
        error_response["version"] = "1.0.0"
        error_response["signature"] = error_signature
        post_webhook_task.delay(lot_data.get('webhook'), error_response)

async def _call_vision_direct(lot_data: dict) -> str:
    """Direct Vision API call for single lot."""
    body = vision.build_vision_body_from_data(lot_data)
    result = await openai_client.call_responses(body)
    return parse_response_output(result)

async def _call_translate_direct(text: str, lang: str) -> str:
    """Direct Translation API call."""
    body = translate.build_translate_body(text, lang)
    result = await openai_client.call_responses(body)
    return parse_response_output(result)

@celery.task(name="tasks.submit_lots_for_processing")
def submit_lots_for_processing(lots: list[dict]):
    for lot in lots:
        redis_client.rpush(VISION_PENDING_QUEUE, json.dumps(lot))

@celery.task(name="tasks.orchestrator_task")
def orchestrator_task():
    active_batches = int(redis_client.get(ACTIVE_BATCH_COUNT) or 0)
    if active_batches >= settings.active_batch_limit:
        return

    # Все задачи теперь используют один и тот же эндпоинт
    endpoint = "/v1/responses"

    if redis_client.llen(TRANSLATE_PENDING_QUEUE) > 0:
        queue_to_process = TRANSLATE_PENDING_QUEUE
        job_type = "translate"
    elif redis_client.llen(VISION_PENDING_QUEUE) > 0:
        queue_to_process = VISION_PENDING_QUEUE
        job_type = "vision"
    else:
        return

    asyncio.run(_process_queue_async(queue_to_process, endpoint, job_type))

@celery.task(name="tasks.check_batch_status_task")
def check_batch_status_task():
    asyncio.run(_check_batch_status_async())

@celery.task(name="tasks.handle_completed_batch")
def handle_completed_batch(batch_id: str, status: str):
    asyncio.run(_handle_completed_batch_async(batch_id, status))

@celery.task(name="tasks.post_webhook_task")
def post_webhook_task(url: str, data: dict):
    asyncio.run(post_webhook(url, data))
