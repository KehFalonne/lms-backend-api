"""
Seeds a course offering + instructor + enrolled student for dev.

Prerequisite: run `seed_academic_structure` and `seed_users` first.

Usage:
    python manage.py seed_course_delivery
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.academics.models import Semester
from apps.courses.models import (
    Course,
    CourseEnrollment,
    CourseInstructor,
    CourseOffering,
    EnrollmentStatus,
    OfferingStatus,
    TeachingRole,
)
from apps.university.models import Programme

User = get_user_model()


class Command(BaseCommand):
    help = "Seed a demo course offering with instructor and enrolled student."

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            semester = Semester.objects.get(is_current=True)
        except Semester.DoesNotExist:
            self.stderr.write(self.style.ERROR("Run seed_academic_structure first."))
            return

        try:
            course = Course.objects.get(code="CSC301")
            programme = Programme.objects.get(code="BSC-CS")
        except (Course.DoesNotExist, Programme.DoesNotExist):
            self.stderr.write(self.style.ERROR("Run seed_academic_structure first."))
            return

        offering, created = CourseOffering.objects.update_or_create(
            course=course,
            semester=semester,
            programme=programme,
            section="A",
            defaults={
                "capacity": 100,
                "status": OfferingStatus.ACTIVE,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"  {'Created' if created else 'Reused'} offering: {offering}"
            )
        )

        # Instructor
        lecturer = User.objects.filter(email="lecturer@graciousuniversity.edu").first()
        if lecturer:
            CourseInstructor.objects.update_or_create(
                course_offering=offering,
                user=lecturer,
                teaching_role=TeachingRole.PRIMARY_INSTRUCTOR,
                defaults={
                    "can_manage_content": True,
                    "can_grade": True,
                    "can_manage_assessments": True,
                    "can_manage_students": True,
                },
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ Instructor: {lecturer.email}"))

        # Student
        student = User.objects.filter(email="student@graciousuniversity.edu").first()
        if student:
            CourseEnrollment.objects.get_or_create(
                course_offering=offering,
                student=student,
                defaults={"status": EnrollmentStatus.ACTIVE},
            )
            self.stdout.write(self.style.SUCCESS(f"  ✓ Enrolled: {student.email}"))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Course delivery seed complete."))
