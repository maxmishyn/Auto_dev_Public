"""
Prometheus metrics module for Auto-Description Service monitoring.
Provides comprehensive observability for queue depths, processing times, and system health.
"""
from prometheus_client import Gauge, Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import redis
from config import settings
import time

# Initialize metrics
queue_depth = Gauge('redis_queue_depth', 'Redis queue depth', ['queue_name'])
active_batch_count = Gauge('active_batch_count', 'Number of active OpenAI batches')
processing_time = Histogram('request_processing_seconds', 'Time spent processing requests', ['request_type'])
batch_processing_time = Histogram('batch_processing_seconds', 'Time spent processing batches', ['batch_type'])

# Counters for tracking volume
requests_total = Counter('requests_total', 'Total number of requests', ['endpoint', 'status'])
lots_processed_total = Counter('lots_processed_total', 'Total lots processed', ['processing_type'])
images_validated_total = Counter('images_validated_total', 'Total images validated', ['validation_result'])
webhooks_sent_total = Counter('webhooks_sent_total', 'Total webhooks sent', ['webhook_type'])

# Dynamic batching metrics
dynamic_interval_seconds = Gauge('dynamic_batching_interval_seconds', 'Current dynamic batching interval')
queue_depth_total = Gauge('queue_depth_total', 'Total queue depth across all queues')

# System health metrics
redis_connection_status = Gauge('redis_connection_status', 'Redis connection status (1=connected, 0=disconnected)')
openai_api_status = Gauge('openai_api_status', 'OpenAI API status (1=healthy, 0=unhealthy)')

# Performance tracking
image_validation_duration = Histogram('image_validation_duration_seconds', 'Time spent validating images')
translation_queue_wait_time = Histogram('translation_queue_wait_time_seconds', 'Time translations spend in queue')

# Queue names for monitoring
VISION_PENDING_QUEUE = "vision_pending_queue"
TRANSLATE_PENDING_QUEUE = "translate_pending_queue"
ACTIVE_BATCH_COUNT = "active_batch_count"

# Redis client for metrics collection
redis_client = redis.from_url(settings.redis_url)

def update_queue_metrics():
    """Update all queue-related metrics."""
    try:
        # Update queue depths
        vision_depth = redis_client.llen(VISION_PENDING_QUEUE)
        translate_depth = redis_client.llen(TRANSLATE_PENDING_QUEUE)
        
        queue_depth.labels(queue_name='vision_pending').set(vision_depth)
        queue_depth.labels(queue_name='translate_pending').set(translate_depth)
        queue_depth_total.set(vision_depth + translate_depth)
        
        # Update active batch count
        active_batches = int(redis_client.get(ACTIVE_BATCH_COUNT) or 0)
        active_batch_count.set(active_batches)
        
        # Update dynamic batching interval
        current_interval = redis_client.get("dynamic_batch_interval")
        if current_interval:
            dynamic_interval_seconds.set(float(current_interval))
        
        # Update Redis connection status
        redis_client.ping()
        redis_connection_status.set(1)
        
    except Exception as e:
        print(f"Error updating queue metrics: {e}")
        redis_connection_status.set(0)

def track_request(endpoint: str, status: str):
    """Track API request."""
    requests_total.labels(endpoint=endpoint, status=status).inc()

def track_lot_processing(processing_type: str, count: int = 1):
    """Track lot processing."""
    lots_processed_total.labels(processing_type=processing_type).inc(count)

def track_image_validation(validation_result: str, count: int = 1):
    """Track image validation results."""
    images_validated_total.labels(validation_result=validation_result).inc(count)

def track_webhook(webhook_type: str):
    """Track webhook sending."""
    webhooks_sent_total.labels(webhook_type=webhook_type).inc()

def track_processing_time(request_type: str):
    """Context manager to track processing time."""
    return processing_time.labels(request_type=request_type).time()

def track_batch_processing_time(batch_type: str):
    """Context manager to track batch processing time."""
    return batch_processing_time.labels(batch_type=batch_type).time()

def track_image_validation_time():
    """Context manager to track image validation time."""
    return image_validation_duration.time()

def get_metrics():
    """Get current metrics in Prometheus format."""
    # Update metrics before returning
    update_queue_metrics()
    return generate_latest()

def get_metrics_summary():
    """Get human-readable metrics summary."""
    try:
        vision_depth = redis_client.llen(VISION_PENDING_QUEUE)
        translate_depth = redis_client.llen(TRANSLATE_PENDING_QUEUE)
        total_depth = vision_depth + translate_depth
        active_batches = int(redis_client.get(ACTIVE_BATCH_COUNT) or 0)
        current_interval = redis_client.get("dynamic_batch_interval")
        interval = float(current_interval) if current_interval else 15.0
        
        return {
            "queue_metrics": {
                "vision_pending": vision_depth,
                "translate_pending": translate_depth,
                "total_queue_depth": total_depth
            },
            "batch_metrics": {
                "active_batches": active_batches,
                "max_batches": settings.active_batch_limit
            },
            "dynamic_batching": {
                "current_interval_seconds": interval,
                "load_level": "high" if total_depth > 1000 else "medium" if total_depth > 100 else "low"
            },
            "system_status": {
                "redis_connected": True,
                "timestamp": time.time()
            }
        }
    except Exception as e:
        return {
            "error": str(e),
            "system_status": {
                "redis_connected": False,
                "timestamp": time.time()
            }
        }

# Middleware helper for automatic request tracking
class MetricsMiddleware:
    """Middleware to automatically track request metrics."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            path = scope["path"]
            method = scope["method"]
            
            start_time = time.time()
            
            async def send_wrapper(message):
                if message["type"] == "http.response.start":
                    status_code = message["status"]
                    processing_duration = time.time() - start_time
                    
                    # Track request
                    status = "success" if 200 <= status_code < 400 else "error"
                    track_request(f"{method} {path}", status)
                    
                    # Track processing time
                    if path.startswith("/api/v1/"):
                        processing_time.labels(request_type="api_request").observe(processing_duration)
                
                await send(message)
            
            await self.app(scope, receive, send_wrapper)
        else:
            await self.app(scope, receive, send)