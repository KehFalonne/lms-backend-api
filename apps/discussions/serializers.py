from rest_framework import serializers

from apps.accounts.serializers import UserSerializer
from .models import DiscussionForum, DiscussionPost, DiscussionTopic


class DiscussionForumSerializer(serializers.ModelSerializer):
    course_offering_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)
    topic_count = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionForum
        fields = [
            "id",
            "course_offering_id",
            "title",
            "description",
            "is_locked",
            "created_by",
            "topic_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "topic_count",
            "created_at",
            "updated_at",
        ]

    def get_topic_count(self, obj) -> int:
        return obj.topics.filter(deleted_at__isnull=True).count()


class DiscussionPostSerializer(serializers.ModelSerializer):
    author = UserSerializer(read_only=True)
    reply_count = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionPost
        fields = [
            "id",
            "topic",
            "parent_post",
            "body",
            "author",
            "reply_count",
            "is_edited",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "topic",
            "parent_post",
            "author",
            "reply_count",
            "is_edited",
            "created_at",
            "updated_at",
        ]

    def get_reply_count(self, obj) -> int:
        return obj.replies.filter(deleted_at__isnull=True).count()


class DiscussionTopicSerializer(serializers.ModelSerializer):
    forum_id = serializers.UUIDField(write_only=True, required=False)
    created_by = UserSerializer(read_only=True)
    post_count = serializers.SerializerMethodField()

    class Meta:
        model = DiscussionTopic
        fields = [
            "id",
            "forum_id",
            "title",
            "body",
            "is_pinned",
            "is_locked",
            "is_edited",
            "created_by",
            "post_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_by",
            "post_count",
            "is_edited",
            "created_at",
            "updated_at",
        ]

    def get_post_count(self, obj) -> int:
        return obj.posts.filter(deleted_at__isnull=True).count()


class DiscussionTopicDetailSerializer(DiscussionTopicSerializer):
    posts = serializers.SerializerMethodField()

    class Meta(DiscussionTopicSerializer.Meta):
        fields = DiscussionTopicSerializer.Meta.fields + ["posts"]

    def get_posts(self, obj):
        root_posts = obj.posts.filter(
            parent_post__isnull=True, deleted_at__isnull=True
        ).order_by("created_at")
        return DiscussionPostSerializer(root_posts, many=True).data
