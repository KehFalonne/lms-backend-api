import pytest
from django.http import Http404
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from apps.common.exceptions.handlers import global_exception_handler
from apps.common.responses import success_response


@pytest.mark.django_db
class TestResponses:
    def test_success_response_shape(self):
        res = success_response(data={"a": 1}, message="ok")
        assert res.data["success"] is True
        assert res.data["message"] == "ok"
        assert res.data["data"] == {"a": 1}
        assert res.data["meta"] is None
        assert res.status_code == 200


@pytest.mark.django_db
class TestExceptionHandler:
    def _context(self):
        return {"request": APIRequestFactory().get("/api/v1/x/"), "view": APIView()}

    def test_validation_error_envelope(self):
        res = global_exception_handler(
            ValidationError({"email": ["Invalid."]}),
            self._context(),
        )
        assert res.status_code == 400
        assert res.data["success"] is False
        assert res.data["statusCode"] == 400
        assert "email" in res.data["errors"]
        assert "path" in res.data
        assert "timestamp" in res.data

    def test_not_found_envelope(self):
        res = global_exception_handler(NotFound(), self._context())
        assert res.status_code == 404
        assert res.data["success"] is False
        assert res.data["statusCode"] == 404

    def test_django_404_maps_to_404(self):
        res = global_exception_handler(Http404(), self._context())
        assert res.status_code == 404
        assert res.data["statusCode"] == 404

    def test_unknown_error_maps_to_500(self):
        res = global_exception_handler(RuntimeError("boom"), self._context())
        assert res.status_code == 500
        assert res.data["message"] == "An unexpected error occurred."
        # Never leak internal detail
        assert "boom" not in str(res.data)
