"""
Background recompute tasks (backend doc §34 — "Analytics Tasks").
"""

from celery import shared_task

from apps.analytics.services.progress_service import ProgressService


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
    ignore_result=True,
)
def recompute_student_progress(self, student_id: str, course_offering_id: str):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    try:
        student = User.objects.get(pk=student_id)
    except User.DoesNotExist:
        return
    ProgressService.recompute(student=student, course_offering_id=course_offering_id)
