"""
Standard pagination — response shape matches backend architecture doc §13:

{
  "success": true,
  "message": "...",
  "data": [...],
  "meta": {"page": 1, "pageSize": 20, "total": 150, "totalPages": 8}
}
"""

from collections import OrderedDict

from rest_framework.pagination import PageNumberPagination


class StandardPageNumberPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = "pageSize"
    max_page_size = 200

    def get_paginated_response(self, data):
        return _paginated_response(data, self)


def _paginated_response(data, paginator):
    from rest_framework.response import Response

    return Response(
        OrderedDict(
            [
                ("success", True),
                ("message", "Retrieved successfully"),
                ("data", data),
                (
                    "meta",
                    OrderedDict(
                        [
                            ("page", paginator.page.number),
                            ("pageSize", paginator.get_page_size(paginator.request)),
                            ("total", paginator.page.paginator.count),
                            ("totalPages", paginator.page.paginator.num_pages),
                        ]
                    ),
                ),
            ]
        )
    )
