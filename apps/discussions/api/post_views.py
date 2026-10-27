"""
Discussion post endpoints.

- GET  /topics/{topic_id}/posts/ — list all posts (flat)
- POST /topics/{topic_id}/posts/ — create a post or reply
- PATCH /posts/{id}/             — edit (author or staff)
- DELETE /posts/{id}/            — soft-delete (author or staff)
"""

from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.common.responses import error_response, success_response
from apps.discussions.models import DiscussionPost, DiscussionTopic
from apps.discussions.serializers import DiscussionPostSerializer


class TopicPostListCreateView(APIView):
    """GET/POST /api/v1/topics/{topic_id}/posts/"""

    serializer_class = DiscussionPostSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request, topic_id):
        topic = get_object_or_404(DiscussionTopic, pk=topic_id, deleted_at__isnull=True)
        qs = (
            topic.posts.filter(deleted_at__isnull=True)
            .select_related("author")
            .order_by("created_at")
        )
        return success_response(data=DiscussionPostSerializer(qs, many=True).data)

    def post(self, request, topic_id):
        topic = get_object_or_404(DiscussionTopic, pk=topic_id, deleted_at__isnull=True)
        if topic.is_locked:
            return error_response("This topic is locked.", status_code=400)

        parent_id = request.data.get("parentPost") or request.data.get("parent_post")
        body = (request.data.get("body") or "").strip()

        if not body:
            return error_response("Body is required.", status_code=400)

        post = DiscussionPost.objects.create(
            topic=topic,
            parent_post_id=parent_id,
            author=request.user,
            body=body,
        )

        # ── Notify relevant participants ──────────────────────────
        try:
            from apps.notifications.services.notification_service import (
                NotificationService,
            )
            from django.contrib.auth import get_user_model

            User = get_user_model()
            recipients: dict[str, str] = {}

            # Notify the topic creator
            if topic.created_by_id and topic.created_by_id != request.user.id:
                recipients[str(topic.created_by_id)] = (
                    f"{request.user.first_name} replied to your topic "
                    f"“{topic.title}”"
                )

            # Notify the parent post author
            if post.parent_post_id:
                parent = (
                    DiscussionPost.objects.filter(pk=post.parent_post_id)
                    .only("author_id")
                    .first()
                )
                if (
                    parent
                    and parent.author_id
                    and parent.author_id != request.user.id
                    and str(parent.author_id) not in recipients
                ):
                    recipients[str(parent.author_id)] = (
                        f"{request.user.first_name} replied to your post in "
                        f"“{topic.title}”"
                    )

            for user_id, message in recipients.items():
                recipient = User.objects.filter(pk=user_id, is_active=True).first()
                if not recipient:
                    continue
                NotificationService.push(
                    recipient=recipient,
                    type="DISCUSSION",
                    title="New reply",
                    message=message,
                    entity_type="topic",
                    entity_id=topic.id,
                    data={
                        "topicId": str(topic.id),
                        "forumId": str(topic.forum_id),
                        "courseOfferingId": str(topic.forum.course_offering_id),
                    },
                )
        except Exception:
            pass  # Never block posting on a notification failure

        # ── Broadcast a lightweight event so other viewers update live ──
        try:
            from asgiref.sync import async_to_sync
            from channels.layers import get_channel_layer
            from apps.courses.models import (
                CourseEnrollment,
                CourseInstructor,
                EnrollmentStatus,
            )

            layer = get_channel_layer()
            if layer:
                offering_id = topic.forum.course_offering_id

                student_ids = set(
                    CourseEnrollment.objects.filter(
                        course_offering_id=offering_id,
                        status=EnrollmentStatus.ACTIVE,
                    ).values_list("student_id", flat=True)
                )

                instructor_ids = set(
                    CourseInstructor.objects.filter(
                        course_offering_id=offering_id,
                    ).values_list("user_id", flat=True)
                )

                recipient_ids = student_ids | instructor_ids

                payload = {
                    "topicId": str(topic.id),
                    "postId": str(post.id),
                    "forumId": str(topic.forum_id),
                    "courseOfferingId": str(offering_id),
                    "authorId": str(request.user.id),
                    "parentPostId": (
                        str(post.parent_post_id) if post.parent_post_id else None
                    ),
                }

                for uid in recipient_ids:
                    async_to_sync(layer.group_send)(
                        f"user_{uid}",
                        {
                            "type": "discussion.post_created",
                            "payload": payload,
                        },
                    )
        except Exception:
            pass  # Never block posting on a broadcast failure

        return success_response(
            data=DiscussionPostSerializer(post).data,
            message="Post created.",
            status=status.HTTP_201_CREATED,
        )


class PostDetailView(APIView):
    """PATCH/DELETE /api/v1/posts/{id}/"""

    serializer_class = DiscussionPostSerializer
    permission_classes = [IsAuthenticatedAndActive]

    def _get(self, pk):
        return get_object_or_404(DiscussionPost, pk=pk, deleted_at__isnull=True)

    def patch(self, request, pk):
        post = self._get(pk)
        if post.author_id != request.user.id and not request.user.is_staff:
            return error_response("Not allowed.", status_code=403)
        body = (request.data.get("body") or "").strip()
        if not body:
            return error_response("Body is required.", status_code=400)
        post.body = body
        post.is_edited = True
        post.save(update_fields=["body", "is_edited", "updated_at"])
        return success_response(data=DiscussionPostSerializer(post).data)

    def delete(self, request, pk):
        post = self._get(pk)
        if post.author_id != request.user.id and not request.user.is_staff:
            return error_response("Not allowed.", status_code=403)
        post.deleted_at = timezone.now()
        post.save(update_fields=["deleted_at", "updated_at"])
        return success_response(message="Post deleted.")
