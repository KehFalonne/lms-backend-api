from django.urls import path

from .api.forum_views import ForumDetailView, OfferingForumListCreateView
from .api.post_views import PostDetailView, TopicPostListCreateView
from .api.topic_views import ForumTopicListCreateView, TopicDetailView

urlpatterns = [
    path(
        "course-offerings/<uuid:offering_id>/forums/",
        OfferingForumListCreateView.as_view(),
        name="offering-forums",
    ),
    path("forums/<uuid:pk>/", ForumDetailView.as_view(), name="forum-detail"),
    path(
        "forums/<uuid:forum_id>/topics/",
        ForumTopicListCreateView.as_view(),
        name="forum-topics",
    ),
    path("topics/<uuid:pk>/", TopicDetailView.as_view(), name="topic-detail"),
    path(
        "topics/<uuid:topic_id>/posts/",
        TopicPostListCreateView.as_view(),
        name="topic-posts",
    ),
    path("posts/<uuid:pk>/", PostDetailView.as_view(), name="post-detail"),
]
