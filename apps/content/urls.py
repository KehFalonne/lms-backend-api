from django.urls import path

from .api.content_views import (
    ContentItemDetailView,
    ContentPublishView,
    ContentUnpublishView,
    ModuleContentListCreateView,
)
from .api.module_views import (
    ModuleDetailView,
    OfferingModuleListCreateView,
    MyContentTreeView,
)

urlpatterns = [
    # Modules (nested under offering)
    path(
        "course-offerings/<uuid:offering_id>/modules/",
        OfferingModuleListCreateView.as_view(),
        name="offering-modules",
    ),
    path("modules/<uuid:pk>/", ModuleDetailView.as_view(), name="module-detail"),
    # Content (nested under module)
    path(
        "modules/<uuid:module_id>/content/",
        ModuleContentListCreateView.as_view(),
        name="module-content",
    ),
    path("content/<uuid:pk>/", ContentItemDetailView.as_view(), name="content-detail"),
    path(
        "content/<uuid:pk>/publish/",
        ContentPublishView.as_view(),
        name="content-publish",
    ),
    path(
        "content/<uuid:pk>/unpublish/",
        ContentUnpublishView.as_view(),
        name="content-unpublish",
    ),
    path(
        "my/course-offerings/<uuid:offering_id>/content-tree/",
        MyContentTreeView.as_view(),
        name="my-content-tree",
    ),
]
