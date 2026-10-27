from rest_framework.views import APIView

from apps.accounts.permissions import IsAuthenticatedAndActive
from apps.analytics.services.dashboard_service import DashboardService
from apps.common.responses import success_response
from rest_framework.permissions import IsAdminUser


class StudentDashboardView(APIView):
    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        return success_response(data=DashboardService.student_dashboard(request.user))


class LecturerDashboardView(APIView):
    serializer_class = None
    permission_classes = [IsAuthenticatedAndActive]

    def get(self, request):
        return success_response(data=DashboardService.lecturer_dashboard(request.user))


class AdminDashboardView(APIView):
    serializer_class = None
    permission_classes = [IsAdminUser]

    def get(self, request):
        return success_response(data=DashboardService.admin_dashboard())


class AdminStatsView(APIView):
    serializer_class = None
    permission_classes = [IsAdminUser]

    def get(self, request):
        data = DashboardService.admin_dashboard()
        return success_response(data=data["totals"])
