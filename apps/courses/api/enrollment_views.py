from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.models import (
    CourseEnrollment,
    CourseOffering,
    EnrollmentStatus,
    OfferingStatus,
)
from apps.courses.serializers import (
    BulkEnrollSerializer,
    CourseEnrollmentSerializer,
    MyCourseEnrollmentSerializer,
)


class OfferingEnrollmentListCreateView(APIView):
    """
    GET  /api/v1/course-offerings/{offering_id}/enrollments/
    POST /api/v1/course-offerings/{offering_id}/enrollments/
    """

    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)

        # Staff, superusers, and instructors of this offering see all enrollments.
        # Everyone else (students) sees only their own.
        from apps.courses.models import CourseInstructor

        is_staff_user = request.user.is_staff or request.user.is_superuser
        is_instructor = CourseInstructor.objects.filter(
            course_offering=offering,
            user=request.user,
        ).exists()

        if is_staff_user or is_instructor:
            qs = offering.enrollments.select_related("student").order_by(
                "student__last_name", "student__first_name"
            )
        else:
            qs = offering.enrollments.filter(student=request.user)

        return success_response(data=CourseEnrollmentSerializer(qs, many=True).data)

    @transaction.atomic
    def post(self, request, offering_id):
        if not request.user.is_staff and not request.user.is_superuser:
            return error_response("Only staff can enroll students.", status_code=403)

        offering = get_object_or_404(CourseOffering, pk=offering_id)

        if offering.status not in (OfferingStatus.ACTIVE, OfferingStatus.DRAFT):
            return error_response(
                f"Cannot enroll into a {offering.status} offering.",
                status_code=400,
            )

        serializer = CourseEnrollmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Capacity check under lock
        offering = CourseOffering.objects.select_for_update().get(pk=offering.pk)
        if offering.is_full:
            return error_response("Course is at full capacity.", status_code=409)

        student_id = serializer.validated_data.pop("student_id")
        try:
            student = User.objects.get(pk=student_id, is_active=True)
        except User.DoesNotExist:
            return error_response("Student not found.", status_code=400)

        if CourseEnrollment.objects.filter(
            course_offering=offering, student=student
        ).exists():
            return error_response(
                "Student is already enrolled in this offering.",
                status_code=409,
            )

        enrollment = CourseEnrollment.objects.create(
            course_offering=offering,
            student=student,
            **serializer.validated_data,
        )
        return success_response(
            data=CourseEnrollmentSerializer(enrollment).data,
            message="Student enrolled successfully.",
            status=status.HTTP_201_CREATED,
        )


class OfferingBulkEnrollView(APIView):
    """
    POST /api/v1/course-offerings/{offering_id}/enrollments/bulk/
    """

    serializer_class = BulkEnrollSerializer
    permission_classes = [IsAuthenticatedAndActive]

    @transaction.atomic
    def post(self, request, offering_id):
        if not request.user.is_staff and not request.user.is_superuser:
            return error_response("Only staff can bulk enroll.", status_code=403)

        offering = CourseOffering.objects.select_for_update().get(pk=offering_id)

        serializer = BulkEnrollSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        student_ids = serializer.validated_data["student_ids"]

        existing = set(offering.enrollments.values_list("student_id", flat=True))
        to_create_ids = [sid for sid in student_ids if sid not in existing]

        # Capacity guard
        slots_left = offering.capacity - len(existing)
        if len(to_create_ids) > slots_left:
            return error_response(
                f"Not enough capacity — {len(to_create_ids)} requested, {slots_left} slots left.",
                status_code=409,
            )

        students = list(User.objects.filter(pk__in=to_create_ids, is_active=True))
        created = []
        for student in students:
            created.append(
                CourseEnrollment(
                    course_offering=offering,
                    student=student,
                    status=EnrollmentStatus.ACTIVE,
                )
            )
        CourseEnrollment.objects.bulk_create(created)

        return success_response(
            data={
                "created": len(created),
                "skipped": len(student_ids) - len(created),
            },
            message=f"{len(created)} students enrolled.",
            status=status.HTTP_201_CREATED,
        )


class EnrollmentDeleteView(APIView):
    """
    DELETE /api/v1/course-offerings/{offering_id}/enrollments/{student_id}/
    """

    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def delete(self, request, offering_id, student_id):
        if not request.user.is_staff and not request.user.is_superuser:
            return error_response("Only staff can remove enrollments.", status_code=403)

        enrollment = get_object_or_404(
            CourseEnrollment,
            course_offering_id=offering_id,
            student_id=student_id,
        )
        enrollment.delete()
        return success_response(message="Enrollment removed.")


class MyCoursesView(APIView):
    """GET /api/v1/my/courses/ — student's active enrollments."""

    serializer_class = MyCourseEnrollmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        qs = (
            CourseEnrollment.objects.filter(student=request.user)
            .exclude(status=EnrollmentStatus.WITHDRAWN)
            .select_related(
                "course_offering",
                "course_offering__course",
                "course_offering__semester",
                "course_offering__programme",
            )
            .order_by("-enrolled_at")
        )
        return success_response(data=MyCourseEnrollmentSerializer(qs, many=True).data)


class MyCourseOfferingView(APIView):
    """
    GET /api/v1/my/course-offerings/{offering_id}/
    """

    serializer_class = CourseEnrollmentSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, offering_id):
        enrollment = get_object_or_404(
            CourseEnrollment,
            course_offering_id=offering_id,
            student=request.user,
        )
        return success_response(data=CourseEnrollmentSerializer(enrollment).data)
