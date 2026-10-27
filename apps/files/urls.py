from django.urls import path

from .api.file_views import (
    CompleteUploadView,
    DownloadUrlView,
    FileDeleteView,
    LocalDownloadView,
    LocalUploadView,
    RequestUploadView,
)

urlpatterns = [
    path("files/upload-url/", RequestUploadView.as_view(), name="file-upload-url"),
    path("files/complete/", CompleteUploadView.as_view(), name="file-complete"),
    path(
        "files/<uuid:pk>/download-url/",
        DownloadUrlView.as_view(),
        name="file-download-url",
    ),
    path("files/<uuid:pk>/", FileDeleteView.as_view(), name="file-delete"),
    # Local dev endpoints
    path("files/local-upload/", LocalUploadView.as_view(), name="file-local-upload"),
    path(
        "files/local-download/", LocalDownloadView.as_view(), name="file-local-download"
    ),
]
