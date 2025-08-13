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
        'run-orchestrator-every-15-seconds': {
            'task': 'tasks.orchestrator_task',
            'schedule': 15.0,
        },
        'check-batches-every-10-seconds': {
            'task': 'tasks.check_batch_status_task',
            'schedule': 10.0,
        },
    },
    timezone='UTC',
)
