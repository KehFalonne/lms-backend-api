"""
File upload/download endpoints (backend doc §23).

Flow:
    1. Client calls POST /files/upload-url/ → gets a presigned upload URL
    2. Client uploads the binary directly to that URL
    3. Client calls POST /files/complete/ to mark the file READY
    4. Downloads go through GET /files/{id}/download-url/

For LOCAL provider, upload/download are proxied through Django using
HMAC-signed URLs (dev-only convenience).
"""

import io
import mimetypes

from django.http import FileResponse, HttpResponse
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from apps.common.responses import error_response, success_response
from apps.files.models import File, FileStatus
from apps.files.services.file_service import FileService
from apps.files.storage import (
    local_open,
    save_local_upload,
    verify_local_signature,
)

# ──────────────────────────────────────────────────────────────────────
# Client-facing API
# ──────────────────────────────────────────────────────────────────────


class RequestUploadView(APIView):
    """POST /api/v1/files/upload-url/"""

    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        filename = request.data.get("filename")
        size_bytes = request.data.get("sizeBytes") or request.data.get("size_bytes")
        mime_type = request.data.get("mimeType") or request.data.get("mime_type")
        prefix = request.data.get("prefix", "uploads")

        if not filename or not size_bytes:
            return error_response(
                "filename and sizeBytes are required.", status_code=400
            )

        try:
            payload = FileService.request_upload(
                user=request.user,
                filename=filename,
                size_bytes=int(size_bytes),
                mime_type=mime_type,
                prefix=prefix,
            )
        except Exception as exc:
            message = getattr(exc, "detail", str(exc))
            if isinstance(message, dict):
                message = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in message.items()
                )
            return error_response(str(message), status_code=400)

        return success_response(data=payload, message="Upload target created.")


class CompleteUploadView(APIView):
    """POST /api/v1/files/complete/"""

    serializer_class = None
    permission_classes = [IsAuthenticated]

    def post(self, request):
        file_id = request.data.get("fileId") or request.data.get("file_id")
        if not file_id:
            return error_response("fileId is required.", status_code=400)

        try:
            file = FileService.complete_upload(user=request.user, file_id=file_id)
        except Exception as exc:
            message = getattr(exc, "detail", str(exc))
            if isinstance(message, dict):
                message = "; ".join(
                    f"{k}: {', '.join(v) if isinstance(v, list) else v}"
                    for k, v in message.items()
                )
            return error_response(str(message), status_code=400)

        return success_response(
            data={
                "id": str(file.id),
                "originalName": file.original_name,
                "sizeBytes": file.size_bytes,
                "mimeType": file.mime_type,
                "status": file.status,
            },
            message="Upload confirmed.",
        )


class DownloadUrlView(APIView):
    """GET /api/v1/files/{id}/download-url/"""

    serializer_class = None
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        file = File.objects.filter(pk=pk, status=FileStatus.READY).first()
        if not file:
            return error_response("File not found.", status_code=404)

        try:
            url = FileService.get_download_url(file)
        except Exception as exc:
            message = getattr(exc, "detail", str(exc))
            return error_response(str(message), status_code=400)

        return success_response(data={"downloadUrl": url, "expiresIn": 600})


class FileDeleteView(APIView):
    """DELETE /api/v1/files/{id}/"""

    serializer_class = None
    permission_classes = [IsAuthenticated]

    def delete(self, request, pk):
        file = File.objects.filter(pk=pk, uploaded_by=request.user).first()
        if not file:
            return error_response("File not found.", status_code=404)
        FileService.soft_delete(file)
        return success_response(message="File deleted.")


# ──────────────────────────────────────────────────────────────────────
# Local dev endpoints (only used when STORAGE_PROVIDER=LOCAL)
# ──────────────────────────────────────────────────────────────────────


class LocalUploadView(APIView):
    """
    PUT /api/v1/files/local-upload/?key=<storage_key>&sig=<hmac>

    Accepts either a multipart `file` upload or a raw body.
    """

    serializer_class = None
    permission_classes = []
    authentication_classes = []

    def put(self, request):
        key = request.query_params.get("key")
        sig = request.query_params.get("sig")

        if not key or not sig or not verify_local_signature(key, sig):
            return HttpResponse(status=403)

        uploaded = request.FILES.get("file")
        if uploaded is not None:
            save_local_upload(key, uploaded)
        elif request.body:
            save_local_upload(key, io.BytesIO(request.body))
        else:
            return HttpResponse(status=400)

        return HttpResponse(status=204)


class LocalDownloadView(APIView):
    """GET /api/v1/files/local-download/?key=<storage_key>&sig=<hmac>"""

    serializer_class = None
    permission_classes = []
    authentication_classes = []

    def get(self, request):
        key = request.query_params.get("key")
        sig = request.query_params.get("sig")

        if not key or not sig or not verify_local_signature(key, sig):
            return HttpResponse(status=403)

        try:
            fh = local_open(key)
        except FileNotFoundError:
            return HttpResponse(status=404)

        response = FileResponse(
            fh,
            content_type=mimetypes.guess_type(key)[0] or "application/octet-stream",
        )
        response["Accept-Ranges"] = "bytes"
        return response
