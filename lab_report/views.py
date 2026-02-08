from django.http import FileResponse, Http404
from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from .models import LabReport

class LabReportPublicDownloadView(APIView):
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            report = LabReport.objects.select_related("product").get(
                public_token=token,
                is_active=True,
            )
        except LabReport.DoesNotExist:
            raise Http404("Invalid or expired lab report")

        return FileResponse(
            report.report_file.open(),
            filename=f"{report.product.name}_batch_{report.batch_number}_lab_report.pdf",
        )
