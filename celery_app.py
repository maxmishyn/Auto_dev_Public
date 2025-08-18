from celery import Celery
from config import settings

celery = Celery(
    __name__,
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=['tasks']
)

celery.conf.update(
    task_track_started=True,
    beat_schedule={
        'run-orchestrator-with-dynamic-batching': {
            'task': 'tasks.orchestrator_task',
            'schedule': 3.0,  # Check every 3 seconds, but orchestrator implements dynamic intervals internally
        },
        'check-batches-every-10-seconds': {
            'task': 'tasks.check_batch_status_task',
            'schedule': 10.0,
        },
        'log-dynamic-batch-stats-every-minute': {
            'task': 'tasks.get_dynamic_batch_stats',
            'schedule': 60.0,  # Log stats every minute for monitoring
        },
    },
    timezone='UTC',
)
