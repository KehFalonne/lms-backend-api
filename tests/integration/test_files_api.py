import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient

from apps.files.models import File, FileStatus

User = get_user_model()
pytestmark = pytest.mark.django_db

UPLOAD_URL = "/api/v1/files/upload-url/"
COMPLETE_URL = "/api/v1/files/complete/"


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture
def lecturer():
    return User.objects.create_user(
        email="files-lecturer@x.y",
        university_id="GU-FILES-1",
        password="p",
        first_name="F",
        last_name="L",
        status="ACTIVE",
    )


def request_upload(api, prefix=None, **overrides):
    payload = {
        "filename": "notes.pdf",
        "sizeBytes": 1024,
        "mimeType": "application/pdf",
    }
    if prefix is not None:
        payload["prefix"] = prefix
    payload.update(overrides)
    return api.post(UPLOAD_URL, payload, format="json")


@pytest.mark.parametrize(
    ("prefix", "folder"),
    [
        (None, "uploads"),
        ("uploads", "uploads"),
        ("profiles", "profiles"),
        ("materials", "materials"),
        ("submissions", "submissions"),
    ],
)
@override_settings(STORAGE_PROVIDER="LOCAL")
def test_upload_url_uses_folder_prefix(api, lecturer, prefix, folder):
    api.force_authenticate(user=lecturer)
    res = request_upload(api, prefix)
    assert res.status_code == 200, res.content
    data = res.json()["data"]
    assert data["storageKey"].startswith(f"{folder}/")
    file = File.objects.get(id=data["fileId"])
    assert file.status == FileStatus.PENDING
    assert file.original_name == "notes.pdf"


@override_settings(STORAGE_PROVIDER="LOCAL")
def test_upload_url_rejects_unknown_folder(api, lecturer):
    api.force_authenticate(user=lecturer)
    res = request_upload(api, "../../etc")
    assert res.status_code == 400
    assert File.objects.count() == 0


@override_settings(STORAGE_PROVIDER="LOCAL")
def test_complete_upload_requires_binary(api, lecturer):
    api.force_authenticate(user=lecturer)
    res = request_upload(api, "materials")
    file_id = res.json()["data"]["fileId"]
    res2 = api.post(COMPLETE_URL, {"fileId": file_id}, format="json")
    assert res2.status_code == 400
    file = File.objects.get(id=file_id)
    assert file.status == FileStatus.PENDING


def test_upload_url_requires_auth(api):
    res = request_upload(api, "profiles")
    assert res.status_code in (401, 403)
    assert File.objects.count() == 0
