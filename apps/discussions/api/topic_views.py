from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.courses.permissions import CanManageCourseContent
from apps.discussions.models import DiscussionForum, DiscussionTopic
from apps.discussions.serializers import (
    DiscussionTopicDetailSerializer,
    DiscussionTopicSerializer,
)


class ForumTopicListCreateView(APIView):
    """GET/POST /api/v1/forums/{forum_id}/topics/"""

    serializer_class = DiscussionTopicSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, forum_id):
        forum = get_object_or_404(DiscussionForum, pk=forum_id)
        qs = forum.topics.filter(deleted_at__isnull=True)
        return success_response(data=DiscussionTopicSerializer(qs, many=True).data)

    def post(self, request, forum_id):
        forum = get_object_or_404(DiscussionForum, pk=forum_id)
        if forum.is_locked:
            return error_response("This forum is locked.", status_code=400)
        serializer = DiscussionTopicSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.validated_data.pop("forum_id", None)
        topic = DiscussionTopic.objects.create(
            forum=forum,
            created_by=request.user,
            **serializer.validated_data,
        )
        return success_response(
            data=DiscussionTopicSerializer(topic).data,
            message="Topic created.",
            status=status.HTTP_201_CREATED,
        )


class TopicDetailView(APIView):
    """GET/PATCH/DELETE /api/v1/topics/{id}/"""

    serializer_class = DiscussionTopicDetailSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk):
        return get_object_or_404(DiscussionTopic, pk=pk, deleted_at__isnull=True)

    def get(self, request, pk):
        topic = self._get(pk)
        return success_response(data=DiscussionTopicDetailSerializer(topic).data)

    def patch(self, request, pk):
        topic = self._get(pk)
        is_author = topic.created_by_id == request.user.id
        is_moderator = request.user.is_staff or request.user.is_superuser
        if not (is_author or is_moderator):
            return error_response("Not allowed.", status_code=403)

        # Authors can only edit title/body
        allowed_fields = {"title", "body", "is_pinned", "is_locked"}
        if not is_moderator:
            allowed_fields = {"title", "body"}

        payload = {k: v for k, v in request.data.items() if k in allowed_fields}
        serializer = DiscussionTopicSerializer(topic, data=payload, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save(is_edited=True)
        return success_response(data=DiscussionTopicSerializer(topic).data)

    def delete(self, request, pk):
        topic = self._get(pk)
        is_author = topic.created_by_id == request.user.id
        is_moderator = request.user.is_staff or request.user.is_superuser
        if not (is_author or is_moderator):
            return error_response("Not allowed.", status_code=403)
        from django.utils import timezone

        topic.deleted_at = timezone.now()
        topic.save(update_fields=["deleted_at", "updated_at"])
        return success_response(message="Topic deleted.")
