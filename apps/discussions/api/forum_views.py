from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import success_response
from apps.courses.models import CourseOffering
from apps.courses.permissions import CanManageCourseContent
from apps.discussions.models import DiscussionForum
from apps.discussions.serializers import DiscussionForumSerializer


class OfferingForumListCreateView(APIView):
    """GET/POST /api/v1/course-offerings/{offering_id}/forums/"""

    serializer_class = DiscussionForumSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get_permissions(self):
        if self.request.method == "POST":
            return [IsAuthenticatedAndActive(), CanManageCourseContent()]
        return super().get_permissions()

    def get(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        qs = offering.forums.all()
        return success_response(data=DiscussionForumSerializer(qs, many=True).data)

    def post(self, request, offering_id):
        offering = get_object_or_404(CourseOffering, pk=offering_id)
        self.check_object_permissions(request, offering)
        serializer = DiscussionForumSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        forum = DiscussionForum.objects.create(
            course_offering=offering,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=DiscussionForumSerializer(forum).data,
            message="Forum created.",
            status=status.HTTP_201_CREATED,
        )


class ForumDetailView(APIView):
    """PATCH/DELETE /api/v1/forums/{id}/"""

    serializer_class = DiscussionForumSerializer
    permission_classes = [IsAuthenticatedAndActive, CanManageCourseContent]

    def patch(self, request, pk):
        forum = get_object_or_404(DiscussionForum, pk=pk)
        self.check_object_permissions(request, forum.course_offering)
        serializer = DiscussionForumSerializer(forum, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("course_offering_id", None)
        serializer.save()
        return success_response(data=DiscussionForumSerializer(forum).data)

    def delete(self, request, pk):
        forum = get_object_or_404(DiscussionForum, pk=pk)
        self.check_object_permissions(request, forum.course_offering)
        forum.delete()
        return success_response(message="Forum deleted.")
