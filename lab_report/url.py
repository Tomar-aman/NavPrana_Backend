from django.urls import path
from .views import LabReportPublicDownloadView

urlpatterns = [
    path("<uuid:token>/",LabReportPublicDownloadView.as_view(),name="lab_report_public_download"),
]