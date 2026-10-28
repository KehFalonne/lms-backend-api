import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("gu_lms")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()
app.conf.beat_schedule = {
    "expire-stuck-assessment-attempts": {
        "task": "apps.assessments.tasks.expire_tasks.expire_stuck_assessment_attempts",
        "schedule": 60.0,  # every minute
    },
}


@app.task(bind=True, ignore_reslts=True)
def debug_task(self):
    print(f"Celery request: {self.request!r}")
